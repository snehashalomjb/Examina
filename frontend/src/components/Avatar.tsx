import { initials } from "@/components/ui";

/** Photo if the user has uploaded one, initials tile otherwise. Used in the sidebar,
 * header, profile and anywhere a user is named. */
export function Avatar({
  name,
  size = 34,
  src,
  className = "",
  shape = "rounded",
}: {
  name: string;
  size?: number;
  src?: string | null;
  className?: string;
  /** "rounded" = soft square corners (default) | "circle" = fully round */
  shape?: "rounded" | "circle";
}) {
  const radius = shape === "circle" ? "rounded-full" : "rounded-[10px]";

  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- presigned, short-lived URL; not worth Next/Image's remote-pattern config for it.
      <img
        src={src}
        alt={name}
        className={`inline-block shrink-0 ${radius} object-cover ${className}`}
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center ${radius} bg-accent-soft font-semibold text-accent-ink ${className}`}
      style={{ width: size, height: size, fontSize: Math.max(11, Math.round(size * 0.36)) }}
    >
      {initials(name)}
    </span>
  );
}
