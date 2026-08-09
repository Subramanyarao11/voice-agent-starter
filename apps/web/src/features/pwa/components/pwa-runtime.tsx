import { useEffect, useState, type ReactNode } from "react";

import { RefreshCw, Wifi } from "lucide-react";

import { Button } from "@/components/ui/button";
import { NetworkStatusBanner } from "@/features/pwa/components/network-status-banner";
import { registerServiceWorker } from "@/pwa/register-service-worker";

export function PwaRuntime({ children }: { children: ReactNode }) {
  const [offlineReady, setOfflineReady] = useState(false);
  const [registrationError, setRegistrationError] = useState<string | null>(null);
  const [needRefresh, setNeedRefresh] = useState(false);
  const [updateServiceWorker, setUpdateServiceWorker] = useState<(() => Promise<void>) | null>(null);

  // Registration is deliberately delayed until after the initial interactive
  // shell. It avoids competing with the first text render and is a no-op in
  // development because the Vite PWA plugin's dev option is disabled.
  useEffect(() => {
    if (!import.meta.env.PROD) {
      // A production service worker previously installed on localhost can
      // otherwise keep serving an old build over the Vite development server.
      // Clear only Cache Storage/service-worker registrations; IndexedDB
      // drafts and user-created local state are intentionally preserved.
      void navigator.serviceWorker?.getRegistrations().then((registrations) =>
        Promise.all(registrations.map((registration) => registration.unregister())),
      );
      if ("caches" in window) {
        void caches.keys().then((keys) => Promise.all(keys.map((key) => caches.delete(key))));
      }
      return;
    }
    const timer = window.setTimeout(() => {
      const update = registerServiceWorker({
        onNeedRefresh: () => setNeedRefresh(true),
        onOfflineReady: () => setOfflineReady(true),
        onError: () => setRegistrationError("Offline support could not be started on this browser."),
      });
      setUpdateServiceWorker(() => update);
    }, 1_200);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <>
      <NetworkStatusBanner />
      {children}
      {(needRefresh || offlineReady || registrationError) && (
        <aside className="fixed inset-x-4 bottom-4 z-50 mx-auto max-w-lg rounded-lg border border-border bg-card p-4 shadow-xl" role="status">
          <div className="flex items-start gap-3">
            {needRefresh ? <RefreshCw className="mt-0.5 size-5 text-primary" aria-hidden="true" /> : <Wifi className="mt-0.5 size-5 text-success" aria-hidden="true" />}
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-foreground">
                {needRefresh ? "A safe update is ready" : offlineReady ? "Public information can be opened offline" : "Offline support unavailable"}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {needRefresh
                  ? "Apply it when you are not recording, editing a draft, or confirming an action."
                  : offlineReady
                    ? "Only reviewed public content is eligible for offline use."
                    : registrationError}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {needRefresh && updateServiceWorker && (
                  <Button type="button" size="sm" onClick={() => void updateServiceWorker()}>
                    Apply update
                  </Button>
                )}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setNeedRefresh(false);
                    setOfflineReady(false);
                    setRegistrationError(null);
                    setUpdateServiceWorker(null);
                  }}
                >
                  Dismiss
                </Button>
              </div>
            </div>
          </div>
        </aside>
      )}
    </>
  );
}
