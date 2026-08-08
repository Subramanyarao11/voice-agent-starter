import { useState, type FormEvent } from "react";

import { MessageSquareWarning } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useReportBenefitIssueMutation } from "@/features/benefits/queries";
import { toUserMessage } from "@/lib/api";

const categories = [
  ["source", "Official source or link"],
  ["eligibility", "Eligibility or criteria"],
  ["deadline", "Deadline or freshness"],
  ["application", "Application steps or documents"],
  ["other", "Something else"],
] as const;

export function ReportIssuePanel({ benefitId, accessToken }: { benefitId: string; accessToken: string }) {
  const mutation = useReportBenefitIssueMutation(benefitId, accessToken);
  const [category, setCategory] = useState<(typeof categories)[number][0]>("source");
  const [description, setDescription] = useState("");
  const [notice, setNotice] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("");
    mutation.mutate(
      { category, description: description.trim() },
      {
        onSuccess: () => {
          setDescription("");
          setNotice("Thank you. The operations team has received this report.");
        },
        onError: (error) => setNotice(toUserMessage(error)),
      },
    );
  }

  return <Card className="mt-5 border-orange/20 bg-orange/[0.05] text-paper"><CardHeader className="gap-2 pb-3"><div className="flex items-center gap-2"><MessageSquareWarning className="size-4 text-orange" aria-hidden="true" /><h2 className="text-lg font-extrabold">Report incorrect information</h2><Badge variant="outline" className="border-orange/30 text-orange">Help us keep this accurate</Badge></div><p className="text-sm leading-6 text-paper/55">Tell us what looks wrong. Do not include your income, phone number, or other private information here.</p></CardHeader><CardContent><form className="grid gap-3 sm:grid-cols-[minmax(190px,.35fr)_1fr_auto] sm:items-end" onSubmit={submit}><label className="grid gap-1 text-xs font-semibold text-paper/60" htmlFor="issue-category">What is wrong?<select id="issue-category" value={category} onChange={(event) => setCategory(event.target.value as typeof category)} className="h-10 rounded-lg border border-paper/15 bg-ink px-2 text-sm text-paper"><option value="source">Official source or link</option><option value="eligibility">Eligibility or criteria</option><option value="deadline">Deadline or freshness</option><option value="application">Application steps or documents</option><option value="other">Something else</option></select></label><label className="grid gap-1 text-xs font-semibold text-paper/60" htmlFor="issue-description">What should we check?<Textarea id="issue-description" required minLength={5} maxLength={1000} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="For example: the official notice shows a different closing date." className="min-h-10" /></label><Button type="submit" size="sm" disabled={!accessToken || mutation.isPending || description.trim().length < 5}>{mutation.isPending ? "Sending…" : "Send report"}</Button></form>{notice && <p className="mt-3 text-xs leading-5 text-acid" role="status">{notice}</p>}</CardContent></Card>;
}
