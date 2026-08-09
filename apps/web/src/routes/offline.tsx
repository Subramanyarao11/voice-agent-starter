import { Link } from "@tanstack/react-router";
import { CloudOff, MessageSquareText } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function OfflinePage() {
  return (
    <main id="main-content" className="mx-auto min-h-svh max-w-3xl px-4 py-12 sm:px-6">
      <div className="flex items-start gap-4">
        <span className="grid size-12 shrink-0 place-items-center rounded-full bg-warning/20 text-warning-foreground">
          <CloudOff className="size-6" aria-hidden="true" />
        </span>
        <div>
          <p className="text-sm font-semibold text-primary">Sahaayak offline mode</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">You can still prepare</h1>
          <p className="mt-3 leading-7 text-muted-foreground">
            This page confirms that the safe app shell loaded without a live connection. Downloaded public information will say when it was last checked. Live eligibility, household data, applications, voice, and submissions wait for the network.
          </p>
        </div>
      </div>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <MessageSquareText className="size-5 text-primary" aria-hidden="true" />
              Write a question
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-6 text-muted-foreground">
              Return to the conversation when connected. You can explicitly save a text-only draft on this device for up to 24 hours.
            </p>
            <Link className="mt-4 inline-flex min-h-11 items-center font-semibold text-primary underline underline-offset-4" to="/">
              Return to Sahaayak
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Device data</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-6 text-muted-foreground">
              Sahaayak does not cache accounts, household facts, transcripts, audio, application references, contacts, or admin pages for offline use.
            </p>
            <Link className="mt-4 inline-flex min-h-11 items-center font-semibold text-primary underline underline-offset-4" to="/settings/data-usage">
              Review data settings
            </Link>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
