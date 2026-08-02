import type { TurnResponse } from "@/lib/api";
import { labelForSlot } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type TurnInspectorProps = {
  turn: TurnResponse | null;
};

export function TurnInspector({ turn }: TurnInspectorProps) {
  const slots = Object.entries(turn?.slots ?? {});

  return (
    <section aria-label="Last turn details">
      <Card className="border-paper/10 bg-paper/[0.04] text-paper">
        <CardHeader className="flex-row items-center justify-between space-y-0 px-5 pb-4 pt-5 sm:px-7">
          <div>
            <span className="font-mono text-[0.6rem] uppercase tracking-[0.2em] text-acid/75">Turn details</span>
            <CardTitle className="mt-2 text-lg text-paper">Structured, not guessed.</CardTitle>
          </div>
          <Badge variant="outline" className="hidden border-paper/15 text-paper/45 sm:inline-flex">debug readout</Badge>
        </CardHeader>
        <CardContent className="grid gap-px overflow-hidden rounded-xl border border-paper/10 bg-paper/10 p-0 sm:grid-cols-2 lg:grid-cols-5">
          <DataPoint label="intent" value={turn?.intent ?? "—"} />
          <DataPoint label="next question" value={labelForSlot(turn?.pending_slot)} />
          <DataPoint
            label="known slots"
            value={slots.length > 0 ? slots.map(([key, value]) => `${labelForSlot(key)}: ${String(value)}`).join(" · ") : "none yet"}
            className="sm:col-span-2 lg:col-span-1"
          />
          <DataPoint label="matches" value={String(turn?.matches?.length ?? 0)} />
          <DataPoint
            label="handoff"
            value={turn?.needs_escalation ? turn.escalation_reason ?? "needed" : "not needed"}
            tone={turn?.needs_escalation ? "warning" : "success"}
          />
        </CardContent>
      </Card>
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
    <div className={`min-h-20 bg-ink-soft px-4 py-3 ${className ?? ""}`}>
      <span className="block font-mono text-[0.58rem] uppercase tracking-[0.15em] text-paper/35">{label}</span>
      <strong className={`mt-2 block break-words text-sm font-semibold ${tone === "warning" ? "text-orange" : tone === "success" ? "text-acid" : "text-paper/80"}`}>
        {value}
      </strong>
    </div>
  );
}
