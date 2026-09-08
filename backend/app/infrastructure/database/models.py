from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
from sqlalchemy.sql import func
import uuid

from app.config import settings
from app.domain.enums import (
    AttemptPolicy,
    AttemptStatus,
    ExamMode,
    ExamStatus,
    InvitationStatus,
    ProctoringEventType,
    QuestionType,
    SnapshotType,
)


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    question_banks = relationship("QuestionBankModel", back_populates="owner")
    exams = relationship("ExamModel", back_populates="owner")
    topics = relationship("TopicModel", back_populates="owner")


class TopicModel(Base):
    __tablename__ = "topics"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    owner_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("UserModel", back_populates="topics")
    questions = relationship("QuestionModel", back_populates="topic")


class QuestionBankModel(Base):
    __tablename__ = "question_banks"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    owner_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("UserModel", back_populates="question_banks")
    questions = relationship("QuestionModel", back_populates="bank", cascade="all, delete-orphan")
    exams = relationship("ExamModel", back_populates="question_bank")


class QuestionModel(Base):
    __tablename__ = "questions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_id = Column(PGUUID(as_uuid=True), ForeignKey("question_banks.id"), nullable=False)
    text = Column(Text, nullable=False)
    question_type = Column(Enum(QuestionType), nullable=False)
    topic_id = Column(PGUUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    time_seconds = Column(Integer, nullable=False, default=60)
    image_url = Column(String(500), nullable=True)
    owner_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bank = relationship("QuestionBankModel", back_populates="questions")
    topic = relationship("TopicModel", back_populates="questions")
    options = relationship("QuestionOptionModel", back_populates="question", cascade="all, delete-orphan")


class QuestionOptionModel(Base):
    __tablename__ = "question_options"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(PGUUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False)
    order = Column(Integer, default=0)

    question = relationship("QuestionModel", back_populates="options")


class ExamModel(Base):
    __tablename__ = "exams"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    owner_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    question_bank_id = Column(PGUUID(as_uuid=True), ForeignKey("question_banks.id"), nullable=False)
    mode = Column(Enum(ExamMode), nullable=False)
    status = Column(Enum(ExamStatus), default=ExamStatus.DRAFT)
    total_score = Column(Float, nullable=False)
    question_count = Column(Integer, nullable=False)
    closes_at = Column(DateTime(timezone=True), nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    random_selection = Column(Boolean, default=True)
    enforce_question_time = Column(Boolean, default=False)
    require_camera = Column(Boolean, default=True, nullable=False)
    require_attempt_video = Column(Boolean, default=False)
    max_attempts = Column(Integer, default=1, nullable=False)
    attempt_policy = Column(String(20), default=AttemptPolicy.FLEXIBLE.value, nullable=False)
    proctoring_sensitivity = Column(Float, default=0.4, nullable=False)
    attempt_cooldown_enabled = Column(Boolean, default=False, nullable=False)
    attempt_cooldown_seconds = Column(Integer, default=0, nullable=False)
    selected_question_ids = Column(JSON, default=list)
    question_configs = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("UserModel", back_populates="exams")
    question_bank = relationship("QuestionBankModel", back_populates="exams")
    invitations = relationship("ExamInvitationModel", back_populates="exam", cascade="all, delete-orphan")
    attempts = relationship("ExamAttemptModel", back_populates="exam", cascade="all, delete-orphan")


class ExamInvitationModel(Base):
    __tablename__ = "exam_invitations"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id = Column(PGUUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    invitee_email = Column(String(255), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(Enum(InvitationStatus), default=InvitationStatus.PENDING)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    decision_deadline_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    exam = relationship("ExamModel", back_populates="invitations")
    attempts = relationship("ExamAttemptModel", back_populates="invitation")


class ExamAttemptModel(Base):
    __tablename__ = "exam_attempts"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invitation_id = Column(PGUUID(as_uuid=True), ForeignKey("exam_invitations.id"), nullable=False)
    exam_id = Column(PGUUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    attempt_number = Column(Integer, default=1, nullable=False)
    status = Column(Enum(AttemptStatus), default=AttemptStatus.NOT_STARTED)
    invitee_full_name = Column(String(255), default="", nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    score = Column(Float, nullable=True)
    fraud_score = Column(Float, default=0.0)
    camera_verified = Column(Boolean, default=False)
    attempt_video_url = Column(String(512), nullable=True)
    selected_question_ids = Column(JSON, default=list)
    question_configs = Column(JSON, default=list)
    current_question_index = Column(Integer, default=0, nullable=False)
    locked_question_ids = Column(JSON, default=list)
    current_question_started_at = Column(DateTime(timezone=True), nullable=True)

    invitation = relationship("ExamInvitationModel", back_populates="attempts")
    exam = relationship("ExamModel", back_populates="attempts")
    answers = relationship("AnswerModel", back_populates="attempt", cascade="all, delete-orphan")
    proctoring_events = relationship("ProctoringEventModel", back_populates="attempt", cascade="all, delete-orphan")
    snapshots = relationship("AttemptSnapshotModel", back_populates="attempt", cascade="all, delete-orphan")


class AnswerModel(Base):
    __tablename__ = "answers"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(PGUUID(as_uuid=True), ForeignKey("exam_attempts.id"), nullable=False)
    question_id = Column(PGUUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    selected_option_ids = Column(JSON, default=list)
    open_text = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    points_earned = Column(Float, default=0.0)

    attempt = relationship("ExamAttemptModel", back_populates="answers")


class ProctoringEventModel(Base):
    __tablename__ = "proctoring_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(PGUUID(as_uuid=True), ForeignKey("exam_attempts.id"), nullable=False)
    event_type = Column(Enum(ProctoringEventType), nullable=False)
    confidence = Column(Float, nullable=False)
    event_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attempt = relationship("ExamAttemptModel", back_populates="proctoring_events")


class AttemptSnapshotModel(Base):
    __tablename__ = "attempt_snapshots"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(PGUUID(as_uuid=True), ForeignKey("exam_attempts.id"), nullable=False)
    snapshot_type = Column(Enum(SnapshotType), nullable=False)
    image_url = Column(String(512), nullable=False)
    captured_at = Column(DateTime(timezone=True), server_default=func.now())

    attempt = relationship("ExamAttemptModel", back_populates="snapshots")


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _apply_schema_updates()


def _apply_schema_updates():
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "exams" in table_names:
        exam_columns = {column["name"] for column in inspector.get_columns("exams")}
        with engine.begin() as connection:
            if "max_attempts" not in exam_columns:
                connection.execute(
                    text("ALTER TABLE exams ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 1")
                )
            if "attempt_policy" not in exam_columns:
                connection.execute(
                    text(
                        "ALTER TABLE exams ADD COLUMN attempt_policy "
                        "VARCHAR(20) NOT NULL DEFAULT 'flexible'"
                    )
                )
            if "require_camera" not in exam_columns:
                connection.execute(
                    text(
                        "ALTER TABLE exams ADD COLUMN require_camera "
                        "BOOLEAN NOT NULL DEFAULT TRUE"
                    )
                )
            if "require_attempt_video" not in exam_columns:
                connection.execute(
                    text(
                        "ALTER TABLE exams ADD COLUMN require_attempt_video "
                        "BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )
            if "proctoring_sensitivity" not in exam_columns:
                connection.execute(
                    text(
                        "ALTER TABLE exams ADD COLUMN proctoring_sensitivity "
                        "DOUBLE PRECISION NOT NULL DEFAULT 0.4"
                    )
                )
            if "attempt_cooldown_enabled" not in exam_columns:
                connection.execute(
                    text(
                        "ALTER TABLE exams ADD COLUMN attempt_cooldown_enabled "
                        "BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )
            if "attempt_cooldown_seconds" not in exam_columns:
                connection.execute(
                    text(
                        "ALTER TABLE exams ADD COLUMN attempt_cooldown_seconds "
                        "INTEGER NOT NULL DEFAULT 0"
                    )
                )
            if "starts_at" not in exam_columns:
                connection.execute(
                    text("ALTER TABLE exams ADD COLUMN starts_at TIMESTAMPTZ")
                )
                connection.execute(
                    text(
                        "UPDATE exams SET starts_at = COALESCE(created_at, NOW() - INTERVAL '1 day') "
                        "WHERE starts_at IS NULL"
                    )
                )
                connection.execute(
                    text("ALTER TABLE exams ALTER COLUMN starts_at SET NOT NULL")
                )

    if "exam_attempts" not in table_names:
        return

    attempt_columns = {column["name"] for column in inspector.get_columns("exam_attempts")}
    with engine.begin() as connection:
        if "invitee_full_name" not in attempt_columns:
            connection.execute(
                text(
                    "ALTER TABLE exam_attempts "
                    "ADD COLUMN invitee_full_name VARCHAR(255) NOT NULL DEFAULT ''"
                )
            )
        if "attempt_number" not in attempt_columns:
            connection.execute(
                text(
                    "ALTER TABLE exam_attempts "
                    "ADD COLUMN attempt_number INTEGER NOT NULL DEFAULT 1"
                )
            )
        if "attempt_video_url" not in attempt_columns:
            connection.execute(
                text("ALTER TABLE exam_attempts ADD COLUMN attempt_video_url VARCHAR(512)")
            )
        if "current_question_index" not in attempt_columns:
            connection.execute(
                text(
                    "ALTER TABLE exam_attempts "
                    "ADD COLUMN current_question_index INTEGER NOT NULL DEFAULT 0"
                )
            )
        if "locked_question_ids" not in attempt_columns:
            connection.execute(
                text("ALTER TABLE exam_attempts ADD COLUMN locked_question_ids JSON DEFAULT '[]'")
            )
        if "current_question_started_at" not in attempt_columns:
            connection.execute(
                text("ALTER TABLE exam_attempts ADD COLUMN current_question_started_at TIMESTAMP WITH TIME ZONE")
            )
        unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("exam_attempts")
        }
        for constraint_name in unique_constraints:
            if constraint_name and "invitation_id" in constraint_name:
                connection.execute(
                    text(f'ALTER TABLE exam_attempts DROP CONSTRAINT IF EXISTS "{constraint_name}"')
                )
                break
        else:
            connection.execute(
                text(
                    "ALTER TABLE exam_attempts "
                    "DROP CONSTRAINT IF EXISTS exam_attempts_invitation_id_key"
                )
            )

    if "exam_invitations" in table_names:
        invitation_columns = {
            column["name"] for column in inspector.get_columns("exam_invitations")
        }
        with engine.begin() as connection:
            if "decision_deadline_at" not in invitation_columns:
                connection.execute(
                    text(
                        "ALTER TABLE exam_invitations "
                        "ADD COLUMN decision_deadline_at TIMESTAMP WITH TIME ZONE"
                    )
                )
