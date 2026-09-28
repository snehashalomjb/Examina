/**
 * Examina Production Service Worker
 *
 * CRITICAL SAFETY RULES:
 * 1. NEVER cache active examination APIs or session data (/api/v1/sessions/*, /api/v1/proctor/*).
 * 2. NEVER cache authentication endpoints or JWT tokens (/api/v1/auth/*).
 * 3. NEVER intercept or cache WebSocket signaling or data (/ws/*, wss://).
 * 4. Cache ONLY safe, immutable static assets (_next/static, fonts, icons, manifest, static assets).
 * 5. HTML navigation requests use a Network-First strategy with fallback to offline page/cache.
 * 6. Active examination taking (/exam/*) is ALWAYS strictly network-dependent.
 */

// Bump this string on any production release that changes cached asset behavior -
// the "activate" handler below only evicts caches under a *different* name, so an
// unbumped version never frees the entries a previous deploy left behind.
const CACHE_NAME = "examina-static-v4";

const PRECACHE_ASSETS = [
  "/",
  "/offline",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
];

// Path fragments that always mean "auth/API/session traffic" - matched with
// includes(), not startsWith(), so this holds regardless of whether the backend
// is mounted at the origin root, behind /api, or behind a versioned /api/v1.
const RESTRICTED_PATH_FRAGMENTS = [
  "/api/",
  "/auth/",
  "/login",
  "/register",
  "/token",
  "/exam/",
  "/ws/",
];

// URLs/patterns that must NEVER be handled or cached by the service worker
function isRestrictedOrDynamic(url) {
  const pathname = url.pathname;

  if (RESTRICTED_PATH_FRAGMENTS.some((fragment) => pathname.includes(fragment))) return true;

  // Never touch WebSocket endpoints
  if (url.protocol === "ws:" || url.protocol === "wss:") return true;

  return false;
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_ASSETS))
      .then(() => self.skipWaiting())
      .catch((err) => {
        console.warn("[SW] Precache skipped items:", err);
      })
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.map((key) => {
            if (key !== CACHE_NAME) {
              return caches.delete(key);
            }
          })
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Only handle GET requests; POST, PUT, DELETE, PATCH must bypass the service worker completely
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);

  // If request is to an external origin (like backend API host) or restricted path, bypass cache
  if (url.origin !== self.location.origin || isRestrictedOrDynamic(url)) {
    return;
  }

  // Handle static assets (_next/static, /icons, /mediapipe, fonts): Cache First with background refresh
  if (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname.startsWith("/mediapipe/") ||
    url.pathname.startsWith("/models/") ||
    url.pathname.endsWith(".png") ||
    url.pathname.endsWith(".svg") ||
    url.pathname.endsWith(".ico")
  ) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return networkResponse;
        });
      })
    );
    return;
  }

  // HTML page navigations (dashboard, etc.): Network first with cache fallback
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return networkResponse;
        })
        .catch(() => {
          return caches.match(request).then((cached) => {
            if (cached) return cached;
            return caches.match("/offline");
          });
        })
    );
    return;
  }
});
