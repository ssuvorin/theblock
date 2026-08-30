"""Self-contained, persistence-neutral LinkedIn export ingestion planner."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from ...domain.identity.normalize import (
    IdentityKind,
    NormalizedIdentity,
    canonicalize_linkedin_url,
    normalize_identity,
)
from ...services.import_guard import DataOrigin, assert_archive_import_allowed
from .normalize import (
    IdentityHint,
    NormalizedInvitation,
    NormalizedMessage,
    NormalizedOwnerProfile,
    message_identity_hints,
    normalize_invitation,
    normalize_message,
    normalize_owner_profile,
)
from .owner import OwnerResolution, resolve_owner_url
from .parse import (
    CONNECTIONS_HEADER_MARKER,
    KNOWN_FILES,
    LinkedInArchiveError,
    archive_file,
    field,
    is_draft,
    parse_connections,
    parse_invitations,
    parse_messages,
    read_csv_rows,
)

_HEADER_MARKERS = {"Connections.csv": CONNECTIONS_HEADER_MARKER}


@dataclass(frozen=True, slots=True)
class ProposedPerson:
    display_name: str
    linkedin_url: str
    is_owner: bool
    evidence: str
    data_origin: str
    current_title: str | None = None
    current_company: str | None = None


@dataclass(frozen=True, slots=True)
class ConnectionProfile:
    """Company and position for a connection, used only to enrich known people."""

    display_name: str
    title: str | None
    company: str | None


@dataclass(frozen=True, slots=True)
class LinkedInImportPlan:
    owner_profile: NormalizedOwnerProfile | None
    owner_identities: tuple[NormalizedIdentity, ...]
    people: tuple[ProposedPerson, ...]
    messages: tuple[NormalizedMessage, ...]
    invitations: tuple[NormalizedInvitation, ...]
    identity_hints: tuple[IdentityHint, ...]
    file_counts: Mapping[str, int]
    warnings: tuple[str, ...]
    data_origin: str
    owner_resolution_method: str = "unresolved"
    owner_resolution_confidence: str = "none"
    drafts_skipped: int = 0
    connections_seen: int = 0
    connections_matched: int = 0

    @property
    def conversation_count(self) -> int:
        return len({message.conversation_external_id for message in self.messages})

    @property
    def interaction_count(self) -> int:
        return len(self.messages)

    @property
    def empty_message_count(self) -> int:
        return sum(not message.is_chunkable for message in self.messages)

    @property
    def unique_identity_count(self) -> int:
        values = {
            (identity.kind.value, identity.normalized_value) for identity in self.owner_identities
        }
        values.update((hint.kind, hint.normalized_value) for hint in self.identity_hints)
        return len(values)

    @property
    def invitation_identity_match_count(self) -> int:
        message_urls = {
            hint.normalized_value for hint in self.identity_hints if hint.evidence == "message"
        }
        invitation_urls = {
            hint.normalized_value for hint in self.identity_hints if hint.evidence == "invitation"
        }
        return len(message_urls & invitation_urls)


class LinkedInExportImporter:
    """Parse an export into deterministic records without coupling to DB models."""

    def __init__(
        self,
        archive_path: str | Path,
        *,
        data_origin: DataOrigin | str = DataOrigin.REAL_IMPORT,
        demo_mode: bool,
    ) -> None:
        self._archive_path = Path(archive_path)
        self._data_origin = assert_archive_import_allowed(
            data_origin,
            demo_mode=demo_mode,
        ).value

    def build_plan(self) -> LinkedInImportPlan:
        paths = self._known_paths()
        if not paths:
            raise LinkedInArchiveError("archive contains no supported LinkedIn CSV files")
        profile_rows = self._rows(paths, "Profile.csv")
        profile_row = profile_rows[0] if profile_rows else None
        sent_rows, draft_count = self._message_rows(paths)
        invitation_rows = self._invitation_rows(paths)
        resolution = resolve_owner_url(profile_row, sent_rows, invitation_rows)
        owner_url = (
            canonicalize_linkedin_url(resolution.profile_url) if resolution.profile_url else None
        )
        owner_profile = self._owner_profile(profile_row, owner_url)
        messages = tuple(
            normalize_message(
                row,
                owner_profile_url=owner_url,
                data_origin=self._data_origin,
            )
            for row in sent_rows
        )
        invitations = tuple(
            normalize_invitation(row, data_origin=self._data_origin) for row in invitation_rows
        )
        hints = _deduplicate_hints(
            tuple(hint for message in messages for hint in message_identity_hints(message))
            + tuple(hint for invitation in invitations for hint in invitation.identity_hints)
        )
        connections = self._connection_profiles(paths)
        people = _people_from_messages(
            messages,
            owner_profile,
            owner_url,
            self._data_origin,
            connections,
        )
        return LinkedInImportPlan(
            owner_profile=owner_profile,
            owner_identities=self._owner_identities(paths, owner_profile),
            people=people,
            messages=messages,
            invitations=invitations,
            identity_hints=hints,
            file_counts=MappingProxyType({name: len(self._rows(paths, name)) for name in paths}),
            warnings=_plan_warnings(resolution, messages),
            data_origin=self._data_origin,
            owner_resolution_method=resolution.method,
            owner_resolution_confidence=resolution.confidence,
            drafts_skipped=draft_count,
            connections_seen=len(connections),
            connections_matched=sum(1 for person in people if person.current_title),
        )

    def _known_paths(self) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        for filename in KNOWN_FILES:
            located = archive_file(self._archive_path, filename)
            if located is not None:
                paths[filename] = located
        return paths

    def _rows(self, paths: Mapping[str, Path], name: str) -> tuple[dict[str, str], ...]:
        path = paths.get(name)
        if path is None:
            return ()
        return read_csv_rows(path, header_marker=_HEADER_MARKERS.get(name))

    def _message_rows(self, paths: Mapping[str, Path]) -> tuple[tuple[dict[str, str], ...], int]:
        """Return sent messages and the number of unsent drafts that were dropped."""

        path = paths.get("messages.csv")
        rows = parse_messages(path) if path else ()
        sent = tuple(row for row in rows if not is_draft(row))
        return sent, len(rows) - len(sent)

    def _invitation_rows(self, paths: Mapping[str, Path]) -> tuple[dict[str, str], ...]:
        path = paths.get("Invitations.csv")
        return parse_invitations(path) if path else ()

    def _connection_profiles(self, paths: Mapping[str, Path]) -> dict[str, ConnectionProfile]:
        """Index connections by canonical URL so known people can gain a title."""

        path = paths.get("Connections.csv")
        if path is None:
            return {}
        profiles: dict[str, ConnectionProfile] = {}
        for row in parse_connections(path):
            raw_url = field(row, "URL", "Url", "PROFILE URL").strip()
            if not raw_url:
                continue
            first = field(row, "First Name", "FIRST NAME").strip()
            last = field(row, "Last Name", "LAST NAME").strip()
            profiles[canonicalize_linkedin_url(raw_url)] = ConnectionProfile(
                display_name=" ".join(part for part in (first, last) if part),
                title=field(row, "Position", "POSITION").strip() or None,
                company=field(row, "Company", "COMPANY").strip() or None,
            )
        return profiles

    def _owner_profile(
        self,
        row: dict[str, str] | None,
        resolved_url: str | None,
    ) -> NormalizedOwnerProfile | None:
        if row is None:
            return None
        return normalize_owner_profile(
            row,
            data_origin=self._data_origin,
            resolved_profile_url=resolved_url,
        )

    def _owner_identities(
        self,
        paths: Mapping[str, Path],
        profile: NormalizedOwnerProfile | None,
    ) -> tuple[NormalizedIdentity, ...]:
        identities: list[NormalizedIdentity] = []
        if profile and profile.profile_url:
            identities.append(
                normalize_identity(
                    IdentityKind.LINKEDIN_URL,
                    profile.profile_url,
                    source="linkedin_export",
                    is_verified=True,
                    is_primary=True,
                )
            )
        identities.extend(self._email_identities(paths))
        identities.extend(self._phone_identities(paths))
        return _deduplicate_identities(identities)

    def _email_identities(self, paths: Mapping[str, Path]) -> list[NormalizedIdentity]:
        identities: list[NormalizedIdentity] = []
        for row in self._rows(paths, "Email Addresses.csv"):
            raw_value = field(row, "Email Address", "EMAIL ADDRESS").strip()
            if not raw_value:
                continue
            identities.append(
                normalize_identity(
                    IdentityKind.EMAIL,
                    raw_value,
                    source="linkedin_export",
                    is_verified=_csv_boolean(field(row, "Confirmed", "CONFIRMED")),
                    is_primary=_csv_boolean(field(row, "Primary", "PRIMARY")),
                )
            )
        return identities

    def _phone_identities(self, paths: Mapping[str, Path]) -> list[NormalizedIdentity]:
        identities: list[NormalizedIdentity] = []
        for row in self._rows(paths, "PhoneNumbers.csv"):
            raw_value = field(row, "Number", "Phone Number", "PHONE NUMBER").strip()
            if not raw_value:
                continue
            identities.append(
                normalize_identity(
                    IdentityKind.PHONE,
                    raw_value,
                    source="linkedin_export",
                    is_verified=True,
                )
            )
        return identities


def load_linkedin_export(
    archive_path: str | Path,
    *,
    data_origin: DataOrigin | str = DataOrigin.REAL_IMPORT,
    demo_mode: bool,
) -> LinkedInImportPlan:
    return LinkedInExportImporter(
        archive_path,
        data_origin=data_origin,
        demo_mode=demo_mode,
    ).build_plan()


def _people_from_messages(
    messages: tuple[NormalizedMessage, ...],
    owner: NormalizedOwnerProfile | None,
    owner_url: str | None,
    data_origin: str,
    connections: Mapping[str, ConnectionProfile],
) -> tuple[ProposedPerson, ...]:
    """Create people only from message evidence; connections merely add a title.

    A connection list alone proves no interaction, so importing all of it would create
    thousands of people the graph can never cite. Titles are still worth taking.
    """

    names: dict[str, tuple[str, str]] = {}
    if owner and owner_url:
        names[owner_url] = (owner.display_name, "owner_profile")
    for message in messages:
        for participant in (message.sender, *message.recipients):
            if participant.profile_url and participant.profile_url not in names:
                names[participant.profile_url] = (participant.display_name, "message")
    people: list[ProposedPerson] = []
    for url, (name, evidence) in sorted(names.items()):
        connection = connections.get(url)
        is_owner = url == owner_url
        people.append(
            ProposedPerson(
                display_name=name or (connection.display_name if connection else ""),
                linkedin_url=url,
                is_owner=is_owner,
                evidence=evidence,
                data_origin=data_origin,
                current_title=None if is_owner or not connection else connection.title,
                current_company=None if is_owner or not connection else connection.company,
            )
        )
    return tuple(people)


def _plan_warnings(
    resolution: OwnerResolution,
    messages: tuple[NormalizedMessage, ...],
) -> tuple[str, ...]:
    """Surface weak owner evidence instead of silently producing a directionless graph."""

    warnings: list[str] = []
    if not resolution.resolved:
        warnings.append("owner profile URL is unresolved; message direction is unknown")
    elif resolution.confidence == "low":
        warnings.append(f"owner profile URL inferred from {resolution.method} with low confidence")
    if messages and all(message.direction is None for message in messages):
        warnings.append("no message could be assigned a direction")
    return tuple(warnings)


def _deduplicate_hints(hints: tuple[IdentityHint, ...]) -> tuple[IdentityHint, ...]:
    unique: dict[tuple[str, str, str], IdentityHint] = {}
    for hint in hints:
        key = (hint.kind, hint.normalized_value, hint.evidence)
        unique.setdefault(key, hint)
    return tuple(unique[key] for key in sorted(unique))


def _deduplicate_identities(
    identities: list[NormalizedIdentity],
) -> tuple[NormalizedIdentity, ...]:
    unique: dict[tuple[str, str], NormalizedIdentity] = {}
    for identity in identities:
        unique.setdefault((identity.kind.value, identity.normalized_value), identity)
    return tuple(unique[key] for key in sorted(unique))


def _csv_boolean(value: str) -> bool:
    return value.strip().casefold() in {"true", "yes", "1"}
