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
import { useTranslations } from "next-intl";

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

const ACCEPT = ".csv,.tsv,.txt,.xlsx,.xlsm,.doc,.docx,.pdf";
const MAX_MB = 20;

const FILE_TYPE_INFO = [
  { ext: "PDF",  label: "PDF",          icon: "📄", color: "#ef4444" },
  { ext: "DOCX", label: "Word (.docx)",  icon: "📝", color: "#2563eb" },
  { ext: "XLSX", label: "Excel (.xlsx)", icon: "📊", color: "#16a34a" },
  { ext: "CSV",  label: "CSV / TSV",    icon: "📋", color: "#0d9488" },
  { ext: "JSON", label: "JSON",          icon: "🔧", color: "#7c3aed" },
];

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
  const t = useTranslations("question");
  const [chosenSubject, setChosenSubject] = useState(subjectId ?? "");
  const subject = subjectId ?? chosenSubject;

  const [mode, setMode] = useState<"file" | "url">("file");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [url, setUrl] = useState("");
  const [urlFetching, setUrlFetching] = useState(false);
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

  /** How many of each question type were actually extracted, so a mixed-type file
   * ("5 Single Choice, 5 True/False, 3 Multiple Choice") shows its full breakdown
   * rather than just a total. */
  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of rows) {
      counts.set(row.question_type, (counts.get(row.question_type) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [rows]);

  async function parse(candidate: File, sheet?: string) {
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
    if (sheet) form.append("sheet_name", sheet);

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
    setError(null);
    if (candidate) void parse(candidate);
  }

  async function fetchUrl() {
    const trimmed = url.trim();
    if (!trimmed) { setError("Paste a Google Forms or web URL first."); return; }
    setUrlFetching(true);
    setError(null);
    setResult(null);
    setParsed(null);
    setRows([]);
    setChosen([]);
    try {
      const form = new FormData();
      form.append("url", trimmed);
      if (subject) form.append("subject_id", subject);
      const data = await api.upload<ImportParseResult>("/questions/import/parse-url", form);
      setParsed(data);
      setRows(data.rows);
      setChosen(
        data.rows
          .filter((row) => row.problems.length === 0 && !row.duplicate_of)
          .map((row) => row.row_number),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not fetch questions from that URL.");
    } finally {
      setUrlFetching(false);
    }
  }

  function detectUrlType(u: string): "google_forms" | "website" | "unknown" {
    if (u.includes("docs.google.com/forms")) return "google_forms";
    if (u.startsWith("http")) return "website";
    return "unknown";
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
          // A row that named its own subject (the CSV/XLSX "Subject" column) keeps it;
          // everything else falls back to the subject chosen above.
          subject_id: row.subject_id,
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
        {/* ── Header ─────────────────────────────────────────── */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-[15px] font-bold tracking-tight text-ink">{t("importer_heading")}</h3>
          <button
            type="button"
            className="text-[12.5px] font-semibold text-accent hover:underline"
            onClick={() =>
              void api
                .download("/questions/import/template", "examina-question-template.csv")
                .catch(() => setError("Could not download the template."))
            }
          >
            ↓ Download CSV template
          </button>
        </div>

        {/* ── Subject picker ──────────────────────────────────── */}
        {!subjectId && (
          <div className="mb-4">
            <Field label="Subject" required hint="Every imported question needs one.">
              <Select value={chosenSubject} onChange={(e) => setChosenSubject(e.target.value)}>
                <option value="">{t("importer_subject_option")}</option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        )}

        {/* ── Mode tabs ───────────────────────────────────────── */}
        <div className="mb-5 flex rounded-[11px] border border-line bg-sunken p-1">
          {([
            { id: "file", label: "📁 Upload File" },
            { id: "url",  label: "🔗 Import from URL" },
          ] as const).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => { setMode(tab.id); setError(null); }}
              className={cx(
                "flex-1 rounded-[8px] px-4 py-2 text-[13px] font-semibold transition-all duration-200",
                mode === tab.id
                  ? "bg-surface text-ink shadow-[var(--shadow-xs)]"
                  : "text-ink-muted hover:text-ink",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* ══ FILE UPLOAD MODE ════════════════════════════════ */}
        {mode === "file" && (
          <>
            {/* Supported formats strip */}
            <div className="mb-4 flex flex-wrap gap-2">
              {FILE_TYPE_INFO.map((ft) => (
                <span
                  key={ft.ext}
                  className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold"
                  style={{ borderColor: `${ft.color}30`, background: `${ft.color}0d`, color: ft.color }}
                >
                  {ft.icon} {ft.label}
                </span>
              ))}
            </div>

            {/* Drop zone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                const dropped = e.dataTransfer.files?.[0];
                if (dropped) pick(dropped);
              }}
              className={cx(
                "relative rounded-[14px] border-2 border-dashed p-8 text-center transition-all duration-200",
                dragging
                  ? "border-accent bg-accent-soft/40 scale-[1.01]"
                  : file
                    ? "border-green/40 bg-green-soft/20"
                    : "border-line-strong bg-sunken/40 hover:border-accent/40 hover:bg-accent-soft/10",
              )}
            >
              {/* Big upload icon */}
              {!file && (
                <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-[14px] border border-line bg-surface text-3xl shadow-[var(--shadow-xs)]">
                  {dragging ? "📂" : "📤"}
                </div>
              )}

              {file ? (
                <div className="flex flex-col items-center gap-2">
                  <div className="flex h-12 w-12 items-center justify-center rounded-[12px] bg-green-soft text-2xl">
                    ✅
                  </div>
                  <p className="text-[14px] font-bold text-ink">{file.name}</p>
                  <p className="text-[12px] text-ink-muted">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              ) : (
                <>
                  <p className="text-[14px] font-semibold text-ink">
                    {dragging ? "Drop it!" : "Drag & drop a file here"}
                  </p>
                  <p className="mt-1 text-[12px] text-ink-muted">
                    PDF, Word (.doc/.docx), Excel (.xlsx), CSV, or JSON — up to {MAX_MB} MB
                  </p>
                </>
              )}

              <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                <label className="cursor-pointer rounded-[10px] border border-line-strong bg-surface px-4 py-2 text-[13px] font-semibold text-ink shadow-[var(--shadow-xs)] hover:bg-sunken hover:-translate-y-[1px] transition-all">
                  {file ? "Choose different file" : "Browse files"}
                  <input
                    type="file"
                    accept={ACCEPT}
                    className="hidden"
                    onChange={(e) => pick(e.target.files?.[0] ?? null)}
                  />
                </label>
                {file && (
                  <Button variant="ghost" size="sm" onClick={() => pick(null)}>
                    ✕ Clear
                  </Button>
                )}
              </div>
            </div>

            {parsing && (
              <div className="mt-4 flex items-center gap-3 rounded-[10px] bg-accent-soft/30 px-4 py-3">
                <span className="animate-spin text-lg">⚙️</span>
                <p className="text-[13px] font-medium text-accent">Reading {file?.name}…</p>
              </div>
            )}
          </>
        )}

        {/* ══ URL IMPORT MODE ═════════════════════════════════ */}
        {mode === "url" && (
          <div className="space-y-4">
            {/* Supported sources */}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex items-start gap-3 rounded-[12px] border border-line bg-gradient-to-br from-blue-50/50 to-transparent p-3.5">
                <span className="text-2xl">📋</span>
                <div>
                  <p className="text-[13px] font-bold text-ink">Google Forms</p>
                  <p className="mt-0.5 text-[11.5px] text-ink-muted">
                    Paste a public Google Forms link — questions are extracted automatically.
                  </p>
                  <p className="mt-1 text-[10.5px] font-mono text-ink-muted">
                    docs.google.com/forms/d/…
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3 rounded-[12px] border border-line bg-gradient-to-br from-purple-50/50 to-transparent p-3.5">
                <span className="text-2xl">🌐</span>
                <div>
                  <p className="text-[13px] font-bold text-ink">Any Website / Quiz URL</p>
                  <p className="mt-0.5 text-[11.5px] text-ink-muted">
                    Publicly accessible quiz pages, question-bank sites, or LMS exports.
                  </p>
                </div>
              </div>
            </div>

            {/* URL input */}
            <div className="space-y-2">
              <div className="relative flex gap-2">
                <div className="relative flex-1">
                  {url && (
                    <span className={cx(
                      "absolute left-3 top-1/2 -translate-y-1/2 text-[11px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded",
                      detectUrlType(url) === "google_forms"
                        ? "bg-blue-100 text-blue-600"
                        : detectUrlType(url) === "website"
                          ? "bg-purple-100 text-purple-600"
                          : "bg-sunken text-ink-muted",
                    )}>
                      {detectUrlType(url) === "google_forms" ? "🔵 Google Forms" : detectUrlType(url) === "website" ? "🌐 Web" : ""}
                    </span>
                  )}
                  <Input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") void fetchUrl(); }}
                    placeholder="Paste Google Forms link or website URL…"
                    className={cx(
                      "w-full pr-4",
                      url && detectUrlType(url) === "google_forms" ? "pl-36" : url ? "pl-20" : "",
                    )}
                  />
                </div>
                <Button
                  onClick={() => void fetchUrl()}
                  loading={urlFetching}
                  disabled={!url.trim()}
                >
                  {urlFetching ? "Fetching…" : "Import"}
                </Button>
              </div>

              {/* Hint rows */}
              <div className="space-y-1 text-[11.5px] text-ink-muted">
                <p>💡 The form or page must be <strong>publicly accessible</strong> (no login required).</p>
                <p>💡 Google Forms: open your form → click ⋮ → <em>Get pre-filled link</em> → copy the URL.</p>
              </div>
            </div>

            {urlFetching && (
              <div className="flex items-center gap-3 rounded-[10px] bg-accent-soft/30 px-4 py-3">
                <span className="animate-spin text-lg">⚙️</span>
                <p className="text-[13px] font-medium text-accent">Fetching questions from URL…</p>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="mt-4">
            <Alert tone="rose">{error}</Alert>
          </div>
        )}
      </Card>

      {result && (
        <Alert tone={result.failed ? "amber" : "mint"} title={t("importer_alert_finished")}>
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

      {parsed && parsed.sheet_names.length > 1 && (
        <Alert tone="accent">
          <div className="flex flex-wrap items-center gap-3">
            <span>
              This workbook has {parsed.sheet_names.length} sheets. Reading{" "}
              <strong>{parsed.sheet_name}</strong>.
            </span>
            <Select
              value={parsed.sheet_name ?? ""}
              onChange={(e) => file && void parse(file, e.target.value)}
              className="w-48"
            >
              {parsed.sheet_names.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          </div>
        </Alert>
      )}

      {parsed && rows.length > 0 && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-[15px] font-semibold tracking-tight text-ink">
                Review before importing
              </h3>
              <Badge tone="neutral">{rows.length} detected</Badge>
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

            <div className="flex flex-wrap items-center gap-1.5">
              {typeCounts.map(([type, count]) => (
                <Badge key={type} tone="neutral">
                  {count} {QUESTION_TYPE_LABEL[type as QuestionType] ?? type}
                </Badge>
              ))}
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
                        {row.subject_name && (
                          <Badge tone="purple">{row.subject_name}</Badge>
                        )}
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
                          {row.problems.map((problem, index) => (
                            <li key={index}>{problem}</li>
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
  const t = useTranslations("question");
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
            <option value="easy">{t("difficulty_easy")}</option>
            <option value="medium">{t("difficulty_medium")}</option>
            <option value="hard">{t("difficulty_hard")}</option>
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
