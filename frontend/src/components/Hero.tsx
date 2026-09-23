import { LowPoly } from "@/components/LowPoly";
import { cx } from "@/components/ui";

/** Page header band — premium gradient version with ambient glow. */
export function Hero({
  title,
  body,
  action,
  compact,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
  /** Tighter padding for pages with a lot below the fold, so 100% zoom fits without scroll. */
  compact?: boolean;
}) {
  return (
    <div
      className={cx(
        "relative overflow-hidden rounded-[18px]",
        compact ? "px-5 py-4 sm:px-6 sm:py-5" : "px-6 py-6 sm:px-7 sm:py-7",
      )}
      style={{
        background: "linear-gradient(135deg, #f8f9ff 0%, #eef2ff 40%, #f5f3ff 100%)",
        border: "1px solid rgba(99,102,241,0.15)",
        boxShadow: "0 0 0 1px rgba(99,102,241,0.05), 0 4px 24px -4px rgba(79,70,229,0.08), 0 1px 3px rgba(13,17,23,0.06)",
      }}>

      {/* Ambient accent glow */}
      <div className="absolute -top-12 -left-12 h-48 w-48 rounded-full"
        style={{
          background: "radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)",
        }} />

      {/* Geometric facets on right */}
      <LowPoly
        variant="corner"
        className="absolute right-0 top-0 hidden h-full w-[42%] opacity-80 sm:block"
      />

      <div className="relative flex flex-wrap items-end justify-between gap-5">
        <div className="max-w-xl">
          <h1 className="text-[21px] font-bold tracking-tight sm:text-[24px]"
            style={{
              background: "linear-gradient(135deg, #1e1b4b 0%, #4f46e5 60%, #7c3aed 100%)",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}>
            {title}
          </h1>
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink-soft">
            {body}
          </p>
        </div>
        {action}
      </div>
    </div>
  );
}
