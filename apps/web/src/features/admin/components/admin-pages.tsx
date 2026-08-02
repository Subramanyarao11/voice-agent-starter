import { useState, type FormEvent } from "react";

import { AlertTriangle, CheckCircle2, Clock3, ExternalLink, RefreshCw, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAdminSessionStore } from "@/features/admin/store";
import {
  useAdminAuditQuery,
  useAdminConversationsQuery,
  useAdminEscalationsQuery,
  useAdminImportsQuery,
  useAdminLanguagesQuery,
  useAdminMeQuery,
  useAdminOverviewQuery,
  useAdminProvidersQuery,
  useAdminReviewsQuery,
  useAdminSystemQuery,
  useAdminTelemetryQuery,
  useRollbackAdminProviderPolicyMutation,
  useResolveAdminEscalationMutation,
  useReviewAdminBenefitMutation,
  useUpdateAdminProviderPolicyMutation,
} from "@/features/admin/queries";
import type { AdminView } from "@/features/admin/components/admin-shell";
import type { ProviderPolicy, ProviderPolicyUpdate } from "@/features/admin/api";
import { toUserMessage } from "@/lib/api";

export function AdminPage({ view }: { view: AdminView }) {
  const token = useAdminSessionStore((state) => state.token);
  const meQuery = useAdminMeQuery(token);

  switch (view) {
    case "overview":
      return <OverviewPage token={token} />;
    case "conversations":
      return <ConversationsPage token={token} />;
    case "telemetry":
      return <TelemetryPage token={token} />;
    case "escalations":
      return <EscalationsPage token={token} role={meQuery.data?.role ?? "observer"} />;
    case "benefits":
      return <BenefitsPage token={token} role={meQuery.data?.role ?? "observer"} />;
    case "providers":
      return <ProvidersPage token={token} role={meQuery.data?.role ?? "observer"} />;
    case "languages":
      return <LanguagesPage token={token} />;
    case "audit":
      return <AuditPage token={token} />;
    case "system":
      return <SystemPage token={token} />;
  }
}

function OverviewPage({ token }: { token: string }) {
  const query = useAdminOverviewQuery(token);
  if (query.isPending) return <Loading label="Loading platform overview…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  const { traffic, quality } = query.data;
  return (
    <div className="space-y-6">
      <PageIntro title="Operational overview" description={`Last ${query.data.window_hours} hours · refreshed ${formatTime(query.data.generated_at)}`} />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Requests" value={formatNumber(traffic.requests)} detail={`${formatNumber(traffic.turns)} conversation turns`} />
        <MetricCard label="P95 latency" value={`${Math.round(traffic.p95_latency_ms)} ms`} detail={`P50 ${Math.round(traffic.p50_latency_ms)} ms`} tone={traffic.p95_latency_ms > 1500 ? "warning" : "default"} />
        <MetricCard label="5xx error rate" value={formatPercent(traffic.error_rate)} detail={`${traffic.errors} server errors`} tone={traffic.error_rate > 0.02 ? "warning" : "default"} />
        <MetricCard label="Active sessions" value={formatNumber(traffic.active_sessions)} detail={`${quality.open_escalations} open escalations`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.1fr_.9fr]">
        <Card className="border-paper/10 bg-paper/[0.04] text-paper">
          <CardHeader><CardTitle className="text-paper">Quality and corpus trust</CardTitle></CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <Stat label="Active benefits" value={quality.active_benefits} />
            <Stat label="Human verified" value={quality.verified_benefits} tone="good" />
            <Stat label="Needs review" value={quality.needs_review_benefits} tone="warning" />
            <Stat label="Illustrative only" value={quality.illustrative_benefits} tone="muted" />
            <Stat label="Escalation rate" value={formatPercent(quality.escalation_rate)} />
            <Stat label="No-match turns" value={quality.no_match_turns} tone={quality.no_match_turns ? "warning" : "default"} />
          </CardContent>
        </Card>
        <Card className="border-paper/10 bg-paper/[0.04] text-paper">
          <CardHeader><CardTitle className="text-paper">Provider posture</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {query.data.providers.map((provider) => <ProviderRow key={provider.name} provider={provider} />)}
          </CardContent>
        </Card>
      </div>

      <Card className="border-paper/10 bg-paper/[0.04] text-paper">
        <CardHeader className="flex-row items-center justify-between space-y-0"><CardTitle className="text-paper">Recent server errors</CardTitle><Badge variant="outline" className="border-paper/15 text-paper/45">redacted</Badge></CardHeader>
        <CardContent><ErrorTable errors={query.data.recent_errors} /></CardContent>
      </Card>
    </div>
  );
}

function ConversationsPage({ token }: { token: string }) {
  const query = useAdminConversationsQuery(token);
  if (query.isPending) return <Loading label="Loading redacted conversations…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  return (
    <div className="space-y-6">
      <PageIntro title="Conversation operations" description="Redacted session metadata only. Raw transcript, audio, caller identifiers, and profile values are intentionally absent from this view." />
      <Card className="border-paper/10 bg-paper/[0.04] text-paper">
        <CardContent className="overflow-x-auto p-0">
          <table className="w-full min-w-[720px] text-left text-sm"><caption className="sr-only">Redacted conversation sessions</caption><thead className="border-b border-paper/10 text-xs uppercase tracking-[0.12em] text-paper/40"><tr><th className="px-5 py-4">Session key</th><th className="px-5 py-4">Locale</th><th className="px-5 py-4">State</th><th className="px-5 py-4">Turns</th><th className="px-5 py-4">Last intent</th><th className="px-5 py-4">Last contact</th></tr></thead><tbody>{query.data.items.map((item) => <tr key={item.session_key} className="border-b border-paper/5 last:border-0"><td className="px-5 py-4 font-mono text-xs text-acid">{item.session_key}</td><td className="px-5 py-4">{item.language_code}</td><td className="px-5 py-4">{item.state_code}</td><td className="px-5 py-4">{item.turn_count}</td><td className="px-5 py-4 text-paper/65">{item.last_intent ?? "—"}</td><td className="px-5 py-4 text-paper/55">{formatTime(item.last_contact_at)}</td></tr>)}</tbody></table>
          {!query.data.items.length && <EmptyState label="No sessions in the current data window." />}
        </CardContent>
      </Card>
    </div>
  );
}

function TelemetryPage({ token }: { token: string }) {
  const query = useAdminTelemetryQuery(token);
  if (query.isPending) return <Loading label="Loading telemetry events…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  return (
    <div className="space-y-6">
      <PageIntro title="Telemetry stream" description="Safe operational events with request correlation. Payloads, transcripts, audio, and sensitive slots are not stored here." />
      <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardContent className="overflow-x-auto p-0"><table className="w-full min-w-[1080px] text-left text-sm"><caption className="sr-only">Recent telemetry events</caption><thead className="border-b border-paper/10 text-xs uppercase tracking-[0.12em] text-paper/40"><tr><th className="px-5 py-4">Time</th><th className="px-5 py-4">Type</th><th className="px-5 py-4">Route</th><th className="px-5 py-4">Surface</th><th className="px-5 py-4">Outcome</th><th className="px-5 py-4">Duration</th><th className="px-5 py-4">Request</th><th className="px-5 py-4">Trace</th></tr></thead><tbody>{query.data.map((event) => <tr key={event.id} className="border-b border-paper/5 last:border-0"><td className="px-5 py-4 text-paper/55">{formatTime(event.created_at)}</td><td className="px-5 py-4"><Badge variant="outline" className="border-paper/15 text-paper/60">{event.event_type}</Badge></td><td className="px-5 py-4 font-mono text-xs text-paper/70">{event.route}</td><td className="px-5 py-4">{event.surface}</td><td className="px-5 py-4">{outcomeBadge(event.outcome)}</td><td className="px-5 py-4 text-paper/55">{event.duration_ms == null ? "—" : `${Math.round(event.duration_ms)} ms`}</td><td className="px-5 py-4 font-mono text-xs text-acid">{event.request_id ?? "—"}</td><td className="px-5 py-4 font-mono text-xs">{event.trace_url ? <a className="text-acid underline-offset-4 hover:underline" href={event.trace_url} target="_blank" rel="noreferrer">Open trace</a> : event.trace_id ? <span className="text-paper/50" title={event.trace_id}>{event.trace_id.slice(0, 12)}…</span> : "—"}</td></tr>)}</tbody></table></CardContent></Card>
    </div>
  );
}

function EscalationsPage({ token, role }: { token: string; role: string }) {
  const query = useAdminEscalationsQuery(token);
  const mutation = useResolveAdminEscalationMutation(token);
  if (query.isPending) return <Loading label="Loading escalation queue…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  const canResolve = role === "operator" || role === "admin";
  return (
    <div className="space-y-6"><PageIntro title="Escalation queue" description="Operator handoffs created when the agent declines to guess. Raw context is available only to operator and admin roles." />
      <div className="grid gap-4">{query.data.map((ticket) => <Card key={ticket.id} className="border-paper/10 bg-paper/[0.04] text-paper"><CardContent className="flex flex-wrap items-start justify-between gap-5 p-5"><div><div className="flex flex-wrap items-center gap-2"><Badge variant="warning">{ticket.reason}</Badge><span className="font-mono text-xs text-paper/40">{ticket.id}</span></div><p className="mt-3 max-w-3xl text-sm leading-6 text-paper/70">{ticket.transcript_excerpt || "Sensitive context is redacted for this role."}</p><p className="mt-2 text-xs text-paper/40">Created {formatTime(ticket.created_at)} · session {ticket.session_id}</p></div>{canResolve && <Button size="sm" variant="outline" disabled={mutation.isPending} onClick={() => mutation.mutate(ticket.id)}>{mutation.isPending ? "Resolving…" : "Resolve"}</Button>}</CardContent></Card>)}</div>
      {!query.data.length && <EmptyState label="No open escalations." />}
    </div>
  );
}

function BenefitsPage({ token, role }: { token: string; role: string }) {
  const query = useAdminReviewsQuery(token);
  const imports = useAdminImportsQuery(token);
  const mutation = useReviewAdminBenefitMutation(token);
  if (query.isPending) return <Loading label="Loading benefit review queue…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  const canReview = role === "reviewer" || role === "admin";
  return (
    <div className="space-y-6"><PageIntro title="Benefits, provenance, and review" description="Machine-structured rows stay inactive until a reviewer records a decision. Every change creates an immutable audit event." />
      <div className="grid gap-4 sm:grid-cols-3">{Object.entries(query.data.status_counts).map(([status, count]) => <MetricCard key={status} label={status.replaceAll("_", " ")} value={String(count)} detail="rows in corpus" tone={status === "needs_review" ? "warning" : "default"} />)}</div>
      <div className="grid gap-4">{query.data.items.map((item) => <ReviewCard key={item.id} item={item} canReview={canReview} onSubmit={(input) => mutation.mutate({benefitId: item.id, ...input})} pending={mutation.isPending} />)}</div>
      {!query.data.items.length && <EmptyState label="No benefits are currently waiting for human review." />}
      <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardHeader><CardTitle className="text-paper">Import history</CardTitle></CardHeader><CardContent className="space-y-3">{imports.data?.map((run) => <div key={run.id} className="flex flex-wrap justify-between gap-3 border-b border-paper/10 pb-3 text-sm last:border-0"><div><p className="font-semibold">{run.source_name}</p><p className="text-xs text-paper/45">{run.model_name || "No model recorded"} · prompt {run.prompt_version || "—"}</p></div><span className="text-xs text-paper/55">{run.accepted_count}/{run.input_count} accepted · {formatTime(run.started_at)}</span></div>)}{imports.data && !imports.data.length && <EmptyState label="No import manifests recorded." />}</CardContent></Card>
    </div>
  );
}

function ProvidersPage({ token, role }: { token: string; role: string }) {
  const query = useAdminProvidersQuery(token);
  const update = useUpdateAdminProviderPolicyMutation(token);
  const rollback = useRollbackAdminProviderPolicyMutation(token);
  if (query.isPending) return <Loading label="Loading provider posture…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  const canManage = role === "admin";
  return <div className="space-y-6"><PageIntro title="Providers, spend, and fallback" description="Configuration and request-level posture are visible here. Cost values are estimates where the provider does not expose a reconciliation API." /><div className="grid gap-4 lg:grid-cols-2">{query.data.providers.map((provider) => <Card key={provider.name} className="border-paper/10 bg-paper/[0.04] text-paper"><CardHeader className="flex-row items-center justify-between space-y-0"><CardTitle className="text-paper">{provider.name}</CardTitle>{provider.configured ? <Badge variant="success">{provider.health}</Badge> : <Badge variant="warning">not configured</Badge>}</CardHeader><CardContent className="space-y-3"><div className="grid grid-cols-2 gap-3 text-sm"><Stat label="Requests" value={provider.requests} /><Stat label="Failures" value={provider.failures} tone={provider.failures ? "warning" : "default"} />{provider.budget_usd != null && <Stat label="Budget remaining" value={`$${provider.remaining_usd?.toFixed(2) ?? "—"}`} tone="good" />}{provider.cache_hits > 0 && <Stat label="Cache hits" value={provider.cache_hits} tone="good" />}</div><p className="text-xs leading-5 text-paper/45">{provider.note}</p></CardContent></Card>)}</div><Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardHeader><CardTitle className="text-paper">Audited provider policies</CardTitle><p className="text-sm leading-6 text-paper/50">{query.data.controls_note}</p></CardHeader><CardContent className="grid gap-4">{query.data.policies.map((policy) => <ProviderPolicyCard key={`${policy.id}-${policy.revision}`} policy={policy} canManage={canManage} onUpdate={(input) => update.mutate(input)} onRollback={(input) => rollback.mutate(input)} pending={update.isPending || rollback.isPending} />)}</CardContent></Card>{!canManage && <p className="rounded-xl border border-paper/10 bg-paper/[0.03] px-4 py-3 text-sm leading-6 text-paper/50">Your role can inspect effective policy posture, but only an admin can change or roll back provider routing.</p>}</div>;
}

function LanguagesPage({ token }: { token: string }) {
  const query = useAdminLanguagesQuery(token);
  if (query.isPending) return <Loading label="Loading language readiness…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  return <div className="space-y-6"><PageIntro title="Language readiness" description="A locale is launch-ready only when interface, prompts, data, understanding, voice, and accessibility have evidence—not merely a catalog row." /><Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardContent className="overflow-x-auto p-0"><table className="w-full min-w-[900px] text-left text-sm"><caption className="sr-only">Language readiness matrix</caption><thead className="border-b border-paper/10 text-xs uppercase tracking-[0.12em] text-paper/40"><tr><th className="px-5 py-4">Language</th><th className="px-5 py-4">Rollout</th><th className="px-5 py-4">Prompts</th><th className="px-5 py-4">Data</th><th className="px-5 py-4">Voice</th><th className="px-5 py-4">Providers</th></tr></thead><tbody>{query.data.map((language) => <tr key={language.code} className="border-b border-paper/5 last:border-0"><td className="px-5 py-4"><span className="font-semibold">{language.native_name}</span><span className="ml-2 text-xs text-paper/40">{language.code}</span></td><td className="px-5 py-4">{language.rollout_status}</td><td className="px-5 py-4">{language.prompt_ready ? "ready" : "missing"}</td><td className="px-5 py-4">{language.data_status} · {language.active_benefits}</td><td className="px-5 py-4">{language.voice_status}</td><td className="px-5 py-4 text-xs text-paper/50">{language.stt_provider} → {language.tts_provider}</td></tr>)}</tbody></table></CardContent></Card></div>;
}

function AuditPage({ token }: { token: string }) {
  const query = useAdminAuditQuery(token);
  if (query.isPending) return <Loading label="Loading audit history…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  return <div className="space-y-6"><PageIntro title="Audit log" description="Append-only workforce actions with safe before/after state. Audit entries are created in the same transaction as review and escalation changes." /><Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardContent className="space-y-3 p-5">{query.data.map((event) => <article key={event.id} className="rounded-xl border border-paper/10 bg-ink/20 p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className="border-acid/25 text-acid">{event.action}</Badge><span className="font-mono text-xs text-paper/45">{event.actor_id} · {event.actor_role}</span></div><time className="text-xs text-paper/40">{formatTime(event.created_at)}</time></div><p className="mt-3 text-sm text-paper/70">{event.reason}</p><p className="mt-2 font-mono text-xs text-paper/40">{event.target_type}/{event.target_id} · request {event.request_id ?? "—"}</p></article>)}{!query.data.length && <EmptyState label="No audited workforce actions yet." />}</CardContent></Card></div>;
}

function SystemPage({ token }: { token: string }) {
  const query = useAdminSystemQuery(token);
  if (query.isPending) return <Loading label="Loading system state…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  return <div className="space-y-6"><PageIntro title="System and deployment state" description="Safe configuration flags and revision identifiers help an operator explain what is running without exposing secrets." /><div className="grid gap-4 lg:grid-cols-2"><Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardHeader><CardTitle className="text-paper">Revision</CardTitle></CardHeader><CardContent className="space-y-3"><Stat label="Environment" value={query.data.environment} /><Stat label="Database" value={query.data.database_mode} /><Stat label="Migration" value={query.data.migration_revision ?? "unknown"} /><Stat label="Commit" value={query.data.git_commit_sha} /><Stat label="Process started" value={formatTime(query.data.process_started_at)} /></CardContent></Card><Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardHeader><CardTitle className="text-paper">Configuration posture</CardTitle></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2">{Object.entries(query.data.configuration).map(([key, value]) => <Stat key={key} label={key.replaceAll("_", " ")} value={value ? "enabled" : "disabled"} tone={value ? "good" : "muted"} />)}</CardContent></Card></div><Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardHeader><CardTitle className="text-paper">Operator notes</CardTitle></CardHeader><CardContent><ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-paper/60">{query.data.deployment_notes.map((note) => <li key={note}>{note}</li>)}</ul></CardContent></Card></div>;
}

function ReviewCard({ item, canReview, onSubmit, pending }: { item: import("@/features/admin/api").ReviewItem; canReview: boolean; onSubmit: (input: { status: string; reason: string; activate: boolean }) => void; pending: boolean }) {
  const [status, setStatus] = useState(item.verification_status);
  const [reason, setReason] = useState("Reviewed against the source document");
  const [activate, setActivate] = useState(item.is_active);
  return <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardContent className="space-y-4 p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className="border-orange/30 text-orange">{item.verification_status}</Badge><span className="font-mono text-xs text-paper/40">{item.id}</span></div><h3 className="mt-2 text-lg font-bold">{item.name}</h3><p className="mt-1 text-sm text-paper/50">{item.domain} · {item.state_code ?? "central"} · {item.source_title || "Source title missing"}</p></div>{item.source_document_url && <a className="inline-flex items-center gap-1 text-xs font-semibold text-acid underline-offset-4 hover:underline" href={item.source_document_url} target="_blank" rel="noreferrer">Source <ExternalLink className="size-3" aria-hidden="true" /></a>}</div><details className="rounded-xl border border-paper/10 bg-ink/20"><summary className="cursor-pointer px-4 py-3 text-sm font-semibold">Show machine review and source excerpt</summary><div className="space-y-3 border-t border-paper/10 px-4 py-3 text-xs leading-5 text-paper/60"><p>{item.source_excerpt || "No source excerpt stored."}</p><pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-ink p-3 font-mono text-[0.68rem]">{JSON.stringify(item.automated_review, null, 2)}</pre></div></details>{canReview ? <form className="grid gap-3 border-t border-paper/10 pt-4 md:grid-cols-[180px_1fr_auto] md:items-end" onSubmit={(event) => { event.preventDefault(); onSubmit({status, reason, activate}); }}><label className="grid gap-1 text-xs font-semibold text-paper/60">Decision<select value={status} onChange={(event) => setStatus(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-2 text-sm text-paper"><option value="human_verified">Human verified</option><option value="needs_review">Needs review</option><option value="stale">Stale</option><option value="machine_reviewed">Machine reviewed</option></select></label><label className="grid gap-1 text-xs font-semibold text-paper/60">Reason<input value={reason} onChange={(event) => setReason(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" /></label><div className="flex items-center gap-3"><label className="flex items-center gap-2 text-xs text-paper/60"><input type="checkbox" checked={activate} onChange={(event) => setActivate(event.target.checked)} /> Publish</label><Button type="submit" size="sm" disabled={pending || reason.trim().length < 3}>{pending ? "Saving…" : "Save decision"}</Button></div></form> : <p className="text-xs text-paper/45">Your role can inspect this row but cannot change publication status.</p>}</CardContent></Card>;
}

function PageIntro({ title, description }: { title: string; description: string }) {
  return <div><h2 className="text-2xl font-extrabold tracking-tight">{title}</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-paper/55">{description}</p></div>;
}

function MetricCard({ label, value, detail, tone = "default" }: { label: string; value: string; detail: string; tone?: "default" | "warning" }) {
  return <Card className={`border-paper/10 bg-paper/[0.04] text-paper ${tone === "warning" ? "border-orange/25" : ""}`}><CardContent className="p-5"><p className="text-xs uppercase tracking-[0.14em] text-paper/45">{label}</p><p className="mt-3 font-mono text-3xl text-acid">{value}</p><p className="mt-2 text-xs text-paper/45">{detail}</p></CardContent></Card>;
}

function Stat({ label, value, tone = "default" }: { label: string; value: string | number; tone?: "default" | "good" | "warning" | "muted" }) {
  const text = tone === "good" ? "text-blue" : tone === "warning" ? "text-orange" : tone === "muted" ? "text-paper/45" : "text-paper";
  return <div className="rounded-xl border border-paper/10 bg-ink/20 px-3 py-3"><p className="text-xs capitalize text-paper/45">{label}</p><p className={`mt-1 font-mono text-lg ${text}`}>{value}</p></div>;
}

function ProviderPolicyCard({
  policy,
  canManage,
  onUpdate,
  onRollback,
  pending,
}: {
  policy: ProviderPolicy;
  canManage: boolean;
  onUpdate: (input: { provider: string; scope: string; payload: ProviderPolicyUpdate }) => void;
  onRollback: (input: { provider: string; scope: string; reason: string }) => void;
  pending: boolean;
}) {
  const [enabled, setEnabled] = useState(policy.enabled);
  const [primaryProvider, setPrimaryProvider] = useState(policy.primary_provider);
  const [fallbackProvider, setFallbackProvider] = useState(policy.fallback_provider ?? "");
  const [circuitState, setCircuitState] = useState<ProviderPolicyUpdate["circuit_state"]>(
    policy.circuit_state as ProviderPolicyUpdate["circuit_state"],
  );
  const [dailyBudget, setDailyBudget] = useState(formatBudget(policy.daily_budget_usd));
  const [monthlyBudget, setMonthlyBudget] = useState(formatBudget(policy.monthly_budget_usd));
  const [expiresAt, setExpiresAt] = useState(toDateTimeInput(policy.override_expires_at));
  const [reason, setReason] = useState("Reviewed provider posture");
  const requiresExpiry = !enabled || circuitState !== "closed";
  const canRollback = !policy.id.startsWith("default:");
  const expiredOverride = Boolean(
    policy.override_expires_at && new Date(policy.override_expires_at).getTime() <= Date.now(),
  );

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage || !reason.trim() || (requiresExpiry && !expiresAt)) return;
    onUpdate({
      provider: policy.provider,
      scope: policy.scope,
      payload: {
        enabled,
        primary_provider: primaryProvider.trim(),
        fallback_provider: fallbackProvider.trim() || null,
        circuit_state: circuitState,
        daily_budget_usd: parseBudget(dailyBudget),
        monthly_budget_usd: parseBudget(monthlyBudget),
        override_expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
        reason: reason.trim(),
      },
    });
  };

  return <article className="rounded-xl border border-paper/10 bg-ink/20 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><Badge variant={expiredOverride ? "outline" : policy.enabled && policy.circuit_state === "closed" ? "success" : "warning"}>{expiredOverride ? "expired → default" : policy.enabled ? policy.circuit_state : "disabled"}</Badge><span className="font-semibold">{policy.provider} / {policy.scope}</span><span className="font-mono text-xs text-paper/40">revision {policy.revision}</span></div><p className="mt-2 text-xs leading-5 text-paper/50">Primary {policy.primary_provider} → fallback {policy.fallback_provider ?? "none"}. {expiredOverride ? "This override is expired; the built-in policy is active." : policy.override_expires_at ? `Override expires ${formatTime(policy.override_expires_at)}.` : "No temporary override."}</p></div>{canRollback && <Button type="button" size="sm" variant="outline" disabled={!canManage || pending || !reason.trim()} onClick={() => onRollback({provider: policy.provider, scope: policy.scope, reason: reason.trim()})}>Rollback latest</Button>}</div>{canManage ? <form className="mt-4 grid gap-3 border-t border-paper/10 pt-4 lg:grid-cols-2" onSubmit={submit}><label className="flex items-center gap-2 text-sm font-semibold"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> Policy enabled</label><label className="grid gap-1 text-xs font-semibold text-paper/60">Circuit state<select value={circuitState} onChange={(event) => setCircuitState(event.target.value as ProviderPolicyUpdate["circuit_state"])} className="h-10 rounded-lg border border-paper/15 bg-ink px-2 text-sm text-paper"><option value="closed">Closed</option><option value="half_open">Half-open</option><option value="open">Open</option></select></label><label className="grid gap-1 text-xs font-semibold text-paper/60">Primary provider<input value={primaryProvider} onChange={(event) => setPrimaryProvider(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" maxLength={80} /></label><label className="grid gap-1 text-xs font-semibold text-paper/60">Fallback provider<input value={fallbackProvider} onChange={(event) => setFallbackProvider(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" maxLength={80} placeholder="none" /></label><label className="grid gap-1 text-xs font-semibold text-paper/60">Daily budget (USD)<input type="number" min="0" max="15" step="0.01" value={dailyBudget} onChange={(event) => setDailyBudget(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" placeholder="unset" /></label><label className="grid gap-1 text-xs font-semibold text-paper/60">Monthly budget (USD)<input type="number" min="0" max="15" step="0.01" value={monthlyBudget} onChange={(event) => setMonthlyBudget(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" placeholder="unset" /></label><label className="grid gap-1 text-xs font-semibold text-paper/60">Temporary override expiry<input type="datetime-local" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" />{requiresExpiry && <span className="text-[0.7rem] font-normal text-orange">Required when disabled or circuit is not closed; maximum 24 hours.</span>}</label><label className="grid gap-1 text-xs font-semibold text-paper/60">Reason<input required minLength={3} maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" /></label><div className="flex items-center justify-between gap-3 lg:col-span-2"><p className="text-xs leading-5 text-paper/40">Every save is written to the audit log with a before/after snapshot.</p><Button type="submit" size="sm" disabled={pending || !reason.trim() || !primaryProvider.trim() || (requiresExpiry && !expiresAt)}>{pending ? "Saving…" : "Save policy"}</Button></div></form> : <p className="mt-4 border-t border-paper/10 pt-4 text-xs leading-5 text-paper/45">Read-only effective policy snapshot. Temporary overrides expire automatically; rollback is admin-only.</p>}</article>;
}

function formatBudget(value: number | null) {
  return value == null ? "" : String(value);
}

function parseBudget(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function toDateTimeInput(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function ProviderRow({ provider }: { provider: import("@/features/admin/api").AdminOverview["providers"][number] }) {
  return <div className="flex items-center justify-between gap-3 rounded-xl border border-paper/10 bg-ink/20 px-3 py-3"><div><p className="font-semibold">{provider.name}</p><p className="text-xs text-paper/45">{provider.requests} requests · {provider.failures} failures</p></div>{provider.configured ? <Badge variant="success">{provider.health}</Badge> : <Badge variant="warning">offline</Badge>}</div>;
}

function ErrorTable({ errors }: { errors: import("@/features/admin/api").AdminOverview["recent_errors"] }) {
  if (!errors.length) return <EmptyState label="No server errors in the selected window." />;
  return <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-sm"><caption className="sr-only">Recent server errors</caption><thead className="border-b border-paper/10 text-xs uppercase tracking-[0.12em] text-paper/40"><tr><th className="px-3 py-3">Time</th><th className="px-3 py-3">Route</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Request</th></tr></thead><tbody>{errors.map((error) => <tr key={`${error.request_id}-${error.created_at}`} className="border-b border-paper/5 last:border-0"><td className="px-3 py-3 text-paper/55">{formatTime(error.created_at)}</td><td className="px-3 py-3 font-mono text-xs">{error.method} {error.route}</td><td className="px-3 py-3 text-orange">{error.status_code ?? "—"}</td><td className="px-3 py-3 font-mono text-xs text-acid">{error.request_id ?? "—"}</td></tr>)}</tbody></table></div>;
}

function Loading({ label }: { label: string }) { return <div className="grid min-h-56 place-items-center rounded-2xl border border-paper/10 bg-paper/[0.03] text-sm text-paper/55"><span role="status" className="inline-flex items-center gap-2"><RefreshCw className="size-4 animate-spin" aria-hidden="true" />{label}</span></div>; }
function ErrorPanel({ error }: { error: unknown }) { return <div role="alert" className="rounded-2xl border border-orange/25 bg-orange/10 p-5 text-sm leading-6 text-orange"><div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" /><span>{toUserMessage(error)}</span></div></div>; }
function EmptyState({ label }: { label: string }) { return <p className="px-4 py-8 text-center text-sm text-paper/45">{label}</p>; }
function outcomeBadge(outcome: string) { if (outcome === "success") return <Badge variant="success"><CheckCircle2 className="size-3" aria-hidden="true" />success</Badge>; if (outcome === "error" || outcome === "escalated") return <Badge variant="warning"><ShieldAlert className="size-3" aria-hidden="true" />{outcome}</Badge>; return <Badge variant="outline" className="border-paper/15 text-paper/55"><Clock3 className="size-3" aria-hidden="true" />{outcome || "event"}</Badge>; }
function formatTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString([], {dateStyle: "medium", timeStyle: "short"}); }
function formatNumber(value: number) { return new Intl.NumberFormat().format(value); }
function formatPercent(value: number) { return `${(value * 100).toFixed(value > 0 && value < 0.1 ? 1 : 0)}%`; }
