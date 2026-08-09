/// <reference lib="webworker" />

import { clientsClaim, type WorkboxPlugin } from "workbox-core";
import { ExpirationPlugin } from "workbox-expiration";
import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching";
import { registerRoute } from "workbox-routing";
import { CacheFirst, NetworkFirst } from "workbox-strategies";

import {
  CACHE_NAMES,
  isPrivatePath,
  isPublicApiPath,
  isPublicReviewedResponse,
  isSafeNavigationPath,
} from "@/pwa/cache-policy";

declare let self: ServiceWorkerGlobalScope;

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);
clientsClaim();

const publicResponseGate: WorkboxPlugin = {
  cacheWillUpdate: async ({ response }) => (isPublicReviewedResponse(response) ? response : null),
};

const publicCacheLimits = new ExpirationPlugin({
  maxEntries: 80,
  maxAgeSeconds: 60 * 60 * 24 * 7,
  purgeOnQuotaError: true,
});

registerRoute(
  ({ request, url }) => request.method === "GET" && isPublicApiPath(url.pathname),
  new NetworkFirst({
    cacheName: CACHE_NAMES.publicCatalog,
    networkTimeoutSeconds: 4,
    plugins: [publicResponseGate, publicCacheLimits],
  }),
);

registerRoute(
  ({ request, url }) => request.method === "GET" && request.destination === "font" && !isPrivatePath(url.pathname),
  new CacheFirst({
    cacheName: CACHE_NAMES.fonts,
    plugins: [
      new ExpirationPlugin({
        maxEntries: 24,
        maxAgeSeconds: 60 * 60 * 24 * 365,
        purgeOnQuotaError: true,
      }),
    ],
  }),
);

registerRoute(
  ({ request, url }) => request.mode === "navigate" && isSafeNavigationPath(url.pathname),
  new NetworkFirst({
    cacheName: CACHE_NAMES.shell,
    networkTimeoutSeconds: 3,
    plugins: [
      new ExpirationPlugin({
        maxEntries: 12,
        maxAgeSeconds: 60 * 60 * 24,
        purgeOnQuotaError: true,
      }),
    ],
  }),
);

self.addEventListener("message", (event) => {
  if (event.data?.type === "APPLY_UPDATE") {
    // An update is applied only after the page explicitly asks for it. This
    // avoids interrupting recording, draft review, or a consequential form.
    void self.skipWaiting();
  }
});
