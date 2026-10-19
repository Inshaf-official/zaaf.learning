/// <reference lib="WebWorker" />
import {
  precacheAndRoute,
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
} from "workbox-precaching";
import { registerRoute, NavigationRoute } from "workbox-routing";
import { NetworkFirst, CacheFirst } from "workbox-strategies";
import { ExpirationPlugin } from "workbox-expiration";
declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: { url: string; revision: string }[];
};
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();
registerRoute(
  new NavigationRoute(createHandlerBoundToURL("/index.html"), {
    denylist: [/^\/api\//],
  }),
);
registerRoute(
  ({ url, request }) =>
    url.origin === self.location.origin &&
    ["script", "style", "font"].includes(request.destination),
  new CacheFirst({
    cacheName: "institution-assets-v1",
    plugins: [new ExpirationPlugin({ maxEntries: 80, maxAgeSeconds: 2592000 })],
  }),
);
// Only low-sensitivity lookup/config responses are cached. Medical, marks, PDFs,
// notifications and profiles always require the network. Keys include membership.
registerRoute(
  ({ url, request }) =>
    request.method === "GET" &&
    /^\/api\/(institution\/config|class-groups|divisions)\/$/.test(
      url.pathname,
    ),
  new NetworkFirst({
    cacheName: "institution-lookups-v1",
    networkTimeoutSeconds: 5,
    plugins: [
      {
        cacheKeyWillBeUsed: async ({ request }) => {
          const url = new URL(request.url);
          url.searchParams.set(
            "__membership",
            request.headers.get("X-Membership-ID") || "none",
          );
          return new Request(url.toString(), { method: "GET" });
        },
        cacheWillUpdate: async ({ response }) =>
          response.status === 200 ? response : null,
      },
      new ExpirationPlugin({ maxEntries: 30, maxAgeSeconds: 86400 }),
    ],
  }),
);
self.addEventListener("message", (event) => {
  if (event.data?.type === "CLEAR_PRIVATE_CACHE") {
    event.waitUntil(caches.delete("institution-lookups-v1"));
  }
  if (event.data?.type === "SKIP_WAITING") void self.skipWaiting();
});
