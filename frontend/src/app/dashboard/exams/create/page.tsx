"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ExamCategoryCard, ExamCategoryType } from "@/components/ExamCategoryCard";
import { Hero } from "@/components/Hero";
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
import { useRequireAuth } from "@/lib/auth";
import type {
  Difficulty,
  ExamType,
  Question,
  QuestionCategory,
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

  // Academic fields
  const [course, setCourse] = useState("");
  const [department, setDepartment] = useState("");
  const [semester, setSemester] = useState("");

  // Corporate fields
  const [companyName, setCompanyName] = useState("");
  const [jobRole, setJobRole] = useState("");

  // Step 4: Sections & Rules
  const [sections, setSections] = useState<
    Array<{
      name: string;
      description: string;
      duration_minutes: number | null;
      marks_per_question: number | null;
      rules: SelectionRule[];
    }>
  >([]);

  // Step 5: Question Pool selection
  const [allQuestions, setAllQuestions] = useState<Question[]>([]);
  const [selectedQuestionIds, setSelectedQuestionIds] = useState<string[]>([]);
  const [questionSearch, setQuestionSearch] = useState("");
  const [filterType, setFilterType] = useState<string>("all");

  // Step 6: Proctoring
  const [proctorWebcam, setProctorWebcam] = useState(true);
  const [proctorGaze, setProctorGaze] = useState(true);
  const [proctorFullscreen, setProctorFullscreen] = useState(true);
  const [proctorBlockCopyPaste, setProctorBlockCopyPaste] = useState(true);

  // Current wizard step: 1..6
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [loadingInitial, setLoadingInitial] = useState(true);

  // Default dates
  useEffect(() => {
    const now = new Date();
    const plus30 = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
    setStartsAt(now.toISOString().slice(0, 16));
    setEndsAt(plus30.toISOString().slice(0, 16));

    async function loadData() {
      try {
        const [subList, qList] = await Promise.all([
          api.get<Subject[]>("/subjects"),
          api.get<Question[]>("/questions"),
        ]);
        setSubjects(subList);
        if (subList.length > 0) setSubjectId(subList[0].id);
        setAllQuestions(qList);
      } catch (err) {
        toast("Failed to load subjects or questions", "rose");
      } finally {
        setLoadingInitial(false);
      }
    }
    void loadData();
  }, []);

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

    setSections(p.sections.map((s) => ({ ...s, marks_per_question: s.marks_per_question })));

    // Auto-select matching questions from question bank
    const requiredRules = p.sections.flatMap((s) => s.rules);
    const poolIds: string[] = [];
    allQuestions.forEach((q) => {
      const match = requiredRules.some(
        (r) =>
          r.question_type === q.question_type &&
          (!r.category || r.category === q.category) &&
          (!r.difficulty || r.difficulty === q.difficulty)
      );
      if (match && poolIds.length < 25) {
        poolIds.push(q.id);
      }
    });
    setSelectedQuestionIds(poolIds);
  }

  // Toggle single question in pool
  function toggleQuestion(id: string) {
    setSelectedQuestionIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  // Select all matching questions
  function selectAllMatching() {
    const matched = filteredQuestions.map((q) => q.id);
    setSelectedQuestionIds((prev) => Array.from(new Set([...prev, ...matched])));
  }

  const filteredQuestions = allQuestions.filter((q) => {
    if (subjectId && q.subject_id !== subjectId && category === "academic") {
      // allow flexible viewing
    }
    if (filterType !== "all" && q.question_type !== filterType) return false;
    if (questionSearch) {
      const s = questionSearch.toLowerCase();
      return (
        q.body.toLowerCase().includes(s) ||
        (q.topic && q.topic.toLowerCase().includes(s)) ||
        q.category.toLowerCase().includes(s)
      );
    }
    return true;
  });

  // Calculate total questions needed from all section rules
  const totalQuestionsNeeded = sections.reduce(
    (acc, sec) => acc + sec.rules.reduce((rAcc, r) => rAcc + r.count, 0),
    0
  );

  async function handleCreateExam() {
    if (!title.trim()) {
      toast("Please enter an exam title", "rose");
      setStep(3);
      return;
    }
    if (!subjectId) {
      toast("Please select a subject", "rose");
      setStep(3);
      return;
    }
    if (sections.length === 0) {
      toast("Please configure at least one section with selection rules", "rose");
      setStep(4);
      return;
    }

    setSubmitting(true);
    try {
      // Combine all rules for the main selection_rules payload
      const combinedRules: SelectionRule[] = [];
      sections.forEach((sec) => {
        sec.rules.forEach((r) => combinedRules.push(r));
      });

      // Prepare API payload matching ExamCreate
      const payload: Record<string, any> = {
        exam_type: category,
        subject_id: subjectId,
        title: title.trim(),
        description: description.trim() || null,
        instructions: instructions.trim() || null,
        duration_minutes: Number(durationMinutes),
        starts_at: new Date(startsAt).toISOString(),
        ends_at: new Date(endsAt).toISOString(),
        selection_rules: { rules: combinedRules.length > 0 ? combinedRules : [{ question_type: "mcq", difficulty: "medium", count: 5 }] },
        randomize: true,
        shuffle_options: true,
        negative_marking: negativeMarking,
        passing_percentage: passingPercentage ? Number(passingPercentage) : null,
        declared_total_marks: declaredTotalMarks ? Number(declaredTotalMarks) : null,
        question_ids: selectedQuestionIds,
        proctor_config: {
          webcam_enabled: proctorWebcam,
          gaze_tracking_enabled: proctorGaze,
          require_fullscreen: proctorFullscreen,
          block_copy_paste: proctorBlockCopyPaste,
          gaze_sensitivity: 0.6,
          max_tab_switches: 3,
          flag_on_score: 45.0,
          terminate_on_score: 100.0,
          snapshot_interval_seconds: 60,
        },
        grading_config: {
          auto_publish_results: category === "academic" && selectedPatternId === "acad-speedquiz",
        },
      };

      // Mode-specific fields
      if (category === "academic") {
        payload.course = course.trim() || null;
        payload.department = department.trim() || null;
        payload.semester = semester.trim() || null;
      } else {
        payload.company_name = companyName.trim() || null;
        payload.job_role = jobRole.trim() || null;
      }

      // Sections array
      payload.sections = sections.map((sec, idx) => ({
        name: sec.name,
        description: sec.description || null,
        order_index: idx,
        selection_rules: { rules: sec.rules },
        marks_per_question: sec.marks_per_question || null,
        duration_minutes: sec.duration_minutes || null,
      }));

      const created = await api.post<{ id: string; title: string }>("/exams", payload);
      toast(`Exam "${title}" created successfully!`, "mint");
      router.push(`/dashboard/exams`);
    } catch (err) {
      if (err instanceof ApiError) {
        toast(err.problems?.length ? `${err.message}: ${err.problems.join(", ")}` : err.message, "rose");
      } else {
        toast("Failed to create exam", "rose");
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

      {/* Stepper Wizard Bar */}
      <div className="flex items-center justify-between rounded-xl border border-line bg-surface p-2 shadow-sm">
        {[
          { num: 1, label: "Category" },
          { num: 2, label: "Pattern" },
          { num: 3, label: "Details" },
          { num: 4, label: "Sections" },
          { num: 5, label: "Question Pool" },
          { num: 6, label: "Review & Proctor" },
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
      {step === 1 && (
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

          <div className="flex justify-end pt-4">
            <Button
              onClick={() => {
                setStep(2);
                if (!selectedPatternId) {
                  applyPattern(patterns[0]);
                }
              }}
            >
              Next: Select Exam Pattern →
            </Button>
          </div>
        </div>
      )}

      {/* STEP 2: PATTERN / BLUEPRINT PRESETS */}
      {step === 2 && (
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
            <Button onClick={() => setStep(3)}>Next: Basic Details →</Button>
          </div>
        </div>
      )}

      {/* STEP 3: EXAM DETAILS */}
      {step === 3 && (
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
      {step === 4 && (
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
            <Button onClick={() => setStep(5)}>Next: Select Question Pool →</Button>
          </div>
        </div>
      )}

      {/* STEP 5: QUESTION POOL SELECTION */}
      {step === 5 && (
        <Card className="space-y-4 animate-fade-in">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-bold text-ink">Select Questions from Bank</h2>
              <p className="text-xs text-ink-muted">
                Bind questions to your exam pool. Your rules will draw dynamically from this selected pool.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={selectedQuestionIds.length >= totalQuestionsNeeded ? "mint" : "amber"}>
                {selectedQuestionIds.length} Selected (Needs at least {totalQuestionsNeeded})
              </Badge>
              <Button size="sm" variant="secondary" onClick={selectAllMatching}>
                Select All Filtered
              </Button>
            </div>
          </div>

          {/* Search & Filters */}
          <div className="flex flex-wrap gap-2 pt-2">
            <div className="flex-1 min-w-[200px]">
              <Input
                value={questionSearch}
                onChange={(e) => setQuestionSearch(e.target.value)}
                placeholder="Search questions by keyword, topic, or category..."
              />
            </div>
            <Select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="w-44"
            >
              <option value="all">All Question Types</option>
              {Object.entries(TYPE_LABEL).map(([t, label]) => (
                <option key={t} value={t}>
                  {label}
                </option>
              ))}
            </Select>
          </div>

          {/* Question List */}
          <div className="max-h-[400px] overflow-y-auto space-y-2 rounded-xl border border-line bg-sunken/20 p-2">
            {filteredQuestions.length === 0 ? (
              <p className="text-center text-xs text-ink-muted py-8">
                No questions found matching your filter criteria.
              </p>
            ) : (
              filteredQuestions.map((q) => {
                const isSelected = selectedQuestionIds.includes(q.id);
                return (
                  <div
                    key={q.id}
                    onClick={() => toggleQuestion(q.id)}
                    className={cx(
                      "flex items-start gap-3 rounded-lg border p-3 text-xs transition-all cursor-pointer",
                      isSelected
                        ? "border-accent bg-accent-soft/20 ring-1 ring-accent"
                        : "border-line bg-surface hover:border-line-strong"
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleQuestion(q.id)}
                      className="mt-0.5 h-4 w-4 rounded border-line text-accent focus:ring-accent"
                    />
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-1.5 mb-1">
                        <Badge tone="neutral">{TYPE_LABEL[q.question_type]}</Badge>
                        <Badge tone={q.difficulty === "hard" ? "rose" : q.difficulty === "medium" ? "amber" : "mint"}>
                          {q.difficulty}
                        </Badge>
                        <span className="text-[11px] font-semibold text-ink-muted">
                          {q.category} {q.topic ? `· ${q.topic}` : ""}
                        </span>
                        <span className="ml-auto font-bold text-ink">{q.marks} marks</span>
                      </div>
                      <p className="text-ink font-medium line-clamp-2">{q.body}</p>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="flex justify-between pt-4 border-t border-line">
            <Button variant="secondary" onClick={() => setStep(4)}>
              ← Back to Sections
            </Button>
            <Button onClick={() => setStep(6)}>Next: Review & Proctoring →</Button>
          </div>
        </Card>
      )}

      {/* STEP 6: REVIEW & PROCTORING */}
      {step === 6 && (
        <div className="space-y-6 animate-fade-in">
          <Card className="space-y-4">
            <div>
              <h2 className="text-lg font-bold text-ink">AI Proctoring & Integrity Controls</h2>
              <p className="text-xs text-ink-muted">
                Configure automated browser proctoring and real-time surveillance settings.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex items-start gap-3 rounded-xl border border-line p-3 cursor-pointer hover:bg-surface-elevated">
                <input
                  type="checkbox"
                  checked={proctorWebcam}
                  onChange={(e) => setProctorWebcam(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-line text-accent focus:ring-accent"
                />
                <div>
                  <span className="font-semibold text-xs text-ink">Webcam Face Verification</span>
                  <p className="text-[11px] text-ink-muted">
                    Continuous facial presence and multiple-face detection.
                  </p>
                </div>
              </label>

              <label className="flex items-start gap-3 rounded-xl border border-line p-3 cursor-pointer hover:bg-surface-elevated">
                <input
                  type="checkbox"
                  checked={proctorGaze}
                  onChange={(e) => setProctorGaze(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-line text-accent focus:ring-accent"
                />
                <div>
                  <span className="font-semibold text-xs text-ink">AI Gaze Tracking</span>
                  <p className="text-[11px] text-ink-muted">
                    Flags prolonged off-screen looking or abnormal eye movements.
                  </p>
                </div>
              </label>

              <label className="flex items-start gap-3 rounded-xl border border-line p-3 cursor-pointer hover:bg-surface-elevated">
                <input
                  type="checkbox"
                  checked={proctorFullscreen}
                  onChange={(e) => setProctorFullscreen(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-line text-accent focus:ring-accent"
                />
                <div>
                  <span className="font-semibold text-xs text-ink">Mandatory Fullscreen Mode</span>
                  <p className="text-[11px] text-ink-muted">
                    Locks candidate into fullscreen; flags window exit attempts.
                  </p>
                </div>
              </label>

              <label className="flex items-start gap-3 rounded-xl border border-line p-3 cursor-pointer hover:bg-surface-elevated">
                <input
                  type="checkbox"
                  checked={proctorBlockCopyPaste}
                  onChange={(e) => setProctorBlockCopyPaste(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-line text-accent focus:ring-accent"
                />
                <div>
                  <span className="font-semibold text-xs text-ink">Block Copy / Paste & DevTools</span>
                  <p className="text-[11px] text-ink-muted">
                    Prevents clipboard copying, pasting, and inspector shortcuts.
                  </p>
                </div>
              </label>
            </div>
          </Card>

          {/* Summary Card */}
          <Card className="space-y-4 border-accent/40 bg-accent-soft/5">
            <h2 className="text-base font-bold text-ink">Summary Review</h2>
            <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <dt className="text-ink-muted uppercase text-[10px]">Mode</dt>
                <dd className="font-bold text-ink">{category === "academic" ? "Academic" : "Corporate Hiring"}</dd>
              </div>
              <div>
                <dt className="text-ink-muted uppercase text-[10px]">Duration</dt>
                <dd className="font-bold text-ink">{durationMinutes} minutes</dd>
              </div>
              <div>
                <dt className="text-ink-muted uppercase text-[10px]">Total Marks</dt>
                <dd className="font-bold text-ink">{declaredTotalMarks || "Auto"}</dd>
              </div>
              <div>
                <dt className="text-ink-muted uppercase text-[10px]">Passing Threshold</dt>
                <dd className="font-bold text-ink">{passingPercentage ? `${passingPercentage}%` : "None"}</dd>
              </div>
              <div>
                <dt className="text-ink-muted uppercase text-[10px]">Sections</dt>
                <dd className="font-bold text-ink">{sections.length} Section(s)</dd>
              </div>
              <div>
                <dt className="text-ink-muted uppercase text-[10px]">Pool Bound</dt>
                <dd className="font-bold text-ink">{selectedQuestionIds.length} questions</dd>
              </div>
              <div>
                <dt className="text-ink-muted uppercase text-[10px]">Target</dt>
                <dd className="font-bold text-ink">
                  {category === "academic" ? course || "Academic Course" : companyName || "Corporate Target"}
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted uppercase text-[10px]">Negative Marking</dt>
                <dd className="font-bold text-ink">{negativeMarking ? "Enabled" : "Disabled"}</dd>
              </div>
            </dl>
          </Card>

          <div className="flex justify-between pt-4">
            <Button variant="secondary" onClick={() => setStep(5)}>
              ← Back to Question Pool
            </Button>
            <Button onClick={handleCreateExam} disabled={submitting}>
              {submitting ? "Creating Exam..." : "✓ Create & Save Exam"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
