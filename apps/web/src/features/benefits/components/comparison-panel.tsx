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
          <h2 id="comparison-title" className="mt-2 flex items-center gap-2 text-2xl font-extrabold tracking-tight text-foreground">
            <Columns3 className="size-5 text-primary" aria-hidden="true" />
            Compare benefits
          </h2>
        </div>
        <Button type="button" size="sm" variant="ghost" onClick={clear}>Clear comparison</Button>
      </div>
      <p className="text-sm leading-6 text-muted-foreground">Comparison highlights public information. It does not change the structured eligibility decision.</p>
      <Card className="border-border bg-card text-card-foreground">
        <CardContent className="p-4 sm:p-0">
          {queries.some((query) => query.isPending) && details.length === 0 && (
            <p className="text-sm text-muted-foreground" role="status">Loading selected benefits…</p>
          )}
          <div className="space-y-3 sm:hidden">
            {details.map((detail) => <MobileComparisonCard key={detail.id} detail={detail} onRemove={() => remove(detail.id)} />)}
          </div>
          <div className="hidden overflow-x-auto sm:block">
          <table className="w-full min-w-[760px] text-left text-sm">
            <caption className="sr-only">Selected benefits compared by public details</caption>
            <thead className="border-b border-border">
              <tr>
                <th className="w-44 px-4 py-4 text-xs uppercase tracking-[0.12em] text-paper/40">Field</th>
                {details.map((detail) => (
                  <th key={detail.id} className="min-w-[230px] px-4 py-4 align-top">
                    <div className="flex items-start justify-between gap-3">
                      <span className="font-bold leading-5 text-foreground">{detail.name}</span>
                      <Button type="button" size="icon" variant="ghost" className="size-7 shrink-0 text-muted-foreground hover:text-destructive" aria-label={`Remove ${detail.name} from comparison`} onClick={() => remove(detail.id)}>
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
              <ComparisonRow label="Official source" values={details.map((detail) => {
                const sourceUrl = safeExternalUrl(detail.source_document_url);
                return sourceUrl ? <a key={detail.id} className="inline-flex items-center gap-1 font-semibold text-primary underline-offset-4 hover:underline" href={sourceUrl} target="_blank" rel="noopener noreferrer">Open source <ExternalLink className="size-3" aria-hidden="true" /></a> : "Not stated";
              })} />
            </tbody>
          </table>
          </div>
        </CardContent>
      </Card>
      {queries.some((query) => query.isError) && <p className="text-sm text-destructive" role="alert">One selected benefit could not be loaded. Remove it and try again.</p>}
    </section>
  );
}

function ComparisonRow({ label, values }: { label: string; values: ReactNode[] }) {
  return <tr className="border-b border-border align-top last:border-0"><th scope="row" className="px-4 py-4 text-xs font-semibold uppercase tracking-[0.1em] text-muted-foreground">{label}</th>{values.map((value, index) => <td key={`${label}-${index}`} className="px-4 py-4 leading-6 text-muted-foreground">{value}</td>)}</tr>;
}

function safeExternalUrl(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

function MobileComparisonCard({ detail, onRemove }: { detail: BenefitDetail; onRemove: () => void }) {
  const sourceUrl = safeExternalUrl(detail.source_document_url);
  const fields: Array<[string, ReactNode]> = [
    ["Type", <Badge key="type" variant="outline">{detail.domain}</Badge>],
    ["Source status", <Badge key="status" variant={detail.verification_status === "human_verified" ? "success" : "warning"}>{detail.verification_status.replaceAll("_", " ")}</Badge>],
    ["What it provides", detail.benefits_text || detail.description || "Not stated"],
    ["Eligibility", criteria(detail)],
    ["Documents", detail.documents_required.length ? detail.documents_required.join(", ") : "See official notification"],
    ["Deadline / validity", detail.valid_until || (detail.domain === "job" ? "Not stated" : "Ongoing or not stated")],
    ["Application", detail.application_process || "Follow the official source"],
    ["Official source", sourceUrl ? <a key="source" className="inline-flex items-center gap-1 font-semibold text-primary underline-offset-4 hover:underline" href={sourceUrl} target="_blank" rel="noopener noreferrer">Open source <ExternalLink className="size-3" aria-hidden="true" /></a> : "Not stated"],
  ];

  return (
    <article className="rounded-lg border border-border bg-muted/25 p-4">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-bold leading-5 text-foreground">{detail.name}</h3>
        <Button type="button" size="icon" variant="ghost" className="-mr-2 -mt-2 size-9 text-muted-foreground hover:text-destructive" aria-label={`Remove ${detail.name} from comparison`} onClick={onRemove}>
          <X className="size-4" aria-hidden="true" />
        </Button>
      </div>
      <dl className="mt-4 space-y-3">
        {fields.map(([label, value]) => (
          <div key={label} className="border-t border-border pt-3 first:border-0 first:pt-0">
            <dt className="text-xs font-semibold uppercase tracking-[0.1em] text-muted-foreground">{label}</dt>
            <dd className="mt-1 text-sm leading-6 text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}
