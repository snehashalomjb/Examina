"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { NextIntlClientProvider } from "next-intl";

import { localePrefs } from "@/lib/api";

export const SUPPORTED_LOCALES = ["en", "te", "hi", "ta", "ml", "kn"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

export const LOCALE_NAMES: Record<Locale, string> = {
  en: "English",
  te: "తెలుగు",
  hi: "हिन्दी",
  ta: "தமிழ்",
  ml: "മലയാളം",
  kn: "ಕನ್ನಡ",
};

const NAMESPACES = [
  "common",
  "auth",
  "dashboard",
  "exam",
  "question",
  "proctoring",
  "results",
  "performance",
  "admin",
  "examiner",
  "validation",
  "notifications",
  "grading",
  "profile",
  "dashboard-detail",
  "createExam",
  "examCategory",
] as const;

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Deep-merge `overrides` onto `base`, key by key. A locale bundle is missing a key ->
 * the English value underneath shows through instead of a raw "namespace.key" string or
 * a blank. This is what makes "fall back to English, never show the key" true for every
 * namespace, not just the ones a translator has fully finished. */
function deepMergeMessages(
  base: Record<string, unknown>,
  overrides: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...base };
  for (const [key, value] of Object.entries(overrides)) {
    const existing = out[key];
    out[key] =
      isPlainObject(value) && isPlainObject(existing) ? deepMergeMessages(existing, value) : value;
  }
  return out;
}

/** Dynamic per-namespace import so a viewer only ever downloads their own locale - plus
 * the English bundle, merged underneath, so a namespace that is only partially
 * translated still resolves every key (see `deepMergeMessages`). English itself skips
 * the extra fetch since it would just merge onto itself. */
async function loadMessages(locale: Locale): Promise<Record<string, unknown>> {
  async function loadLocale(loc: Locale): Promise<Record<string, unknown>> {
    const entries = await Promise.all(
      NAMESPACES.map(async (ns) => {
        try {
          const mod = await import(`../i18n/${loc}/${ns}.json`);
          return [ns, mod.default ?? mod] as const;
        } catch {
          return [ns, {}] as const;
        }
      }),
    );
    return Object.fromEntries(entries);
  }

  if (locale === "en") return loadLocale("en");
  const [en, target] = await Promise.all([loadLocale("en"), loadLocale(locale)]);
  return deepMergeMessages(en, target);
}

export function isSupportedLocale(value: string | null | undefined): value is Locale {
  return !!value && (SUPPORTED_LOCALES as readonly string[]).includes(value);
}

function detectInitialLocale(): Locale {
  const stored = localePrefs.get();
  if (isSupportedLocale(stored)) return stored;
  if (typeof navigator !== "undefined") {
    const browser = navigator.language?.split("-")[0];
    if (isSupportedLocale(browser)) return browser;
  }
  return "en";
}

interface LocaleState {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

const LocaleContext = createContext<LocaleState | null>(null);

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");
  const [messages, setMessages] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const initial = detectInitialLocale();
    setLocaleState(initial);
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadMessages(locale).then((loaded) => {
      if (!cancelled) setMessages(loaded);
    });
    return () => {
      cancelled = true;
    };
  }, [locale]);

  useEffect(() => {
    if (typeof document !== "undefined") document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    localePrefs.set(next);
  }, []);

  const value = useMemo(() => ({ locale, setLocale }), [locale, setLocale]);

  // Render children even before the first message bundle lands - the app has no
  // locale-prefixed routing to gate on, so blocking the whole tree on a fetch would
  // flash a blank page. `messages ?? {}` just means the very first paint may render a
  // raw key before the bundle resolves, same as a font swap.
  return (
    <LocaleContext.Provider value={value}>
      <NextIntlClientProvider
        locale={locale}
        messages={(messages ?? {}) as Record<string, never>}
        onError={() => {
          /* missing keys fall back to raw key text below rather than throwing */
        }}
        getMessageFallback={({ key }) => key}
      >
        {children}
      </NextIntlClientProvider>
    </LocaleContext.Provider>
  );
}

/** The current locale and setter, outside of next-intl's own hooks - for code (like
 * `auth.tsx`'s login reconciliation) that isn't a translated component itself. */
export function useLocale(): LocaleState {
  const context = useContext(LocaleContext);
  if (!context) throw new Error("useLocale must be used inside <LocaleProvider>");
  return context;
}
