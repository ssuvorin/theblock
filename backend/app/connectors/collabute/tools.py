"""Bind only to the Collabute tools this workspace actually exposes.

Tool names are not guessed. They are read from ``tools/list`` at connect time, compared
against the committed fixture, and looked up by role — so a renamed or withdrawn tool
degrades the connection with a readable reason instead of failing mid-sync on a 404.

Every Collabute tool requires a ``context`` argument of 15-25 third-person words, which the
server uses for intent analytics. The canned strings below satisfy that contract and say
truthfully what the CRM is doing, so nothing has to be invented per call site.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# The fixture ships inside the package: only ``backend/`` reaches the container image, so a
# copy under ``specs/`` would be missing exactly where the drift check has to run.
FIXTURE_PATH = Path(__file__).resolve().parent / "tools_list.fixture.json"

PING = "system.ping"
LIST_RECENT = "meeting.list_recent"
GET_MEETING = "meeting.get"
GET_TRANSCRIPT = "meeting.get_transcript"
MEMORY_SEARCH = "memory.search"

# The CRM binds read tools only. Collabute's write tools are all approval-gated proposals
# and none of them can register a meeting, so importing is the entire integration.
REQUIRED_TOOLS: tuple[str, ...] = (LIST_RECENT, GET_MEETING)
OPTIONAL_TOOLS: tuple[str, ...] = (PING, GET_TRANSCRIPT, MEMORY_SEARCH)

CONTEXTS: dict[str, str] = {
    PING: (
        "Verifying Collabute connectivity and tenant resolution during connection setup "
        "so the owner sees an accurate source status."
    ),
    LIST_RECENT: (
        "Importing recent Collabute meetings into the owner relationship graph so meeting "
        "participants and action items become searchable private evidence."
    ),
    GET_MEETING: (
        "Fetching one Collabute meeting with summary, decisions and action items so the "
        "relationship graph can store cited private evidence."
    ),
    GET_TRANSCRIPT: (
        "Reading meeting transcript text so the relationship graph can cite the exact "
        "passage supporting an imported decision or action item."
    ),
    MEMORY_SEARCH: (
        "Searching Collabute workspace memory for prior decisions that explain how the "
        "owner already relates to a company or person."
    ),
}


class ToolUnavailable(RuntimeError):
    """A tool the integration depends on is not present in this workspace."""


@dataclass(frozen=True, slots=True)
class ToolDrift:
    """How the live tool list compares to the fixture the adapter was written against."""

    matches: bool
    missing: tuple[str, ...]
    added: tuple[str, ...]
    required_missing: tuple[str, ...]
    fixture_available: bool = True

    def as_dict(self) -> dict:
        return {
            "matches": self.matches,
            "missing": list(self.missing),
            "added": list(self.added),
            "required_missing": list(self.required_missing),
            "fixture_available": self.fixture_available,
        }


class ToolBinding:
    """The subset of tools this connection may call, and the arguments they demand."""

    def __init__(self, tools: list[dict]) -> None:
        self._available = {
            str(tool.get("name")): tool for tool in tools if isinstance(tool.get("name"), str)
        }

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._available))

    def has(self, name: str) -> bool:
        return name in self._available

    def require(self, name: str) -> str:
        if name not in self._available:
            raise ToolUnavailable(
                f"Collabute workspace does not expose {name}; "
                f"available tools are {', '.join(self.names) or 'none'}"
            )
        return name

    def arguments(self, name: str, **arguments: object) -> dict:
        """Attach the mandatory context and drop unset optional arguments."""

        payload = {key: value for key, value in arguments.items() if value is not None}
        payload["context"] = CONTEXTS.get(name, _generic_context())
        return payload

    def drift(self) -> ToolDrift:
        """Compare live tools to the fixture, never claiming a match we could not check."""

        expected = _fixture_names()
        live = set(self._available)
        required_missing = tuple(name for name in REQUIRED_TOOLS if name not in live)
        if not expected:
            return ToolDrift(False, (), (), required_missing, fixture_available=False)
        missing = tuple(sorted(expected - live))
        added = tuple(sorted(live - expected))
        return ToolDrift(
            matches=not missing and not added,
            missing=missing,
            added=added,
            required_missing=required_missing,
        )

    def capability_summary(self) -> dict:
        drift = self.drift()
        return {
            "tools": list(self.names),
            "bound": [name for name in (*REQUIRED_TOOLS, *OPTIONAL_TOOLS) if self.has(name)],
            "write_access": False,
            "drift": drift.as_dict(),
        }


def _fixture_names() -> set[str]:
    """The committed tool list. A missing fixture must not fail a sync, only drift checks."""

    try:
        body = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    tools = body.get("tools") if isinstance(body, dict) else None
    return {
        str(tool.get("name"))
        for tool in tools or []
        if isinstance(tool, dict) and isinstance(tool.get("name"), str)
    }


def _generic_context() -> str:
    return (
        "Reading Collabute workspace context so the customer relationship graph can store "
        "cited meeting evidence for the owner."
    )
