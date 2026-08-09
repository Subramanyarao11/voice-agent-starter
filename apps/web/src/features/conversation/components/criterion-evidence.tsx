import { CheckCircle2, CircleAlert, CircleX } from "lucide-react";

import type { MatchSummary } from "@/lib/api";

const slotLabels: Record<string, string> = {
  age: "Age",
  annual_family_income: "Annual family income",
  social_category: "Social category",
  gender: "Gender",
  education_level: "Education",
  occupation: "Occupation",
  enrollment_mode: "Study mode",
  state_residency: "State residency",
  disability: "Disability certificate",
  experience_years: "Experience",
  location: "Location",
};

function slotLabel(slot: string): string {
  return slotLabels[slot] ?? slot.replaceAll("_", " ");
}

function criterionStatusLabel(status: MatchSummary["criteria"][number]["status"]): string {
  switch (status) {
    case "pass":
      return "Passed";
    case "fail":
      return "Not met";
    case "unknown":
      return "Needs confirmation";
  }
}

function statusStyles(status: MatchSummary["criteria"][number]["status"]): {
  icon: typeof CheckCircle2;
  iconClass: string;
  textClass: string;
} {
  switch (status) {
    case "pass":
      return { icon: CheckCircle2, iconClass: "text-success", textClass: "text-foreground" };
    case "fail":
      return { icon: CircleX, iconClass: "text-destructive", textClass: "text-foreground" };
    case "unknown":
      return { icon: CircleAlert, iconClass: "text-warning-foreground", textClass: "text-foreground" };
  }
}

export function CriterionEvidence({ match, compact = false }: { match: MatchSummary; compact?: boolean }) {
  if (match.criteria.length === 0 && match.caveats.length === 0) return null;

  return (
    <div className={compact ? "mt-4" : "mt-1"}>
      <h4 className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
        What was checked
      </h4>
      <ul className="mt-2 space-y-2" aria-label={`Eligibility criteria for ${match.benefit_name}`}>
        {match.criteria.map((criterion, index) => {
          const { icon: Icon, iconClass, textClass } = statusStyles(criterion.status);
          const answer = criterion.caller_value?.trim();
          return (
            <li key={`${criterion.slot}-${criterion.requirement}-${index}`} className="flex items-start gap-2 text-xs leading-5">
              <Icon className={`mt-0.5 size-4 shrink-0 ${iconClass}`} aria-hidden="true" />
              <span className={textClass}>
                <span className="font-semibold">{slotLabel(criterion.slot)} · {criterionStatusLabel(criterion.status)}</span>
                <span className="block text-muted-foreground">{criterion.requirement}</span>
                {answer && <span className="block text-muted-foreground">Your answer: {answer}</span>}
                {criterion.status === "unknown" && !answer && (
                  <span className="block text-warning-foreground">No answer recorded yet.</span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
      {match.caveats.length > 0 && (
        <div className="mt-3 rounded-lg border border-warning/50 bg-warning/15 px-3 py-2 text-xs leading-5 text-warning-foreground">
          <span className="font-semibold">Confirm these conditions:</span>{" "}
          {match.caveats.join("; ")}
        </div>
      )}
    </div>
  );
}
