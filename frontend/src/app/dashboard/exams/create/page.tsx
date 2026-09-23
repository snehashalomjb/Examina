"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AIGenerator } from "@/components/AIGenerator";
import { BlueprintBuilder } from "@/components/BlueprintBuilder";
import { CandidateSelector } from "@/components/CandidateSelector";
import { ExamCategoryCard, ExamCategoryType } from "@/components/ExamCategoryCard";
import { ExaminerPaperPreview } from "@/components/ExaminerPaperPreview";
import { GuidedSectionPicker } from "@/components/GuidedSectionPicker";
import { PaperPreview } from "@/components/PaperPreview";
import { QuestionBankSelector } from "@/components/QuestionBankSelector";
import { QuestionEditor } from "@/components/QuestionEditor";
import { QuestionImporter } from "@/components/QuestionImporter";
import { QuestionPool } from "@/components/QuestionPool";
import { SubjectCombobox } from "@/components/SubjectCombobox";
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
import { exampleFor } from "@/lib/exampleQuestions";
import { LOCALE_NAMES, SUPPORTED_LOCALES, type Locale } from "@/lib/locale";
import type {
  BlueprintRow,
  BlueprintRowResult,
  Difficulty,
  Exam,
  ExamPool,
  Question,
  QuestionCategory,
  QuestionType,
  SelectionRule,
  Subject,
} from "@/lib/types";
import { CATEGORY_LABEL, QUESTION_TYPE_LABEL as TYPE_LABEL } from "@/lib/types";

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
  const [enabledLanguages, setEnabledLanguages] = useState<Locale[]>(["en"]);

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
  // Off by default, and independent of `randomize` - see the toggle copy below.
  const [shuffleOptions, setShuffleOptions] = useState(false);

  // Step 4: Sections & Rules
  const [sections, setSections] = useState<
    Array<{
      /**
       * The saved section's server id, once the draft has been saved.
       *
       * Undefined until then, and that is the whole reason the per-section bank picker
       * needs a saved draft: a question is pinned to a section id, and a section that
       * exists only in this component's state has none.
       */
      id?: string;
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
  const [poolTab, setPoolTab] = useState<"create" | "bank" | "ai" | "import" | "blueprint">("bank");
  /** The guided, section-by-section picker is the default way to fill the pool - the
   * "Advanced" tabs stay available for AI generation, import, or free browsing. */
  const [guidedMode, setGuidedMode] = useState(true);
  const [guidedComplete, setGuidedComplete] = useState(false);
  const [guidedReloadToken, setGuidedReloadToken] = useState(0);
  const [shufflingPool, setShufflingPool] = useState(false);
  /**
   * Questions written on the pattern step, before there is a draft to attach them to.
   *
   * An examiner who already knows the questions should not have to walk three steps of
   * configuration before they can type one. There is no exam yet, so these are saved to
   * the question bank with their answer keys; they are remembered here and added to
   * this exam's pool the moment the draft exists, on the way into step 5.
   */
  const [earlyQuestions, setEarlyQuestions] = useState<Question[]>([]);
  const [authoringEarly, setAuthoringEarly] = useState(false);
  /**
   * Which section rule the examiner is writing a question for, on the sections step.
   *
   * A question is never owned by a section - sections draw from the pool by rule. So
   * "write one for this section" means "write one this rule will match": the editor
   * opens with the rule's type and difficulty already set, which is the only thing that
   * decides whether the rule can draw it.
   */
  const [ruleAuthor, setRuleAuthor] = useState<{ s: number; r: number } | null>(null);
  /** True when the open editor started from the worked example rather than blank. */
  const [ruleSeeded, setRuleSeeded] = useState(false);
  /** Which rule's worked example is expanded, as "sectionIndex:ruleIndex". */
  const [exampleOpen, setExampleOpen] = useState<string | null>(null);
  /** Which section has the Question Bank browser open beneath it. */
  const [bankForSection, setBankForSection] = useState<number | null>(null);
  const [pinning, setPinning] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<Question | null>(null);
  const [assignedCount, setAssignedCount] = useState(0);
  /** Review tab: the summary and checklist, the candidate's-eye paper, or the
   * examiner's full structured question-paper preview. */
  const [reviewTab, setReviewTab] = useState<"summary" | "paper" | "full">("summary");
  /** Set once the examiner has opened the full paper preview at least once - publishing
   * without having looked at the assembled paper is not allowed. */
  const [paperPreviewed, setPaperPreviewed] = useState(false);
  const [showPublishConfirm, setShowPublishConfirm] = useState(false);
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
  /** Times a candidate may leave the exam window before it submits itself. 0 = off. */
  const [maxFocusViolations, setMaxFocusViolations] = useState(3);

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
        setEnabledLanguages((exam.languages?.length ? exam.languages : ["en"]) as Locale[]);

        setSections(
          [...exam.sections]
            .sort((a, b) => a.order_index - b.order_index)
            .map((section) => ({
              id: section.id,
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
        setMaxFocusViolations(num("max_focus_violations", 3));

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
        max_focus_violations: maxFocusViolations,
      },
      grading_config: { auto_publish_results: false },
      enabled_languages: enabledLanguages,
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

  /** Every publish gate at once - the pool itself, no duplicates, every question in the
   * right section, and the examiner having actually looked at the assembled paper. */
  function canPublish(): boolean {
    if (!pool?.can_publish) return false;
    if (!paperPreviewed) return false;
    const seen = new Set<string>();
    for (const e of pool.entries) {
      if (seen.has(e.question_id)) return false;
      seen.add(e.question_id);
    }
    for (const e of pool.entries) {
      if (!e.section_id) continue;
      const sec = sections.find((s) => s.id === e.section_id);
      if (!sec) continue;
      const matches = sec.rules.some(
        (r) => r.question_type === e.question_type && (!r.difficulty || r.difficulty === e.difficulty),
      );
      if (!matches) return false;
    }
    return true;
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
          const updated = await api.patch<Exam>(`/exams/${examId}`, payload);
          absorbSectionIds(updated);
          if (!options?.quiet) toast("Draft saved", "mint");
          return examId;
        }
        const created = await api.post<Exam>("/exams", {
          ...payload,
          question_ids: [],
        });
        absorbSectionIds(created);
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

  /**
   * Shuffle the pool's saved order with one click, using the same reorder endpoint the
   * drag handles call. Only meaningful when "Unique paper per candidate" is off - once
   * randomize is on, every candidate gets their own draw and this order is never shown.
   */
  async function shufflePool() {
    if (!examId || !pool) return;
    const ids = pool.entries.map((e) => e.question_id);
    for (let i = ids.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [ids[i], ids[j]] = [ids[j], ids[i]];
    }
    setShufflingPool(true);
    try {
      setPool(await api.put<ExamPool>(`/exams/${examId}/questions/order`, { question_ids: ids }));
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not shuffle the pool.", "rose");
    } finally {
      setShufflingPool(false);
    }
  }

  /**
   * Learn the server's section ids after a save.
   *
   * The wizard edits sections as a positional list; the server returns them with ids.
   * Matching by ``order_index`` is safe because that is exactly how the two sides agree
   * on which section is which - see ``_set_sections``, which updates by position rather
   * than recreating, so an id survives every autosave.
   */
  function absorbSectionIds(exam: Exam) {
    const byOrder = new Map((exam.sections ?? []).map((s) => [s.order_index, s.id]));
    setSections((prev) => prev.map((sec, index) => ({ ...sec, id: byOrder.get(index) ?? sec.id })));
  }

  /**
   * The exam id and section id needed to pin a question, saving the draft if necessary.
   *
   * A section only has an id once it has been written to the server, so the first time
   * an examiner picks questions for Section A the draft is saved for them rather than
   * being refused. The saved exam is re-read instead of trusting component state,
   * because ``setSections`` has not landed yet at this point in the same tick.
   */
  async function sectionTarget(sIdx: number): Promise<{ exam: string; section: string } | null> {
    const id = examId ?? (await saveDraft({ quiet: true }));
    if (!id) return null;

    const known = sections[sIdx]?.id;
    if (examId && known) return { exam: id, section: known };

    try {
      const exam = await api.get<Exam>(`/exams/${id}`);
      absorbSectionIds(exam);
      const ordered = [...(exam.sections ?? [])].sort((a, b) => a.order_index - b.order_index);
      const section = ordered[sIdx]?.id;
      if (!section) {
        toast("Save the draft before picking questions for this section.", "amber");
        return null;
      }
      return { exam: id, section };
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not read the exam.", "rose");
      return null;
    }
  }

  /** Add bank questions straight into one section, not just into the shared pool. */
  async function addToSection(sIdx: number, questionIds: string[]) {
    const target = await sectionTarget(sIdx);
    if (!target) return;
    setPinning(true);
    try {
      setPool(
        await api.post<ExamPool>(`/exams/${target.exam}/questions`, {
          question_ids: questionIds,
          section_id: target.section,
        }),
      );
      toast(
        `${questionIds.length} question(s) added to ${sections[sIdx]?.name ?? "the section"}`,
        "mint",
      );
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not add those questions.", "rose");
    } finally {
      setPinning(false);
    }
  }

  /** Move a question already in the pool into one section. */
  async function pinToSection(sIdx: number, questionId: string) {
    const target = await sectionTarget(sIdx);
    if (!target) return;
    try {
      setPool(
        await api.patch<ExamPool>(`/exams/${target.exam}/questions/${questionId}/section`, {
          section_id: target.section,
        }),
      );
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not move that question.", "rose");
    }
  }

  /** Return a question to the shared pool. The question itself is untouched. */
  async function unpinFromSection(questionId: string) {
    if (!examId) return;
    try {
      setPool(
        await api.patch<ExamPool>(`/exams/${examId}/questions/${questionId}/section`, {
          section_id: null,
        }),
      );
      toast("Returned to the shared pool", "mint");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not move that question.", "rose");
    }
  }

  /** Drop a question from the pool entirely - used when deselecting a previously-picked
   * question in the guided flow, rather than just unpinning it back to "any section". */
  async function unpinAndRemove(questionId: string) {
    if (!examId) return;
    try {
      setPool(await api.delete<ExamPool>(`/exams/${examId}/questions/${questionId}`));
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not remove that question.", "rose");
    }
  }

  /** Save the draft, then move to the pool step with a live pool loaded. */
  async function goToPool() {
    const id = await saveDraft({ quiet: Boolean(examId) });
    if (!id) return;

    // Anything written on the pattern step has been waiting for an exam to belong to.
    // A pool may not mix subjects, so questions written against a different subject are
    // left in the bank and the examiner is told, rather than failing the whole batch.
    if (earlyQuestions.length) {
      const matching = earlyQuestions.filter((q) => q.subject_id === subjectId);
      const strays = earlyQuestions.length - matching.length;
      if (matching.length) {
        try {
          await api.post<ExamPool>(`/exams/${id}/questions`, {
            question_ids: matching.map((q) => q.id),
          });
          toast(`${matching.length} question(s) you wrote earlier added to the pool`, "mint");
        } catch (err) {
          toast(
            err instanceof ApiError ? err.message : "Could not add your earlier questions.",
            "rose",
          );
        }
      }
      if (strays) {
        toast(
          `${strays} question(s) are for another subject — they stayed in the bank.`,
          "amber",
        );
      }
      setEarlyQuestions([]);
    }

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

  /**
   * Apply the blueprint table: each row becomes a real section with a matching rule, and
   * the server has already pulled every matching bank question into the pool. The wizard
   * only owns `sections` in its own state until it is saved - the blueprint writes
   * sections directly on the server, so the client copy is re-read afterwards rather
   * than staying stale and then being overwritten on the next "Save draft".
   */
  async function applyBlueprint(rows: BlueprintRow[]): Promise<BlueprintRowResult[] | null> {
    if (!examId) return null;
    try {
      const result = await api.post<{ rows: BlueprintRowResult[]; pool: ExamPool }>(
        `/exams/${examId}/blueprint`,
        { rows },
      );
      setPool(result.pool);
      const exam = await api.get<Exam>(`/exams/${examId}`);
      setSections(
        [...exam.sections]
          .sort((a, b) => a.order_index - b.order_index)
          .map((section) => ({
            id: section.id,
            name: section.name,
            description: section.description ?? "",
            duration_minutes: section.duration_minutes,
            marks_per_question: section.marks_per_question,
            negative_marks: section.negative_marks,
            rules: section.selection_rules?.rules ?? [],
          })),
      );
      const shortfalls = result.rows.filter((r) => r.added < r.requested);
      toast(
        shortfalls.length
          ? `${result.rows.length - shortfalls.length}/${result.rows.length} rows fully filled - some rows need more bank questions`
          : `${result.rows.length} section(s) filled from the bank`,
        shortfalls.length ? "amber" : "mint",
      );
      return result.rows;
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not apply the blueprint.", "rose");
      return null;
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
      {/* Premium Header */}
      <div className="relative overflow-hidden rounded-[18px] px-6 py-5"
        style={{
          background: category === "academic"
            ? "linear-gradient(135deg, #f8f9ff 0%, #eef2ff 50%, #f5f3ff 100%)"
            : "linear-gradient(135deg, #faf5ff 0%, #f3e8ff 50%, #ede9fe 100%)",
          border: `1px solid ${category === "academic" ? "rgba(99,102,241,0.15)" : "rgba(139,92,246,0.2)"}`,
          boxShadow: "0 2px 16px -4px rgba(79,70,229,0.08), 0 1px 3px rgba(13,17,23,0.05)",
        }}>
        <div className="absolute -top-8 -right-8 h-40 w-40 rounded-full opacity-40"
          style={{ background: `radial-gradient(circle, ${category === "academic" ? "rgba(99,102,241,0.15)" : "rgba(139,92,246,0.2)"} 0%, transparent 70%)` }} />
        <div className="relative flex items-start justify-between gap-4">
          <div>
            <Link href="/dashboard/exams"
              className="inline-flex items-center gap-1 text-[12px] font-semibold text-ink-muted hover:text-accent transition-colors mb-2">
              ← Back to Exams
            </Link>
            <h1 className="text-[22px] font-bold tracking-tight"
              style={{ background: category === "academic" ? "linear-gradient(135deg, #1e1b4b, #4f46e5)" : "linear-gradient(135deg, #3b0764, #7c3aed)", WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              Create Examination
            </h1>
            <p className="mt-1 text-[13px] text-ink-muted">
              Configure examination mode, choose blueprint patterns, bind question pools, and set AI proctoring.
            </p>
          </div>
          <Badge tone={category === "academic" ? "accent" : "purple"} className="mt-1 shrink-0">
            {category === "academic" ? "🎓 Academic Mode" : "💼 Corporate Mode"}
          </Badge>
        </div>
      </div>

      {/* Published. The wizard stops being a form and becomes a receipt. */}
      {published && (
        <div className="overflow-hidden rounded-[18px] border border-green/20 shadow-[var(--shadow-lift)]"
          style={{ background: "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 50%, #f0fdf4 100%)" }}>
          {/* Green top bar */}
          <div className="h-[3px] bg-gradient-to-r from-green via-emerald-400 to-teal-400" />
          <div className="space-y-4 p-6">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[18px] text-white shadow-[0_4px_12px_-2px_rgba(22,163,74,0.4)]"
              style={{ background: "linear-gradient(135deg, #16a34a, #22c55e)" }}>
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
          </div>
        </div>
      )}

      {/* Premium Stepper Bar */}
      <div className="overflow-hidden rounded-[16px] border border-line bg-surface shadow-[var(--shadow-card)]">
        {/* Progress line */}
        <div className="h-1 bg-sunken">
          <div
            className="h-full bg-gradient-to-r from-accent to-indigo-400 transition-all duration-500"
            style={{ width: `${((step - 1) / 6) * 100}%` }}
          />
        </div>
        <div className="flex items-stretch divide-x divide-line">
          {[
            { num: 1, label: "Category", short: "Cat" },
            { num: 2, label: "Pattern", short: "Pat" },
            { num: 3, label: "Details", short: "Det" },
            { num: 4, label: "Sections", short: "Sec" },
            { num: 5, label: "Pool", short: "Pool" },
            { num: 6, label: "Candidates", short: "Cand" },
            { num: 7, label: "Review & Publish", short: "Pub" },
          ].map((s) => {
            const isDone = step > s.num;
            const isActive = step === s.num;
            return (
              <button
                key={s.num}
                type="button"
                onClick={() => setStep(s.num)}
                className={cx(
                  "flex flex-1 flex-col items-center gap-1 px-1 py-3 text-center transition-all duration-200",
                  isActive ? "bg-accent/5" : isDone ? "hover:bg-sunken" : "hover:bg-sunken"
                )}
              >
                <span
                  className={cx(
                    "flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold transition-all duration-200",
                    isActive
                      ? "bg-gradient-to-br from-accent to-indigo-500 text-white shadow-[0_2px_8px_-2px_rgba(79,70,229,0.5)]"
                      : isDone
                        ? "bg-green text-white"
                        : "bg-line text-ink-muted"
                  )}
                >
                  {isDone ? "✓" : s.num}
                </span>
                <span
                  className={cx(
                    "hidden text-[11px] font-semibold sm:block",
                    isActive ? "text-accent" : isDone ? "text-green" : "text-ink-muted"
                  )}
                >
                  {s.label}
                </span>
                <span className={cx("text-[10px] font-semibold sm:hidden", isActive ? "text-accent" : isDone ? "text-green" : "text-ink-muted")}>
                  {s.short}
                </span>
              </button>
            );
          })}
        </div>
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

          {/* ------------------------------------ write questions without waiting */}
          <Card className="space-y-4 border-line">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-ink">
                  Already know the questions? Write them now
                </h3>
                <p className="mt-0.5 text-xs text-ink-muted">
                  Type the question, its options, and tick the correct answer. Saved to
                  your Question Bank and added to this exam&apos;s pool at step 5.
                </p>
              </div>
              <Button
                size="sm"
                variant={authoringEarly ? "secondary" : "primary"}
                onClick={() => setAuthoringEarly((open) => !open)}
              >
                {authoringEarly ? "Close editor" : "+ Add a question"}
              </Button>
            </div>

            {earlyQuestions.length > 0 && (
              <ul className="space-y-2 rounded-lg border border-line bg-sunken/40 p-3">
                {earlyQuestions.map((q, idx) => {
                  const answer = answerKeySummary(q);
                  return (
                    <li key={q.id} className="flex items-start gap-2 text-xs">
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-accent-soft text-[10px] font-bold text-accent">
                        {idx + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-semibold text-ink">{q.body}</p>
                        <p className="mt-0.5 text-ink-muted">
                          {TYPE_LABEL[q.question_type]} · {q.marks} mark
                          {q.marks === 1 ? "" : "s"} · Answer:{" "}
                          <span className="font-semibold text-ink">{answer}</span>
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          setEarlyQuestions((prev) => prev.filter((p) => p.id !== q.id))
                        }
                        className="shrink-0 text-[11px] font-semibold text-rose-500 hover:text-rose-700"
                        title="Leave it in the bank, but do not put it in this exam"
                      >
                        Not in this exam
                      </button>
                    </li>
                  );
                })}
                <li className="pt-1 text-[11px] text-ink-muted">
                  Correct answers stay on the server. Nothing here is ever sent to a
                  candidate&apos;s browser.
                </li>
              </ul>
            )}

            {authoringEarly && (
              <QuestionEditor
                subjects={subjects}
                lockedSubjectId={subjectId || undefined}
                stayOpen
                onSaved={(q) => setEarlyQuestions((prev) => [...prev, q])}
                onCancel={() => setAuthoringEarly(false)}
              />
            )}
          </Card>

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
              <SubjectCombobox
                subjects={subjects}
                value={subjectId}
                onChange={setSubjectId}
                onCreated={(subject) => setSubjects((prev) => [...prev, subject])}
              />
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

                        <span className="text-ink-muted">category</span>
                        <select
                          value={rule.category ?? ""}
                          onChange={(e) => {
                            const val = (e.target.value || null) as QuestionCategory | null;
                            setSections((prev) =>
                              prev.map((s, sI) =>
                                sI === sIdx
                                  ? {
                                      ...s,
                                      rules: s.rules.map((r, rI) =>
                                        rI === rIdx ? { ...r, category: val } : r
                                      ),
                                    }
                                  : s
                              )
                            );
                          }}
                          className="rounded border border-line bg-surface px-2 py-1 text-xs"
                        >
                          <option value="">Any category</option>
                          {(Object.keys(CATEGORY_LABEL) as QuestionCategory[]).map((c) => (
                            <option key={c} value={c}>
                              {CATEGORY_LABEL[c]}
                            </option>
                          ))}
                        </select>

                        <span className="text-ink-muted">subject</span>
                        <select
                          value={rule.topic ?? ""}
                          onChange={(e) => {
                            const val = e.target.value || null;
                            setSections((prev) =>
                              prev.map((s, sI) =>
                                sI === sIdx
                                  ? {
                                      ...s,
                                      rules: s.rules.map((r, rI) =>
                                        rI === rIdx ? { ...r, topic: val } : r
                                      ),
                                    }
                                  : s
                              )
                            );
                          }}
                          className="max-w-[160px] rounded border border-line bg-surface px-2 py-1 text-xs"
                        >
                          <option value="">Any subject</option>
                          {subjects.map((sub) => (
                            <option key={sub.id} value={sub.name}>
                              {sub.name}
                            </option>
                          ))}
                        </select>

                        {/* Write a question this rule can actually draw. */}
                        <button
                          type="button"
                          onClick={() => {
                            setRuleSeeded(false);
                            setExampleOpen(null);
                            setRuleAuthor((cur) =>
                              cur && cur.s === sIdx && cur.r === rIdx ? null : { s: sIdx, r: rIdx },
                            );
                          }}
                          className="rounded border border-accent/40 bg-accent-soft/30 px-2 py-1 text-[11px] font-semibold text-accent hover:bg-accent-soft/60"
                        >
                          {ruleAuthor?.s === sIdx && ruleAuthor?.r === rIdx
                            ? "Close editor"
                            : "+ Write one"}
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            const key = `${sIdx}:${rIdx}`;
                            setExampleOpen((cur) => (cur === key ? null : key));
                          }}
                          className="rounded border border-line bg-surface px-2 py-1 text-[11px] font-semibold text-ink-muted hover:text-ink"
                        >
                          {exampleOpen === `${sIdx}:${rIdx}` ? "Hide example" : "See example"}
                        </button>

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

                    {/* ------ the worked example for the rule being looked at ------ */}
                    {exampleOpen?.startsWith(`${sIdx}:`) &&
                      (() => {
                        const rIdx = Number(exampleOpen.split(":")[1]);
                        const rule = sec.rules[rIdx];
                        if (!rule) return null;
                        return (
                          <ExampleCard
                            type={rule.question_type}
                            onUse={() => {
                              setRuleSeeded(true);
                              setRuleAuthor({ s: sIdx, r: rIdx });
                              setExampleOpen(null);
                            }}
                          />
                        );
                      })()}

                    {/* ------ authoring, pre-set to the rule that will draw it ------ */}
                    {ruleAuthor?.s === sIdx &&
                      (() => {
                        const rule = sec.rules[ruleAuthor.r];
                        if (!rule) return null;
                        return (
                          <div className="rounded-lg border border-accent/30 bg-accent-soft/10 p-3">
                            <p className="mb-3 text-[11.5px] text-ink-muted">
                              Writing for{" "}
                              <span className="font-semibold text-ink">{sec.name}</span> ·{" "}
                              rule {ruleAuthor.r + 1}. Type and difficulty are pre-set to{" "}
                              <span className="font-semibold text-ink">
                                {TYPE_LABEL[rule.question_type]}
                              </span>
                              {rule.difficulty ? ` / ${rule.difficulty}` : ""} so this rule
                              can draw it. Change either and the rule will skip it.
                              {ruleSeeded && " Started from the worked example — rewrite it."}
                            </p>
                            <QuestionEditor
                              key={`${sIdx}:${ruleAuthor.r}:${ruleSeeded}`}
                              subjects={subjects}
                              examId={examId ?? undefined}
                              lockedSubjectId={subjectId || undefined}
                              initialType={rule.question_type}
                              initialDifficulty={rule.difficulty ?? undefined}
                              seed={ruleSeeded ? exampleFor(rule.question_type) : null}
                              stayOpen
                              onSaved={(q) => {
                                // Written for this section, so it belongs to this
                                // section - not dropped into the shared pool for any
                                // rule to pick up.
                                if (examId && sections[sIdx]?.id) void pinToSection(sIdx, q.id);
                                else if (examId) void refreshPool(examId);
                                else setEarlyQuestions((prev) => [...prev, q]);
                              }}
                              onCancel={() => setRuleAuthor(null)}
                            />
                          </div>
                        );
                      })()}
                  </div>

                  {/* --------- questions chosen for THIS section, not the exam --------- */}
                  {(() => {
                    const mine = sections[sIdx]?.id
                      ? (pool?.entries ?? []).filter((e) => e.section_id === sections[sIdx].id)
                      : [];
                    const needed = sec.rules.reduce((sum, r) => sum + r.count, 0);

                    return (
                      <div className="space-y-3 border-t border-line/60 pt-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <span className="text-xs font-bold text-ink">
                              Questions chosen for this section
                            </span>
                            <p className="mt-0.5 text-[11px] text-ink-muted">
                              {mine.length} chosen of {needed} this section draws. The rest
                              are drawn at random from the shared pool.
                            </p>
                          </div>
                          <Button
                            size="sm"
                            variant={bankForSection === sIdx ? "secondary" : "primary"}
                            loading={pinning && bankForSection === sIdx}
                            onClick={() => {
                              setRuleAuthor(null);
                              setExampleOpen(null);
                              setBankForSection((cur) => (cur === sIdx ? null : sIdx));
                            }}
                          >
                            {bankForSection === sIdx ? "Close bank" : "Pick from Question Bank"}
                          </Button>
                        </div>

                        {mine.length > 0 && (
                          <ul className="space-y-1.5">
                            {mine.map((entry, i) => (
                              <li
                                key={entry.question_id}
                                className="flex items-start gap-2 rounded-lg border border-line bg-sunken/40 p-2 text-xs"
                              >
                                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-accent-soft text-[10px] font-bold text-accent">
                                  {i + 1}
                                </span>
                                <div className="min-w-0 flex-1">
                                  <p className="truncate font-medium text-ink">{entry.body}</p>
                                  <p className="mt-0.5 text-ink-muted">
                                    {TYPE_LABEL[entry.question_type]} · {entry.difficulty} ·{" "}
                                    {entry.effective_marks} mark
                                    {entry.effective_marks === 1 ? "" : "s"}
                                    {!entry.has_answer_key && (
                                      <span className="ml-1 font-semibold text-amber">
                                        · no answer key
                                      </span>
                                    )}
                                  </p>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => void unpinFromSection(entry.question_id)}
                                  className="shrink-0 text-[11px] font-semibold text-ink-muted hover:text-ink"
                                  title="Keep it in the exam, but let any section draw it"
                                >
                                  Unpin
                                </button>
                              </li>
                            ))}
                          </ul>
                        )}

                        {bankForSection === sIdx && (
                          <div className="rounded-lg border border-line bg-surface p-3">
                            <Alert tone="accent">
                              Anything you add here is chosen <strong>for {sec.name}</strong>:
                              this section draws it first, and no other section can. It still
                              has to match one of this section&apos;s rules — the Question Bank
                              is your reusable library, the pool is what this exam may draw
                              from.
                            </Alert>
                            <div className="mt-3">
                              <QuestionBankSelector
                                subjects={subjects}
                                subjectId={subjectId || undefined}
                                alreadyIn={(pool?.entries ?? []).map((e) => e.question_id)}
                                onAdd={(ids) => addToSection(sIdx, ids)}
                                currentUserId={user?.id}
                                isAdmin={user?.role === "admin"}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}
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
              {/* guided vs advanced */}
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-[10px] border border-line bg-sunken/40 px-3 py-2">
                <p className="text-[12.5px] text-ink-muted">
                  {guidedMode
                    ? "Guided: one section at a time, filtered to exactly its subject, type and difficulty."
                    : "Advanced: write, browse, AI-generate or import freely into the shared pool."}
                </p>
                <Button size="sm" variant="secondary" onClick={() => setGuidedMode((v) => !v)}>
                  {guidedMode ? "Switch to Advanced editor" : "Switch to Guided Selection"}
                </Button>
              </div>

              {guidedMode && (
                <GuidedSectionPicker
                  sections={sections}
                  subjects={subjects}
                  examSubjectId={subjectId}
                  pool={pool}
                  onAdd={addToSection}
                  onRemove={unpinAndRemove}
                  onWriteOne={(sIdx, rIdx) => setRuleAuthor({ s: sIdx, r: rIdx })}
                  onAllComplete={setGuidedComplete}
                  reloadToken={guidedReloadToken}
                />
              )}

              {ruleAuthor && guidedMode && (
                <Modal open onClose={() => setRuleAuthor(null)} title="Write a matching question" size="lg">
                  {(() => {
                    const rule = sections[ruleAuthor.s]?.rules[ruleAuthor.r];
                    if (!rule) return null;
                    return (
                      <div className="space-y-3">
                        <p className="text-[12px] text-ink-muted">
                          Type and difficulty are pre-set to{" "}
                          <span className="font-semibold text-ink">{TYPE_LABEL[rule.question_type]}</span>
                          {rule.difficulty ? ` / ${rule.difficulty}` : ""} so this section can use it.
                        </p>
                        <QuestionEditor
                          subjects={subjects}
                          examId={examId ?? undefined}
                          lockedSubjectId={subjectId || undefined}
                          initialType={rule.question_type}
                          initialDifficulty={rule.difficulty ?? undefined}
                          stayOpen
                          onSaved={async (q) => {
                            if (examId && sections[ruleAuthor.s]?.id) await pinToSection(ruleAuthor.s, q.id);
                            else if (examId) await refreshPool(examId);
                            setGuidedReloadToken((t) => t + 1);
                            setRuleAuthor(null);
                          }}
                          onCancel={() => setRuleAuthor(null)}
                        />
                      </div>
                    );
                  })()}
                </Modal>
              )}

              {!guidedMode && (
              <>
              {/* the four sources */}
              <div className="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
                {(
                  [
                    { key: "create", label: "+ Create Question" },
                    { key: "bank", label: "Question Bank" },
                    { key: "ai", label: "AI Generate" },
                    { key: "import", label: "Import Questions" },
                    { key: "blueprint", label: "Blueprint" },
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

                {poolTab === "blueprint" && (
                  <BlueprintBuilder subjects={subjects} onApply={applyBlueprint} />
                )}
              </Card>
              </>
              )}

              {/* the pool itself */}
              <div>
                <div className="mb-3 flex items-center gap-2">
                  <h3 className="text-lg font-bold text-ink">Exam Question Pool</h3>
                  <Badge tone="neutral">
                    {pool?.stats.total_questions ?? 0} / {pool?.required_count ?? 0} needed
                  </Badge>
                  {!randomize && (pool?.entries.length ?? 0) > 1 && (
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={shufflingPool}
                      onClick={() => void shufflePool()}
                    >
                      🔀 Shuffle order
                    </Button>
                  )}
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

          {guidedMode && !guidedComplete && (
            <Alert tone="amber">
              Every section still needs its exact question count selected before you can
              continue.
            </Alert>
          )}

          <div className="flex justify-between pt-4 border-t border-line">
            <Button variant="secondary" onClick={() => setStep(4)}>
              ← Back to Sections
            </Button>
            <Button
              onClick={() => setStep(6)}
              disabled={guidedMode ? !guidedComplete : !pool?.can_publish}
            >
              Next: Assign Candidates →
            </Button>
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
                title="Randomize question order"
                body="Every candidate gets the same questions in a different order — the count never changes, and a question never leaves its section."
              />
              <Toggle
                checked={shuffleOptions}
                onChange={setShuffleOptions}
                title="Randomize answer options"
                body="A separate setting. Shuffles A/B/C/D within each choice question, so &quot;the answer is C&quot; is not shareable. Off by default."
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
                label="Times a candidate may leave the exam"
                hint="Tab switch, minimise, or leaving fullscreen. On the last one their answers are submitted and the exam closes. 0 turns this off."
              >
                <Input
                  type="number"
                  min="0"
                  max="20"
                  value={maxFocusViolations}
                  onChange={(e) => setMaxFocusViolations(Number(e.target.value))}
                />
              </Field>
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
              {maxFocusViolations > 0 ? (
                <>
                  Leaving the exam escalates: warning, final warning, then the answers are
                  submitted and the exam closes at{" "}
                  <span className="font-semibold">{maxFocusViolations}</span>. That is a
                  submitted paper, not a void one — it is marked and published through the
                  normal workflow. You review the evidence afterwards and rule the sitting
                  a genuine attempt or malpractice.
                </>
              ) : (
                <>
                  Leaving the exam is recorded but will not close it. Flagged sittings are
                  still marked — you review the evidence and rule each one a genuine
                  attempt or malpractice.
                </>
              )}
            </Alert>
          </Card>

          {/* ------------------------------------------------- review & validation */}
          <div className="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
            {(
              [
                { key: "summary", label: "Summary & validation" },
                { key: "full", label: "📋 Question Paper Preview" },
                { key: "paper", label: "Preview the candidate's paper" },
              ] as { key: typeof reviewTab; label: string }[]
            ).map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => {
                  setReviewTab(tab.key);
                  if (tab.key === "full") setPaperPreviewed(true);
                }}
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

          {reviewTab === "full" && (
            <ExaminerPaperPreview
              examId={examId}
              examTitle={title}
              category={category}
              subjectName={subjects.find((s) => s.id === subjectId)?.name ?? null}
              department={department || null}
              semester={semester || null}
              companyName={companyName || null}
              jobRole={jobRole || null}
              durationMinutes={durationMinutes}
              instructions={instructions}
              sections={sections}
              pool={pool}
            />
          )}

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
              reviewTab !== "summary" && "hidden"
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
                label="Leaving the exam"
                value={
                  maxFocusViolations > 0
                    ? `Auto-submits at ${maxFocusViolations}`
                    : "Recorded only"
                }
              />
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

            {(() => {
              const seen = new Set<string>();
              const duplicateIds = new Set<string>();
              for (const e of pool?.entries ?? []) {
                if (seen.has(e.question_id)) duplicateIds.add(e.question_id);
                seen.add(e.question_id);
              }
              const sectionMismatch = (pool?.entries ?? []).some((e) => {
                if (!e.section_id) return false;
                const sec = sections.find((s) => s.id === e.section_id);
                if (!sec) return false;
                return !sec.rules.some(
                  (r) => r.question_type === e.question_type && (!r.difficulty || r.difficulty === e.difficulty),
                );
              });
              const readyToPublish = canPublish();

              return (
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
                      label: "No duplicate questions in the pool",
                      ok: duplicateIds.size === 0,
                      detail: duplicateIds.size ? `${duplicateIds.size} question(s) appear more than once.` : undefined,
                    },
                    {
                      label: "Every selected question matches its section's subject, type and difficulty",
                      ok: !sectionMismatch,
                    },
                    {
                      label: "Question Paper Preview reviewed",
                      ok: paperPreviewed,
                      detail: paperPreviewed
                        ? undefined
                        : 'Open the "Question Paper Preview" tab above before publishing.',
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
              );
            })()}
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
                onClick={() => setShowPublishConfirm(true)}
                disabled={submitting || !canPublish()}
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
          {pool?.can_publish && !paperPreviewed && (
            <Alert tone="amber" title="Review the paper first">
              Open the &quot;Question Paper Preview&quot; tab above and check the exam
              exactly as it will appear to candidates before publishing.
            </Alert>
          )}

          {showPublishConfirm && (
            <Modal open onClose={() => setShowPublishConfirm(false)} title="Publish this exam?">
              <div className="space-y-4">
                <dl className="grid grid-cols-2 gap-3 text-[13px]">
                  <Summary label="Exam name" value={title || "Untitled"} />
                  <Summary label="Total questions" value={String(pool?.stats.total_questions ?? 0)} />
                  <Summary label="Total marks" value={String(pool?.stats.total_marks ?? 0)} />
                  <Summary label="Duration" value={`${durationMinutes} minutes`} />
                  <Summary label="Sections" value={String(sections.length)} />
                  <Summary label="Candidates assigned" value={String(assignedCount)} />
                </dl>
                <Alert tone="accent">
                  Once published and a candidate has started, the question assignment can
                  no longer change.
                </Alert>
                <div className="flex justify-end gap-2">
                  <Button variant="secondary" onClick={() => setShowPublishConfirm(false)}>
                    Cancel
                  </Button>
                  <Button
                    loading={submitting}
                    onClick={async () => {
                      setShowPublishConfirm(false);
                      await publishExam();
                    }}
                  >
                    Publish Exam
                  </Button>
                </div>
              </div>
            </Modal>
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

/**
 * A worked example of one question type, shown beside the rule that would draw it.
 *
 * Read-only on purpose. "Use this as a starting point" seeds a new question the examiner
 * then rewrites — it never saves the example itself, because an exam full of the sample
 * questions is worse than an empty one.
 */
function ExampleCard({ type, onUse }: { type: QuestionType; onUse: () => void }) {
  const ex = exampleFor(type);
  const key = answerKeySummary({ ...ex, options: ex.options ?? [] } as Question);

  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <Badge tone="neutral">Example · {TYPE_LABEL[type]}</Badge>
        <Button size="sm" variant="secondary" onClick={onUse}>
          Use this as a starting point
        </Button>
      </div>

      <p className="text-[11.5px] italic text-ink-muted">{ex.note}</p>

      <p className="mt-2 whitespace-pre-wrap text-[13px] font-medium text-ink">{ex.body}</p>

      {ex.options && ex.options.length > 0 && (
        <ul className="mt-2 space-y-1">
          {ex.options.map((o, i) => (
            <li
              key={i}
              className={cx(
                "flex items-center gap-2 rounded px-2 py-1 text-xs",
                o.is_correct ? "bg-mint/10 font-semibold text-ink" : "text-ink-soft",
              )}
            >
              <span className="text-ink-muted">{String.fromCharCode(65 + i)}.</span>
              <span>{o.text}</span>
              {o.is_correct && <span className="ml-auto text-[10px] text-mint">correct</span>}
            </li>
          ))}
        </ul>
      )}

      <p className="mt-2 text-[11.5px] text-ink-muted">
        Answer key: <span className="font-semibold text-ink">{key}</span> · {ex.marks ?? 0} mark
        {ex.marks === 1 ? "" : "s"}
        <span className="ml-1">— examiner only, never sent to a candidate.</span>
      </p>
    </div>
  );
}

/**
 * One line describing where a question's marks come from.
 *
 * Examiner-side only, and deliberately so: this reads the answer key the examiner just
 * typed back to them for confirmation. The candidate's paper API strips all of it.
 */
function answerKeySummary(q: Question): string {
  const ticked = q.options.filter((o) => o.is_correct).map((o) => o.text);
  if (ticked.length) return ticked.join(", ");

  const spec = q.spec;
  if (q.question_type === "numerical" && spec && "answer" in spec) {
    return spec.unit ? `${spec.answer} ${spec.unit}` : String(spec.answer);
  }
  if (q.question_type === "fill_blank" && spec && "accepted_answers" in spec) {
    return spec.accepted_answers.join(" / ");
  }
  if (q.model_answer) return "Model answer set";
  return "Marked by an examiner";
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
