import { Bookmark, BookmarkCheck, CheckCircle2, CircleAlert, CircleX, Columns3 } from "lucide-react";
import { Link } from "@tanstack/react-router";

import type { MatchSummary, TurnResponse } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CriterionEvidence } from "@/features/conversation/components/criterion-evidence";
import { useUi } from "@/features/i18n/ui-provider";
import type { UiTranslator } from "@/lib/i18n";

type MatchesPanelProps = {
  turn: TurnResponse | null;
  savedBenefitIds?: ReadonlySet<string>;
  onToggleSaved?: (benefitId: string, saved: boolean) => void;
  comparedBenefitIds?: ReadonlySet<string>;
  onToggleCompare?: (benefitId: string, compared: boolean) => void;
};

export function MatchesPanel({ turn, savedBenefitIds = new Set(), onToggleSaved, comparedBenefitIds = new Set(), onToggleCompare }: MatchesPanelProps) {
  const { t } = useUi();
  const matches = turn?.matches ?? [];
  if (!turn) return null;

  const hasClearMatch = !turn.needs_escalation && matches.some(isClearMatch);
  const needsMoreInformation = Boolean(turn.pending_slot);

  return (
    <section className="space-y-5" aria-labelledby="matches-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.2em] text-primary">{t("eligibilityReadout")}</span>
          <h2 id="matches-title" className="mt-2 text-2xl font-extrabold tracking-tight text-foreground">
            {hasClearMatch ? t("whatAgentFound") : matches.length > 0 ? t("possibleOptions") : t("noClearMatchTitle")}
          </h2>
        </div>
        <span className="max-w-xs text-right text-xs text-muted-foreground">{t("structuredReasons")}</span>
      </div>
      <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
        {hasClearMatch ? t("guidanceDisclaimer") : matches.length > 0 ? t("possibleOptionsDescription") : t("noClearMatchDescription")}
      </p>
      {!hasClearMatch && (
        <Card className="border-warning/45 bg-warning/10 text-warning-foreground" role="status">
          <CardContent className="p-4 sm:p-5">
            <p className="font-semibold">
              {needsMoreInformation ? t("resultNeedsMoreInfo") : t("noClearMatchTitle")}
            </p>
            <p className="mt-1 text-sm leading-6 opacity-90">
              {needsMoreInformation ? t("resultNeedsMoreInfoDescription") : t("noClearMatchDescription")}
            </p>
          </CardContent>
        </Card>
      )}
      {matches.length > 0 && (
        <ul className="grid list-none gap-4 p-0 md:grid-cols-2 lg:grid-cols-3">
          {matches.map((match) => (
            <li key={match.benefit_id}>
              <MatchCard
                match={match}
                saved={savedBenefitIds.has(match.benefit_id)}
                onToggleSaved={onToggleSaved}
                compared={comparedBenefitIds.has(match.benefit_id)}
                onToggleCompare={onToggleCompare}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function isClearMatch(match: MatchSummary): boolean {
  const verdict = match.verdict.trim().toLowerCase();
  return verdict === "eligible" || (verdict.includes("eligible") && !verdict.includes("not"));
}

function MatchCard({
  match,
  saved,
  onToggleSaved,
  compared,
  onToggleCompare,
}: {
  match: MatchSummary;
  saved: boolean;
  onToggleSaved?: (benefitId: string, saved: boolean) => void;
  compared: boolean;
  onToggleCompare?: (benefitId: string, compared: boolean) => void;
}) {
  const { t } = useUi();
  const verdict = match.verdict.toLowerCase();
  const isEligible = verdict.includes("eligible") && !verdict.includes("not");
  const isNotEligible = verdict.includes("not") || verdict.includes("ineligible");
  const Icon = isEligible ? CheckCircle2 : isNotEligible ? CircleX : CircleAlert;
  const verificationLabel = verificationLabelFor(match.verification_status, t);
  const sourceUrl = match.source_document_url.trim();

  return (
    <Card
      className="h-full border-border bg-card text-card-foreground transition-colors hover:border-primary/45"
      aria-labelledby={`match-${match.benefit_id}`}
    >
      <CardContent className="p-5">
        <div className="flex items-center justify-between gap-3">
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">{match.domain}</span>
          <div className="flex items-center gap-2">
            {onToggleSaved && (
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="size-8 text-muted-foreground hover:text-primary"
                aria-pressed={saved}
                aria-label={`${saved ? "Remove" : "Save"} ${match.benefit_name}`}
                onClick={() => onToggleSaved(match.benefit_id, saved)}
              >
                {saved ? <BookmarkCheck className="size-4" aria-hidden="true" /> : <Bookmark className="size-4" aria-hidden="true" />}
              </Button>
            )}
            {onToggleCompare && (
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="size-8 text-muted-foreground hover:text-info"
                aria-pressed={compared}
                aria-label={`${compared ? "Remove" : "Add"} ${match.benefit_name} ${compared ? "from" : "to"} comparison`}
                onClick={() => onToggleCompare(match.benefit_id, compared)}
              >
                <Columns3 className="size-4" aria-hidden="true" />
              </Button>
            )}
            <Badge variant={isEligible ? "success" : isNotEligible ? "warning" : "secondary"} className="gap-1.5">
              <Icon className="size-3" aria-hidden="true" />
              {match.verdict.replaceAll("_", " ")}
            </Badge>
          </div>
        </div>
        <h3 id={`match-${match.benefit_id}`} className="mt-5 text-lg font-bold leading-snug text-foreground">{match.benefit_name}</h3>
        <p className="mt-3 min-h-12 text-sm leading-6 text-muted-foreground">{match.reasons?.[0] ?? t("noAdditionalReason")}</p>
        <CriterionEvidence match={match} compact />
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant={match.verification_status === "human_verified" ? "success" : "warning"}>
            {verificationLabel}
          </Badge>
          {match.source_title && <span>{match.source_title}</span>}
          {match.verification_status === "human_verified" && match.last_verified_date && (
            <span>verified {match.last_verified_date}</span>
          )}
        </div>
        {sourceUrl && (
          <a
            className="mt-4 inline-flex text-xs font-semibold text-primary underline-offset-4 hover:underline"
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Open the official source for ${match.benefit_name}`}
          >
            {t("openSource")}
          </a>
        )}
        <Link
          to="/benefits/$benefitId"
          params={{ benefitId: match.benefit_id }}
          className="mt-4 inline-flex text-xs font-semibold text-info underline-offset-4 hover:underline"
        >
          {t("viewDetails")}
        </Link>
      </CardContent>
    </Card>
  );
}

function verificationLabelFor(status: MatchSummary["verification_status"], t: UiTranslator): string {
  switch (status) {
    case "human_verified":
      return t("verifiedSource");
    case "machine_reviewed":
      return t("aiReviewedAwaitingHuman");
    case "machine_structured":
      return t("machineStructuredAwaitingReview");
    case "needs_review":
      return t("needsHumanReview");
    case "stale":
      return t("sourceMayBeOutOfDate");
    case "illustrative":
      return t("illustrativeDemo");
  }
}
