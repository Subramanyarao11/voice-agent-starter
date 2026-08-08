# Operator escalation operations

Sahaayak creates a durable escalation ticket when a caller requests a person,
the agent repeatedly cannot understand them, or the evidence is too weak to
answer safely. The ticket is the source of truth; a notification channel may be
added later without changing the handoff contract.

## Queue behavior

Tickets start as `open`. An operator or admin claims one atomically, moving it to
`claimed` and recording `assigned_to` and `claimed_at`. A claimed ticket can be
updated with bounded operational notes and resolved with an explicit outcome:

- `answered`
- `referred`
- `no_action`
- `duplicate`
- `unreachable`

The queue sorts active tickets by SLA breach, deadline, and creation time. A
default 24-hour deadline is assigned at creation through `ESCALATION_SLA_HOURS`.
Legacy tickets created before migration `20260808_0012` may have no deadline and
are labelled as such rather than being silently treated as on time.

## Routing behavior

New tickets first try an approved, recently verified directory route from:

1. an exact pincode match;
2. a pincode-prefix match; or
3. an exact district match for the session state and conversation domain.

When no current directory row matches, tickets receive the deterministic
fallback route from:

1. the session state code;
2. the conversation domain (scheme, scholarship, or job); and
3. a caller-stated city/district value when one exists.

Approved directory matches are marked `authoritative_directory` and retain the
directory row ID, source URL, and verification timestamp on the ticket. The
admin console displays that provenance. Stale or unapproved rows are never used
for runtime routing; a `state_domain_fallback` is still only a routing hint and
must be confirmed before referral. Operators/admins can replace the department
and location hint; that change is marked `operator_override` and audited.

Do not infer a department, district, or pincode from an unverified transcript.
Directory data is imported with `scripts/16_import_department_directory.py` and
must carry a source name, URL, and verification timestamp. See
`data/directory/README.md` for the official-source format and the review gate.

## API

All endpoints require workforce authentication. Production uses OIDC + MFA;
static tokens are only a local/test seam.

```text
GET  /api/escalations?status=active&overdue_only=false
POST /api/escalations/{id}/claim
POST /api/escalations/{id}/notes       {"text":"..."}
POST /api/escalations/{id}/route       {"department":"...", "routing_location":"..."}
POST /api/escalations/{id}/resolve    {"resolution_code":"referred", "note":"..."}
```

Observers and reviewers can see queue metadata but not transcript excerpts,
caller context, location hints, or operator notes. Operators and admins can see
the restricted fields needed to complete a handoff. Every claim, note, route
change, and resolution writes an audit event in the same database transaction.

## Deployment checklist

```bash
uv run python -m alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.auth.yml up -d --build
curl http://localhost:8000/health
```

Before production, configure the actual department directory or a staffed
operator process, import and human-approve the applicable district/pincode
records, define SLA escalation alerts, test two concurrent claims against
Postgres, and confirm retention/deletion rules for transcript excerpts and
caller context.
