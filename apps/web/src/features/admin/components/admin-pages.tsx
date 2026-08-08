import { useState, type FormEvent } from "react";

import { AlertTriangle, CheckCircle2, Clock3, Download, ExternalLink, RefreshCw, RotateCcw, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useAdminSessionStore } from "@/features/admin/store";
import {
  useAdminAuditQuery,
  useAdminBenefitReportsQuery,
  useAdminConversationsQuery,
  useAdminDirectoryQuery,
  useAdminEscalationsQuery,
  useAdminImportsQuery,
  useAdminLanguagesQuery,
  useAdminNotificationsQuery,
  useAdminFreshnessQuery,
  useAdminEvaluationsQuery,
  useAdminFeatureFlagsQuery,
  useAdminMeQuery,
  useAdminOverviewQuery,
  useAdminBenefitVersionsQuery,
  useAdminDeploymentComparisonQuery,
  useAdminProviderFailureSimulationsQuery,
  useAdminProvidersQuery,
  useAdminReviewsQuery,
  useAdminSystemQuery,
  useAdminTelemetryQuery,
  useRollbackAdminProviderPolicyMutation,
  useRollbackAdminFeatureFlagMutation,
  useAddAdminEscalationNoteMutation,
  useClaimAdminEscalationMutation,
  useRouteAdminEscalationMutation,
  useResolveAdminEscalationMutation,
  useReviewAdminBenefitMutation,
  useRollbackAdminBenefitMutation,
  useUpdateAdminBenefitMutation,
  useUpdateFreshnessAlertMutation,
  useUpdateAdminProviderPolicyMutation,
  useUpdateAdminFeatureFlagMutation,
  useUpdateAdminBenefitReportMutation,
  useUpdateAdminLanguageReviewMutation,
  useApproveAdminDirectoryMutation,
  useDeactivateAdminDirectoryMutation,
  useDownloadAdminAuditMutation,
} from "@/features/admin/queries";
import type { AdminView } from "@/features/admin/components/admin-shell";
import type {
  LanguageReviewUpdate,
  ProviderPolicy,
  ProviderPolicyUpdate,
} from "@/features/admin/api";
import { toUserMessage } from "@/lib/api";

type LanguageReviewStatus = LanguageReviewUpdate["native_speaker_status"];
type LanguageReviewStatuses = Pick<
  LanguageReviewUpdate,
  | "native_speaker_status"
  | "interface_status"
  | "prompt_status"
  | "content_status"
  | "understanding_status"
  | "voice_status"
  | "accessibility_status"
>;

function normalizeLanguageReviewStatus(value: string): LanguageReviewStatus {
  return value === "approved" || value === "rejected" ? value : "pending";
}

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
    case "directory":
      return <DirectoryPage token={token} role={meQuery.data?.role ?? "observer"} />;
    case "benefits":
      return <BenefitsPage token={token} role={meQuery.data?.role ?? "observer"} />;
    case "providers":
      return <ProvidersPage token={token} role={meQuery.data?.role ?? "observer"} />;
    case "messaging":
      return <MessagingPage token={token} />;
    case "quality":
      return <QualityPage token={token} role={meQuery.data?.role ?? "observer"} />;
    case "flags":
      return <FeatureFlagsPage token={token} role={meQuery.data?.role ?? "observer"} />;
    case "languages":
      return <LanguagesPage token={token} role={meQuery.data?.role ?? "observer"} />;
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
  const claim = useClaimAdminEscalationMutation(token);
  const note = useAddAdminEscalationNoteMutation(token);
  const route = useRouteAdminEscalationMutation(token);
  const resolve = useResolveAdminEscalationMutation(token);
  if (query.isPending) return <Loading label="Loading escalation queue…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  const canOperate = role === "operator" || role === "admin";
  const mutationError = [claim, note, route, resolve].find((item) => item.isError)?.error;
  return (
    <div className="space-y-6"><PageIntro title="Escalation queue" description="Operator handoffs created when the agent declines to guess. Claim ownership, verify the fallback route, leave a bounded note, and record the resolution." />
      {mutationError && <div role="alert" className="rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-orange">{toUserMessage(mutationError)}</div>}
      <div className="grid gap-4">{query.data.map((ticket) => <EscalationCard key={ticket.id} ticket={ticket} canOperate={canOperate} busy={claim.isPending || note.isPending || route.isPending || resolve.isPending} onClaim={() => claim.mutate(ticket.id)} onNote={(text) => note.mutate({ticketId: ticket.id, text})} onRoute={(department, routingLocation) => route.mutate({ticketId: ticket.id, department, routing_location: routingLocation})} onResolve={(resolutionCode, resolutionNote) => resolve.mutate({ticketId: ticket.id, resolution_code: resolutionCode, note: resolutionNote})} />)}</div>
      {!query.data.length && <EmptyState label="No open escalations." />}
    </div>
  );
}

function EscalationCard({
  ticket,
  canOperate,
  busy,
  onClaim,
  onNote,
  onRoute,
  onResolve,
}: {
  ticket: import("@/features/admin/api").AdminTicket;
  canOperate: boolean;
  busy: boolean;
  onClaim: () => void;
  onNote: (text: string) => void;
  onRoute: (department: string, routingLocation: string) => void;
  onResolve: (resolutionCode: string, resolutionNote: string) => void;
}) {
  const [note, setNote] = useState("");
  const [department, setDepartment] = useState(ticket.department);
  const [routingLocation, setRoutingLocation] = useState(ticket.routing_location);
  const [resolutionCode, setResolutionCode] = useState("answered");
  const [resolutionNote, setResolutionNote] = useState("");
  const fallbackRoute = ticket.routing_source === "state_domain_fallback";

  return <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardContent className="space-y-5 p-5">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex flex-wrap items-center gap-2"><Badge variant="warning">{ticket.reason}</Badge><Badge variant={ticket.status === "claimed" ? "success" : "outline"}>{ticket.status}</Badge>{ticket.sla_breached && <Badge variant="warning">SLA overdue</Badge>}<span className="font-mono text-xs text-paper/40">{ticket.id}</span></div><p className="mt-3 max-w-3xl text-sm leading-6 text-paper/70">{ticket.transcript_excerpt || "Sensitive context is redacted for this role."}</p><p className="mt-2 text-xs text-paper/40">Created {formatTime(ticket.created_at)} · session {ticket.session_id}{ticket.assigned_to ? ` · owner ${ticket.assigned_to}` : ""}</p></div>{canOperate && ticket.status === "open" && <Button size="sm" variant="outline" disabled={busy} onClick={onClaim}>{busy ? "Claiming…" : "Claim ticket"}</Button>}</div>
    <div className="grid gap-3 rounded-xl border border-paper/10 bg-ink/20 p-4 text-sm sm:grid-cols-3"><div><p className="text-xs uppercase tracking-[0.12em] text-paper/40">Department</p><p className="mt-1 font-semibold">{ticket.department}</p></div><div><p className="text-xs uppercase tracking-[0.12em] text-paper/40">Location hint</p><p className="mt-1 text-paper/70">{ticket.routing_location || "Not stated"}</p></div><div><p className="text-xs uppercase tracking-[0.12em] text-paper/40">SLA</p><p className={ticket.sla_breached ? "mt-1 font-semibold text-orange" : "mt-1 text-paper/70"}>{ticket.sla_due_at ? formatTime(ticket.sla_due_at) : "Legacy ticket — no deadline"}</p></div></div>
    {ticket.routing_source === "authoritative_directory" && <p className="text-xs leading-5 text-acid/80">Matched from the approved department directory{ticket.routing_verified_at ? ` · verified ${formatTime(ticket.routing_verified_at)}` : ""}{ticket.routing_source_url && <> · <a className="underline underline-offset-4 hover:text-acid" href={ticket.routing_source_url} target="_blank" rel="noreferrer">source</a></>}</p>}
    {fallbackRoute && <p className="text-xs leading-5 text-orange/80">Fallback route based on state and conversation domain. Confirm the real department or help centre before referring the caller.</p>}
    {!!ticket.operator_notes.length && <div className="space-y-2"><p className="text-xs uppercase tracking-[0.12em] text-paper/40">Operator notes</p>{ticket.operator_notes.map((item) => <div key={item.id} className="rounded-lg border border-paper/10 bg-paper/[0.03] px-3 py-2 text-sm"><p className="text-paper/75">{item.text}</p><p className="mt-1 text-xs text-paper/40">{item.actor_id} · {formatTime(item.created_at)}</p></div>)}</div>}
    {canOperate && <div className="grid gap-4 border-t border-paper/10 pt-4 lg:grid-cols-3"><div className="space-y-2"><label className="text-xs font-semibold uppercase tracking-[0.12em] text-paper/50" htmlFor={`route-${ticket.id}`}>Department route</label><input id={`route-${ticket.id}`} value={department} onChange={(event) => setDepartment(event.target.value)} className="h-10 w-full rounded-lg border border-paper/15 bg-background/40 px-3 text-sm text-paper outline-none focus:ring-2 focus:ring-ring" maxLength={160} /><input aria-label="District or pincode routing hint" value={routingLocation} onChange={(event) => setRoutingLocation(event.target.value)} placeholder="District or pincode hint" className="h-10 w-full rounded-lg border border-paper/15 bg-background/40 px-3 text-sm text-paper outline-none focus:ring-2 focus:ring-ring" maxLength={120} /><Button size="sm" variant="outline" disabled={busy || department.trim().length < 2} onClick={() => onRoute(department.trim(), routingLocation.trim())}>Save route</Button></div><div className="space-y-2"><label className="text-xs font-semibold uppercase tracking-[0.12em] text-paper/50" htmlFor={`note-${ticket.id}`}>Add note</label><Textarea id={`note-${ticket.id}`} value={note} onChange={(event) => setNote(event.target.value)} maxLength={2000} placeholder="Record only operational facts; do not paste unnecessary personal data." /><Button size="sm" variant="outline" disabled={busy || note.trim().length < 1} onClick={() => { onNote(note.trim()); setNote(""); }}>Add note</Button></div><div className="space-y-2"><label className="text-xs font-semibold uppercase tracking-[0.12em] text-paper/50" htmlFor={`resolution-${ticket.id}`}>Resolution</label><select id={`resolution-${ticket.id}`} value={resolutionCode} onChange={(event) => setResolutionCode(event.target.value)} className="h-10 w-full rounded-lg border border-paper/15 bg-background/40 px-3 text-sm text-paper outline-none focus:ring-2 focus:ring-ring"><option value="answered">Answered</option><option value="referred">Referred</option><option value="no_action">No action</option><option value="duplicate">Duplicate</option><option value="unreachable">Could not reach</option></select><Textarea value={resolutionNote} onChange={(event) => setResolutionNote(event.target.value)} maxLength={2000} placeholder="Optional resolution summary" /><Button size="sm" disabled={busy || ticket.status === "resolved"} onClick={() => onResolve(resolutionCode, resolutionNote.trim())}>Resolve ticket</Button></div></div>}
  </CardContent></Card>;
}

function DirectoryPage({ token, role }: { token: string; role: string }) {
  const query = useAdminDirectoryQuery(token);
  const approve = useApproveAdminDirectoryMutation(token);
  const deactivate = useDeactivateAdminDirectoryMutation(token);
  if (query.isPending) return <Loading label="Loading department directory…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  const canReview = role === "reviewer" || role === "admin";
  const mutationError = approve.error ?? deactivate.error;
  return (
    <div className="space-y-6">
      <PageIntro
        title="Department directory"
        description="Official India.gov department and district records are imported as source-attested candidates. Imports remain inactive until a reviewer approves a recent source."
      />
      {mutationError && (
        <div role="alert" className="rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-orange">
          {toUserMessage(mutationError)}
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Directory rows"
          value={String(query.data.total)}
          detail={`${query.data.coverage_by_state.length} state/UT sources in coverage`}
        />
        <MetricCard
          label="Approved and active"
          value={String(query.data.active_approved_count)}
          detail="eligible for runtime routing"
        />
        <MetricCard
          label="Pending review"
          value={String(query.data.status_counts.pending ?? 0)}
          detail="never used by callers"
          tone="warning"
        />
        <MetricCard
          label="Stale records"
          value={String(query.data.stale_count)}
          detail={`freshness window ${query.data.stale_after_days} days`}
          tone={query.data.stale_count ? "warning" : "default"}
        />
      </div>
      <Card className="border-paper/10 bg-paper/[0.04] text-paper">
        <CardHeader>
          <CardTitle className="text-paper">Coverage and provenance</CardTitle>
          <p className="text-sm leading-6 text-paper/50">
            India.gov provides official state, department, directorate, and district portal records. It does not by itself prove that a particular scheme is handled by a particular office. Pincode routing remains disabled until a source explicitly attests a pincode or an approved district match is appropriate.
          </p>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-paper/45">Imported by source</h3>
              <div className="mt-3 space-y-2">
                {Object.entries(query.data.source_counts).map(([source, count]) => (
                  <div key={source} className="flex items-center justify-between gap-4 text-sm">
                    <span className="truncate text-paper/70">{source}</span>
                    <span className="font-mono text-acid">{count}</span>
                  </div>
                ))}
                {!Object.keys(query.data.source_counts).length && <EmptyState label="No source runs recorded." />}
              </div>
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-paper/45">Sync workflow</h3>
              <p className="mt-3 text-sm leading-6 text-paper/60">
                Fetch a fresh snapshot with <code className="rounded bg-ink px-1.5 py-0.5 text-xs text-acid">make directory-india-gov</code>, then import it with the directory importer. Unchanged approved source records retain approval; changed records return to this queue.
              </p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <caption className="sr-only">Department directory coverage by state and union territory</caption>
              <thead className="border-b border-paper/10 text-xs uppercase tracking-[0.12em] text-paper/40">
                <tr><th className="px-3 py-3">State/UT</th><th className="px-3 py-3">Rows</th><th className="px-3 py-3">Approved</th><th className="px-3 py-3">Pending</th><th className="px-3 py-3">Districts</th><th className="px-3 py-3">Stale</th></tr>
              </thead>
              <tbody>
                {query.data.coverage_by_state.map((item) => (
                  <tr key={item.state_code} className="border-b border-paper/5 last:border-0">
                    <td className="px-3 py-3"><span className="font-mono text-xs text-acid">{item.state_code}</span> <span className="ml-2">{item.state_name}</span></td>
                    <td className="px-3 py-3">{item.total}</td>
                    <td className="px-3 py-3">{item.active_approved}/{item.approved}</td>
                    <td className="px-3 py-3">{item.pending}</td>
                    <td className="px-3 py-3">{item.districts}</td>
                    <td className="px-3 py-3">{item.stale ? <span className="text-orange">{item.stale}</span> : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!query.data.coverage_by_state.length && <EmptyState label="No directory coverage yet." />}
          </div>
        </CardContent>
      </Card>
      <Card className="border-paper/10 bg-paper/[0.04] text-paper">
        <CardHeader>
          <CardTitle className="text-paper">Review and provenance</CardTitle>
          <p className="text-sm leading-6 text-paper/50">The runtime prefers exact pincode, then pincode prefix, then district. Stale or unapproved records fall back to a clearly labelled state/domain helpdesk.</p>
        </CardHeader>
        <CardContent className="space-y-3">
          {query.data.entries.map((entry) => (
            <article key={entry.id} className="rounded-xl border border-paper/10 bg-ink/20 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={entry.approval_status === "approved" && entry.is_active ? "success" : "warning"}>{entry.approval_status}{entry.is_active ? " · active" : " · inactive"}</Badge>
                    {entry.stale && <Badge variant="warning">stale</Badge>}
                    <span className="font-mono text-xs text-paper/40">{entry.id}</span>
                  </div>
                  <h3 className="mt-2 font-semibold">{entry.department_name}</h3>
                  <p className="mt-1 text-sm text-paper/65">{entry.state_code} · {entry.district_name || "statewide"} · {entry.pincode || (entry.pincode_prefix ? `${entry.pincode_prefix}xxx` : "district")}</p>
                </div>
                {canReview && <div className="flex flex-wrap gap-2">{entry.approval_status !== "approved" && <Button size="sm" disabled={approve.isPending || deactivate.isPending || entry.stale} onClick={() => approve.mutate({entryId: entry.id, reason: "Verified official department source in the directory review queue"})}>Approve</Button>}{entry.is_active && <Button size="sm" variant="outline" disabled={approve.isPending || deactivate.isPending} onClick={() => deactivate.mutate({entryId: entry.id, reason: "Deactivated from the department directory review queue"})}>Deactivate</Button>}</div>}
              </div>
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-paper/45">
                <span>{entry.source_kind} · {entry.source_scope}</span>
                <span>{entry.service_domain}</span>
                <span>{entry.help_centre_name || "Help centre name not supplied"}</span>
                <span>Verified {entry.source_last_verified ? formatTime(entry.source_last_verified) : "never"}</span>
                {entry.source_url && <a className="text-acid underline-offset-4 hover:underline" href={entry.source_url} target="_blank" rel="noreferrer">Official source</a>}
                {entry.website_url && <a className="text-acid underline-offset-4 hover:underline" href={entry.website_url} target="_blank" rel="noreferrer">Public portal</a>}
              </div>
            </article>
          ))}
          {!query.data.entries.length && <EmptyState label="No directory rows imported. Run the official directory import script, then review the pending rows here." />}
        </CardContent>
      </Card>
    </div>
  );
}

function BenefitsPage({ token, role }: { token: string; role: string }) {
  const query = useAdminReviewsQuery(token);
  const imports = useAdminImportsQuery(token);
  const reports = useAdminBenefitReportsQuery(token);
  const mutation = useReviewAdminBenefitMutation(token);
  const editMutation = useUpdateAdminBenefitMutation(token);
  const rollbackMutation = useRollbackAdminBenefitMutation(token);
  const reportMutation = useUpdateAdminBenefitReportMutation(token);
  if (query.isPending) return <Loading label="Loading benefit review queue…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  const canReview = role === "reviewer" || role === "admin";
  return (
    <div className="space-y-6"><PageIntro title="Benefits, provenance, and review" description="Machine-structured rows stay inactive until a reviewer records a decision. Every change creates an immutable audit event." />
      <div className="grid gap-4 sm:grid-cols-3">{Object.entries(query.data.status_counts).map(([status, count]) => <MetricCard key={status} label={status.replaceAll("_", " ")} value={String(count)} detail="rows in corpus" tone={status === "needs_review" ? "warning" : "default"} />)}</div>
      <div className="grid gap-4">{query.data.items.map((item) => <ReviewCard key={item.id} token={token} item={item} canReview={canReview} canRollback={role === "admin"} onSubmit={(input) => mutation.mutate({benefitId: item.id, ...input})} onEdit={(payload) => editMutation.mutate({benefitId: item.id, payload})} onRollback={(version, reason) => rollbackMutation.mutate({benefitId: item.id, version, reason})} pending={mutation.isPending || editMutation.isPending || rollbackMutation.isPending} />)}</div>
      {!query.data.items.length && <EmptyState label="No benefits are currently waiting for human review." />}
      <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardHeader><CardTitle className="text-paper">Import history</CardTitle></CardHeader><CardContent className="space-y-3">{imports.data?.map((run) => <div key={run.id} className="flex flex-wrap justify-between gap-3 border-b border-paper/10 pb-3 text-sm last:border-0"><div><p className="font-semibold">{run.source_name}</p><p className="text-xs text-paper/45">{run.model_name || "No model recorded"} · prompt {run.prompt_version || "—"}</p></div><span className="text-xs text-paper/55">{run.accepted_count}/{run.input_count} accepted · {formatTime(run.started_at)}</span></div>)}{imports.data && !imports.data.length && <EmptyState label="No import manifests recorded." />}</CardContent></Card>
      <IssueReportsPanel reports={reports.data ?? []} loading={reports.isPending} canResolve={role === "operator" || role === "admin"} pending={reportMutation.isPending} onUpdate={(reportId, status) => reportMutation.mutate({ reportId, status, reason: "Reviewed from the benefits operations queue" })} />
    </div>
  );
}

function IssueReportsPanel({
  reports,
  loading,
  canResolve,
  pending,
  onUpdate,
}: {
  reports: import("@/features/admin/api").BenefitIssueReport[];
  loading: boolean;
  canResolve: boolean;
  pending: boolean;
  onUpdate: (reportId: string, status: "acknowledged" | "resolved" | "dismissed") => void;
}) {
  return <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardHeader><CardTitle className="text-paper">Citizen issue reports</CardTitle><p className="text-sm leading-6 text-paper/50">Reports are rate-limited, linked to the public source, and kept separate from private caller profile data.</p></CardHeader><CardContent className="space-y-3">{loading && <p className="text-sm text-paper/45">Loading reports…</p>}{!loading && reports.map((report) => <article key={report.id} className="rounded-xl border border-orange/20 bg-orange/[0.05] p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><Badge variant="warning">{report.category}</Badge><span className="font-mono text-xs text-paper/40">{report.id}</span></div><h3 className="mt-2 font-semibold">{report.benefit_name}</h3><p className="mt-2 text-sm leading-6 text-paper/70">{report.description || "Description redacted for this role."}</p><p className="mt-2 text-xs text-paper/40">{report.locale} · {formatTime(report.created_at)} · {report.source_title || "Source title missing"}</p></div>{report.source_document_url && <a className="inline-flex items-center gap-1 text-xs font-semibold text-acid underline-offset-4 hover:underline" href={report.source_document_url} target="_blank" rel="noreferrer">Source <ExternalLink className="size-3" aria-hidden="true" /></a>}</div>{canResolve && <div className="mt-4 flex flex-wrap gap-2 border-t border-paper/10 pt-3"><Button size="sm" variant="outline" disabled={pending} onClick={() => onUpdate(report.id, "acknowledged")}>Acknowledge</Button><Button size="sm" disabled={pending} onClick={() => onUpdate(report.id, "resolved")}>Resolve</Button><Button size="sm" variant="ghost" disabled={pending} onClick={() => onUpdate(report.id, "dismissed")}>Dismiss</Button></div>}</article>)}{!loading && !reports.length && <EmptyState label="No open citizen issue reports." />}</CardContent></Card>;
}

function ProvidersPage({ token, role }: { token: string; role: string }) {
  const query = useAdminProvidersQuery(token);
  const simulations = useAdminProviderFailureSimulationsQuery(token);
  const update = useUpdateAdminProviderPolicyMutation(token);
  const rollback = useRollbackAdminProviderPolicyMutation(token);
  if (query.isPending || simulations.isPending) return <Loading label="Loading provider posture…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  if (simulations.isError || !simulations.data) return <ErrorPanel error={simulations.error} />;
  const canManage = role === "admin";
  return (
    <div className="space-y-6">
      <PageIntro
        title="Providers, spend, and fallback"
        description="Configuration and request-level posture are visible here. Cost values are estimates where the provider does not expose a reconciliation API."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        {query.data.providers.map((provider) => (
          <Card key={provider.name} className="border-paper/10 bg-paper/[0.04] text-paper">
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle className="text-paper">{provider.name}</CardTitle>
              {provider.configured ? <Badge variant="success">{provider.health}</Badge> : <Badge variant="warning">not configured</Badge>}
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <Stat label="Requests" value={provider.requests} />
                <Stat label="Failures" value={provider.failures} tone={provider.failures ? "warning" : "default"} />
                {provider.budget_usd != null && <Stat label="Budget remaining" value={`$${provider.remaining_usd?.toFixed(2) ?? "—"}`} tone="good" />}
                {provider.cache_hits > 0 && <Stat label="Cache hits" value={provider.cache_hits} tone="good" />}
              </div>
              {Object.keys(provider.cost_by_operation).length > 0 && (
                <div className="rounded-lg border border-paper/10 bg-ink/20 px-3 py-2 text-xs">
                  <p className="font-semibold text-paper/65">Reserved by operation</p>
                  <p className="mt-1 leading-5 text-paper/45">{formatUsdBreakdown(provider.cost_by_operation)}</p>
                  <p className="mt-1 leading-5 text-paper/40">Observed: {formatUsdBreakdown(provider.observed_cost_by_operation)}</p>
                </div>
              )}
              {Object.keys(provider.voice_requests_by_language).length > 0 && (
                <div className="rounded-lg border border-paper/10 bg-ink/20 px-3 py-2 text-xs">
                  <p className="font-semibold text-paper/65">Voice activity by language</p>
                  <p className="mt-1 leading-5 text-paper/45">{formatCountBreakdown(provider.voice_requests_by_language)} requests</p>
                  {Object.keys(provider.tts_billed_characters_by_language).length > 0 && <p className="mt-1 leading-5 text-paper/40">TTS characters: {formatCountBreakdown(provider.tts_billed_characters_by_language)}</p>}
                </div>
              )}
              {provider.cost_scope && <p className="text-[0.68rem] leading-5 text-paper/35">{provider.cost_scope}</p>}
              <p className="text-xs leading-5 text-paper/45">{provider.note}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <ProviderFailureDrills data={simulations.data} />
      <Card className="border-paper/10 bg-paper/[0.04] text-paper">
        <CardHeader>
          <CardTitle className="text-paper">Audited provider policies</CardTitle>
          <p className="text-sm leading-6 text-paper/50">{query.data.controls_note}</p>
        </CardHeader>
        <CardContent className="grid gap-4">
          {query.data.policies.map((policy) => (
            <ProviderPolicyCard
              key={`${policy.id}-${policy.revision}`}
              policy={policy}
              canManage={canManage}
              onUpdate={(input) => update.mutate(input)}
              onRollback={(input) => rollback.mutate(input)}
              pending={update.isPending || rollback.isPending}
            />
          ))}
        </CardContent>
      </Card>
      {!canManage && <p className="rounded-xl border border-paper/10 bg-paper/[0.03] px-4 py-3 text-sm leading-6 text-paper/50">Your role can inspect effective policy posture, but only an admin can change or roll back provider routing.</p>}
    </div>
  );
}

function ProviderFailureDrills({ data }: { data: import("@/features/admin/api").ProviderFailureSimulationList }) {
  return (
    <Card className="border-paper/10 bg-paper/[0.04] text-paper">
      <CardHeader>
        <CardTitle className="text-paper">Provider failure drills</CardTitle>
        <p className="text-sm leading-6 text-paper/50">Dry-run containment paths for {data.language_code}/{data.state_code}. This dashboard never calls a provider or sends a notification.</p>
      </CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full min-w-[1040px] text-left text-sm">
          <caption className="sr-only">Provider failure simulation paths</caption>
          <thead className="border-b border-paper/10 text-xs uppercase tracking-[0.12em] text-paper/40">
            <tr><th className="px-5 py-4">Scenario</th><th className="px-5 py-4">Current gate</th><th className="px-5 py-4">Fallback</th><th className="px-5 py-4">Drill path</th></tr>
          </thead>
          <tbody>
            {data.simulations.map((simulation) => (
              <tr key={simulation.scenario} className="border-b border-paper/5 align-top last:border-0">
                <td className="px-5 py-4"><p className="font-semibold">{simulation.scenario.replaceAll("_", " ")}</p><p className="mt-1 font-mono text-xs text-paper/40">{simulation.provider}</p></td>
                <td className="px-5 py-4"><Badge variant={simulation.current_posture === "ready for controlled drill" ? "success" : "warning"}>{simulation.current_posture}</Badge><p className="mt-2 text-xs text-paper/45">flag {simulation.flag_enabled ? "on" : "off"} · policy {simulation.policy_enabled ? "on" : "off"} · circuit {simulation.circuit_state} · {simulation.configured ? "configured" : "not configured"}</p></td>
                <td className="max-w-xs px-5 py-4 text-xs leading-5 text-paper/60">{simulation.user_facing_fallback}</td>
                <td className="px-5 py-4"><details><summary className="cursor-pointer text-xs font-semibold text-acid">View expected path</summary><ol className="mt-2 list-decimal space-y-1 pl-5 text-xs leading-5 text-paper/55">{simulation.expected_path.map((step) => <li key={step}>{step}</li>)}</ol><p className="mt-3 text-xs leading-5 text-paper/45"><span className="font-semibold text-paper/65">Operator:</span> {simulation.operator_action}</p></details></td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="border-t border-paper/10 px-5 py-4 text-xs leading-5 text-paper/40">{data.note}</p>
      </CardContent>
    </Card>
  );
}

function MessagingPage({ token }: { token: string }) {
  const query = useAdminNotificationsQuery(token);
  if (query.isPending) return <Loading label="Loading messaging cost and delivery posture…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  const data = query.data;
  return (
    <div className="space-y-6">
      <PageIntro title="Messaging cost and delivery" description={`Last ${data.window_hours} hours · accepted is not delivered · ${data.controls_note}`} />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Daily spend" value={`${formatMinor(data.budget_daily_spent_minor_units)} ${data.cost_currency}`} detail={data.budget_daily_limit_minor_units == null ? "No daily cap configured" : `Limit ${formatMinor(data.budget_daily_limit_minor_units)} ${data.cost_currency}`} tone={data.budget_daily_limit_minor_units != null && data.budget_daily_spent_minor_units > data.budget_daily_limit_minor_units ? "warning" : "default"} />
        <MetricCard label="Monthly spend" value={`${formatMinor(data.budget_monthly_spent_minor_units)} ${data.cost_currency}`} detail={data.budget_monthly_limit_minor_units == null ? "No monthly cap configured" : `Limit ${formatMinor(data.budget_monthly_limit_minor_units)} ${data.cost_currency}`} />
        <MetricCard label="SMS delivery" value={formatPercent(data.channels.find((channel) => channel.channel === "sms")?.delivery_rate ?? 0)} detail="Reported delivered or seen" />
        <MetricCard label="Stale callbacks" value={formatNumber(data.channels.reduce((total, channel) => total + channel.stale_awaiting_report, 0))} detail="Accepted messages without a timely report" tone={data.channels.some((channel) => channel.stale_awaiting_report > 0) ? "warning" : "default"} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {data.channels.map((channel) => (
          <Card key={channel.channel} className="border-paper/10 bg-paper/[0.04] text-paper">
            <CardHeader className="flex-row items-center justify-between space-y-0"><CardTitle className="capitalize text-paper">{channel.channel}</CardTitle><Badge variant={channel.configured && channel.policy_enabled && channel.template_ready ? "success" : "warning"}>{channel.configured ? (channel.policy_enabled ? "ready" : "policy off") : "not configured"}</Badge></CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <Stat label="Delivered / seen" value={channel.delivered} tone="good" />
              <Stat label="Failed" value={channel.failed} tone={channel.failed ? "warning" : "default"} />
              <Stat label="Cost" value={`${formatMinor(channel.cost_minor_units)} ${channel.cost_currency}`} />
              <Stat label="Verified contacts" value={channel.verified_contacts} />
              <p className="sm:col-span-2 text-xs leading-5 text-paper/45">{channel.note} {channel.top_error_class ? `Top error: ${channel.top_error_class}.` : ""}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <CostBreakdown title="Cost by language" values={data.cost_by_language} currency={data.cost_currency} />
        <CostBreakdown title="Cost by provider" values={data.cost_by_provider} currency={data.cost_currency} />
      </div>
    </div>
  );
}

function CostBreakdown({ title, values, currency }: { title: string; values: Record<string, number>; currency: string }) {
  return <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardHeader><CardTitle className="text-paper">{title}</CardTitle></CardHeader><CardContent className="space-y-2">{Object.entries(values).map(([key, value]) => <div key={key} className="flex items-center justify-between gap-4 border-b border-paper/5 py-2 text-sm last:border-0"><span className="text-paper/60">{key}</span><span className="font-mono text-acid">{formatMinor(value)} {currency}</span></div>)}{!Object.keys(values).length && <EmptyState label="No billable delivery data in this window." />}</CardContent></Card>;
}

function QualityPage({ token, role }: { token: string; role: string }) {
  const freshness = useAdminFreshnessQuery(token);
  const evaluations = useAdminEvaluationsQuery(token);
  const updateAlert = useUpdateFreshnessAlertMutation(token);
  if (freshness.isPending || evaluations.isPending) return <Loading label="Loading freshness and evaluation evidence…" />;
  if (freshness.isError) return <ErrorPanel error={freshness.error} />;
  if (evaluations.isError) return <ErrorPanel error={evaluations.error} />;
  if (!freshness.data || !evaluations.data) return <ErrorPanel error={new Error("Quality data is unavailable.")} />;
  return (
    <div className="space-y-6">
      <PageIntro title="Data freshness and evaluations" description={`Freshness threshold ${freshness.data.stale_after_days} days · generated ${formatTime(freshness.data.generated_at)}. Machine-structured rows remain visible but are not publication evidence.`} />
      <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardHeader><CardTitle className="text-paper">Source freshness alerts</CardTitle><p className="text-sm leading-6 text-paper/50">Alerts are deduplicated by benefit and source condition. Acknowledging an alert records ownership; it is automatically resolved when the next scan sees fresh evidence.</p></CardHeader><CardContent className="space-y-3">{freshness.data.alerts.map((alert) => <article key={alert.id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-orange/20 bg-orange/[0.05] p-4"><div><div className="flex flex-wrap items-center gap-2"><Badge variant="warning">{alert.severity}</Badge><Badge variant="outline" className="border-orange/30 text-orange">{alert.status}</Badge><span className="font-mono text-xs text-paper/40">{alert.alert_type}</span></div><p className="mt-2 text-sm text-paper/75">{alert.message}</p><p className="mt-1 text-xs text-paper/40">{alert.dataset} · last seen {formatTime(alert.last_seen_at)}</p></div>{(role === "reviewer" || role === "admin") && <div className="flex gap-2"><Button type="button" size="sm" variant="outline" disabled={updateAlert.isPending || alert.status === "acknowledged"} onClick={() => updateAlert.mutate({alertId: alert.id, status: "acknowledged", reason: "Acknowledged from the freshness console"})}>Acknowledge</Button><Button type="button" size="sm" disabled={updateAlert.isPending} onClick={() => updateAlert.mutate({alertId: alert.id, status: "resolved", reason: "Resolved from the freshness console"})}>Resolve</Button></div>}</article>)}{!freshness.data.alerts.length && <EmptyState label="No open or acknowledged source freshness alerts." />}</CardContent></Card>
      <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardContent className="overflow-x-auto p-0"><table className="w-full min-w-[920px] text-left text-sm"><caption className="sr-only">Data freshness by source dataset</caption><thead className="border-b border-paper/10 text-xs uppercase tracking-[0.12em] text-paper/40"><tr><th className="px-5 py-4">Dataset</th><th className="px-5 py-4">Status</th><th className="px-5 py-4">Rows</th><th className="px-5 py-4">Active</th><th className="px-5 py-4">Human verified</th><th className="px-5 py-4">Stale / expired</th><th className="px-5 py-4">Latest check</th></tr></thead><tbody>{freshness.data.sources.map((source) => <tr key={source.dataset} className="border-b border-paper/5 last:border-0"><td className="px-5 py-4 font-semibold">{source.dataset}</td><td className="px-5 py-4"><Badge variant={source.status === "healthy" ? "success" : "warning"}>{source.status}</Badge></td><td className="px-5 py-4">{source.total_rows}</td><td className="px-5 py-4">{source.active_rows}</td><td className="px-5 py-4">{source.human_verified_rows}</td><td className="px-5 py-4">{source.stale_rows} / {source.expired_rows}</td><td className="px-5 py-4 text-xs text-paper/50">{source.latest_verified_date ?? "not checked"}</td></tr>)}</tbody></table>{!freshness.data.sources.length && <EmptyState label="No benefit or job source rows are loaded." />}</CardContent></Card>
      <div className="grid gap-4">{evaluations.data.map((run) => { const metrics = evaluationMetrics(run.report_json); return <Card key={run.id} className="border-paper/10 bg-paper/[0.04] text-paper"><CardContent className="flex flex-wrap items-center justify-between gap-4 p-5"><div><div className="flex items-center gap-2"><Badge variant={run.passed ? "success" : "warning"}>{run.passed ? "passed" : "failed"}</Badge><span className="font-semibold">{run.suite_name}</span></div><p className="mt-2 text-xs text-paper/45">suite {run.suite_version} · {formatTime(run.completed_at ?? run.started_at)} · languages {Object.entries(run.language_counts).map(([language, count]) => `${language} ${count}`).join(", ") || "—"}</p>{metrics && <p className="mt-1 text-xs text-paper/40">Average {Math.round(metrics.average_duration_ms)} ms · P95 {Math.round(metrics.p95_duration_ms)} ms · {formatPercent(metrics.pass_rate)} overall pass rate</p>}</div><div className="text-right"><p className="font-mono text-2xl text-acid">{run.passed_count}/{run.case_count}</p><p className="text-xs text-paper/45">cases passed</p></div></CardContent></Card>; })}{!evaluations.data.length && <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardContent><EmptyState label="No evaluation runs recorded yet. Run make evaluate to create evidence." /></CardContent></Card>}</div>
    </div>
  );
}

function FeatureFlagsPage({ token, role }: { token: string; role: string }) {
  const query = useAdminFeatureFlagsQuery(token);
  const update = useUpdateAdminFeatureFlagMutation(token);
  const rollback = useRollbackAdminFeatureFlagMutation(token);
  if (query.isPending) return <Loading label="Loading feature flags…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  const canManage = role === "admin";
  return <div className="space-y-6"><PageIntro title="Feature flags and staged rollout" description="Flags are persisted, scoped by language/state, percentage-bucketed deterministically, and every change has an audited rollback path." /><div className="grid gap-4">{query.data.flags.map((flag) => <FeatureFlagCard key={flag.key} flag={flag} canManage={canManage} pending={update.isPending || rollback.isPending} onUpdate={(payload) => update.mutate({key: flag.key, payload})} onRollback={(reason) => rollback.mutate({key: flag.key, reason})} />)}</div>{!canManage && <p className="rounded-xl border border-paper/10 bg-paper/[0.03] px-4 py-3 text-sm leading-6 text-paper/50">Your role can inspect rollout posture. Only an admin can change or roll back flags.</p>}</div>;
}

function FeatureFlagCard({ flag, canManage, pending, onUpdate, onRollback }: { flag: import("@/features/admin/api").FeatureFlag; canManage: boolean; pending: boolean; onUpdate: (payload: import("@/features/admin/api").FeatureFlagUpdate) => void; onRollback: (reason: string) => void }) {
  const [enabled, setEnabled] = useState(flag.enabled);
  const [percentage, setPercentage] = useState(String(flag.rollout_percentage));
  const [languages, setLanguages] = useState(flag.target_languages.join(", "));
  const [states, setStates] = useState(flag.target_states.join(", "));
  const [reason, setReason] = useState("Reviewed rollout posture");
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); onUpdate({enabled, rollout_percentage: Math.max(0, Math.min(100, Number(percentage) || 0)), target_languages: languages.split(",").map((value) => value.trim().toLowerCase()).filter(Boolean), target_states: states.split(",").map((value) => value.trim().toUpperCase()).filter(Boolean), reason: reason.trim()}); };
  return <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardContent className="space-y-4 p-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex items-center gap-2"><Badge variant={flag.enabled ? "success" : "warning"}>{flag.enabled ? `${flag.rollout_percentage}% live` : "off"}</Badge><h3 className="font-semibold">{flag.key}</h3><span className="font-mono text-xs text-paper/40">revision {flag.revision}</span></div><p className="mt-2 max-w-2xl text-sm leading-6 text-paper/55">{flag.description}</p></div>{canManage && <Button type="button" size="sm" variant="outline" disabled={pending || flag.revision < 1} onClick={() => onRollback(reason.trim() || "Rollback reviewed feature flag") }><RotateCcw className="size-3.5" aria-hidden="true" />Rollback</Button>}</div>{canManage ? <form className="grid gap-3 border-t border-paper/10 pt-4 md:grid-cols-2" onSubmit={submit}><label className="flex items-center gap-2 text-sm font-semibold"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> Enabled</label><label className="grid gap-1 text-xs font-semibold text-paper/60">Rollout percentage<input type="number" min="0" max="100" value={percentage} onChange={(event) => setPercentage(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" /></label><label className="grid gap-1 text-xs font-semibold text-paper/60">Languages (comma separated)<input value={languages} onChange={(event) => setLanguages(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" placeholder="kn, hi" /></label><label className="grid gap-1 text-xs font-semibold text-paper/60">States (comma separated)<input value={states} onChange={(event) => setStates(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" placeholder="KA, DL" /></label><label className="grid gap-1 text-xs font-semibold text-paper/60 md:col-span-2">Reason<input value={reason} onChange={(event) => setReason(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" minLength={3} /></label><div className="flex items-center justify-between gap-3 md:col-span-2"><p className="text-xs text-paper/40">Target lists are optional. Empty lists mean all supported locales/states.</p><Button type="submit" size="sm" disabled={pending || reason.trim().length < 3}>{pending ? "Saving…" : "Save flag"}</Button></div></form> : <p className="border-t border-paper/10 pt-4 text-xs text-paper/45">Targets: {flag.target_languages.join(", ") || "all languages"} · {flag.target_states.join(", ") || "all states"}</p>}</CardContent></Card>;
}

function LanguagesPage({ token, role }: { token: string; role: string }) {
  const query = useAdminLanguagesQuery(token);
  const update = useUpdateAdminLanguageReviewMutation(token);
  if (query.isPending) return <Loading label="Loading language readiness…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  const canReview = role === "reviewer" || role === "admin";
  return <div className="space-y-6"><PageIntro title="Language readiness" description="A locale is launch-ready only when interface, prompts, data, understanding, voice, and accessibility have evidence—not merely a catalog row." />
    {update.isError && <ErrorPanel error={update.error} />}
    <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardContent className="overflow-x-auto p-0"><table className="w-full min-w-[1180px] text-left text-sm"><caption className="sr-only">Language readiness matrix</caption><thead className="border-b border-paper/10 text-xs uppercase tracking-[0.12em] text-paper/40"><tr><th className="px-5 py-4">Language</th><th className="px-5 py-4">Rollout</th><th className="px-5 py-4">Prompt bundle</th><th className="px-5 py-4">Native review</th><th className="px-5 py-4">Content / accessibility</th><th className="px-5 py-4">Voice</th><th className="px-5 py-4">Data</th></tr></thead><tbody>{query.data.map((language) => <tr key={language.code} className="border-b border-paper/5 last:border-0"><td className="px-5 py-4"><span className="font-semibold">{language.native_name}</span><span className="ml-2 text-xs text-paper/40">{language.code}</span></td><td className="px-5 py-4">{language.rollout_status}</td><td className="px-5 py-4"><span className="block">{language.prompt_ready ? language.prompt_status : "missing"}</span><span className="text-xs text-paper/40">{language.prompt_bundle_status}</span></td><td className="px-5 py-4">{language.native_speaker_status}</td><td className="px-5 py-4">{language.content_status} · {language.accessibility_status}</td><td className="px-5 py-4">{language.voice_status} · {language.voice_review_status}</td><td className="px-5 py-4">{language.data_status} · {language.active_benefits}</td></tr>)}</tbody></table></CardContent></Card>
    <div className="grid gap-4">{query.data.map((language) => <LanguageReviewCard key={language.code} language={language} canReview={canReview} canActivate={role === "admin"} pending={update.isPending} onSave={(payload) => update.mutate({code: language.code, payload})} />)}</div>
  </div>;
}

function LanguageReviewCard({ language, canReview, canActivate, pending, onSave }: { language: import("@/features/admin/api").LanguageReadiness; canReview: boolean; canActivate: boolean; pending: boolean; onSave: (payload: import("@/features/admin/api").LanguageReviewUpdate) => void }) {
  const [statuses, setStatuses] = useState<LanguageReviewStatuses>({native_speaker_status: normalizeLanguageReviewStatus(language.native_speaker_status), interface_status: normalizeLanguageReviewStatus(language.interface_review_status), prompt_status: normalizeLanguageReviewStatus(language.prompt_status), content_status: normalizeLanguageReviewStatus(language.content_status), understanding_status: normalizeLanguageReviewStatus(language.understanding_status), voice_status: normalizeLanguageReviewStatus(language.voice_review_status), accessibility_status: normalizeLanguageReviewStatus(language.accessibility_status)});
  const [evidenceUrl, setEvidenceUrl] = useState(language.evidence_url);
  const [notes, setNotes] = useState(language.review_notes);
  const [attestation, setAttestation] = useState(false);
  const allApproved = Object.values(statuses).every((status) => status === "approved");
  return <Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardHeader><div className="flex flex-wrap items-center justify-between gap-3"><div><CardTitle className="text-paper">{language.native_name} · {language.name}</CardTitle><p className="mt-2 text-sm leading-6 text-paper/50">Review evidence before enabling this locale. A prompt bundle must be installed before prompt readiness can be approved.</p></div><Badge variant={language.rollout_status === "active" ? "success" : "warning"}>{language.rollout_status}</Badge></div></CardHeader><CardContent>{canReview ? <form className="grid gap-4 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); onSave({...statuses, evidence_url: evidenceUrl.trim(), review_notes: notes.trim(), attestation, activate: canActivate && allApproved}); }}><div className="grid gap-3 sm:grid-cols-2">{Object.entries(statuses).map(([key, value]) => <label key={key} className="grid gap-1 text-xs font-semibold capitalize text-paper/60">{key.replaceAll("_", " ")}<select value={value} onChange={(event) => setStatuses((current) => ({...current, [key]: normalizeLanguageReviewStatus(event.target.value)}))} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm font-normal text-paper"><option value="pending">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select></label>)}</div><div className="space-y-3"><label className="grid gap-1 text-xs font-semibold text-paper/60">Evidence URL<input value={evidenceUrl} onChange={(event) => setEvidenceUrl(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" placeholder="QA report, recording, or review artifact" /></label><label className="grid gap-1 text-xs font-semibold text-paper/60">Review notes<Textarea value={notes} onChange={(event) => setNotes(event.target.value)} minLength={3} maxLength={2000} placeholder="Who reviewed wording, pronunciation, data, and accessibility?" /></label><label className="flex items-start gap-2 text-xs leading-5 text-paper/55"><input type="checkbox" checked={attestation} onChange={(event) => setAttestation(event.target.checked)} className="mt-1" /> I attest that the linked evidence was checked by the appropriate native-language reviewer(s).</label><Button type="submit" size="sm" disabled={pending || !attestation || notes.trim().length < 3}>{pending ? "Saving…" : canActivate && allApproved ? "Save and activate" : "Save review gate"}</Button></div></form> : <p className="text-sm text-paper/50">Observer access can inspect this gate; a reviewer or admin must provide the native-speaker evidence.</p>}</CardContent></Card>;
}

function AuditPage({ token }: { token: string }) {
  const query = useAdminAuditQuery(token);
  const download = useDownloadAdminAuditMutation(token);
  const exportCsv = async () => {
    const blob = await download.mutateAsync("csv");
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "sahaayak-audit.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };
  if (query.isPending) return <Loading label="Loading audit history…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  return <div className="space-y-6"><div className="flex flex-wrap items-end justify-between gap-4"><PageIntro title="Audit log" description="Append-only workforce actions with safe before/after state. Exports contain only the redacted audit projection, never transcripts, contacts, or secrets." /><Button type="button" variant="outline" disabled={download.isPending} onClick={() => { void exportCsv(); }}><Download className="size-3.5" aria-hidden="true" />{download.isPending ? "Preparing…" : "Export CSV"}</Button></div>{download.isError && <ErrorPanel error={download.error} />}<Card className="border-paper/10 bg-paper/[0.04] text-paper"><CardContent className="space-y-3 p-5">{query.data.map((event) => <article key={event.id} className="rounded-xl border border-paper/10 bg-ink/20 p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className="border-acid/25 text-acid">{event.action}</Badge><span className="font-mono text-xs text-paper/45">{event.actor_id} · {event.actor_role}</span></div><time className="text-xs text-paper/40">{formatTime(event.created_at)}</time></div><p className="mt-3 text-sm text-paper/70">{event.reason}</p><p className="mt-2 font-mono text-xs text-paper/40">{event.target_type}/{event.target_id} · request {event.request_id ?? "—"}</p></article>)}{!query.data.length && <EmptyState label="No audited workforce actions yet." />}</CardContent></Card></div>;
}

function SystemPage({ token }: { token: string }) {
  const query = useAdminSystemQuery(token);
  const comparison = useAdminDeploymentComparisonQuery(token);
  if (query.isPending) return <Loading label="Loading system state…" />;
  if (query.isError || !query.data) return <ErrorPanel error={query.error} />;
  if (comparison.isPending) return <Loading label="Loading deployment comparison…" />;
  if (comparison.isError || !comparison.data) return <ErrorPanel error={comparison.error} />;
  return (
    <div className="space-y-6">
      <PageIntro title="System and deployment state" description="Safe configuration flags and revision identifiers help an operator explain what is running without exposing secrets." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border-paper/10 bg-paper/[0.04] text-paper">
          <CardHeader><CardTitle className="text-paper">Revision</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Stat label="Environment" value={query.data.environment} />
            <Stat label="Database" value={query.data.database_mode} />
            <Stat label="Migration" value={query.data.migration_revision ?? "unknown"} />
            <Stat label="Commit" value={query.data.git_commit_sha} />
            <Stat label="Deployment" value={query.data.deployment_id ?? "not recorded"} />
            <Stat label="Process started" value={formatTime(query.data.process_started_at)} />
          </CardContent>
        </Card>
        <Card className="border-paper/10 bg-paper/[0.04] text-paper">
          <CardHeader><CardTitle className="text-paper">Configuration posture</CardTitle></CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {Object.entries(query.data.configuration).map(([key, value]) => <Stat key={key} label={key.replaceAll("_", " ")} value={value ? "enabled" : "disabled"} tone={value ? "good" : "muted"} />)}
          </CardContent>
        </Card>
      </div>
      <Card className="border-paper/10 bg-paper/[0.04] text-paper">
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="text-paper">Release readiness gates</CardTitle>
            <Badge variant={query.data.release_ready ? "success" : "warning"}>
              {query.data.release_ready ? "ready" : "external checks pending"}
            </Badge>
          </div>
          <p className="text-sm leading-6 text-paper/50">
            Configuration is checked locally. Provider approvals, human QA, and remote receipt checks stay explicitly pending until an operator records them.
          </p>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {query.data.release_gates.map((gate) => (
            <article key={gate.key} className="rounded-xl border border-paper/10 bg-ink/20 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold">{gate.key.replaceAll("_", " ")}</h3>
                <Badge variant={gate.status === "ready" ? "success" : gate.status === "external_review" ? "secondary" : "warning"}>
                  {gate.status.replaceAll("_", " ")}
                </Badge>
              </div>
              <p className="mt-2 text-sm leading-6 text-paper/60">{gate.detail}</p>
              <p className="mt-2 text-xs leading-5 text-acid/80">Next: {gate.next_action}</p>
            </article>
          ))}
        </CardContent>
      </Card>
      <DeploymentComparisonCard data={comparison.data} />
      <Card className="border-paper/10 bg-paper/[0.04] text-paper">
        <CardHeader><CardTitle className="text-paper">Operator notes</CardTitle></CardHeader>
        <CardContent><ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-paper/60">{query.data.deployment_notes.map((note) => <li key={note}>{note}</li>)}</ul></CardContent>
      </Card>
    </div>
  );
}

function DeploymentComparisonCard({ data }: { data: import("@/features/admin/api").DeploymentComparison }) {
  return (
    <Card className="border-paper/10 bg-paper/[0.04] text-paper">
      <CardHeader>
        <CardTitle className="text-paper">Deployment/version comparison</CardTitle>
        <p className="text-sm leading-6 text-paper/50">{data.note}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Stat label="Current release" value={data.current ? `${data.current.app_version} · ${data.current.id}` : "not recorded"} tone="good" />
          <Stat label="Previous release" value={data.previous ? `${data.previous.app_version} · ${data.previous.id}` : "no baseline yet"} tone="muted" />
        </div>
        {data.changes.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <caption className="sr-only">Changes between the current and previous deployment</caption>
              <thead className="border-b border-paper/10 text-xs uppercase tracking-[0.12em] text-paper/40"><tr><th className="px-3 py-3">Field</th><th className="px-3 py-3">Previous</th><th className="px-3 py-3">Current</th></tr></thead>
              <tbody>{data.changes.map((change) => <tr key={change.field} className="border-b border-paper/5 align-top last:border-0"><td className="px-3 py-3 font-semibold">{change.field.replaceAll("_", " ")}</td><td className="max-w-sm px-3 py-3 font-mono text-xs text-paper/50">{displayDeploymentValue(change.previous)}</td><td className="max-w-sm px-3 py-3 font-mono text-xs text-acid">{displayDeploymentValue(change.current)}</td></tr>)}</tbody>
            </table>
          </div>
        ) : <EmptyState label="No field-level changes from the previous release." />}
        <details className="rounded-xl border border-paper/10 bg-ink/20 p-4">
          <summary className="cursor-pointer text-sm font-semibold text-acid">Show recorded release history</summary>
          <div className="mt-3 space-y-2">{data.history.map((release) => <div key={release.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-paper/10 py-2 text-sm last:border-0"><div><p className="font-semibold">{release.app_version} · {release.environment}</p><p className="font-mono text-xs text-paper/40">{release.id} · migration {release.migration_revision ?? "unknown"} · data {release.data_revision}</p></div><time className="text-xs text-paper/45">{formatTime(release.deployed_at)}</time></div>)}</div>
        </details>
      </CardContent>
    </Card>
  );
}

function displayDeploymentValue(value: unknown) {
  if (value == null) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function ReviewCard({
  token,
  item,
  canReview,
  canRollback,
  onSubmit,
  onEdit,
  onRollback,
  pending,
}: {
  token: string;
  item: import("@/features/admin/api").ReviewItem;
  canReview: boolean;
  canRollback: boolean;
  onSubmit: (input: { status: string; reason: string; activate: boolean }) => void;
  onEdit: (payload: import("@/features/admin/api").BenefitEditPayload) => void;
  onRollback: (version: number, reason: string) => void;
  pending: boolean;
}) {
  const [status, setStatus] = useState(item.verification_status);
  const [reason, setReason] = useState("Reviewed against the source document");
  const [activate, setActivate] = useState(item.is_active);
  const [editing, setEditing] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [editError, setEditError] = useState("");
  const [draft, setDraft] = useState(() => benefitEditDraft(item));
  const versions = useAdminBenefitVersionsQuery(token, item.id, showHistory);
  const job = item.domain === "job" ? item.job_metadata : {};
  const jobValue = (key: string) => {
    const value = job[key];
    return typeof value === "string" || typeof value === "number" ? String(value) : "";
  };
  const setField = <K extends keyof BenefitEditDraft>(
    key: K,
    value: BenefitEditDraft[K],
  ) => setDraft((current) => ({...current, [key]: value}));
  const submitEdit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const eligibility = JSON.parse(draft.eligibility_initial_json) as Record<string, unknown>;
      const renewal = draft.eligibility_renewal_json.trim()
        ? JSON.parse(draft.eligibility_renewal_json) as Record<string, unknown>
        : null;
      const localized = draft.localized_summary_json.trim()
        ? JSON.parse(draft.localized_summary_json) as Record<string, string>
        : {};
      const jobMetadata = draft.job_metadata_json.trim()
        ? JSON.parse(draft.job_metadata_json) as Record<string, unknown>
        : null;
      setEditError("");
      onEdit({
        expected_revision: item.content_revision,
        domain: draft.domain,
        name: draft.name.trim(),
        state_code: draft.state_code.trim() || null,
        category: draft.category.trim(),
        description: draft.description.trim(),
        eligibility_initial: eligibility,
        eligibility_renewal: renewal,
        benefits_text: draft.benefits_text.trim(),
        documents_required: draft.documents_text.split("\n").map((value) => value.trim()).filter(Boolean),
        application_process: draft.application_process.trim(),
        source_url: draft.source_url.trim(),
        source_title: draft.source_title.trim(),
        source_document_url: draft.source_document_url.trim(),
        source_excerpt: draft.source_excerpt.trim() || null,
        valid_from: draft.valid_from || null,
        valid_until: draft.valid_until || null,
        localized_summary: localized,
        job_metadata: jobMetadata,
        reason: draft.reason.trim(),
      });
      setEditing(false);
    } catch {
      setEditError("Eligibility, localization, and job metadata fields must contain valid JSON.");
    }
  };
  return (
    <Card className="border-paper/10 bg-paper/[0.04] text-paper">
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="border-orange/30 text-orange">{item.verification_status}</Badge>
              <span className="font-mono text-xs text-paper/40">{item.id}</span>
              <span className="font-mono text-xs text-paper/40">revision {item.content_revision}</span>
            </div>
            <h3 className="mt-2 text-lg font-bold">{item.name}</h3>
            <p className="mt-1 text-sm text-paper/50">{item.domain} · {item.state_code ?? "central"} · {item.source_title || "Source title missing"}</p>
            <p className="mt-1 text-xs text-paper/40">Last source check: {item.last_verified_date ?? "not recorded"}</p>
          </div>
          {item.source_document_url && <a className="inline-flex items-center gap-1 text-xs font-semibold text-acid underline-offset-4 hover:underline" href={item.source_document_url} target="_blank" rel="noreferrer">Source <ExternalLink className="size-3" aria-hidden="true" /></a>}
        </div>
        {item.domain === "job" && <div className="grid gap-2 rounded-xl border border-blue/20 bg-blue/[0.06] p-4 text-xs text-paper/70 sm:grid-cols-2"><p><span className="text-paper/40">Employer:</span> {jobValue("employer") || "Not stated"}</p><p><span className="text-paper/40">Deadline:</span> {jobValue("application_deadline") || "Not stated"}</p><p><span className="text-paper/40">Vacancies:</span> {jobValue("vacancy_count") || "Not stated"}</p><p><span className="text-paper/40">Employment:</span> {jobValue("employment_type") || "Not stated"}</p></div>}
        <details className="rounded-xl border border-paper/10 bg-ink/20"><summary className="cursor-pointer px-4 py-3 text-sm font-semibold">Show machine review and source excerpt</summary><div className="space-y-3 border-t border-paper/10 px-4 py-3 text-xs leading-5 text-paper/60"><p>{item.source_excerpt || "No source excerpt stored."}</p><pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-ink p-3 font-mono text-[0.68rem]">{JSON.stringify(item.automated_review, null, 2)}</pre></div></details>
        <div className="flex flex-wrap gap-2 border-t border-paper/10 pt-4">
          {canReview && <Button type="button" size="sm" variant="outline" onClick={() => { setEditing((value) => !value); setEditError(""); }}>{editing ? "Close editor" : "Edit benefit"}</Button>}
          <Button type="button" size="sm" variant="ghost" onClick={() => setShowHistory((value) => !value)}>{showHistory ? "Hide history" : "View version history"}</Button>
        </div>
        {editing && canReview && <form className="grid gap-3 rounded-xl border border-acid/20 bg-acid/[0.04] p-4 md:grid-cols-2" onSubmit={submitEdit}>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Name<input required value={draft.name} onChange={(event) => setField("name", event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Domain<select value={draft.domain} onChange={(event) => setField("domain", event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-2 text-sm text-paper"><option value="scheme">Scheme</option><option value="scholarship">Scholarship</option><option value="job">Job</option></select></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">State code<input value={draft.state_code} onChange={(event) => setField("state_code", event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" placeholder="KA or blank for central" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Category<input value={draft.category} onChange={(event) => setField("category", event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60 md:col-span-2">Description<textarea value={draft.description} onChange={(event) => setField("description", event.target.value)} className="min-h-24 rounded-lg border border-paper/15 bg-ink px-3 py-2 text-sm text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Eligibility JSON<textarea required value={draft.eligibility_initial_json} onChange={(event) => setField("eligibility_initial_json", event.target.value)} className="min-h-32 rounded-lg border border-paper/15 bg-ink px-3 py-2 font-mono text-xs text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Renewal eligibility JSON<textarea value={draft.eligibility_renewal_json} onChange={(event) => setField("eligibility_renewal_json", event.target.value)} className="min-h-32 rounded-lg border border-paper/15 bg-ink px-3 py-2 font-mono text-xs text-paper" placeholder="Optional JSON object" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Benefits text<textarea value={draft.benefits_text} onChange={(event) => setField("benefits_text", event.target.value)} className="min-h-24 rounded-lg border border-paper/15 bg-ink px-3 py-2 text-sm text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Documents, one per line<textarea value={draft.documents_text} onChange={(event) => setField("documents_text", event.target.value)} className="min-h-24 rounded-lg border border-paper/15 bg-ink px-3 py-2 text-sm text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60 md:col-span-2">Application process<textarea value={draft.application_process} onChange={(event) => setField("application_process", event.target.value)} className="min-h-24 rounded-lg border border-paper/15 bg-ink px-3 py-2 text-sm text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Source URL<input value={draft.source_url} onChange={(event) => setField("source_url", event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Source title<input value={draft.source_title} onChange={(event) => setField("source_title", event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Source document URL<input value={draft.source_document_url} onChange={(event) => setField("source_document_url", event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Valid from<input type="date" value={draft.valid_from} onChange={(event) => setField("valid_from", event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Valid until<input type="date" value={draft.valid_until} onChange={(event) => setField("valid_until", event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60 md:col-span-2">Source excerpt<textarea value={draft.source_excerpt} onChange={(event) => setField("source_excerpt", event.target.value)} className="min-h-24 rounded-lg border border-paper/15 bg-ink px-3 py-2 text-sm text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Localized summaries JSON<textarea value={draft.localized_summary_json} onChange={(event) => setField("localized_summary_json", event.target.value)} className="min-h-24 rounded-lg border border-paper/15 bg-ink px-3 py-2 font-mono text-xs text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60">Job metadata JSON<textarea value={draft.job_metadata_json} onChange={(event) => setField("job_metadata_json", event.target.value)} className="min-h-24 rounded-lg border border-paper/15 bg-ink px-3 py-2 font-mono text-xs text-paper" /></label>
          <label className="grid gap-1 text-xs font-semibold text-paper/60 md:col-span-2">Edit reason<input required minLength={3} value={draft.reason} onChange={(event) => setField("reason", event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" /></label>
          {editError && <p role="alert" className="md:col-span-2 text-sm text-orange">{editError}</p>}
          <div className="flex flex-wrap items-center justify-between gap-3 md:col-span-2"><p className="text-xs leading-5 text-orange/80">Saving an edit deactivates the row and sends it back to review.</p><Button type="submit" size="sm" disabled={pending}>{pending ? "Saving…" : "Save edit"}</Button></div>
        </form>}
        {canReview ? <form className="grid gap-3 border-t border-paper/10 pt-4 md:grid-cols-[180px_1fr_auto] md:items-end" onSubmit={(event) => { event.preventDefault(); onSubmit({status, reason, activate}); }}><label className="grid gap-1 text-xs font-semibold text-paper/60">Decision<select value={status} onChange={(event) => setStatus(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-2 text-sm text-paper"><option value="human_verified">Human verified</option><option value="needs_review">Needs review</option><option value="stale">Stale</option><option value="machine_reviewed">Machine reviewed</option></select></label><label className="grid gap-1 text-xs font-semibold text-paper/60">Reason<input value={reason} onChange={(event) => setReason(event.target.value)} className="h-10 rounded-lg border border-paper/15 bg-ink px-3 text-sm text-paper" /></label><div className="flex items-center gap-3"><label className="flex items-center gap-2 text-xs text-paper/60"><input type="checkbox" checked={activate} onChange={(event) => setActivate(event.target.checked)} /> Publish</label><Button type="submit" size="sm" disabled={pending || reason.trim().length < 3}>{pending ? "Saving…" : "Save decision"}</Button></div></form> : <p className="text-xs text-paper/45">Your role can inspect this row but cannot change publication status.</p>}
        {showHistory && <div className="space-y-2 rounded-xl border border-paper/10 bg-ink/20 p-4"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-paper/40">Immutable version history</p>{versions.isPending && <p className="text-sm text-paper/45">Loading history…</p>}{versions.isError && <p role="alert" className="text-sm text-orange">Could not load version history.</p>}{versions.data?.versions.map((version) => <div key={version.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-paper/10 py-2 text-sm last:border-0"><div><p><span className="font-mono text-acid">v{version.version}</span> · <span className="font-semibold">{version.action}</span> · {version.actor_id}</p><p className="text-xs text-paper/45">{version.reason} · {formatTime(version.created_at)}</p></div>{canRollback && version.version !== item.content_revision && <Button type="button" size="sm" variant="outline" disabled={pending} onClick={() => onRollback(version.version, `Restore benefit version ${version.version}`)}><RotateCcw className="size-3.5" aria-hidden="true" />Restore v{version.version}</Button>}</div>)}{versions.data && !versions.data.versions.length && <p className="text-sm text-paper/45">No history recorded yet.</p>}</div>}
      </CardContent>
    </Card>
  );
}

type BenefitEditDraft = Omit<import("@/features/admin/api").BenefitEditPayload, "state_code" | "source_excerpt" | "valid_from" | "valid_until"> & {
  state_code: string;
  source_excerpt: string;
  valid_from: string;
  valid_until: string;
  documents_text: string;
  eligibility_initial_json: string;
  eligibility_renewal_json: string;
  localized_summary_json: string;
  job_metadata_json: string;
};

function benefitEditDraft(item: import("@/features/admin/api").ReviewItem): BenefitEditDraft {
  return {
    expected_revision: item.content_revision,
    domain: item.domain,
    name: item.name,
    state_code: item.state_code ?? "",
    category: item.category,
    description: item.description,
    eligibility_initial: item.eligibility_initial,
    eligibility_renewal: item.eligibility_renewal,
    benefits_text: item.benefits_text,
    documents_required: item.documents_required,
    application_process: item.application_process,
    source_url: item.source_url,
    source_title: item.source_title,
    source_document_url: item.source_document_url,
    source_excerpt: item.source_excerpt ?? "",
    valid_from: item.valid_from ?? "",
    valid_until: item.valid_until ?? "",
    localized_summary: item.localized_summary,
    job_metadata: Object.keys(item.job_metadata).length ? item.job_metadata : null,
    reason: "Corrected against the official source",
    documents_text: item.documents_required.join("\n"),
    eligibility_initial_json: JSON.stringify(item.eligibility_initial, null, 2),
    eligibility_renewal_json: item.eligibility_renewal ? JSON.stringify(item.eligibility_renewal, null, 2) : "",
    localized_summary_json: JSON.stringify(item.localized_summary, null, 2),
    job_metadata_json: item.job_metadata && Object.keys(item.job_metadata).length ? JSON.stringify(item.job_metadata, null, 2) : "",
  };
}

function PageIntro({ title, description }: { title: string; description: string }) {
  return <div><h2 className="text-2xl font-bold tracking-tight text-foreground">{title}</h2><p className="mt-2 max-w-3xl text-base leading-6 text-muted-foreground">{description}</p></div>;
}

function MetricCard({ label, value, detail, tone = "default" }: { label: string; value: string; detail: string; tone?: "default" | "warning" }) {
  return <Card className={`border-border bg-card ${tone === "warning" ? "border-warning/70" : ""}`}><CardContent className="p-5"><p className="text-sm font-semibold text-muted-foreground">{label}</p><p className={`mt-3 text-3xl font-bold ${tone === "warning" ? "text-warning-foreground" : "text-primary"}`}>{value}</p><p className="mt-2 text-sm text-muted-foreground">{detail}</p></CardContent></Card>;
}

function Stat({ label, value, tone = "default" }: { label: string; value: string | number; tone?: "default" | "good" | "warning" | "muted" }) {
  const text = tone === "good" ? "text-success" : tone === "warning" ? "text-destructive" : tone === "muted" ? "text-muted-foreground" : "text-foreground";
  return <div className="rounded border border-border bg-muted/40 px-3 py-3"><p className="text-sm text-muted-foreground">{label}</p><p className={`mt-1 text-lg font-bold ${text}`}>{value}</p></div>;
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

function Loading({ label }: { label: string }) { return <div className="grid min-h-56 place-items-center rounded-lg border border-border bg-muted/30 text-sm text-muted-foreground"><span role="status" className="inline-flex items-center gap-2"><RefreshCw className="size-4 motion-safe:animate-spin motion-reduce:animate-none" aria-hidden="true" />{label}</span></div>; }
function ErrorPanel({ error }: { error: unknown }) { return <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-5 text-base leading-6 text-destructive"><div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" /><span>{toUserMessage(error)}</span></div></div>; }
function EmptyState({ label }: { label: string }) { return <p className="px-4 py-8 text-center text-base text-muted-foreground">{label}</p>; }
function outcomeBadge(outcome: string) { if (outcome === "success") return <Badge variant="success"><CheckCircle2 className="size-3" aria-hidden="true" />success</Badge>; if (outcome === "error" || outcome === "escalated") return <Badge variant="warning"><ShieldAlert className="size-3" aria-hidden="true" />{outcome}</Badge>; return <Badge variant="outline" className="border-paper/15 text-paper/55"><Clock3 className="size-3" aria-hidden="true" />{outcome || "event"}</Badge>; }
function formatTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString([], {dateStyle: "medium", timeStyle: "short"}); }
function formatNumber(value: number) { return new Intl.NumberFormat().format(value); }
function formatMinor(value: number) { return new Intl.NumberFormat(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(value / 100); }
function formatUsdBreakdown(values: Record<string, number>) { const entries = Object.entries(values); return entries.length ? entries.map(([key, value]) => `${key} $${value.toFixed(4)}`).join(" · ") : "not reported"; }
function formatCountBreakdown(values: Record<string, number>) { const entries = Object.entries(values); return entries.length ? entries.map(([key, value]) => `${key} ${formatNumber(value)}`).join(" · ") : "none"; }
function formatPercent(value: number) { return `${(value * 100).toFixed(value > 0 && value < 0.1 ? 1 : 0)}%`; }
function evaluationMetrics(report: Record<string, unknown>) {
  const raw = report.metrics;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const metrics = raw as Record<string, unknown>;
  const average = metrics.average_duration_ms;
  const p95 = metrics.p95_duration_ms;
  const passRate = metrics.passed_count && metrics.case_count ? Number(metrics.passed_count) / Number(metrics.case_count) : null;
  if (typeof average !== "number" || typeof p95 !== "number" || passRate == null || !Number.isFinite(passRate)) return null;
  return {average_duration_ms: average, p95_duration_ms: p95, pass_rate: passRate};
}
