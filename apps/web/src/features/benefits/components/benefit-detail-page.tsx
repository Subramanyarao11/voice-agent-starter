import { useState, type ReactNode } from "react";

import { Link, useNavigate, useParams } from "@tanstack/react-router";
import {
  ArrowLeft,
  BriefcaseBusiness,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  ExternalLink,
  FileText,
  MapPin,
  Share2,
  TriangleAlert,
} from "lucide-react";

import { PublicFooter, Topbar } from "@/components/app/topbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useBenefitDetailQuery } from "@/features/benefits/queries";
import { useCreateApplicationMutation } from "@/features/applications/queries";
import { ReportIssuePanel } from "@/features/benefits/components/report-issue-panel";
import { CriterionEvidence } from "@/features/conversation/components/criterion-evidence";
import { useConversationStore } from "@/features/conversation/store";
import { useGuestSessionStore } from "@/features/session/store";
import type { BenefitDetail } from "@/lib/api";
import { toUserMessage } from "@/lib/api";

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function safeNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "Not stated";
  const parsed = new Date(value + "T00:00:00");
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function verificationLabel(status: BenefitDetail["verification_status"]): string {
  switch (status) {
    case "human_verified":
      return "Human-verified source";
    case "machine_reviewed":
      return "AI reviewed · awaiting human approval";
    case "machine_structured":
      return "Machine structured · awaiting review";
    case "needs_review":
      return "Needs human review";
    case "stale":
      return "Source may be out of date";
    default:
      return "Illustrative demo data";
  }
}

function formatCriterion(key: string, value: unknown): string {
  const labels: Record<string, string> = {
    age_min: "Minimum age",
    age_max: "Maximum age",
    max_annual_family_income_inr: "Maximum annual family income",
    category: "Categories",
    gender: "Gender",
    occupation: "Occupation",
    education_level: "Education",
    min_education_level: "Minimum education",
    enrollment_mode: "Study mode",
    state_residency_required: "State residency required",
    disability_required: "Disability certificate required",
    min_experience_years: "Minimum experience",
    locations: "Locations",
    exclusions: "Important caveat",
  };
  const label = labels[key] ?? key.replaceAll("_", " ");
  const rendered = Array.isArray(value)
    ? value.join(", ")
    : typeof value === "boolean"
      ? value
        ? "Yes"
        : "No"
      : String(value);
  return label + ": " + rendered;
}

function isExpired(value: string | null): boolean {
  if (!value) return false;
  const today = new Date();
  const deadline = new Date(value + "T23:59:59");
  return !Number.isNaN(deadline.getTime()) && deadline < today;
}

export function BenefitDetailPage() {
  const { benefitId } = useParams({ from: "/benefits/$benefitId" });
  const detailQuery = useBenefitDetailQuery(benefitId);
  const sessionId = useGuestSessionStore((state) => state.sessionId);
  const accessToken = useGuestSessionStore((state) => state.accessToken);
  const createApplicationMutation = useCreateApplicationMutation(sessionId, accessToken);
  const navigate = useNavigate();
  const languageCode = useConversationStore((state) => state.languageCode);
  const lastTurn = useConversationStore((state) => state.lastTurn);
  const [shareNotice, setShareNotice] = useState("");
  const [applicationNotice, setApplicationNotice] = useState("");

  const currentMatch = lastTurn?.matches.find((match) => match.benefit_id === benefitId);
  const detail = detailQuery.data;
  const job = detail?.domain === "job" ? detail.job_metadata : {};
  const deadline = safeText(job?.application_deadline) || detail?.valid_until || null;
  const expired = isExpired(deadline);

  async function sharePage() {
    const shareData = { title: detail?.name ?? "Sahaayak benefit", url: window.location.href };
    try {
      if (navigator.share) {
        await navigator.share(shareData);
        setShareNotice("Share sheet opened.");
      } else {
        await navigator.clipboard.writeText(window.location.href);
        setShareNotice("Link copied.");
      }
    } catch {
      setShareNotice("Sharing was cancelled.");
    }
  }

  function startApplicationAssistance() {
    if (!detail || !sessionId || !accessToken) {
      setApplicationNotice("Start a guest session from the home page before creating a private checklist.");
      return;
    }
    setApplicationNotice("");
    createApplicationMutation.mutate(
      { benefit_id: detail.id, application_channel: "official_portal" },
      {
        onSuccess: (application) =>
          void navigate({
            to: "/applications/$applicationId",
            params: { applicationId: application.id },
          }),
        onError: (error) => setApplicationNotice(toUserMessage(error)),
      },
    );
  }

  return (
    <div className="min-h-svh bg-background text-foreground">
      <Topbar sessionId={sessionId} connected={Boolean(sessionId)} currentLanguage={languageCode} />
      <main id="main-content" tabIndex={-1} className="outline-none" aria-labelledby="benefit-title">
        <div className="mx-auto max-w-[1200px] px-4 py-10 sm:px-6 sm:py-14 lg:px-8 lg:py-16">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm font-semibold text-blue underline-offset-4 hover:underline"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Back to conversation
        </Link>

        {detailQuery.isPending && (
          <p className="mt-12 text-paper/65" role="status" aria-live="polite">
            Loading the source-backed details…
          </p>
        )}

        {detailQuery.error && (
          <Card className="mt-12 border-orange/30 bg-orange/10 text-paper">
            <CardContent className="p-6">
              <p className="flex items-start gap-3 text-sm leading-6">
                <TriangleAlert className="mt-0.5 size-5 shrink-0 text-orange" aria-hidden="true" />
                {toUserMessage(detailQuery.error)}
              </p>
            </CardContent>
          </Card>
        )}

        {detail && (
          <>
            <header className="mt-10">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="border-acid/30 text-acid">
                  {detail.domain}
                </Badge>
                <Badge
                  variant={detail.verification_status === "human_verified" ? "success" : "warning"}
                >
                  {verificationLabel(detail.verification_status)}
                </Badge>
                {expired && <Badge variant="warning">Application window closed</Badge>}
              </div>
              <div className="mt-5 flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h1 id="benefit-title" className="max-w-3xl text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
                    {detail.name}
                  </h1>
                  <p className="mt-4 max-w-3xl text-base leading-7 text-paper/65">{detail.description}</p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
                  {detail.verification_status === "human_verified" && (
                    <Button
                      type="button"
                      onClick={startApplicationAssistance}
                      disabled={createApplicationMutation.isPending}
                    >
                      <ClipboardList className="size-4" aria-hidden="true" />
                      {createApplicationMutation.isPending
                        ? "Opening…"
                        : "Start application assistance"}
                    </Button>
                  )}
                  <Button type="button" variant="outline" onClick={sharePage}>
                    <Share2 className="size-4" aria-hidden="true" />
                    Share
                  </Button>
                </div>
              </div>
              {shareNotice && <p className="mt-2 text-xs text-acid" role="status">{shareNotice}</p>}
              {applicationNotice && (
                <p className="mt-2 text-xs text-orange" role="status">
                  {applicationNotice}
                </p>
              )}
            </header>

            {currentMatch && (
              <Card className="mt-8 border-blue/25 bg-blue/[0.08] text-paper">
                <CardHeader className="gap-3 pb-3">
                  <div className="flex items-center gap-2">
                    {currentMatch.verdict === "eligible" ? (
                      <CheckCircle2 className="size-5 text-acid" aria-hidden="true" />
                    ) : (
                      <TriangleAlert className="size-5 text-orange" aria-hidden="true" />
                    )}
                    <h2 className="text-lg font-extrabold">What your latest answers indicate</h2>
                  </div>
                  <p className="text-sm leading-6 text-paper/65">
                    This is guidance from the structured matcher, not an official government decision.
                  </p>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Badge variant={currentMatch.verdict === "eligible" ? "success" : "warning"}>
                    {currentMatch.verdict.replaceAll("_", " ")}
                  </Badge>
                  {currentMatch.reasons.length > 0 && (
                    <ul className="list-disc space-y-1 pl-5 text-sm leading-6 text-paper/75">
                      {currentMatch.reasons.map((reason) => <li key={reason}>{reason}</li>)}
                    </ul>
                  )}
                  <CriterionEvidence match={currentMatch} />
                  <p className="text-xs leading-5 text-paper/50">
                    {currentMatch.verdict === "eligible"
                      ? "Your answers match the conditions checked above. Confirm the official source before applying."
                      : currentMatch.verdict === "not_eligible"
                        ? "At least one confirmed answer does not meet a condition above. This is guidance, not an official decision."
                        : "Some conditions still need information or source confirmation before eligibility can be assessed."}
                  </p>
                </CardContent>
              </Card>
            )}

            <div className="mt-8 grid gap-5 md:grid-cols-2">
              <DetailSection
                title={detail.domain === "job" ? "Posting overview" : "What this provides"}
                icon={<ClipboardList className="size-4" aria-hidden="true" />}
              >
                <p className="text-sm leading-7 text-paper/75">
                  {detail.benefits_text || "The notification does not provide a short benefit summary."}
                </p>
                {detail.domain === "job" && (
                  <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
                    <Definition label="Employer" value={safeText(job?.employer) || "UPSC notification"} />
                    <Definition label="Vacancies" value={safeNumber(job?.vacancy_count)?.toString() ?? "See notification"} />
                    <Definition label="Employment type" value={safeText(job?.employment_type) || "See notification"} />
                    <Definition label="Location" value={safeText(job?.headquarters) || "See notification"} />
                  </dl>
                )}
              </DetailSection>

              <DetailSection title="Dates and freshness" icon={<CalendarDays className="size-4" aria-hidden="true" />}>
                <dl className="grid gap-3 text-sm">
                  {detail.domain === "job" && <Definition label="Application deadline" value={formatDate(deadline)} />}
                  <Definition label="Last checked" value={formatDate(detail.last_verified_date)} />
                  <Definition label="Valid from" value={formatDate(detail.valid_from)} />
                  <Definition label="Source status" value={verificationLabel(detail.verification_status)} />
                </dl>
              </DetailSection>
            </div>

            <div className="mt-5 grid gap-5 md:grid-cols-2">
              <DetailSection title="Who may qualify" icon={<CheckCircle2 className="size-4" aria-hidden="true" />}>
                {Object.keys(detail.eligibility_initial).length > 0 ? (
                  <ul className="space-y-2 text-sm leading-6 text-paper/75">
                    {Object.entries(detail.eligibility_initial).map(([key, value]) => (
                      <li key={key}>{formatCriterion(key, value)}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm leading-6 text-paper/65">
                    No machine-checkable criteria were extracted. Please read the notification or ask a person.
                  </p>
                )}
              </DetailSection>

              <DetailSection title="Documents and next step" icon={<FileText className="size-4" aria-hidden="true" />}>
                {detail.documents_required.length > 0 ? (
                  <ul className="list-disc space-y-1 pl-5 text-sm leading-6 text-paper/75">
                    {detail.documents_required.map((document) => <li key={document}>{document}</li>)}
                  </ul>
                ) : (
                  <p className="text-sm leading-6 text-paper/65">
                    The document list must be confirmed in the official notification.
                  </p>
                )}
                <p className="mt-5 border-t border-paper/10 pt-4 text-sm leading-7 text-paper/75">
                  {detail.application_process || "Follow the official source for application instructions."}
                </p>
              </DetailSection>
            </div>

            <Card className="mt-5 border-paper/10 bg-paper/[0.04] text-paper">
              <CardHeader className="gap-2 pb-3">
                <div className="flex items-center gap-2">
                  {detail.domain === "job" ? (
                    <BriefcaseBusiness className="size-4 text-acid" aria-hidden="true" />
                  ) : (
                    <MapPin className="size-4 text-acid" aria-hidden="true" />
                  )}
                  <h2 className="text-lg font-extrabold">Official source</h2>
                </div>
                <p className="text-sm leading-6 text-paper/55">
                  Always check the original notification before sharing documents or paying an application fee.
                </p>
              </CardHeader>
              <CardContent>
                {detail.source_excerpt && (
                  <details className="rounded-xl border border-paper/10 bg-ink/30">
                    <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-paper/75">
                      Show extracted supporting excerpt
                    </summary>
                    <p className="border-t border-paper/10 px-4 py-4 text-xs leading-6 text-paper/60">
                      {detail.source_excerpt}
                    </p>
                  </details>
                )}
                {detail.source_document_url && (
                  <a
                    className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-acid underline-offset-4 hover:underline"
                    href={detail.source_document_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {detail.source_title || "Open official source"}
                    <ExternalLink className="size-4" aria-hidden="true" />
                  </a>
                )}
              </CardContent>
            </Card>
            <ReportIssuePanel benefitId={benefitId} accessToken={accessToken} />
          </>
        )}
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}

function DetailSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card className="border-paper/10 bg-paper/[0.04] text-paper">
      <CardHeader className="flex-row items-center gap-2 pb-3">
        <span className="text-acid">{icon}</span>
        <h2 className="text-lg font-extrabold">{title}</h2>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function Definition({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-[0.12em] text-paper/40">{label}</dt>
      <dd className="mt-1 text-paper/80">{value}</dd>
    </div>
  );
}
