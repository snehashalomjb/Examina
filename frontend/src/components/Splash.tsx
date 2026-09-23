"use client";

import { LowPoly, Mark } from "@/components/LowPoly";

/**
 * Boot splash — Premium version.
 *
 * Shown while the app resolves the stored token against `/auth/me`. It exists so the
 * first paint is never a half-built dashboard or a login flash for someone who is
 * already signed in.
 */
export function Splash({ label = "Preparing your workspace" }: { label?: string }) {
  return (
    <div className="fixed inset-0 z-[200] flex flex-col items-center justify-center overflow-hidden"
      style={{ background: "#080b12" }}>

      {/* Aurora orbs */}
      <div className="aurora-orb" style={{
        width: 600, height: 600,
        background: "radial-gradient(circle, rgba(79,70,229,0.25) 0%, transparent 70%)",
        top: "-20%", left: "-10%",
      }} />
      <div className="aurora-orb animate-glow-pulse" style={{
        width: 500, height: 500,
        background: "radial-gradient(circle, rgba(139,92,246,0.18) 0%, transparent 70%)",
        bottom: "-15%", right: "-5%",
        animationDelay: "1s",
      }} />
      <div className="aurora-orb" style={{
        width: 300, height: 300,
        background: "radial-gradient(circle, rgba(6,182,212,0.12) 0%, transparent 70%)",
        top: "30%", right: "10%",
      }} />

      {/* Low-poly mesh on top of dark bg */}
      <LowPoly variant="hero" className="absolute inset-0 h-full w-full opacity-20" animate />

      {/* Card */}
      <div className="relative flex flex-col items-center animate-rise">
        {/* Logo box */}
        <div className="animate-logo-reveal" style={{ animationDelay: "0.05s" }}>
          <div className="relative flex h-20 w-20 items-center justify-center rounded-[22px]"
            style={{
              background: "linear-gradient(135deg, rgba(99,102,241,0.25) 0%, rgba(139,92,246,0.15) 100%)",
              border: "1px solid rgba(99,102,241,0.4)",
              boxShadow: "0 0 40px rgba(79,70,229,0.4), inset 0 1px 0 rgba(255,255,255,0.1)",
            }}>
            <Mark size={44} />
            {/* Glow ring */}
            <div className="absolute inset-0 rounded-[22px] animate-ring" />
          </div>
        </div>

        <div className="mt-6 text-center animate-rise-sm" style={{ animationDelay: "0.15s" }}>
          <p className="text-[18px] font-bold tracking-tight text-white">Examina</p>
          <p className="mt-1 text-[13px] font-medium" style={{ color: "#8b8ba7" }}>{label}</p>
        </div>

        {/* Progress bar */}
        <div className="mt-7 h-[3px] w-48 overflow-hidden rounded-full animate-rise-sm"
          style={{ background: "rgba(255,255,255,0.08)", animationDelay: "0.2s" }}>
          <div className="skeleton h-full w-full rounded-full"
            style={{ background: "linear-gradient(90deg, #4f46e5, #818cf8, #4f46e5)" }} />
        </div>

        {/* Dots */}
        <div className="mt-5 flex items-center gap-2 animate-fade" style={{ animationDelay: "0.3s" }}>
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-1.5 w-1.5 rounded-full animate-glow-pulse"
              style={{
                background: i === 0 ? "#4f46e5" : "rgba(255,255,255,0.2)",
                animationDelay: `${i * 0.3}s`,
              }} />
          ))}
        </div>
      </div>

      {/* Bottom tagline */}
      <p className="absolute bottom-8 text-[11px] font-semibold uppercase tracking-[0.2em]"
        style={{ color: "#444466" }}>
        AI-Proctored Examination Platform
      </p>
    </div>
  );
}
