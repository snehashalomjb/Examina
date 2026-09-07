"use client";

/**
 * Smart Assess.ai — Shared UI Component Library v2
 *
 * Professional SaaS design system.
 * Components are composable, accessible, and consistent across all dashboards.
 */

import { forwardRef, useEffect, useRef, useState } from "react";

/* ═══════════════════════════════════════════════════════════════════
   UTILITIES
═══════════════════════════════════════════════════════════════════ */
export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

/* ═══════════════════════════════════════════════════════════════════
   SURFACES
═══════════════════════════════════════════════════════════════════ */

export function Card({
  children,
  className = "",
  padded = true,
  hover = false,
  variant = "default",
}: {
  children: React.ReactNode;
  className?: string;
  padded?: boolean;
  hover?: boolean;
  /** "default" = border + soft shadow | "elevated" = stronger shadow | "flat" = border only */
  variant?: "default" | "elevated" | "flat";
}) {
  const base = "rounded-[12px] bg-surface";
  const variants = {
    default: "border border-line shadow-[var(--shadow-card)]",
    elevated: "border border-line shadow-[var(--shadow-lift)]",
    flat: "border border-line",
  };
  return (
    <div
      className={cx(
        base,
        variants[variant],
        padded && "p-5",
        hover && "card-hover cursor-pointer",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SectionTitle({
  title,
  hint,
  action,
  size = "default",
}: {
  title: string;
  hint?: string;
  action?: React.ReactNode;
  size?: "default" | "lg";
}) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div>
        {size === "lg" ? (
          <h1 className="text-[22px] font-bold tracking-tight text-ink">{title}</h1>
        ) : (
          <h2 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h2>
        )}
        {hint && <p className="mt-0.5 text-[13px] text-ink-muted">{hint}</p>}
      </div>
      {action}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   STAT CARD
═══════════════════════════════════════════════════════════════════ */

export function StatCard({
  label,
  value,
  hint,
  tone = "accent",
  icon,
  trend,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: Tone;
  icon?: React.ReactNode;
  /** e.g. "+12% this month" */
  trend?: { value: string; up?: boolean };
}) {
  const bars: Record<Tone, string> = {
    accent: "bg-accent",
    green: "bg-green",
    amber: "bg-amber",
    rose: "bg-rose",
    mint: "bg-mint",
    neutral: "bg-line-strong",
    purple: "bg-purple-500",
  };
  const iconBg: Record<Tone, string> = {
    accent: "bg-accent-soft text-accent",
    green: "bg-green-soft text-green",
    amber: "bg-amber-soft text-amber",
    rose: "bg-rose-soft text-rose",
    mint: "bg-mint-soft text-mint",
    neutral: "bg-sunken text-ink-muted",
    purple: "bg-purple-100 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300",
  };
  return (
    <Card className="relative overflow-hidden">
      <span className={cx("absolute inset-x-0 top-0 h-0.5", bars[tone])} />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11.5px] font-semibold uppercase tracking-[0.06em] text-ink-muted">
            {label}
          </p>
          <p className="mt-2 text-[28px] font-bold leading-none tracking-tight text-ink animate-count">
            {value}
          </p>
          {trend && (
            <p
              className={cx(
                "mt-1.5 flex items-center gap-1 text-[12px] font-medium",
                trend.up !== false ? "text-green" : "text-rose",
              )}
            >
              <span>{trend.up !== false ? "↑" : "↓"}</span>
              {trend.value}
            </p>
          )}
          {hint && !trend && (
            <p className="mt-1 text-[12px] text-ink-muted">{hint}</p>
          )}
        </div>
        {icon && (
          <div className={cx("flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px]", iconBg[tone])}>
            {icon}
          </div>
        )}
      </div>
    </Card>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   BUTTONS
═══════════════════════════════════════════════════════════════════ */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "success";

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-[9px] font-medium transition-all " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent " +
  "disabled:cursor-not-allowed disabled:opacity-50 btn-press select-none";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-white hover:bg-accent-hover hover:shadow-[var(--shadow-button)] hover:-translate-y-[1px] " +
    "active:translate-y-0 active:shadow-none",
  secondary:
    "bg-surface text-ink border border-line-strong hover:bg-sunken hover:border-line-strong/80 " +
    "hover:-translate-y-[1px] hover:shadow-[var(--shadow-xs)]",
  ghost:
    "text-ink-soft hover:bg-sunken hover:text-ink",
  danger:
    "bg-rose text-white hover:brightness-[1.08] hover:-translate-y-[1px] hover:shadow-[0_2px_8px_-2px_rgba(220,38,38,0.3)]",
  success:
    "bg-green text-white hover:brightness-[1.06] hover:-translate-y-[1px] hover:shadow-[0_2px_8px_-2px_rgba(22,163,74,0.3)]",
};

const BUTTON_SIZE = {
  sm: "h-8 px-3 text-[13px]",
  md: "h-9 px-4 text-[13.5px]",
  lg: "h-11 px-5 text-[14px]",
};

export const Button = forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: ButtonVariant;
    size?: "sm" | "md" | "lg";
    loading?: boolean;
  }
>(function Button(
  { variant = "primary", size = "md", loading, className = "", children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cx(
        BUTTON_BASE,
        BUTTON_SIZE[size],
        BUTTON_STYLES[variant],
        className,
      )}
      {...rest}
    >
      {loading && <Spinner className="h-3.5 w-3.5" />}
      {children}
    </button>
  );
});

/* ═══════════════════════════════════════════════════════════════════
   FORM CONTROLS
═══════════════════════════════════════════════════════════════════ */

export function Field({
  label,
  hint,
  error,
  required,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center gap-1 text-[13px] font-medium text-ink-soft">
        {label}
        {required && <span className="text-rose">*</span>}
      </span>
      {children}
      {error ? (
        <span className="mt-1 flex items-center gap-1 text-[12px] text-rose">
          <span>⚠</span> {error}
        </span>
      ) : hint ? (
        <span className="mt-1 block text-[12px] text-ink-muted">{hint}</span>
      ) : null}
    </label>
  );
}

const CONTROL =
  "w-full rounded-[9px] border border-line-strong bg-surface px-3 text-[13.5px] text-ink " +
  "placeholder:text-ink-placeholder transition-all " +
  "focus:border-accent focus:outline-none focus:ring-3 focus:ring-accent/10 " +
  "disabled:bg-sunken disabled:text-ink-muted";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className = "", ...rest }, ref) {
    return <input ref={ref} className={cx(CONTROL, "h-9", className)} {...rest} />;
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className = "", ...rest }, ref) {
    return <textarea ref={ref} className={cx(CONTROL, "py-2.5 leading-relaxed", className)} {...rest} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className = "", children, ...rest }, ref) {
    return (
      <select ref={ref} className={cx(CONTROL, "h-9 pr-8", className)} {...rest}>
        {children}
      </select>
    );
  },
);

/* ═══════════════════════════════════════════════════════════════════
   BADGES
═══════════════════════════════════════════════════════════════════ */

export type Tone = "neutral" | "accent" | "green" | "mint" | "amber" | "rose" | "purple";

const BADGE_TONES: Record<Tone, string> = {
  neutral: "bg-sunken text-ink-soft border-line",
  accent: "bg-accent-soft text-accent-ink border-accent-border",
  green: "bg-green-soft text-green-ink border-green-border",
  mint: "bg-mint-soft text-mint border-mint/20",
  amber: "bg-amber-soft text-amber-ink border-amber/20",
  rose: "bg-rose-soft text-rose-ink border-rose/20",
  purple: "bg-purple-100 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300 border-purple-300 dark:border-purple-800",
};

export function Badge({
  children,
  tone = "neutral",
  className = "",
  size = "sm",
}: {
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
  size?: "xs" | "sm";
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-full border font-medium",
        size === "xs" ? "px-1.5 py-px text-[10px]" : "px-2 py-0.5 text-[11.5px]",
        BADGE_TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   INDICATORS
═══════════════════════════════════════════════════════════════════ */

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={cx("animate-spin", className)} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="2.5" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div className={cx("skeleton", className)} />;
}

export function ProgressBar({
  value,
  tone = "accent",
  animated = true,
  size = "sm",
}: {
  value: number;
  tone?: Tone;
  animated?: boolean;
  size?: "xs" | "sm" | "md";
}) {
  const fills: Record<Tone, string> = {
    neutral: "bg-ink-muted",
    accent: "bg-accent",
    green: "bg-green",
    mint: "bg-mint",
    amber: "bg-amber",
    rose: "bg-rose",
    purple: "bg-purple-600",
  };
  const heights = { xs: "h-1", sm: "h-1.5", md: "h-2" };
  return (
    <div className={cx("w-full overflow-hidden rounded-full bg-sunken", heights[size])}>
      <div
        className={cx(
          "h-full rounded-full transition-all duration-700 ease-out",
          fills[tone],
          animated && "animate-[progress-fill_0.8s_ease-out_both]",
        )}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   ALERTS
═══════════════════════════════════════════════════════════════════ */

export function Alert({
  tone = "amber",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children: React.ReactNode;
}) {
  const styles: Record<Tone, string> = {
    neutral: "border-line bg-sunken text-ink",
    accent: "border-accent-border bg-accent-soft text-accent-ink",
    green: "border-green-border bg-green-soft text-green-ink",
    mint: "border-mint/20 bg-mint-soft text-mint",
    amber: "border-amber/20 bg-amber-soft text-amber-ink",
    rose: "border-rose/20 bg-rose-soft text-rose-ink",
    purple: "border-purple-300 dark:border-purple-800 bg-purple-50 dark:bg-purple-950/30 text-purple-700 dark:text-purple-300",
  };
  const icons: Record<Tone, string> = {
    neutral: "ℹ",
    accent: "ℹ",
    green: "✓",
    mint: "✓",
    amber: "⚠",
    rose: "✕",
    purple: "💼",
  };
  return (
    <div className={cx("rounded-[10px] border px-4 py-3 text-[13px]", styles[tone])}>
      {title ? (
        <div className="flex items-start gap-2">
          <span className="mt-0.5 shrink-0 font-bold">{icons[tone]}</span>
          <div>
            <p className="font-semibold">{title}</p>
            <div className="mt-0.5 opacity-85">{children}</div>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-2">
          <span className="mt-0.5 shrink-0 font-bold">{icons[tone]}</span>
          <div className="opacity-90">{children}</div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   EMPTY STATE
═══════════════════════════════════════════════════════════════════ */

export function EmptyState({
  title,
  body,
  action,
  icon,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[14px] border border-dashed border-line-strong bg-surface/60 px-8 py-16 text-center">
      {icon ? (
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-[14px] bg-sunken text-ink-muted">
          {icon}
        </div>
      ) : (
        <div className="mb-4 h-12 w-12 rotate-6 rounded-[12px] border border-line bg-sunken" />
      )}
      <p className="text-[15px] font-semibold text-ink">{title}</p>
      <p className="mt-1.5 max-w-sm text-[13px] leading-relaxed text-ink-muted">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   MODAL
═══════════════════════════════════════════════════════════════════ */

export function Modal({
  open,
  onClose,
  title,
  children,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  const sizeClasses = {
    sm: "max-w-sm",
    md: "max-w-lg",
    lg: "max-w-2xl",
    xl: "max-w-4xl",
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      role="dialog"
      aria-modal="true"
    >
      <div
        className="absolute inset-0 bg-ink/50 backdrop-blur-[2px] animate-fade"
        onClick={onClose}
      />
      <div
        className={cx(
          "relative z-10 w-full rounded-[16px] bg-surface shadow-[var(--shadow-lift)] animate-scale-in",
          sizeClasses[size],
        )}
      >
        {title && (
          <div className="flex items-center justify-between border-b border-line px-6 py-4">
            <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
            <button
              onClick={onClose}
              className="rounded-[8px] p-1.5 text-ink-muted hover:bg-sunken hover:text-ink transition"
              aria-label="Close"
            >
              <CloseIcon />
            </button>
          </div>
        )}
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}

function CloseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════════════════════════ */

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { value: T; label: string; count?: number }[];
  active: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="flex items-center gap-1 rounded-[10px] border border-line bg-sunken p-1">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          onClick={() => onChange(tab.value)}
          className={cx(
            "flex items-center gap-1.5 rounded-[8px] px-3 py-1.5 text-[13px] font-medium transition-all",
            active === tab.value
              ? "bg-surface text-ink shadow-[var(--shadow-xs)]"
              : "text-ink-muted hover:text-ink",
          )}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span
              className={cx(
                "inline-flex h-4.5 min-w-[18px] items-center justify-center rounded-full px-1 text-[10px] font-semibold",
                active === tab.value ? "bg-accent text-white" : "bg-line text-ink-muted",
              )}
            >
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   DIVIDER
═══════════════════════════════════════════════════════════════════ */

export function Divider({ label }: { label?: string }) {
  if (!label) return <div className="my-4 border-t border-line" />;
  return (
    <div className="my-4 flex items-center gap-3">
      <div className="flex-1 border-t border-line" />
      <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">{label}</span>
      <div className="flex-1 border-t border-line" />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   TOASTS
═══════════════════════════════════════════════════════════════════ */

export interface Toast {
  id: number;
  message: string;
  tone: Tone;
}

let pushToast: ((message: string, tone?: Tone) => void) | null = null;

export function toast(message: string, tone: Tone = "neutral") {
  pushToast?.(message, tone);
}

export function ToastHost() {
  const [items, setItems] = useState<Toast[]>([]);

  useEffect(() => {
    pushToast = (message, tone = "neutral") => {
      const id = Date.now() + Math.random();
      setItems((current) => [...current, { id, message, tone }]);
      setTimeout(() => setItems((current) => current.filter((t) => t.id !== id)), 4500);
    };
    return () => { pushToast = null; };
  }, []);

  const toastStyles: Record<Tone, string> = {
    neutral: "border-line bg-surface text-ink",
    accent: "border-accent-border bg-accent-soft text-accent-ink",
    green: "border-green-border bg-green-soft text-green-ink",
    mint: "border-mint/20 bg-mint-soft text-mint",
    amber: "border-amber/20 bg-amber-soft text-amber-ink",
    rose: "border-rose/20 bg-rose-soft text-rose-ink",
    purple: "border-purple-300 dark:border-purple-800 bg-purple-50 dark:bg-purple-950/30 text-purple-700 dark:text-purple-300",
  };
  const toastIcons: Record<Tone, string> = {
    neutral: "ℹ", accent: "●", green: "✓", mint: "✓", amber: "⚠", rose: "✕", purple: "💼",
  };

  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-[200] flex w-[min(380px,calc(100vw-2.5rem))] flex-col gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          className={cx(
            "animate-slide-up pointer-events-auto flex items-center gap-3 rounded-[12px] border px-4 py-3 text-[13px] shadow-[var(--shadow-lift)]",
            toastStyles[item.tone],
          )}
        >
          <span className="shrink-0 font-bold">{toastIcons[item.tone]}</span>
          <span className="flex-1">{item.message}</span>
        </div>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   HELPERS
═══════════════════════════════════════════════════════════════════ */

export function formatDate(value: string | null | undefined, withTime = true): string {
  if (!value) return "—";
  const date = new Date(value);
  return date.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

export function formatDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

/* Legacy compat: Stat component (replaced by StatCard but kept for pages that import it) */
export function Stat({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: Tone;
}) {
  return <StatCard label={label} value={value} hint={hint} tone={tone} />;
}
