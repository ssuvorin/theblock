"""Self-contained, persistence-neutral LinkedIn export ingestion planner."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from ...domain.identity.normalize import (
    IdentityKind,
    NormalizedIdentity,
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
from .parse import (
    KNOWN_FILES,
    LinkedInArchiveError,
    archive_file,
    field,
    parse_invitations,
    parse_messages,
    read_csv_rows,
)


@dataclass(frozen=True, slots=True)
class ProposedPerson:
    display_name: str
    linkedin_url: str
    is_owner: bool
    evidence: str
    data_origin: str


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
        owner_profile = self._owner_profile(profile_rows)
        owner_url = owner_profile.profile_url if owner_profile else None
        message_rows = self._message_rows(paths)
        invitation_rows = self._invitation_rows(paths)
        messages = tuple(
            normalize_message(
                row,
                owner_profile_url=owner_url,
                data_origin=self._data_origin,
            )
            for row in message_rows
        )
        invitations = tuple(
            normalize_invitation(row, data_origin=self._data_origin) for row in invitation_rows
        )
        identities = self._owner_identities(paths, owner_profile)
        hints = _deduplicate_hints(
            tuple(hint for message in messages for hint in message_identity_hints(message))
            + tuple(hint for invitation in invitations for hint in invitation.identity_hints)
        )
        return LinkedInImportPlan(
            owner_profile=owner_profile,
            owner_identities=identities,
            people=_people_from_messages(messages, owner_profile, self._data_origin),
            messages=messages,
            invitations=invitations,
            identity_hints=hints,
            file_counts=MappingProxyType({name: len(self._rows(paths, name)) for name in paths}),
            warnings=(),
            data_origin=self._data_origin,
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
        return read_csv_rows(path) if path else ()

    def _message_rows(self, paths: Mapping[str, Path]) -> tuple[dict[str, str], ...]:
        path = paths.get("messages.csv")
        return parse_messages(path) if path else ()

    def _invitation_rows(self, paths: Mapping[str, Path]) -> tuple[dict[str, str], ...]:
        path = paths.get("Invitations.csv")
        return parse_invitations(path) if path else ()

    def _owner_profile(
        self,
        rows: tuple[dict[str, str], ...],
    ) -> NormalizedOwnerProfile | None:
        if not rows:
            return None
        return normalize_owner_profile(rows[0], data_origin=self._data_origin)

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
    data_origin: str,
) -> tuple[ProposedPerson, ...]:
    owner_url = owner.profile_url if owner else None
    names: dict[str, tuple[str, str]] = {}
    if owner and owner_url:
        names[owner_url] = (owner.display_name, "owner_profile")
    for message in messages:
        participants = (message.sender, *message.recipients)
        for participant in participants:
            if participant.profile_url and participant.profile_url not in names:
                names[participant.profile_url] = (participant.display_name, "message")
    return tuple(
        ProposedPerson(
            display_name=name,
            linkedin_url=url,
            is_owner=url == owner_url,
            evidence=evidence,
            data_origin=data_origin,
        )
        for url, (name, evidence) in sorted(names.items())
    )


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
