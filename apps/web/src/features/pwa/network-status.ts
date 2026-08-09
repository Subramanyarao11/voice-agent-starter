import { useCallback, useEffect, useState } from "react";

export type NetworkMode = "unknown" | "online_good" | "online_constrained" | "degraded" | "offline" | "recovering";

export type NetworkSnapshot = {
  mode: NetworkMode;
  browserOnline: boolean;
  apiReachable: boolean | null;
  effectiveType: string;
  saveData: boolean;
  lastCheckedAt: string | null;
};

type NetworkInformationLike = {
  effectiveType?: string;
  saveData?: boolean;
  rtt?: number;
  addEventListener?: (type: string, listener: () => void) => void;
  removeEventListener?: (type: string, listener: () => void) => void;
};

type NavigatorWithConnection = Navigator & { connection?: NetworkInformationLike };

const API_ROOT = import.meta.env.VITE_API_BASE_URL ?? "";

function browserOnline(): boolean {
  return typeof navigator === "undefined" ? true : navigator.onLine;
}

function connectionInfo(): NetworkInformationLike {
  return (typeof navigator !== "undefined" ? (navigator as NavigatorWithConnection).connection : undefined) ?? {};
}

function snapshotFor(mode: NetworkMode, apiReachable: boolean | null): NetworkSnapshot {
  const connection = connectionInfo();
  return {
    mode,
    browserOnline: browserOnline(),
    apiReachable,
    effectiveType: connection.effectiveType ?? "unknown",
    saveData: connection.saveData ?? false,
    lastCheckedAt: new Date().toISOString(),
  };
}

async function probeApi(): Promise<boolean> {
  if (!browserOnline()) return false;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 3_000);
  try {
    const url = API_ROOT ? new URL("/health", API_ROOT).toString() : "/health";
    const response = await fetch(url, {
      method: "GET",
      cache: "no-store",
      credentials: "omit",
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(timeout);
  }
}

function modeFor(apiReachable: boolean | null): NetworkMode {
  if (!browserOnline()) return "offline";
  if (apiReachable === false) return "degraded";
  const connection = connectionInfo();
  if (connection.saveData || connection.effectiveType === "slow-2g" || connection.effectiveType === "2g") {
    return "online_constrained";
  }
  if (connection.rtt && connection.rtt > 800) return "online_constrained";
  return apiReachable === null ? "unknown" : "online_good";
}

export function useNetworkStatus(): NetworkSnapshot {
  const [snapshot, setSnapshot] = useState<NetworkSnapshot>(() => snapshotFor("unknown", null));

  const refresh = useCallback(async (recovering = false) => {
    setSnapshot((current) => snapshotFor(recovering ? "recovering" : current.mode, current.apiReachable));
    const reachable = await probeApi();
    setSnapshot(snapshotFor(modeFor(reachable), reachable));
  }, []);

  useEffect(() => {
    void refresh();
    const onOnline = () => void refresh(true);
    const onOffline = () => setSnapshot(snapshotFor("offline", false));
    const onConnectionChange = () => void refresh();
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    const connection = connectionInfo();
    connection.addEventListener?.("change", onConnectionChange);
    const interval = window.setInterval(() => void refresh(), 30_000);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      connection.removeEventListener?.("change", onConnectionChange);
      window.clearInterval(interval);
    };
  }, [refresh]);

  return snapshot;
}
