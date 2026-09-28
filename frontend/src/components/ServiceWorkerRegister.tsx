"use client";

import { useEffect } from "react";

/**
 * Registers the PWA service worker in production only.
 *
 * `sw.js` cache-firsts `/_next/static/*` under a cache name that never changes between
 * builds, so once a browser has it installed, every dev rebuild is invisible to that tab
 * - hot reload swaps the module graph in memory, but a hard refresh re-fetches the old
 * cached chunk instead of the new one. Registering it in dev at all is what causes a
 * fixed bug to keep "coming back" for whoever's browser installed it first.
 */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
      return;
    }

    if (process.env.NODE_ENV !== "production") {
      // Undo any earlier build that registered unconditionally - without this a dev
      // browser stays stuck on its first-ever cached bundle no matter what ships next.
      navigator.serviceWorker.getRegistrations().then((registrations) => {
        registrations.forEach((registration) => registration.unregister());
      });
      if ("caches" in window) {
        caches.keys().then((keys) => keys.forEach((key) => caches.delete(key)));
      }
      return;
    }

    const registerSW = async () => {
      try {
        const registration = await navigator.serviceWorker.register("/sw.js", {
          scope: "/",
        });
        if (registration.installing) {
          console.debug("[SW] Service worker installing");
        } else if (registration.active) {
          console.debug("[SW] Service worker active");
        }
      } catch (error) {
        console.warn("[SW] Service worker registration failed:", error);
      }
    };

    if (document.readyState === "complete") {
      registerSW();
    } else {
      window.addEventListener("load", registerSW);
      return () => window.removeEventListener("load", registerSW);
    }
  }, []);

  return null;
}
