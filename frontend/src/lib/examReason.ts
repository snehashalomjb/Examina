import type { CandidateExamCard } from "@/lib/types";

/**
 * `CandidateExamCard.reason_code` → an `exam` namespace key.
 *
 * The API sends both `reason_code` (stable) and `reason` (a fixed English sentence). The
 * code decides the message, so a translated UI never shows English prose. Before this,
 * the dashboard matched on that prose with `reason.startsWith("Opens")` to decide whether
 * to show a countdown - which silently failed in every non-English locale, and would break
 * if the sentence were ever reworded.
 */
export const REASON_KEY: Record<string, string> = {
  in_progress: "reason_in_progress",
  already_attempted: "reason_already_attempted",
  not_published: "reason_not_published",
  opens_later: "reason_opens_later",
  window_closed: "reason_window_closed",
};

type Translator = (key: string, values?: Record<string, string | number>) => string;

/**
 * Why this exam cannot be started, in the viewer's language.
 *
 * Falls back to the server's English `reason` when the code is absent (an older server) or
 * unfamiliar (a newer one), so a missing key degrades to English rather than to nothing.
 */
export function examReasonText(
  card: CandidateExamCard,
  t: Translator,
  formatDate: (value: string) => string,
): string | null {
  const key = card.reason_code ? REASON_KEY[card.reason_code] : undefined;
  if (!key) return card.reason;
  return t(key, { date: formatDate(card.starts_at) });
}
