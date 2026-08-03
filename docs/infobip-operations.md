# Infobip operations

**Status:** integration built, every channel disabled
**Date:** 2026-08-03
**Plan:** [`infobip-integration-plan.md`](./infobip-integration-plan.md)

This records what is implemented, what an operator must do before any message
can legally be sent, and what has and has not been verified.

## What is implemented

Phases 1 through 4 of the plan, plus the SMS and email adapters and their
callbacks:

| Area | Location |
| --- | --- |
| Shared HTTP client, retry, error taxonomy | `services/api/src/sahaayak_api/integrations/infobip/` |
| SMS and email adapters | `integrations/infobip/{sms,email}.py` |
| Provider-neutral notification layer | `services/api/src/sahaayak_api/notifications/` |
| Contact points, consent, verification | `routers/contact_points.py` |
| Delivery and inbound callbacks | `routers/webhooks_infobip.py` |
| Tables and migration | `sahaayak_common/models.py`, `migrations/versions/20260803_0008_*` |
| Destination encryption | `sahaayak_common/contact_crypto.py` |

Not implemented: the WhatsApp adapter, voice transport, the notification
worker, and the admin/frontend surfaces. Reminders on an external channel are
recorded with a `next_attempt_at` but nothing dispatches them yet — that is the
worker, plan §11.

## What has been verified

- 357 offline tests pass, including the full retry, segmentation, gating,
  webhook auth, replay, and ordering paths against a mocked transport.
- The migration applies, reverses, and re-applies on a clean database.
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
- Point delivery callbacks at `/api/webhooks/infobip/{sms,email}` and inbound
  SMS at `/api/webhooks/infobip/sms/inbound`.

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
