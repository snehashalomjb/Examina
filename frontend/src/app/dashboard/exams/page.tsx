"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Hero } from "@/components/Hero";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  SectionTitle,
  Select,
  Skeleton,
  Textarea,
  cx,
  formatDate,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type {
  CandidateRow,
  Difficulty,
  EnrollmentRow,
  Exam,
  ExamPoolCheck,
  ExamType,
  Question,
  QuestionType,
  SelectionRule,
  Subject,
} from "@/lib/types";
import { QUESTION_TYPE_LABEL as TYPE_LABEL } from "@/lib/types";

export default function ExamsPage() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  const [exams, setExams] = useState<Exam[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [building, setBuilding] = useState(false);
  const [checks, setChecks] = useState<Record<string, ExamPoolCheck>>({});
  const [filterTab, setFilterTab] = useState<
    "all" | "academic" | "corporate" | "draft" | "published" | "closed"
  >("all");
  const [search, setSearch] = useState("");

  const filteredExams = useMemo(() => {
    return exams.filter((e) => {
      if (filterTab === "academic" && e.exam_type !== "academic") return false;
      if (filterTab === "corporate" && e.exam_type !== "corporate") return false;
      if (filterTab === "draft" && e.status !== "draft") return false;
      if (filterTab === "published" && e.status !== "published") return false;
      if (filterTab === "closed" && e.status !== "closed") return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          e.title.toLowerCase().includes(q) ||
          (e.subject_name && e.subject_name.toLowerCase().includes(q)) ||
          (e.company_name && e.company_name.toLowerCase().includes(q)) ||
          (e.course && e.course.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [exams, filterTab, search]);

  const load = useCallback(async () => {
    try {
      const [examData, subjectData] = await Promise.all([
        api.get<Exam[]>("/exams"),
        api.get<Subject[]>("/subjects"),
      ]);
      setExams(examData);
      setSubjects(subjectData);
      setError(null);

      // Tell the examiner up front whether each draft can actually be published.
      const results = await Promise.all(
        examData
          .filter((exam) => exam.status === "draft")
          .map(async (exam) => {
            try {
              return [exam.id, await api.get<ExamPoolCheck>(`/exams/${exam.id}/pool-check`)] as const;
            } catch {
              return null;
            }
          }),
      );
      setChecks(Object.fromEntries(results.filter(Boolean) as [string, ExamPoolCheck][]));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load exams.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  async function publish(exam: Exam) {
    try {
      await api.post(`/exams/${exam.id}/publish`);
      toast(`${exam.title} is live`, "mint");
      void load();
    } catch (err) {
      if (err instanceof ApiError) {
        toast(
          err.problems?.length ? `${err.message}: ${err.problems.join("; ")}` : err.message,
          "rose",
        );
      }
    }
  }

  async function close(exam: Exam) {
    try {
      await api.post(`/exams/${exam.id}/close`);
      toast(`${exam.title} closed`, "neutral");
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not close the exam", "rose");
    }
  }

  if (!user) return null;

  return (
    <div className="space-y-6">
      <Hero
        title="Exams"
        body="An exam is a set of rules, not a fixed paper: each candidate's questions are drawn dynamically from your question bank pool."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Link href="/dashboard/exams/create">
              <Button size="sm">
                + Create Exam Wizard
              </Button>
            </Link>
            <Button size="sm" variant="secondary" onClick={() => setBuilding((v) => !v)}>
              {building ? "Close quick builder" : "Quick Builder"}
            </Button>
          </div>
        }
      />

      {error && <Alert tone="rose">{error}</Alert>}

      {/* Filter Tabs & Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
          {[
            { key: "all", label: `All (${exams.length})` },
            { key: "academic", label: `🎓 Academic (${exams.filter((e) => e.exam_type === "academic").length})` },
            { key: "corporate", label: `💼 Corporate (${exams.filter((e) => e.exam_type === "corporate").length})` },
            { key: "published", label: `Live (${exams.filter((e) => e.status === "published").length})` },
            { key: "draft", label: `Drafts (${exams.filter((e) => e.status === "draft").length})` },
          ].map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setFilterTab(tab.key as any)}
              className={cx(
                "rounded-lg px-3 py-1.5 text-xs font-semibold transition-all",
                filterTab === tab.key
                  ? "bg-accent text-white shadow-sm"
                  : "text-ink-muted hover:text-ink hover:bg-surface-elevated"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="w-64">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search exams..."
            className="text-xs h-9"
          />
        </div>
      </div>

      {building && (
        <ExamBuilder
          subjects={subjects}
          onDone={() => {
            setBuilding(false);
            void load();
          }}
        />
      )}

      {loading ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-[220px] rounded-[14px]" />
          ))}
        </div>
      ) : filteredExams.length === 0 ? (
        <EmptyState
          title={exams.length === 0 ? "No exams yet" : "No exams match filter"}
          body={exams.length === 0 ? "Build an exam from your question bank or use the creation wizard." : "Try adjusting your search query or switching tabs."}
          action={
            <Link href="/dashboard/exams/create">
              <Button size="sm">+ Create Exam Wizard</Button>
            </Link>
          }
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {filteredExams.map((exam) => {
            const check = checks[exam.id];
            return (
              <Card key={exam.id} className="flex flex-col">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="truncate text-[15px] font-semibold tracking-tight text-ink">
                        {exam.title}
                      </p>
                      <Badge tone={exam.exam_type === "corporate" ? "purple" : "accent"}>
                        {exam.exam_type === "corporate" ? "💼 Corporate" : "🎓 Academic"}
                      </Badge>
                    </div>
                    <p className="mt-0.5 text-[12.5px] text-ink-muted">
                      {exam.exam_type === "corporate" && exam.company_name
                        ? `${exam.company_name}${exam.job_role ? ` · ${exam.job_role}` : ""}`
                        : exam.subject_name}{" "}
                      · {formatDate(exam.starts_at, false)} → {formatDate(exam.ends_at, false)}
                    </p>
                  </div>
                  <Badge
                    tone={
                      exam.status === "published"
                        ? "mint"
                        : exam.status === "draft"
                          ? "amber"
                          : "neutral"
                    }
                  >
                    {exam.status}
                  </Badge>
                </div>

                <dl className="mt-4 grid grid-cols-4 gap-2 rounded-[10px] bg-sunken/60 p-3 text-center">
                  {[
                    ["Duration", `${exam.duration_minutes}m`],
                    ["Questions", String(exam.total_questions)],
                    ["Pool", String(exam.pool_size)],
                    ["Negative", exam.negative_marking ? "on" : "off"],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt className="text-[10.5px] uppercase tracking-wide text-ink-muted">
                        {label}
                      </dt>
                      <dd className="mt-0.5 text-[13px] font-semibold text-ink">{value}</dd>
                    </div>
                  ))}
                </dl>

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {exam.selection_rules.rules.map((rule, index) => (
                    <Badge key={index}>
                      {rule.count}× {TYPE_LABEL[rule.question_type]}
                      {rule.difficulty ? ` (${rule.difficulty})` : ""}
                    </Badge>
                  ))}
                </div>

                {check && !check.can_publish && (
                  <div className="mt-3">
                    <Alert tone="amber" title="Cannot publish yet">
                      <ul className="list-disc pl-4">
                        {check.problems.map((problem) => (
                          <li key={problem}>{problem}</li>
                        ))}
                      </ul>
                    </Alert>
                  </div>
                )}

                <div className="mt-auto flex items-center gap-2 pt-4 flex-wrap">
                  {exam.status === "draft" && (
                    <Button
                      size="sm"
                      onClick={() => publish(exam)}
                      disabled={Boolean(check && !check.can_publish)}
                    >
                      Publish
                    </Button>
                  )}
                  {exam.status === "published" && (
                    <Button size="sm" variant="secondary" onClick={() => close(exam)}>
                      Close exam
                    </Button>
                  )}
                  <PaperPreviewButton examId={exam.id} />
                  <EnrollmentButton exam={exam} />
                  <Link href={`/dashboard/exams/${exam.id}/analytics`}>
                    <Button size="sm" variant="ghost">Analytics</Button>
                  </Link>
                  {exam.exam_type === "corporate" && (
                    <Link href={`/dashboard/exams/${exam.id}/ranking`}>
                      <Button size="sm" variant="ghost">Ranking</Button>
                    </Link>
                  )}
                  {exam.results_published && <Badge tone="mint">results published</Badge>}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Proves the determinism claim to the examiner: same call, byte-identical paper. */
function PaperPreviewButton({ examId }: { examId: string }) {
  const [preview, setPreview] = useState<{ seed: string; entries: { question_id: string; body: string; marks: number }[] } | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    try {
      const data = await api.post<{
        seed: string;
        entries: { question_id: string; body: string; marks: number }[];
      }>(`/exams/${examId}/preview-paper`);
      setPreview(data);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not generate a preview", "rose");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button size="sm" variant="ghost" loading={busy} onClick={run}>
        Preview paper
      </Button>
      {preview && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 px-5 backdrop-blur-sm">
          <Card className="animate-rise max-h-[80vh] w-full max-w-2xl overflow-y-auto">
            <SectionTitle
              title="Generated paper"
              hint={`Seed ${preview.seed.slice(0, 16)}… — the same candidate always gets this exact paper.`}
              action={
                <Button size="sm" variant="secondary" onClick={() => setPreview(null)}>
                  Close
                </Button>
              }
            />
            <ol className="space-y-2">
              {preview.entries.map((entry, index) => (
                <li key={entry.question_id} className="rounded-[10px] border border-line p-3">
                  <div className="mb-1 flex items-center gap-2">
                    <Badge tone="accent">Q{index + 1}</Badge>
                    <Badge>{entry.marks} marks</Badge>
                  </div>
                  <p className="text-[13px] leading-relaxed text-ink-soft">{entry.body}</p>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      )}
    </>
  );
}

/* --------------------------------------------------------------- builder */
function toLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

interface SectionDraft {
  name: string;
  description: string;
  order_index: number;
  duration_minutes: string;
  marks_per_question: string;
  negative_marks: string;
  rules: SelectionRule[];
}

function makeSectionDraft(order_index: number): SectionDraft {
  return {
    name: `Section ${order_index + 1}`,
    description: "",
    order_index,
    duration_minutes: "",
    marks_per_question: "1",
    negative_marks: "0.25",
    rules: [{ question_type: "mcq" as QuestionType, difficulty: null, count: 5 }],
  };
}

function ExamBuilder({ subjects, onDone }: { subjects: Subject[]; onDone: () => void }) {
  const now = new Date();

  const [examType, setExamType] = useState<"academic" | "corporate">("academic");
  const [subjectId, setSubjectId] = useState(subjects[0]?.id ?? "");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [duration, setDuration] = useState("45");
  const [startsAt, setStartsAt] = useState(toLocalInput(now));
  const [endsAt, setEndsAt] = useState(toLocalInput(new Date(now.getTime() + 7 * 864e5)));
  const [negative, setNegative] = useState(true);
  const [randomize, setRandomize] = useState(true);
  const [maxTabs, setMaxTabs] = useState("3");
  const [webcam, setWebcam] = useState(true);
  const [passingPct, setPassingPct] = useState("50");
  const [course, setCourse] = useState("");
  const [department, setDepartment] = useState("");
  const [semester, setSemester] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [jobRole, setJobRole] = useState("");
  const [rules, setRules] = useState<SelectionRule[]>([
    { question_type: "mcq", difficulty: null, count: 5 },
  ]);
  const [sections, setSections] = useState<SectionDraft[]>([makeSectionDraft(0)]);
  const [pool, setPool] = useState<Question[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!subjectId) return;
    (async () => {
      try {
        setPool(await api.get<Question[]>(`/questions?subject_id=${subjectId}&limit=500`));
      } catch {
        setPool([]);
      }
    })();
  }, [subjectId]);

  const feasibility = useMemo(() => {
    const effectiveRules = examType === "academic" ? rules : sections.flatMap((s) => s.rules);
    const remaining = [...pool];
    const problems: string[] = [];
    const ordered = [...effectiveRules].sort(
      (a, b) => Number(a.difficulty === null) - Number(b.difficulty === null),
    );
    for (const rule of ordered) {
      const matches = remaining.filter(
        (q) =>
          q.question_type === rule.question_type &&
          (rule.difficulty === null || q.difficulty === rule.difficulty),
      );
      if (matches.length < rule.count) {
        problems.push(
          `Need ${rule.count} ${TYPE_LABEL[rule.question_type]}${rule.difficulty ? ` (${rule.difficulty})` : ""}, pool has ${matches.length}`,
        );
      }
      matches.slice(0, rule.count).forEach((match) => {
        const index = remaining.indexOf(match);
        if (index >= 0) remaining.splice(index, 1);
      });
    }
    return problems;
  }, [pool, rules, sections, examType]);

  const totalQuestions =
    examType === "academic"
      ? rules.reduce((s, r) => s + r.count, 0)
      : sections.reduce((s, sec) => s + sec.rules.reduce((ss, r) => ss + r.count, 0), 0);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        exam_type: examType,
        subject_id: subjectId || null,
        title: title.trim(),
        description: description.trim() || null,
        duration_minutes: Number(duration),
        starts_at: new Date(startsAt).toISOString(),
        ends_at: new Date(endsAt).toISOString(),
        randomize,
        shuffle_options: randomize,
        negative_marking: negative,
        passing_percentage: passingPct ? Number(passingPct) : null,
        proctor_config: {
          webcam_enabled: webcam,
          gaze_tracking_enabled: webcam,
          gaze_sensitivity: 0.6,
          max_tab_switches: Number(maxTabs),
          flag_on_score: 45,
          terminate_on_score: 100,
          snapshot_interval_seconds: 60,
          require_fullscreen: true,
          block_copy_paste: true,
        },
        grading_config: { partial_credit_multi_select: false, auto_publish_results: false },
      };
      if (examType === "academic") {
        body.selection_rules = { rules };
        body.course = course.trim() || null;
        body.department = department.trim() || null;
        body.semester = semester.trim() || null;
      } else {
        body.company_name = companyName.trim() || null;
        body.job_role = jobRole.trim() || null;
        body.selection_rules = { rules: [] };
        body.sections = sections.map((sec, i) => ({
          name: sec.name.trim(),
          description: sec.description.trim() || null,
          order_index: i,
          duration_minutes: sec.duration_minutes ? Number(sec.duration_minutes) : null,
          marks_per_question: Number(sec.marks_per_question),
          negative_marks: Number(sec.negative_marks),
          selection_rules: { rules: sec.rules },
        }));
      }
      await api.post("/exams", body);
      toast(`${title} created as a draft`, "mint");
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the exam.");
    } finally {
      setBusy(false);
    }
  }

  if (subjects.length === 0) {
    return (
      <Card>
        <Alert tone="amber" title="No subjects yet">
          Create a subject and some questions in the question bank first.
        </Alert>
      </Card>
    );
  }

  return (
    <Card>
      <SectionTitle
        title="Build an exam"
        hint="Choose Academic for a single-subject paper or Corporate for a multi-section hiring assessment."
      />
      <form onSubmit={submit} className="space-y-5">
        <div className="flex gap-2">
          {(["academic", "corporate"] as const).map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => setExamType(type)}
              className={cx(
                "flex-1 rounded-[10px] border px-4 py-3 text-left transition",
                examType === type
                  ? type === "corporate"
                    ? "border-accent bg-accent-soft text-accent-ink"
                    : "border-line-strong bg-sunken text-ink"
                  : "border-line text-ink-soft hover:bg-sunken",
              )}
            >
              <p className="text-[13px] font-semibold capitalize">{type}</p>
              <p className="mt-0.5 text-[12px] opacity-70">
                {type === "academic"
                  ? "Single subject paper — graded results"
                  : "Multi-section hiring drive — ranking & shortlisting"}
              </p>
            </button>
          ))}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Title">
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={examType === "academic" ? "CS101 Mid-Semester Examination" : "Software Engineer Hiring Drive 2025"}
              required
              minLength={3}
            />
          </Field>
          <Field label="Subject" hint={examType === "corporate" ? "Optional for corporate exams" : undefined}>
            <Select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} required={examType === "academic"}>
              {examType === "corporate" && <option value="">— Any / All subjects —</option>}
              {subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.code} — {subject.name} ({subject.question_count} questions)
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <Field label="Description" hint="Shown to candidates before they start.">
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="What this paper covers and how it is marked."
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Duration (minutes)">
            <Input type="number" min="1" max="600" value={duration} onChange={(e) => setDuration(e.target.value)} required />
          </Field>
          <Field label="Window opens">
            <Input type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} required />
          </Field>
          <Field label="Window closes">
            <Input type="datetime-local" value={endsAt} onChange={(e) => setEndsAt(e.target.value)} required />
          </Field>
        </div>

        {examType === "academic" && (
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Course code" hint="Optional"><Input value={course} onChange={(e) => setCourse(e.target.value)} placeholder="CS101" /></Field>
            <Field label="Department" hint="Optional"><Input value={department} onChange={(e) => setDepartment(e.target.value)} placeholder="Computer Science" /></Field>
            <Field label="Semester / batch" hint="Optional"><Input value={semester} onChange={(e) => setSemester(e.target.value)} placeholder="Sem 3 — 2025" /></Field>
          </div>
        )}

        {examType === "corporate" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Company name"><Input value={companyName} onChange={(e) => setCompanyName(e.target.value)} placeholder="Acme Technologies" /></Field>
            <Field label="Job role"><Input value={jobRole} onChange={(e) => setJobRole(e.target.value)} placeholder="Software Engineer — Backend" /></Field>
          </div>
        )}

        <Field label="Passing percentage" hint="Used in analytics and pass/fail calculation">
          <Input type="number" min="1" max="100" value={passingPct} onChange={(e) => setPassingPct(e.target.value)} />
        </Field>

        {examType === "academic" ? (
          <div>
            <p className="mb-2 text-[13px] font-medium text-ink-soft">
              Paper composition <span className="font-normal text-ink-muted">— {totalQuestions} questions per candidate</span>
            </p>
            <RuleEditor rules={rules} onChange={setRules} />
            {feasibility.length > 0 && (
              <div className="mt-3">
                <Alert tone="amber" title="The pool cannot satisfy these rules">
                  <ul className="list-disc pl-4">{feasibility.map((p) => <li key={p}>{p}</li>)}</ul>
                </Alert>
              </div>
            )}
          </div>
        ) : (
          <div>
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-[13px] font-medium text-ink-soft">
                Sections <span className="font-normal text-ink-muted">— {totalQuestions} questions total</span>
              </p>
              <Button type="button" variant="secondary" size="sm" onClick={() => setSections((s) => [...s, makeSectionDraft(s.length)])}>
                + Add section
              </Button>
            </div>
            <div className="space-y-4">
              {sections.map((sec, si) => (
                <div key={si} className="rounded-[12px] border border-line bg-sunken/40 p-4 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-accent/15 text-[11px] font-bold text-accent">{si + 1}</span>
                      <input
                        className="rounded-[8px] border border-line-strong bg-surface px-2.5 py-1.5 text-[13px] font-medium text-ink focus:border-accent focus:outline-none"
                        value={sec.name}
                        onChange={(e) => setSections((s) => s.map((x, i) => i === si ? { ...x, name: e.target.value } : x))}
                        placeholder="Section name"
                      />
                    </div>
                    {sections.length > 1 && (
                      <Button type="button" variant="ghost" size="sm" onClick={() => setSections((s) => s.filter((_, i) => i !== si).map((x, i) => ({ ...x, order_index: i })))}>
                        Remove
                      </Button>
                    )}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <Field label="Section duration (min)" hint="Leave blank to share the exam timer">
                      <Input type="number" min="1" value={sec.duration_minutes} onChange={(e) => setSections((s) => s.map((x, i) => i === si ? { ...x, duration_minutes: e.target.value } : x))} placeholder="—" />
                    </Field>
                    <Field label="Marks per question">
                      <Input type="number" min="0.5" step="0.5" value={sec.marks_per_question} onChange={(e) => setSections((s) => s.map((x, i) => i === si ? { ...x, marks_per_question: e.target.value } : x))} />
                    </Field>
                    <Field label="Negative marks">
                      <Input type="number" min="0" step="0.25" value={sec.negative_marks} onChange={(e) => setSections((s) => s.map((x, i) => i === si ? { ...x, negative_marks: e.target.value } : x))} />
                    </Field>
                  </div>
                  <div>
                    <p className="mb-1.5 text-[12px] font-medium text-ink-muted">Question rules</p>
                    <RuleEditor
                      rules={sec.rules}
                      onChange={(newRules) => setSections((s) => s.map((x, i) => i === si ? { ...x, rules: newRules } : x))}
                    />
                  </div>
                </div>
              ))}
            </div>
            {feasibility.length > 0 && (
              <div className="mt-3">
                <Alert tone="amber" title="Pool gap across sections">
                  <ul className="list-disc pl-4">{feasibility.map((p) => <li key={p}>{p}</li>)}</ul>
                </Alert>
              </div>
            )}
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <ToggleRow label="Randomize per candidate" hint="Each candidate gets a different draw and option order." checked={randomize} onChange={setRandomize} />
          <ToggleRow label="Negative marking" hint="Wrong objective answers deduct the question's penalty." checked={negative} onChange={setNegative} />
          <ToggleRow label="Webcam proctoring" hint="Face presence, face count and head orientation." checked={webcam} onChange={setWebcam} />
          <Field label="Tab-switch warnings before flagging">
            <Input type="number" min="0" max="50" value={maxTabs} onChange={(e) => setMaxTabs(e.target.value)} />
          </Field>
        </div>

        {error && <Alert tone="rose">{error}</Alert>}

        <div className="flex items-center justify-between gap-3">
          <p className="text-[12.5px] text-ink-muted">Created as a draft — review it, then publish when ready.</p>
          <Button type="submit" loading={busy} disabled={feasibility.length > 0}>Create exam</Button>
        </div>
      </form>
    </Card>
  );
}

function RuleEditor({ rules, onChange }: { rules: SelectionRule[]; onChange: (rules: SelectionRule[]) => void }) {
  return (
    <div className="space-y-2">
      {rules.map((rule, index) => (
        <div key={index} className="flex flex-wrap items-center gap-2">
          <Select
            className="w-[185px]"
            value={rule.question_type}
            onChange={(e) => onChange(rules.map((r, i) => i === index ? { ...r, question_type: e.target.value as QuestionType } : r))}
          >
            {Object.entries(TYPE_LABEL).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </Select>
          <Select
            className="w-[140px]"
            value={rule.difficulty ?? ""}
            onChange={(e) => onChange(rules.map((r, i) => i === index ? { ...r, difficulty: (e.target.value || null) as Difficulty | null } : r))}
          >
            <option value="">Any difficulty</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </Select>
          <Input
            type="number"
            min="1"
            className="w-[90px]"
            value={rule.count}
            onChange={(e) => onChange(rules.map((r, i) => i === index ? { ...r, count: Math.max(1, Number(e.target.value)) } : r))}
          />
          {rules.length > 1 && (
            <Button type="button" variant="ghost" size="sm" onClick={() => onChange(rules.filter((_, i) => i !== index))}>
              Remove
            </Button>
          )}
        </div>
      ))}
      <Button type="button" variant="secondary" size="sm" className="mt-1" onClick={() => onChange([...rules, { question_type: "short_answer" as QuestionType, difficulty: null, count: 1 }])}>
        Add rule
      </Button>
    </div>
  );
}

function ToggleRow({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={cx(
        "flex items-start gap-3 rounded-[11px] border px-3.5 py-3 text-left transition",
        checked ? "border-accent bg-accent-soft" : "border-line hover:bg-sunken",
      )}
    >
      <span
        className={cx(
          "mt-0.5 flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition",
          checked ? "bg-accent" : "bg-line-strong",
        )}
      >
        <span
          className={cx(
            "h-4 w-4 rounded-full bg-white transition-transform",
            checked && "translate-x-4",
          )}
        />
      </span>
      <span>
        <span className="block text-[13px] font-medium text-ink">{label}</span>
        <span className="block text-[12px] text-ink-muted">{hint}</span>
      </span>
    </button>
  );
}

/* ------------------------------------------------------------------ enrolment */
function EnrollmentButton({ exam }: { exam: Exam }) {
  const [open, setOpen] = useState(false);
  const [enrolled, setEnrolled] = useState<EnrollmentRow[]>([]);
  const [candidates, setCandidates] = useState<CandidateRow[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rows, roster] = await Promise.all([
        api.get<EnrollmentRow[]>(`/exams/${exam.id}/enrollments`),
        api.get<CandidateRow[]>("/admin/candidates"),
      ]);
      setEnrolled(rows);
      setCandidates(roster);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not load enrolments", "rose");
    } finally {
      setLoading(false);
    }
  }, [exam.id]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  async function assign() {
    if (selected.size === 0) return;
    setBusy(true);
    try {
      const response = await api.post<{ detail: string }>(`/exams/${exam.id}/enrollments`, {
        candidate_ids: [...selected],
      });
      toast(response.detail, "mint");
      setSelected(new Set());
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not enrol", "rose");
    } finally {
      setBusy(false);
    }
  }

  async function remove(candidateId: string) {
    try {
      await api.delete(`/exams/${exam.id}/enrollments/${candidateId}`);
      toast("Enrolment removed", "neutral");
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not remove the enrolment", "rose");
    }
  }

  const enrolledIds = new Set(enrolled.map((row) => row.candidate_id));
  const available = candidates.filter(
    (candidate) =>
      !enrolledIds.has(candidate.id) &&
      (!search.trim() ||
        `${candidate.full_name} ${candidate.email}`.toLowerCase().includes(search.toLowerCase())),
  );

  return (
    <>
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
        Candidates
      </Button>

      {open && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-ink/40 px-5 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div className="w-full max-w-3xl" onClick={(e) => e.stopPropagation()}>
            <Card className="animate-rise max-h-[82vh] overflow-y-auto">
              <SectionTitle
                title="Assigned candidates"
                hint={`Only enrolled candidates can see or sit ${exam.title}.`}
                action={
                  <Button size="sm" variant="secondary" onClick={() => setOpen(false)}>
                    Close
                  </Button>
                }
              />

              {loading ? (
                <Skeleton className="h-40 rounded-[12px]" />
              ) : (
                <div className="grid gap-5 md:grid-cols-2">
                  {/* -------------------------------------------- enrolled */}
                  <div>
                    <p className="mb-2 text-[12px] font-medium uppercase tracking-wide text-ink-muted">
                      Enrolled ({enrolled.length})
                    </p>
                    {enrolled.length === 0 ? (
                      <EmptyState
                        title="Nobody assigned"
                        body="This paper is invisible to every candidate until you assign someone."
                      />
                    ) : (
                      <ul className="divide-y divide-line rounded-[11px] border border-line">
                        {enrolled.map((row) => (
                          <li key={row.candidate_id} className="flex items-center gap-2 px-3 py-2.5">
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-[13px] font-medium text-ink">
                                {row.full_name}
                              </p>
                              <p className="truncate text-[11.5px] text-ink-muted">{row.email}</p>
                            </div>
                            {row.login_access && (
                              <Badge
                                tone={
                                  row.login_access === "approved"
                                    ? "mint"
                                    : row.login_access === "pending"
                                      ? "amber"
                                      : "rose"
                                }
                              >
                                {row.login_access}
                              </Badge>
                            )}
                            {row.has_attempted ? (
                              <Badge tone="accent">sat</Badge>
                            ) : (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => remove(row.candidate_id)}
                              >
                                Remove
                              </Button>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  {/* ------------------------------------------- available */}
                  <div>
                    <p className="mb-2 text-[12px] font-medium uppercase tracking-wide text-ink-muted">
                      Add candidates
                    </p>
                    <Field label="Search">
                      <Input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Name or email"
                      />
                    </Field>

                    <div className="mt-3 max-h-64 overflow-y-auto rounded-[11px] border border-line">
                      {available.length === 0 ? (
                        <p className="px-3 py-6 text-center text-[12.5px] text-ink-muted">
                          Everyone matching is already enrolled.
                        </p>
                      ) : (
                        <ul className="divide-y divide-line">
                          {available.map((candidate) => {
                            const checked = selected.has(candidate.id);
                            return (
                              <li key={candidate.id}>
                                <label className="flex cursor-pointer items-center gap-2.5 px-3 py-2.5 transition hover:bg-sunken">
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() =>
                                      setSelected((current) => {
                                        const next = new Set(current);
                                        if (next.has(candidate.id)) next.delete(candidate.id);
                                        else next.add(candidate.id);
                                        return next;
                                      })
                                    }
                                    className="h-4 w-4 accent-[var(--color-accent)]"
                                  />
                                  <span className="min-w-0 flex-1">
                                    <span className="block truncate text-[13px] font-medium text-ink">
                                      {candidate.full_name}
                                    </span>
                                    <span className="block truncate text-[11.5px] text-ink-muted">
                                      {candidate.email}
                                    </span>
                                  </span>
                                </label>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </div>

                    <div className="mt-3 flex justify-end">
                      <Button size="sm" loading={busy} disabled={selected.size === 0} onClick={assign}>
                        Assign {selected.size > 0 ? `${selected.size} ` : ""}candidate
                        {selected.size === 1 ? "" : "s"}
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
