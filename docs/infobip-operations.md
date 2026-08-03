# Infobip operations

**Status:** integration built end to end, every channel disabled
**Date:** 2026-08-03
**Plan:** [`infobip-integration-plan.md`](./infobip-integration-plan.md)

This records what is implemented, what an operator must do before any message
can legally be sent, and what has and has not been verified.

## What is implemented

All phases of the plan except real-time voice transport (§10 Paths A and B):

| Area | Location |
| --- | --- |
| Shared HTTP client, retry, error taxonomy | `services/api/src/sahaayak_api/integrations/infobip/` |
| SMS and email adapters | `integrations/infobip/{sms,email}.py` |
| Provider-neutral notification layer | `services/api/src/sahaayak_api/notifications/` |
| Contact points, consent, verification | `routers/contact_points.py` |
| Delivery and inbound callbacks | `routers/webhooks_infobip.py` |
| WhatsApp send and inbound conversation | `integrations/infobip/whatsapp.py`, `workers/whatsapp_inbound.py` |
| Clip-based inbound voice | `integrations/infobip/calls.py`, `workers/voice_call.py` |
| Notification worker | `workers/notification_worker.py`, `scripts/14_run_notification_worker.py` |
| Admin channel view | `routers/admin_notifications.py` |
| Contact settings UI | `apps/web/src/features/contacts/` |
| Tables and migrations | `sahaayak_common/models.py`, `migrations/versions/20260803_000{8,9}_*` |
| Destination encryption | `sahaayak_common/contact_crypto.py` |

Not implemented, deliberately: real-time streaming voice (Infobip WebSocket
media or a SIP trunk to Jambonz), and outbound calling. The plan calls for
choosing between those two paths before building either; the clip-based path
here is the proof that the shared runtime works over a phone line.

## What has been verified

- 437 offline tests pass, covering retry policy, SMS segmentation, channel
  gating, worker claiming and retries, webhook auth, replay and out-of-order
  reports, the WhatsApp window, and the call state machine.
- Both migrations apply, reverse, and re-apply on a clean database.
- No test reaches the network. `tests/conftest.py` fails any test that tries.

## What has NOT been verified

Nothing has been run against a real Infobip account. In particular no test
here proves that the request bodies match the API version your account
exposes, that a message is delivered, or that a callback arrives in the shape
the parser expects. **Confirm the endpoint paths below before enabling a
channel**, and treat the first live send as a smoke test.

| Constant | Value | File |
| --- | --- | --- |
| SMS send | `POST /sms/3/messages` | `integrations/infobip/sms.py` |
| Email send | `POST /email/3/send` | `integrations/infobip/email.py` |
| WhatsApp template | `POST /whatsapp/1/message/template` | `integrations/infobip/whatsapp.py` |
| WhatsApp text | `POST /whatsapp/1/message/text` | `integrations/infobip/whatsapp.py` |
| Call actions | `POST /calls/1/calls/{id}/…` | `integrations/infobip/calls.py` |

The Calls API paths are the least certain of these: the capture/play flow was
written from the documented event model and has never seen a real call.

## Operator prerequisites

None of the following can be done from the codebase. Each is a hard gate.

### Account

1. Create a development account and note the personalized base URL. It is not
   a secret; the API key is.
2. Create separate API keys per environment and per capability, with the
   narrowest scopes the authorization screen offers. Do not grant billing or
   account-management scopes to the runtime key.
3. Register the test recipients the trial permits.

### Email, before `INFOBIP_EMAIL_ENABLED=true`

- Verify the sending domain.
- Configure SPF, DKIM, and DMARC. Without these the mail is delivered to spam,
  which is indistinguishable from success at the API.
- Establish a monitored `Reply-To`.
- Confirm Kannada and Hindi render in the target clients.

### SMS, before `INFOBIP_SMS_ENABLED=true`

- Complete DLT registration for the entity.
- Register the sender header.
- Register each template and record its DLT template ID on the matching
  `notification_template` row. The SMS channel will refuse to send until
  `provider_template_name` is set, by design.
- Confirm the transactional/service category.
- Test delivery to both DND and non-DND numbers.

### Webhooks

- Terminate TLS at the proxy; the application assumes HTTPS upstream.
- Set `INFOBIP_WEBHOOK_AUTH_SECRET` and configure Infobip to send it as
  `X-Infobip-Webhook-Secret`. With no secret configured the routes return 503
  and process nothing.
- Point callbacks at, as applicable:

  | Purpose | Path |
  | --- | --- |
  | SMS delivery reports | `/api/webhooks/infobip/sms` |
  | SMS inbound (STOP handling) | `/api/webhooks/infobip/sms/inbound` |
  | Email delivery reports | `/api/webhooks/infobip/email` |
  | WhatsApp delivery/seen | `/api/webhooks/infobip/whatsapp` |
  | WhatsApp inbound | `/api/webhooks/infobip/whatsapp/inbound` |
  | Calls API events | `/api/webhooks/infobip/voice/events` |

### Encryption key

Generate once per environment and store in the secret manager:

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Rotating `INFOBIP_CONTACT_ENCRYPTION_KEY` makes existing stored destinations
undecryptable and their reminders undeliverable. There is no re-encryption
path yet; rotate only with a plan for the existing rows.

## Enabling a channel

Both switches are required, and both can be flipped without a deployment:

1. `INFOBIP_ENABLED=true` plus the channel's own flag and sender in the
   environment.
2. The provider policy for that channel enabled through the admin console.
   Messaging channels ship disabled in `DEFAULT_PROVIDER_POLICIES`.

An operator can disable a channel at any time through the policy alone. Its
reminders are then suppressed rather than lost, and in-app delivery keeps
working.

## Privacy invariants

These hold in the current code and should be checked by any change:

- A destination exists only as ciphertext, a keyed hash, and a masked suffix.
  No API response returns one.
- Verification codes are stored only as a keyed hash, discarded on use, and
  never logged.
- Provider request and response bodies are never logged.
- `notification_delivery` holds a template key, never a message body.
- Telemetry carries channel, template key, locale, and status only.

## Cost controls

`INFOBIP_DAILY_BUDGET_MINOR_UNITS` and `INFOBIP_MONTHLY_BUDGET_MINOR_UNITS`
are rolling caps in minor units of `INFOBIP_COST_CURRENCY`, computed from the
recorded cost on delivery rows. Rows whose cost a provider has not yet reported
count as zero, so the cap is a floor rather than a guarantee — set it below the
amount that would actually hurt.

`SMS_MAX_SEGMENTS` caps a single message. Kannada and Hindi force UCS-2
encoding at 67 characters per segment, so a message that is one segment in
English can be five in Kannada.

### WhatsApp, before `INFOBIP_WHATSAPP_ENABLED=true`

- Verify the Meta Business Portfolio and onboard a WABA through Infobip.
- Configure and verify the sender.
- Register utility templates for reminders and authentication templates for
  verification. Record each approved name on the matching
  `notification_template` row; WhatsApp refuses to send without one.
- Confirm Indian WhatsApp pricing and per-conversation limits.

### Voice, before `INFOBIP_VOICE_ENABLED=true`

- Provision an India DID and complete number KYC.
- Confirm Calls API availability on the account.
- Set `INFOBIP_CALLS_CONFIGURATION_ID` and link the DID to it.
- Confirm whether Indian inbound voice requires additional enterprise
  communication authorization for your use case.

Outbound calling is not implemented and should stay that way until there is a
reason and an authorization for it.

## Running the worker

External-channel reminders are dispatched by a separate process. Nothing is
sent until it runs.

```bash
make notifications-dry-run   # what is due, sends nothing — run this first
make notifications           # one batch
```

In Compose, the `notification-worker` service runs it continuously. It is
harmless with every channel disabled: it claims nothing.

## Watching it

`GET /api/admin/notifications` shows per-channel posture, delivery counts,
suppression reasons, and cost. The number to watch is
**accepted but never reported on** — messages a provider took and never
reported back about. From the send side that is indistinguishable from
everything working. It is also the `SahaayakDeliveryReportsStopped` alert in
`infra/monitor/alert.rules.yml`.
