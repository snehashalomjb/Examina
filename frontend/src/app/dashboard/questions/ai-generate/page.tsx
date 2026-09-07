"use client";

import { useEffect, useState } from "react";

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
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type {
  AiDraft,
  Difficulty,
  DraftStatus,
  QuestionCategory,
  QuestionType,
  Subject,
} from "@/lib/types";
import { CATEGORY_LABEL, QUESTION_TYPE_LABEL } from "@/lib/types";

const DIFFICULTY_OPTIONS: { value: Difficulty; label: string }[] = [
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
];

const STATUS_TONE: Record<DraftStatus, "amber" | "mint" | "rose"> = {
  pending: "amber",
  approved: "mint",
  rejected: "rose",
};

export default function AiGeneratePage() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [drafts, setDrafts] = useState<AiDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [subjectId, setSubjectId] = useState("");
  const [category, setCategory] = useState<QuestionCategory>("technical");
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [questionType, setQuestionType] = useState<QuestionType>("mcq");
  const [count, setCount] = useState("5");
  const [extraInstructions, setExtraInstructions] = useState("");

  // Edit/review
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editPayload, setEditPayload] = useState("");
  const [reviewBusy, setReviewBusy] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<DraftStatus | "">("");

  async function loadDrafts() {
    try {
      const data = await api.get<AiDraft[]>(
        `/questions/ai-drafts${statusFilter ? `?status=${statusFilter}` : ""}`,
      );
      setDrafts(data);
    } catch {
      // non-fatal
    }
  }

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      try {
        const [subjectData] = await Promise.all([api.get<Subject[]>("/subjects")]);
        if (!cancelled) {
          setSubjects(subjectData);
          if (subjectData[0]) setSubjectId(subjectData[0].id);
        }
        await loadDrafts();
      } catch (err) {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Could not load page.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user]);

  useEffect(() => {
    if (user) void loadDrafts();
  }, [statusFilter]);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setGenerating(true);
    setError(null);
    try {
      const newDrafts = await api.post<AiDraft[]>("/questions/ai-generate", {
        subject_id: subjectId || null,
        category,
        topic: topic.trim() || null,
        difficulty,
        question_type: questionType,
        count: Number(count),
        extra_instructions: extraInstructions.trim() || null,
      });
      toast(`Generated ${newDrafts.length} draft(s) — review them below`, "mint");
      setDrafts((prev) => [...newDrafts, ...prev]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Generation failed.");
    } finally {
      setGenerating(false);
    }
  }

  async function approve(draft: AiDraft) {
    setReviewBusy(draft.id);
    try {
      let payload = draft.payload;
      if (editingId === draft.id) {
        try {
          payload = JSON.parse(editPayload);
        } catch {
          toast("Invalid JSON — please fix before approving", "rose");
          setReviewBusy(null);
          return;
        }
      }
      await api.put(`/questions/ai-drafts/${draft.id}/approve`, { payload });
      setDrafts((prev) =>
        prev.map((d) => (d.id === draft.id ? { ...d, status: "approved" as DraftStatus } : d))
      );
      setEditingId(null);
      toast("Question added to the bank!", "mint");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Approval failed", "rose");
    } finally {
      setReviewBusy(null);
    }
  }

  async function reject(draft: AiDraft, reason: string) {
    setReviewBusy(draft.id);
    try {
      await api.put(`/questions/ai-drafts/${draft.id}/reject`, { reason });
      setDrafts((prev) =>
        prev.map((d) => (d.id === draft.id ? { ...d, status: "rejected" as DraftStatus } : d))
      );
      toast("Draft rejected", "neutral");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Rejection failed", "rose");
    } finally {
      setReviewBusy(null);
    }
  }

  if (!user) return null;

  const pendingCount = drafts.filter((d) => d.status === "pending").length;

  return (
    <div className="space-y-6">
      <Hero
        title="AI Question Generation"
        body="Generate question drafts with AI. Every draft requires your review before it enters the live question bank."
      />

      {error && <Alert tone="rose">{error}</Alert>}

      <div className="grid gap-5 lg:grid-cols-[1fr_1.5fr]">
        {/* Generation form */}
        <Card>
          <SectionTitle
            title="Generate Questions"
            hint="Powered by the configured AI provider (or built-in stub in development)"
          />
          <form onSubmit={generate} className="space-y-4">
            <Field label="Category">
              <Select
                value={category}
                onChange={(e) => setCategory(e.target.value as QuestionCategory)}
              >
                {(Object.entries(CATEGORY_LABEL) as [QuestionCategory, string][]).map(
                  ([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  )
                )}
              </Select>
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Question Type">
                <Select
                  value={questionType}
                  onChange={(e) => setQuestionType(e.target.value as QuestionType)}
                >
                  {(
                    [
                      "mcq",
                      "multi_select",
                      "true_false",
                      "fill_blank",
                      "numerical",
                      "short_answer",
                      "coding",
                    ] as QuestionType[]
                  ).map((qt) => (
                    <option key={qt} value={qt}>
                      {QUESTION_TYPE_LABEL[qt]}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Difficulty">
                <Select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value as Difficulty)}
                >
                  {DIFFICULTY_OPTIONS.map(({ value, label }) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            <Field
              label="Topic (optional)"
              hint="e.g. 'Data Structures', 'Profit and Loss', 'Python OOP'"
            >
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Leave blank for general questions"
              />
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Subject (optional)">
                <Select value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
                  <option value="">— None —</option>
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.code} — {s.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Count" hint="1–20 questions">
                <Input
                  type="number"
                  min="1"
                  max="20"
                  value={count}
                  onChange={(e) => setCount(e.target.value)}
                />
              </Field>
            </div>

            <Field label="Extra instructions (optional)" hint="Injected into the generation prompt">
              <Textarea
                value={extraInstructions}
                onChange={(e) => setExtraInstructions(e.target.value)}
                rows={2}
                placeholder="e.g. 'Focus on time complexity. Avoid trivial examples.'"
              />
            </Field>

            <Button type="submit" loading={generating} className="w-full">
              {generating ? "Generating…" : "Generate Drafts"}
            </Button>
          </form>
        </Card>

        {/* Draft review panel */}
        <div className="space-y-4">
          <Card>
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-[15px] font-semibold tracking-tight text-ink">
                  Draft Review Queue
                </h2>
                {pendingCount > 0 && (
                  <p className="mt-0.5 text-[13px] text-amber">
                    {pendingCount} draft{pendingCount !== 1 ? "s" : ""} awaiting your review
                  </p>
                )}
              </div>
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as DraftStatus | "")}
                className="w-36"
              >
                <option value="">All drafts</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </Select>
            </div>
          </Card>

          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-40 rounded-[14px]" />
              ))}
            </div>
          ) : drafts.length === 0 ? (
            <EmptyState
              title="No drafts yet"
              body="Generate some questions using the form and they will appear here for review."
            />
          ) : (
            <div className="space-y-3">
              {drafts.map((draft) => (
                <DraftCard
                  key={draft.id}
                  draft={draft}
                  editing={editingId === draft.id}
                  editPayload={editPayload}
                  busy={reviewBusy === draft.id}
                  onStartEdit={() => {
                    setEditingId(draft.id);
                    setEditPayload(JSON.stringify(draft.payload, null, 2));
                  }}
                  onCancelEdit={() => setEditingId(null)}
                  onEditChange={setEditPayload}
                  onApprove={() => approve(draft)}
                  onReject={(reason) => reject(draft, reason)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DraftCard({
  draft,
  editing,
  editPayload,
  busy,
  onStartEdit,
  onCancelEdit,
  onEditChange,
  onApprove,
  onReject,
}: {
  draft: AiDraft;
  editing: boolean;
  editPayload: string;
  busy: boolean;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onEditChange: (v: string) => void;
  onApprove: () => void;
  onReject: (reason: string) => void;
}) {
  const [rejectReason, setRejectReason] = useState("");
  const [rejecting, setRejecting] = useState(false);

  const p = draft.payload as Record<string, unknown>;
  const options = (p.options as Array<{ text: string; is_correct?: boolean }>) ?? [];

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={STATUS_TONE[draft.status]}>{draft.status}</Badge>
          <Badge>{QUESTION_TYPE_LABEL[draft.question_type]}</Badge>
          <Badge>{CATEGORY_LABEL[draft.category]}</Badge>
          {draft.topic && <Badge>{draft.topic}</Badge>}
          <Badge>{draft.difficulty}</Badge>
          <span className="text-[11px] text-ink-muted">via {draft.provider}</span>
          {draft.error && <Badge tone="rose">error</Badge>}
        </div>
      </div>

      {draft.error ? (
        <Alert tone="rose" title="Generation error">
          {draft.error}
        </Alert>
      ) : editing ? (
        <div className="mt-3">
          <Field label="Edit payload (JSON)" hint="Edit then approve to save to the question bank">
            <Textarea
              value={editPayload}
              onChange={(e) => onEditChange(e.target.value)}
              rows={10}
              className="font-mono text-[12px]"
            />
          </Field>
        </div>
      ) : (
        <div className="mt-3">
          <p className="text-[13.5px] leading-relaxed text-ink whitespace-pre-wrap">
            {(p.body as string) || "—"}
          </p>
          {options.length > 0 && (
            <ul className="mt-2 space-y-1">
              {options.map((opt, i) => (
                <li
                  key={i}
                  className={cx(
                    "flex items-center gap-2 rounded-[8px] px-2.5 py-1.5 text-[13px]",
                    opt.is_correct
                      ? "bg-mint-soft text-mint border border-mint/20"
                      : "bg-sunken text-ink-soft"
                  )}
                >
                  <span className="shrink-0 font-medium">{String.fromCharCode(65 + i)}.</span>
                  {String(opt.text)}
                  {opt.is_correct && <span className="ml-auto text-[11px]">✓ correct</span>}
                </li>
              ))}
            </ul>
          )}
          {typeof p.explanation === "string" && (
            <p className="mt-2 text-[12.5px] text-ink-muted italic border-l-2 border-accent/40 pl-3">
              {p.explanation}
            </p>
          )}
        </div>
      )}

      {draft.status === "pending" && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            {!editing ? (
              <>
                <Button size="sm" loading={busy} onClick={onApprove}>
                  Approve & Add to Bank
                </Button>
                <Button size="sm" variant="secondary" onClick={onStartEdit}>
                  Edit first
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setRejecting((v) => !v)}
                >
                  Reject
                </Button>
              </>
            ) : (
              <>
                <Button size="sm" loading={busy} onClick={onApprove}>
                  Approve with edits
                </Button>
                <Button size="sm" variant="secondary" onClick={onCancelEdit}>
                  Cancel
                </Button>
              </>
            )}
          </div>
          {rejecting && (
            <div className="flex items-center gap-2">
              <Input
                placeholder="Reason for rejection…"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                className="flex-1"
              />
              <Button
                size="sm"
                variant="danger"
                loading={busy}
                onClick={() => {
                  if (rejectReason.trim()) {
                    onReject(rejectReason.trim());
                    setRejecting(false);
                  }
                }}
              >
                Confirm
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setRejecting(false)}>
                Cancel
              </Button>
            </div>
          )}
        </div>
      )}

      {draft.status === "approved" && draft.published_question_id && (
        <p className="mt-3 text-[12px] text-mint">
          ✓ Added to question bank
        </p>
      )}

      {draft.status === "rejected" && draft.reject_reason && (
        <p className="mt-3 text-[12px] text-rose">
          Rejected: {draft.reject_reason}
        </p>
      )}
    </Card>
  );
}
