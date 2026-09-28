/**
 * Locale data that is not React state.
 *
 * Deliberately separate from `locale.tsx`, which is a `"use client"` context provider.
 * Pure constants imported from a provider module drag the whole provider into every
 * consumer, and tie plain data to a module that must evaluate first. The `Locale`
 * import below is type-only, so this file has no runtime dependencies at all.
 */

import type { Locale } from "@/lib/locale";

/**
 * English names for each locale, mirroring `LOCALE_LABELS` in
 * `app/services/translation/base.py` so both ends call a language the same thing.
 *
 * `LOCALE_NAMES` is each language's *own* name, which is what a language switcher
 * should show someone who reads that script. This is for the places that describe a
 * language rather than offer it - chiefly the "Exam Language" dropdown, where an
 * examiner scanning for "Tamil" should see the word Tamil.
 */
export const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  hi: "Hindi",
  kn: "Kannada",
  ml: "Malayalam",
  te: "Telugu",
  ta: "Tamil",
};

/**
 * The Exam Language options, in the order the wizard lists them. A deliberate subset
 * of `SUPPORTED_LOCALES` in a deliberate order - English first as the fallback, then
 * the five Indian languages alphabetically.
 */
export const EXAM_LANGUAGES = [
  "en",
  "hi",
  "kn",
  "ml",
  "te",
  "ta",
] as const satisfies readonly Locale[];

/**
 * The subject-code display prefix for a non-English Question Bank language, e.g. a
 * shared subject "CS203" reads as "HIN-CS203" when Hindi is the exam language. Purely
 * a label - the underlying `subject_id` never changes, and English carries no prefix.
 */
export const LANGUAGE_SUBJECT_PREFIX: Record<Locale, string> = {
  en: "",
  hi: "HIN-",
  kn: "KA-",
  ml: "MAL-",
  te: "TEL-",
  ta: "TAM-",
};

/**
 * Prefixes a subject's code for display in the given exam language, without touching
 * the code that's actually submitted/stored anywhere. A subject already minted with
 * its own language-specific code (e.g. "KA-AI", "HIN-CN", "MAL-CC") is left alone -
 * re-prefixing it would show "KA-KA-AI".
 */
export function displaySubjectCode(code: string, language: Locale): string {
  const prefix = LANGUAGE_SUBJECT_PREFIX[language];
  if (!prefix || code.startsWith(prefix)) return code;
  return `${prefix}${code}`;
}
