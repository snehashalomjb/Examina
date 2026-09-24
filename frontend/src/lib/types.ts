export type UserRole = "admin" | "examiner" | "candidate";
export type AccessStatus = "pending" | "approved" | "revoked";

/** Permission to *use* the platform. Separate from whether the account exists. */
export type LoginAccessStatus = "pending" | "approved" | "rejected";

export type QuestionType =
  | "mcq"
  | "multi_select"
  | "short_answer"
  | "long_answer"
  | "image_upload"
  | "true_false"
  | "fill_blank"
  | "numerical"
  | "passage"
  | "coding";

/**
 * One label per question type, used by the bank, the exam builder and the runner.
 * Kept beside the union so adding a type is a type error until it is named here.
 */
export const QUESTION_TYPE_LABEL: Record<QuestionType, string> = {
  mcq: "Single choice",
  multi_select: "Multiple choice",
  true_false: "True / False",
  fill_blank: "Fill in the blank",
  numerical: "Numerical",
  short_answer: "Short answer",
  long_answer: "Long answer",
  image_upload: "Handwritten upload",
  passage: "Passage",
  coding: "Coding",
};

export const CATEGORY_LABEL: Record<QuestionCategory, string> = {
  academic: "Academic",
  aptitude: "Quantitative Aptitude",
  verbal_ability: "Verbal Ability",
  logical_reasoning: "Logical Reasoning",
  technical: "Technical",
  coding: "Coding",
};

/** Scored from selected option ids - mcq, multi_select and true_false share a path. */
export const OPTION_BEARING_TYPES: QuestionType[] = ["mcq", "multi_select", "true_false"];
/** Scored by comparing typed text against the question's spec. */
export const RESPONSE_TYPES: QuestionType[] = ["fill_blank", "numerical"];
/** Needs a grader or a human. */
export const SUBJECTIVE_TYPES: QuestionType[] = [
  "short_answer",
  "long_answer",
  "image_upload",
  "coding",
];
/** Carries no answer and no marks - it holds the text its children are asked about. */
export const CONTAINER_TYPES: QuestionType[] = ["passage"];

/** The bank's top-level shelf, orthogonal to subject. Corporate sections select on it. */
export type QuestionCategory =
  | "academic"
  | "aptitude"
  | "verbal_ability"
  | "logical_reasoning"
  | "technical"
  | "coding";

export type QuestionStatus = "draft" | "published" | "archived";

/** How a question came to exist. Provenance, not permission. */
export type QuestionSource = "manual" | "ai_generated" | "imported";

export const QUESTION_SOURCE_LABEL: Record<QuestionSource, string> = {
  manual: "Written by hand",
  ai_generated: "AI generated",
  imported: "Imported",
};

export type ExamType = "academic" | "corporate";

export type ShortlistStatus = "shortlisted" | "rejected" | "on_hold";

export type DraftStatus = "pending" | "approved" | "rejected";

export type CodingLanguage = "python" | "java" | "cpp" | "javascript";

/** Type-specific configuration. Mirrors app/services/question_spec.py. */
export interface NumericalSpec {
  kind?: "numerical";
  answer: number;
  tolerance?: number;
  relative_tolerance?: number | null;
  unit?: string | null;
}

export interface FillBlankSpec {
  kind?: "fill_blank";
  accepted_answers: string[];
  case_sensitive?: boolean;
  normalise_whitespace?: boolean;
  allow_substring?: boolean;
}

export interface CodingSampleCase {
  input: string;
  output: string;
  explanation?: string | null;
}

export interface CodingSpec {
  kind?: "coding";
  languages: CodingLanguage[];
  default_language?: CodingLanguage | null;
  input_format: string;
  output_format: string;
  constraints: string;
  sample_cases: CodingSampleCase[];
  starter_code?: Record<string, string>;
  time_limit_seconds?: number | null;
}

export interface PassageSpec {
  kind?: "passage";
  passage_text?: string | null;
  source?: string | null;
  sticky?: boolean;
}

export interface TrueFalseSpec {
  kind?: "true_false";
  true_label?: string;
  false_label?: string;
}

export type QuestionSpec =
  | NumericalSpec
  | FillBlankSpec
  | CodingSpec
  | PassageSpec
  | TrueFalseSpec;

export type Difficulty = "easy" | "medium" | "hard";
export type ExamStatus = "draft" | "published" | "closed";
export type SessionStatus = "in_progress" | "submitted" | "auto_submitted" | "terminated";
export type GradeStatus =
  | "unanswered"
  | "auto_scored"
  | "pending_ai"
  | "ai_scored"
  | "examiner_reviewed";

export type ProctorEventType =
  | "face_missing"
  | "multiple_faces"
  | "phone_detected"
  | "gaze_away"
  | "tab_switch"
  | "window_blur"
  | "fullscreen_exit"
  | "camera_blocked"
  | "paste_attempt"
  | "copy_attempt"
  | "devtools_open"
  | "right_click"
  | "cut_attempt"
  | "text_selection"
  | "additional_person"
  | "mic_disconnected"
  | "network_lost"
  | "headphones_manual";

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: UserRole;
  access_status: AccessStatus;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  access_note: string | null;
  avatar_url: string | null;
  preferred_locale: string;
}

export interface AdminUser extends User {
  exam_count: number;
  session_count: number;
  access_changed_at: string | null;
  access_changed_by_email: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  /** Candidates only; null for examiners and admins, who are not login-gated. */
  login_access: LoginAccessStatus | null;
}

export interface LoginAccess {
  status: LoginAccessStatus;
  requested_at: string;
  reviewed_at: string | null;
  review_note: string | null;
}

export interface LoginRequestRow {
  id: string;
  candidate_id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  status: LoginAccessStatus;
  requested_at: string;
  reviewed_at: string | null;
  reviewed_by_name: string | null;
  review_note: string | null;
  enrolled_exams: string[];
}

export interface EnrollmentRow {
  candidate_id: string;
  full_name: string;
  email: string;
  assigned_at: string;
  assigned_by_name: string | null;
  login_access: LoginAccessStatus | null;
  has_attempted: boolean;
}

export interface Subject {
  id: string;
  code: string;
  name: string;
  description: string | null;
  question_count: number;
}

export interface Option {
  id: string;
  text: string;
  image_key?: string | null;
  image_url?: string | null;
  order_index: number;
  is_correct?: boolean;
  /** Per-locale text already on file, keyed by locale ("en" included). Examiner view only. */
  translations?: Record<string, string>;
}

export interface Question {
  id: string;
  subject_id: string;
  question_type: QuestionType;
  category: QuestionCategory;
  topic: string | null;
  difficulty: Difficulty;
  status: QuestionStatus;
  body: string;
  marks: number;
  negative_marks: number;
  /** Written-answer length bounds. short_answer / long_answer only. */
  min_words: number | null;
  max_words: number | null;
  tags: string[] | null;
  is_active: boolean;
  source: QuestionSource;
  created_by_id?: string | null;
  created_by_name?: string | null;
  subject_code?: string | null;
  /** True when the question is private to one exam rather than shelved in the bank. */
  exam_only?: boolean;
  image_key?: string | null;
  image_url?: string | null;
  /** Set on a child question to attach it to its passage. */
  parent_question_id?: string | null;
  created_at: string;
  updated_at?: string | null;
  model_answer?: string | null;
  explanation?: string | null;
  rubric?: Record<string, unknown> | null;
  /** Examiner view only - for numerical and fill_blank this IS the answer key. */
  spec?: QuestionSpec | null;
  options: Option[];
  /** Per-locale {body, model_answer, explanation} already on file, keyed by locale
   * ("en" included). Examiner view only. */
  translations?: Record<string, { body?: string; model_answer?: string; explanation?: string }>;
}

/** A preview of what "Generate Translations" would produce - never auto-saved. */
export interface GeneratedTranslations {
  translations: Record<string, { body?: string; explanation?: string }>;
  options: Record<string, Record<string, string>>;
  provider: "stub" | "openai" | string;
  skipped_existing: string[];
}

// ------------------------------------------------------------- paper preview
//
// What one candidate would sit. Note the absent field: options carry no is_correct,
// because this comes from the candidate-shaped projection and always has.

export interface PreviewOption {
  id: string;
  text: string;
}

export interface PaperPreviewEntry {
  question_id: string;
  body: string;
  question_type: QuestionType;
  difficulty: Difficulty;
  marks: number;
  negative_marks: number;
  topic: string | null;
  option_order: string[];
  options: PreviewOption[];
}

export interface PaperPreviewResult {
  seed: string;
  candidate_id: string;
  total_marks: number;
  entries: PaperPreviewEntry[];
}

// ------------------------------------------------------- the exam question pool
//
// "Pool" and "paper" stay different words on purpose. The pool is everything an exam
// may draw from; the paper is the subset one candidate sits.

export interface PoolEntry {
  question_id: string;
  order_index: number;
  subject_id: string;
  subject_name: string;
  /** The section this question was chosen for, or null if any section may draw it. */
  section_id: string | null;
  /** Per-exam marks override. Null means "use the question's own marks". */
  marks_override: number | null;
  effective_marks: number;
  body: string;
  question_type: QuestionType;
  difficulty: Difficulty;
  category: QuestionCategory;
  topic: string | null;
  source: QuestionSource;
  exam_only: boolean;
  created_by_name: string | null;
  option_count: number;
  has_answer_key: boolean;
}

export interface PoolStats {
  total_questions: number;
  total_marks: number;
  by_type: Record<string, number>;
  by_difficulty: Record<string, number>;
  /** Keyed by subject name — "Java: 5, Python: 5" — meaningful once a corporate pool
   * mixes subjects; present but a single entry for a single-subject pool. */
  by_subject: Record<string, number>;
}

export interface ExamPool {
  exam_id: string;
  entries: PoolEntry[];
  stats: PoolStats;
  /** How many questions the selection rules put on one candidate's paper. */
  required_count: number;
  can_publish: boolean;
  problems: string[];
}

/** What the image upload endpoint returns. */
export interface QuestionImage {
  image_key: string;
  image_url: string | null;
  thumbnail_url: string | null;
}

export interface SelectionRule {
  question_type: QuestionType;
  difficulty: Difficulty | null;
  count: number;
  category?: QuestionCategory | null;
  topic?: string | null;
  /** Narrow to one subject — "Python MCQ 10" alongside "SQL MCQ 10" in one paper. */
  subject_id?: string | null;
  /** Match-any tag narrowing. */
  tags?: string[] | null;
}

// -------------------------------------------------------- duplicate detection

export interface DuplicateMatch {
  id: string;
  body: string;
}

export interface DuplicateCheckResult {
  matches: DuplicateMatch[];
}

// ------------------------------------------------------------- exam blueprint
//
// One row of "Python | MCQ | Medium | 10". The server turns each into a section with a
// matching selection rule and pulls every matching bank question into the pool.

export interface BlueprintRow {
  title: string;
  subject_id?: string | null;
  category?: QuestionCategory | null;
  question_type: QuestionType;
  difficulty?: Difficulty | null;
  topic?: string | null;
  tags?: string[] | null;
  count: number;
}

export interface BlueprintRowResult {
  title: string;
  requested: number;
  matched: number;
  added: number;
  section_id: string;
}

export interface BlueprintResult {
  rows: BlueprintRowResult[];
  pool: ExamPool;
}

// ---------------------------------------------------------------- sections

export interface ExamSection {
  id: string;
  exam_id: string;
  name: string;
  description: string | null;
  order_index: number;
  selection_rules: { rules: SelectionRule[] };
  marks_per_question: number | null;
  negative_marks: number | null;
  duration_minutes: number | null;
  created_at: string;
}

// ---------------------------------------------------------------- exams

export interface Exam {
  id: string;
  exam_type: ExamType;
  subject_id: string;
  title: string;
  description: string | null;
  instructions: string | null;
  duration_minutes: number;
  starts_at: string;
  ends_at: string;
  status: ExamStatus;
  /** "draft" | "scheduled" | "live" | "completed" | "archived" - derived from `status`
   * plus the start/end window, never stored. */
  effective_status: "draft" | "scheduled" | "live" | "completed" | "archived";
  randomize: boolean;
  shuffle_options: boolean;
  negative_marking: boolean;
  results_published: boolean;
  selection_rules: { rules: SelectionRule[] };
  proctor_config: ProctorConfig;
  grading_config: Record<string, unknown>;
  created_at: string;
  pool_size: number;
  total_questions: number;
  subject_name: string | null;
  // Mode-specific
  passing_percentage: number | null;
  declared_total_marks: number | null;
  /** How many sittings one candidate may take. */
  max_attempts: number;
  /** A descriptive tag shown to candidates. Null means "mixed". */
  difficulty: Difficulty | null;
  // Academic
  course: string | null;
  department: string | null;
  semester: string | null;
  // Corporate
  company_name: string | null;
  job_role: string | null;
  // Sections
  sections: ExamSection[];
  /** Language codes the candidate's selector offers for this exam. Always leads "en". */
  languages: string[];
}

// ---------------------------------------------------------------- templates

export interface ExamTemplate {
  id: string;
  name: string;
  description: string | null;
  exam_type: ExamType;
  job_role: string | null;
  sections: Array<{
    name: string;
    order_index: number;
    selection_rules: { rules: SelectionRule[] };
    marks_per_question: number | null;
    negative_marks: number | null;
    duration_minutes: number | null;
  }>;
  duration_minutes: number | null;
  is_builtin: boolean;
}

// ---------------------------------------------------------------- recruitment

export interface SectionScore {
  section_name: string;
  obtained_marks: number;
  total_marks: number;
  percentage: number;
  correct: number;
  incorrect: number;
  unanswered: number;
}

export interface RankingRow {
  candidate_id: string;
  full_name: string;
  email: string;
  overall_percentage: number;
  obtained_marks: number;
  total_marks: number;
  correct_count: number;
  incorrect_count: number;
  unanswered_count: number;
  accuracy: number;
  time_taken_seconds: number | null;
  rank: number;
  section_scores: SectionScore[];
  shortlist_status: ShortlistStatus | null;
  suspicion_score: number;
  is_flagged: boolean;
  result_id: string | null;
  session_id: string | null;
  published: boolean;
  needs_integrity_review: boolean;
  integrity_verdict: string;
  pending_review_count: number;
}

export interface TopPerformer {
  candidate_name: string;
  exam_title: string;
  obtained_marks: number;
  total_marks: number;
  percentage: number;
}

export interface ShortlistDecision {
  candidate_id: string;
  status: ShortlistStatus;
  note?: string | null;
}

// ---------------------------------------------------------------- AI drafts

/**
 * Result of a PDF import. Mirrors `AiPdfImportOut`.
 *
 * The read counts travel with the drafts so the examiner can tell a fully-parsed
 * document from one where only a few pages carried a text layer.
 */
export interface PdfImportResult {
  filename: string;
  pages: number;
  empty_pages: number;
  characters: number;
  truncated: boolean;
  /** False when the drafts came from the offline stub and are NOT drawn from the PDF. */
  source_grounded: boolean;
  drafts: AiDraft[];
}

export interface AiDraft {
  id: string;
  subject_id: string | null;
  category: QuestionCategory;
  topic: string | null;
  difficulty: Difficulty;
  question_type: QuestionType;
  payload: Record<string, unknown>;
  original_payload: Record<string, unknown> | null;
  provider: string;
  model: string | null;
  error: string | null;
  status: DraftStatus;
  requested_by_id: string | null;
  reviewed_by_id: string | null;
  reviewed_at: string | null;
  reject_reason: string | null;
  published_question_id: string | null;
  created_at: string;
}

// ------------------------------------------------------------ question import

export interface ImportedOption {
  text: string;
  is_correct: boolean;
}

/** One parsed row, with everything wrong with it attached. */
export interface ImportedRow {
  /** 1-based including the header, so it matches the row number in Excel. */
  row_number: number;
  body: string;
  /** Resolved from the row's own "Subject" cell, or the import's default subject. */
  subject_id: string | null;
  subject_name: string | null;
  question_type: QuestionType;
  difficulty: Difficulty;
  category: QuestionCategory;
  topic: string | null;
  marks: number;
  negative_marks: number;
  model_answer: string | null;
  explanation: string | null;
  tags: string[];
  min_words: number | null;
  max_words: number | null;
  spec: Record<string, unknown> | null;
  options: ImportedOption[];
  /** Empty means the row passes the same validation the authoring form applies. */
  problems: string[];
  /** Where an identical question already exists — an earlier row, or the bank. */
  duplicate_of: string | null;
  /** Client-side only: whether the examiner has this row ticked for import. */
  save_to_bank?: boolean;
}

export interface ImportParseResult {
  filename: string;
  total: number;
  valid: number;
  invalid: number;
  duplicates: number;
  rows: ImportedRow[];
  /** Every worksheet name, for an .xlsx/.xlsm with more than one. Empty otherwise. */
  sheet_names: string[];
  /** Which sheet `rows` was actually read from. */
  sheet_name: string | null;
}

export interface ImportResult {
  created: number;
  failed: number;
  errors: { row_number?: number; error: string }[];
  question_ids: string[];
}

// ---------------------------------------------------------------- analytics

export interface TopicPerformance {
  topic: string;
  total_questions: number;
  correct: number;
  incorrect: number;
  avg_score_pct: number;
}

export interface SectionAnalytics {
  section_name: string;
  total_marks: number;
  avg_obtained: number;
  avg_percentage: number;
  /** null when the exam declared no pass mark - no verdict, not 0% passing. */
  pass_rate: number | null;
}

export interface ExamAnalytics {
  exam_id: string;
  exam_title: string;
  exam_type: string;
  total_sessions: number;
  completed_sessions: number;
  avg_percentage: number;
  highest_percentage: number;
  lowest_percentage: number;
  /** null when the exam declared no pass mark - no verdict, not 0% passing. */
  pass_rate: number | null;
  avg_time_seconds: number | null;
  difficulty_breakdown: Array<{
    difficulty: Difficulty;
    total_questions: number;
    correct: number;
    incorrect: number;
    unanswered: number;
    avg_score_pct: number;
  }>;
  topic_performance: TopicPerformance[];
  section_analytics: SectionAnalytics[];
  score_distribution: number[];
}

export interface TopicScore {
  topic: string;
  percentage: number;
  /** Sample size. "40% in Normalisation" reads differently over 2 answers than 20. */
  answers: number;
}

export interface PerformanceAnalysis {
  candidate_id: string;
  candidate_name: string;
  overall_percentage: number;
  strong_areas: string[];
  weak_areas: string[];
  recommendations: string[];
  summary: string;
  section_notes: string[];
  /** Per-topic breakdown behind the narrative, so the summary can be checked. */
  topic_scores: TopicScore[];
  generated_at: string;
}

// ---------------------------------------------------------------- proctoring

export interface ProctorConfig {
  webcam_enabled: boolean;
  gaze_tracking_enabled: boolean;
  gaze_sensitivity: number;
  max_tab_switches: number;
  /**
   * Times the candidate may leave the exam window (tab switch or fullscreen exit)
   * before their answers are submitted for them. 0 switches the ladder off.
   */
  max_focus_violations?: number;
  flag_on_score: number;
  terminate_on_score: number;
  snapshot_interval_seconds: number;
  require_fullscreen: boolean;
  require_microphone?: boolean;
  require_single_display?: boolean;
  min_bandwidth_mbps?: number;
  block_copy_paste: boolean;
  weights?: Record<string, number>;
}

export interface ExamPoolCheck {
  can_publish: boolean;
  problems: string[];
  pool_size: number;
  required_count: number;
}

export interface PaperQuestion {
  question_id: string;
  question_type: QuestionType;
  difficulty: Difficulty;
  body: string;
  marks: number;
  negative_marks: number;
  category: QuestionCategory;
  topic: string | null;
  min_words: number | null;
  max_words: number | null;
  image_url: string | null;
  /** Candidate-safe projection only. Never the answer key. */
  spec: QuestionSpec | null;
  parent_question_id: string | null;
  /** Section this question belongs to. Null on single-section papers. */
  section_id: string | null;
  options: Option[];
  saved_option_ids: string[];
  saved_text: string | null;
  saved_image_url: string | null;
  saved_word_count: number | null;
  /** Candidate's mark-for-review flag. Persisted in DB. */
  is_review_flagged: boolean;
}

export interface SessionSection {
  id: string;
  name: string;
  order_index: number;
  question_ids: string[];
}

export interface ExamSession {
  session_id: string;
  exam_id: string;
  exam_title: string;
  status: SessionStatus;
  started_at: string;
  expires_at: string;
  server_time: string;
  seconds_remaining: number;
  total_marks: number;
  questions: PaperQuestion[];
  proctor_config: ProctorConfig;
  exam_token: string | null;
  /** Ordered sections for section-navigation tabs. Empty on single-section papers. */
  sections: SessionSection[];
  /** The locale this paper was rendered in - what the language selector should show
   * as selected right now. */
  locale: string;
  /** Language codes this exam's selector may switch to. Always leads "en". */
  available_languages: string[];
}

export interface CandidateExamCard {
  exam_id: string;
  title: string;
  subject_name: string;
  duration_minutes: number;
  starts_at: string;
  ends_at: string;
  total_questions: number;
  session_status: SessionStatus | null;
  session_id: string | null;
  result_id: string | null;
  result_published: boolean;
  /** All null until an examiner releases the result — an unpublished score is not a result. */
  obtained_marks?: number | null;
  total_marks?: number | null;
  percentage?: number | null;
  passing_percentage?: number | null;
  /** null when the exam declared no pass mark, or the result is not out yet. */
  passed?: boolean | null;
  submitted_at?: string | null;
  can_start: boolean;
  reason: string | null;
  exam_type?: ExamType;
  course?: string | null;
  department?: string | null;
  semester?: string | null;
  company_name?: string | null;
  job_role?: string | null;
  sections_count?: number;
  has_coding?: boolean;
  proctor_config?: ProctorConfig;
  /** Language codes this exam's selector may switch to. Always leads "en". */
  available_languages?: string[];
}

export interface HeartbeatOut {
  server_time: string;
  seconds_remaining: number;
  status: SessionStatus;
  suspicion_score: number;
  focus_violation_count: number;
  focus_violations_left: number;
  warnings: string[];
  exam_token: string | null;
}

export interface ProctorBatchOut {
  accepted: number;
  suspicion_score: number;
  tab_switch_count: number;
  /** Times the candidate left the exam window - tab switch or fullscreen exit. */
  focus_violation_count: number;
  /** How many more are allowed before the paper is submitted. -1 = ladder off. */
  focus_violations_left: number;
  is_flagged: boolean;
  terminated: boolean;
  /** The ladder ran out: the paper was submitted and will be marked normally. */
  auto_submitted: boolean;
  warnings: string[];
}

export interface ProctorEvent {
  id: string;
  event_type: ProctorEventType;
  severity: "info" | "warning" | "critical";
  occurred_at: string;
  server_received_at: string;
  duration_ms: number | null;
  weight: number;
  confidence: number | null;
  question_id: string | null;
  metadata: Record<string, unknown> | null;
  snapshot_url: string | null;
}

export interface ProctorReview {
  session_id: string;
  candidate_name: string;
  candidate_email: string;
  exam_title: string;
  status: string;
  started_at: string;
  submitted_at: string | null;
  suspicion_score: number;
  tab_switch_count: number;
  /** Tab switches plus fullscreen exits — what the exam-window rule counts. */
  focus_violation_count: number;
  is_flagged: boolean;
  termination_reason: string | null;
  /** The examiner's ruling on how the sitting was conducted. Separate from the score. */
  integrity_verdict: IntegrityVerdict;
  integrity_note: string | null;
  integrity_reviewed_by: string | null;
  integrity_reviewed_at: string | null;
  /** Flagged and still unruled — the queue an examiner clears before results go out. */
  needs_integrity_review: boolean;
  breakdown: Record<string, number>;
  events: ProctorEvent[];
}

/**
 * Proctoring flags a sitting; a named examiner decides what it was. A candidate can sit
 * honestly and score badly, or cheat and score well — score and conduct are separate axes.
 */
export type IntegrityVerdict = "pending" | "cleared" | "malpractice";

export const INTEGRITY_VERDICT_LABEL: Record<IntegrityVerdict, string> = {
  pending: "Awaiting review",
  cleared: "Genuine attempt",
  malpractice: "Malpractice",
};

export interface AiEvaluation {
  provider: string;
  model: string | null;
  score: number;
  max_score: number;
  justification: string;
  confidence: number;
  key_points_matched: string[];
  key_points_missed: string[];
  created_at: string;
  error: string | null;
}

export interface GradingQueueItem {
  answer_id: string;
  session_id: string;
  exam_id: string;
  exam_title: string;
  candidate_name: string;
  candidate_email: string;
  question_id: string;
  question_body: string;
  question_type: QuestionType;
  model_answer: string | null;
  rubric: Record<string, unknown> | null;
  text_answer: string | null;
  word_count: number | null;
  /** Words below the question's minimum. Informational - never a penalty. */
  words_below_minimum: number;
  image_url: string | null;
  image_thumb_url: string | null;
  /** Tesseract's read of a handwritten scan. Advisory. */
  ocr_text: string | null;
  ocr_confidence: number | null;
  max_marks: number;
  awarded_marks: number | null;
  grade_status: GradeStatus;
  examiner_comment: string | null;
  ai_evaluation: AiEvaluation | null;
  submitted_at: string | null;
}

export interface GradingSummary {
  exam_id: string;
  exam_title: string;
  total_sessions: number;
  submitted_sessions: number;
  pending_review: number;
  reviewed: number;
  results_published: boolean;
}

export interface Result {
  id: string;
  session_id: string;
  total_marks: number;
  obtained_marks: number;
  percentage: number;
  correct_count: number;
  incorrect_count: number;
  unanswered_count: number;
  pending_review_count: number;
  published: boolean;
  published_at: string | null;
  /** Context so a bare percentage is readable on a dashboard row. */
  exam_title?: string | null;
  subject_name?: string | null;
  passing_percentage?: number | null;
  /** null when the exam declared no pass mark — no verdict, not a failure. */
  passed?: boolean | null;
}

export interface SectionScoreResult {
  section_id: string;
  section_name: string;
  total_marks: number;
  obtained_marks: number;
  percentage: number;
  correct: number;
  incorrect: number;
  unanswered: number;
}

export interface QuestionResult {
  question_id: string;
  body: string;
  question_type: QuestionType;
  marks: number;
  awarded_marks: number | null;
  grade_status: GradeStatus;
  is_correct: boolean | null;
  your_answer: string | null;
  correct_answer: string | null;
  examiner_comment: string | null;
  ai_justification: string | null;
  section_name: string | null;
}

export interface ResultDetail {
  result: Result;
  exam_title: string;
  subject_name: string;
  candidate_name: string;
  submitted_at: string | null;
  questions: QuestionResult[];
  /** Per-section scores. Empty on single-section papers. */
  section_scores: SectionScoreResult[];
  /** "academic" | "corporate" — drives PASS/FAIL vs QUALIFIED display. */
  exam_type: string;
  passing_percentage: number | null;
  /** Percentile vs published cohort. null when cohort < 10. */
  percentile: number | null;
  cohort_size: number;
  time_taken_seconds: number | null;
}

export interface AdminStats {
  total_users: number;
  candidates: number;
  examiners: number;
  admins: number;
  pending_approvals: number;
  subjects: number;
  questions: number;
  exams: number;
  published_exams: number;
  /** Published and inside its start/end window right now. */
  live_exams: number;
  /** Published, but its window has already ended. */
  completed_exams: number;
  live_sessions: number;
  flagged_sessions: number;
  pending_grading: number;
}

export interface LiveExamRow {
  exam_id: string;
  exam_title: string;
  examiner_name: string;
  candidate_count: number;
  active_count: number;
  flagged_count: number;
  time_remaining_str: string;
}

export interface ComponentHealth {
  /** "checked" = a real probe ran this request. "configured" = not independently
   * measurable, only reports whether the feature is wired up. */
  basis: "checked" | "configured";
  status: string;
  detail?: string | null;
}

export interface SystemHealth {
  api: ComponentHealth;
  database: ComponentHealth;
  storage: ComponentHealth;
  websocket: ComponentHealth;
  ai_proctoring: ComponentHealth;
  authentication: ComponentHealth;
}

export interface ExaminerStats {
  my_questions: number;
  my_exams: number;
  published_exams: number;
  live_sessions: number;
  flagged_sessions: number;
  pending_grading: number;
  subjects: number;
  active_assessments: number;
  completed_assessments: number;
  published_results_count: number;
  total_candidates: number;
}

export interface CandidateStats {
  available_exams: number;
  completed_exams: number;
  published_results: number;
  average_percentage: number | null;
  best_percentage: number | null;
}

export interface CandidateRow {
  id: string;
  full_name: string;
  email: string;
  access_status: AccessStatus;
  is_active: boolean;
  /** Permission to sign in, which is not the same as the account existing. */
  login_access: LoginAccessStatus | null;
  created_at: string;
  last_login_at: string | null;
  attempts: number;
  completed: number;
  flagged_sessions: number;
  average_percentage: number | null;
}

export interface CandidateAttempt {
  session_id: string;
  exam_id: string;
  exam_title: string;
  status: SessionStatus;
  started_at: string;
  submitted_at: string | null;
  percentage: number | null;
  published: boolean;
  result_id: string | null;
  suspicion_score: number;
  is_flagged: boolean;
  integrity_verdict: IntegrityVerdict;
  /** Flagged and unruled — publishing is blocked until an examiner decides. */
  needs_integrity_review: boolean;
  /** Answers still awaiting a human decision. Publishing is blocked while non-zero. */
  pending_review_count: number;
}

export interface ExamResultRow {
  session_id: string;
  result_id: string | null;
  candidate_name: string;
  candidate_email: string;
  status: SessionStatus;
  submitted_at: string | null;
  obtained_marks: number | null;
  total_marks: number | null;
  percentage: number | null;
  pending_review: number;
  published: boolean;
  suspicion_score: number;
  is_flagged: boolean;
}

export interface Activity {
  kind: string;
  message: string;
  at: string;
  severity: "info" | "warning" | "critical";
}

export interface LiveSessionRow {
  session_id: string;
  candidate_name: string;
  initials: string;
  exam_title: string;
  subject_name: string;
  answered_count: number;
  total_questions: number;
  time_remaining_str: string;
  suspicion_score: number;
  is_flagged: boolean;
  status: string;
}

export interface ProctoringAlertRow {
  id: string;
  alert_type: string;
  candidate_name: string;
  exam_title: string;
  time_ago: string;
  suspicion_delta: string;
  severity: "rose" | "amber" | "mint";
}

export interface ProctoringSignals {
  face_present_pct: number;
  gaze_on_screen_pct: number;
  no_tab_switches_pct: number;
  single_face_pct: number;
  high_suspicion_pct: number;
}

export interface ScoreHistogramBin {
  bin: string;
  count: number;
}

export interface AiGradingQueueItem {
  id: string;
  question_type: "short" | "long" | "image";
  title: string;
  ai_score: string;
}

export interface UpcomingExamItem {
  id: string;
  title: string;
  time_str: string;
}

export interface RecentActivityItem {
  message: string;
  time_ago: string;
  severity: string;
}

export interface LiveDashboardData {
  active_sessions_count: number;
  exams_today_count: number;
  flagged_sessions_count: number;
  grading_queue_count: number;
  ai_prescored_count: number;
  avg_score_pct: number;
  live_sessions: LiveSessionRow[];
  proctoring_alerts: ProctoringAlertRow[];
  proctoring_signals: ProctoringSignals;
  score_distribution: ScoreHistogramBin[];
  ai_grading_queue: AiGradingQueueItem[];
  upcoming_exams: UpcomingExamItem[];
  recent_activity: RecentActivityItem[];
}

