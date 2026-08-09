import { useEffect, useState } from "react";

import { Link } from "@tanstack/react-router";
import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { usePwaPreferences } from "@/features/pwa/store";
import { clearOfflineDrafts, listOfflineDrafts, type OfflineDraft } from "@/pwa/offline-store";

export function DataUsagePage() {
  const dataSaver = usePwaPreferences((state) => state.dataSaver);
  const setDataSaver = usePwaPreferences((state) => state.setDataSaver);
  const [drafts, setDrafts] = useState<OfflineDraft[]>([]);

  useEffect(() => {
    void listOfflineDrafts().then(setDrafts).catch(() => setDrafts([]));
  }, []);

  const clearDrafts = async () => {
    await clearOfflineDrafts();
    setDrafts([]);
  };

  return (
    <main id="main-content" className="mx-auto min-h-svh max-w-3xl px-4 py-12 sm:px-6" aria-labelledby="data-usage-title">
      <p className="text-sm font-semibold text-primary">Settings</p>
      <h1 id="data-usage-title" className="mt-2 text-3xl font-bold tracking-tight">Data use and offline information</h1>
      <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
        Choose how Sahaayak behaves on a limited connection. This setting does not change what the server stores or what you are eligible for.
      </p>

      <div className="mt-8 grid gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Data-saver mode</CardTitle>
            <CardDescription>Text comes first; audio and downloads need an explicit action.</CardDescription>
          </CardHeader>
          <CardContent>
            <label className="flex min-h-11 items-center gap-3 text-sm font-semibold">
              <input
                className="size-5 accent-primary"
                type="checkbox"
                checked={dataSaver}
                onChange={(event) => setDataSaver(event.target.checked)}
              />
              Use less data on this device
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Saved offline drafts</CardTitle>
            <CardDescription>Text-only drafts expire after 24 hours. Audio, answers, profiles, and account data are never stored here.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{drafts.length} draft{drafts.length === 1 ? "" : "s"} on this device.</p>
            <Button className="mt-4" type="button" variant="outline" disabled={drafts.length === 0} onClick={() => void clearDrafts()}>
              <Trash2 className="size-4" aria-hidden="true" />
              Clear offline drafts
            </Button>
          </CardContent>
        </Card>
      </div>

      <Link className="mt-8 inline-flex min-h-11 items-center font-semibold text-primary underline underline-offset-4" to="/">
        Return to Sahaayak
      </Link>
    </main>
  );
}
