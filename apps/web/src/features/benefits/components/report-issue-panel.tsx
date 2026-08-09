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

  return (
    <Card className="mt-5 border-warning/35 bg-warning/10 text-foreground">
      <CardHeader className="gap-2 pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <MessageSquareWarning className="size-4 text-warning-foreground" aria-hidden="true" />
          <h2 className="text-lg font-extrabold">Report incorrect information</h2>
          <Badge variant="outline" className="border-warning/50 text-warning-foreground">
            Help us keep this accurate
          </Badge>
        </div>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Tell us what looks wrong. Do not include your income, phone number, or other private information here.
        </p>
      </CardHeader>
      <CardContent>
        <form className="grid max-w-5xl gap-4 lg:grid-cols-[minmax(220px,.4fr)_minmax(0,1fr)]" onSubmit={submit}>
          <label className="grid content-start gap-1 text-xs font-semibold text-foreground" htmlFor="issue-category">
            What is wrong?
            <select
              id="issue-category"
              value={category}
              onChange={(event) => setCategory(event.target.value as typeof category)}
              className="h-11 rounded-lg border border-border bg-background px-3 text-sm text-foreground"
            >
              {categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-xs font-semibold text-foreground" htmlFor="issue-description">
            What should we check?
            <Textarea
              id="issue-description"
              required
              minLength={5}
              maxLength={1000}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="For example: the official notice shows a different closing date."
              className="min-h-24 bg-background"
            />
          </label>
          <div className="flex justify-end lg:col-start-2">
            <Button
              type="submit"
              size="sm"
              className="w-full sm:w-auto"
              disabled={!accessToken || mutation.isPending || description.trim().length < 5}
            >
              {mutation.isPending ? "Sending…" : "Send report"}
            </Button>
          </div>
        </form>
        {notice && <p className="mt-3 text-xs leading-5 text-success" role="status">{notice}</p>}
      </CardContent>
    </Card>
  );
}
