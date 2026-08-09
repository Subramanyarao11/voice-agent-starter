import { CloudOff, Gauge, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePwaPreferences } from "@/features/pwa/store";
import { useNetworkStatus } from "@/features/pwa/network-status";

export function NetworkStatusBanner() {
  const snapshot = useNetworkStatus();
  const dataSaver = usePwaPreferences((state) => state.dataSaver);
  const setDataSaver = usePwaPreferences((state) => state.setDataSaver);

  if (snapshot.mode === "online_good" && !dataSaver) return null;

  const offline = snapshot.mode === "offline";
  const constrained = snapshot.mode === "online_constrained" || dataSaver;
  const title = offline
    ? "You are offline"
    : snapshot.mode === "recovering"
      ? "Checking the connection"
      : constrained
        ? "Data-saver mode is on"
        : "Connection is limited";
  const description = offline
    ? "Only the safe app shell and downloaded public information are available. Live eligibility and submissions wait for a connection."
    : constrained
      ? "Text is prioritised. Audio and downloads will wait for your explicit action."
      : "The API did not respond. Your text stays on this page until you choose what to do.";

  return (
    <div
      className="border-b border-warning/60 bg-warning/15 px-4 py-3 text-sm text-foreground"
      role="status"
      aria-live="polite"
    >
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-3 sm:px-2">
        {offline ? <CloudOff className="size-5 shrink-0" aria-hidden="true" /> : <Gauge className="size-5 shrink-0" aria-hidden="true" />}
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{title}</p>
          <p className="mt-0.5 text-muted-foreground">{description}</p>
        </div>
        {snapshot.effectiveType !== "unknown" && <Badge variant="outline">{snapshot.effectiveType}</Badge>}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setDataSaver(!dataSaver)}
          aria-pressed={dataSaver}
        >
          {dataSaver ? "Use standard data" : "Use less data"}
        </Button>
        {!offline && (
          <Button type="button" variant="ghost" size="icon" onClick={() => window.location.reload()} aria-label="Refresh connection">
            <RefreshCw className="size-4" aria-hidden="true" />
          </Button>
        )}
      </div>
    </div>
  );
}
