"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AIGenerator } from "@/components/AIGenerator";
import { CandidateSelector } from "@/components/CandidateSelector";
import { ExamCategoryCard, ExamCategoryType } from "@/components/ExamCategoryCard";
import { Hero } from "@/components/Hero";
import { PaperPreview } from "@/components/PaperPreview";
import { QuestionBankSelector } from "@/components/QuestionBankSelector";
import { QuestionEditor } from "@/components/QuestionEditor";
import { QuestionImporter } from "@/components/QuestionImporter";
import { QuestionPool } from "@/components/QuestionPool";
import {
  Alert,
  Badge,
  Button,
  Card,
  Field,
  Input,
  Modal,
  Select,
  Textarea,
  cx,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type {
  Difficulty,
  Exam,
  ExamPool,
  Question,
  QuestionType,
  SelectionRule,
  Subject,
} from "@/lib/types";
import { QUESTION_TYPE_LABEL as TYPE_LABEL } from "@/lib/types";

interface ExamPattern {
  id: string;
  name: string;
  category: ExamCategoryType;
  description: string;
  duration_minutes: number;
  passing_percentage: number;
  declared_total_marks: number;
  negative_marking: boolean;
  default_course?: string;
  default_dept?: string;
  default_sem?: string;
  default_company?: string;
  default_role?: string;
  sections: Array<{
    name: string;
    description: string;
    duration_minutes: number | null;
    marks_per_question: number;
    rules: SelectionRule[];
  }>;
}

const ACADEMIC_PATTERNS: ExamPattern[] = [
  {
    id: "acad-final",
    name: "Semester Final Examination (Comprehensive)",
    category: "academic",
    description: "Comprehensive end-term exam with mixed objective MCQs, short explanations, deep essays, and handwritten diagram uploads.",
    duration_minutes: 90,
    passing_percentage: 40,
    declared_total_marks: 100,
    negative_marking: true,
    default_course: "B.Tech Computer Science & Engineering",
    default_dept: "Computer Science & Engineering",
    default_sem: "Semester IV",
    sections: [
      {
        name: "Section A: Objective & Conceptual",
        description: "MCQs and multi-select questions",
        duration_minutes: 30,
        marks_per_question: 2,
        rules: [
          { question_type: "mcq", difficulty: "easy", count: 5 },
          { question_type: "mcq", difficulty: "medium", count: 5 },
          { question_type: "multi_select", difficulty: "medium", count: 3 },
        ],
      },
      {
        name: "Section B: Analytical & Descriptive",
        description: "Short and long answers with handwritten diagrams",
        duration_minutes: 60,
        marks_per_question: 5,
        rules: [
          { question_type: "short_answer", difficulty: "medium", count: 3 },
          { question_type: "long_answer", difficulty: "hard", count: 1 },
          { question_type: "image_upload", difficulty: "medium", count: 1 },
        ],
      },
    ],
  },
  {
    id: "acad-midterm",
    name: "Mid-Term / Unit Topic Assessment",
    category: "academic",
    description: "Focused periodic unit test evaluating core theoretical concepts and basic problem solving.",
    duration_minutes: 45,
    passing_percentage: 50,
    declared_total_marks: 50,
    negative_marking: false,
    default_course: "B.Tech CSE",
    default_dept: "CSE",
    default_sem: "Semester III",
    sections: [
      {
        name: "Unit Evaluation",
        description: "Objective questions and short explanations",
        duration_minutes: 45,
        marks_per_question: 2,
        rules: [
          { question_type: "mcq", difficulty: "medium", count: 6 },
          { question_type: "fill_blank", difficulty: "easy", count: 2 },
          { question_type: "short_answer", difficulty: "medium", count: 2 },
        ],
      },
    ],
  },
  {
    id: "acad-speedquiz",
    name: "Objective / Speed Quiz Assessment",
    category: "academic",
    description: "Rapid-fire purely objective test (MCQ, True/False, Fill in blanks) with instant results auto-publishing.",
    duration_minutes: 20,
    passing_percentage: 60,
    declared_total_marks: 30,
    negative_marking: false,
    default_course: "BCA / MCA",
    default_dept: "Information Technology",
    default_sem: "Semester II",
    sections: [
      {
        name: "Speed Quiz",
        description: "Fast-paced objective questions",
        duration_minutes: 20,
        marks_per_question: 2,
        rules: [
          { question_type: "mcq", difficulty: "easy", count: 6 },
          { question_type: "true_false", difficulty: "easy", count: 3 },
          { question_type: "fill_blank", difficulty: "easy", count: 3 },
        ],
      },
    ],
  },
  {
    id: "acad-labviva",
    name: "Practical / Lab Viva & Submission Exam",
    category: "academic",
    description: "Laboratory evaluation testing practical code implementations, architecture diagrams, and viva questions.",
    duration_minutes: 60,
    passing_percentage: 50,
    declared_total_marks: 60,
    negative_marking: false,
    default_course: "B.Tech IT",
    default_dept: "Software Engineering",
    default_sem: "Semester VI",
    sections: [
      {
        name: "Practical & Viva",
        description: "Architecture diagrams, code analysis, and viva short answers",
        duration_minutes: 60,
        marks_per_question: 5,
        rules: [
          { question_type: "mcq", difficulty: "medium", count: 4 },
          { question_type: "short_answer", difficulty: "medium", count: 2 },
          { question_type: "image_upload", difficulty: "hard", count: 1 },
        ],
      },
    ],
  },
  {
    id: "acad-essay",
    name: "Theoretical & Descriptive Essay Examination",
    category: "academic",
    description: "Deep descriptive examination requiring long structured essays, evaluated via rubric scoring.",
    duration_minutes: 75,
    passing_percentage: 45,
    declared_total_marks: 80,
    negative_marking: false,
    default_course: "M.Sc Computer Science",
    default_dept: "Computer Science",
    default_sem: "Semester I",
    sections: [
      {
        name: "Descriptive Papers",
        description: "In-depth theoretical analyses and essays",
        duration_minutes: 75,
        marks_per_question: 10,
        rules: [
          { question_type: "short_answer", difficulty: "medium", count: 3 },
          { question_type: "long_answer", difficulty: "hard", count: 2 },
        ],
      },
    ],
  },
  {
    id: "acad-scholarship",
    name: "Merit Scholarship & National Entrance Test",
    category: "academic",
    description: "High-stakes competitive exam with strict proctoring, negative marking, and high difficulty threshold.",
    duration_minutes: 60,
    passing_percentage: 70,
    declared_total_marks: 100,
    negative_marking: true,
    default_course: "National Entrance Test",
    default_dept: "Engineering Admissions",
    default_sem: "2026 Batch",
    sections: [
      {
        name: "Competitive Screening",
        description: "High difficulty problems with negative marking",
        duration_minutes: 60,
        marks_per_question: 3,
        rules: [
          { question_type: "mcq", difficulty: "hard", count: 8 },
          { question_type: "multi_select", difficulty: "hard", count: 3 },
          { question_type: "numerical", difficulty: "hard", count: 2 },
        ],
      },
    ],
  },
];

const CORPORATE_PATTERNS: ExamPattern[] = [
  {
    id: "corp-sde",
    name: "Full-Stack Software Engineer (SDE-1) Assessment",
    category: "corporate",
    description: "4-stage evaluation: Quantitative Aptitude, Core CS & Web Tech, System Design, and Hands-on Coding.",
    duration_minutes: 90,
    passing_percentage: 70,
    declared_total_marks: 100,
    negative_marking: true,
    default_company: "TechCorp Global",
    default_role: "Full-Stack Software Engineer (SDE-1)",
    sections: [
      {
        name: "Section 1: Quantitative & Analytical Aptitude",
        description: "Problem solving and quantitative skills",
        duration_minutes: 20,
        marks_per_question: 2,
        rules: [{ question_type: "mcq", difficulty: "medium", count: 4, category: "aptitude" }],
      },
      {
        name: "Section 2: Core CS & Web Technologies",
        description: "React, TypeScript, databases, and APIs",
        duration_minutes: 30,
        marks_per_question: 3,
        rules: [{ question_type: "mcq", difficulty: "medium", count: 5, category: "technical" }],
      },
      {
        name: "Section 3: Hands-on Coding Challenge",
        description: "Algorithmic programming implementation",
        duration_minutes: 40,
        marks_per_question: 20,
        rules: [{ question_type: "coding", difficulty: "easy", count: 1, category: "coding" }],
      },
    ],
  },
  {
    id: "corp-aptitude",
    name: "Quantitative & Logical Aptitude Screening",
    category: "corporate",
    description: "First-round screening test evaluating mathematical acumen, data interpretation, and deductive logic.",
    duration_minutes: 45,
    passing_percentage: 65,
    declared_total_marks: 60,
    negative_marking: true,
    default_company: "Apex Strategic Consulting",
    default_role: "Associate Consultant / Analyst",
    sections: [
      {
        name: "Section A: Quantitative Ability",
        description: "Arithmetic, algebra, and data interpretation",
        duration_minutes: 25,
        marks_per_question: 2.5,
        rules: [{ question_type: "mcq", difficulty: "medium", count: 5, category: "aptitude" }],
      },
      {
        name: "Section B: Logical & Critical Reasoning",
        description: "Puzzles, syllogisms, and series",
        duration_minutes: 20,
        marks_per_question: 2.5,
        rules: [{ question_type: "mcq", difficulty: "medium", count: 5, category: "logical_reasoning" }],
      },
    ],
  },
  {
    id: "corp-data-analyst",
    name: "Data Analyst & BI Specialist Assessment",
    category: "corporate",
    description: "Evaluates SQL database querying, statistical modeling, data interpretation, and business insights.",
    duration_minutes: 60,
    passing_percentage: 60,
    declared_total_marks: 75,
    negative_marking: false,
    default_company: "FinTech Global Solutions",
    default_role: "Data Analyst & BI Specialist",
    sections: [
      {
        name: "SQL & Relational Databases",
        description: "Joins, aggregations, window functions",
        duration_minutes: 30,
        marks_per_question: 3,
        rules: [{ question_type: "mcq", difficulty: "medium", count: 4, category: "technical" }],
      },
      {
        name: "Quantitative & Business Analytics",
        description: "Statistics and business data interpretation",
        duration_minutes: 30,
        marks_per_question: 3,
        rules: [{ question_type: "mcq", difficulty: "medium", count: 4, category: "aptitude" }],
      },
    ],
  },
  {
    id: "corp-frontend",
    name: "Senior Frontend Engineer Assessment",
    category: "corporate",
    description: "Specialized assessment for Frontend Developers: React 19, TypeScript, Web Performance, and UI coding.",
    duration_minutes: 75,
    passing_percentage: 70,
    declared_total_marks: 80,
    negative_marking: false,
    default_company: "MetaLab Innovations",
    default_role: "Senior Frontend Engineer (React / Next.js)",
    sections: [
      {
        name: "HTML5, CSS & Web Architecture",
        description: "DOM, Layouts, Box Model, Performance",
        duration_minutes: 25,
        marks_per_question: 2,
        rules: [{ question_type: "mcq", difficulty: "medium", count: 4, category: "technical" }],
      },
      {
        name: "React, State & TypeScript",
        description: "Hooks, reconciliation, typing",
        duration_minutes: 25,
        marks_per_question: 3,
        rules: [{ question_type: "mcq", difficulty: "medium", count: 4, category: "technical" }],
      },
      {
        name: "Frontend Coding Challenge",
        description: "Component logic and algorithmic transformation",
        duration_minutes: 25,
        marks_per_question: 20,
        rules: [{ question_type: "coding", difficulty: "easy", count: 1, category: "coding" }],
      },
    ],
  },
  {
    id: "corp-backend",
    name: "Backend & Distributed Systems Assessment",
    category: "corporate",
    description: "Advanced backend engineering: OS concurrency, database transaction engines, Raft/WAL, and coding.",
    duration_minutes: 90,
    passing_percentage: 65,
    declared_total_marks: 100,
    negative_marking: true,
    default_company: "CloudScale Systems",
    default_role: "Backend / Distributed Systems Engineer",
    sections: [
      {
        name: "Operating Systems & Networking",
        description: "Threads, sockets, TCP, race conditions",
        duration_minutes: 25,
        marks_per_question: 3,
        rules: [{ question_type: "mcq", difficulty: "hard", count: 4, category: "technical" }],
      },
      {
        name: "Databases, WAL & Distributed Systems",
        description: "Raft, 2PC, MVCC, Indexing",
        duration_minutes: 25,
        marks_per_question: 3,
        rules: [{ question_type: "mcq", difficulty: "hard", count: 4, category: "technical" }],
      },
      {
        name: "Backend Coding Challenge",
        description: "Algorithmic and concurrency problem solving",
        duration_minutes: 40,
        marks_per_question: 25,
        rules: [{ question_type: "coding", difficulty: "medium", count: 1, category: "coding" }],
      },
    ],
  },
  {
    id: "corp-freshers",
    name: "Freshers Campus Graduate Hiring Drive",
    category: "corporate",
    description: "Standardized 4-section campus test: Quantitative, Logical Reasoning, Verbal Communication, and Programming.",
    duration_minutes: 60,
    passing_percentage: 60,
    declared_total_marks: 75,
    negative_marking: false,
    default_company: "Tata Tech Global",
    default_role: "Graduate Trainee Engineer (GET)",
    sections: [
      {
        name: "Quantitative Aptitude",
        description: "Numerical problem solving",
        duration_minutes: 15,
        marks_per_question: 2,
        rules: [{ question_type: "mcq", difficulty: "easy", count: 3, category: "aptitude" }],
      },
      {
        name: "Logical & Deductive Reasoning",
        description: "Puzzles and series",
        duration_minutes: 15,
        marks_per_question: 2,
        rules: [{ question_type: "mcq", difficulty: "easy", count: 3, category: "logical_reasoning" }],
      },
      {
        name: "Verbal Ability & English",
        description: "Grammar and comprehension",
        duration_minutes: 15,
        marks_per_question: 2,
        rules: [{ question_type: "mcq", difficulty: "easy", count: 2, category: "verbal_ability" }],
      },
      {
        name: "Basic Computer Science Foundations",
        description: "Syntax and core concepts",
        duration_minutes: 15,
        marks_per_question: 2,
        rules: [{ question_type: "mcq", difficulty: "easy", count: 2, category: "technical" }],
      },
    ],
  },
];

export default function CreateExamWizard() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  const router = useRouter();
  // ?exam=<id> reopens a draft. Saving a draft you cannot come back to is a trap, and
  // the pool step deliberately leaves drafts behind.
  const resumeId = useSearchParams().get("exam");

  // Step 1: Category
  const [category, setCategory] = useState<ExamCategoryType>("academic");
  // Step 2: Pattern Preset
  const [selectedPatternId, setSelectedPatternId] = useState<string>("");
  // Step 3: Metadata
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [declaredTotalMarks, setDeclaredTotalMarks] = useState<number | "">(100);
  const [passingPercentage, setPassingPercentage] = useState<number | "">(50);
  const [negativeMarking, setNegativeMarking] = useState(false);
  const [maxAttempts, setMaxAttempts] = useState(1);
  const [difficulty, setDifficulty] = useState<Difficulty | "">("");

  // Academic fields
  const [course, setCourse] = useState("");
  const [department, setDepartment] = useState("");
  const [semester, setSemester] = useState("");

  // Corporate fields
  const [companyName, setCompanyName] = useState("");
  const [jobRole, setJobRole] = useState("");

  // Randomisation. The pool and the paper are different things: the pool is every
  // question the exam may draw from, the paper is what one candidate sits.
  const [randomize, setRandomize] = useState(true);
  const [shuffleOptions, setShuffleOptions] = useState(true);

  // Step 4: Sections & Rules
  const [sections, setSections] = useState<
    Array<{
      name: string;
      description: string;
      duration_minutes: number | null;
      marks_per_question: number | null;
      negative_marks: number | null;
      rules: SelectionRule[];
    }>
  >([]);

  // Step 5: the question pool.
  //
  // The pool lives on the server rather than in this component's state, because three
  // of the four ways to fill it - authoring, AI approval, file import - create real
  // questions that have to belong to a real exam. So the wizard saves a draft on the
  // way into this step and edits the pool in place from there.
  const [examId, setExamId] = useState<string | null>(null);
  const [pool, setPool] = useState<ExamPool | null>(null);
  const [poolTab, setPoolTab] = useState<"create" | "bank" | "ai" | "import">("bank");
  const [savingDraft, setSavingDraft] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<Question | null>(null);
  const [assignedCount, setAssignedCount] = useState(0);
  /** Review tab: the summary and checklist, or the candidate's-eye paper. */
  const [reviewTab, setReviewTab] = useState<"summary" | "paper">("summary");
  /** Set once the exam is live, so the wizard can show what was published. */
  const [published, setPublished] = useState<{ id: string; questions: number } | null>(
    null,
  );

  // Step 6: Proctoring. AI detects and flags; the examiner rules on it afterwards.
  // Nothing configured here fails a candidate on its own.
  const [proctorWebcam, setProctorWebcam] = useState(true);
  const [proctorGaze, setProctorGaze] = useState(true);
  const [proctorFullscreen, setProctorFullscreen] = useState(true);
  const [proctorBlockCopyPaste, setProctorBlockCopyPaste] = useState(true);
  const [proctorMicrophone, setProctorMicrophone] = useState(true);
  const [proctorSingleDisplay, setProctorSingleDisplay] = useState(true);
  const [gazeSensitivity, setGazeSensitivity] = useState(0.6);
  const [maxTabSwitches, setMaxTabSwitches] = useState(3);
  const [flagOnScore, setFlagOnScore] = useState(45);
  const [terminateOnScore, setTerminateOnScore] = useState(100);
  const [snapshotInterval, setSnapshotInterval] = useState(60);

  // Current wizard step: 1..6
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);

  // Default dates
  useEffect(() => {
    const now = new Date();
    const plus30 = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
    setStartsAt(now.toISOString().slice(0, 16));
    setEndsAt(plus30.toISOString().slice(0, 16));

    async function loadData() {
      try {
        const subjectList = await api.get<Subject[]>("/subjects");
        setSubjects(subjectList);
        if (subjectList.length > 0) setSubjectId(subjectList[0].id);
      } catch {
        toast("Failed to load subjects", "rose");
      }
    }
    void loadData();
  }, []);

  /**
   * Reopen a draft.
   *
   * Everything the wizard collects is read back off the exam, so the second visit is
   * the same form with the same values - not a fresh form that will overwrite half of
   * them with defaults on the next save.
   */
  useEffect(() => {
    if (!resumeId || !user) return;
    let cancelled = false;

    (async () => {
      try {
        const exam = await api.get<Exam>(`/exams/${resumeId}`);
        if (cancelled) return;

        setExamId(exam.id);
        setCategory(exam.exam_type === "corporate" ? "corporate" : "academic");
        setTitle(exam.title);
        setDescription(exam.description ?? "");
        setInstructions(exam.instructions ?? "");
        setSubjectId(exam.subject_id);
        setDurationMinutes(exam.duration_minutes);
        setStartsAt(new Date(exam.starts_at).toISOString().slice(0, 16));
        setEndsAt(new Date(exam.ends_at).toISOString().slice(0, 16));
        setDeclaredTotalMarks(exam.declared_total_marks ?? "");
        setPassingPercentage(exam.passing_percentage ?? "");
        setNegativeMarking(exam.negative_marking);
        setMaxAttempts(exam.max_attempts);
        setDifficulty(exam.difficulty ?? "");
        setRandomize(exam.randomize);
        setShuffleOptions(exam.shuffle_options);
        setCourse(exam.course ?? "");
        setDepartment(exam.department ?? "");
        setSemester(exam.semester ?? "");
        setCompanyName(exam.company_name ?? "");
        setJobRole(exam.job_role ?? "");

        setSections(
          [...exam.sections]
            .sort((a, b) => a.order_index - b.order_index)
            .map((section) => ({
              name: section.name,
              description: section.description ?? "",
              duration_minutes: section.duration_minutes,
              marks_per_question: section.marks_per_question,
              negative_marks: section.negative_marks,
              rules: section.selection_rules?.rules ?? [],
            })),
        );

        const config = exam.proctor_config as unknown as Record<string, unknown>;
        const bool = (key: string, fallback: boolean) =>
          typeof config[key] === "boolean" ? (config[key] as boolean) : fallback;
        const num = (key: string, fallback: number) =>
          typeof config[key] === "number" ? (config[key] as number) : fallback;
        setProctorWebcam(bool("webcam_enabled", true));
        setProctorGaze(bool("gaze_tracking_enabled", true));
        setProctorFullscreen(bool("require_fullscreen", true));
        setProctorBlockCopyPaste(bool("block_copy_paste", true));
        setProctorMicrophone(bool("require_microphone", true));
        setProctorSingleDisplay(bool("require_single_display", true));
        setGazeSensitivity(num("gaze_sensitivity", 0.6));
        setMaxTabSwitches(num("max_tab_switches", 3));
        setFlagOnScore(num("flag_on_score", 45));
        setTerminateOnScore(num("terminate_on_score", 100));
        setSnapshotInterval(num("snapshot_interval_seconds", 60));

        setPool(await api.get<ExamPool>(`/exams/${exam.id}/pool`));
        setStep(5); // straight to the pool, which is why anyone reopens a draft
      } catch (err) {
        toast(
          err instanceof ApiError ? err.message : "Could not open that draft.",
          "rose",
        );
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [resumeId, user]);

  // When pattern is selected, pre-fill fields
  function applyPattern(p: ExamPattern) {
    setSelectedPatternId(p.id);
    setTitle(p.name);
    setDescription(p.description);
    setDurationMinutes(p.duration_minutes);
    setPassingPercentage(p.passing_percentage);
    setDeclaredTotalMarks(p.declared_total_marks);
    setNegativeMarking(p.negative_marking);

    if (p.category === "academic") {
      setCourse(p.default_course || "");
      setDepartment(p.default_dept || "");
      setSemester(p.default_sem || "");
    } else {
      setCompanyName(p.default_company || "");
      setJobRole(p.default_role || "");
    }

    setSections(
      p.sections.map((section) => ({
        ...section,
        marks_per_question: section.marks_per_question,
        negative_marks: null,
      })),
    );
    // A template pre-fills configuration only. It deliberately does not guess at
    // questions: an exam quietly stuffed with 25 loosely-matching questions is worse
    // than an empty pool, because the examiner has no reason to look at it.
  }

  // Calculate total questions needed from all section rules
  const totalQuestionsNeeded = sections.reduce(
    (acc, sec) => acc + sec.rules.reduce((rAcc, r) => rAcc + r.count, 0),
    0
  );

  /** Everything the exam endpoints take, built from the wizard's state. */
  function buildPayload(): Record<string, unknown> {
    const combinedRules: SelectionRule[] = sections.flatMap((sec) => sec.rules);

    const payload: Record<string, unknown> = {
      exam_type: category,
      subject_id: subjectId,
      title: title.trim(),
      description: description.trim() || null,
      instructions: instructions.trim() || null,
      duration_minutes: Number(durationMinutes),
      starts_at: new Date(startsAt).toISOString(),
      ends_at: new Date(endsAt).toISOString(),
      selection_rules: {
        rules: combinedRules.length
          ? combinedRules
          : [{ question_type: "mcq", difficulty: "medium", count: 5 }],
      },
      randomize,
      shuffle_options: shuffleOptions,
      negative_marking: negativeMarking,
      passing_percentage: passingPercentage ? Number(passingPercentage) : null,
      declared_total_marks: declaredTotalMarks ? Number(declaredTotalMarks) : null,
      max_attempts: maxAttempts,
      difficulty: difficulty || null,
      proctor_config: {
        webcam_enabled: proctorWebcam,
        gaze_tracking_enabled: proctorGaze,
        require_fullscreen: proctorFullscreen,
        block_copy_paste: proctorBlockCopyPaste,
        gaze_sensitivity: gazeSensitivity,
        max_tab_switches: maxTabSwitches,
        flag_on_score: flagOnScore,
        terminate_on_score: Math.max(flagOnScore + 1, terminateOnScore),
        snapshot_interval_seconds: snapshotInterval,
        require_microphone: proctorMicrophone,
        require_single_display: proctorSingleDisplay,
      },
      grading_config: { auto_publish_results: false },
      sections: sections.map((sec, idx) => ({
        name: sec.name,
        description: sec.description || null,
        order_index: idx,
        selection_rules: { rules: sec.rules },
        marks_per_question: sec.marks_per_question || null,
        negative_marks: sec.negative_marks ?? null,
        duration_minutes: sec.duration_minutes || null,
      })),
    };

    if (category === "academic") {
      payload.course = course.trim() || null;
      payload.department = department.trim() || null;
      payload.semester = semester.trim() || null;
    } else {
      payload.company_name = companyName.trim() || null;
      payload.job_role = jobRole.trim() || null;
    }
    return payload;
  }

  /** What stops this exam being publishable, in the examiner's words. */
  function configurationProblems(): string[] {
    const found: string[] = [];
    if (!title.trim()) found.push("The exam needs a title.");
    if (!subjectId) found.push("Pick the subject this exam belongs to.");
    if (!startsAt || !endsAt) found.push("Set when the exam opens and closes.");
    else if (new Date(endsAt) <= new Date(startsAt)) {
      found.push("The exam window must end after it starts.");
    } else {
      const windowMinutes =
        (new Date(endsAt).getTime() - new Date(startsAt).getTime()) / 60000;
      if (durationMinutes > windowMinutes) {
        found.push(
          `The ${durationMinutes}-minute duration is longer than the exam window.`,
        );
      }
    }
    if (sections.length === 0) found.push("Add at least one section with selection rules.");
    if (sections.some((sec) => sec.rules.length === 0)) {
      found.push("Every section needs at least one selection rule.");
    }
    if (!sections.some((sec) => sec.name.trim())) found.push("Sections need names.");
    return found;
  }

  /**
   * Create the draft on first call, update it thereafter.
   *
   * Saving before the pool step is what makes authoring, AI approval and file import
   * possible there - all three create questions that must belong to an exam. The exam
   * is a draft throughout, and a draft is invisible to candidates.
   */
  const saveDraft = useCallback(
    async (options?: { quiet?: boolean }): Promise<string | null> => {
      const problems = configurationProblems();
      if (problems.length) {
        toast(problems[0], "rose");
        if (!title.trim() || !subjectId || !startsAt) setStep(3);
        else setStep(4);
        return null;
      }

      setSavingDraft(true);
      try {
        const payload = buildPayload();
        if (examId) {
          await api.patch(`/exams/${examId}`, payload);
          if (!options?.quiet) toast("Draft saved", "mint");
          return examId;
        }
        const created = await api.post<{ id: string }>("/exams", {
          ...payload,
          question_ids: [],
        });
        setExamId(created.id);
        if (!options?.quiet) toast("Draft saved — now build the question pool", "mint");
        return created.id;
      } catch (err) {
        toast(
          err instanceof ApiError
            ? err.problems?.length
              ? `${err.message}: ${err.problems.join(", ")}`
              : err.message
            : "Could not save the draft.",
          "rose",
        );
        return null;
      } finally {
        setSavingDraft(false);
      }
    },
    // buildPayload and configurationProblems read the whole form, so this is
    // deliberately recreated on every render rather than pretending to a dep list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [examId, title, subjectId, startsAt, endsAt, durationMinutes, sections],
  );

  const refreshPool = useCallback(async (id: string) => {
    try {
      setPool(await api.get<ExamPool>(`/exams/${id}/pool`));
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not load the pool.", "rose");
    }
  }, []);

  /** Save the draft, then move to the pool step with a live pool loaded. */
  async function goToPool() {
    const id = await saveDraft({ quiet: Boolean(examId) });
    if (!id) return;
    await refreshPool(id);
    setStep(5);
  }

  async function addFromBank(questionIds: string[]) {
    if (!examId) return;
    try {
      setPool(
        await api.post<ExamPool>(`/exams/${examId}/questions`, { question_ids: questionIds }),
      );
      toast(`${questionIds.length} question(s) added`, "mint");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not add those questions.", "rose");
    }
  }

  async function duplicateIntoExam(question: Question) {
    if (!examId) return;
    try {
      await api.post(`/questions/${question.id}/duplicate`, { exam_id: examId });
      await refreshPool(examId);
      toast("Copied into this exam", "mint");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not duplicate that.", "rose");
    }
  }

  async function publishExam() {
    const id = await saveDraft({ quiet: true });
    if (!id) return;

    setSubmitting(true);
    try {
      await api.post(`/exams/${id}/publish`);
      toast(`"${title}" is published`, "mint");
      setPublished({ id, questions: pool?.required_count ?? 0 });
    } catch (err) {
      if (err instanceof ApiError) {
        toast(
          err.problems?.length ? `${err.message}: ${err.problems.join(", ")}` : err.message,
          "rose",
        );
        await refreshPool(id);
        setStep(5);
      } else {
        toast("Could not publish the exam.", "rose");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const patterns = category === "academic" ? ACADEMIC_PATTERNS : CORPORATE_PATTERNS;

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-12">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Link
              href="/dashboard/exams"
              className="text-xs font-semibold text-ink-muted hover:text-ink transition-colors"
            >
              ← Back to Exams
            </Link>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-ink mt-1">
            Create Examination
          </h1>
          <p className="text-sm text-ink-muted">
            Configure examination mode, choose blueprint patterns, bind question bank pools, and set AI proctoring.
          </p>
        </div>
        <Badge tone={category === "academic" ? "accent" : "purple"}>
          {category === "academic" ? "🎓 Academic Mode" : "💼 Corporate Mode"}
        </Badge>
      </div>

      {/* Published. The wizard stops being a form and becomes a receipt. */}
      {published && (
        <Card className="space-y-4 border-mint/50 bg-mint-soft/20">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-mint text-[16px] text-white">
              ✓
            </span>
            <div>
              <h2 className="text-lg font-bold text-ink">Exam published</h2>
              <p className="text-[13px] text-ink-muted">
                {title} is live for its window. Only assigned candidates can see it.
              </p>
            </div>
          </div>

          <dl className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
            <Summary label="Exam ID" value={published.id.slice(0, 8)} />
            <Summary label="Questions per candidate" value={String(published.questions)} />
            <Summary
              label="Candidates assigned"
              value={assignedCount ? String(assignedCount) : "None yet"}
            />
            <Summary
              label="Window"
              value={`${new Date(startsAt).toLocaleDateString()} → ${new Date(endsAt).toLocaleDateString()}`}
            />
          </dl>

          <div className="rounded-[10px] border border-line bg-surface p-3">
            <p className="text-[11.5px] font-semibold uppercase tracking-wide text-ink-muted">
              How candidates reach it
            </p>
            <p className="mt-1 text-[13px] text-ink-soft">
              There is no shareable link, by design. An assigned candidate signs in and
              finds the exam under <span className="font-medium text-ink">My Exams</span>,
              which is what keeps a paper from being opened by whoever has the URL.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Link href="/dashboard/exams">
              <Button size="sm">Back to exams</Button>
            </Link>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setPublished(null);
                setStep(6);
              }}
            >
              Assign more candidates
            </Button>
            <Link href="/dashboard/exams/create">
              <Button size="sm" variant="ghost">
                Create another
              </Button>
            </Link>
          </div>
        </Card>
      )}

      {/* Stepper Wizard Bar */}
      <div className="flex items-center justify-between rounded-xl border border-line bg-surface p-2 shadow-sm">
        {[
          { num: 1, label: "Category" },
          { num: 2, label: "Pattern" },
          { num: 3, label: "Details" },
          { num: 4, label: "Sections" },
          { num: 5, label: "Question Pool" },
          { num: 6, label: "Candidates" },
          { num: 7, label: "Review & Publish" },
        ].map((s) => (
          <button
            key={s.num}
            type="button"
            onClick={() => setStep(s.num)}
            className={cx(
              "flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-xs font-medium transition-all",
              step === s.num
                ? "bg-accent text-white shadow-sm font-semibold"
                : step > s.num
                ? "text-accent hover:bg-accent-soft/30"
                : "text-ink-muted hover:text-ink hover:bg-surface-elevated"
            )}
          >
            <span
              className={cx(
                "flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold",
                step === s.num
                  ? "bg-white text-accent"
                  : step > s.num
                  ? "bg-accent-soft text-accent"
                  : "bg-line text-ink-muted"
              )}
            >
              {step > s.num ? "✓" : s.num}
            </span>
            <span className="hidden sm:inline">{s.label}</span>
          </button>
        ))}
      </div>

      {/* STEP 1: EXAM CATEGORY */}
      {step === 1 && !published && (
        <div className="space-y-6 animate-fade-in">
          <div className="text-center max-w-xl mx-auto mb-6">
            <h2 className="text-xl font-bold text-ink">Select Examination Category</h2>
            <p className="text-sm text-ink-muted mt-1">
              Choose the operating mode for this examination. Both modes draw directly from your unified question bank.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <ExamCategoryCard
              category="academic"
              selected={category === "academic"}
              onSelect={(cat) => {
                setCategory(cat);
                setSelectedPatternId("");
                setSections([]);
              }}
            />
            <ExamCategoryCard
              category="corporate"
              selected={category === "corporate"}
              onSelect={(cat) => {
                setCategory(cat);
                setSelectedPatternId("");
                setSections([]);
              }}
            />
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <Button
              variant="secondary"
              onClick={() => {
                setSelectedPatternId("");
                setSections([]);
                setStep(3);
              }}
            >
              Skip templates — Create from scratch
            </Button>
            <Button onClick={() => setStep(2)}>Next: Select Exam Pattern →</Button>
          </div>
        </div>
      )}

      {/* STEP 2: PATTERN / BLUEPRINT PRESETS */}
      {step === 2 && !published && (
        <div className="space-y-6 animate-fade-in">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-ink">
                Choose a {category === "academic" ? "Academic" : "Corporate Hiring"} Exam Pattern
              </h2>
              <p className="text-sm text-ink-muted mt-1">
                Select a structured blueprint to pre-configure sections, rules, timers, and question pool filters.
              </p>
            </div>
            <Badge tone={category === "academic" ? "accent" : "purple"}>
              6 {category === "academic" ? "Academic" : "Corporate"} Patterns Available
            </Badge>
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {patterns.map((p) => {
              const isSelected = selectedPatternId === p.id;
              return (
                <div
                  key={p.id}
                  onClick={() => applyPattern(p)}
                  className={cx(
                    "flex flex-col justify-between rounded-xl border p-5 transition-all cursor-pointer",
                    isSelected
                      ? "border-accent bg-accent-soft/20 shadow-md ring-2 ring-accent"
                      : "border-line bg-surface hover:border-line-strong hover:shadow-sm"
                  )}
                >
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <h3 className="text-sm font-bold text-ink leading-snug">{p.name}</h3>
                      {isSelected && (
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent text-white text-[10px] font-bold">
                          ✓
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-ink-muted leading-relaxed mb-4">{p.description}</p>

                    <div className="space-y-1.5 border-t border-line/60 pt-3 text-[11px] text-ink-muted">
                      <div className="flex justify-between">
                        <span>Duration:</span>
                        <span className="font-semibold text-ink">{p.duration_minutes} mins</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Total Marks:</span>
                        <span className="font-semibold text-ink">{p.declared_total_marks}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Sections:</span>
                        <span className="font-semibold text-ink">{p.sections.length} section(s)</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Passing Threshold:</span>
                        <span className="font-semibold text-ink">{p.passing_percentage}%</span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-line">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        applyPattern(p);
                      }}
                      className={cx(
                        "w-full rounded-lg py-1.5 px-3 text-xs font-semibold transition-colors",
                        isSelected
                          ? "bg-accent text-white shadow-sm"
                          : "bg-surface-soft text-ink hover:bg-surface-elevated border border-line"
                      )}
                    >
                      {isSelected ? "Selected Pattern" : "Use This Pattern"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex justify-between pt-4">
            <Button variant="secondary" onClick={() => setStep(1)}>
              ← Back to Category
            </Button>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                onClick={() => {
                  setSelectedPatternId("");
                  setSections([]);
                  setStep(3);
                }}
              >
                Start from scratch instead
              </Button>
              <Button onClick={() => setStep(3)}>Next: Basic Details →</Button>
            </div>
          </div>
        </div>
      )}

      {/* STEP 3: EXAM DETAILS */}
      {step === 3 && !published && (
        <Card className="space-y-5 animate-fade-in">
          <div>
            <h2 className="text-lg font-bold text-ink">Exam Details & Target Configuration</h2>
            <p className="text-xs text-ink-muted">
              Configure titles, window duration, subject binding, and mode-specific parameters.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Exam Title" required>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. CS101 Semester Final Examination"
              />
            </Field>

            <Field label="Primary Subject" required>
              <Select
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
              >
                {subjects.map((sub) => (
                  <option key={sub.id} value={sub.id}>
                    {sub.code} — {sub.name}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <Field label="Description">
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="Short overview of syllabus, topics covered, and evaluation structure..."
            />
          </Field>

          <Field label="Instructions" hint="Shown to the candidate before they start.">
            <Textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={3}
              placeholder="e.g. No calculators. Answer all questions. Read each question carefully..."
            />
          </Field>

          {/* Mode-Specific Fields */}
          {category === "academic" ? (
            <div className="rounded-xl border border-accent/20 bg-accent-soft/10 p-4 space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold text-accent uppercase tracking-wider">
                🎓 Academic Metadata
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label="Course / Degree">
                  <Input
                    value={course}
                    onChange={(e) => setCourse(e.target.value)}
                    placeholder="e.g. B.Tech Computer Science"
                  />
                </Field>
                <Field label="Department">
                  <Input
                    value={department}
                    onChange={(e) => setDepartment(e.target.value)}
                    placeholder="e.g. Computer Science & Eng"
                  />
                </Field>
                <Field label="Semester / Batch">
                  <Input
                    value={semester}
                    onChange={(e) => setSemester(e.target.value)}
                    placeholder="e.g. Semester IV"
                  />
                </Field>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-purple-500/20 bg-purple-50/20 dark:bg-purple-950/20 p-4 space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold text-purple-600 dark:text-purple-400 uppercase tracking-wider">
                💼 Corporate Hiring Metadata
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Company / Organization Name">
                  <Input
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="e.g. TechCorp Global"
                  />
                </Field>
                <Field label="Target Job Role">
                  <Input
                    value={jobRole}
                    onChange={(e) => setJobRole(e.target.value)}
                    placeholder="e.g. Full-Stack Software Engineer (SDE-1)"
                  />
                </Field>
              </div>
            </div>
          )}

          {/* Timing & Scoring */}
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Duration (minutes)" required>
              <Input
                type="number"
                min={5}
                max={600}
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
              />
            </Field>

            <Field label="Declared Total Marks">
              <Input
                type="number"
                min={1}
                value={declaredTotalMarks}
                onChange={(e) => setDeclaredTotalMarks(e.target.value === "" ? "" : Number(e.target.value))}
              />
            </Field>

            <Field label="Passing Percentage (%)">
              <Input
                type="number"
                min={0}
                max={100}
                value={passingPercentage}
                onChange={(e) => setPassingPercentage(e.target.value === "" ? "" : Number(e.target.value))}
              />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Difficulty Level" hint="A descriptive tag shown to candidates.">
              <Select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value as Difficulty | "")}
              >
                <option value="">Mixed</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </Select>
            </Field>

            <Field label="Maximum Attempts">
              <Input
                type="number"
                min={1}
                max={10}
                value={maxAttempts}
                onChange={(e) => setMaxAttempts(Number(e.target.value))}
              />
            </Field>

            <Field
              label="Questions per candidate"
              hint="Calculated from the section rules — never typed, so it cannot contradict them."
            >
              <div className="flex h-[38px] items-center rounded-[10px] border border-line bg-sunken px-3 text-[13px] font-semibold text-ink">
                {totalQuestionsNeeded || "Set by your sections"}
              </div>
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Opens At (Window Start)" required>
              <Input
                type="datetime-local"
                value={startsAt}
                onChange={(e) => setStartsAt(e.target.value)}
              />
            </Field>
            <Field label="Closes At (Window End)" required>
              <Input
                type="datetime-local"
                value={endsAt}
                onChange={(e) => setEndsAt(e.target.value)}
              />
            </Field>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <label className="flex items-center gap-2 text-xs font-semibold text-ink cursor-pointer">
              <input
                type="checkbox"
                checked={negativeMarking}
                onChange={(e) => setNegativeMarking(e.target.checked)}
                className="h-4 w-4 rounded border-line text-accent focus:ring-accent"
              />
              Enable Negative Marking
            </label>
          </div>

          <div className="flex justify-between pt-4 border-t border-line">
            <Button variant="secondary" onClick={() => setStep(2)}>
              ← Back to Patterns
            </Button>
            <Button onClick={() => setStep(4)}>Next: Configure Sections →</Button>
          </div>
        </Card>
      )}

      {/* STEP 4: SECTIONS & SELECTION RULES */}
      {step === 4 && !published && (
        <div className="space-y-6 animate-fade-in">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-ink">Exam Sections & Selection Rules</h2>
              <p className="text-sm text-ink-muted mt-0.5">
                Define the sections and algorithmic rules to draw random questions from your pool.
              </p>
            </div>
            <Button
              size="sm"
              onClick={() => {
                setSections((prev) => [
                  ...prev,
                  {
                    name: `Section ${prev.length + 1}`,
                    description: "",
                    duration_minutes: null,
                    marks_per_question: 2,
                    negative_marks: null,
                    rules: [{ question_type: "mcq", difficulty: "medium", count: 5 }],
                  },
                ]);
              }}
            >
              + Add Section
            </Button>
          </div>

          {sections.length === 0 ? (
            <Card className="text-center py-8">
              <p className="text-sm text-ink-muted mb-3">No sections defined yet.</p>
              <Button
                size="sm"
                onClick={() => {
                  setSections([
                    {
                      name: "General Section",
                      description: "Main exam questions",
                      duration_minutes: null,
                      marks_per_question: 2,
                      negative_marks: null,
                      rules: [{ question_type: "mcq", difficulty: "medium", count: 5 }],
                    },
                  ]);
                }}
              >
                Add Default Section
              </Button>
            </Card>
          ) : (
            <div className="space-y-4">
              {sections.map((sec, sIdx) => (
                <Card key={sIdx} className="space-y-4 border-line">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 items-center justify-center rounded bg-accent-soft text-accent text-xs font-bold">
                        {sIdx + 1}
                      </span>
                      <Input
                        value={sec.name}
                        onChange={(e) => {
                          const val = e.target.value;
                          setSections((prev) =>
                            prev.map((s, idx) => (idx === sIdx ? { ...s, name: val } : s))
                          );
                        }}
                        className="font-bold text-sm h-8"
                        placeholder="Section Name"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => setSections((prev) => prev.filter((_, idx) => idx !== sIdx))}
                      className="text-xs text-rose-500 hover:text-rose-700 font-semibold"
                    >
                      Remove Section
                    </button>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 text-xs">
                    <Field label="Section Description">
                      <Input
                        value={sec.description}
                        onChange={(e) => {
                          const val = e.target.value;
                          setSections((prev) =>
                            prev.map((s, idx) => (idx === sIdx ? { ...s, description: val } : s))
                          );
                        }}
                        placeholder="Optional description"
                      />
                    </Field>
                    <Field label="Section Duration (mins, null = shared)">
                      <Input
                        type="number"
                        value={sec.duration_minutes || ""}
                        onChange={(e) => {
                          const val = e.target.value === "" ? null : Number(e.target.value);
                          setSections((prev) =>
                            prev.map((s, idx) => (idx === sIdx ? { ...s, duration_minutes: val } : s))
                          );
                        }}
                        placeholder="Leave blank for shared exam timer"
                      />
                    </Field>
                  </div>

                  {/* Rules list */}
                  <div className="space-y-2 border-t border-line/60 pt-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-ink">Question Selection Rules</span>
                      <button
                        type="button"
                        onClick={() => {
                          setSections((prev) =>
                            prev.map((s, idx) =>
                              idx === sIdx
                                ? {
                                    ...s,
                                    rules: [
                                      ...s.rules,
                                      { question_type: "mcq", difficulty: "medium", count: 3 },
                                    ],
                                  }
                                : s
                            )
                          );
                        }}
                        className="text-xs text-accent hover:underline font-semibold"
                      >
                        + Add Rule
                      </button>
                    </div>

                    {sec.rules.map((rule, rIdx) => (
                      <div
                        key={rIdx}
                        className="flex flex-wrap items-center gap-2 rounded-lg bg-sunken/40 p-2 text-xs"
                      >
                        <span className="text-ink-muted">Draw</span>
                        <input
                          type="number"
                          min={1}
                          max={50}
                          value={rule.count}
                          onChange={(e) => {
                            const val = Math.max(1, Number(e.target.value));
                            setSections((prev) =>
                              prev.map((s, sI) =>
                                sI === sIdx
                                  ? {
                                      ...s,
                                      rules: s.rules.map((r, rI) =>
                                        rI === rIdx ? { ...r, count: val } : r
                                      ),
                                    }
                                  : s
                              )
                            );
                          }}
                          className="w-16 rounded border border-line bg-surface px-2 py-1 text-center font-bold"
                        />
                        <span className="text-ink-muted">questions of type</span>
                        <select
                          value={rule.question_type}
                          onChange={(e) => {
                            const val = e.target.value as QuestionType;
                            setSections((prev) =>
                              prev.map((s, sI) =>
                                sI === sIdx
                                  ? {
                                      ...s,
                                      rules: s.rules.map((r, rI) =>
                                        rI === rIdx ? { ...r, question_type: val } : r
                                      ),
                                    }
                                  : s
                              )
                            );
                          }}
                          className="rounded border border-line bg-surface px-2 py-1 text-xs"
                        >
                          {Object.entries(TYPE_LABEL).map(([t, label]) => (
                            <option key={t} value={t}>
                              {label}
                            </option>
                          ))}
                        </select>

                        <span className="text-ink-muted">difficulty</span>
                        <select
                          value={rule.difficulty || "any"}
                          onChange={(e) => {
                            const val = e.target.value === "any" ? null : (e.target.value as Difficulty);
                            setSections((prev) =>
                              prev.map((s, sI) =>
                                sI === sIdx
                                  ? {
                                      ...s,
                                      rules: s.rules.map((r, rI) =>
                                        rI === rIdx ? { ...r, difficulty: val } : r
                                      ),
                                    }
                                  : s
                              )
                            );
                          }}
                          className="rounded border border-line bg-surface px-2 py-1 text-xs"
                        >
                          <option value="any">Any difficulty</option>
                          <option value="easy">Easy</option>
                          <option value="medium">Medium</option>
                          <option value="hard">Hard</option>
                        </select>

                        {sec.rules.length > 1 && (
                          <button
                            type="button"
                            onClick={() => {
                              setSections((prev) =>
                                prev.map((s, sI) =>
                                  sI === sIdx
                                    ? { ...s, rules: s.rules.filter((_, rI) => rI !== rIdx) }
                                    : s
                                )
                              );
                            }}
                            className="ml-auto text-rose-500 hover:text-rose-700"
                          >
                            ✕
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          )}

          <div className="flex justify-between pt-4">
            <Button variant="secondary" onClick={() => setStep(3)}>
              ← Back to Details
            </Button>
            <Button loading={savingDraft} onClick={() => void goToPool()}>
              {examId ? "Next: Build Question Pool →" : "Save draft & build the pool →"}
            </Button>
          </div>
        </div>
      )}

      {/* STEP 5: QUESTION POOL SELECTION */}
      {/* STEP 5: BUILD QUESTION POOL — four sources, one pool */}
      {step === 5 && !published && (
        <div className="space-y-6 animate-fade-in">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-bold text-ink">Build Question Pool</h2>
              <p className="text-sm text-ink-muted mt-0.5">
                Write questions yourself, reuse the bank, generate a set with AI, or
                import a file. Use as many of the four as you like.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={pool?.can_publish ? "mint" : "amber"}>
                {pool?.stats.total_questions ?? 0} in the pool ·{" "}
                {pool?.required_count ?? totalQuestionsNeeded} per paper
              </Badge>
              <Button
                size="sm"
                variant="secondary"
                loading={savingDraft}
                onClick={() => void saveDraft()}
              >
                Save draft
              </Button>
            </div>
          </div>

          {!examId ? (
            <Alert tone="amber" title="Save the draft first">
              The pool belongs to an exam, so the exam has to exist before questions can
              join it. Go back a step and save the draft.
            </Alert>
          ) : (
            <>
              {/* the four sources */}
              <div className="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
                {(
                  [
                    { key: "create", label: "+ Create Question" },
                    { key: "bank", label: "Question Bank" },
                    { key: "ai", label: "AI Generate" },
                    { key: "import", label: "Import Questions" },
                  ] as { key: typeof poolTab; label: string }[]
                ).map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setPoolTab(tab.key)}
                    className={cx(
                      "flex-1 rounded-lg px-3 py-2 text-[13px] font-semibold transition-all",
                      poolTab === tab.key
                        ? "bg-accent text-white shadow-sm"
                        : "text-ink-muted hover:bg-sunken hover:text-ink"
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <Card>
                {poolTab === "create" && (
                  <QuestionEditor
                    subjects={subjects}
                    examId={examId}
                    lockedSubjectId={subjectId}
                    stayOpen
                    onSaved={() => void refreshPool(examId)}
                  />
                )}

                {poolTab === "bank" && (
                  <QuestionBankSelector
                    subjects={subjects}
                    subjectId={subjectId}
                    alreadyIn={(pool?.entries ?? []).map((e) => e.question_id)}
                    onAdd={addFromBank}
                    onEdit={setEditingQuestion}
                    onDuplicate={duplicateIntoExam}
                    currentUserId={user?.id}
                    isAdmin={user?.role === "admin"}
                  />
                )}

                {poolTab === "ai" && (
                  <AIGenerator
                    subjects={subjects}
                    examId={examId}
                    subjectId={subjectId}
                    onApproved={() => void refreshPool(examId)}
                  />
                )}

                {poolTab === "import" && (
                  <QuestionImporter
                    subjects={subjects}
                    examId={examId}
                    subjectId={subjectId}
                    onImported={() => void refreshPool(examId)}
                  />
                )}
              </Card>

              {/* the pool itself */}
              <div>
                <div className="mb-3 flex items-center gap-2">
                  <h3 className="text-lg font-bold text-ink">Exam Question Pool</h3>
                  <Badge tone="neutral">
                    {pool?.stats.total_questions ?? 0} / {pool?.required_count ?? 0} needed
                  </Badge>
                </div>
                <QuestionPool
                  pool={pool}
                  reorderable={!randomize}
                  onReorder={async (ids) => {
                    setPool(
                      await api.put<ExamPool>(`/exams/${examId}/questions/order`, {
                        question_ids: ids,
                      })
                    );
                  }}
                  onRemove={async (questionId) => {
                    setPool(
                      await api.delete<ExamPool>(
                        `/exams/${examId}/questions/${questionId}`
                      )
                    );
                  }}
                  onOverrideMarks={async (questionId, marks) => {
                    setPool(
                      await api.patch<ExamPool>(
                        `/exams/${examId}/questions/${questionId}/marks`,
                        { marks_override: marks }
                      )
                    );
                  }}
                  onEdit={async (questionId) => {
                    try {
                      setEditingQuestion(await api.get<Question>(`/questions/${questionId}`));
                      setPoolTab("bank");
                    } catch (err) {
                      toast(
                        err instanceof ApiError ? err.message : "Could not open that question.",
                        "rose"
                      );
                    }
                  }}
                />
              </div>
            </>
          )}

          <div className="flex justify-between pt-4 border-t border-line">
            <Button variant="secondary" onClick={() => setStep(4)}>
              ← Back to Sections
            </Button>
            <Button onClick={() => setStep(6)}>Next: Assign Candidates →</Button>
          </div>
        </div>
      )}

      {/* STEP 6: CANDIDATES */}
      {step === 6 && !published && (
        <div className="space-y-6 animate-fade-in">
          <div>
            <h2 className="text-xl font-bold text-ink">Assign Candidates</h2>
            <p className="text-sm text-ink-muted mt-0.5">
              Only assigned candidates ever see this exam. Assigning somebody whose login
              access is still pending is allowed — the exam waits for them.
            </p>
          </div>

          <CandidateSelector examId={examId} onChange={setAssignedCount} />

          <div className="flex justify-between pt-4 border-t border-line">
            <Button variant="secondary" onClick={() => setStep(5)}>
              ← Back to the Question Pool
            </Button>
            <Button onClick={() => setStep(7)}>Next: Review &amp; Publish →</Button>
          </div>
        </div>
      )}

      {/* STEP 7: RANDOMISATION, PROCTORING, VALIDATION, PUBLISH */}
      {step === 7 && !published && (
        <div className="space-y-6 animate-fade-in">
          {/* ------------------------------------------------------ randomisation */}
          <Card className="space-y-4">
            <div>
              <h2 className="text-lg font-bold text-ink">Randomisation</h2>
              <p className="text-xs text-ink-muted">
                The pool holds {pool?.stats.total_questions ?? 0} questions. Each
                candidate sits {pool?.required_count ?? totalQuestionsNeeded} of them,
                drawn by the section rules.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <Toggle
                checked={randomize}
                onChange={setRandomize}
                title="Unique paper per candidate"
                body="Each paper is drawn deterministically from the pool, so two candidates rarely see the same set."
              />
              <Toggle
                checked={shuffleOptions}
                onChange={setShuffleOptions}
                title="Shuffle options"
                body="Option order differs per candidate, so &quot;the answer is C&quot; is not shareable."
              />
            </div>

            {!randomize && (
              <Alert tone="amber">
                With randomisation off, every candidate sits the pool in the order you
                arranged it — so the pool must hold exactly what you want asked.
              </Alert>
            )}
          </Card>

          {/* --------------------------------------------------------- proctoring */}
          <Card className="space-y-4">
            <div>
              <h2 className="text-lg font-bold text-ink">Proctoring &amp; Integrity</h2>
              <p className="text-xs text-ink-muted">
                These settings decide what gets detected and flagged. They never decide
                whether a candidate cheated — you rule on the evidence afterwards.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <Toggle
                checked={proctorWebcam}
                onChange={setProctorWebcam}
                title="Webcam face verification"
                body="Continuous facial presence, plus multiple-face detection."
              />
              <Toggle
                checked={proctorGaze}
                onChange={setProctorGaze}
                title="Gaze tracking"
                body="Raises a signal on prolonged off-screen looking."
              />
              <Toggle
                checked={proctorFullscreen}
                onChange={setProctorFullscreen}
                title="Fullscreen enforcement"
                body="Tab switches and window blur are recorded with timestamps."
              />
              <Toggle
                checked={proctorBlockCopyPaste}
                onChange={setProctorBlockCopyPaste}
                title="Block copy / paste"
                body="Clipboard actions inside the runner are refused."
              />
              <Toggle
                checked={proctorMicrophone}
                onChange={setProctorMicrophone}
                title="Require a microphone"
                body="Checked during the pre-flight test, before the timer starts."
              />
              <Toggle
                checked={proctorSingleDisplay}
                onChange={setProctorSingleDisplay}
                title="Single display only"
                body="A second monitor is refused at pre-flight."
              />
            </div>

            <div className="grid gap-4 border-t border-line pt-4 sm:grid-cols-2 lg:grid-cols-3">
              <Field
                label="Tab switches before flagging"
                hint="Earlier switches warn the candidate; this many flags the sitting."
              >
                <Input
                  type="number"
                  min="0"
                  max="50"
                  value={maxTabSwitches}
                  onChange={(e) => setMaxTabSwitches(Number(e.target.value))}
                />
              </Field>
              <Field label="Gaze sensitivity" hint="0 is lenient, 1 is strict.">
                <Input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  value={gazeSensitivity}
                  onChange={(e) => setGazeSensitivity(Number(e.target.value))}
                />
              </Field>
              <Field label="Snapshot interval (seconds)">
                <Input
                  type="number"
                  min="10"
                  max="600"
                  step="10"
                  value={snapshotInterval}
                  onChange={(e) => setSnapshotInterval(Number(e.target.value))}
                />
              </Field>
              <Field
                label="Suspicion score that flags"
                hint="The sitting is marked for your review at this score."
              >
                <Input
                  type="number"
                  min="1"
                  value={flagOnScore}
                  onChange={(e) => setFlagOnScore(Number(e.target.value))}
                />
              </Field>
              <Field
                label="Suspicion score that ends the sitting"
                hint="Must be above the flag score. Ending a sitting is not a verdict."
              >
                <Input
                  type="number"
                  min={flagOnScore + 1}
                  value={terminateOnScore}
                  onChange={(e) => setTerminateOnScore(Number(e.target.value))}
                />
              </Field>
            </div>

            <Alert tone="accent">
              A flagged sitting is still marked. You review the evidence and rule it a
              genuine attempt or malpractice — and a genuine candidate&apos;s paper is
              evaluated and published like anyone else&apos;s.
            </Alert>
          </Card>

          {/* ------------------------------------------------- review & validation */}
          <div className="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
            {(
              [
                { key: "summary", label: "Summary & validation" },
                { key: "paper", label: "Preview the candidate's paper" },
              ] as { key: typeof reviewTab; label: string }[]
            ).map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setReviewTab(tab.key)}
                className={cx(
                  "flex-1 rounded-lg px-3 py-2 text-[13px] font-semibold transition-all",
                  reviewTab === tab.key
                    ? "bg-accent text-white shadow-sm"
                    : "text-ink-muted hover:bg-sunken hover:text-ink"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {reviewTab === "paper" && (
            <PaperPreview
              examId={examId}
              examTitle={title}
              durationMinutes={durationMinutes}
              instructions={instructions}
            />
          )}

          <Card
            className={cx(
              "space-y-4 border-accent/40 bg-accent-soft/5",
              reviewTab === "paper" && "hidden"
            )}
          >
            <h2 className="text-base font-bold text-ink">Review before publishing</h2>
            <dl className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
              <Summary label="Mode" value={category === "academic" ? "Academic" : "Corporate"} />
              <Summary label="Duration" value={`${durationMinutes} minutes`} />
              <Summary label="Declared marks" value={String(declaredTotalMarks || "Auto")} />
              <Summary
                label="Pass mark"
                value={passingPercentage ? `${passingPercentage}%` : "None declared"}
              />
              <Summary label="Sections" value={`${sections.length}`} />
              <Summary
                label="Pool"
                value={`${pool?.stats.total_questions ?? 0} questions · ${pool?.stats.total_marks ?? 0} marks`}
              />
              <Summary
                label="Per candidate"
                value={`${pool?.required_count ?? totalQuestionsNeeded} questions`}
              />
              <Summary label="Negative marking" value={negativeMarking ? "On" : "Off"} />
              <Summary label="Attempts allowed" value={String(maxAttempts)} />
              <Summary label="Randomised" value={randomize ? "Per candidate" : "Fixed order"} />
              <Summary
                label="Target"
                value={category === "academic" ? course || "Not set" : companyName || "Not set"}
              />
              <Summary
                label="Candidates"
                value={assignedCount ? `${assignedCount} assigned` : "None assigned"}
              />
              <Summary label="Status" value={examId ? "Draft saved" : "Not saved yet"} />
            </dl>

            <ValidationChecklist
              items={[
                { label: "Required details completed", ok: Boolean(title.trim() && subjectId) },
                {
                  label: "Exam window is valid and fits the duration",
                  ok: configurationProblems().every((problem) => !problem.includes("window")),
                },
                { label: "At least one section with rules", ok: sections.length > 0 },
                {
                  label: "Enough questions in the pool for every rule",
                  ok: Boolean(pool?.can_publish),
                  detail: pool?.problems.join(" "),
                },
                {
                  label: "Every pooled question has an answer key or model answer",
                  ok: (pool?.entries ?? []).every((entry) => entry.has_answer_key),
                  detail: (pool?.entries ?? []).some((entry) => !entry.has_answer_key)
                    ? "Some pooled questions have nothing to grade against."
                    : undefined,
                },
                {
                  label: "Proctoring thresholds are consistent",
                  ok: terminateOnScore > flagOnScore,
                  detail: "The score that ends a sitting must be above the one that flags it.",
                },
                {
                  // A warning, not a blocker: an exam can legitimately be published
                  // before its cohort is known, and candidates can be added later.
                  label: "Candidates assigned",
                  ok: assignedCount > 0,
                  detail:
                    "Nobody is assigned yet, so nobody will see this exam. You can assign them after publishing.",
                },
              ]}
            />
          </Card>

          <div className="flex flex-wrap justify-between gap-3 pt-4">
            <Button variant="secondary" onClick={() => setStep(6)}>
              ← Back to Candidates
            </Button>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" loading={savingDraft} onClick={() => void saveDraft()}>
                Save draft
              </Button>
              <Button
                onClick={() => void publishExam()}
                disabled={submitting || !pool?.can_publish}
                loading={submitting}
              >
                Publish exam
              </Button>
            </div>
          </div>

          {!pool?.can_publish && (
            <Alert tone="amber" title="Publishing is blocked">
              {pool?.problems.length
                ? pool.problems.join(" ")
                : "Build the question pool first — an exam with no questions cannot be sat."}
            </Alert>
          )}
        </div>
      )}

      {/* Editing a question, from the bank browser or the pool - same editor either way. */}
      {editingQuestion && (
        <Modal open onClose={() => setEditingQuestion(null)} title="Edit question" size="xl">
          <QuestionEditor
            subjects={subjects}
            question={editingQuestion}
            onCancel={() => setEditingQuestion(null)}
            onSaved={() => {
              setEditingQuestion(null);
              if (examId) void refreshPool(examId);
            }}
          />
        </Modal>
      )}

    </div>
  );
}


function Toggle({
  checked,
  onChange,
  title,
  body,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  title: string;
  body: string;
}) {
  return (
    <label
      className={cx(
        "flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition",
        checked ? "border-accent/50 bg-accent-soft/20" : "border-line hover:bg-sunken/40"
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-line text-accent focus:ring-accent"
      />
      <span>
        <span className="text-xs font-semibold text-ink">{title}</span>
        <span className="mt-0.5 block text-[11px] text-ink-muted">{body}</span>
      </span>
    </label>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase text-ink-muted">{label}</dt>
      <dd className="font-bold text-ink">{value}</dd>
    </div>
  );
}

/**
 * Every check, passing or not, with the failing ones explained.
 *
 * Showing the passes too is deliberate: six ticks and one cross tells the examiner what
 * the platform actually verified, where a bare error message leaves them guessing
 * whether anything else was checked at all.
 */
function ValidationChecklist({
  items,
}: {
  items: { label: string; ok: boolean; detail?: string }[];
}) {
  return (
    <ul className="space-y-1.5 border-t border-line pt-4">
      {items.map((item) => (
        <li key={item.label} className="flex items-start gap-2 text-xs">
          <span
            className={cx(
              "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold",
              item.ok ? "bg-mint-soft text-mint" : "bg-amber-soft text-amber-ink"
            )}
          >
            {item.ok ? "✓" : "!"}
          </span>
          <span>
            <span className={item.ok ? "text-ink-soft" : "font-semibold text-ink"}>
              {item.label}
            </span>
            {!item.ok && item.detail && (
              <span className="mt-0.5 block text-[11px] text-ink-muted">{item.detail}</span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}
