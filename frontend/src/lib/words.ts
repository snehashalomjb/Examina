/**
 * Word counting, kept deliberately in step with the server.
 *
 * The backend counts with `[^\W_]+(?:['’-][^\W_]+)*` under Python's Unicode rules
 * (app/services/text_metrics.py). This is the same rule written in JS: a word is a run of
 * letters, digits or combining marks, with internal apostrophes and hyphens kept whole.
 *
 * They must agree. If the counter in the runner says 249 and the API refuses the save at
 * 251, the candidate has no way to understand what happened - so the two implementations
 * are written to the same definition and the server's count is echoed back on every save
 * to correct any drift.
 */

const WORD_RE = /[\p{L}\p{N}\p{M}]+(?:['’\-][\p{L}\p{N}\p{M}]+)*/gu;

export function countWords(text: string | null | undefined): number {
  if (!text) return 0;
  return text.match(WORD_RE)?.length ?? 0;
}

export interface WordBounds {
  min_words: number | null;
  max_words: number | null;
}

export type WordState = "none" | "under" | "ok" | "over";

/**
 * How a count sits against the question's bounds.
 *
 * `under` is not an error while the candidate is still writing - the server accepts short
 * answers on autosave and only reports the shortfall to the examiner. `over` is, because
 * the save will be refused.
 */
export function wordState(count: number, bounds: WordBounds): WordState {
  if (count === 0) return "none";
  if (bounds.max_words != null && count > bounds.max_words) return "over";
  if (bounds.min_words != null && count < bounds.min_words) return "under";
  return "ok";
}

/** The line under the textarea: "128 words", "128 / 300 words", "128 words · 22 to go". */
export function wordLabel(count: number, bounds: WordBounds): string {
  const noun = count === 1 ? "word" : "words";
  if (bounds.max_words != null) {
    const over = count - bounds.max_words;
    const suffix = over > 0 ? ` · ${over} over the limit` : "";
    return `${count} / ${bounds.max_words} ${noun}${suffix}`;
  }
  if (bounds.min_words != null && count > 0 && count < bounds.min_words) {
    return `${count} ${noun} · ${bounds.min_words - count} to reach the minimum`;
  }
  return `${count} ${noun}`;
}
