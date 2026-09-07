"use client";

import { LowPoly, Mark } from "@/components/LowPoly";

/**
 * Boot splash.
 *
 * Shown while the app resolves the stored token against `/auth/me`. It exists so the
 * first paint is never a half-built dashboard or a login flash for someone who is
 * already signed in.
 */
export function Splash({ label = "Preparing your workspace" }: { label?: string }) {
  return (
    <div className="fixed inset-0 z-[200] flex flex-col items-center justify-center overflow-hidden bg-paper">
      <LowPoly variant="hero" className="absolute inset-0 h-full w-full opacity-70" animate />

      <div className="relative flex flex-col items-center">
        <div className="animate-ring rounded-[18px] bg-surface p-4 shadow-[var(--shadow-lift)]">
          <Mark size={44} />
        </div>

        <p className="mt-6 text-[15px] font-semibold tracking-tight text-ink">Examina</p>
        <p className="mt-1 text-[13px] text-ink-muted">{label}</p>

        <div className="mt-6 h-[3px] w-40 overflow-hidden rounded-full bg-line">
          <div className="skeleton h-full w-full rounded-full" />
        </div>
      </div>

      <p className="absolute bottom-8 text-[11px] uppercase tracking-[0.18em] text-ink-muted">
        AI-Proctored Examination Platform
      </p>
    </div>
  );
}
