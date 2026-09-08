from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.domain.enums import ExamMode, QuestionType, AttemptPolicy


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    mfa_code: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class QuestionOptionRequest(BaseModel):
    text: str
    is_correct: bool = False


class CreateQuestionBankRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class UpdateQuestionBankRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class CreateTopicRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class UpdateTopicRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class CreateQuestionRequest(BaseModel):
    text: str = Field(min_length=1)
    question_type: QuestionType
    time_seconds: int = Field(gt=0)
    topic_id: Optional[UUID] = None
    options: list[QuestionOptionRequest] = []


class UpdateQuestionRequest(BaseModel):
    text: str = Field(min_length=1)
    question_type: QuestionType
    time_seconds: int = Field(gt=0)
    topic_id: Optional[UUID] = None
    options: list[QuestionOptionRequest] = []


class RestoreQuestionBackupResponse(BaseModel):
    imported_count: int
    deleted_count: int
    skipped_count: int
    errors: list[str] = []


class CreateExamRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    question_bank_id: UUID
    mode: ExamMode
    total_score: float = Field(gt=0)
    question_count: int = Field(gt=0)
    closes_at: datetime
    random_selection: bool = True
    enforce_question_time: bool = False
    require_camera: bool = True
    require_attempt_video: bool = False
    max_attempts: int = Field(default=1, ge=1)
    attempt_policy: AttemptPolicy = AttemptPolicy.FLEXIBLE
    proctoring_sensitivity: float = Field(default=0.4, ge=0.1, le=1.0)
    attempt_cooldown_enabled: bool = False
    attempt_cooldown_seconds: int = Field(default=0, ge=0)
    selected_question_ids: list[UUID] = []


class InviteRequest(BaseModel):
    emails: list[EmailStr] = Field(min_length=1)


class SubmitAnswerRequest(BaseModel):
    question_id: UUID
    selected_option_ids: list[UUID] = []
    open_text: Optional[str] = None


class SubmitExamRequest(BaseModel):
    skip_video_required: bool = False


class SavedAnswerResponse(BaseModel):
    question_id: UUID
    selected_option_ids: list[UUID] = []
    open_text: Optional[str] = None


class SaveAttemptProgressRequest(BaseModel):
    current_question_index: int = Field(ge=0)
    locked_question_ids: list[UUID] = []


class StartAttemptRequest(BaseModel):
    camera_verified: bool = False
    full_name: str = Field(min_length=2, max_length=255)


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    mfa_enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionBankResponse(BaseModel):
    id: UUID
    name: str
    description: str
    owner_id: UUID
    created_at: datetime
    has_exams: bool = False
    question_count: int = 0


class TopicResponse(BaseModel):
    id: UUID
    name: str
    description: str
    owner_id: UUID
    created_at: datetime


class QuestionOptionResponse(BaseModel):
    id: UUID
    text: str
    is_correct: bool = False
    order: int


class QuestionResponse(BaseModel):
    id: UUID
    text: str
    question_type: QuestionType
    time_seconds: int
    topic_id: Optional[UUID] = None
    topic_name: Optional[str] = None
    image_url: Optional[str] = None
    options: list[QuestionOptionResponse] = []
    used_in_exam: bool = False


class PaginatedQuestionsResponse(BaseModel):
    items: list[QuestionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ExamResponse(BaseModel):
    id: UUID
    title: str
    description: str
    mode: ExamMode
    status: str
    total_score: float
    question_count: int
    closes_at: datetime
    random_selection: bool
    enforce_question_time: bool
    require_camera: bool
    require_attempt_video: bool
    max_attempts: int
    attempt_policy: AttemptPolicy
    proctoring_sensitivity: float
    attempt_cooldown_enabled: bool
    attempt_cooldown_seconds: int
    question_bank_id: UUID
    has_attempts: bool = False


class InvitationResponse(BaseModel):
    id: UUID
    invitee_email: str
    token: str
    status: str


class InvitationDetailResponse(BaseModel):
    id: UUID
    invitee_email: str
    token: str
    status: str
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    attempt_status: str = "not_started"
    attempts_completed: int = 0
    attempts_total: int = 1
    invite_link: str


class AttemptResponse(BaseModel):
    id: UUID
    exam_id: UUID
    status: str
    attempt_number: int = 1
    started_at: Optional[datetime] = None
    score: Optional[float] = None
    fraud_score: float = 0.0


class AttemptAnswerDetailResponse(BaseModel):
    question_id: UUID
    order: int
    question_text: str
    question_type: QuestionType
    selected_options: list[str] = []
    correct_options: list[str] = []
    open_text: Optional[str] = None
    is_correct: Optional[bool] = None
    points_earned: float = 0
    max_points: float = 0
    answered: bool = False


class AttemptSnapshotResponse(BaseModel):
    id: UUID
    snapshot_type: str
    image_url: str
    captured_at: Optional[datetime] = None


class AttemptAnswersReportResponse(BaseModel):
    attempt_id: UUID
    attempt_number: int = 1
    invitee_email: str
    invitee_full_name: str = ""
    exam_title: str
    score: Optional[float] = None
    total_score: float
    answers: list[AttemptAnswerDetailResponse]
    snapshots: list[AttemptSnapshotResponse] = []
    video_url: Optional[str] = None
    require_attempt_video: bool = False


class ExamSessionResponse(BaseModel):
    attempt: AttemptResponse
    exam: ExamResponse
    questions: list[QuestionResponse]
    total_time_seconds: int
    remaining_seconds: int
    saved_answers: list[SavedAnswerResponse] = []
    current_question_index: int = 0
    locked_question_ids: list[UUID] = []
    question_remaining_seconds: Optional[int] = None
    resumed: bool = False
