"use client";

/**
 * Examina — Shared UI Component Library v3
 *
 * Premium SaaS design system.
 * Components are composable, accessible, and consistent across all dashboards.
 * Features: gradient buttons, glowing stat cards, glassmorphism surfaces, premium toasts.
 */

import { forwardRef, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

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
  /** "default" = border + soft shadow | "elevated" = stronger shadow | "flat" = border only | "glow" = accent glow */
  variant?: "default" | "elevated" | "flat" | "glow";
}) {
  // min-w-0: a card is usually a grid or flex item, whose default minimum width is its
  // content's. A long truncated title would otherwise stop the card shrinking and push
  // the whole page wider than a phone screen.
  const base = "min-w-0 rounded-[14px] bg-surface";
  const variants = {
    default: "border border-line shadow-[var(--shadow-card)]",
    elevated: "border border-line shadow-[var(--shadow-lift)]",
    flat: "border border-line",
    glow: "border border-accent/20 shadow-[var(--shadow-card),0_0_32px_-8px_rgba(79,70,229,0.15)]",
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
          <h1 className="text-[23px] font-bold tracking-tight text-ink">{title}</h1>
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
  const gradients: Record<Tone, string> = {
    accent: "from-accent to-indigo-400",
    green: "from-green to-emerald-400",
    amber: "from-amber to-yellow-400",
    rose: "from-rose to-red-400",
    mint: "from-mint to-teal-400",
    neutral: "from-slate-400 to-slate-300",
    purple: "from-purple-600 to-violet-400",
  };
  const iconBg: Record<Tone, string> = {
    accent: "bg-accent/10 text-accent",
    green: "bg-green/10 text-green",
    amber: "bg-amber/10 text-amber",
    rose: "bg-rose/10 text-rose",
    mint: "bg-mint/10 text-mint",
    neutral: "bg-sunken text-ink-muted",
    purple: "bg-purple-100 text-purple-700",
  };
  const glows: Record<Tone, string> = {
    accent: "group-hover:shadow-[var(--shadow-glow-accent)]",
    green: "group-hover:shadow-[var(--shadow-glow-green)]",
    amber: "group-hover:shadow-[var(--shadow-glow-amber)]",
    rose: "group-hover:shadow-[var(--shadow-glow-rose)]",
    mint: "group-hover:shadow-[0_0_24px_-4px_rgba(13,148,136,0.35)]",
    neutral: "",
    purple: "group-hover:shadow-[0_0_24px_-4px_rgba(147,51,234,0.35)]",
  };
  return (
    <div className={cx("group relative overflow-hidden rounded-[14px] bg-surface border border-line shadow-[var(--shadow-card)] p-5 transition-all duration-300 hover:-translate-y-1", glows[tone])}>
      {/* Gradient top bar */}
      <span className={cx("absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r", gradients[tone])} />
      {/* Subtle background gradient tint */}
      <div className={cx("absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-[14px]", 
        tone === "accent" ? "bg-gradient-to-br from-accent/3 to-transparent" :
        tone === "green" ? "bg-gradient-to-br from-green/3 to-transparent" :
        tone === "rose" ? "bg-gradient-to-br from-rose/3 to-transparent" :
        tone === "amber" ? "bg-gradient-to-br from-amber/3 to-transparent" :
        "bg-gradient-to-br from-mint/3 to-transparent"
      )} />
      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-ink-muted">
            {label}
          </p>
          <p className="mt-2 text-[30px] font-bold leading-none tracking-tight text-ink animate-count">
            {value}
          </p>
          {trend && (
            <p
              className={cx(
                "mt-1.5 flex items-center gap-1 text-[12px] font-semibold",
                trend.up !== false ? "text-green" : "text-rose",
              )}
            >
              <span className="text-[10px]">{trend.up !== false ? "▲" : "▼"}</span>
              {trend.value}
            </p>
          )}
          {hint && !trend && (
            <p className="mt-1 text-[12px] text-ink-muted">{hint}</p>
          )}
        </div>
        {icon && (
          <div className={cx("flex h-11 w-11 shrink-0 items-center justify-center rounded-[12px] transition-transform duration-300 group-hover:scale-110", iconBg[tone])}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   BUTTONS
═══════════════════════════════════════════════════════════════════ */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "success";

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-[10px] font-semibold transition-all duration-200 " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent " +
  "disabled:cursor-not-allowed disabled:opacity-50 btn-press select-none";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary:
    "bg-gradient-to-r from-accent to-indigo-500 text-white btn-shimmer " +
    "hover:from-accent-hover hover:to-indigo-600 hover:shadow-[var(--shadow-button)] hover:-translate-y-[1px] " +
    "active:translate-y-0 active:shadow-none",
  secondary:
    "bg-surface text-ink border border-line-strong hover:bg-sunken hover:border-accent/30 " +
    "hover:-translate-y-[1px] hover:shadow-[var(--shadow-xs)]",
  ghost:
    "text-ink-soft hover:bg-sunken hover:text-ink",
  danger:
    "bg-gradient-to-r from-rose to-red-500 text-white btn-shimmer hover:-translate-y-[1px] " +
    "hover:shadow-[var(--shadow-glow-rose)] active:translate-y-0",
  success:
    "bg-gradient-to-r from-green to-emerald-500 text-white btn-shimmer hover:-translate-y-[1px] " +
    "hover:shadow-[var(--shadow-glow-green)] active:translate-y-0",
};

const BUTTON_SIZE = {
  sm: "h-8 px-3 text-[12.5px]",
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
      <span className="mb-1.5 flex items-center gap-1 text-[13px] font-semibold text-ink-soft">
        {label}
        {required && <span className="text-rose">*</span>}
      </span>
      {children}
      {error ? (
        <span className="mt-1.5 flex items-center gap-1.5 text-[12px] text-rose font-medium">
          <span className="text-[10px]">⚠</span> {error}
        </span>
      ) : hint ? (
        <span className="mt-1 block text-[12px] text-ink-muted">{hint}</span>
      ) : null}
    </label>
  );
}

const CONTROL =
  "w-full rounded-[10px] border border-line-strong bg-surface px-3.5 text-[13.5px] text-ink " +
  "placeholder:text-ink-placeholder transition-all duration-200 " +
  "focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/10 focus:shadow-[0_0_0_3px_rgba(79,70,229,0.08)] " +
  "disabled:bg-sunken disabled:text-ink-muted";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className = "", ...rest }, ref) {
    return <input ref={ref} className={cx(CONTROL, "h-10", className)} {...rest} />;
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
      <select ref={ref} className={cx(CONTROL, "h-10 pr-8", className)} {...rest}>
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
  accent:  "bg-accent-soft text-accent-ink border-accent-border",
  green:   "bg-green-soft text-green-ink border-green-border",
  mint:    "bg-mint-soft text-mint border-mint/25",
  amber:   "bg-amber-soft text-amber-ink border-amber/25",
  rose:    "bg-rose-soft text-rose-ink border-rose/25",
  purple:  "bg-purple-50 text-purple-700 border-purple-200",
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
  const dotColors: Record<Tone, string> = {
    neutral: "bg-slate-400",
    accent:  "bg-accent",
    green:   "bg-green",
    mint:    "bg-mint",
    amber:   "bg-amber",
    rose:    "bg-rose",
    purple:  "bg-purple-600",
  };
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border font-semibold",
        size === "xs" ? "px-1.5 py-px text-[10px]" : "px-2 py-0.5 text-[11px]",
        BADGE_TONES[tone],
        className,
      )}
    >
      <span className={cx("h-1.5 w-1.5 rounded-full shrink-0", dotColors[tone])} />
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
    accent:  "bg-gradient-to-r from-accent to-indigo-400",
    green:   "bg-gradient-to-r from-green to-emerald-400",
    mint:    "bg-gradient-to-r from-mint to-teal-400",
    amber:   "bg-gradient-to-r from-amber to-yellow-400",
    rose:    "bg-gradient-to-r from-rose to-red-400",
    purple:  "bg-gradient-to-r from-purple-600 to-violet-400",
  };
  const heights = { xs: "h-1", sm: "h-1.5", md: "h-2.5" };
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
    accent:  "border-accent-border bg-accent-soft text-accent-ink",
    green:   "border-green-border bg-green-soft text-green-ink",
    mint:    "border-mint/25 bg-mint-soft text-mint",
    amber:   "border-amber/25 bg-amber-soft text-amber-ink",
    rose:    "border-rose/25 bg-rose-soft text-rose-ink",
    purple:  "border-purple-200 bg-purple-50 text-purple-700",
  };
  const icons: Record<Tone, string> = {
    neutral: "ℹ", accent: "ℹ", green: "✓", mint: "✓",
    amber: "⚠", rose: "✕", purple: "💼",
  };
  return (
    <div className={cx("rounded-[11px] border px-4 py-3.5 text-[13px]", styles[tone])}>
      {title ? (
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 shrink-0 font-bold">{icons[tone]}</span>
          <div>
            <p className="font-semibold">{title}</p>
            <div className="mt-0.5 opacity-85">{children}</div>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-2.5">
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
    <div className="flex flex-col items-center justify-center rounded-[16px] border-2 border-dashed border-line bg-surface/60 px-8 py-16 text-center">
      {icon ? (
        <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-[16px] bg-accent-soft text-accent shadow-[var(--shadow-soft)]">
          {icon}
        </div>
      ) : (
        <div className="mb-5 h-14 w-14 rotate-6 rounded-[14px] border-2 border-line bg-sunken" />
      )}
      <p className="text-[16px] font-bold text-ink">{title}</p>
      <p className="mt-2 max-w-sm text-[13px] leading-relaxed text-ink-muted">{body}</p>
      {action && <div className="mt-6">{action}</div>}
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
  const tc = useTranslations("common");
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
        className="absolute inset-0 bg-ink/60 backdrop-blur-[3px] animate-fade"
        onClick={onClose}
      />
      <div
        className={cx(
          "relative z-10 w-full rounded-[18px] bg-surface shadow-[var(--shadow-lift)] animate-scale-in overflow-hidden",
          sizeClasses[size],
        )}
      >
        {/* Top gradient line */}
        <div className="h-[2px] bg-gradient-to-r from-accent via-purple-400 to-cyan-400" />
        {title && (
          <div className="flex items-center justify-between border-b border-line px-6 py-4">
            <h2 className="text-[15px] font-bold text-ink">{title}</h2>
            <button
              onClick={onClose}
              className="rounded-[8px] p-1.5 text-ink-muted hover:bg-sunken hover:text-ink transition"
              aria-label={tc("close")}
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
    <div className="flex items-center gap-1 rounded-[11px] border border-line bg-sunken p-1">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          onClick={() => onChange(tab.value)}
          className={cx(
            "flex items-center gap-1.5 rounded-[8px] px-3.5 py-1.5 text-[13px] font-semibold transition-all duration-200",
            active === tab.value
              ? "bg-surface text-ink shadow-[var(--shadow-xs)] shadow-sm"
              : "text-ink-muted hover:text-ink",
          )}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span
              className={cx(
                "inline-flex h-5 min-w-[20px] items-center justify-center rounded-full px-1 text-[10px] font-bold",
                active === tab.value ? "bg-accent text-white" : "bg-line-strong text-ink-muted",
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
      <span className="text-[11px] font-bold uppercase tracking-wider text-ink-muted">{label}</span>
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

  const leftBorders: Record<Tone, string> = {
    neutral: "border-l-slate-300",
    accent:  "border-l-accent",
    green:   "border-l-green",
    mint:    "border-l-mint",
    amber:   "border-l-amber",
    rose:    "border-l-rose",
    purple:  "border-l-purple-500",
  };
  const toastStyles: Record<Tone, string> = {
    neutral: "bg-surface border-line text-ink",
    accent:  "bg-white border-accent-border text-accent-ink",
    green:   "bg-white border-green-border text-green-ink",
    mint:    "bg-white border-mint/25 text-mint",
    amber:   "bg-white border-amber/25 text-amber-ink",
    rose:    "bg-white border-rose/25 text-rose-ink",
    purple:  "bg-white border-purple-200 text-purple-700",
  };
  const toastIcons: Record<Tone, string> = {
    neutral: "ℹ", accent: "●", green: "✓", mint: "✓", amber: "⚠", rose: "✕", purple: "💼",
  };

  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-[200] flex w-[min(390px,calc(100vw-2.5rem))] flex-col gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          className={cx(
            "animate-slide-up pointer-events-auto flex items-center gap-3 rounded-[13px] border border-l-4 px-4 py-3.5 text-[13px] shadow-[var(--shadow-lift)]",
            toastStyles[item.tone],
            leftBorders[item.tone],
          )}
        >
          <span className="shrink-0 font-bold text-[14px]">{toastIcons[item.tone]}</span>
          <span className="flex-1 font-medium">{item.message}</span>
        </div>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   HELPERS
═══════════════════════════════════════════════════════════════════ */

/** The active app locale, as `LocaleProvider` mirrors it onto `<html lang>`; undefined
 * (the runtime default) on the server or before it is set. */
function activeLocale(): string | undefined {
  if (typeof document === "undefined") return undefined;
  return document.documentElement.lang || undefined;
}

export function formatDate(value: string | null | undefined, withTime = true): string {
  if (!value) return "—";
  const date = new Date(value);
  return date.toLocaleString(activeLocale(), {
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

/* ═══════════════════════════════════════════════════════════════════
   COUNT-UP ANIMATION
═══════════════════════════════════════════════════════════════════ */
/** Animates a number from 0 → end over `duration` ms on first mount. */
export function CountUp({
  end,
  duration = 900,
  suffix = "",
  prefix = "",
}: {
  end: number;
  duration?: number;
  suffix?: string;
  prefix?: string;
}) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let start = 0;
    const step = Math.max(1, Math.ceil(end / 60));
    const interval = Math.round(duration / Math.max(1, end / step));
    const t = setInterval(() => {
      start += step;
      if (start >= end) { setDisplay(end); clearInterval(t); }
      else setDisplay(start);
    }, interval);
    return () => clearInterval(t);
  }, [end, duration]);
  return <>{prefix}{display.toLocaleString(activeLocale())}{suffix}</>;
}

/* ═══════════════════════════════════════════════════════════════════
   RING PROGRESS (SVG circular progress)
═══════════════════════════════════════════════════════════════════ */
export function RingProgress({
  value,
  size = 56,
  stroke = 5,
  tone = "accent",
  label,
}: {
  value: number; // 0–100
  size?: number;
  stroke?: number;
  tone?: Tone;
  label?: string;
}) {
  const r = (size - stroke * 2) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value));
  const dashoffset = circ * (1 - pct / 100);
  const strokeColors: Record<Tone, string> = {
    accent: "#4f46e5", green: "#16a34a", amber: "#d97706",
    rose: "#e11d48", mint: "#0d9488", neutral: "#94a3b8", purple: "#9333ea",
  };
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke="currentColor" strokeWidth={stroke} className="text-sunken" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={strokeColors[tone]} strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={dashoffset}
          style={{ transition: "stroke-dashoffset 0.9s cubic-bezier(.4,0,.2,1)" }}
        />
      </svg>
      {label !== undefined && (
        <span className="absolute text-[11px] font-bold text-ink">{label}</span>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   SPARKLINE (mini SVG line chart)
═══════════════════════════════════════════════════════════════════ */
export function Sparkline({
  data,
  width = 80,
  height = 32,
  tone = "accent",
}: {
  data: number[];
  width?: number;
  height?: number;
  tone?: Tone;
}) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const xStep = width / (data.length - 1);
  const points = data
    .map((v, i) => `${i * xStep},${height - ((v - min) / range) * (height - 6) - 3}`)
    .join(" ");
  const strokeColors: Partial<Record<Tone, string>> = {
    accent: "#4f46e5", green: "#16a34a", amber: "#d97706", rose: "#e11d48", mint: "#0d9488",
  };
  const color = strokeColors[tone] ?? "#4f46e5";
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* last point dot */}
      {(() => {
        const last = data[data.length - 1];
        const lx = (data.length - 1) * xStep;
        const ly = height - ((last - min) / range) * (height - 6) - 3;
        return <circle cx={lx} cy={ly} r="3" fill={color} />;
      })()}
    </svg>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   COUNTDOWN (live ticking timer)
═══════════════════════════════════════════════════════════════════ */
/** Counts down from a target ISO datetime string. Returns "—" when expired. */
export function Countdown({
  target,
  onExpire,
}: {
  target: string | null | undefined;
  onExpire?: () => void;
}) {
  const t = useTranslations("adminShell");
  const expiredLabel = t("countdown_expired");
  const [remaining, setRemaining] = useState("");
  useEffect(() => {
    if (!target) { setRemaining("—"); return; }
    const tick = () => {
      const diff = new Date(target).getTime() - Date.now();
      if (diff <= 0) { setRemaining(expiredLabel); onExpire?.(); return; }
      const h = Math.floor(diff / 3_600_000);
      const m = Math.floor((diff % 3_600_000) / 60_000);
      const s = Math.floor((diff % 60_000) / 1_000);
      const pad = (n: number) => String(n).padStart(2, "0");
      setRemaining(h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`);
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [target, onExpire, expiredLabel]);
  return <>{remaining}</>;
}

/* ═══════════════════════════════════════════════════════════════════
   STATUS DOT (animated health indicator)
═══════════════════════════════════════════════════════════════════ */
export function StatusDot({
  tone = "green",
  pulse = true,
  label,
}: {
  tone?: "green" | "amber" | "rose" | "neutral";
  pulse?: boolean;
  label?: string;
}) {
  const colors = { green: "bg-green", amber: "bg-amber", rose: "bg-rose", neutral: "bg-ink-muted" };
  const pingColors = { green: "bg-green", amber: "bg-amber", rose: "bg-rose", neutral: "bg-ink-muted" };
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative inline-flex h-2 w-2">
        {pulse && (
          <span className={cx("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", pingColors[tone])} />
        )}
        <span className={cx("relative inline-flex h-2 w-2 rounded-full", colors[tone])} />
      </span>
      {label && <span className="text-[12px] font-medium text-ink-soft">{label}</span>}
    </span>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   KPI BANNER (hero stats strip)
═══════════════════════════════════════════════════════════════════ */
export function KPIBanner({
  items,
}: {
  items: {
    label: string;
    value: number;
    suffix?: string;
    prefix?: string;
    tone?: Tone;
    trend?: { value: string; up?: boolean };
  }[];
}) {
  const gradients: Record<Tone, string> = {
    accent: "from-accent/10 to-indigo-400/5",
    green:  "from-green/10 to-emerald-400/5",
    amber:  "from-amber/10 to-yellow-400/5",
    rose:   "from-rose/10 to-red-400/5",
    mint:   "from-mint/10 to-teal-400/5",
    neutral:"from-slate-400/10 to-transparent",
    purple: "from-purple-600/10 to-violet-400/5",
  };
  const topBar: Record<Tone, string> = {
    accent: "from-accent to-indigo-400",
    green:  "from-green to-emerald-400",
    amber:  "from-amber to-yellow-400",
    rose:   "from-rose to-red-400",
    mint:   "from-mint to-teal-400",
    neutral:"from-slate-400 to-slate-300",
    purple: "from-purple-600 to-violet-400",
  };
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {items.map((item, i) => {
        const tone = item.tone ?? "accent";
        return (
          <div
            key={i}
            className={cx(
              "relative overflow-hidden rounded-[14px] border border-line bg-gradient-to-br p-4 shadow-[var(--shadow-card)]",
              gradients[tone],
            )}
          >
            <span className={cx("absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r", topBar[tone])} />
            <p className="text-[10.5px] font-bold uppercase tracking-[0.1em] text-ink-muted">{item.label}</p>
            <p className="mt-2 text-[26px] font-extrabold leading-none tracking-tight text-ink">
              <CountUp end={item.value} prefix={item.prefix} suffix={item.suffix} />
            </p>
            {item.trend && (
              <p className={cx("mt-1 text-[11px] font-semibold flex items-center gap-0.5",
                item.trend.up !== false ? "text-green" : "text-rose")}>
                <span className="text-[9px]">{item.trend.up !== false ? "▲" : "▼"}</span>
                {item.trend.value}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   TIMELINE CARD (activity feed item)
═══════════════════════════════════════════════════════════════════ */
export function TimelineCard({
  icon,
  title,
  subtitle,
  time,
  tone = "neutral",
  last = false,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  time?: string;
  tone?: Tone;
  last?: boolean;
}) {
  const dotBg: Record<Tone, string> = {
    neutral: "bg-sunken border-line",
    accent:  "bg-accent-soft border-accent-border",
    green:   "bg-green-soft border-green-border",
    mint:    "bg-mint-soft border-mint/25",
    amber:   "bg-amber-soft border-amber/25",
    rose:    "bg-rose-soft border-rose/25",
    purple:  "bg-purple-50 border-purple-200",
  };
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div className={cx("flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-[13px]", dotBg[tone])}>
          {icon}
        </div>
        {!last && <div className="mt-1 w-px flex-1 bg-line min-h-[20px]" />}
      </div>
      <div className="pb-4 min-w-0 flex-1">
        <p className="text-[13px] font-semibold text-ink leading-snug">{title}</p>
        {subtitle && <p className="mt-0.5 text-[12px] text-ink-muted truncate">{subtitle}</p>}
        {time && <p className="mt-1 text-[11px] text-ink-muted">{time}</p>}
      </div>
    </div>
  );
}
