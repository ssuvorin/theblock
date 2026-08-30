# Integration Contract: Collabute Coding Tools MCP

**Endpoint**: `https://api.collabute.ai/api/mcp` (Streamable HTTP MCP, protocol 2025-06-18)
**Auth**: OAuth 2.1 public client + PKCE (S256), human AuthKit login
**Scopes**: `meeting:read` (minimum), optionally `memory:read`

---

## OAuth Flow

### Discovery

```
GET https://api.collabute.ai/.well-known/oauth-authorization-server

Response 200:
{
  "issuer": "https://api.collabute.ai",
  "authorization_endpoint": "https://api.collabute.ai/api/mcp/oauth/authorize",
  "token_endpoint": "https://api.collabute.ai/api/mcp/oauth/token",
  "registration_endpoint": "https://api.collabute.ai/api/mcp/oauth/register",
  "device_authorization_endpoint": "https://api.collabute.ai/api/mcp/oauth/device/start",
  "grant_types_supported": ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:device_code"],
  "response_types_supported": ["code"],
  "token_endpoint_auth_methods_supported": ["none"],
  "code_challenge_methods_supported": ["S256"]
}
```

### Dynamic Client Registration

```
POST https://api.collabute.ai/api/mcp/oauth/register
Content-Type: application/json

{ "redirect_uris": ["https://<crm-host>/api/integrations/collabute/callback"] }

Response 201: { "client_id": "...", ... }
```

### Authorize URL

```
https://api.collabute.ai/api/mcp/oauth/authorize?
  response_type=code
  &client_id=<client_id>
  &redirect_uri=<callback>
  &scope=meeting:read
  &state=<nonce>
  &code_challenge=<S256 hash>
  &code_challenge_method=S256
  &resource=https%3A%2F%2Fapi.collabute.ai%2Fapi%2Fmcp
```

**Human completes AuthKit login in browser.** Agents MUST NOT automate this step.

### Token Exchange

```
POST https://api.collabute.ai/api/mcp/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=<code>
&code_verifier=<pkce verifier>
&redirect_uri=<callback>
&client_id=<client_id>
&resource=https://api.collabute.ai/api/mcp

Response 200: { "access_token": "...", "refresh_token": "...", "expires_in": N, "token_type": "Bearer" }
```

### Token Refresh

```
POST https://api.collabute.ai/api/mcp/oauth/token
grant_type=refresh_token
&refresh_token=<current>
&client_id=<client_id>
&resource=https://api.collabute.ai/api/mcp

Response 200: { "access_token": "...", "refresh_token": "<ROTATED>", "expires_in": N }
```

**Rotation mandatory**: store new refresh token every time. Refresh at ~80% of `expires_in`, reactively on 401. Refresh failure → `needs_reauth`.

---

## MCP Session Lifecycle

### Initialize

```
POST https://api.collabute.ai/api/mcp
Authorization: Bearer <access_token>
Accept: application/json, text/event-stream
Content-Type: application/json
MCP-Protocol-Version: 2025-06-18

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": { "name": "second-brain-crm", "version": "0.1.0" }
  }
}

Response: { "jsonrpc": "2.0", "id": 1, "result": { "protocolVersion": "...", "capabilities": { "tools": { "listChanged": true } }, "serverInfo": {...} } }
Headers: Mcp-Session-Id: <session-id> (if stateful)
```

### Notify Initialized

```
POST https://api.collabute.ai/api/mcp
Authorization: Bearer <access_token>
Mcp-Session-Id: <session-id>
MCP-Protocol-Version: 2025-06-18

{ "jsonrpc": "2.0", "method": "notifications/initialized" }

Response: 202 Accepted
```

### tools/list

```
POST https://api.collabute.ai/api/mcp
Authorization: Bearer <access_token>
Mcp-Session-Id: <session-id>

{ "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {} }

Response: {
  "jsonrpc": "2.0", "id": 2,
  "result": {
    "tools": [
      { "name": "...", "title": "...", "description": "...", "inputSchema": {...}, "outputSchema": {...}? }
    ]
  }
}
```

**FR-4.3**: Capture this response as versioned fixture in `contracts/collabute-tools-list.fixture.json`. Verify against fixture on subsequent runs.

### tools/call

```
POST https://api.collabute.ai/api/mcp
Authorization: Bearer <access_token>
Mcp-Session-Id: <session-id>

{ "jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": { "name": "<tool_name>", "arguments": {...} } }

Response: {
  "jsonrpc": "2.0", "id": 3,
  "result": {
    "content": [ { "type": "text", "text": "..." } ],
    "structuredContent": {...}?,
    "isError": false
  }
}
```

**Parse defensively**: `content[]` blocks are typically `type:"text"` — may contain JSON in text. `structuredContent` present only if tool declares `outputSchema`.

### Session Teardown

```
DELETE https://api.collabute.ai/api/mcp
Mcp-Session-Id: <session-id>

Response: 200 or 405 (server may not support)
```

---

## Rate Limits

- **60 requests/minute** (standard plan)
- Headers: `RateLimit: limit=60, remaining=N, reset=<unix>`, `RateLimit-Policy: 60;w=60`
- 429: honor `Retry-After` (if present), else exponential backoff with jitter
- Bounded: ≤5 retries, max 5 min backoff, then mark sync failed (preserve last cursor)

---

## Free Tier Constraints

- 30 meetings/month
- **7-day context history** — demo meeting MUST be <7 days old at demo time (FR-4.8)

---

## Normalized Meeting Schema (CRM target)

```python
{
    "external_id": str,          # Collabute workspace meeting ID
    "type": "meeting",
    "occurred_at": datetime,
    "subject": str | None,       # meeting title
    "body_text": str | None,     # summary
    "participants": list[{
        "source_address": str,   # email or display name
        "role": "attendee" | "organizer",
        "identity_hint": dict | None,
    }],
    "metadata": {
        "decisions": list[str],
        "action_items": list[{
            "text": str,
            "owner": str | None,
            "stable_id": str | None,    # Collabute action ID
        }],
    },
    "raw_ref": str,
}
```

### Action Item Dedup (FR-4.5)

- Prefer stable Collabute workspace/resource/action ID
- Fallback: deterministic content hash = `sha256(meeting_id + normalized_action_text)`
- Follow-up `source_key` = stable ID or content hash

---

## Must-Capture-After-First-Auth

| Item | Status | Action |
|------|--------|--------|
| Exact meeting tool names | Unknown | Capture in tools/list fixture |
| inputSchema parameters | Unknown | Capture in fixture |
| Response format (JSON vs prose) | Unknown | Parse defensively, capture sample |
| `expires_in` value | Unknown | Capture from first token response |
| `Mcp-Session-Id` issued? | Unknown | Check initialize response headers |
| Participant identity format | Unknown | Capture from first meeting payload |

---

## Python Dependencies

```
mcp>=0.7.0          # official MCP SDK, streamable_http client
httpx               # OAuth flow
```

```python
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

async def collabute_session(token: str):
    async with streamablehttp_client(
        "https://api.collabute.ai/api/mcp",
        headers={"Authorization": f"Bearer {token}"},
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            # ... call tools ...
```
