"use client";

/**
 * Pick an existing subject, or type one that doesn't exist yet and create it inline.
 *
 * Subjects are a centralised entity (``app/db/models/question.py::Subject``) shared by
 * exams, the question bank, sections, questions, results and performance reports - so
 * creating one here is exactly the same POST /subjects the question bank's "Manage
 * Subjects" screen uses. The only thing this component adds is not making the examiner
 * leave the exam wizard to do it.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { cx } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Subject } from "@/lib/types";

/** "Cloud Computing" -> "CLOUD-COMPUTING", deduped against codes already in use. */
function codeFor(name: string, existing: Set<string>): string {
  const base = name
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 28) || "SUBJECT";
  if (!existing.has(base)) return base;
  let suffix = 2;
  while (existing.has(`${base}-${suffix}`)) suffix += 1;
  return `${base}-${suffix}`;
}

export function SubjectCombobox({
  subjects,
  value,
  onChange,
  onCreated,
}: {
  subjects: Subject[];
  value: string;
  onChange: (subjectId: string) => void;
  onCreated: (subject: Subject) => void;
}) {
  const selected = subjects.find((s) => s.id === value) ?? null;
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onClickAway(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, []);

  const needle = query.trim().toLowerCase();
  const filtered = useMemo(
    () =>
      needle
        ? subjects.filter(
            (s) => s.name.toLowerCase().includes(needle) || s.code.toLowerCase().includes(needle),
          )
        : subjects,
    [subjects, needle],
  );
  // Case-insensitive exact match - typing what already exists selects it, never
  // duplicates it, whichever case the examiner happens to use.
  const exactMatch = subjects.find((s) => s.name.toLowerCase() === needle);
  const canCreate = needle.length >= 2 && !exactMatch;

  function pick(subject: Subject) {
    onChange(subject.id);
    setQuery("");
    setOpen(false);
    setError(null);
  }

  async function createAndSelect() {
    const name = query.trim();
    if (!name) return;
    setCreating(true);
    setError(null);
    try {
      const existingCodes = new Set(subjects.map((s) => s.code));
      const created = await api.post<Subject>("/subjects", {
        code: codeFor(name, existingCodes),
        name,
      });
      onCreated(created);
      pick(created);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create that subject.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cx(
          "flex w-full items-center justify-between rounded-lg border border-line bg-surface px-3 py-2 text-left text-[13.5px] text-ink transition",
          "hover:border-line-strong focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20",
        )}
      >
        <span className={selected ? "text-ink" : "text-ink-muted"}>
          {selected ? `${selected.code} — ${selected.name}` : "Search or enter subject…"}
        </span>
        <span className="text-ink-muted">▾</span>
      </button>

      {open && (
        <div className="absolute z-20 mt-1.5 w-full overflow-hidden rounded-lg border border-line bg-surface shadow-[var(--shadow-lift)]">
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && canCreate) void createAndSelect();
              if (e.key === "Escape") setOpen(false);
            }}
            placeholder="Search or type a new subject…"
            className="w-full border-b border-line px-3 py-2 text-[13.5px] text-ink outline-none"
          />
          <ul className="max-h-56 overflow-y-auto py-1">
            {filtered.map((subject) => (
              <li key={subject.id}>
                <button
                  type="button"
                  onClick={() => pick(subject)}
                  className={cx(
                    "block w-full px-3 py-2 text-left text-[13px] transition hover:bg-sunken",
                    subject.id === value && "bg-accent-soft text-accent-ink",
                  )}
                >
                  {subject.code} — {subject.name}
                </button>
              </li>
            ))}
            {!filtered.length && !canCreate && (
              <li className="px-3 py-2 text-[12.5px] text-ink-muted">No subjects match.</li>
            )}
            {canCreate && (
              <li>
                <button
                  type="button"
                  disabled={creating}
                  onClick={() => void createAndSelect()}
                  className="block w-full px-3 py-2 text-left text-[13px] font-medium text-accent transition hover:bg-accent-soft disabled:opacity-60"
                >
                  {creating ? "Adding…" : `+ Add "${query.trim()}"`}
                </button>
              </li>
            )}
          </ul>
          {error && <p className="border-t border-line px-3 py-2 text-[12px] text-rose">{error}</p>}
        </div>
      )}
    </div>
  );
}
