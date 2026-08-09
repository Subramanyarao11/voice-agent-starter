import { useEffect, useState, type FormEvent } from "react";

import { Link, useParams } from "@tanstack/react-router";
import {
  Check,
  ClipboardCheck,
  Copy,
  ExternalLink,
  KeyRound,
  Link2,
  LockKeyhole,
  Pause,
  Play,
  ShieldCheck,
  Square,
  UserRoundCheck,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAdminMeQuery } from "@/features/admin/queries";
import { beginAdminOidcLogin, isAdminOidcConfigured } from "@/features/admin/oidc";
import { useAdminSessionStore } from "@/features/admin/store";
import {
  useAssistanceReceiptQuery,
  useCitizenAssistanceActionsQuery,
  useCitizenAssistanceQuery,
  useCompleteAssistanceMutation,
  useConfirmAssistanceActionMutation,
  useConsentAssistanceMutation,
  useCreateAssistanceInvitationMutation,
  useDraftAssistanceActionMutation,
  useExecuteAssistanceActionMutation,
  useHelperAssistanceActionsQuery,
  useHelperAssistanceQuery,
  usePauseAssistanceMutation,
  useRedeemAssistanceMutation,
  useRevokeAssistanceMutation,
} from "@/features/assistance/queries";
import { ApiError, toUserMessage, type AssistanceAction, type AssistanceSession } from "@/lib/api";

const ACTION_LABELS: Record<string, string> = {
  review_public_benefit: "Review a benefit with the citizen",
  prepare_application: "Prepare an application",
  record_application_reference: "Record an application reference",
  contact_department: "Open a department handoff",
  create_escalation: "Create a human-support escalation",
  print_application_pack: "Prepare an application pack",
  language_or_accessibility_help: "Provide language or accessibility help",
};

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function AssistanceError({ error }: { error: unknown }) {
  return (
    <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm leading-6 text-destructive">
      {toUserMessage(error)}
    </p>
  );
}

function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2_000);
    } catch {
      setCopied(false);
    }
  };
  return (
    <Button type="button" variant="outline" className="gap-2" onClick={() => void copy()}>
      {copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
      {copied ? "Copied" : label}
    </Button>
  );
}

function AccessCard({ error }: { error?: string }) {
  const token = useAdminSessionStore((state) => state.token);
  const setToken = useAdminSessionStore((state) => state.setToken);
  const [draft, setDraft] = useState("");
  const oidcConfigured = isAdminOidcConfigured();
  const allowManualToken = !oidcConfigured || import.meta.env.VITE_ADMIN_ALLOW_MANUAL_TOKEN === "true";
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (draft.trim()) setToken(draft);
  };

  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardHeader>
        <Badge variant="outline" className="w-fit border-primary/40 text-primary">Workforce helper access</Badge>
        <CardTitle className="text-2xl">Open a Saathi session securely.</CardTitle>
        <CardDescription className="text-base leading-7">
          Helpers must use the workforce identity and role assigned by the deployment. Citizen data is not available until the citizen confirms the named purpose.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {error && <AssistanceError error={error} />}
        {oidcConfigured && (
          <Button type="button" className="gap-2" onClick={() => void beginAdminOidcLogin()}>
            <ShieldCheck className="size-4" aria-hidden="true" />
            Sign in with organization SSO
          </Button>
        )}
        {allowManualToken && (
          <form className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end" onSubmit={submit}>
            <label className="grid gap-2 text-sm font-semibold">
              Workforce token
              <input
                type="password"
                autoComplete="off"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                className="min-h-11 rounded-md border bg-background px-3 font-normal"
              />
            </label>
            <Button type="submit" disabled={!draft.trim()} className="gap-2">
              <KeyRound className="size-4" aria-hidden="true" />
              Continue
            </Button>
          </form>
        )}
        {!token && <p className="text-sm text-muted-foreground">For a local demo, an operator can sign in from the <Link to="/admin" className="font-semibold text-primary underline underline-offset-4">admin access page</Link> first.</p>}
        <p className="flex items-start gap-2 text-sm leading-6 text-muted-foreground">
          <LockKeyhole className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
          The browser only keeps the workforce session in tab-scoped storage. Invitation secrets are never saved here.
        </p>
      </CardContent>
    </Card>
  );
}

export function CitizenAssistancePage() {
  const { assistanceId } = useParams({ from: "/assistant/sessions/$assistanceId" });
  const sessionQuery = useCitizenAssistanceQuery(assistanceId);
  const actionsQuery = useCitizenAssistanceActionsQuery(
    assistanceId,
    sessionQuery.data?.status === "active" || sessionQuery.data?.status === "awaiting_citizen_consent",
  );
  const consentMutation = useConsentAssistanceMutation(assistanceId);
  const revokeMutation = useRevokeAssistanceMutation(assistanceId);
  const confirmActionMutation = useConfirmAssistanceActionMutation(assistanceId);
  const receiptQuery = useAssistanceReceiptQuery(
    assistanceId,
    Boolean(sessionQuery.data && ["completed", "revoked", "expired"].includes(sessionQuery.data.status)),
  );
  const session = sessionQuery.data;
  const actionRows = actionsQuery.data ?? receiptQuery.data?.actions ?? [];
  const isCitizenAuthError = sessionQuery.error instanceof ApiError && [401, 403].includes(sessionQuery.error.status);

  return (
    <main className="min-h-svh bg-background px-4 py-8 text-foreground sm:px-6 sm:py-12">
      <div className="mx-auto max-w-3xl space-y-6">
        <header>
          <Link to="/household" className="text-sm font-semibold text-primary underline underline-offset-4">← Household workspace</Link>
          <p className="mt-6 text-sm font-semibold text-primary">Citizen approval</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">Review your Saathi session</h1>
          <p className="mt-3 text-base leading-7 text-muted-foreground">A helper can see only the purpose and categories you approve. You can withdraw access at any time.</p>
        </header>
        {sessionQuery.isPending && <p role="status" className="text-sm text-muted-foreground">Loading the secure invitation…</p>}
        {isCitizenAuthError && (
          <Card className="border-warning/40 bg-warning/10">
            <CardHeader><CardTitle>Sign in is required</CardTitle><CardDescription>Open this page after signing in to your citizen workspace. The invitation itself does not sign you in.</CardDescription></CardHeader>
            <CardContent><Link to="/household" className="inline-flex min-h-11 items-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">Open citizen sign-in</Link></CardContent>
          </Card>
        )}
        {sessionQuery.error && !isCitizenAuthError && <AssistanceError error={sessionQuery.error} />}
        {session && <CitizenSessionCard session={session} actions={actionRows} consentMutation={consentMutation} revokeMutation={revokeMutation} confirmActionMutation={confirmActionMutation} />}
        {receiptQuery.error && <AssistanceError error={receiptQuery.error} />}
      </div>
    </main>
  );
}

function CitizenSessionCard({
  session,
  actions,
  consentMutation,
  revokeMutation,
  confirmActionMutation,
}: {
  session: AssistanceSession;
  actions: AssistanceAction[];
  consentMutation: ReturnType<typeof useConsentAssistanceMutation>;
  revokeMutation: ReturnType<typeof useRevokeAssistanceMutation>;
  confirmActionMutation: ReturnType<typeof useConfirmAssistanceActionMutation>;
}) {
  const awaiting = session.status === "awaiting_citizen_consent";
  const active = session.status === "active";
  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Badge variant={active ? "success" : awaiting ? "warning" : "outline"}>{humanize(session.status)}</Badge>
          <span className="text-sm text-muted-foreground">Expires {formatDate(session.expires_at)}</span>
        </div>
        <CardTitle>{humanize(session.purpose)}</CardTitle>
        <CardDescription>This grant is limited to {session.helper_org_id || "the named helper organization"} and the current purpose.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <InfoList title="Helper can see" values={session.approved_data_categories} />
          <InfoList title="Helper can do" values={session.allowed_action_keys.map((key) => ACTION_LABELS[key] ?? humanize(key))} />
        </div>
        {awaiting && (
          <div className="rounded-lg border border-warning/40 bg-warning/10 p-4">
            <p className="font-semibold">Confirm only if this purpose is correct.</p>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">The helper is waiting. Confirming creates an auditable consent record and reveals the bounded projection.</p>
            <Button type="button" className="mt-4 gap-2" disabled={consentMutation.isPending} onClick={() => consentMutation.mutate()}>
              <UserRoundCheck className="size-4" aria-hidden="true" />
              {consentMutation.isPending ? "Confirming…" : "Confirm this Saathi session"}
            </Button>
          </div>
        )}
        {active && (
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" variant="outline" className="gap-2" disabled={revokeMutation.isPending} onClick={() => revokeMutation.mutate()}>
              <Square className="size-4" aria-hidden="true" />
              {revokeMutation.isPending ? "Withdrawing…" : "Withdraw access"}
            </Button>
            <span className="text-sm text-muted-foreground">Withdrawals stop new helper actions immediately.</span>
          </div>
        )}
        {(consentMutation.error || revokeMutation.error) && <AssistanceError error={consentMutation.error ?? revokeMutation.error} />}
        {actions.length > 0 && <ActionStatusList actions={actions} onConfirm={(id) => confirmActionMutation.mutate(id)} />}
        {confirmActionMutation.error && <AssistanceError error={confirmActionMutation.error} />}
      </CardContent>
    </Card>
  );
}

function InfoList({ title, values }: { title: string; values: string[] }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-sm font-semibold">{title}</p>
      <ul className="mt-2 space-y-2 text-sm leading-6 text-muted-foreground">
        {values.length > 0 ? values.map((value) => <li key={value} className="flex gap-2"><Check className="mt-1 size-4 shrink-0 text-success" aria-hidden="true" />{value}</li>) : <li>None listed</li>}
      </ul>
    </div>
  );
}

function ActionStatusList({ actions, onConfirm, onExecute }: { actions: AssistanceAction[]; onConfirm?: (id: string) => void; onExecute?: (id: string) => void }) {
  return (
    <div className="space-y-3" aria-live="polite">
      <h2 className="text-lg font-bold">Action record</h2>
      {actions.map((action) => (
        <div key={action.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
          <div>
            <p className="font-semibold">{ACTION_LABELS[action.action_key] ?? humanize(action.action_key)}</p>
            <p className="mt-1 text-sm text-muted-foreground">{humanize(action.stage)}{action.target_type ? ` · ${humanize(action.target_type)}` : ""}</p>
            {action.effect_code && <p className="mt-1 text-sm font-semibold text-success">Result: {humanize(action.effect_code)}{action.effect_reference_masked ? ` · ${action.effect_reference_masked}` : ""}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            {onConfirm && action.stage === "drafted" && <Button type="button" variant="outline" className="gap-2" onClick={() => onConfirm(action.id)}><UserRoundCheck className="size-4" aria-hidden="true" />Confirm action</Button>}
            {onExecute && action.stage === "citizen_confirmed" && <Button type="button" className="gap-2" onClick={() => onExecute(action.id)}><Play className="size-4" aria-hidden="true" />Execute confirmed action</Button>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function HelperRedeemPage() {
  const [invitationToken, setInvitationToken] = useState("");
  const [assistanceId, setAssistanceId] = useState("");
  const [tokenReady, setTokenReady] = useState(false);
  const adminToken = useAdminSessionStore((state) => state.token);
  const meQuery = useAdminMeQuery(adminToken);
  const redeemMutation = useRedeemAssistanceMutation();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setInvitationToken(params.get("token") ?? "");
    setAssistanceId(params.get("session") ?? "");
    setTokenReady(true);
  }, []);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!invitationToken.trim() || !adminToken) return;
    redeemMutation.mutate(
      { invitationToken: invitationToken.trim(), adminToken },
      { onSuccess: (session) => setAssistanceId(session.id) },
    );
  };

  const accessError = meQuery.error ? toUserMessage(meQuery.error) : undefined;
  return (
    <main className="min-h-svh bg-background px-4 py-8 text-foreground sm:px-6 sm:py-12">
      <div className="mx-auto max-w-4xl space-y-6">
        <header>
          <Link to="/" className="text-sm font-semibold text-primary underline underline-offset-4">← Sahaayak home</Link>
          <p className="mt-6 text-sm font-semibold text-primary">Assisted Saathi</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">Helper workspace</h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">Redeem a citizen invitation, wait for consent, and carry out only the actions the citizen has confirmed.</p>
        </header>
        {!adminToken && <AccessCard />}
        {adminToken && meQuery.isPending && <p role="status" className="text-sm text-muted-foreground">Checking workforce access…</p>}
        {adminToken && meQuery.isError && <AccessCard error={accessError} />}
        {adminToken && meQuery.data && tokenReady && !assistanceId && (
          <Card>
            <CardHeader><CardTitle>Redeem invitation</CardTitle><CardDescription>Paste the one-time token the citizen shared with you. It is used only for this redemption request.</CardDescription></CardHeader>
            <CardContent>
              <form className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end" onSubmit={submit}>
                <label className="grid gap-2 text-sm font-semibold">Invitation token<input className="min-h-11 rounded-md border bg-background px-3 font-mono text-sm font-normal" value={invitationToken} onChange={(event) => setInvitationToken(event.target.value)} autoComplete="off" /></label>
                <Button type="submit" disabled={!invitationToken.trim() || redeemMutation.isPending} className="gap-2"><Link2 className="size-4" aria-hidden="true" />{redeemMutation.isPending ? "Redeeming…" : "Redeem invitation"}</Button>
              </form>
              {redeemMutation.error && <div className="mt-4"><AssistanceError error={redeemMutation.error} /></div>}
            </CardContent>
          </Card>
        )}
        {adminToken && meQuery.data && assistanceId && <HelperWorkspace assistanceId={assistanceId} adminToken={adminToken} />}
      </div>
    </main>
  );
}

function HelperWorkspace({ assistanceId, adminToken }: { assistanceId: string; adminToken: string }) {
  const sessionQuery = useHelperAssistanceQuery(assistanceId, adminToken, true);
  const actionsQuery = useHelperAssistanceActionsQuery(assistanceId, adminToken, Boolean(sessionQuery.data));
  const draftMutation = useDraftAssistanceActionMutation(assistanceId, adminToken);
  const executeMutation = useExecuteAssistanceActionMutation(assistanceId, adminToken);
  const pauseMutation = usePauseAssistanceMutation(assistanceId, adminToken);
  const completeMutation = useCompleteAssistanceMutation(assistanceId, adminToken);
  const [actionKey, setActionKey] = useState("");
  const [targetType, setTargetType] = useState("");
  const [targetId, setTargetId] = useState("");
  const [applicationStatus, setApplicationStatus] = useState("submitted");
  const [submissionDate, setSubmissionDate] = useState("");
  const [externalReference, setExternalReference] = useState("");
  const session = sessionQuery.data;
  const actions = actionsQuery.data ?? [];
  const selectedActionKey = actionKey || session?.allowed_action_keys[0] || "";
  const targetRequired = ["application_case", "benefit", "department"].includes(targetType);

  useEffect(() => {
    if (session?.allowed_action_keys[0] && !actionKey) setActionKey(session.allowed_action_keys[0]);
  }, [actionKey, session?.allowed_action_keys]);

  const draft = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedActionKey) return;
    draftMutation.mutate({
      action_key: selectedActionKey,
      target_type: targetType,
      target_id: targetId.trim(),
      preview_code: "helper_ui_review",
      application_status: applicationStatus,
      submission_date: submissionDate || undefined,
      external_reference: externalReference.trim() || undefined,
      reason_code: "assisted_saathi",
      idempotency_key: `helper-ui-${crypto.randomUUID()}`,
    });
  };

  if (sessionQuery.isPending) return <p role="status" className="text-sm text-muted-foreground">Loading the helper projection…</p>;
  if (sessionQuery.error) return <AssistanceError error={sessionQuery.error} />;
  if (!session) return null;
  const active = session.status === "active";
  const terminal = ["completed", "revoked", "expired"].includes(session.status);
  return (
    <>
      <Card>
        <CardHeader className="gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3"><Badge variant={active ? "success" : session.status === "awaiting_citizen_consent" ? "warning" : "outline"}>{humanize(session.status)}</Badge><span className="text-sm text-muted-foreground">Session {session.id}</span></div>
          <CardTitle>{ACTION_LABELS[session.allowed_action_keys[0] ?? ""] ? "Citizen assistance session" : humanize(session.purpose)}</CardTitle>
          <CardDescription>Purpose: {humanize(session.purpose)} · expires {formatDate(session.expires_at)}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2"><InfoList title="Approved categories" values={session.approved_data_categories} /><InfoList title="Allowed actions" values={session.allowed_action_keys.map((key) => ACTION_LABELS[key] ?? humanize(key))} /></div>
          {session.status === "awaiting_citizen_consent" && <div className="rounded-lg border border-warning/40 bg-warning/10 p-4 text-sm leading-6"><p className="font-semibold">Waiting for citizen confirmation.</p><p className="mt-1">Ask the citizen to open the approval page:</p><a className="mt-2 inline-flex items-center gap-2 font-semibold text-primary underline underline-offset-4" href={`/assistant/sessions/${encodeURIComponent(assistanceId)}`} target="_blank" rel="noreferrer">Open approval page <ExternalLink className="size-3.5" aria-hidden="true" /></a></div>}
          {active && <form className="space-y-4 rounded-lg border bg-muted/20 p-4" onSubmit={draft}><div><h2 className="font-bold">Prepare a citizen-confirmed action</h2><p className="mt-1 text-sm leading-6 text-muted-foreground">Drafting does not change an application. The citizen must review and confirm it before execution.</p></div><div className="grid gap-4 sm:grid-cols-2"><label className="grid gap-2 text-sm font-semibold">Action<select className="min-h-11 rounded-md border bg-background px-3 font-normal" value={selectedActionKey} onChange={(event) => setActionKey(event.target.value)}>{session.allowed_action_keys.map((key) => <option key={key} value={key}>{ACTION_LABELS[key] ?? humanize(key)}</option>)}</select></label><label className="grid gap-2 text-sm font-semibold">Target type<select className="min-h-11 rounded-md border bg-background px-3 font-normal" value={targetType} onChange={(event) => setTargetType(event.target.value)}><option value="">No target</option><option value="application_case">Application case</option><option value="benefit">Benefit</option><option value="department">Department</option><option value="language">Language</option></select></label></div><label className="grid gap-2 text-sm font-semibold">Target identifier <span className="font-normal text-muted-foreground">(optional unless the action needs one)</span><input className="min-h-11 rounded-md border bg-background px-3 font-normal" value={targetId} onChange={(event) => setTargetId(event.target.value)} placeholder={targetRequired ? "Paste the safe record identifier" : "Leave blank when not needed"} /></label>{selectedActionKey === "record_application_reference" && <div className="grid gap-4 rounded-lg border border-primary/20 bg-background p-4 sm:grid-cols-3"><label className="grid gap-2 text-sm font-semibold">Application status<select className="min-h-11 rounded-md border bg-background px-3 font-normal" value={applicationStatus} onChange={(event) => setApplicationStatus(event.target.value)}><option value="submitted">Submitted</option><option value="acknowledged">Acknowledged</option><option value="under_review">Under review</option><option value="action_required">Action required</option><option value="approved">Approved</option><option value="delivered">Delivered</option><option value="rejected">Rejected</option><option value="withdrawn">Withdrawn</option></select></label><label className="grid gap-2 text-sm font-semibold">Submission date<input type="date" className="min-h-11 rounded-md border bg-background px-3 font-normal" value={submissionDate} onChange={(event) => setSubmissionDate(event.target.value)} /></label><label className="grid gap-2 text-sm font-semibold">Reference number <span className="font-normal text-muted-foreground">(encrypted)</span><input className="min-h-11 rounded-md border bg-background px-3 font-normal" value={externalReference} onChange={(event) => setExternalReference(event.target.value)} /></label></div>}<Button type="submit" disabled={draftMutation.isPending || (targetRequired && !targetId.trim())} className="gap-2"><ClipboardCheck className="size-4" aria-hidden="true" />{draftMutation.isPending ? "Creating draft…" : "Create action draft"}</Button>{draftMutation.error && <AssistanceError error={draftMutation.error} />}</form>}
          {actionsQuery.error && <AssistanceError error={actionsQuery.error} />}
          {actions.length > 0 && <ActionStatusList actions={actions} onExecute={(id) => executeMutation.mutate(id)} />}
          {executeMutation.error && <AssistanceError error={executeMutation.error} />}
          {active && <div className="flex flex-wrap gap-3 border-t pt-5"><Button type="button" variant="outline" className="gap-2" disabled={pauseMutation.isPending} onClick={() => pauseMutation.mutate()}><Pause className="size-4" aria-hidden="true" />Pause session</Button><Button type="button" variant="outline" className="gap-2" disabled={completeMutation.isPending} onClick={() => completeMutation.mutate()}><Square className="size-4" aria-hidden="true" />{completeMutation.isPending ? "Closing…" : "Complete session"}</Button></div>}
          {(pauseMutation.error || completeMutation.error) && <AssistanceError error={pauseMutation.error ?? completeMutation.error} />}
          {terminal && <p className="rounded-lg bg-muted p-4 text-sm leading-6">This session is closed. No new projection or action can be created.</p>}
        </CardContent>
      </Card>
    </>
  );
}
