import { initials } from "@/components/ui";

/** Initials tile. Used in the sidebar, profile and anywhere a user is named. */
export function Avatar({ name, size = 34 }: { name: string; size?: number }) {
  return (
    <span
      className="inline-flex items-center justify-center rounded-[10px] bg-accent-soft font-semibold text-accent-ink"
      style={{ width: size, height: size, fontSize: Math.max(11, Math.round(size * 0.36)) }}
    >
      {initials(name)}
    </span>
  );
}
