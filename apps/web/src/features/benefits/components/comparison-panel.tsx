import type { ReactNode } from "react";

import { useQueries } from "@tanstack/react-query";
import { Columns3, ExternalLink, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useCompareStore } from "@/features/benefits/compare-store";
import { benefitDetailQueryKey } from "@/features/benefits/queries";
import { getBenefit, type BenefitDetail } from "@/lib/api";

function renderValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value == null || value === "") return "Not stated";
  return String(value);
}

function criteria(detail: BenefitDetail): string {
  const values = Object.entries(detail.eligibility_initial).map(
    ([key, value]) => `${key.replaceAll("_", " ")}: ${renderValue(value)}`,
  );
  return values.length ? values.join(" · ") : "No structured criteria extracted";
}

export function ComparisonPanel() {
  const benefitIds = useCompareStore((state) => state.benefitIds);
  const remove = useCompareStore((state) => state.remove);
  const clear = useCompareStore((state) => state.clear);
  const queries = useQueries({
    queries: benefitIds.map((benefitId) => ({
      queryKey: benefitDetailQueryKey(benefitId),
      queryFn: () => getBenefit(benefitId),
      staleTime: 5 * 60 * 1000,
    })),
  });
  const details = queries
    .map((query) => query.data)
    .filter((detail): detail is BenefitDetail => Boolean(detail));

  if (!benefitIds.length) return null;

  return (
    <section className="space-y-5" aria-labelledby="comparison-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.2em] text-acid/75">Decision aid</span>
          <h2 id="comparison-title" className="mt-2 flex items-center gap-2 text-2xl font-extrabold tracking-tight text-paper">
            <Columns3 className="size-5 text-acid" aria-hidden="true" />
            Compare benefits
          </h2>
        </div>
        <Button type="button" size="sm" variant="ghost" onClick={clear}>Clear comparison</Button>
      </div>
      <p className="text-sm leading-6 text-paper/55">Comparison highlights public information. It does not change the structured eligibility decision.</p>
      <Card className="border-paper/10 bg-paper/[0.04] text-paper">
        <CardContent className="overflow-x-auto p-0">
          <table className="w-full min-w-[900px] text-left text-sm">
            <caption className="sr-only">Selected benefits compared by public details</caption>
            <thead className="border-b border-paper/10">
              <tr>
                <th className="w-44 px-4 py-4 text-xs uppercase tracking-[0.12em] text-paper/40">Field</th>
                {details.map((detail) => (
                  <th key={detail.id} className="min-w-[230px] px-4 py-4 align-top">
                    <div className="flex items-start justify-between gap-3">
                      <span className="font-bold leading-5">{detail.name}</span>
                      <Button type="button" size="icon" variant="ghost" className="size-7 shrink-0 text-paper/50 hover:text-orange" aria-label={`Remove ${detail.name} from comparison`} onClick={() => remove(detail.id)}>
                        <X className="size-3.5" aria-hidden="true" />
                      </Button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <ComparisonRow label="Type" values={details.map((detail) => <Badge key={detail.id} variant="outline">{detail.domain}</Badge>)} />
              <ComparisonRow label="Source status" values={details.map((detail) => <Badge key={detail.id} variant={detail.verification_status === "human_verified" ? "success" : "warning"}>{detail.verification_status.replaceAll("_", " ")}</Badge>)} />
              <ComparisonRow label="What it provides" values={details.map((detail) => detail.benefits_text || detail.description || "Not stated")} />
              <ComparisonRow label="Eligibility" values={details.map(criteria)} />
              <ComparisonRow label="Documents" values={details.map((detail) => detail.documents_required.length ? detail.documents_required.join(", ") : "See official notification")} />
              <ComparisonRow label="Deadline / validity" values={details.map((detail) => detail.valid_until || (detail.domain === "job" ? "Not stated" : "Ongoing or not stated"))} />
              <ComparisonRow label="Application" values={details.map((detail) => detail.application_process || "Follow the official source")} />
              <ComparisonRow label="Official source" values={details.map((detail) => detail.source_document_url ? <a key={detail.id} className="inline-flex items-center gap-1 font-semibold text-acid underline-offset-4 hover:underline" href={detail.source_document_url} target="_blank" rel="noopener noreferrer">Open source <ExternalLink className="size-3" aria-hidden="true" /></a> : "Not stated")} />
            </tbody>
          </table>
        </CardContent>
      </Card>
      {queries.some((query) => query.isError) && <p className="text-sm text-orange" role="alert">One selected benefit could not be loaded. Remove it and try again.</p>}
    </section>
  );
}

function ComparisonRow({ label, values }: { label: string; values: ReactNode[] }) {
  return <tr className="border-b border-paper/5 align-top last:border-0"><th scope="row" className="px-4 py-4 text-xs font-semibold uppercase tracking-[0.1em] text-paper/40">{label}</th>{values.map((value, index) => <td key={`${label}-${index}`} className="px-4 py-4 leading-6 text-paper/70">{value}</td>)}</tr>;
}
