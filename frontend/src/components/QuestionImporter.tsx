"use client";

/**
 * Upload → parse → validate → preview → fix → import.
 *
 * The preview is where the work happens. Rows the server could not make sense of are
 * shown with what is wrong, editable in place, and excluded from the import until
 * they pass - so a file with two broken rows imports fourteen questions and leaves
 * the examiner looking at exactly the two that need them.
 */

import { useMemo, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  Field,
  Input,
  Select,
  Textarea,
  cx,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import {
  QUESTION_TYPE_LABEL,
  type Difficulty,
  type ImportParseResult,
  type ImportResult,
  type ImportedRow,
  type QuestionType,
  type Subject,
} from "@/lib/types";

const ACCEPT = ".csv,.tsv,.txt,.xlsx,.xlsm,.docx";
const MAX_MB = 10;

export interface QuestionImporterProps {
  subjects: Subject[];
  /** Imported questions also join this exam's pool when set. */
  examId?: string;
  subjectId?: string;
  onImported?: (result: ImportResult) => void;
}

export function QuestionImporter({
  subjects,
  examId,
  subjectId,
  onImported,
}: QuestionImporterProps) {
  const [chosenSubject, setChosenSubject] = useState(subjectId ?? "");
  const subject = subjectId ?? chosenSubject;

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parsed, setParsed] = useState<ImportParseResult | null>(null);
  const [rows, setRows] = useState<ImportedRow[]>([]);
  /** Row numbers the examiner has chosen to import. Broken rows are never included. */
  const [chosen, setChosen] = useState<number[]>([]);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [skipDuplicates, setSkipDuplicates] = useState(true);

  const importable = useMemo(
    () =>
      rows.filter(
        (row) => row.problems.length === 0 && !(skipDuplicates && row.duplicate_of),
      ),
    [rows, skipDuplicates],
  );

  const selectedRows = useMemo(
    () => importable.filter((row) => chosen.includes(row.row_number)),
    [importable, chosen],
  );

  async function parse(candidate: File) {
    if (candidate.size > MAX_MB * 1024 * 1024) {
      setError(`That file is larger than ${MAX_MB} MB.`);
      return;
    }
    setParsing(true);
    setError(null);
    setResult(null);
    const form = new FormData();
    form.append("file", candidate);
    if (subject) form.append("subject_id", subject);

    try {
      const data = await api.upload<ImportParseResult>("/questions/import/parse", form);
      setParsed(data);
      setRows(data.rows);
      setChosen(
        data.rows
          .filter((row) => row.problems.length === 0 && !row.duplicate_of)
          .map((row) => row.row_number),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That file could not be read.");
      setParsed(null);
      setRows([]);
    } finally {
      setParsing(false);
    }
  }

  function pick(candidate: File | null) {
    setFile(candidate);
    setParsed(null);
    setRows([]);
    setChosen([]);
    if (candidate) void parse(candidate);
  }

  function patchRow(rowNumber: number, patch: Partial<ImportedRow>) {
    setRows((current) =>
      current.map((row) => (row.row_number === rowNumber ? { ...row, ...patch } : row)),
    );
  }

  async function commit() {
    if (!subject) {
      setError("Pick the subject these questions belong to.");
      return;
    }
    if (!selectedRows.length) return;

    setImporting(true);
    setError(null);
    try {
      const outcome = await api.post<ImportResult>("/questions/import", {
        subject_id: subject,
        exam_id: examId ?? null,
        rows: selectedRows.map((row) => ({
          row_number: row.row_number,
          body: row.body,
          question_type: row.question_type,
          difficulty: row.difficulty,
          category: row.category,
          topic: row.topic,
          marks: row.marks,
          negative_marks: row.negative_marks,
          model_answer: row.model_answer,
          explanation: row.explanation,
          tags: row.tags,
          min_words: row.min_words,
          max_words: row.max_words,
          spec: row.spec,
          options: row.options,
          save_to_bank: row.save_to_bank ?? true,
        })),
      });
      setResult(outcome);
      toast(
        outcome.failed
          ? `${outcome.created} imported, ${outcome.failed} refused`
          : `${outcome.created} question(s) imported`,
        outcome.failed ? "amber" : "mint",
      );
      onImported?.(outcome);
      // Drop what landed, so a second press cannot import the same rows twice.
      const done = new Set(selectedRows.map((row) => row.row_number));
      setRows((current) => current.filter((row) => !done.has(row.row_number)));
      setChosen([]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The import failed.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-[15px] font-semibold tracking-tight text-ink">Import questions</h3>
          <button
            type="button"
            className="text-[12.5px] font-medium text-accent hover:underline"
            onClick={() =>
              void api
                .download("/questions/import/template", "examina-question-template.csv")
                .catch(() => setError("Could not download the template."))
            }
          >
            Download the CSV template
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {!subjectId && (
            <Field label="Subject" required hint="Every imported question needs one.">
              <Select value={chosenSubject} onChange={(e) => setChosenSubject(e.target.value)}>
                <option value="">Choose a subject</option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const dropped = e.dataTransfer.files?.[0];
            if (dropped) pick(dropped);
          }}
          className={cx(
            "mt-4 rounded-[12px] border-2 border-dashed p-6 text-center transition",
            dragging ? "border-accent bg-accent-soft/40" : "border-line-strong bg-sunken/40",
          )}
        >
          <p className="text-[13.5px] font-medium text-ink">
            {file ? file.name : "Drop a file here, or choose one"}
          </p>
          <p className="mt-1 text-[12px] text-ink-muted">
            CSV, Excel (.xlsx) or Word (.docx) — up to {MAX_MB} MB. PDFs go through AI
            Generate, which reads a syllabus rather than a question table.
          </p>
          <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
            <label className="cursor-pointer rounded-[9px] border border-line-strong bg-surface px-3 py-1.5 text-[13px] font-medium text-ink hover:bg-sunken">
              Choose file
              <input
                type="file"
                accept={ACCEPT}
                className="hidden"
                onChange={(e) => pick(e.target.files?.[0] ?? null)}
              />
            </label>
            {file && (
              <Button variant="ghost" size="sm" onClick={() => pick(null)}>
                Clear
              </Button>
            )}
          </div>
        </div>

        {parsing && (
          <p className="mt-3 text-[13px] text-ink-muted">Reading {file?.name}…</p>
        )}
        {error && (
          <div className="mt-3">
            <Alert tone="rose">{error}</Alert>
          </div>
        )}
      </Card>

      {result && (
        <Alert tone={result.failed ? "amber" : "mint"} title="Import finished">
          {result.created} question{result.created === 1 ? "" : "s"} imported
          {examId ? " and added to this exam" : " into your bank"}.
          {result.failed > 0 && (
            <ul className="mt-1 list-inside list-disc">
              {result.errors.map((e, i) => (
                <li key={i}>
                  {e.row_number ? `Row ${e.row_number}: ` : ""}
                  {e.error}
                </li>
              ))}
            </ul>
          )}
        </Alert>
      )}

      {parsed && rows.length > 0 && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-[15px] font-semibold tracking-tight text-ink">
                Review before importing
              </h3>
              <Badge tone="mint">{rows.filter((r) => !r.problems.length).length} ready</Badge>
              {rows.some((r) => r.problems.length > 0) && (
                <Badge tone="rose">
                  {rows.filter((r) => r.problems.length > 0).length} need fixing
                </Badge>
              )}
              {parsed.duplicates > 0 && (
                <Badge tone="amber">{parsed.duplicates} duplicate</Badge>
              )}
            </div>
            <label className="flex items-center gap-2 text-[12.5px] text-ink-soft">
              <input
                type="checkbox"
                checked={skipDuplicates}
                onChange={(e) => setSkipDuplicates(e.target.checked)}
                className="h-4 w-4 rounded border-line-strong"
              />
              Skip duplicates
            </label>
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-line bg-sunken/50 px-3 py-2">
            <label className="flex items-center gap-2 text-[13px] text-ink-soft">
              <input
                type="checkbox"
                checked={
                  importable.length > 0 && selectedRows.length === importable.length
                }
                disabled={importable.length === 0}
                onChange={() =>
                  setChosen(
                    selectedRows.length === importable.length
                      ? []
                      : importable.map((row) => row.row_number),
                  )
                }
                className="h-4 w-4 rounded border-line-strong"
              />
              {selectedRows.length} of {importable.length} selected
            </label>
            <Button
              loading={importing}
              disabled={!selectedRows.length || !subject}
              onClick={() => void commit()}
            >
              Import {selectedRows.length || ""}
              {examId ? " into this exam" : " into bank"}
            </Button>
          </div>

          <ul className="mt-3 space-y-2">
            {rows.map((row) => {
              const broken = row.problems.length > 0;
              const skipped = skipDuplicates && Boolean(row.duplicate_of);
              const ticked = chosen.includes(row.row_number);
              return (
                <li
                  key={row.row_number}
                  className={cx(
                    "rounded-[10px] border px-3 py-2.5 transition",
                    broken
                      ? "border-rose/40 bg-rose-soft/30"
                      : skipped
                        ? "border-line bg-sunken/60 opacity-70"
                        : ticked
                          ? "border-accent bg-accent-soft/30"
                          : "border-line bg-surface",
                  )}
                >
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={ticked}
                      disabled={broken || skipped}
                      onChange={() =>
                        setChosen((current) =>
                          current.includes(row.row_number)
                            ? current.filter((n) => n !== row.row_number)
                            : [...current, row.row_number],
                        )
                      }
                      className="mt-1 h-4 w-4 shrink-0 rounded border-line-strong"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-[13.5px] text-ink">
                        <span className="mr-2 font-mono text-[11.5px] text-ink-muted">
                          row {row.row_number}
                        </span>
                        {row.body || <span className="italic text-ink-muted">(no text)</span>}
                      </p>

                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        <Badge tone="neutral">
                          {QUESTION_TYPE_LABEL[row.question_type] ?? row.question_type}
                        </Badge>
                        <Badge tone="neutral">{row.difficulty}</Badge>
                        <Badge tone="accent">{row.marks} marks</Badge>
                        {row.options.length > 0 && (
                          <Badge tone="neutral">
                            {row.options.length} options ·{" "}
                            {row.options
                              .map((o, i) => (o.is_correct ? String.fromCharCode(65 + i) : null))
                              .filter(Boolean)
                              .join(",") || "no key"}
                          </Badge>
                        )}
                        {row.duplicate_of && (
                          <Badge tone="amber">duplicate of {row.duplicate_of}</Badge>
                        )}
                      </div>

                      {broken && (
                        <ul className="mt-2 list-inside list-disc text-[12.5px] text-rose-ink">
                          {row.problems.map((problem) => (
                            <li key={problem}>{problem}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        setExpanded(expanded === row.row_number ? null : row.row_number)
                      }
                    >
                      {expanded === row.row_number ? "Close" : broken ? "Fix" : "Edit"}
                    </Button>
                  </div>

                  {expanded === row.row_number && (
                    <RowFixer
                      row={row}
                      onChange={(patch) => patchRow(row.row_number, patch)}
                    />
                  )}
                </li>
              );
            })}
          </ul>

          <p className="mt-3 text-[12px] text-ink-muted">
            Fixes made here are re-checked on the server when you import. Rows that
            still fail are reported back, never quietly dropped.
          </p>
        </Card>
      )}
    </div>
  );
}

/**
 * Correct one row in place.
 *
 * Only the fields a broken import actually turns on: the type, the marks, the key, the
 * model answer. Anything more and this becomes a second question editor that has to be
 * kept in step with the real one.
 */
function RowFixer({
  row,
  onChange,
}: {
  row: ImportedRow;
  onChange: (patch: Partial<ImportedRow>) => void;
}) {
  const optionBearing = ["mcq", "multi_select", "true_false"].includes(row.question_type);
  const single = row.question_type === "mcq" || row.question_type === "true_false";
  const written = row.question_type === "short_answer" || row.question_type === "long_answer";

  return (
    <div className="mt-3 space-y-3 rounded-[10px] border border-line bg-surface p-3">
      <Field label="Question">
        <Textarea
          value={row.body}
          onChange={(e) => onChange({ body: e.target.value, problems: [] })}
          rows={2}
        />
      </Field>

      <div className="grid gap-3 sm:grid-cols-4">
        <Field label="Type">
          <Select
            value={row.question_type}
            onChange={(e) =>
              onChange({ question_type: e.target.value as QuestionType, problems: [] })
            }
          >
            {(Object.keys(QUESTION_TYPE_LABEL) as QuestionType[]).map((value) => (
              <option key={value} value={value}>
                {QUESTION_TYPE_LABEL[value]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Difficulty">
          <Select
            value={row.difficulty}
            onChange={(e) => onChange({ difficulty: e.target.value as Difficulty })}
          >
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </Select>
        </Field>
        <Field label="Marks">
          <Input
            type="number"
            min="0"
            step="0.5"
            value={row.marks}
            onChange={(e) => onChange({ marks: Number(e.target.value), problems: [] })}
          />
        </Field>
        <Field label="Negative">
          <Input
            type="number"
            min="0"
            step="0.25"
            value={row.negative_marks}
            onChange={(e) => onChange({ negative_marks: Number(e.target.value) })}
          />
        </Field>
      </div>

      {optionBearing && row.options.length > 0 && (
        <div>
          <p className="mb-1.5 text-[13px] font-medium text-ink-soft">
            Correct answer — tap a letter
          </p>
          <div className="space-y-1.5">
            {row.options.map((option, index) => (
              <div key={index} className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    onChange({
                      options: row.options.map((o, i) =>
                        single
                          ? { ...o, is_correct: i === index }
                          : i === index
                            ? { ...o, is_correct: !o.is_correct }
                            : o,
                      ),
                      problems: [],
                    })
                  }
                  className={cx(
                    "flex h-8 w-8 shrink-0 items-center justify-center border text-[12px] font-semibold transition",
                    single ? "rounded-full" : "rounded-[8px]",
                    option.is_correct
                      ? "border-accent bg-accent text-white"
                      : "border-line-strong text-ink-muted hover:bg-sunken",
                  )}
                >
                  {String.fromCharCode(65 + index)}
                </button>
                <Input
                  value={option.text}
                  onChange={(e) =>
                    onChange({
                      options: row.options.map((o, i) =>
                        i === index ? { ...o, text: e.target.value } : o,
                      ),
                      problems: [],
                    })
                  }
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {written && (
        <Field label="Model answer" required>
          <Textarea
            value={row.model_answer ?? ""}
            onChange={(e) => onChange({ model_answer: e.target.value, problems: [] })}
            rows={3}
          />
        </Field>
      )}

      <label className="flex items-center gap-2 text-[12.5px] text-ink-soft">
        <input
          type="checkbox"
          checked={row.save_to_bank ?? true}
          onChange={(e) => onChange({ save_to_bank: e.target.checked })}
          className="h-4 w-4 rounded border-line-strong"
        />
        Save this one to my Question Bank
      </label>
    </div>
  );
}
