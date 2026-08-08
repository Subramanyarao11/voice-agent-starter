import { Bookmark, BookmarkCheck, CheckCircle2, CircleAlert, CircleX, Columns3 } from "lucide-react";
import { Link } from "@tanstack/react-router";

import type { MatchSummary, TurnResponse } from "@/lib/api";
import { formatConfidence } from "@/lib/utils";
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
  if (matches.length === 0) return null;

  return (
    <section className="space-y-5" aria-labelledby="matches-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.2em] text-acid/75">{t("eligibilityReadout")}</span>
          <h2 id="matches-title" className="mt-2 text-2xl font-extrabold tracking-tight text-paper">{t("whatAgentFound")}</h2>
        </div>
        <span className="text-xs text-paper/40">{t("structuredReasons")}</span>
      </div>
      <p className="max-w-3xl text-sm leading-6 text-paper/55">
        {t("guidanceDisclaimer")}
      </p>
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
    </section>
  );
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
      className="h-full border-paper/10 bg-paper/[0.04] text-paper transition-transform hover:-translate-y-1 hover:border-acid/30"
      aria-labelledby={`match-${match.benefit_id}`}
    >
      <CardContent className="p-5">
        <div className="flex items-center justify-between gap-3">
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-paper/45">{match.domain}</span>
          <div className="flex items-center gap-2">
            {onToggleSaved && (
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="size-8 text-paper/50 hover:text-acid"
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
                className="size-8 text-paper/50 hover:text-blue"
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
        <h3 id={`match-${match.benefit_id}`} className="mt-5 text-lg font-bold leading-snug text-paper">{match.benefit_name}</h3>
        <p className="mt-3 min-h-12 text-sm leading-6 text-paper/60">{match.reasons?.[0] ?? t("noAdditionalReason")}</p>
        <CriterionEvidence match={match} compact />
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-paper/45">
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
            className="mt-4 inline-flex text-xs font-semibold text-acid underline-offset-4 hover:underline"
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
          className="mt-4 inline-flex text-xs font-semibold text-blue underline-offset-4 hover:underline"
        >
          {t("viewDetails")}
        </Link>
        <p className="mt-5 font-mono text-[0.65rem] uppercase tracking-[0.14em] text-paper/35">
          {t("confidence")} · {formatConfidence(match.confidence)}
        </p>
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
