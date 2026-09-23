/**
 * Low-poly backdrop — v2.
 *
 * A fixed triangulated mesh rendered as inline SVG. Richer opacity and an optional
 * `glowing` prop that adds luminance to select accent facets for premium surfaces.
 */

type Variant = "hero" | "panel" | "corner";

const MESH: Record<Variant, { points: string; fill: string; opacity: number }[]> = {
  hero: [
    { points: "0,0 300,0 140,220",   fill: "#4f46e5", opacity: 0.10 },
    { points: "300,0 560,0 380,180", fill: "#0f9b8e", opacity: 0.08 },
    { points: "140,220 300,0 380,180", fill: "#4f46e5", opacity: 0.06 },
    { points: "560,0 800,0 700,260", fill: "#6366f1", opacity: 0.07 },
    { points: "380,180 560,0 700,260", fill: "#0ea5e9", opacity: 0.065 },
    { points: "0,0 140,220 0,320",   fill: "#818cf8", opacity: 0.07 },
    { points: "140,220 380,180 260,400", fill: "#0f9b8e", opacity: 0.055 },
    { points: "0,320 140,220 260,400", fill: "#4f46e5", opacity: 0.045 },
    { points: "380,180 700,260 520,420", fill: "#4f46e5", opacity: 0.06 },
    { points: "700,260 800,0 800,340", fill: "#0f9b8e", opacity: 0.07 },
    { points: "260,400 520,420 400,560", fill: "#6366f1", opacity: 0.045 },
    { points: "520,420 700,260 800,480", fill: "#0ea5e9", opacity: 0.05 },
    { points: "0,320 260,400 0,560",  fill: "#4f46e5", opacity: 0.04 },
    { points: "700,260 800,340 800,480", fill: "#818cf8", opacity: 0.045 },
    { points: "400,560 520,420 800,480", fill: "#4f46e5", opacity: 0.035 },
  ],
  panel: [
    { points: "0,0 260,0 120,150",   fill: "#4f46e5", opacity: 0.11 },
    { points: "260,0 480,0 340,130", fill: "#0f9b8e", opacity: 0.09 },
    { points: "120,150 260,0 340,130", fill: "#6366f1", opacity: 0.07 },
    { points: "0,0 120,150 0,240",   fill: "#818cf8", opacity: 0.08 },
    { points: "340,130 480,0 480,220", fill: "#0ea5e9", opacity: 0.07 },
    { points: "120,150 340,130 220,280", fill: "#4f46e5", opacity: 0.055 },
    { points: "0,240 120,150 220,280", fill: "#0f9b8e", opacity: 0.05 },
    { points: "220,280 340,130 480,220", fill: "#4f46e5", opacity: 0.045 },
  ],
  corner: [
    { points: "0,0 200,0 90,120",    fill: "#4f46e5", opacity: 0.14 },
    { points: "200,0 360,0 240,100", fill: "#0f9b8e", opacity: 0.11 },
    { points: "90,120 200,0 240,100", fill: "#6366f1", opacity: 0.09 },
    { points: "0,0 90,120 0,200",    fill: "#818cf8", opacity: 0.10 },
    { points: "240,100 360,0 360,180", fill: "#0ea5e9", opacity: 0.08 },
    { points: "90,120 240,100 160,220", fill: "#4f46e5", opacity: 0.065 },
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
          strokeOpacity={0.25}
          strokeWidth={0.6}
        />
      ))}
    </svg>
  );
}

/**
 * The platform mark: an open book with a bookmark ribbon.
 * Now features a subtle gradient on the cover for added depth.
 */
export function Mark({ size = 32, className = "" }: { size?: number; className?: string }) {
  const detailed = size >= 28;
  const id = `mark-grad-${size}`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <defs>
        <linearGradient id={id} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#818cf8" />
          <stop offset="100%" stopColor="#4f46e5" />
        </linearGradient>
      </defs>

      {/* Spine */}
      <rect x="18.3" y="10.8" width="3.4" height="23.2" rx="1.7" fill="#3730a3" />

      {/* Left page */}
      <path
        d="M19.3 12.4C15.4 9.9 10.8 8.7 5.8 8.9 5.2 8.9 4.7 9.4 4.7 10.1v17.9c0 .6.5 1.1 1.1 1.1 5-.2 9.6 1 13.5 3.5V12.4Z"
        fill="#818cf8"
      />
      {/* Right page */}
      <path
        d="M20.7 12.4c3.9-2.5 8.5-3.7 13.5-3.5.6 0 1.1.5 1.1 1.2v17.9c0 .6-.5 1.1-1.1 1.1-5-.2-9.6 1-13.5 3.5V12.4Z"
        fill={`url(#${id})`}
      />

      {detailed && (
        <>
          {/* Page rules */}
          <g stroke="#ffffff" strokeOpacity="0.55" strokeWidth="1.3" strokeLinecap="round">
            <path d="M8.2 15c2.4.2 4.6.8 6.8 1.9" />
            <path d="M8.2 19.6c2.4.2 4.6.8 6.8 1.9" />
            <path d="M8.2 24.2c2.4.2 4.6.8 6.8 1.9" />
            <path d="M31.8 15c-2.4.2-4.6.8-6.8 1.9" />
            <path d="M31.8 19.6c-2.4.2-4.6.8-6.8 1.9" />
            <path d="M31.8 24.2c-2.4.2-4.6.8-6.8 1.9" />
          </g>
          {/* Bookmark ribbon */}
          <path d="M26.9 6.6h4.4v8.6l-2.2-1.8-2.2 1.8V6.6Z" fill="#0f9b8e" />
        </>
      )}
    </svg>
  );
}

/**
 * Mark plus wordmark.
 */
export function Brand({
  size = 22,
  onDark = false,
  className = "",
}: {
  size?: number;
  onDark?: boolean;
  className?: string;
}) {
  return (
    <span className={`flex min-w-0 items-center gap-2.5 ${className}`}>
      <span
        className="flex shrink-0 items-center justify-center rounded-[10px] p-1.5"
        style={onDark
          ? { background: "linear-gradient(135deg, rgba(99,102,241,0.3), rgba(139,92,246,0.2))", border: "1px solid rgba(99,102,241,0.35)" }
          : { background: "linear-gradient(135deg, #eef2ff, #f5f3ff)", border: "1px solid rgba(99,102,241,0.2)" }
        }
      >
        <Mark size={size} />
      </span>
      <span
        className="truncate text-[14px] font-bold tracking-tight"
        style={onDark
          ? { color: "#ffffff" }
          : {
              background: "linear-gradient(135deg, #1e1b4b, #4f46e5)",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }
        }
      >
        Examina
      </span>
    </span>
  );
}
