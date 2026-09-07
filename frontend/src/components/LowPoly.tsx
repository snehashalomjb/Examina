/**
 * Low-poly backdrop.
 *
 * A fixed triangulated mesh rendered as inline SVG - no images, no runtime cost beyond
 * one paint. The facets are deterministic (hand-placed, not random) so the composition
 * stays balanced and the same on every render, and every fill is a low-opacity tint of
 * the accent palette so data laid over it always wins.
 */

type Variant = "hero" | "panel" | "corner";

const MESH: Record<Variant, { points: string; fill: string; opacity: number }[]> = {
  hero: [
    { points: "0,0 300,0 140,220", fill: "#4f46e5", opacity: 0.07 },
    { points: "300,0 560,0 380,180", fill: "#0f9b8e", opacity: 0.06 },
    { points: "140,220 300,0 380,180", fill: "#4f46e5", opacity: 0.04 },
    { points: "560,0 800,0 700,260", fill: "#6366f1", opacity: 0.05 },
    { points: "380,180 560,0 700,260", fill: "#0ea5e9", opacity: 0.045 },
    { points: "0,0 140,220 0,320", fill: "#818cf8", opacity: 0.05 },
    { points: "140,220 380,180 260,400", fill: "#0f9b8e", opacity: 0.035 },
    { points: "0,320 140,220 260,400", fill: "#4f46e5", opacity: 0.03 },
    { points: "380,180 700,260 520,420", fill: "#4f46e5", opacity: 0.04 },
    { points: "700,260 800,0 800,340", fill: "#0f9b8e", opacity: 0.05 },
    { points: "260,400 520,420 400,560", fill: "#6366f1", opacity: 0.03 },
    { points: "520,420 700,260 800,480", fill: "#0ea5e9", opacity: 0.035 },
    { points: "0,320 260,400 0,560", fill: "#4f46e5", opacity: 0.025 },
    { points: "700,260 800,340 800,480", fill: "#818cf8", opacity: 0.03 },
    { points: "400,560 520,420 800,480", fill: "#4f46e5", opacity: 0.022 },
  ],
  panel: [
    { points: "0,0 260,0 120,150", fill: "#4f46e5", opacity: 0.08 },
    { points: "260,0 480,0 340,130", fill: "#0f9b8e", opacity: 0.07 },
    { points: "120,150 260,0 340,130", fill: "#6366f1", opacity: 0.05 },
    { points: "0,0 120,150 0,240", fill: "#818cf8", opacity: 0.06 },
    { points: "340,130 480,0 480,220", fill: "#0ea5e9", opacity: 0.05 },
    { points: "120,150 340,130 220,280", fill: "#4f46e5", opacity: 0.04 },
    { points: "0,240 120,150 220,280", fill: "#0f9b8e", opacity: 0.035 },
    { points: "220,280 340,130 480,220", fill: "#4f46e5", opacity: 0.03 },
  ],
  corner: [
    { points: "0,0 200,0 90,120", fill: "#4f46e5", opacity: 0.1 },
    { points: "200,0 360,0 240,100", fill: "#0f9b8e", opacity: 0.08 },
    { points: "90,120 200,0 240,100", fill: "#6366f1", opacity: 0.06 },
    { points: "0,0 90,120 0,200", fill: "#818cf8", opacity: 0.07 },
    { points: "240,100 360,0 360,180", fill: "#0ea5e9", opacity: 0.055 },
    { points: "90,120 240,100 160,220", fill: "#4f46e5", opacity: 0.045 },
  ],
};

const VIEWBOX: Record<Variant, string> = {
  hero: "0 0 800 560",
  panel: "0 0 480 280",
  corner: "0 0 360 220",
};

export function LowPoly({
  variant = "hero",
  className = "",
  animate = false,
}: {
  variant?: Variant;
  className?: string;
  animate?: boolean;
}) {
  return (
    <svg
      viewBox={VIEWBOX[variant]}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
      className={`pointer-events-none select-none ${animate ? "animate-drift" : ""} ${className}`}
    >
      {MESH[variant].map((facet, index) => (
        <polygon
          key={index}
          points={facet.points}
          fill={facet.fill}
          fillOpacity={facet.opacity}
          stroke="#ffffff"
          strokeOpacity={0.35}
          strokeWidth={0.7}
        />
      ))}
    </svg>
  );
}

/**
 * The platform mark: an open book with a bookmark ribbon, drawn rather than imported.
 *
 * Flat fills, no gradients - two marks can sit on one page without colliding over a
 * shared `<defs>` id, and the shape stays readable at 16px in the sidebar. The page
 * rules and the ribbon are dropped below 28px, where they would only turn to mush.
 */
export function Mark({ size = 32, className = "" }: { size?: number; className?: string }) {
  const detailed = size >= 28;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      {/* Spine, drawn first so both pages meet over it. */}
      <rect x="18.3" y="10.8" width="3.4" height="23.2" rx="1.7" fill="#3730a3" />

      {/* Left page */}
      <path
        d="M19.3 12.4C15.4 9.9 10.8 8.7 5.8 8.9 5.2 8.9 4.7 9.4 4.7 10.1v17.9c0 .6.5 1.1 1.1 1.1 5-.2 9.6 1 13.5 3.5V12.4Z"
        fill="#818cf8"
      />
      {/* Right page - the darker half, so the book reads as lit from the left. */}
      <path
        d="M20.7 12.4c3.9-2.5 8.5-3.7 13.5-3.5.6 0 1.1.5 1.1 1.2v17.9c0 .6-.5 1.1-1.1 1.1-5-.2-9.6 1-13.5 3.5V12.4Z"
        fill="#4f46e5"
      />

      {detailed && (
        <>
          {/* Page rules */}
          <g stroke="#ffffff" strokeOpacity="0.5" strokeWidth="1.3" strokeLinecap="round">
            <path d="M8.2 15c2.4.2 4.6.8 6.8 1.9" />
            <path d="M8.2 19.6c2.4.2 4.6.8 6.8 1.9" />
            <path d="M8.2 24.2c2.4.2 4.6.8 6.8 1.9" />
            <path d="M31.8 15c-2.4.2-4.6.8-6.8 1.9" />
            <path d="M31.8 19.6c-2.4.2-4.6.8-6.8 1.9" />
            <path d="M31.8 24.2c-2.4.2-4.6.8-6.8 1.9" />
          </g>
          {/* Bookmark ribbon, the one non-indigo note in the mark. */}
          <path d="M26.9 6.6h4.4v8.6l-2.2-1.8-2.2 1.8V6.6Z" fill="#0f9b8e" />
        </>
      )}
    </svg>
  );
}

/**
 * Mark plus wordmark, one lockup for every chrome that shows the brand - sidebar,
 * mobile drawer, sign-in panel. Kept in one place so the name and the spacing cannot
 * drift apart across pages the way two spellings of it once did.
 */
export function Brand({
  size = 22,
  onDark = false,
  className = "",
}: {
  size?: number;
  /** Set on the dark sidebar and the sign-in brand panel. */
  onDark?: boolean;
  className?: string;
}) {
  return (
    <span className={`flex min-w-0 items-center gap-2.5 ${className}`}>
      <span
        className={`flex shrink-0 items-center justify-center rounded-[9px] p-1 ${
          onDark ? "bg-white/10" : "bg-accent-soft"
        }`}
      >
        <Mark size={size} />
      </span>
      <span
        className={`truncate text-[14px] font-bold tracking-tight ${
          onDark ? "text-white" : "text-ink"
        }`}
      >
        Examina
      </span>
    </span>
  );
}
