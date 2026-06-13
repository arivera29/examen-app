from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from app.domain.enums import (
    AttemptPolicy,
    AttemptStatus,
    ExamMode,
    ExamStatus,
    InvitationStatus,
    ProctoringEventType,
    SnapshotType,
    QuestionType,
)


@dataclass
class User:
    email: str
    hashed_password: str
    full_name: str
    id: UUID = field(default_factory=uuid4)
    is_active: bool = True
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QuestionOption:
    text: str
    is_correct: bool
    id: UUID = field(default_factory=uuid4)
    question_id: Optional[UUID] = None
    order: int = 0


@dataclass
class Topic:
    name: str
    owner_id: UUID
    id: UUID = field(default_factory=uuid4)
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Question:
    text: str
    question_type: QuestionType
    time_seconds: int
    owner_id: UUID
    id: UUID = field(default_factory=uuid4)
    topic_id: Optional[UUID] = None
    topic_name: Optional[str] = None
    image_url: Optional[str] = None
    options: list[QuestionOption] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QuestionBank:
    name: str
    description: str
    owner_id: UUID
    id: UUID = field(default_factory=uuid4)
    questions: list[Question] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExamQuestionConfig:
    question_id: UUID
    order: int
    points: float
    time_seconds: int


@dataclass
class Exam:
    title: str
    description: str
    owner_id: UUID
    question_bank_id: UUID
    mode: ExamMode
    total_score: float
    question_count: int
    closes_at: datetime
    random_selection: bool
    enforce_question_time: bool = False
    require_attempt_video: bool = False
    max_attempts: int = 1
    attempt_policy: AttemptPolicy = AttemptPolicy.FLEXIBLE
    id: UUID = field(default_factory=uuid4)
    status: ExamStatus = ExamStatus.DRAFT
    selected_question_ids: list[UUID] = field(default_factory=list)
    question_configs: list[ExamQuestionConfig] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExamInvitation:
    exam_id: UUID
    invitee_email: str
    id: UUID = field(default_factory=uuid4)
    token: str = field(default_factory=lambda: str(uuid4()))
    status: InvitationStatus = InvitationStatus.PENDING
    sent_at: Optional[datetime] = None
    decision_deadline_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExamAttempt:
    invitation_id: UUID
    exam_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: AttemptStatus = AttemptStatus.NOT_STARTED
    attempt_number: int = 1
    invitee_full_name: str = ""
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    score: Optional[float] = None
    fraud_score: float = 0.0
    camera_verified: bool = False
    attempt_video_url: Optional[str] = None
    selected_question_ids: list[UUID] = field(default_factory=list)
    question_configs: list[ExamQuestionConfig] = field(default_factory=list)
    current_question_index: int = 0
    locked_question_ids: list[UUID] = field(default_factory=list)
    current_question_started_at: Optional[datetime] = None


@dataclass
class Answer:
    attempt_id: UUID
    question_id: UUID
    id: UUID = field(default_factory=uuid4)
    selected_option_ids: list[UUID] = field(default_factory=list)
    open_text: Optional[str] = None
    is_correct: Optional[bool] = None
    points_earned: float = 0.0


@dataclass
class ProctoringEvent:
    attempt_id: UUID
    event_type: ProctoringEventType
    confidence: float
    id: UUID = field(default_factory=uuid4)
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AttemptSnapshot:
    attempt_id: UUID
    snapshot_type: SnapshotType
    image_url: str
    id: UUID = field(default_factory=uuid4)
    captured_at: datetime = field(default_factory=datetime.utcnow)
