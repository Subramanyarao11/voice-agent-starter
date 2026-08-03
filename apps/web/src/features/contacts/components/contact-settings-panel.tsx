import { useState } from "react";

import { Check, Mail, MessageSquare, Phone, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  useAddContactPointMutation,
  useContactPointsQuery,
  useNotificationChannelsQuery,
  useRevokeContactPointMutation,
  useVerifyContactPointMutation,
} from "@/features/contacts/queries";
import type { ChannelStatus, ContactPoint } from "@/lib/api";

type ContactSettingsPanelProps = {
  sessionId: string;
  accessToken: string;
  languageCode: string;
};

const CHANNEL_LABELS: Record<string, string> = {
  in_app: "In the app",
  email: "Email",
  sms: "SMS",
  whatsapp: "WhatsApp",
};

const CHANNEL_ICONS: Record<string, typeof Mail> = {
  email: Mail,
  sms: Phone,
  whatsapp: MessageSquare,
};

/**
 * What the caller agrees to. Kept verbatim next to the control rather than
 * behind a link, and versioned server-side, so what someone consented to is
 * recorded rather than inferred.
 */
const CONSENT_TEXT =
  "Send me reminders about benefits I save. Messages come only when a reminder " +
  "I set is due. I can remove this contact at any time to stop them. Standard " +
  "carrier and provider terms apply.";

export function ContactSettingsPanel({
  sessionId,
  accessToken,
  languageCode,
}: ContactSettingsPanelProps) {
  const contactsQuery = useContactPointsQuery(sessionId, accessToken);
  const channelsQuery = useNotificationChannelsQuery(sessionId, accessToken);
  const addMutation = useAddContactPointMutation(sessionId, accessToken);
  const verifyMutation = useVerifyContactPointMutation(sessionId, accessToken);
  const revokeMutation = useRevokeContactPointMutation(sessionId, accessToken);

  const [channel, setChannel] = useState("email");
  const [destination, setDestination] = useState("");
  const [consent, setConsent] = useState(false);
  const [code, setCode] = useState("");
  const [pendingId, setPendingId] = useState("");
  const [notice, setNotice] = useState("");

  const contacts = contactsQuery.data ?? [];
  const channels = channelsQuery.data ?? [];
  // Channels the deployment can offer at all. A channel with no provider is
  // not shown as a choice, but its reason is still explained below.
  const offerable = channels.filter((item) => item.channel !== "in_app");

  const submitContact = (event: React.FormEvent) => {
    event.preventDefault();
    setNotice("");
    addMutation.mutate(
      { channel, destination, locale: languageCode, consent },
      {
        onSuccess: (created) => {
          setPendingId(created.id);
          setDestination("");
          setConsent(false);
          setNotice(`We sent a code to ${created.display_suffix}. Enter it below.`);
        },
        onError: (error) =>
          setNotice(
            error instanceof Error
              ? error.message
              : "That contact could not be added. Please check it and try again.",
          ),
      },
    );
  };

  const submitCode = (event: React.FormEvent) => {
    event.preventDefault();
    setNotice("");
    verifyMutation.mutate(
      { contactId: pendingId, code },
      {
        onSuccess: () => {
          setPendingId("");
          setCode("");
          setNotice("Contact verified. You can now use it for reminders.");
        },
        onError: () => setNotice("That code was not correct. Check it and try again."),
      },
    );
  };

  return (
    <section className="space-y-5" aria-labelledby="contact-settings-title">
      <div>
        <span className="font-mono text-[0.6rem] uppercase tracking-[0.2em] text-acid/75">
          Reminders
        </span>
        <h2
          id="contact-settings-title"
          className="mt-2 text-2xl font-extrabold tracking-tight text-paper"
        >
          Where we can reach you
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-paper/55">
          In-app reminders always work and need no contact details. Add a contact only
          if you want reminders to reach you elsewhere. We store it encrypted and show
          only the last few characters.
        </p>
      </div>

      {notice ? (
        <p role="status" className="text-sm text-paper/80">
          {notice}
        </p>
      ) : null}

      {contacts.length > 0 ? (
        <ul className="grid gap-3 md:grid-cols-2">
          {contacts.map((contact) => (
            <ContactRow
              key={contact.id}
              contact={contact}
              onRevoke={() => revokeMutation.mutate(contact.id)}
              busy={revokeMutation.isPending}
            />
          ))}
        </ul>
      ) : null}

      {pendingId ? (
        <Card>
          <CardContent className="space-y-3 p-4">
            <label htmlFor="verification-code" className="text-sm font-semibold text-paper">
              Enter the code we sent
            </label>
            <form onSubmit={submitCode} className="flex flex-wrap gap-2">
              <input
                id="verification-code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                inputMode="numeric"
                autoComplete="one-time-code"
                className="rounded-md border border-paper/20 bg-transparent px-3 py-2 text-paper"
                required
              />
              <Button type="submit" disabled={verifyMutation.isPending}>
                Verify
              </Button>
            </form>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent className="space-y-4 p-4">
          <form onSubmit={submitContact} className="space-y-4">
            <fieldset className="space-y-2">
              <legend className="text-sm font-semibold text-paper">Add a contact</legend>
              <div className="flex flex-wrap gap-2">
                {offerable.map((item) => (
                  <ChannelChoice
                    key={item.channel}
                    status={item}
                    selected={channel === item.channel}
                    onSelect={() => setChannel(item.channel)}
                  />
                ))}
              </div>
            </fieldset>

            <div className="space-y-1">
              <label htmlFor="contact-destination" className="text-sm text-paper/80">
                {channel === "email" ? "Email address" : "Phone number with country code"}
              </label>
              <input
                id="contact-destination"
                value={destination}
                onChange={(event) => setDestination(event.target.value)}
                type={channel === "email" ? "email" : "tel"}
                placeholder={channel === "email" ? "you@example.com" : "+919876543210"}
                autoComplete={channel === "email" ? "email" : "tel"}
                className="w-full rounded-md border border-paper/20 bg-transparent px-3 py-2 text-paper"
                required
              />
            </div>

            <label className="flex items-start gap-3 text-sm leading-6 text-paper/70">
              <input
                type="checkbox"
                checked={consent}
                onChange={(event) => setConsent(event.target.checked)}
                className="mt-1"
                required
              />
              <span>{CONSENT_TEXT}</span>
            </label>

            <Button type="submit" disabled={addMutation.isPending || !consent}>
              Send verification code
            </Button>
          </form>
        </CardContent>
      </Card>

      <UnavailableChannels channels={offerable} />
    </section>
  );
}

function ContactRow({
  contact,
  onRevoke,
  busy,
}: {
  contact: ContactPoint;
  onRevoke: () => void;
  busy: boolean;
}) {
  const Icon = CHANNEL_ICONS[contact.channel] ?? Mail;
  const verified = contact.verification_status === "verified";
  return (
    <li>
      <Card>
        <CardContent className="flex items-center justify-between gap-3 p-4">
          <div className="flex items-center gap-3">
            <Icon aria-hidden className="h-4 w-4 text-paper/60" />
            <div>
              <p className="text-sm font-semibold text-paper">
                {CHANNEL_LABELS[contact.channel] ?? contact.channel}
              </p>
              {/* Masked. The full destination is never sent to the browser. */}
              <p className="text-sm text-paper/60">{contact.display_suffix}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Status is carried by text as well as colour, so it survives
                both a screen reader and a monochrome display. */}
            <Badge variant={verified ? "default" : "outline"}>
              {verified ? (
                <>
                  <Check aria-hidden className="mr-1 h-3 w-3" />
                  Verified
                </>
              ) : (
                statusLabel(contact)
              )}
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              onClick={onRevoke}
              disabled={busy}
              aria-label={`Remove ${CHANNEL_LABELS[contact.channel] ?? contact.channel} contact ${contact.display_suffix}`}
            >
              <Trash2 aria-hidden className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </li>
  );
}

function statusLabel(contact: ContactPoint): string {
  if (contact.consent_status === "opted_out") return "Removed";
  if (contact.verification_status === "invalid") return "Not reachable";
  if (contact.verification_status === "revoked") return "Removed";
  return "Awaiting code";
}

function ChannelChoice({
  status,
  selected,
  onSelect,
}: {
  status: ChannelStatus;
  selected: boolean;
  onSelect: () => void;
}) {
  const Icon = CHANNEL_ICONS[status.channel] ?? Mail;
  return (
    <Button
      type="button"
      variant={selected ? "default" : "outline"}
      size="sm"
      onClick={onSelect}
      aria-pressed={selected}
    >
      <Icon aria-hidden className="mr-2 h-4 w-4" />
      {CHANNEL_LABELS[status.channel] ?? status.channel}
    </Button>
  );
}

/**
 * Explains every channel the caller cannot currently use.
 *
 * Deliberately prose rather than a disabled control with no explanation: a
 * greyed-out button tells someone that something is wrong without telling them
 * whether it is their fault or ours, or what would fix it.
 */
function UnavailableChannels({ channels }: { channels: ChannelStatus[] }) {
  const blocked = channels.filter((item) => !item.available && item.reason);
  if (blocked.length === 0) return null;

  return (
    <div className="rounded-lg border border-paper/15 p-4">
      <h3 className="text-sm font-semibold text-paper">Channels not available right now</h3>
      <dl className="mt-2 space-y-2">
        {blocked.map((item) => (
          <div key={item.channel} className="text-sm">
            <dt className="font-medium text-paper/80">
              {CHANNEL_LABELS[item.channel] ?? item.channel}
            </dt>
            <dd className="text-paper/55">{item.reason}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-sm text-paper/55">
        In-app reminders are unaffected and will still appear here.
      </p>
    </div>
  );
}
