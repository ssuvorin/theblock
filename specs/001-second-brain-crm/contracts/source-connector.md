# Integration Contract: SourceConnector Protocol

Every source adapter implements this Python protocol. Adding a new source requires only implementing it and registering in the DI container — zero core changes.

```python
from typing import Protocol, runtime_checkable
from enum import Enum

class SourceStatus(str, Enum):
    DISCONNECTED = "disconnected"
    AUTHORIZING = "authorizing"
    CONNECTED = "connected"
    SYNCING = "syncing"
    DEGRADED = "degraded"
    REAUTH_REQUIRED = "reauth_required"
    ERROR = "error"

class SyncMode(str, Enum):
    INITIAL = "initial"
    DELTA = "delta"

@runtime_checkable
class SourceConnector(Protocol):
    """Contract for all source adapters."""

    @property
    def source_type(self) -> str:
        """Extensible string identifier (e.g. 'gmail', 'whatsapp')."""
        ...

    @property
    def capabilities(self) -> dict:
        """Declared capabilities and required scopes/config."""
        ...

    def initiate_auth(self, owner_id: str, redirect_uri: str) -> dict:
        """Start OAuth or connection flow. Returns redirect_url or qr_code."""
        ...

    def handle_callback(self, owner_id: str, code: str, state: str) -> str:
        """Process OAuth callback. Returns connection_id."""
        ...

    def get_status(self, connection_id: str) -> SourceStatus:
        """Current connection state."""
        ...

    def sync(self, connection_id: str, mode: SyncMode) -> str:
        """Trigger initial or delta sync. Returns sync_run_id."""
        ...

    def normalize(self, raw_record: dict, connection_id: str) -> dict:
        """Transform source-native record to canonical schema."""
        ...

    def health_check(self, connection_id: str) -> bool:
        """Verify the connection is operational."""
        ...

    def disconnect(self, connection_id: str, delete_data: bool) -> dict:
        """Revoke credentials and optionally delete imported data."""
        ...
```

## Registration

```python
# In the DI container (composition root):
connector_registry: dict[str, type[SourceConnector]] = {
    "gmail": GmailConnector,
    "calendar": CalendarConnector,
    "drive": DriveConnector,
    "whatsapp": WhatsAppConnector,
    "collabute": CollabuteConnector,
}

# Adding Outlook post-hackathon:
connector_registry["outlook"] = OutlookConnector  # one line, zero core changes
```

## Normalized Record Contract

Every `normalize()` output MUST include:

```python
{
    "owner_id": str,           # CRM owner
    "source_connection_id": str,
    "external_id": str,        # source-native unique ID
    "content_version": int,    # increments on audited updates
    "type": str,               # email|message|meeting|call|document_shared
    "occurred_at": datetime,
    "updated_at": datetime,
    "direction": str | None,   # incoming|outgoing
    "subject": str | None,
    "body_text": str | None,
    "participants": list[{
        "source_address": str,
        "role": str,           # sender|recipient|cc|attendee|organizer|group_member
        "identity_hint": dict | None,  # email/phone/url for resolution
    }],
    "metadata": dict,          # source-specific fields
    "raw_ref": str,            # opaque reference to immutable raw record
}
```

## Connector Contract Tests

Every connector MUST pass these tests (shared test suite, parameterized per source):

1. **Auth lifecycle**: initiate → callback → connected → disconnect
2. **Initial sync**: produces normalized records with all required fields
3. **Delta sync**: produces only new/changed records
4. **Idempotency**: re-running sync with same cursor produces no duplicates
5. **Cursor invalidation**: expired cursor triggers bounded resync
6. **Failure isolation**: connector error does not affect other connectors
7. **Disconnect**: stops sync, revokes credentials, optionally deletes data
8. **Status reporting**: all SourceStatus states are reachable and reported
