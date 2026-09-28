import Link from "next/link";

export const metadata = {
  title: "Offline — Examina",
};

/**
 * Cached by sw.js as the navigation-fallback target. Must not depend on any
 * network call (auth, API, fonts fetch) - it is the page shown precisely when
 * those are unreachable.
 */
export default function OfflinePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#181b2e] px-6 text-center text-white">
      <div className="flex h-16 w-16 items-center justify-center rounded-[16px] bg-white/10">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M3 3l18 18M8.5 8.5A9.5 9.5 0 0 0 3.5 11m4-6.5A11 11 0 0 1 21.5 11M12 18h.01M8.5 14.5a5.5 5.5 0 0 1 7-1"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <h1 className="text-[20px] font-bold tracking-tight">You&apos;re offline</h1>
      <p className="max-w-sm text-[13.5px] leading-relaxed text-white/70">
        Examina can&apos;t reach the network right now. Reconnect and try again — active
        exam sessions always require a live connection.
      </p>
      <Link
        href="/dashboard"
        className="mt-2 inline-flex h-10 items-center justify-center rounded-[10px] bg-white px-5 text-[13.5px] font-semibold text-[#181b2e] transition hover:bg-white/90"
      >
        Retry
      </Link>
    </main>
  );
}
