import { BookOpen, ExternalLink, Info, Quote } from "lucide-react";

import type { TurnResponse } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useUi } from "@/features/i18n/ui-provider";

type SourcesPanelProps = {
  turn: TurnResponse | null;
};

function isSafeExternalUrl(value: string): boolean {
  return value.startsWith("https://") || value.startsWith("http://");
}

function relevanceLabel(score: number): string {
  return `${Math.round(Math.max(0, Math.min(1, score)) * 100)}% relevant`;
}

export function SourcesPanel({ turn }: SourcesPanelProps) {
  const { t } = useUi();
  const sources = turn?.sources ?? [];
  const groundedAnswer = turn?.grounded_answer?.trim();

  if (!groundedAnswer && sources.length === 0) return null;

  return (
    <section className="space-y-4" aria-labelledby="sources-title">
      <Card className="border-blue/20 bg-blue/[0.06] text-paper">
        <CardHeader className="gap-3 px-5 pb-4 pt-5 sm:px-7">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <span
                className="grid size-10 shrink-0 place-items-center rounded-xl border border-blue/25 bg-blue/10 text-blue"
                aria-hidden="true"
              >
                <BookOpen className="size-4" />
              </span>
              <div>
                <span className="font-mono text-[0.6rem] uppercase tracking-[0.2em] text-blue/80">
                  {t("evidenceTrail")}
                </span>
                <h2 id="sources-title" className="mt-1 text-lg font-extrabold text-paper">
                  {t("sourcesForAnswer")}
                </h2>
              </div>
            </div>
            <Badge variant="outline" className="border-blue/25 text-blue">
              <Quote className="size-3" aria-hidden="true" />
              {t("sourceGrounded")}
            </Badge>
          </div>
          <p className="flex items-start gap-2 text-sm leading-6 text-paper/65">
            <Info className="mt-1 size-4 shrink-0 text-blue" aria-hidden="true" />
            <span>
              {t("sourceDisclaimer")}
            </span>
          </p>
        </CardHeader>

        <CardContent className="space-y-4 px-5 pb-6 sm:px-7">
          {groundedAnswer && (
            <blockquote className="rounded-xl border border-paper/10 bg-ink/30 px-4 py-3 text-sm leading-6 text-paper/80">
              <span className="mb-2 block font-mono text-[0.58rem] uppercase tracking-[0.16em] text-paper/45">
                {t("answerWithCitations")}
              </span>
              {groundedAnswer}
            </blockquote>
          )}

          {sources.length > 0 ? (
            <ol className="grid gap-3" aria-label="Retrieved source documents">
              {sources.map((source, index) => {
                const sourceUrl = source.source_url.trim();
                const sourceHeadingId = `source-${index + 1}-title`;

                return (
                  <li key={`${source.source_id}-${source.filename}`}>
                    <article
                      className="rounded-xl border border-paper/10 bg-ink/20 px-4 py-4"
                      aria-labelledby={sourceHeadingId}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="font-mono text-[0.58rem] uppercase tracking-[0.15em] text-blue/80">
                            {t("source")} {index + 1}
                          </p>
                          <h3 id={sourceHeadingId} className="mt-1 break-words text-sm font-bold text-paper">
                            {source.filename || source.source_id}
                          </h3>
                        </div>
                        <Badge variant="outline" className="border-paper/15 text-paper/55">
                          {relevanceLabel(source.score)}
                        </Badge>
                      </div>

                      <details className="group mt-3 rounded-lg border border-paper/10 bg-paper/[0.03]">
                        <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-paper/70 outline-none transition hover:text-paper focus-visible:ring-2 focus-visible:ring-ring">
                          {t("showSupportingExcerpt")}
                        </summary>
                        <p className="border-t border-paper/10 px-3 py-3 text-xs leading-5 text-paper/60">
                          {source.excerpt || t("noAdditionalReason")}
                        </p>
                      </details>

                      {isSafeExternalUrl(sourceUrl) && (
                        <a
                          className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-acid underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          href={sourceUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label={`Open source document ${index + 1} in a new tab`}
                        >
                          {t("openSourceDocument")}
                          <ExternalLink className="size-3" aria-hidden="true" />
                        </a>
                      )}
                    </article>
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="rounded-xl border border-orange/20 bg-orange/10 px-4 py-3 text-sm leading-6 text-orange">
              {t("noSupportingSource")}
            </p>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
