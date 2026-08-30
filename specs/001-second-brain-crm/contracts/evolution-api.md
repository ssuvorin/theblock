# Integration Contract: Evolution API 2.3.7 (WhatsApp)

**Pinned version**: 2.3.7 (validated source commit `fa09d37892cdbb1d65a250155d293d92230c5b30`)
**Endpoint**: `http://localhost:8080` (dev, runtime-configurable)
**Auth**: `apikey` header (global key for create/delete, per-instance `hash` for instance ops)

---

## REST Endpoints

### Create Instance

```
POST /instance/create
apikey: <global key>
Content-Type: application/json

{
  "instanceName": "crm-owner-<uuid>",
  "integration": "WHATSAPP-BAILEYS",
  "qrcode": true,
  "syncFullHistory": true,
  "webhook": {
    "enabled": true,
    "url": "http://localhost:8000/api/webhooks/evolution/crm-owner-<uuid>",
    "headers": { "x-webhook-secret": "<rotated secret>" },
    "byEvents": false,
    "base64": false,
    "events": ["QRCODE_UPDATED", "CONNECTION_UPDATE", "MESSAGES_SET", "MESSAGES_UPSERT"]
  }
}

Response 201:
{
  "instance": { "instanceName": "...", "instanceId": "...", "integration": "WHATSAPP-BAILEYS", "status": "..." },
  "hash": "<instance token>",
  "qrcode": { "pairingCode": null, "code": "...", "base64": "data:image/png;base64,...", "count": 1 }
}
```

### Connect / Get QR

```
GET /instance/connect/{instanceName}
apikey: <instance hash or global key>

Response 200 (connecting):
{ "instance": { "instanceName": "...", "state": "connecting" }, "qrcode": { "code": "...", "base64": "...", "count": N } }

Response 200 (open):
{ "instance": { "instanceName": "...", "state": "open" }, ... }
```

### Connection State

```
GET /instance/connectionState/{instanceName}
apikey: <instance hash or global key>

Response 200: { "instance": { "instanceName": "...", "state": "open|connecting|close" } }
```

### Logout

```
DELETE /instance/logout/{instanceName}
apikey: <instance hash or global key>

Response 200: { "status": "SUCCESS", "error": false, "response": { "message": "Instance logged out" } }
```

### Delete Instance

```
DELETE /instance/delete/{instanceName}
apikey: <global key>

Response 200: { "status": "SUCCESS", "error": false, "response": { "message": "Instance deleted" } }
```

---

## Webhook Envelope

```jsonc
{
  "event": "messages.upsert",       // dot.lowercase: messages.upsert|messages.set|qrcode.updated|connection.update
  "instance": "crm-owner-<uuid>",
  "data": { ... } | [ ... ],        // MessageRaw or MessageRaw[]
  "destination": "<configured url>",
  "date_time": "<local ISO>",
  "sender": "<wuid>",
  "server_url": "<url>",
  "apikey": "<instance token or null>"  // only if AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=true
}
```

### Authentication

- **Custom header**: `x-webhook-secret: <rotated secret>` (set in webhook config `headers`)
- **Optional jwt_key**: if `jwt_key` in webhook headers, Evolution signs HS256 `{iat, exp: iat+600}` → `Authorization: Bearer <jwt>`. Verify with same secret. 10-min expiry.
- **No HMAC body signature.** No event ID in envelope.

### Deduplication

No unique event ID. Dedup key: `(instance, data.key.id)`. Store with TTL ≥ 24h (Evolution retries up to 10 times with ≤300s backoff).

---

## Event Payloads

### QRCODE_UPDATED

```jsonc
// Normal rotation:
{ "event": "qrcode.updated", "data": { "qrcode": { "instance": "...", "pairingCode": null, "code": "...", "base64": "data:image/png;base64,..." } } }

// Limit reached (count >= QRCODE_LIMIT):
{ "event": "qrcode.updated", "data": { "message": "QR code limit reached, please login again", "statusCode": 500 } }
```

### CONNECTION_UPDATE

```jsonc
{ "event": "connection.update", "data": { "status": "open|connecting|close|refused", "statusReason": <Boom code>, "wuid": "...", "profileName": "...", "profilePictureUrl": "..." } }
```

### MESSAGES_SET (initial history)

```jsonc
{
  "event": "messages.set",
  "data": [ MessageRaw, MessageRaw, ... ],  // ARRAY
  "isLatest": false,     // true = final chunk
  "progress": 45         // 0-100 percent
}
```

### MESSAGES_UPSERT (live messages)

```jsonc
{
  "event": "messages.upsert",
  "data": MessageRaw    // SINGLE object (one webhook per message)
}
```

### MessageRaw Schema

```jsonc
{
  "key": {
    "id": "string",              // WhatsApp message ID (dedup key)
    "remoteJid": "string",       // chat JID: <num>@s.whatsapp.net | @g.us | @lid
    "fromMe": true,              // direction: true=outgoing, false=incoming
    "participant": "string?",    // sender JID inside groups
    "remoteJidAlt": "string?",   // PN alt when remoteJid is @lid (2.3.7 rewrites)
    "addressingMode": "lid|pn?"
  },
  "pushName": "string",          // sender display name; "Você" when fromMe
  "status": "PENDING|SERVER_ACK|DELIVERY_ACK|READ|PLAYED",
  "message": { /* raw WA proto; conversation field has text */ },
  "messageType": "conversation|imageMessage|videoMessage|audioMessage|documentMessage|...",
  "messageTimestamp": 1735600000,  // unix seconds
  "instanceId": "uuid",
  "source": "ios|android|web|unknown|desktop"
}
```

**Text extraction**: `data.message.conversation` (covers plain + formerly-extendedText messages).

---

## PII-Log Sanitization

**Critical**: `console.log(messageRaw)` at line 1487 of `whatsapp.baileys.service.ts` logs every inbound message body to stdout regardless of `LOG_LEVEL`.

### Mitigation

1. **Patch source**: Replace `console.log(messageRaw)` with `this.logger.debug(messageRaw)` (gated by `LOG_LEVEL`).
2. **Config**: `LOG_LEVEL=ERROR,WARN`, `LOG_BAILEYS=error`, `SENTRY_DSN` unset.
3. **Container**: Treat stdout as sensitive. Restrict log access. Short retention.
4. **Reject build**: CI preflight checks for unsanitized `console.log` in baileys service.

### Other leak sites (all `console.log`, not suppressible by config)

| Line | Content |
|------|---------|
| 1487 | `console.log(messageRaw)` — every inbound message |
| 950 | `console.log('received on-demand history sync, messages=', messages)` |
| 1119 | `console.log('Message received from phone, id=', requestId, received)` |
| 4869 | `console.log('stanza', JSON.stringify(stanza))` |

---

## Configuration

```env
# Evolution API .env (critical for P0)
AUTHENTICATION_API_KEY=<strong random key>  # NOT the default 'BQR...'
LOG_LEVEL=ERROR,WARN
LOG_BAILEYS=error
SENTRY_DSN=
QRCODE_LIMIT=30
DATABASE_SAVE_DATA_HISTORIC=true
WEBHOOK_RETRY_MAX_ATTEMPTS=10
WEBHOOK_REQUEST_TIMEOUT_MS=60000
```
