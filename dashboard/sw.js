/* OpenSense service worker — stale-while-revalidate.
   The shell and the last pipeline data are cached, so the installed PWA opens
   instantly and works offline with the most recent run's numbers. */
const CACHE = "opensense-v4";
const SHELL = [
  "/dashboard/",
  "/dashboard/manifest.webmanifest",
  "/dashboard/icons/icon-192.png",
  "/dashboard/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;              // star/profile/match POSTs pass through
  if (url.pathname.startsWith("/api/")) return;            // API is always live — never serve stale stars
  const isHtml = url.pathname.endsWith("/") || url.pathname.endsWith(".html");
  if (isHtml) {
    // network-first for the shell: a stale broken shell would live forever otherwise
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const cache = caches.open(CACHE).then((c) => c.put(event.request, response.clone()));
          return response;
        })
        .catch(() => caches.match(event.request, { ignoreSearch: true }))
    );
    return;
  }
  const isData = url.pathname.startsWith("/data/");
  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(event.request, { ignoreSearch: isData });
      const network = fetch(event.request)
        .then((response) => {
          if (response.ok) cache.put(event.request, response.clone());
          return response;
        })
        .catch(() => cached);
      return cached || network;                             // stale first, revalidate behind
    })
  );
});
