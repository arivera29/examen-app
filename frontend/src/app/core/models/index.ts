export interface User {
  id: string;
  email: string;
  full_name: string;
  mfa_enabled: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface QuestionBank {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  created_at: string;
  has_exams?: boolean;
  question_count?: number;
}

export interface Topic {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  created_at: string;
}

export interface QuestionOption {
  id: string;
  text: string;
  is_correct: boolean;
  order: number;
}

export interface Question {
  id: string;
  text: string;
  question_type: 'single_choice' | 'multiple_choice' | 'open' | 'true_false';
  time_seconds: number;
  topic_id?: string | null;
  topic_name?: string | null;
  image_url?: string;
  options: QuestionOption[];
  used_in_exam?: boolean;
}

export interface PaginatedQuestions {
  items: Question[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface QuestionBackupRestoreResult {
  imported_count: number;
  deleted_count: number;
  skipped_count: number;
  errors: string[];
}

export interface Exam {
  id: string;
  title: string;
  description: string;
  mode: 'simulation' | 'real';
  status: string;
  total_score: number;
  question_count: number;
  closes_at: string;
  random_selection: boolean;
  enforce_question_time: boolean;
  require_attempt_video: boolean;
  max_attempts: number;
  attempt_policy: 'flexible' | 'sequential';
  question_bank_id: string;
  has_attempts?: boolean;
}

export interface ExamSession {
  attempt: {
    id: string;
    exam_id: string;
    status: string;
    attempt_number?: number;
    started_at?: string;
    score?: number;
    fraud_score: number;
  };
  exam: Exam;
  questions: Question[];
  total_time_seconds: number;
  remaining_seconds: number;
  saved_answers?: SavedAnswer[];
  current_question_index?: number;
  locked_question_ids?: string[];
  question_remaining_seconds?: number | null;
  resumed?: boolean;
}

export interface SavedAnswer {
  question_id: string;
  selected_option_ids: string[];
  open_text?: string | null;
}

export interface Invitation {
  id: string;
  invitee_email: string;
  token: string;
  status: string;
  sent_at: string | null;
  created_at: string | null;
  attempt_status: string;
  attempts_completed?: number;
  attempts_total?: number;
  invite_link: string;
}

export interface ExamReport {
  exam_id: string;
  exam_title: string;
  total_score: number;
  question_count?: number;
  individual_reports: IndividualReport[];
  summary: {
    total_invitees: number;
    completed: number;
    average_score: number;
    highest_score: number;
    lowest_score: number;
    average_correct_answers?: number;
    average_incorrect_answers?: number;
  };
}

export interface IndividualReport {
  attempt_id: string;
  attempt_number: number;
  attempts_used?: number;
  invitee_email: string;
  invitee_full_name: string;
  score: number | null;
  total_score: number;
  percentage: number;
  status: string;
  fraud_score: number;
  proctoring_events_count: number;
  answers_count: number;
  correct_answers_count?: number;
  incorrect_answers_count?: number;
  started_at: string | null;
  submitted_at: string | null;
  is_final_score?: boolean;
}

export interface AttemptAnswerDetail {
  question_id: string;
  order: number;
  question_text: string;
  question_type: string;
  selected_options: string[];
  correct_options: string[];
  open_text: string | null;
  is_correct: boolean | null;
  points_earned: number;
  max_points: number;
  answered: boolean;
}

export interface AttemptSnapshot {
  id: string;
  snapshot_type: 'start' | 'progress';
  image_url: string;
  captured_at: string | null;
}

export interface AttemptAnswersReport {
  attempt_id: string;
  invitee_email: string;
  invitee_full_name: string;
  exam_title: string;
  score: number | null;
  total_score: number;
  answers: AttemptAnswerDetail[];
  snapshots?: AttemptSnapshot[];
  video_url?: string | null;
  require_attempt_video?: boolean;
}
