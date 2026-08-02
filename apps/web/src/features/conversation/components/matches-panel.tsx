import { CheckCircle2, CircleAlert, CircleX } from "lucide-react";

import type { MatchSummary, TurnResponse } from "@/lib/api";
import { formatConfidence } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

type MatchesPanelProps = {
  turn: TurnResponse | null;
};

export function MatchesPanel({ turn }: MatchesPanelProps) {
  const matches = turn?.matches ?? [];
  if (matches.length === 0) return null;

  return (
    <section className="space-y-5" aria-label="Eligibility matches">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.2em] text-acid/75">Eligibility readout</span>
          <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-paper">What the agent found</h2>
        </div>
        <span className="text-xs text-paper/40">Reasons come from structured criteria.</span>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {matches.map((match) => (
          <MatchCard match={match} key={match.benefit_id} />
        ))}
      </div>
    </section>
  );
}

function MatchCard({ match }: { match: MatchSummary }) {
  const verdict = match.verdict.toLowerCase();
  const isEligible = verdict.includes("eligible") && !verdict.includes("not");
  const isNotEligible = verdict.includes("not") || verdict.includes("ineligible");
  const Icon = isEligible ? CheckCircle2 : isNotEligible ? CircleX : CircleAlert;

  return (
    <Card className="border-paper/10 bg-paper/[0.04] text-paper transition-transform hover:-translate-y-1 hover:border-acid/30">
      <CardContent className="p-5">
        <div className="flex items-center justify-between gap-3">
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-paper/45">{match.domain}</span>
          <Badge variant={isEligible ? "success" : isNotEligible ? "warning" : "secondary"} className="gap-1.5">
            <Icon className="size-3" />
            {match.verdict.replaceAll("_", " ")}
          </Badge>
        </div>
        <h3 className="mt-5 text-lg font-bold leading-snug text-paper">{match.benefit_name}</h3>
        <p className="mt-3 min-h-12 text-sm leading-6 text-paper/60">{match.reasons?.[0] ?? "No additional reason was returned."}</p>
        <p className="mt-5 font-mono text-[0.65rem] uppercase tracking-[0.14em] text-paper/35">
          confidence · {formatConfidence(match.confidence)}
        </p>
      </CardContent>
    </Card>
  );
}
