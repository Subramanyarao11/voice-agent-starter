import { registerSW } from "virtual:pwa-register";

export type ServiceWorkerCallbacks = {
  onNeedRefresh?: () => void;
  onOfflineReady?: () => void;
  onError?: (error: unknown) => void;
};

export function registerServiceWorker(callbacks: ServiceWorkerCallbacks = {}): () => Promise<void> {
  return registerSW({
    immediate: false,
    onNeedRefresh: callbacks.onNeedRefresh,
    onOfflineReady: callbacks.onOfflineReady,
    onRegisterError: callbacks.onError,
  });
}
