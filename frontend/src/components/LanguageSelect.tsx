"use client";

import { Select } from "@/components/ui";
import { LOCALE_NAMES, SUPPORTED_LOCALES, type Locale } from "@/lib/locale";

/**
 * Content-language control for the question bank and question editor.
 *
 * The app already has a global UI-language switch. This is deliberately a separate
 * control: an examiner can browse the bank in Malayalam while the surrounding dashboard
 * stays in English, and the selected value is sent to the API as ``?lang=`` so subject
 * labels and question text resolve from the same locale.
 */
export function LanguageSelect({
  value,
  onChange,
  className = "",
  ariaLabel = "Content language",
  disabled = false,
}: {
  value: Locale;
  onChange: (locale: Locale) => void;
  className?: string;
  ariaLabel?: string;
  disabled?: boolean;
}) {
  return (
    <Select
      value={value}
      onChange={(event) => onChange(event.target.value as Locale)}
      className={className}
      aria-label={ariaLabel}
      disabled={disabled}
    >
      {SUPPORTED_LOCALES.map((locale) => (
        <option key={locale} value={locale}>
          {LOCALE_NAMES[locale]}
        </option>
      ))}
    </Select>
  );
}
