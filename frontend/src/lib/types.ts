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
  | "gaze_away"
  | "tab_switch"
  | "window_blur"
  | "fullscreen_exit"
  | "camera_blocked"
  | "paste_attempt"
  | "copy_attempt"
  | "devtools_open";

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
  // Academic
  course: string | null;
  department: string | null;
  semester: string | null;
  // Corporate
  company_name: string | null;
  job_role: string | null;
  // Sections
  sections: ExamSection[];
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
  pass_rate: number;
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
  pass_rate: number;
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

export interface PerformanceAnalysis {
  candidate_id: string;
  candidate_name: string;
  overall_percentage: number;
  strong_areas: string[];
  weak_areas: string[];
  recommendations: string[];
  summary: string;
  section_notes: string[];
  generated_at: string;
}

// ---------------------------------------------------------------- proctoring

export interface ProctorConfig {
  webcam_enabled: boolean;
  gaze_tracking_enabled: boolean;
  gaze_sensitivity: number;
  max_tab_switches: number;
  flag_on_score: number;
  terminate_on_score: number;
  snapshot_interval_seconds: number;
  require_fullscreen: boolean;
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
}

export interface HeartbeatOut {
  server_time: string;
  seconds_remaining: number;
  status: SessionStatus;
  suspicion_score: number;
  warnings: string[];
  exam_token: string | null;
}

export interface ProctorBatchOut {
  accepted: number;
  suspicion_score: number;
  tab_switch_count: number;
  is_flagged: boolean;
  terminated: boolean;
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
  is_flagged: boolean;
  termination_reason: string | null;
  breakdown: Record<string, number>;
  events: ProctorEvent[];
}

export interface AiEvaluation {
  provider: string;
  model: string | null;
  score: number;
  max_score: number;
  justification: string;
  confidence: number;
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
  live_sessions: number;
  flagged_sessions: number;
  pending_grading: number;
}

export interface ExaminerStats {
  my_questions: number;
  my_exams: number;
  published_exams: number;
  live_sessions: number;
  flagged_sessions: number;
  pending_grading: number;
  subjects: number;
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

