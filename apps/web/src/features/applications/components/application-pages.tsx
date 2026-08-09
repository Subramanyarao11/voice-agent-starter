import { useEffect, useState, type FormEvent } from "react";

import { Link, useNavigate, useParams } from "@tanstack/react-router";
import {
  ArrowLeft,
  CheckCircle2,
  Circle,
  ClipboardCheck,
  ExternalLink,
  FileText,
  LockKeyhole,
  Printer,
  TriangleAlert,
} from "lucide-react";

import { PublicFooter, Topbar } from "@/components/app/topbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  useApplicationQuery,
  useApplicationPackPreviewQuery,
  useApplicationFieldsQuery,
  useApplicationOutcomeQuery,
  useApplicationRequirementsQuery,
  useApplicationsQuery,
  useRecordApplicationOutcomeMutation,
  useRecordApplicationStatusMutation,
  useUpdateApplicationFieldMutation,
  useUpdateApplicationRequirementMutation,
} from "@/features/applications/queries";
import { useGuestSessionStore } from "@/features/session/store";
import { useUpdateApplicationTaskMutation } from "@/features/saved/queries";
import type {
  ApplicationCase,
  ApplicationFieldDefinition,
  ApplicationRequirement,
  ApplicationTask,
} from "@/lib/api";
import { toUserMessage } from "@/lib/api";

const STATUS_OPTIONS = [
  "portal_opened",
  "submitted",
  "acknowledged",
  "under_review",
  "action_required",
  "approved",
  "delivered",
  "rejected",
  "withdrawn",
] as const;

function statusLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function formatDate(value: string | null): string {
  if (!value) return "Not recorded";
  const date = new Date(value + "T00:00:00");
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, { dateStyle: "medium" });
}

function readinessLabel(value: string): string {
  if (value === "ready") return "Ready to submit";
  if (value === "ready_with_warnings") return "Ready with checks";
  return "Checklist incomplete";
}

function isTerminalStatus(value: string): boolean {
  return ["delivered", "rejected", "withdrawn"].includes(value);
}

function GuestSessionNotice() {
  return (
    <Card className="border-warning/30 bg-warning/10">
      <CardContent className="flex items-start gap-3 p-5">
        <LockKeyhole className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden="true" />
        <div>
          <h2 className="font-semibold">Start a guest session first</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            Your application checklist is private to this browser session.
          </p>
          <Link to="/" className="mt-3 inline-flex font-semibold text-primary underline-offset-4 hover:underline">
            Return to Sahaayak
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

export function ApplicationsPage() {
  const sessionId = useGuestSessionStore((state) => state.sessionId);
  const accessToken = useGuestSessionStore((state) => state.accessToken);
  const applicationsQuery = useApplicationsQuery(sessionId, accessToken);

  return (
    <div className="min-h-svh bg-background text-foreground">
      <Topbar sessionId={sessionId} connected={Boolean(sessionId)} activeSection="applications" />
      <main id="main-content" tabIndex={-1} className="outline-none">
        <div className="mx-auto max-w-[1200px] space-y-8 px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
          <header>
            <Link to="/" className="inline-flex items-center gap-2 text-sm font-semibold text-primary underline-offset-4 hover:underline">
              <ArrowLeft className="size-4" aria-hidden="true" />
              Back to conversation
            </Link>
            <p className="mt-8 text-xs font-semibold uppercase tracking-[0.16em] text-primary">My applications</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Application completion and status</h1>
            <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
              Keep your document checklist and record updates you receive from the official department.
              Sahaayak does not claim that a citizen-reported update is an official status.
            </p>
          </header>

          {!sessionId && <GuestSessionNotice />}
          {applicationsQuery.isPending && sessionId && (
            <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
              Loading your applications…
            </p>
          )}
          {applicationsQuery.error && (
            <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm">
              {toUserMessage(applicationsQuery.error)}
            </p>
          )}
          {sessionId && applicationsQuery.data?.length === 0 && (
            <Card>
              <CardContent className="p-6">
                <p className="font-semibold">No application journeys yet.</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Open a human-verified benefit and choose “Start application assistance” to create one.
                </p>
                <Link to="/" className="mt-4 inline-flex font-semibold text-primary underline-offset-4 hover:underline">
                  Find a benefit
                </Link>
              </CardContent>
            </Card>
          )}
          {applicationsQuery.data && applicationsQuery.data.length > 0 && (
            <div className="grid gap-5 md:grid-cols-2">
              {applicationsQuery.data.map((application) => (
                <ApplicationSummaryCard key={application.id} application={application} />
              ))}
            </div>
          )}
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}

function ApplicationSummaryCard({ application }: { application: ApplicationCase }) {
  const pendingTasks = application.tasks.filter((task) => task.status === "pending").length;
  return (
    <Card className="border-border bg-card">
      <CardHeader className="gap-3 pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Badge variant={application.status === "rejected" ? "warning" : "outline"}>
            {statusLabel(application.status)}
          </Badge>
          <Badge variant={application.readiness_state === "ready" ? "success" : "warning"}>
            {readinessLabel(application.readiness_state)}
          </Badge>
        </div>
        <h2 className="text-xl font-bold leading-snug">{application.benefit_name}</h2>
        <p className="text-sm text-muted-foreground">
          {pendingTasks + " checklist item" + (pendingTasks === 1 ? "" : "s") + " remaining"} · Updated{" "}
          {formatDateTime(application.updated_at)}
        </p>
      </CardHeader>
      <CardContent>
        <Link
          to="/applications/$applicationId"
          params={{ applicationId: application.id }}
          className="inline-flex min-h-11 items-center gap-2 font-semibold text-primary underline-offset-4 hover:underline"
        >
          Open application workspace
          <ExternalLink className="size-4" aria-hidden="true" />
        </Link>
      </CardContent>
    </Card>
  );
}

export function ApplicationDetailPage() {
  const { applicationId } = useParams({ from: "/applications/$applicationId" });
  const sessionId = useGuestSessionStore((state) => state.sessionId);
  const accessToken = useGuestSessionStore((state) => state.accessToken);
  const applicationQuery = useApplicationQuery(sessionId, applicationId, accessToken);
  const updateStatusMutation = useRecordApplicationStatusMutation(
    sessionId,
    applicationId,
    accessToken,
  );
  const updateTaskMutation = useUpdateApplicationTaskMutation(
    sessionId,
    accessToken,
    applicationId,
  );
  const fieldsQuery = useApplicationFieldsQuery(sessionId, applicationId, accessToken);
  const requirementsQuery = useApplicationRequirementsQuery(sessionId, applicationId, accessToken);
  const outcomeQuery = useApplicationOutcomeQuery(sessionId, applicationId, accessToken);
  const updateFieldMutation = useUpdateApplicationFieldMutation(
    sessionId,
    applicationId,
    accessToken,
  );
  const updateRequirementMutation = useUpdateApplicationRequirementMutation(
    sessionId,
    applicationId,
    accessToken,
  );
  const recordOutcomeMutation = useRecordApplicationOutcomeMutation(
    sessionId,
    applicationId,
    accessToken,
  );
  const [status, setStatus] = useState("submitted");
  const [reference, setReference] = useState("");
  const [submissionDate, setSubmissionDate] = useState("");
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState("");
  const navigate = useNavigate();
  const application = applicationQuery.data;

  function submitStatus(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("");
    updateStatusMutation.mutate(
      {
        status,
        submission_date: submissionDate || undefined,
        external_reference: reference.trim() || undefined,
        reason_code: reason.trim() || undefined,
      },
      {
        onSuccess: () => {
          setReference("");
          setReason("");
          setNotice("Your update was saved as citizen-reported evidence.");
        },
        onError: (error) => setNotice(toUserMessage(error)),
      },
    );
  }

  function updateTask(task: ApplicationTask, completed: boolean) {
    updateTaskMutation.mutate(
      { taskId: task.id, status: completed ? "completed" : "pending" },
      { onError: (error) => setNotice(toUserMessage(error)) },
    );
  }

  return (
    <div className="min-h-svh bg-background text-foreground">
      <Topbar sessionId={sessionId} connected={Boolean(sessionId)} activeSection="applications" />
      <main id="main-content" tabIndex={-1} className="outline-none">
        <div className="mx-auto max-w-[1200px] space-y-8 px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
          <header>
            <Link to="/applications" className="inline-flex items-center gap-2 text-sm font-semibold text-primary underline-offset-4 hover:underline">
              <ArrowLeft className="size-4" aria-hidden="true" />
              All applications
            </Link>
          </header>
          {!sessionId && <GuestSessionNotice />}
          {applicationQuery.isPending && sessionId && (
            <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
              Loading the application workspace…
            </p>
          )}
          {applicationQuery.error && (
            <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm">
              {toUserMessage(applicationQuery.error)}
            </p>
          )}
          {application && (
            <>
              <section aria-labelledby="application-title">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{application.benefit_domain}</Badge>
                  <Badge variant={application.status === "rejected" ? "warning" : "success"}>
                    {statusLabel(application.status)}
                  </Badge>
                  <Badge variant={application.readiness_state === "ready" ? "success" : "warning"}>
                    {readinessLabel(application.readiness_state)}
                  </Badge>
                </div>
                <h1 id="application-title" className="mt-4 max-w-3xl text-3xl font-bold tracking-tight sm:text-4xl">
                  {application.benefit_name}
                </h1>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
                  Started {formatDateTime(application.created_at)} · This workspace is private to your guest session.
                </p>
              </section>

              {(application.source_stale || application.benefit_change_state !== "none") && (
                <Card className="border-warning/30 bg-warning/10">
                  <CardContent className="flex items-start gap-3 p-5">
                    <TriangleAlert className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden="true" />
                    <div>
                      <h2 className="font-semibold">
                        {application.benefit_change_state === "application_invalidated"
                          ? "Review this application before continuing"
                          : "The official benefit information has changed"}
                      </h2>
                      <p className="mt-1 text-sm leading-6">
                        {application.source_stale
                          ? "The current public source needs a fresh human verification."
                          : "Your case keeps its original revision; these are the changes in the current record."}
                      </p>
                      {application.benefit_change_items.length > 0 && (
                        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                          {application.benefit_change_items.map((item) => <li key={item}>{item}</li>)}
                        </ul>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
                <ChecklistCard
                  application={application}
                  pending={updateTaskMutation.isPending}
                  onToggle={updateTask}
                />
                <SourceCard application={application} />
              </div>

              <ApplicationRequirementsCard
                requirements={requirementsQuery.data ?? []}
                loading={requirementsQuery.isPending}
                pending={updateRequirementMutation.isPending}
                onStatusChange={(requirement, nextStatus) =>
                  updateRequirementMutation.mutate({
                    requirementKey: requirement.requirement_key,
                    status: nextStatus,
                    expectedCaseRevision: application.revision,
                  })
                }
              />
              <ApplicationFieldsCard
                fields={fieldsQuery.data ?? []}
                loading={fieldsQuery.isPending}
                pending={updateFieldMutation.isPending}
                onSave={(field, value) =>
                  updateFieldMutation.mutate({
                    fieldKey: field.field_key,
                    value,
                    expectedRevision: field.value?.revision,
                  })
                }
              />

              <Button asChild variant="outline">
                <Link
                  to="/applications/$applicationId/pack"
                  params={{ applicationId: application.id }}
                >
                  <Printer className="size-4" aria-hidden="true" />
                  Preview or print preparation pack
                </Link>
              </Button>

              <StatusCard
                application={application}
                status={status}
                reference={reference}
                submissionDate={submissionDate}
                reason={reason}
                setStatus={setStatus}
                setReference={setReference}
                setSubmissionDate={setSubmissionDate}
                setReason={setReason}
                onSubmit={submitStatus}
                pending={updateStatusMutation.isPending}
                notice={notice}
              />
              <Timeline events={application.status_events} />
              {isTerminalStatus(application.status) && (
                <ApplicationOutcomeCard
                  existing={outcomeQuery.data}
                  pending={recordOutcomeMutation.isPending}
                  caseRevision={application.revision}
                  onSubmit={(payload) =>
                    recordOutcomeMutation.mutate({
                      ...payload,
                      expected_case_revision: application.revision,
                    })
                  }
                  notice={recordOutcomeMutation.error ? toUserMessage(recordOutcomeMutation.error) : ""}
                />
              )}
              <Button type="button" variant="outline" onClick={() => void navigate({ to: "/applications" })}>
                Return to applications
              </Button>
            </>
          )}
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}

export function ApplicationPackPage() {
  const { applicationId } = useParams({ from: "/applications/$applicationId/pack" });
  const sessionId = useGuestSessionStore((state) => state.sessionId);
  const accessToken = useGuestSessionStore((state) => state.accessToken);
  const packQuery = useApplicationPackPreviewQuery(sessionId, applicationId, accessToken);
  const navigate = useNavigate();

  function printPack() {
    const html = packQuery.data?.html;
    if (!html) return;
    const printWindow = window.open("", "_blank", "noopener,noreferrer");
    if (!printWindow) return;
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  }

  return (
    <div className="min-h-svh bg-background text-foreground">
      <Topbar sessionId={sessionId} connected={Boolean(sessionId)} activeSection="applications" />
      <main id="main-content" tabIndex={-1} className="outline-none">
        <div className="mx-auto max-w-[1000px] space-y-8 px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
          <header>
            <Link
              to="/applications/$applicationId"
              params={{ applicationId }}
              className="inline-flex items-center gap-2 text-sm font-semibold text-primary underline-offset-4 hover:underline"
            >
              <ArrowLeft className="size-4" aria-hidden="true" />
              Back to application
            </Link>
            <p className="mt-8 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
              Source-backed preparation
            </p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
              Application preparation pack
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              This pack is a private, on-demand checklist summary. It is not a government form or proof that an application was submitted.
            </p>
          </header>
          {!sessionId && <GuestSessionNotice />}
          {packQuery.isPending && sessionId && (
            <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
              Preparing a printable preview…
            </p>
          )}
          {packQuery.error && (
            <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm">
              {toUserMessage(packQuery.error)}
            </p>
          )}
          {packQuery.data && (
            <Card>
              <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold">Preview</h2>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Preview expires {formatDateTime(packQuery.data.expires_at)} · checksum {packQuery.data.content_sha256.slice(0, 12)}…
                  </p>
                </div>
                <Button type="button" onClick={printPack}>
                  <Printer className="size-4" aria-hidden="true" />
                  Print
                </Button>
              </CardHeader>
              <CardContent>
                <iframe
                  title="Sahaayak application preparation pack preview"
                  srcDoc={packQuery.data.html}
                  sandbox=""
                  className="min-h-[720px] w-full rounded-lg border border-border bg-white"
                />
                <p className="mt-3 text-xs text-muted-foreground">
                  The preview is generated without storing a durable document. Close it when you finish printing.
                </p>
              </CardContent>
            </Card>
          )}
          <Button type="button" variant="outline" onClick={() => void navigate({ to: "/applications/$applicationId", params: { applicationId } })}>
            Return to application
          </Button>
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}

function ChecklistCard({
  application,
  pending,
  onToggle,
}: {
  application: ApplicationCase;
  pending: boolean;
  onToggle: (task: ApplicationTask, completed: boolean) => void;
}) {
  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="size-5 text-primary" aria-hidden="true" />
          <h2 className="text-lg font-bold">Your checklist</h2>
        </div>
        <p className="text-sm leading-6 text-muted-foreground">
          These tasks are extracted from the reviewed benefit record. Checking one off is personal progress, not an official submission.
        </p>
      </CardHeader>
      <CardContent>
        {application.readiness_blockers.length > 0 && (
          <div className="mb-4 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm">
            <p className="font-semibold">Before you submit</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {application.readiness_blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
            </ul>
          </div>
        )}
        {application.tasks.length === 0 ? (
          <p className="text-sm text-muted-foreground">No structured tasks were published for this benefit.</p>
        ) : (
          <ul className="space-y-3">
            {application.tasks.map((task) => (
              <li key={task.id} className="flex items-start gap-3 rounded-lg border border-border p-3">
                <input
                  type="checkbox"
                  checked={task.status === "completed"}
                  onChange={(event) => onToggle(task, event.target.checked)}
                  disabled={pending}
                  className="mt-1 size-4 accent-primary"
                  aria-label={(task.status === "completed" ? "Reopen " : "Complete ") + task.title}
                />
                <span className="min-w-0">
                  <span
                    className={
                      "block text-sm font-semibold " +
                      (task.status === "completed" ? "text-muted-foreground line-through" : "")
                    }
                  >
                    {task.title}
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-muted-foreground">{task.description}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function SourceCard({ application }: { application: ApplicationCase }) {
  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex items-center gap-2">
          <FileText className="size-5 text-primary" aria-hidden="true" />
          <h2 className="text-lg font-bold">Official source</h2>
        </div>
        <p className="text-sm leading-6 text-muted-foreground">
          Status is not verified by Sahaayak. Use the official source to confirm deadlines and the next action.
        </p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p><span className="font-semibold">Last verified:</span> {formatDate(application.last_verified_date)}</p>
        <p><span className="font-semibold">Benefit revision:</span> {application.benefit_revision}</p>
        {application.source_document_url && (
          <a
            href={application.source_document_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center gap-2 font-semibold text-primary underline-offset-4 hover:underline"
          >
            {application.source_title || "Open official source"}
            <ExternalLink className="size-4" aria-hidden="true" />
          </a>
        )}
      </CardContent>
    </Card>
  );
}

function ApplicationRequirementsCard({
  requirements,
  loading,
  pending,
  onStatusChange,
}: {
  requirements: ApplicationRequirement[];
  loading: boolean;
  pending: boolean;
  onStatusChange: (requirement: ApplicationRequirement, nextStatus: "ready") => void;
}) {
  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="size-5 text-primary" aria-hidden="true" />
          <h2 className="text-lg font-bold">Requirements and evidence</h2>
        </div>
        <p className="text-sm leading-6 text-muted-foreground">
          These rows preserve what the reviewed benefit requires. Marking a row ready records your progress, not an official document submission.
        </p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p role="status" className="text-sm text-muted-foreground">Loading source requirements…</p>
        ) : requirements.length === 0 ? (
          <p className="text-sm text-muted-foreground">No structured requirements were published for this application.</p>
        ) : (
          <ul className="space-y-3">
            {requirements.map((requirement) => (
              <li key={requirement.requirement_key} className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-border p-3">
                <div className="min-w-0">
                  <p className="font-semibold">{requirement.title}</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">{requirement.description}</p>
                  <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {requirement.status.replaceAll("_", " ")}
                  </p>
                </div>
                {requirement.status === "missing" || requirement.status === "needs_update" ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={pending}
                    onClick={() => onStatusChange(requirement, "ready")}
                  >
                    Mark ready
                  </Button>
                ) : (
                  <Badge variant="success">{requirement.status.replaceAll("_", " ")}</Badge>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ApplicationFieldsCard({
  fields,
  loading,
  pending,
  onSave,
}: {
  fields: ApplicationFieldDefinition[];
  loading: boolean;
  pending: boolean;
  onSave: (field: ApplicationFieldDefinition, value: string) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  useEffect(() => {
    setValues((current) => {
      const next = { ...current };
      for (const field of fields) next[field.field_key] ??= "";
      return next;
    });
  }, [fields]);

  if (!loading && fields.length === 0) return null;
  return (
    <Card>
      <CardHeader className="gap-2">
        <h2 className="text-lg font-bold">Application information</h2>
        <p className="text-sm leading-6 text-muted-foreground">
          Only reviewed fields appear here. Values are encrypted after you confirm them; Sahaayak never shows the stored value again.
        </p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p role="status" className="text-sm text-muted-foreground">Loading reviewed application fields…</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {fields.map((field) => {
              const label = field.label.en ?? Object.values(field.label)[0] ?? field.field_key;
              const help = field.help_text.en ?? Object.values(field.help_text)[0];
              return (
                <div key={field.field_key} className="grid gap-2">
                  <label htmlFor={`application-field-${field.field_key}`} className="text-sm font-semibold">
                    {label}{field.required ? " *" : ""}
                  </label>
                  {help && <p className="text-xs leading-5 text-muted-foreground">{help}</p>}
                  {field.value && (
                    <p className="text-xs text-muted-foreground">Stored value: {field.value.masked_value}</p>
                  )}
                  <div className="flex gap-2">
                    <input
                      id={`application-field-${field.field_key}`}
                      type={field.data_type === "date" ? "date" : "text"}
                      value={values[field.field_key] ?? ""}
                      onChange={(event) => setValues((current) => ({ ...current, [field.field_key]: event.target.value }))}
                      placeholder={field.value ? "Enter a replacement value" : "Enter value"}
                      className="min-h-11 min-w-0 flex-1 rounded-lg border border-border bg-background px-3 text-sm"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      disabled={pending || !(values[field.field_key] ?? "").trim()}
                      onClick={() => onSave(field, values[field.field_key] ?? "")}
                    >
                      Save
                    </Button>
                  </div>
                  {field.source_url && (
                    <a href={field.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-primary underline-offset-4 hover:underline">
                      Field source <ExternalLink className="size-3" aria-hidden="true" />
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ApplicationOutcomeCard({
  existing,
  pending,
  onSubmit,
  notice,
}: {
  existing: { outcome: string; confirmed_at: string; has_comment: boolean } | undefined;
  pending: boolean;
  caseRevision: number;
  onSubmit: (payload: {
    outcome: "received" | "not_received" | "partially_received" | "unknown";
    reason_code?: string;
    free_text?: string;
    satisfaction_score?: number;
    consent_for_evaluation?: boolean;
  }) => void;
  notice: string;
}) {
  const [outcome, setOutcome] = useState<"received" | "not_received" | "partially_received" | "unknown">("received");
  const [comment, setComment] = useState("");
  const [consent, setConsent] = useState(false);
  return (
    <Card>
      <CardHeader className="gap-2">
        <h2 className="text-lg font-bold">What happened after the application?</h2>
        <p className="text-sm leading-6 text-muted-foreground">
          This is optional citizen feedback and is never treated as official department evidence.
        </p>
      </CardHeader>
      <CardContent>
        {existing ? (
          <p className="rounded-lg border border-success/30 bg-success/10 p-4 text-sm">
            You recorded: <strong>{existing.outcome.replaceAll("_", " ")}</strong> · {formatDateTime(existing.confirmed_at)}
            {existing.has_comment ? " · private note saved" : ""}
          </p>
        ) : (
          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              onSubmit({ outcome, free_text: comment.trim() || undefined, consent_for_evaluation: consent });
            }}
          >
            <label className="grid gap-2 text-sm font-semibold">
              Outcome
              <select value={outcome} onChange={(event) => setOutcome(event.target.value as typeof outcome)} className="min-h-11 rounded-lg border border-border bg-background px-3 font-normal">
                <option value="received">Received</option>
                <option value="partially_received">Partially received</option>
                <option value="not_received">Not received</option>
                <option value="unknown">Not sure</option>
              </select>
            </label>
            <label className="grid gap-2 text-sm font-semibold">
              Private note (optional)
              <input value={comment} onChange={(event) => setComment(event.target.value)} maxLength={2000} className="min-h-11 rounded-lg border border-border bg-background px-3 font-normal" />
            </label>
            <label className="flex items-start gap-2 text-sm md:col-span-2">
              <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} className="mt-1 size-4 accent-primary" />
              <span>Allow this outcome to be used in aggregate product evaluation.</span>
            </label>
            <div className="flex items-center gap-3 md:col-span-2">
              <Button type="submit" disabled={pending}>{pending ? "Saving…" : "Save outcome"}</Button>
              {notice && <p role="alert" className="text-sm text-destructive">{notice}</p>}
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

function StatusCard({
  application,
  status,
  reference,
  submissionDate,
  reason,
  setStatus,
  setReference,
  setSubmissionDate,
  setReason,
  onSubmit,
  pending,
  notice,
}: {
  application: ApplicationCase;
  status: string;
  reference: string;
  submissionDate: string;
  reason: string;
  setStatus: (value: string) => void;
  setReference: (value: string) => void;
  setSubmissionDate: (value: string) => void;
  setReason: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  pending: boolean;
  notice: string;
}) {
  const isTerminal = ["delivered", "rejected", "withdrawn"].includes(application.status);
  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex items-center gap-2">
          <TriangleAlert className="size-5 text-warning" aria-hidden="true" />
          <h2 className="text-lg font-bold">Record an update</h2>
        </div>
        <p className="text-sm leading-6 text-muted-foreground">
          Tell Sahaayak what you heard from the department. This is marked citizen-reported until an authorized status adapter verifies it.
        </p>
      </CardHeader>
      <CardContent>
        {isTerminal ? (
          <p className="rounded-lg border border-border bg-muted/40 p-4 text-sm">
            This journey is marked <strong>{statusLabel(application.status)}</strong>. Start a new conversation with a human if the department gives you a correction.
          </p>
        ) : (
          <form className="grid gap-4 md:grid-cols-2" onSubmit={onSubmit}>
            <label className="grid gap-2 text-sm font-semibold">
              New status
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                className="min-h-11 rounded-lg border border-border bg-background px-3 font-normal"
              >
                {STATUS_OPTIONS.map((option) => <option key={option} value={option}>{statusLabel(option)}</option>)}
              </select>
            </label>
            <label className="grid gap-2 text-sm font-semibold">
              Date submitted
              <input
                type="date"
                value={submissionDate}
                onChange={(event) => setSubmissionDate(event.target.value)}
                className="min-h-11 rounded-lg border border-border bg-background px-3 font-normal"
              />
            </label>
            <label className="grid gap-2 text-sm font-semibold md:col-span-2">
              Acknowledgement/reference number (optional)
              <input
                value={reference}
                onChange={(event) => setReference(event.target.value)}
                maxLength={160}
                placeholder="Stored encrypted; only the last four characters are shown"
                className="min-h-11 rounded-lg border border-border bg-background px-3 font-normal"
              />
            </label>
            <label className="grid gap-2 text-sm font-semibold md:col-span-2">
              Note code (optional)
              <input
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                maxLength={80}
                placeholder="For example: missing_document or department_called"
                className="min-h-11 rounded-lg border border-border bg-background px-3 font-normal"
              />
            </label>
            <div className="flex flex-wrap items-center gap-3 md:col-span-2">
              <Button type="submit" disabled={pending}>{pending ? "Saving…" : "Save update"}</Button>
              {notice && <p className="text-sm text-muted-foreground" role="status">{notice}</p>}
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

function Timeline({ events }: { events: ApplicationCase["status_events"] }) {
  return (
    <section aria-labelledby="status-history-title">
      <h2 id="status-history-title" className="text-lg font-bold">Status history</h2>
      <ol className="mt-4 space-y-4">
        {events.map((event) => (
          <li key={event.id} className="relative flex gap-3">
            {event.status === "approved" || event.status === "delivered" ? (
              <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-success" aria-hidden="true" />
            ) : (
              <Circle className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
            )}
            <div className="min-w-0">
              <p className="font-semibold">{statusLabel(event.status)}</p>
              <p className="text-xs text-muted-foreground">
                {formatDateTime(event.occurred_at)} ·{" "}
                {event.provenance === "citizen_reported" ? "Reported by you" : "Recorded by Sahaayak"}
                {event.external_reference_masked ? " · " + event.external_reference_masked : ""}
              </p>
              {event.reason_code && <p className="mt-1 text-sm text-muted-foreground">Note: {event.reason_code}</p>}
              {event.source_url && (
                <a href={event.source_url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-primary underline-offset-4 hover:underline">
                  Source <ExternalLink className="size-3" aria-hidden="true" />
                </a>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
