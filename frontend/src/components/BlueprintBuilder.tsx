"use client";

/**
 * "Python MCQ Medium 10, SQL MCQ Medium 10, Logical Reasoning MCQ 5" - one table instead
 * of search-the-bank-then-add-one-at-a-time plus hand-writing a matching selection rule.
 *
 * Each row becomes one exam section with a rule to match, and every bank question
 * meeting the row's criteria is pulled into the pool unpinned - see the ``/blueprint``
 * endpoint for what "unpinned" buys: the section's rule randomly draws ``count`` of them
 * per candidate, same as an examiner pinning them in one at a time would.
 */

import { useState } from "react";

import { Badge, Button, Field, Input, Select, cx } from "@/components/ui";
import { CATEGORY_LABEL, QUESTION_TYPE_LABEL } from "@/lib/types";
import type {
  BlueprintRow,
  BlueprintRowResult,
  Difficulty,
  QuestionCategory,
  QuestionType,
  Subject,
} from "@/lib/types";

type DraftRow = BlueprintRow & { tagsText: string };

function emptyRow(): DraftRow {
  return { title: "", question_type: "mcq", count: 10, tagsText: "" };
}

export function BlueprintBuilder({
  subjects,
  onApply,
}: {
  subjects: Subject[];
  onApply: (rows: BlueprintRow[]) => Promise<BlueprintRowResult[] | null>;
}) {
  const [rows, setRows] = useState<DraftRow[]>([emptyRow()]);
  const [results, setResults] = useState<BlueprintRowResult[] | null>(null);
  const [busy, setBusy] = useState(false);

  function updateRow(index: number, patch: Partial<DraftRow>) {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  function addRow() {
    setRows((prev) => [...prev, emptyRow()]);
  }

  function removeRow(index: number) {
    setRows((prev) => prev.filter((_, i) => i !== index));
  }

  const valid = rows.length > 0 && rows.every((r) => r.title.trim() && r.count > 0);

  async function generate() {
    setBusy(true);
    setResults(null);
    try {
      const payload: BlueprintRow[] = rows.map((row) => ({
        title: row.title.trim(),
        subject_id: row.subject_id || null,
        category: row.category || null,
        question_type: row.question_type,
        difficulty: row.difficulty || null,
        topic: row.topic?.trim() || null,
        tags: row.tagsText
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        count: row.count,
      }));
      const outcome = await onApply(payload);
      setResults(outcome);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-[12.5px] text-ink-muted">
        Name what you want - a subject, a type, a difficulty and a count - and the pool
        fills itself from the bank. Leave a field blank to mean &ldquo;any&rdquo;.
      </p>

      <div className="space-y-2">
        {rows.map((row, index) => (
          <div
            key={index}
            className="grid grid-cols-2 gap-2 rounded-[10px] border border-line bg-surface p-3 sm:grid-cols-3 lg:grid-cols-7"
          >
            <Field label="Section title">
              <Input
                value={row.title}
                onChange={(e) => updateRow(index, { title: e.target.value })}
                placeholder="e.g. Python"
              />
            </Field>
            <Field label="Subject">
              <Select
                value={row.subject_id ?? ""}
                onChange={(e) => updateRow(index, { subject_id: e.target.value || undefined })}
              >
                <option value="">Any subject</option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>{s.code}</option>
                ))}
              </Select>
            </Field>
            <Field label="Category">
              <Select
                value={row.category ?? ""}
                onChange={(e) =>
                  updateRow(index, { category: (e.target.value || undefined) as QuestionCategory })
                }
              >
                <option value="">Any category</option>
                {(Object.keys(CATEGORY_LABEL) as QuestionCategory[]).map((value) => (
                  <option key={value} value={value}>{CATEGORY_LABEL[value]}</option>
                ))}
              </Select>
            </Field>
            <Field label="Type">
              <Select
                value={row.question_type}
                onChange={(e) => updateRow(index, { question_type: e.target.value as QuestionType })}
              >
                {(Object.keys(QUESTION_TYPE_LABEL) as QuestionType[]).map((value) => (
                  <option key={value} value={value}>{QUESTION_TYPE_LABEL[value]}</option>
                ))}
              </Select>
            </Field>
            <Field label="Difficulty">
              <Select
                value={row.difficulty ?? ""}
                onChange={(e) =>
                  updateRow(index, { difficulty: (e.target.value || undefined) as Difficulty })
                }
              >
                <option value="">Any</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </Select>
            </Field>
            <Field label="Tags">
              <Input
                value={row.tagsText}
                onChange={(e) => updateRow(index, { tagsText: e.target.value })}
                placeholder="OOP, Classes"
              />
            </Field>
            <div className="flex items-end gap-1.5">
              <Field label="Count">
                <Input
                  type="number"
                  min={1}
                  value={row.count}
                  onChange={(e) => updateRow(index, { count: Number(e.target.value) || 0 })}
                />
              </Field>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="text-rose hover:bg-rose-soft"
                onClick={() => removeRow(index)}
                disabled={rows.length === 1}
              >
                ✕
              </Button>
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="secondary" size="sm" onClick={addRow}>
          + Add row
        </Button>
        <Button type="button" size="sm" disabled={!valid} loading={busy} onClick={() => void generate()}>
          Generate from Question Bank
        </Button>
      </div>

      {results && (
        <ul className="space-y-1.5">
          {results.map((result) => {
            const short = result.added < result.requested;
            return (
              <li
                key={result.section_id}
                className={cx(
                  "flex items-center justify-between gap-3 rounded-[9px] border px-3 py-2 text-[13px]",
                  short ? "border-amber/30 bg-amber-soft" : "border-mint/30 bg-mint-soft",
                )}
              >
                <span className="font-medium text-ink">{result.title}</span>
                <Badge tone={short ? "amber" : "mint"} size="xs">
                  {short
                    ? `${result.matched}/${result.requested} available in the bank`
                    : `${result.added}/${result.requested} added`}
                </Badge>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
