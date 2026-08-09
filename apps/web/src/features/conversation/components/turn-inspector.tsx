import type { TurnResponse } from "@/lib/api";
import { labelForSlot } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { useUi } from "@/features/i18n/ui-provider";

type TurnInspectorProps = {
  turn: TurnResponse | null;
};

export function TurnInspector({ turn }: TurnInspectorProps) {
  const { t } = useUi();
  const slots = Object.entries(turn?.slots ?? {});
  if (!turn) return null;

  return (
    <section aria-labelledby="turn-summary-title">
      <details className="group rounded-lg border border-border bg-muted/25 text-foreground">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 outline-none marker:hidden sm:px-7">
          <div>
            <span className="font-mono text-[0.6rem] uppercase tracking-[0.2em] text-primary">{t("transparency")}</span>
            <h2 id="turn-summary-title" className="mt-1 text-base font-bold text-foreground">{t("conversationDetails")}</h2>
          </div>
          <Badge variant="outline" className="border-border text-muted-foreground">{t("transparency")}</Badge>
        </summary>
        <div className="grid gap-px overflow-hidden border-t border-border bg-border sm:grid-cols-2 lg:grid-cols-5">
          <DataPoint label="intent" value={turn.intent || "—"} />
          <DataPoint label="next question" value={labelForSlot(turn.pending_slot)} />
          <DataPoint
            label="known slots"
            value={slots.length > 0 ? slots.map(([key, value]) => `${labelForSlot(key)}: ${String(value)}`).join(" · ") : "none yet"}
            className="sm:col-span-2 lg:col-span-1"
          />
          <DataPoint label="matches" value={String(turn.matches.length)} />
          <DataPoint
            label="handoff"
            value={turn.needs_escalation ? turn.escalation_reason ?? "needed" : "not needed"}
            tone={turn.needs_escalation ? "warning" : "success"}
          />
        </div>
      </details>
    </section>
  );
}

function DataPoint({
  label,
  value,
  className,
  tone,
}: {
  label: string;
  value: string;
  className?: string;
  tone?: "success" | "warning";
}) {
  return (
    <div className={`min-h-20 bg-card px-4 py-3 ${className ?? ""}`}>
      <span className="block font-mono text-[0.58rem] uppercase tracking-[0.15em] text-muted-foreground">{label}</span>
      <strong className={`mt-2 block break-words text-sm font-semibold ${tone === "warning" ? "text-destructive" : tone === "success" ? "text-success" : "text-foreground"}`}>
        {value}
      </strong>
    </div>
  );
}
