import { useState } from "react";

import { Bell, BookmarkCheck, ExternalLink, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  useCreateReminderMutation,
  useRemindersQuery,
  useRemoveSavedBenefitMutation,
} from "@/features/saved/queries";
import type { SavedBenefit } from "@/lib/api";

type SavedBenefitsPanelProps = {
  sessionId: string;
  accessToken: string;
  savedBenefits: SavedBenefit[];
};

export function SavedBenefitsPanel({
  sessionId,
  accessToken,
  savedBenefits,
}: SavedBenefitsPanelProps) {
  const removeMutation = useRemoveSavedBenefitMutation(sessionId, accessToken);
  const reminderMutation = useCreateReminderMutation(sessionId, accessToken);
  const remindersQuery = useRemindersQuery(sessionId, accessToken);
  const [notice, setNotice] = useState("");

  if (savedBenefits.length === 0 && !remindersQuery.data?.length) return null;

  const scheduleReminder = (benefitId: string) => {
    const due = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
    setNotice("");
    reminderMutation.mutate(
      { benefit_id: benefitId, due_at: due, note: "Follow up on this saved benefit." },
      {
        onSuccess: () => setNotice("Reminder set for seven days from now."),
        onError: () => setNotice("The reminder could not be set. Please try again."),
      },
    );
  };

  return (
    <section className="space-y-5" aria-labelledby="saved-benefits-title">
      <div>
        <span className="font-mono text-[0.6rem] uppercase tracking-[0.2em] text-acid/75">
          Your shortlist
        </span>
        <h2 id="saved-benefits-title" className="mt-2 text-2xl font-extrabold tracking-tight text-paper">
          Saved benefits
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-paper/55">
          Saved privately in this guest session. You can remove the session at any time.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {savedBenefits.map((benefit) => (
          <Card key={benefit.id} className="border-paper/10 bg-paper/[0.04] text-paper">
            <CardContent className="space-y-4 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <Badge variant="outline" className="border-acid/25 text-acid">
                    {benefit.domain}
                  </Badge>
                  <h3 className="mt-3 text-lg font-bold leading-snug">{benefit.name}</h3>
                </div>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={`Remove ${benefit.name} from saved benefits`}
                  onClick={() => removeMutation.mutate(benefit.benefit_id)}
                  disabled={removeMutation.isPending}
                >
                  <X className="size-4" aria-hidden="true" />
                </Button>
              </div>
              <p className="text-sm leading-6 text-paper/60">{benefit.description}</p>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => scheduleReminder(benefit.benefit_id)}
                  disabled={reminderMutation.isPending}
                >
                  <Bell className="size-3.5" aria-hidden="true" />
                  Remind me in 7 days
                </Button>
                {benefit.source_document_url && (
                  <a
                    className="inline-flex items-center gap-1.5 rounded-md px-2 text-xs font-semibold text-acid underline-offset-4 hover:underline"
                    href={benefit.source_document_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Source <ExternalLink className="size-3" aria-hidden="true" />
                  </a>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {remindersQuery.data && remindersQuery.data.length > 0 && (
        <div className="rounded-2xl border border-acid/20 bg-acid/5 p-4 text-sm text-paper/65">
          <p className="flex items-center gap-2 font-semibold text-acid">
            <BookmarkCheck className="size-4" aria-hidden="true" />
            Upcoming reminders
          </p>
          <ul className="mt-3 space-y-2">
            {remindersQuery.data
              .filter((reminder) => reminder.status === "scheduled")
              .map((reminder) => (
                <li key={reminder.id}>
                  {reminder.benefit_name} · {new Date(reminder.due_at).toLocaleDateString()}
                </li>
              ))}
          </ul>
        </div>
      )}
      {notice && <p className="text-xs text-acid" role="status">{notice}</p>}
    </section>
  );
}
