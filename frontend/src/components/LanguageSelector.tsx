"use client";

import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth";
import { LOCALE_NAMES, SUPPORTED_LOCALES, useLocale } from "@/lib/locale";

/**
 * The global language switch: 🌐 + the current language's own name, opening a list of
 * every supported language in its own script. Calling `changeLocale` updates the whole
 * app instantly (no reload - see `LocaleProvider`) and persists the choice for a signed-in
 * user, so it follows them across devices.
 */
export function LanguageSelector({
  className = "",
  variant = "light",
}: {
  className?: string;
  /** "dark" for placement on the dark sidebar/top-nav, where default text is near-invisible. */
  variant?: "light" | "dark";
}) {
  const { locale } = useLocale();
  const { changeLocale } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Select language"
        className="flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors"
        style={
          variant === "dark"
            ? { borderColor: "rgba(255,255,255,0.18)", color: "var(--color-sidebar-text, #8b8ba7)" }
            : { borderColor: "var(--color-border, #e5e7eb)" }
        }
      >
        <span aria-hidden="true">🌐</span>
        <span className="whitespace-nowrap">{LOCALE_NAMES[locale]}</span>
        <span aria-hidden="true" className="text-xs opacity-60">▾</span>
      </button>
      {open && (
        <ul
          role="listbox"
          aria-label="Available languages"
          className="absolute right-0 z-50 mt-2 min-w-[10rem] overflow-hidden rounded-xl border bg-white py-1 shadow-lg"
          style={{ borderColor: "var(--color-border, #e5e7eb)" }}
        >
          {SUPPORTED_LOCALES.map((code) => (
            <li key={code} role="option" aria-selected={code === locale}>
              <button
                type="button"
                onClick={() => {
                  changeLocale(code);
                  setOpen(false);
                }}
                className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-black/5"
                style={code === locale ? { fontWeight: 600, background: "rgba(0,0,0,0.04)" } : undefined}
              >
                <span className="whitespace-normal break-words">{LOCALE_NAMES[code]}</span>
                {code === locale && <span aria-hidden="true">✓</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
