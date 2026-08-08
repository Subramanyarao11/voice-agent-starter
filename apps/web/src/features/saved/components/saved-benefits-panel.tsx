import { useEffect, useState } from "react";

import { Link } from "@tanstack/react-router";
import { Bell, BookmarkCheck, ExternalLink, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useNotificationChannelsQuery } from "@/features/contacts/queries";
import {
  useCancelReminderMutation,
  useCreateReminderMutation,
  useRemindersQuery,
  useRemoveSavedBenefitMutation,
} from "@/features/saved/queries";
import type { Reminder, SavedBenefit } from "@/lib/api";

type SavedBenefitsPanelProps = {
  sessionId: string;
  accessToken: string;
  savedBenefits: SavedBenefit[];
};

const CHANNEL_LABELS: Record<string, string> = {
  in_app: "In the app",
  email: "Email",
  sms: "SMS",
  whatsapp: "WhatsApp",
};

const CHANNEL_ORDER = ["in_app", "email", "sms", "whatsapp"];

export function SavedBenefitsPanel({
  sessionId,
  accessToken,
  savedBenefits,
}: SavedBenefitsPanelProps) {
  const removeMutation = useRemoveSavedBenefitMutation(sessionId, accessToken);
  const reminderMutation = useCreateReminderMutation(sessionId, accessToken);
  const cancelReminderMutation = useCancelReminderMutation(sessionId, accessToken);
  const remindersQuery = useRemindersQuery(sessionId, accessToken);
  const channelsQuery = useNotificationChannelsQuery(sessionId, accessToken);
  const [selectedChannel, setSelectedChannel] = useState("in_app");
  const [notice, setNotice] = useState("");

  const channels = channelsQuery.data ?? [];
  const selectedStatus = channels.find((item) => item.channel === selectedChannel);

  useEffect(() => {
    if (!channels.length) return;
    const selected = channels.find((item) => item.channel === selectedChannel);
    if (!selected?.available) setSelectedChannel("in_app");
  }, [channels, selectedChannel]);

  if (savedBenefits.length === 0 && !remindersQuery.data?.length) return null;

  const scheduleReminder = (benefitId: string) => {
    const due = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
    setNotice("");
    reminderMutation.mutate(
      {
        benefit_id: benefitId,
        due_at: due,
        note: "Follow up on this saved benefit.",
        channel: selectedChannel,
      },
      {
        onSuccess: () =>
          setNotice(
            selectedChannel === "in_app"
              ? "In-app reminder set for seven days from now."
              : `${CHANNEL_LABELS[selectedChannel] ?? selectedChannel} reminder scheduled for seven days from now. Delivery status will update here.`,
          ),
        onError: (error) =>
          setNotice(error instanceof Error ? error.message : "The reminder could not be set. Please try again."),
      },
    );
  };

  const cancelReminder = (reminderId: string) => {
    setNotice("");
    cancelReminderMutation.mutate(reminderId, {
      onSuccess: () => setNotice("Reminder cancelled."),
      onError: () => setNotice("The reminder could not be cancelled. Please try again."),
    });
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

      {savedBenefits.length > 0 && (
        <Card className="border-acid/20 bg-acid/[0.04] text-paper">
          <CardContent className="space-y-2 p-4">
            <label htmlFor="reminder-channel" className="text-sm font-semibold text-paper">
              Where should new reminders arrive?
            </label>
            <select
              id="reminder-channel"
              value={selectedChannel}
              onChange={(event) => setSelectedChannel(event.target.value)}
              aria-describedby="reminder-channel-help"
              className="w-full rounded-md border border-paper/20 bg-ink px-3 py-2 text-sm text-paper sm:max-w-sm"
            >
              {CHANNEL_ORDER.map((channel) => {
                const status = channels.find((item) => item.channel === channel);
                return (
                  <option key={channel} value={channel} disabled={status ? !status.available : channel !== "in_app"}>
                    {CHANNEL_LABELS[channel]}
                    {status && !status.available && channel !== "in_app" ? " — unavailable" : ""}
                  </option>
                );
              })}
            </select>
            <p id="reminder-channel-help" className="text-xs leading-5 text-paper/55">
              {selectedStatus?.available
                ? selectedStatus.channel === "in_app"
                  ? "In-app reminders need no contact details."
                  : `Messages will go to ${selectedStatus.display_suffix}. Only the masked address is shown here.`
                : selectedStatus?.reason || "Loading channel availability…"}
            </p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {savedBenefits.map((benefit) => (
          <Card key={benefit.id} className="border-paper/10 bg-paper/[0.04] text-paper">
            <CardContent className="space-y-4 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <Badge variant="outline" className="border-acid/25 text-acid">
                    {benefit.domain}
                  </Badge>
                  <h3 className="mt-3 text-lg font-bold leading-snug">
                    <Link
                      to="/benefits/$benefitId"
                      params={{ benefitId: benefit.benefit_id }}
                      className="underline-offset-4 hover:underline"
                    >
                      {benefit.name}
                    </Link>
                  </h3>
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
                  disabled={reminderMutation.isPending || !selectedStatus?.available}
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
            Reminder status
          </p>
          <ul className="mt-3 space-y-3">
            {remindersQuery.data.map((reminder) => (
              <ReminderRow
                key={reminder.id}
                reminder={reminder}
                onCancel={() => cancelReminder(reminder.id)}
                busy={cancelReminderMutation.isPending}
              />
            ))}
          </ul>
          <p className="mt-3 text-xs leading-5 text-paper/45">
            External delivery means the provider accepted the message; “delivered” appears only after Infobip reports it.
          </p>
        </div>
      )}
      {notice && <p className="text-xs text-acid" role="status">{notice}</p>}
    </section>
  );
}

function ReminderRow({
  reminder,
  onCancel,
  busy,
}: {
  reminder: Reminder;
  onCancel: () => void;
  busy: boolean;
}) {
  const isScheduled = reminder.status === "scheduled";
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 border-t border-paper/10 pt-3 first:border-t-0 first:pt-0">
      <div>
        <p className="font-medium text-paper">{reminder.benefit_name}</p>
        <p className="mt-1 text-xs text-paper/50">
          {CHANNEL_LABELS[reminder.channel] ?? reminder.channel} · {new Date(reminder.due_at).toLocaleDateString()}
          {reminder.contact_display_suffix ? ` · ${reminder.contact_display_suffix}` : ""}
        </p>
        <p className="mt-1 text-xs text-paper/65">{reminderStatusLabel(reminder)}</p>
      </div>
      {isScheduled && (
        <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      )}
    </li>
  );
}

function reminderStatusLabel(reminder: Reminder): string {
  if (reminder.status === "cancelled") return "Cancelled";
  if (reminder.status === "failed") return "Could not be delivered; in-app fallback remains available.";
  if (reminder.status === "delivered") return "Delivered";
  if (reminder.delivery_status === "delivered" || reminder.delivery_status === "seen") {
    return reminder.delivery_status === "seen" ? "Seen" : "Delivered";
  }
  if (reminder.delivery_status === "accepted") return "Accepted by provider; waiting for delivery confirmation.";
  if (reminder.delivery_status === "suppressed") return "Not sent because consent, policy, or budget blocked this channel.";
  if (reminder.delivery_status === "failed") return "Provider could not deliver this message.";
  return reminder.channel === "in_app" ? "Scheduled in the app." : "Scheduled; waiting for dispatch.";
}
