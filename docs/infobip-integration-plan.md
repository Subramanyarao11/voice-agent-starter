# Infobip Integration Plan for Sahaayak

**Status:** Proposed implementation plan  
**Date:** 2026-08-03  
**Scope:** Integrate Infobip wherever it is a good fit without replacing the
existing eligibility, RAG, Sarvam, OpenAI, auth, or admin architecture.

## 1. Recommendation

Use Infobip as a provider adapter for:

1. Transactional SMS.
2. WhatsApp messaging and inbound WhatsApp events.
3. Transactional email.
4. Optional Indian inbound voice transport through Infobip Calls API or an
   Infobip DID/SIP trunk connected to Jambonz.
5. Delivery reports, message status, provider health, and cost/usage telemetry.

Do not use Infobip to replace:

- the structured eligibility matcher;
- the OpenAI-hosted Vector Store;
- Sarvam Kannada/Hindi TTS;
- OpenAI transcription or reasoning fallback;
- guest-session authorization;
- Keycloak/OIDC/MFA;
- the Sahaayak admin control center.

The correct boundary is:

~~~text
Sahaayak agent and product logic
  -> provider-neutral notification, voice-transport, and status interfaces
  -> Infobip adapter
  -> SMS / WhatsApp / Email / Voice networks
~~~

Infobip provides APIs and telecom connectivity, but it does not make the RAG
answer correct, translate all content, or replace Indian telecom/WhatsApp
compliance work.

Infobip authenticates API calls through an Authorization header, supports scoped
API keys, and gives each account a personalized base URL. The base URL is not a
secret; the API key is. [Infobip API authentication](https://www.infobip.com/docs/essentials/api-essentials/api-authentication) · [Infobip base URL](https://www.infobip.com/docs/essentials/api-essentials/base-url)

## 2. What is feasible now

| Product area | Infobip fit | Implementation decision |
| --- | --- | --- |
| In-app reminders | Not needed | Keep the existing in-app path |
| Email reminders | Strong | Implement first after the shared notification foundation |
| SMS reminders | Strong, India compliance required | Implement with delivery reports and consent |
| WhatsApp reminders | Strong, Meta onboarding/templates required | Implement after SMS/email |
| WhatsApp inbound text | Strong | Normalize into the same conversation runtime |
| WhatsApp voice notes | Feasible | Download media, process through existing clip voice path, then reply |
| PSTN inbound voice | Feasible after account/channel activation | Use a staged Calls API or SIP/Jambonz path |
| Real-time telephony voice bot | Feasible but not immediate | Requires streaming audio interfaces and turn detection |
| OTP/contact verification | Feasible | Add only for verified reminder channels; do not replace admin OIDC |
| Admin observability | Strong through our own adapter telemetry | Add Infobip channel status and delivery views |
| RAG ingestion/vector storage | Not applicable | Keep OpenAI-hosted Vector Store |
| STT/TTS | Not the preferred product path | Keep OpenAI transcription and Sarvam Bulbul policy |

Infobip’s current trial includes small test allocations across SMS, voice, email,
and WhatsApp, but trial recipients and senders are restricted. Use the trial
for controlled smoke tests, not production traffic. [Infobip free trial](https://www.infobip.com/docs/essentials/getting-started/free-trial)

## 3. Integration principles

### 3.1 Keep Infobip behind interfaces

No route, agent graph node, matcher, or frontend component should call an Infobip
URL directly.

Use interfaces such as:

~~~text
NotificationProvider
  send_email(...)
  send_sms(...)
  send_whatsapp(...)
  get_delivery_status(...)

VoiceTransportProvider
  receive_call_event(...)
  answer_call(...)
  play_audio(...)
  start_media_stream(...)
  end_call(...)

ContactVerificationProvider
  request_phone_verification(...)
  verify_phone_code(...)
  request_email_verification(...)
  verify_email_code(...)
~~~

The first implementation can provide:

~~~text
InfobipNotificationProvider
InfobipCallsProvider
InfobipContactVerificationProvider
~~~

The existing in-app provider remains available and should be the safe fallback.

### 3.2 Keep the agent provider-neutral

The agent should only receive normalized application events:

~~~text
InboundMessage(
  channel,
  external_user_key,
  locale,
  text,
  media_reference,
  user_initiated,
  consent_context
)
~~~

It should return:

~~~text
AgentReply(
  text,
  audio,
  sources,
  suggested_actions,
  safe_channel_content
)
~~~

The Infobip adapter translates that reply into SMS, email, WhatsApp, or voice
actions. The matcher and RAG code must not know whether the user arrived through
a browser, WhatsApp, or a phone call.

### 3.3 Do not use free trial credentials in production

Development and staging should use separate Infobip applications/API keys.
Production should have separate keys with least-privilege scopes, short expiry,
rotation procedures, and secret-manager storage.

Never log:

- Infobip API keys;
- email addresses;
- phone numbers;
- WhatsApp user IDs;
- message bodies containing user data;
- raw provider webhook payloads.

Use opaque internal IDs and hashes in logs and callback metadata.

## 4. Phase 0 — Account and capability verification

### Objective

Confirm that the Infobip account can support the exact India use cases before
writing provider-specific production code.

### Account setup

Create or configure:

- one Infobip development account;
- one staging application;
- one production application later;
- a personalized API base URL;
- separate API keys for SMS, WhatsApp/email, and voice where practical;
- verified test phone numbers and email addresses;
- a test sender for each enabled channel.

The free trial permits verified-recipient testing. The actual sender/number,
India routing, WhatsApp sender, email domain, and voice DID must be confirmed
before the implementation is considered production-capable.

### Request/confirm these capabilities

Ask Infobip to confirm in writing:

- India SMS availability and DLT registration requirements.
- India inbound voice DID availability.
- India voice number KYC and rental requirements.
- Calls API availability for the account.
- Calls API media-streaming activation.
- SIP trunking activation and whether an Infobip DID can route to Jambonz.
- WhatsApp Business Account onboarding and sender ownership.
- WhatsApp template approval process and supported Indian language templates.
- Email sending-domain verification and transactional-email limits.
- Delivery-report and webhook configuration.
- API rate limits, concurrency, retry behavior, and account balance alerts.
- Any minimum spend or production commitment.
- Whether media streaming is available during the free trial or requires a paid
  account/Account Manager activation.

Infobip documents that Calls API media streaming and SIP trunking require account
activation, so this is a gate rather than an assumption. [Infobip Calls API](https://www.infobip.com/docs/voice-and-video/calls)

### API key scopes

Create separate keys with only the scopes required by each service.

Suggested scopes:

~~~text
SMS sender:
  sms:message:send
  sms:logs:read

WhatsApp sender:
  whatsapp:message:send
  whatsapp:inbound-message:read
  whatsapp:logs:read
  whatsapp:manage

Email sender:
  email:message:send
  email:logs:read
  email:templates:manage

Voice sender:
  calls:manage
  calls:traffic:receive
  calls:traffic:send
  calls:configuration:manage
  voice:logs:read

Webhook administration:
  subscriptions:manage
~~~

The exact scopes should be checked against the current Infobip account/API
authorization screen before provisioning. Do not grant account-management or
billing permissions to the runtime key. [Infobip API authorization](https://www.infobip.com/docs/essentials/api-essentials/api-authorization)

### Phase 0 acceptance criteria

- API key can send one test SMS to a verified number.
- API key can send one test email to a verified address.
- WhatsApp test sender can send a permitted test message.
- Infobip can deliver at least one inbound voice event or one voice test call.
- The account manager confirms India number and media/SIP requirements.
- All keys are stored outside Git and outside frontend environment variables.
- A short account capability record is added to the admin/operations documentation.

## 5. Phase 1 — Shared Infobip client foundation

### Suggested code layout

Add a new provider package under the API service:

~~~text
services/api/src/sahaayak_api/integrations/
  __init__.py
  infobip/
    __init__.py
    client.py
    config.py
    errors.py
    models.py
    retry.py
    sms.py
    whatsapp.py
    email.py
    calls.py
    webhooks.py
    health.py
~~~

If voice streaming becomes a separate process, move the real-time media bridge
to a dedicated service:

~~~text
services/telephony/
  src/sahaayak_telephony/
    infobip_websocket.py
    jambonz_adapter.py
    audio_codec.py
    turn_detection.py
~~~

Do not introduce a second eligibility graph in that service.

### Shared HTTP client

Use the existing HTTPX dependency and create one long-lived async client per
process rather than creating a new client for every message.

The shared client should provide:

- base URL normalization;
- Authorization header injection;
- Content-Type and Accept headers;
- connect/read/write/pool timeouts;
- bounded retries for transient 429/5xx failures;
- Retry-After handling;
- correlation ID propagation;
- external message/call ID extraction;
- structured error normalization;
- redacted request/response logging;
- cancellation on shutdown.

Retry rules:

| Error | Retry? | Behavior |
| --- | --- | --- |
| Timeout/connect failure | Yes, bounded | Exponential backoff with jitter |
| HTTP 429 | Yes, bounded | Respect Retry-After; trip budget/rate alert if sustained |
| HTTP 500/502/503/504 | Yes, bounded | Retry only if the operation has an idempotency key |
| HTTP 400 | No | Mark delivery failed and expose normalized reason |
| HTTP 401/403 | No | Disable the affected provider scope and alert admin |
| Template/DLT rejection | No | Mark configuration/content failure; do not retry |
| Invalid destination | No | Mark contact invalid and request correction |

### Settings and secrets

Add settings with names similar to:

~~~text
INFOBIP_ENABLED=false
INFOBIP_BASE_URL=
INFOBIP_API_KEY=
INFOBIP_ENVIRONMENT=development

INFOBIP_SMS_ENABLED=false
INFOBIP_SMS_SENDER=
INFOBIP_SMS_WEBHOOK_URL=

INFOBIP_WHATSAPP_ENABLED=false
INFOBIP_WHATSAPP_SENDER=
INFOBIP_WHATSAPP_WEBHOOK_URL=

INFOBIP_EMAIL_ENABLED=false
INFOBIP_EMAIL_SENDER=
INFOBIP_EMAIL_SENDER_NAME=
INFOBIP_EMAIL_WEBHOOK_URL=

INFOBIP_VOICE_ENABLED=false
INFOBIP_VOICE_NUMBER=
INFOBIP_CALLS_CONFIGURATION_ID=
INFOBIP_CALLS_SUBSCRIPTION_ID=
INFOBIP_VOICE_WEBHOOK_URL=
INFOBIP_VOICE_WEBSOCKET_URL=

INFOBIP_WEBHOOK_AUTH_SECRET=
INFOBIP_REQUEST_TIMEOUT_SECONDS=10
INFOBIP_MAX_RETRIES=2
INFOBIP_MAX_MESSAGE_BYTES=10485760
INFOBIP_DAILY_BUDGET_INR=
INFOBIP_MONTHLY_BUDGET_INR=
~~~

Secrets:

- INFOBIP_API_KEY
- INFOBIP_WEBHOOK_AUTH_SECRET

Non-secrets:

- INFOBIP_BASE_URL
- sender IDs
- webhook URLs
- calls configuration IDs
- environment labels

Add these to .env.example with blank values and safe comments. Do not add the
actual local .env values.

### Provider health

Add a provider health check that reports:

~~~text
configured
enabled
base_url_present
api_key_present
channel_capabilities
last_success_at
last_failure_at
last_webhook_at
last_error_class
rate_limited_until
trial_or_production_label
~~~

Health probes must not send real messages. Use a lightweight account/capability
endpoint if available, or report configuration posture plus recent request
telemetry. A configured key is not evidence that SMS, WhatsApp, email, or voice
is actually enabled.

### Provider policies

Extend the existing provider-policy registry with:

~~~text
sms:
  primary_provider: infobip_sms
  fallback_provider: in_app

whatsapp:
  primary_provider: infobip_whatsapp
  fallback_provider: sms

email:
  primary_provider: infobip_email
  fallback_provider: in_app

telephony:
  primary_provider: infobip_calls
  fallback_provider: browser_voice_or_text
~~~

The existing admin policy mechanism should control:

- enabled/disabled state;
- primary provider;
- fallback provider;
- circuit state;
- locale scope;
- state scope;
- daily/monthly budget;
- override expiry;
- reason;
- audited rollback.

Do not reuse the OpenAI USD ledger for Infobip. Add provider/channel usage
tracking with an explicit currency field, preferably minor units plus ISO currency,
because telecom and messaging charges may be reported in INR or another currency.

## 6. Phase 2 — Contact points, consent, and delivery data model

The current Reminder API intentionally accepts only in-app delivery. Infobip
integration must not simply change that literal to SMS/email/WhatsApp without
adding verified contacts and consent.

### New ContactPoint table

Suggested fields:

~~~text
ContactPoint
  id
  session_id
  channel                 email | sms | whatsapp
  destination_ciphertext  encrypted at rest
  destination_hash        indexed lookup hash
  display_suffix          safe masked value, e.g. ******1234
  locale
  verification_status     pending | verified | invalid | revoked
  verification_provider   infobip_verify | email_link | manual
  verified_at
  consent_status          opted_in | opted_out | unknown
  consent_purpose         reminders | support | verification
  consent_source          browser | whatsapp_inbound | operator
  consent_at
  opted_out_at
  created_at
  updated_at
~~~

Do not use the unencrypted phone/email as a public session identifier. Store a
hash for deduplication and an encrypted value only where delivery requires it.

### New NotificationDelivery table

Suggested fields:

~~~text
NotificationDelivery
  id
  reminder_id
  session_id
  contact_point_id
  channel
  provider                 infobip
  template_key
  locale
  internal_message_id
  external_message_id
  external_bulk_id
  status                   queued | sending | accepted | delivered | seen |
                           failed | suppressed | cancelled
  provider_status_code
  provider_status_group
  provider_error_code
  provider_error_class
  attempt_count
  next_attempt_at
  idempotency_key
  sent_at
  delivered_at
  seen_at
  failed_at
  cost_minor_units
  cost_currency
  safe_metadata
  created_at
  updated_at
~~~

Never store the complete message body in this table. Store a template key and
safe parameters only.

### Reminder changes

Extend Reminder with:

~~~text
channel                  in_app | email | sms | whatsapp
contact_point_id         nullable for in_app
template_key             nullable for in_app
consent_snapshot_id      audit reference
next_attempt_at
last_delivery_id
~~~

The API should reject external channels when:

- the contact point is missing;
- the contact point is not verified;
- consent is absent or revoked;
- the reminder has no approved template;
- the provider policy is disabled;
- the daily/monthly budget is exhausted;
- the session is expired/deleted.

### Consent behavior

Entering a phone number or email address is not sufficient consent.

The UI must explain:

- what channel will be used;
- what type of messages will be sent;
- how often reminders may be sent;
- how to opt out;
- that external provider terms and telecom/WhatsApp rules apply.

Every opt-in and opt-out becomes an append-only consent event. SMS STOP-like
responses and WhatsApp marketing-subscription events should revoke the relevant
purpose without deleting unrelated in-app data.

### Contact verification

Use a separate verification flow:

~~~text
POST /api/sessions/{session_id}/contact-points
  -> creates a pending contact point
  -> sends a verification challenge

POST /api/sessions/{session_id}/contact-points/{contact_id}/verify
  -> verifies the OTP or email token
  -> marks the contact point verified

DELETE /api/sessions/{session_id}/contact-points/{contact_id}
  -> revokes the contact point and future deliveries
~~~

For phone verification, Infobip’s 2FA/Verify capability can be evaluated. Do not
make it a replacement for the guest session token. Rate-limit challenge creation
and verification attempts separately, and never log the verification code.

For email verification, use a short-lived signed verification token or a
provider-neutral code flow. The email body must not contain sensitive profile
data.

## 7. Phase 3 — Infobip SMS integration

Infobip’s current programmable SMS API uses the SMS v3 messages endpoint and
supports delivery webhooks. [Infobip SMS API](https://www.infobip.com/sms/api) · [SMS delivery reports](https://www.infobip.com/docs/sms/message-delivery)

### Use cases

Initial allowed use cases:

- verified reminder for a saved benefit;
- application-deadline reminder;
- source link delivery after explicit request;
- contact verification;
- operational alerts to an authorized admin contact.

Do not enable promotional campaigns, bulk outreach, or outbound calling from this
integration.

### Adapter contract

~~~python
class SmsProvider(Protocol):
    async def send(
        self,
        *,
        destination: str,
        sender: str,
        text: str,
        internal_message_id: str,
        callback_data: str,
    ) -> ProviderSendResult: ...
~~~

The adapter should:

1. Validate E.164 destination format.
2. Resolve the approved template and locale.
3. Enforce maximum characters and segment budget.
4. Attach an opaque internal message ID in provider callback data.
5. Send through the Infobip SMS v3 API.
6. Persist the returned external message ID and initial status.
7. Emit redacted telemetry.
8. Return a normalized result to the notification worker.

For Kannada/Hindi, account for Unicode SMS segmentation. Keep messages short and
prefer one canonical source link. If a message exceeds the approved segment
budget, suppress it and use email/WhatsApp or a short link only after consent.

### DLT and India configuration

Before live Indian SMS:

- register the business/entity as required;
- register sender IDs/headers;
- register approved templates;
- map each notification template to its DLT template;
- confirm transactional/service category;
- include opt-out language where required;
- test delivery to DND and non-DND numbers;
- record DLT configuration metadata in the admin system.

The app must not treat a provider HTTP 200 as delivery. It means the request was
accepted/queued; the delivery webhook determines final status.

### SMS webhook

Add:

~~~text
POST /api/webhooks/infobip/sms
~~~

Behavior:

1. Accept only HTTPS traffic through the reverse proxy.
2. Validate an Infobip-specific secret/header or trusted webhook configuration.
3. Enforce a maximum body size.
4. Parse the event into a versioned Pydantic schema.
5. Deduplicate by external message ID and event type.
6. Update NotificationDelivery.
7. Process opt-out/STOP events if present.
8. Emit safe telemetry.
9. Return 2xx quickly.
10. Perform slow follow-up work asynchronously.

Do not use the browser bearer token or admin token for this provider webhook.

### SMS fallback

WhatsApp-to-SMS fallback may be enabled only when:

- the user has explicit SMS consent;
- a verified SMS contact point exists;
- the notification is eligible for SMS;
- the user has not opted out;
- the provider policy allows fallback;
- the cost budget allows it.

The default fallback should be in-app, not SMS, until external delivery is proven.

### SMS acceptance criteria

- Unit tests cover request serialization, Unicode limits, and provider errors.
- Mock tests cover 2xx, 400, 401, 403, 429, 500, timeout, and malformed response.
- Webhook tests cover duplicate, delayed, delivered, failed, and opt-out events.
- One verified-trial SMS is sent and its delivery state appears in admin telemetry.
- No phone number or message body appears in logs or traces.
- An admin can disable SMS without redeploying.

## 8. Phase 4 — Infobip email integration

Infobip supports transactional email through HTTP or SMTP. The HTTP API is the
preferred application integration; the current documentation describes a JSON
modern endpoint and a multipart endpoint for fully featured messages. A verified
sending domain is required. [Infobip Email API](https://www.infobip.com/docs/email/email-over-api) · [Send email over HTTP](https://www.infobip.com/docs/email/email-over-api/send-email-over-http-api)

### Use cases

Initial allowed use cases:

- benefit reminder;
- saved-benefit summary;
- source/citation pack requested by the user;
- contact verification;
- admin operational alerts;
- deployment/provider incident alerts.

Do not include sensitive income, caste/category, disability, or transcript details
in email by default. Link to an authenticated or expiring result page instead.

### Email domain setup

Before production sending:

- verify the sending domain in Infobip;
- configure SPF;
- configure DKIM;
- configure DMARC;
- configure bounce/complaint handling;
- establish a From address;
- use a Reply-To address monitored by the team;
- test Kannada/Hindi font rendering and plain-text alternatives;
- document unsubscribe behavior for any non-transactional content.

The first release should use transactional templates, not marketing campaigns.

### Adapter contract

~~~python
class EmailProvider(Protocol):
    async def send(
        self,
        *,
        destination: str,
        subject: str,
        template_key: str,
        locale: str,
        variables: Mapping[str, str],
        internal_message_id: str,
    ) -> ProviderSendResult: ...
~~~

The adapter should:

1. Validate and normalize the email address.
2. Resolve a versioned template by locale.
3. Render both HTML and plain text.
4. Escape user-controlled variables.
5. Include a source URL and verification date where relevant.
6. Attach an opaque internal ID for delivery reconciliation.
7. Send using the current Infobip Email API.
8. Persist the external message ID and initial status.
9. Emit redacted telemetry.

### Email webhook/report processing

Infobip supports email delivery reports; the integration should support either
webhook events or a bounded report poller depending on the account capability.
Each report is treated as an idempotent status update. [Infobip email delivery reports](https://www.infobip.com/docs/email/email-over-api/email-api-delivery-reports)

Internal status mapping:

~~~text
accepted/queued -> accepted
delivered       -> delivered
opened          -> opened
clicked         -> clicked
bounced         -> failed + contact invalid candidate
complaint       -> failed + consent revoked for campaign purpose
unsubscribed    -> suppressed
~~~

### Email acceptance criteria

- Verified sending domain passes SPF/DKIM/DMARC checks.
- One trial email arrives at the verified recipient.
- Kannada/Hindi templates render correctly with a plain-text version.
- Delivery and bounce status update the same NotificationDelivery row.
- A bounced address is suppressed from future attempts.
- Admin can inspect delivery counts without seeing full email addresses or bodies.

## 9. Phase 5 — Infobip WhatsApp integration

Infobip supports WhatsApp template messages, free-form messages within the
permitted messaging window, inbound messages, media retrieval, delivery reports,
and seen reports. [Infobip WhatsApp over API](https://www.infobip.com/docs/whatsapp/whatsapp-over-api) · [WhatsApp inbound messages](https://www.infobip.com/docs/whatsapp/message-types-and-templates/inbound-messages)

### Onboarding requirements

Before application code:

- create/verify the Meta Business Portfolio;
- onboard a WhatsApp Business Account through Infobip;
- configure a WhatsApp sender;
- verify the business and sender;
- define user opt-in language;
- register utility/authentication templates;
- configure inbound and delivery webhooks;
- confirm Indian WhatsApp messaging pricing and limits.

Do not use unofficial WhatsApp Web automation.

### Initial templates

Create a small, versioned template set:

~~~text
benefit_reminder_utility_kn
benefit_reminder_utility_hi
benefit_reminder_utility_en
benefit_source_link_utility_kn
benefit_source_link_utility_hi
benefit_source_link_utility_en
contact_verification_auth_kn
contact_verification_auth_hi
contact_verification_auth_en
human_help_requested_utility_kn
human_help_requested_utility_hi
human_help_requested_utility_en
~~~

Templates must not promise approval or guaranteed eligibility. They should say
that the user may qualify and provide a source/action link.

### Outbound message rules

Use:

- free-form text only during the permitted user-service window;
- approved templates to initiate or resume communication outside that window;
- utility templates for reminders and requested source links;
- authentication templates only for contact verification;
- no marketing category for the beta.

Infobip documents that templates are required when initiating a conversation or
when the window has expired; free-form messages are allowed inside the active
window. [WhatsApp message rules](https://www.infobip.com/docs/whatsapp/send-a-message)

### Adapter contract

~~~python
class WhatsAppProvider(Protocol):
    async def send_template(
        self,
        *,
        destination: str,
        sender: str,
        template_key: str,
        locale: str,
        variables: Mapping[str, str],
        internal_message_id: str,
    ) -> ProviderSendResult: ...

    async def send_freeform(
        self,
        *,
        destination: str,
        sender: str,
        text: str,
        internal_message_id: str,
    ) -> ProviderSendResult: ...
~~~

Use the Infobip WhatsApp API template/text endpoints, map internal template keys
to approved Infobip template names, and preserve an opaque internal ID in
callback data.

### Inbound WhatsApp webhook

Add:

~~~text
POST /api/webhooks/infobip/whatsapp
~~~

Normalize inbound events:

~~~text
TEXT       -> text turn
AUDIO      -> download media -> clip voice turn
VOICE      -> download media -> clip voice turn
BUTTON     -> structured action
LIST       -> structured action
IMAGE/DOC  -> safe unsupported-media response or future document flow
LOCATION   -> explicit location consent flow, not automatic profile mutation
~~~

Important identity rules:

- Treat the Infobip sender as a channel identity, not as a trusted user ID.
- Hash the sender for internal storage.
- Do not automatically merge a WhatsApp sender with a browser guest session.
- Merge only after an explicit user-controlled linking flow.
- Apply per-sender and per-IP-equivalent channel rate limits.
- Cap inbound media size and content types.
- Download media only for processing and delete it promptly.
- Do not persist raw WhatsApp audio or images by default.

For inbound audio, call the shared VoiceService directly from an internal service
function rather than making a loopback HTTP request to the public route.

### WhatsApp delivery/seen/template webhooks

Handle:

- delivery;
- seen;
- inbound message;
- button/list interaction;
- template approval/update;
- opt-in/opt-out events;
- media retrieval errors.

Infobip supports global or per-message notification URLs for delivery and seen
reports. [WhatsApp reports](https://www.infobip.com/docs/whatsapp/reports)

### WhatsApp acceptance criteria

- One test sender sends an approved utility template to a verified recipient.
- A user reply reaches the webhook and appears as a normalized conversation event.
- A button/list reply maps to a typed action without LLM interpretation.
- An inbound audio message reaches the existing clip voice path.
- Delivery and seen events update NotificationDelivery.
- Template-window violations are handled with a clear fallback.
- User opt-out suppresses future external messages.
- Admin can pause WhatsApp independently from SMS and email.

## 10. Phase 6 — Voice transport integration

There are three possible Infobip voice paths. Do not build all three at once.

### Path A — Infobip DID/SIP trunk to Jambonz

This is the recommended production-oriented path if Jambonz remains the selected
voice orchestration layer.

~~~text
Indian caller
  -> Infobip voice DID
  -> Infobip SIP trunk
  -> public SBC or Jambonz
  -> Sahaayak telephony/media adapter
  -> shared AgentRuntime
~~~

Infobip documents that inbound DIDs can be forwarded to customer SIP
infrastructure and that static SIP trunks require public, dedicated IP
configuration. [Infobip SIP trunking](https://www.infobip.com/docs/voice-and-video/sip-trunking) · [Infobip SIP trunk setup](https://www.infobip.com/docs/voice-and-video/sip-trunking/set-up-sip-trunk)

Implementation work:

1. Provision an Infobip India voice DID.
2. Confirm KYC and authorization requirements.
3. Provision one low-concurrency SIP trunk.
4. Deploy a hardened SBC or configure Jambonz according to its SIP requirements.
5. Use TLS/SRTP where supported.
6. Configure inbound call routing to the Jambonz/SBC endpoint.
7. Normalize provider caller identity into a hashed telephony identity.
8. Reuse the existing session and AgentRuntime.
9. Keep the signed telephony endpoint as an internal adapter seam, not a public
   Infobip endpoint.
10. Add call lifecycle telemetry and call-cost reconciliation.

Security requirements:

- Public static IP or approved FQDN.
- Firewall allowlist.
- SIP authentication or IP authentication as appropriate.
- No direct exposure of Postgres, Redis, or the internal API.
- Replay protection for any HTTP callback.
- Call concurrency ceiling.
- Maximum call duration.
- Emergency disconnect on provider or budget incident.

### Path B — Infobip Calls API with WebSocket media

This is the fastest route to a direct real-time voice experiment if Infobip
activates Calls API media streaming and the team is willing to implement a new
streaming audio service.

Infobip supports bidirectional WebSocket audio endpoints. The documented media
formats are 16-bit linear PCM at 8, 16, 24, or 32 kHz with 20 ms frames; text
messages carry connection/DTMF events and binary messages carry audio. [Infobip WebSocket streaming](https://www.infobip.com/docs/voice-and-video/calls/use-websocket-streaming)

Implementation work:

1. Create a Calls Configuration.
2. Create an event subscription scoped to that configuration.
3. Link the Infobip DID to the Calls Configuration.
4. Expose a public TLS WebSocket endpoint.
5. Validate the Infobip connection event and customData.
6. Implement PCM frame parsing and output framing.
7. Add turn detection and interruption handling.
8. Add a streaming STT interface.
9. Add a streaming or chunked TTS interface.
10. Map call IDs to server-owned voice sessions.
11. Enforce maximum duration and per-call budget.
12. Close the stream on timeout, provider failure, or user hangup.

Current limitation: Sahaayak has clip-based OpenAI transcription and Sarvam WAV
synthesis, not a complete streaming STT/TTS loop. Therefore this path is not a
drop-in replacement for the existing /api/telephony/turns endpoint.

### Path C — Calls API capture/play smoke test

This is the lowest-risk voice proof:

1. Receive CALL_RECEIVED.
2. Answer the call.
3. Play a cached prompt.
4. Capture a short speech response.
5. Download or receive the captured audio.
6. Run the existing VoiceService.
7. Upload or reference the Sarvam WAV result.
8. Play the result.
9. Repeat for one or two turns.
10. End the call.

Infobip’s Calls API supports inbound call events, call actions, speech capture,
and audio playback. It also documents that CALL_RECEIVED and CALL_ESTABLISHED are
operational events that drive the application flow. [Infobip Calls API](https://www.infobip.com/docs/voice-and-video/calls)

### Voice recommendation

Implement in this order:

1. Calls API capture/play smoke test using trial credits if available.
2. Decide whether Jambonz/SIP or direct Infobip WebSocket is the production path.
3. Build only the selected real-time path.
4. Keep outbound calls disabled.
5. Perform a native-speaker Kannada test and a short Hindi test.
6. Add telephony to the public product only after security, rate, budget, and
   compliance gates pass.

### Voice webhook routes

Add separate routes rather than mixing provider events with browser turns:

~~~text
POST /api/webhooks/infobip/voice/events
POST /api/webhooks/infobip/voice/recordings
WS   /api/telephony/infobip/media
~~~

Store only safe call lifecycle data:

~~~text
CallSession
  internal_id
  provider
  provider_call_id
  hashed_caller_identity
  language_code
  state_code
  status
  started_at
  answered_at
  ended_at
  duration_seconds
  provider_error_code
  safe_metadata
~~~

Do not store recordings by default. If recordings are temporarily used for QA,
apply explicit consent, retention, deletion, and access controls.

## 11. Phase 7 — Notification worker and reminder delivery

The current Reminder route creates in-app reminders only. Add a separate dispatcher
so sending external messages does not block a citizen API request.

### Worker design

Add a Compose service or deployment process:

~~~text
notification-worker
  -> claims due Reminder rows
  -> validates consent/contact/provider policy
  -> creates NotificationDelivery
  -> calls Infobip adapter
  -> records accepted/failed status
  -> retries eligible failures
  -> updates final delivery status from webhooks
~~~

Prefer a Postgres row-claiming pattern with short transactions and
FOR UPDATE SKIP LOCKED in production. Redis may provide a distributed wakeup or
lock, but the delivery record must remain durable in Postgres.

### State machine

~~~text
scheduled
  -> claimed
  -> sending
  -> accepted
  -> delivered
  -> seen/opened
~~~

Failure path:

~~~text
sending
  -> transient failure -> retry_wait -> sending
  -> permanent failure -> failed
  -> no consent/provider disabled/budget exhausted -> suppressed
  -> user cancellation -> cancelled
~~~

### Retry policy

- 429: respect Retry-After and retry within a bounded window.
- 5xx/network timeout: exponential backoff with jitter.
- 4xx/template/DLT/invalid destination: do not retry automatically.
- Duplicate worker claim: idempotency key prevents duplicate send.
- Provider disabled: preserve the reminder and mark delivery suppressed; do not
  silently delete it.
- WhatsApp outside window: use approved template or stop; do not send free-form.
- SMS fallback: only after explicit SMS consent.

### Message templates

Store application-owned template keys, not provider-specific strings in reminder
rows:

~~~text
benefit_reminder
benefit_source_link
application_deadline
contact_verification
human_help_followup
provider_incident_admin
~~~

Map each key to:

~~~text
template_key
channel
locale
provider_template_name
provider_template_version
approval_status
content_revision
active
~~~

This lets the admin reviewer see exactly which text is active and roll back a
bad translation or template.

## 12. Phase 8 — Admin and observability integration

The current admin control center already exposes provider posture and audited
provider policies. Extend it with Infobip-specific bounded data.

### Provider screens

Add provider cards for:

~~~text
infobip_sms
infobip_whatsapp
infobip_email
infobip_calls
infobip_voice_stream
~~~

Each card should show:

- configured/not configured;
- channel enabled/disabled;
- sender readiness;
- template readiness;
- last successful request;
- last failure;
- 429 count;
- webhook freshness;
- accepted/delivered/failed counts;
- current circuit state;
- budget posture;
- fallback path;
- last provider status class;
- link to Infobip dashboard only when the link is safe and authorized.

Do not show complete recipients, full message bodies, or provider secrets.

### New telemetry dimensions

Record bounded dimensions:

~~~text
provider=infobip
channel=sms|whatsapp|email|voice
operation=send|webhook|verify|call_event|media_stream
status=accepted|delivered|failed|seen|suppressed
provider_status_group
provider_error_class
template_key
locale
duration_ms
retry_count
cost_currency
cost_minor_units
~~~

Do not record:

- destination;
- body;
- audio;
- transcript;
- raw callbackData;
- access tokens.

### OpenTelemetry spans

Add spans around:

- Infobip HTTP request;
- webhook parse and state transition;
- notification worker claim;
- provider retry;
- voice call event;
- WebSocket connect/disconnect;
- audio frame bridge.

Recommended attributes:

~~~text
sahaayak.provider = infobip
sahaayak.channel = sms|whatsapp|email|voice
sahaayak.operation = send|webhook|call_event|stream
sahaayak.template_key = benefit_reminder
sahaayak.locale = kn
sahaayak.status_group = delivered
~~~

Use an internal message ID and request ID to correlate without putting PII in
callback data. Langfuse should continue to contain only redacted agent traces.

### Metrics and alerts

Add privacy-safe metrics:

~~~text
sahaayak_notification_send_total
sahaayak_notification_delivery_total
sahaayak_notification_failure_total
sahaayak_notification_retry_total
sahaayak_notification_suppressed_total
sahaayak_notification_latency_seconds
sahaayak_notification_queue_age_seconds
sahaayak_provider_rate_limit_total
sahaayak_provider_webhook_lag_seconds
sahaayak_voice_calls_total
sahaayak_voice_call_duration_seconds
sahaayak_infobip_cost_minor_units_total
~~~

Alert on:

- provider authentication failures;
- sustained 429 responses;
- delivery failure rate above threshold;
- webhook silence;
- notification queue age;
- budget threshold;
- voice call failure rate;
- unexpected outbound traffic;
- disabled provider unexpectedly receiving traffic.

## 13. Phase 9 — Frontend changes

The browser should not expose Infobip configuration or call it directly.

### Contact settings

Add an accessible contact/reminder settings surface:

- Add email.
- Add phone/WhatsApp number.
- Show masked destination.
- Show verification status.
- Show consent purpose.
- Show channel-specific opt-out.
- Remove/revoke a contact.
- Choose language for notifications.
- Choose default reminder channel.
- Keep in-app delivery available regardless of external provider health.

### Reminder creation

The reminder form should show only channels that satisfy all conditions:

~~~text
in_app -> always available
email  -> verified email + email consent + provider ready
sms    -> verified phone + SMS consent + provider ready
whatsapp -> verified WhatsApp contact + WhatsApp consent + approved template
~~~

If a channel is unavailable, explain why in plain language. Do not hide the reason
behind a disabled button.

### Delivery status

Show:

- scheduled;
- sent/accepted;
- delivered;
- seen/opened where available;
- failed;
- paused by policy;
- cancelled.

Use text and icons/status labels, not color alone. The same status must remain
understandable to screen-reader users.

### Voice/WhatsApp affordances

Later, add:

- “Continue on WhatsApp” only after explicit linking;
- share-source link;
- send me a reminder;
- request human help;
- microphone/voice-note entry on WhatsApp if enabled.

Do not imply that WhatsApp linkage creates a full citizen account.

## 14. Phase 10 — Security and compliance gates

### Webhook security

Each webhook must have:

- HTTPS;
- a separate secret or provider-supported authorization header;
- body-size limit;
- schema validation;
- replay/idempotency protection;
- event deduplication;
- no browser/admin authentication dependency;
- fast 2xx response;
- asynchronous processing for slow work;
- provider IP allowlisting where stable and supported;
- audit logs for configuration changes, not raw payloads.

### Provider and application security

- Keep Infobip keys only in the server secret store.
- Use separate keys by environment and capability.
- Rotate/revoke keys after testing.
- Never put keys in Vite variables.
- Do not pass provider credentials to the browser or WhatsApp user.
- Do not trust caller IDs or WhatsApp sender strings as authorization.
- Keep rate limits on SMS/WhatsApp/verification/calls independent from browser
  rate limits.
- Add an emergency global outbound kill switch.
- Add per-channel and per-template kill switches.
- Default outbound campaign capability to disabled.
- Treat provider 2xx as accepted, not delivered.

### India and WhatsApp compliance

Before production:

- confirm Indian voice authorization and carrier requirements;
- complete number KYC;
- complete DLT registration and approved SMS templates;
- capture and retain communication consent evidence;
- implement opt-out behavior;
- use approved WhatsApp templates and the correct messaging window;
- avoid unsolicited marketing;
- document retention and deletion for contact data;
- review whether the intended use requires additional enterprise communication
  authorization.

Relevant references:

- [DoT Enterprise Communication Service authorization](https://eservices.dot.gov.in/enterprise-communication-service-authorisation)
- [TRAI telemarketer guidance](https://trai.gov.in/advice-telemarketers)
- [WhatsApp message templates and window rules](https://www.infobip.com/docs/whatsapp/send-a-message)

## 15. Phase 11 — Testing plan

### Unit tests

Add tests for:

- settings validation;
- API-key header construction;
- base URL joining;
- timeout and retry policy;
- 429 Retry-After parsing;
- normalized provider errors;
- E.164 validation;
- email validation;
- Unicode SMS segmentation;
- template lookup and locale fallback;
- consent checks;
- provider-policy checks;
- budget checks;
- idempotency key generation;
- redaction of provider payloads.

### Contract tests with mocked Infobip

Use HTTPX mocking such as respx or a small in-process fake server.

Cover:

- SMS send accepted;
- WhatsApp template accepted;
- WhatsApp free-form rejected outside window;
- email accepted;
- call event received;
- provider 401/403;
- provider 429;
- provider 5xx;
- malformed JSON;
- missing message ID;
- duplicate delivery report;
- out-of-order delivery reports;
- webhook replay;
- invalid webhook secret;
- oversized inbound media.

No real Infobip calls should run in normal CI.

### Integration smoke tests with the trial

Use only the verified test number/address and the account’s permitted sender:

1. SMS send.
2. SMS delivery webhook.
3. Email send.
4. Email delivery/bounce report if available.
5. WhatsApp template send.
6. WhatsApp inbound text.
7. WhatsApp inbound audio.
8. Voice CALL_RECEIVED and CALL_ESTABLISHED.
9. One short voice response.
10. Admin dashboard visibility.
11. Provider disable/rollback.
12. Opt-out and suppression.

Keep the real smoke test budget bounded. Do not create multiple accounts to multiply
trial credits.

### End-to-end product tests

- Save a verified benefit.
- Create an email reminder.
- Create an SMS reminder.
- Create a WhatsApp reminder.
- Run the worker.
- Observe accepted status.
- Deliver a webhook.
- Observe final status.
- Cancel a reminder before dispatch.
- Revoke consent and confirm suppression.
- Delete the guest session and confirm contact/reminder deletion or anonymization.
- Confirm no PII appears in telemetry or traces.

### Voice acceptance tests

For the staged voice path:

- inbound number receives call;
- caller identity becomes a hashed session identity;
- language selection is respected;
- prompt audio plays;
- user audio is captured;
- STT result reaches the shared graph;
- RAG sources remain available for informational questions;
- structured matcher remains authoritative for eligibility;
- Sarvam audio plays back;
- hangup closes the session;
- provider failure returns a safe text/audio fallback;
- max duration and rate limits work;
- no raw recording remains after the retention window.

## 16. Phase 12 — Deployment changes

### Compose services

Add only what is needed:

~~~text
api
web
postgres
redis
notification-worker
optional: telephony-media-bridge
optional: otel-collector
prometheus
alertmanager
~~~

Infobip itself remains an external managed service. Do not add an Infobip
database or try to mirror the provider’s entire dashboard locally.

### Production secrets

Use a secret manager for:

~~~text
INFOBIP_API_KEY
INFOBIP_WEBHOOK_AUTH_SECRET
~~~

Use deployment configuration for:

~~~text
INFOBIP_BASE_URL
INFOBIP_SMS_SENDER
INFOBIP_WHATSAPP_SENDER
INFOBIP_EMAIL_SENDER
INFOBIP_VOICE_NUMBER
INFOBIP_CALLS_CONFIGURATION_ID
INFOBIP_CALLS_SUBSCRIPTION_ID
~~~

### Public endpoints

The deployment must expose only the minimum necessary:

~~~text
POST /api/webhooks/infobip/sms
POST /api/webhooks/infobip/whatsapp
POST /api/webhooks/infobip/email
POST /api/webhooks/infobip/voice/events
WS   /api/telephony/infobip/media
~~~

Every route needs separate routing, rate, size, auth, and observability rules.

### Backups and retention

Back up:

- ContactPoint rows, with encrypted destinations handled according to the key
  management policy.
- Consent events.
- Reminder and NotificationDelivery rows.
- Template mappings.
- Provider policy revisions.
- Infobip external message IDs and status history.

Do not back up raw webhook payloads or audio unless explicitly required for a
time-limited QA purpose.

Retention must distinguish:

- contact destination;
- consent evidence;
- delivery metadata;
- message content;
- raw media;
- provider logs.

## 17. Suggested delivery milestones

These are approximate engineering estimates for one engineer familiar with the
repository; account onboarding and provider approval can take longer than coding.

### M0 — Infobip capability proof

**Approximate effort:** 0.5–1 day of coding/configuration, plus provider response time.

- Account and trial setup.
- Base URL/key/scope verification.
- Test SMS/email/WhatsApp.
- Confirm voice number and media/SIP activation.
- Add capability notes to operations docs.

### M1 — Shared client and provider status

**Approximate effort:** 1–2 days.

- Infobip HTTP client.
- Settings and secret examples.
- Error/retry/correlation behavior.
- Provider health and admin cards.
- Unit/contract tests.

### M2 — Email and SMS notification adapters

**Approximate effort:** 2–4 days.

- ContactPoint and consent foundation.
- NotificationDelivery table.
- Email templates and domain setup.
- SMS adapter, DLT template mapping, delivery webhooks.
- Notification worker.
- End-to-end trial smoke test.

### M3 — WhatsApp adapter

**Approximate effort:** 3–5 days plus Meta template approval.

- WABA/sender configuration.
- Utility/auth templates.
- Outbound template/free-form adapters.
- Inbound text/button/audio webhook.
- Delivery/seen/template status.
- Media download/delete controls.
- Channel-specific admin and UI.

### M4 — Calls API clip-based voice proof

**Approximate effort:** 2–4 days plus account activation.

- Calls Configuration.
- Voice number link.
- Event subscription/webhooks.
- Capture/play loop.
- Shared runtime integration.
- Short Kannada/Hindi test.

### M5 — Production voice transport

**Approximate effort:** 5–10+ days depending selected path.

- Jambonz/SIP/SBC integration or direct Infobip WebSocket.
- Streaming STT/TTS interfaces if using real-time media.
- Audio codec bridge.
- Turn detection/interruption.
- Call lifecycle, budgets, rate limits, and incident controls.
- Production compliance and carrier validation.

## 18. Definition of done

Infobip integration is complete for the first beta only when:

### Shared foundation

- Infobip credentials are server-only and environment-separated.
- Provider policies can enable, disable, fallback, and roll back each channel.
- Provider calls have timeouts, bounded retries, idempotency, and safe telemetry.
- Webhooks are authenticated, validated, deduplicated, and replay-safe.
- No sensitive destination or message body is written to logs/traces.

### Email

- Sending domain is verified.
- Transactional templates exist for English, Hindi, and Kannada.
- Email delivery/bounce states update the application.
- A user can opt out or revoke the contact.

### SMS

- Indian sender/DLT setup is complete.
- Templates are approved and mapped.
- Delivery reports update the application.
- Unicode/segment and cost limits are enforced.
- STOP/opt-out handling is tested.

### WhatsApp

- WABA and sender are approved.
- Utility/auth templates are approved.
- 24-hour window handling is correct.
- Inbound text and audio are normalized into the shared runtime.
- Delivery, seen, inbound, and opt-out events are handled.

### Voice

- The chosen voice path is documented and tested.
- An inbound call reaches the shared agent runtime.
- Kannada voice is tested end to end.
- Hindi has a short validated flow.
- Outbound campaigns remain disabled.
- Rate, concurrency, duration, recording, and cost controls are active.

### Product and operations

- Reminders require verified contact and explicit consent.
- In-app reminders remain available as a fallback.
- Admin sees channel health, delivery outcomes, policy, and audit history.
- Staging has a real redacted OTel/Langfuse trace.
- Backups, retention, alerts, and rollback are exercised.

## 19. Immediate next actions

1. Create an Infobip trial account and record the personalized base URL without
   sharing the API key.
2. Verify SMS, email, and WhatsApp trial capability with the registered test
   recipient.
3. Ask Infobip to confirm Indian voice DID, Calls API media-streaming, SIP trunk,
   DLT, and WhatsApp onboarding requirements.
4. Add a provider-capability record to the admin/operations documentation.
5. Implement the shared Infobip HTTP client and settings.
6. Implement ContactPoint, consent, NotificationDelivery, and worker foundations.
7. Ship email and SMS adapters first.
8. Ship WhatsApp inbound/outbound messaging next.
9. Run the staged Calls API voice proof.
10. Decide between Infobip-to-Jambonz SIP and direct Infobip WebSocket before
    implementing real-time telephony.
11. Update docs/implementation-roadmap.md as each milestone becomes verified.

