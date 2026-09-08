from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.application.attempt_access import count_finished_attempts, get_in_progress_attempt
from app.domain.entities import (
    Answer,
    AttemptSnapshot,
    Exam,
    ExamAttempt,
    ExamInvitation,
    ExamQuestionConfig,
    ProctoringEvent,
    Question,
    QuestionBank,
    QuestionOption,
    Topic,
    User,
)
from app.domain.enums import AttemptPolicy, AttemptStatus, SnapshotType
from app.domain.repositories import (
    AnswerRepository,
    AttemptSnapshotRepository,
    AttemptRepository,
    ExamRepository,
    InvitationRepository,
    ProctoringRepository,
    QuestionBankRepository,
    QuestionRepository,
    TopicRepository,
    UserRepository,
)
from app.infrastructure.database.models import (
    AnswerModel,
    AttemptSnapshotModel,
    ExamAttemptModel,
    ExamInvitationModel,
    ExamModel,
    ProctoringEventModel,
    QuestionBankModel,
    QuestionModel,
    QuestionOptionModel,
    TopicModel,
    UserModel,
)


def _user_to_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        hashed_password=model.hashed_password,
        full_name=model.full_name,
        is_active=model.is_active,
        mfa_enabled=model.mfa_enabled,
        mfa_secret=model.mfa_secret,
        created_at=model.created_at,
    )


def _question_option_to_entity(model: QuestionOptionModel) -> QuestionOption:
    return QuestionOption(
        id=model.id,
        question_id=model.question_id,
        text=model.text,
        is_correct=model.is_correct,
        order=model.order,
    )


def _question_to_entity(model: QuestionModel) -> Question:
    return Question(
        id=model.id,
        text=model.text,
        question_type=model.question_type,
        topic_id=model.topic_id,
        topic_name=model.topic.name if model.topic else None,
        time_seconds=model.time_seconds,
        image_url=model.image_url,
        owner_id=model.owner_id,
        options=[_question_option_to_entity(o) for o in model.options],
        created_at=model.created_at,
    )


def _topic_to_entity(model: TopicModel) -> Topic:
    return Topic(
        id=model.id,
        name=model.name,
        description=model.description,
        owner_id=model.owner_id,
        created_at=model.created_at,
    )


def _bank_to_entity(model: QuestionBankModel, include_questions: bool = False) -> QuestionBank:
    questions = [_question_to_entity(q) for q in model.questions] if include_questions else []
    return QuestionBank(
        id=model.id,
        name=model.name,
        description=model.description,
        owner_id=model.owner_id,
        questions=questions,
        created_at=model.created_at,
    )


def _exam_to_entity(model: ExamModel) -> Exam:
    configs = [
        ExamQuestionConfig(
            question_id=UUID(c["question_id"]) if isinstance(c["question_id"], str) else c["question_id"],
            order=c["order"],
            points=c["points"],
            time_seconds=c["time_seconds"],
        )
        for c in (model.question_configs or [])
    ]
    selected_ids = [UUID(i) if isinstance(i, str) else i for i in (model.selected_question_ids or [])]
    return Exam(
        id=model.id,
        title=model.title,
        description=model.description,
        owner_id=model.owner_id,
        question_bank_id=model.question_bank_id,
        mode=model.mode,
        status=model.status,
        total_score=model.total_score,
        question_count=model.question_count,
        closes_at=model.closes_at,
        starts_at=model.starts_at,
        random_selection=model.random_selection,
        enforce_question_time=model.enforce_question_time,
        require_camera=model.require_camera,
        require_attempt_video=model.require_attempt_video,
        max_attempts=model.max_attempts,
        attempt_policy=AttemptPolicy(model.attempt_policy),
        proctoring_sensitivity=model.proctoring_sensitivity,
        attempt_cooldown_enabled=model.attempt_cooldown_enabled,
        attempt_cooldown_seconds=model.attempt_cooldown_seconds,
        selected_question_ids=selected_ids,
        question_configs=configs,
        created_at=model.created_at,
    )


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: Session):
        self._session = session

    def create(self, user: User) -> User:
        model = UserModel(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
            full_name=user.full_name,
            is_active=user.is_active,
            mfa_enabled=user.mfa_enabled,
            mfa_secret=user.mfa_secret,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return _user_to_entity(model)

    def get_by_id(self, user_id: UUID) -> User | None:
        model = self._session.query(UserModel).filter(UserModel.id == user_id).first()
        return _user_to_entity(model) if model else None

    def get_by_email(self, email: str) -> User | None:
        model = self._session.query(UserModel).filter(UserModel.email == email).first()
        return _user_to_entity(model) if model else None

    def update(self, user: User) -> User:
        model = self._session.query(UserModel).filter(UserModel.id == user.id).first()
        if not model:
            raise ValueError("User not found")
        model.email = user.email
        model.hashed_password = user.hashed_password
        model.full_name = user.full_name
        model.is_active = user.is_active
        model.mfa_enabled = user.mfa_enabled
        model.mfa_secret = user.mfa_secret
        self._session.commit()
        self._session.refresh(model)
        return _user_to_entity(model)


class SQLAlchemyQuestionBankRepository(QuestionBankRepository):
    def __init__(self, session: Session):
        self._session = session

    def create(self, bank: QuestionBank) -> QuestionBank:
        model = QuestionBankModel(
            id=bank.id,
            name=bank.name,
            description=bank.description,
            owner_id=bank.owner_id,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return _bank_to_entity(model)

    def get_by_id(self, bank_id: UUID) -> QuestionBank | None:
        model = self._session.query(QuestionBankModel).filter(QuestionBankModel.id == bank_id).first()
        return _bank_to_entity(model, include_questions=True) if model else None

    def list_by_owner(self, owner_id: UUID) -> list[QuestionBank]:
        models = self._session.query(QuestionBankModel).filter(QuestionBankModel.owner_id == owner_id).all()
        return [_bank_to_entity(m) for m in models]

    def update(self, bank: QuestionBank) -> QuestionBank:
        model = self._session.query(QuestionBankModel).filter(QuestionBankModel.id == bank.id).first()
        if not model:
            raise ValueError("Question bank not found")
        model.name = bank.name
        model.description = bank.description
        self._session.commit()
        self._session.refresh(model)
        return _bank_to_entity(model)

    def delete(self, bank_id: UUID) -> bool:
        model = self._session.query(QuestionBankModel).filter(QuestionBankModel.id == bank_id).first()
        if not model:
            return False
        self._session.delete(model)
        self._session.commit()
        return True


class SQLAlchemyTopicRepository(TopicRepository):
    def __init__(self, session: Session):
        self._session = session

    def create(self, topic: Topic) -> Topic:
        model = TopicModel(
            id=topic.id,
            name=topic.name,
            description=topic.description,
            owner_id=topic.owner_id,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return _topic_to_entity(model)

    def get_by_id(self, topic_id: UUID) -> Topic | None:
        model = self._session.query(TopicModel).filter(TopicModel.id == topic_id).first()
        return _topic_to_entity(model) if model else None

    def list_by_owner(self, owner_id: UUID) -> list[Topic]:
        models = (
            self._session.query(TopicModel)
            .filter(TopicModel.owner_id == owner_id)
            .order_by(TopicModel.name)
            .all()
        )
        return [_topic_to_entity(m) for m in models]

    def update(self, topic: Topic) -> Topic:
        model = self._session.query(TopicModel).filter(TopicModel.id == topic.id).first()
        if not model:
            raise ValueError("Topic not found")
        model.name = topic.name
        model.description = topic.description
        self._session.commit()
        self._session.refresh(model)
        return _topic_to_entity(model)

    def delete(self, topic_id: UUID) -> bool:
        model = self._session.query(TopicModel).filter(TopicModel.id == topic_id).first()
        if not model:
            return False
        self._session.delete(model)
        self._session.commit()
        return True


class SQLAlchemyQuestionRepository(QuestionRepository):
    def __init__(self, session: Session):
        self._session = session

    def create(self, question: Question) -> Question:
        model = QuestionModel(
            id=question.id,
            bank_id=question.owner_id,  # will be set via bank
            text=question.text,
            question_type=question.question_type,
            topic_id=question.topic_id,
            time_seconds=question.time_seconds,
            image_url=question.image_url,
            owner_id=question.owner_id,
        )
        self._session.add(model)
        self._session.flush()
        for opt in question.options:
            opt_model = QuestionOptionModel(
                id=opt.id,
                question_id=model.id,
                text=opt.text,
                is_correct=opt.is_correct,
                order=opt.order,
            )
            self._session.add(opt_model)
        self._session.commit()
        self._session.refresh(model)
        return _question_to_entity(model)

    def create_in_bank(self, bank_id: UUID, question: Question) -> Question:
        model = QuestionModel(
            id=question.id,
            bank_id=bank_id,
            text=question.text,
            question_type=question.question_type,
            topic_id=question.topic_id,
            time_seconds=question.time_seconds,
            image_url=question.image_url,
            owner_id=question.owner_id,
        )
        self._session.add(model)
        self._session.flush()
        for opt in question.options:
            opt_model = QuestionOptionModel(
                id=opt.id,
                question_id=model.id,
                text=opt.text,
                is_correct=opt.is_correct,
                order=opt.order,
            )
            self._session.add(opt_model)
        self._session.commit()
        self._session.refresh(model)
        return _question_to_entity(model)

    def get_by_id(self, question_id: UUID) -> Question | None:
        model = self._session.query(QuestionModel).filter(QuestionModel.id == question_id).first()
        return _question_to_entity(model) if model else None

    def get_by_id_in_bank(self, bank_id: UUID, question_id: UUID) -> Question | None:
        model = (
            self._session.query(QuestionModel)
            .filter(QuestionModel.bank_id == bank_id, QuestionModel.id == question_id)
            .first()
        )
        return _question_to_entity(model) if model else None

    def list_by_bank(self, bank_id: UUID) -> list[Question]:
        models = (
            self._session.query(QuestionModel)
            .filter(QuestionModel.bank_id == bank_id)
            .order_by(QuestionModel.created_at)
            .all()
        )
        return [_question_to_entity(m) for m in models]

    def _bank_questions_query(self, bank_id: UUID, search: str | None = None):
        query = self._session.query(QuestionModel).filter(QuestionModel.bank_id == bank_id)
        normalized = (search or "").strip()
        if not normalized:
            return query

        term = f"%{normalized}%"
        option_match = exists(
            select(1).where(
                QuestionOptionModel.question_id == QuestionModel.id,
                QuestionOptionModel.text.ilike(term),
            )
        )
        topic_match = exists(
            select(1).where(
                TopicModel.id == QuestionModel.topic_id,
                TopicModel.name.ilike(term),
            )
        )
        return query.filter(
            or_(
                QuestionModel.text.ilike(term),
                topic_match,
                option_match,
            )
        )

    def count_by_bank(self, bank_id: UUID, search: str | None = None) -> int:
        return self._bank_questions_query(bank_id, search).count()

    def list_by_bank_paginated(
        self, bank_id: UUID, page: int, page_size: int, search: str | None = None
    ) -> list[Question]:
        offset = (page - 1) * page_size
        models = (
            self._bank_questions_query(bank_id, search)
            .order_by(QuestionModel.created_at)
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return [_question_to_entity(m) for m in models]

    def list_by_ids(self, question_ids: list[UUID]) -> list[Question]:
        if not question_ids:
            return []
        models = self._session.query(QuestionModel).filter(QuestionModel.id.in_(question_ids)).all()
        return [_question_to_entity(m) for m in models]

    def update(self, question: Question) -> Question:
        model = self._session.query(QuestionModel).filter(QuestionModel.id == question.id).first()
        if not model:
            raise ValueError("Question not found")
        model.text = question.text
        model.question_type = question.question_type
        model.topic_id = question.topic_id
        model.time_seconds = question.time_seconds
        model.image_url = question.image_url
        self._session.query(QuestionOptionModel).filter(QuestionOptionModel.question_id == question.id).delete()
        for opt in question.options:
            opt_model = QuestionOptionModel(
                id=opt.id,
                question_id=model.id,
                text=opt.text,
                is_correct=opt.is_correct,
                order=opt.order,
            )
            self._session.add(opt_model)
        self._session.commit()
        self._session.refresh(model)
        return _question_to_entity(model)

    def delete(self, question_id: UUID) -> bool:
        model = self._session.query(QuestionModel).filter(QuestionModel.id == question_id).first()
        if not model:
            return False
        self._session.delete(model)
        self._session.commit()
        return True


class SQLAlchemyExamRepository(ExamRepository):
    def __init__(self, session: Session):
        self._session = session

    def create(self, exam: Exam) -> Exam:
        model = ExamModel(
            id=exam.id,
            title=exam.title,
            description=exam.description,
            owner_id=exam.owner_id,
            question_bank_id=exam.question_bank_id,
            mode=exam.mode,
            status=exam.status,
            total_score=exam.total_score,
            question_count=exam.question_count,
            closes_at=exam.closes_at,
            starts_at=exam.starts_at,
            random_selection=exam.random_selection,
            enforce_question_time=exam.enforce_question_time,
            require_camera=exam.require_camera,
            require_attempt_video=exam.require_attempt_video,
            max_attempts=exam.max_attempts,
            attempt_policy=exam.attempt_policy.value,
            proctoring_sensitivity=exam.proctoring_sensitivity,
            attempt_cooldown_enabled=exam.attempt_cooldown_enabled,
            attempt_cooldown_seconds=exam.attempt_cooldown_seconds,
            selected_question_ids=[str(i) for i in exam.selected_question_ids],
            question_configs=[
                {
                    "question_id": str(c.question_id),
                    "order": c.order,
                    "points": c.points,
                    "time_seconds": c.time_seconds,
                }
                for c in exam.question_configs
            ],
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return _exam_to_entity(model)

    def get_by_id(self, exam_id: UUID) -> Exam | None:
        model = self._session.query(ExamModel).filter(ExamModel.id == exam_id).first()
        return _exam_to_entity(model) if model else None

    def list_by_owner(self, owner_id: UUID) -> list[Exam]:
        models = self._session.query(ExamModel).filter(ExamModel.owner_id == owner_id).all()
        return [_exam_to_entity(m) for m in models]

    def count_by_question_bank(self, question_bank_id: UUID) -> int:
        return (
            self._session.query(ExamModel)
            .filter(ExamModel.question_bank_id == question_bank_id)
            .count()
        )

    def count_exams_using_question(self, question_id: UUID) -> int:
        qid = str(question_id)
        models = self._session.query(ExamModel).all()
        return sum(1 for m in models if qid in (m.selected_question_ids or []))

    def update(self, exam: Exam) -> Exam:
        model = self._session.query(ExamModel).filter(ExamModel.id == exam.id).first()
        if not model:
            raise ValueError("Exam not found")
        model.title = exam.title
        model.description = exam.description
        model.mode = exam.mode
        model.status = exam.status
        model.total_score = exam.total_score
        model.question_count = exam.question_count
        model.question_bank_id = exam.question_bank_id
        model.closes_at = exam.closes_at
        model.starts_at = exam.starts_at
        model.random_selection = exam.random_selection
        model.enforce_question_time = exam.enforce_question_time
        model.require_camera = exam.require_camera
        model.require_attempt_video = exam.require_attempt_video
        model.max_attempts = exam.max_attempts
        model.attempt_policy = exam.attempt_policy.value
        model.proctoring_sensitivity = exam.proctoring_sensitivity
        model.attempt_cooldown_enabled = exam.attempt_cooldown_enabled
        model.attempt_cooldown_seconds = exam.attempt_cooldown_seconds
        model.selected_question_ids = [str(i) for i in exam.selected_question_ids]
        model.question_configs = [
            {
                "question_id": str(c.question_id),
                "order": c.order,
                "points": c.points,
                "time_seconds": c.time_seconds,
            }
            for c in exam.question_configs
        ]
        self._session.commit()
        self._session.refresh(model)
        return _exam_to_entity(model)

    def delete(self, exam_id: UUID) -> bool:
        model = self._session.query(ExamModel).filter(ExamModel.id == exam_id).first()
        if not model:
            return False
        self._session.delete(model)
        self._session.commit()
        return True


class SQLAlchemyInvitationRepository(InvitationRepository):
    def __init__(self, session: Session):
        self._session = session

    def create(self, invitation: ExamInvitation) -> ExamInvitation:
        model = ExamInvitationModel(
            id=invitation.id,
            exam_id=invitation.exam_id,
            invitee_email=invitation.invitee_email,
            token=invitation.token,
            status=invitation.status,
            sent_at=invitation.sent_at,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_entity(model)

    def get_by_id(self, invitation_id: UUID) -> ExamInvitation | None:
        model = self._session.query(ExamInvitationModel).filter(ExamInvitationModel.id == invitation_id).first()
        return self._to_entity(model) if model else None

    def get_by_token(self, token: str) -> ExamInvitation | None:
        model = self._session.query(ExamInvitationModel).filter(ExamInvitationModel.token == token).first()
        return self._to_entity(model) if model else None

    def list_by_exam(self, exam_id: UUID) -> list[ExamInvitation]:
        models = self._session.query(ExamInvitationModel).filter(ExamInvitationModel.exam_id == exam_id).all()
        return [self._to_entity(m) for m in models]

    def get_by_exam_and_email(self, exam_id: UUID, email: str) -> list[ExamInvitation]:
        normalized = email.lower().strip()
        models = (
            self._session.query(ExamInvitationModel)
            .filter(
                ExamInvitationModel.exam_id == exam_id,
                func.lower(ExamInvitationModel.invitee_email) == normalized,
            )
            .all()
        )
        return [self._to_entity(m) for m in models]

    def update(self, invitation: ExamInvitation) -> ExamInvitation:
        model = self._session.query(ExamInvitationModel).filter(ExamInvitationModel.id == invitation.id).first()
        if not model:
            raise ValueError("Invitation not found")
        model.status = invitation.status
        model.sent_at = invitation.sent_at
        model.decision_deadline_at = invitation.decision_deadline_at
        self._session.commit()
        self._session.refresh(model)
        return self._to_entity(model)

    def delete(self, invitation_id: UUID) -> bool:
        model = self._session.query(ExamInvitationModel).filter(ExamInvitationModel.id == invitation_id).first()
        if not model:
            return False
        self._session.delete(model)
        self._session.commit()
        return True

    @staticmethod
    def _to_entity(model: ExamInvitationModel) -> ExamInvitation:
        return ExamInvitation(
            id=model.id,
            exam_id=model.exam_id,
            invitee_email=model.invitee_email,
            token=model.token,
            status=model.status,
            sent_at=model.sent_at,
            decision_deadline_at=model.decision_deadline_at,
            created_at=model.created_at,
        )


def _attempt_configs_from_model(model: ExamAttemptModel) -> list[ExamQuestionConfig]:
    return [
        ExamQuestionConfig(
            question_id=UUID(c["question_id"]) if isinstance(c["question_id"], str) else c["question_id"],
            order=c["order"],
            points=c["points"],
            time_seconds=c["time_seconds"],
        )
        for c in (model.question_configs or [])
    ]


def _attempt_to_entity(model: ExamAttemptModel) -> ExamAttempt:
    selected_ids = [UUID(i) if isinstance(i, str) else i for i in (model.selected_question_ids or [])]
    return ExamAttempt(
        id=model.id,
        invitation_id=model.invitation_id,
        exam_id=model.exam_id,
        status=model.status,
        attempt_number=model.attempt_number,
        invitee_full_name=model.invitee_full_name or "",
        started_at=model.started_at,
        submitted_at=model.submitted_at,
        score=model.score,
        fraud_score=model.fraud_score,
        camera_verified=model.camera_verified,
        attempt_video_url=model.attempt_video_url,
        selected_question_ids=selected_ids,
        question_configs=_attempt_configs_from_model(model),
        current_question_index=model.current_question_index or 0,
        locked_question_ids=[
            UUID(question_id) if isinstance(question_id, str) else question_id
            for question_id in (model.locked_question_ids or [])
        ],
        current_question_started_at=model.current_question_started_at,
    )


class SQLAlchemyAttemptRepository(AttemptRepository):
    def __init__(self, session: Session):
        self._session = session

    def create(self, attempt: ExamAttempt) -> ExamAttempt:
        model = ExamAttemptModel(
            id=attempt.id,
            invitation_id=attempt.invitation_id,
            exam_id=attempt.exam_id,
            status=attempt.status,
            attempt_number=attempt.attempt_number,
            invitee_full_name=attempt.invitee_full_name,
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
            score=attempt.score,
            fraud_score=attempt.fraud_score,
            camera_verified=attempt.camera_verified,
            selected_question_ids=[str(question_id) for question_id in attempt.selected_question_ids],
            question_configs=[
                {
                    "question_id": str(config.question_id),
                    "order": config.order,
                    "points": config.points,
                    "time_seconds": config.time_seconds,
                }
                for config in attempt.question_configs
            ],
            current_question_index=attempt.current_question_index,
            locked_question_ids=[str(question_id) for question_id in attempt.locked_question_ids],
            current_question_started_at=attempt.current_question_started_at,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return _attempt_to_entity(model)

    def get_by_id(self, attempt_id: UUID) -> ExamAttempt | None:
        model = self._session.query(ExamAttemptModel).filter(ExamAttemptModel.id == attempt_id).first()
        return _attempt_to_entity(model) if model else None

    def get_by_invitation(self, invitation_id: UUID) -> ExamAttempt | None:
        in_progress = self.get_in_progress_by_invitation(invitation_id)
        if in_progress:
            return in_progress
        attempts = self.list_by_invitation(invitation_id)
        return attempts[-1] if attempts else None

    def get_in_progress_by_invitation(self, invitation_id: UUID) -> ExamAttempt | None:
        return get_in_progress_attempt(self.list_by_invitation(invitation_id))

    def list_by_invitation(self, invitation_id: UUID) -> list[ExamAttempt]:
        models = (
            self._session.query(ExamAttemptModel)
            .filter(ExamAttemptModel.invitation_id == invitation_id)
            .order_by(ExamAttemptModel.attempt_number.asc())
            .all()
        )
        return [_attempt_to_entity(model) for model in models]

    def list_by_email(self, exam_id: UUID, email: str) -> list[ExamAttempt]:
        normalized = email.lower().strip()
        models = (
            self._session.query(ExamAttemptModel)
            .join(ExamInvitationModel, ExamAttemptModel.invitation_id == ExamInvitationModel.id)
            .filter(
                ExamAttemptModel.exam_id == exam_id,
                func.lower(ExamInvitationModel.invitee_email) == normalized,
            )
            .order_by(ExamAttemptModel.attempt_number.asc())
            .all()
        )
        return [_attempt_to_entity(model) for model in models]

    def count_finished_for_email(self, exam_id: UUID, email: str) -> int:
        return count_finished_attempts(self.list_by_email(exam_id, email))

    def list_by_exam(self, exam_id: UUID) -> list[ExamAttempt]:
        models = self._session.query(ExamAttemptModel).filter(ExamAttemptModel.exam_id == exam_id).all()
        return [_attempt_to_entity(m) for m in models]

    def has_completed_attempt_for_email(self, exam_id: UUID, email: str) -> bool:
        normalized = email.lower().strip()
        completed = (
            self._session.query(ExamAttemptModel)
            .join(ExamInvitationModel, ExamAttemptModel.invitation_id == ExamInvitationModel.id)
            .filter(
                ExamAttemptModel.exam_id == exam_id,
                func.lower(ExamInvitationModel.invitee_email) == normalized,
                ExamAttemptModel.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.TIMED_OUT]),
            )
            .first()
        )
        return completed is not None

    def has_in_progress_attempt_for_email(
        self, exam_id: UUID, email: str, exclude_invitation_id: UUID | None = None
    ) -> bool:
        normalized = email.lower().strip()
        query = (
            self._session.query(ExamAttemptModel)
            .join(ExamInvitationModel, ExamAttemptModel.invitation_id == ExamInvitationModel.id)
            .filter(
                ExamAttemptModel.exam_id == exam_id,
                func.lower(ExamInvitationModel.invitee_email) == normalized,
                ExamAttemptModel.status == AttemptStatus.IN_PROGRESS,
            )
        )
        if exclude_invitation_id:
            query = query.filter(ExamAttemptModel.invitation_id != exclude_invitation_id)
        return query.first() is not None

    def update(self, attempt: ExamAttempt) -> ExamAttempt:
        model = self._session.query(ExamAttemptModel).filter(ExamAttemptModel.id == attempt.id).first()
        if not model:
            raise ValueError("Attempt not found")
        model.status = attempt.status
        model.attempt_number = attempt.attempt_number
        model.invitee_full_name = attempt.invitee_full_name
        model.started_at = attempt.started_at
        model.submitted_at = attempt.submitted_at
        model.score = attempt.score
        model.fraud_score = attempt.fraud_score
        model.camera_verified = attempt.camera_verified
        model.attempt_video_url = attempt.attempt_video_url
        model.selected_question_ids = [str(question_id) for question_id in attempt.selected_question_ids]
        model.question_configs = [
            {
                "question_id": str(config.question_id),
                "order": config.order,
                "points": config.points,
                "time_seconds": config.time_seconds,
            }
            for config in attempt.question_configs
        ]
        model.current_question_index = attempt.current_question_index
        model.locked_question_ids = [str(question_id) for question_id in attempt.locked_question_ids]
        model.current_question_started_at = attempt.current_question_started_at
        self._session.commit()
        self._session.refresh(model)
        return _attempt_to_entity(model)

    def delete(self, attempt_id: UUID) -> bool:
        model = self._session.query(ExamAttemptModel).filter(ExamAttemptModel.id == attempt_id).first()
        if not model:
            return False
        self._session.delete(model)
        self._session.commit()
        return True


class SQLAlchemyAnswerRepository(AnswerRepository):
    def __init__(self, session: Session):
        self._session = session

    def create(self, answer: Answer) -> Answer:
        model = AnswerModel(
            id=answer.id,
            attempt_id=answer.attempt_id,
            question_id=answer.question_id,
            selected_option_ids=[str(i) for i in answer.selected_option_ids],
            open_text=answer.open_text,
            is_correct=answer.is_correct,
            points_earned=answer.points_earned,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_entity(model)

    def get_by_attempt(self, attempt_id: UUID) -> list[Answer]:
        models = self._session.query(AnswerModel).filter(AnswerModel.attempt_id == attempt_id).all()
        return [self._to_entity(m) for m in models]

    def upsert(self, answer: Answer) -> Answer:
        model = (
            self._session.query(AnswerModel)
            .filter(
                AnswerModel.attempt_id == answer.attempt_id,
                AnswerModel.question_id == answer.question_id,
            )
            .first()
        )
        if model:
            model.selected_option_ids = [str(i) for i in answer.selected_option_ids]
            model.open_text = answer.open_text
            model.is_correct = answer.is_correct
            model.points_earned = answer.points_earned
        else:
            model = AnswerModel(
                id=answer.id,
                attempt_id=answer.attempt_id,
                question_id=answer.question_id,
                selected_option_ids=[str(i) for i in answer.selected_option_ids],
                open_text=answer.open_text,
                is_correct=answer.is_correct,
                points_earned=answer.points_earned,
            )
            self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: AnswerModel) -> Answer:
        return Answer(
            id=model.id,
            attempt_id=model.attempt_id,
            question_id=model.question_id,
            selected_option_ids=[UUID(i) if isinstance(i, str) else i for i in (model.selected_option_ids or [])],
            open_text=model.open_text,
            is_correct=model.is_correct,
            points_earned=model.points_earned,
        )


class SQLAlchemyProctoringRepository(ProctoringRepository):
    def __init__(self, session: Session):
        self._session = session

    def create(self, event: ProctoringEvent) -> ProctoringEvent:
        model = ProctoringEventModel(
            id=event.id,
            attempt_id=event.attempt_id,
            event_type=event.event_type,
            confidence=event.confidence,
            event_metadata=event.metadata,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return ProctoringEvent(
            id=model.id,
            attempt_id=model.attempt_id,
            event_type=model.event_type,
            confidence=model.confidence,
            metadata=model.event_metadata or {},
            created_at=model.created_at,
        )

    def list_by_attempt(self, attempt_id: UUID) -> list[ProctoringEvent]:
        models = (
            self._session.query(ProctoringEventModel)
            .filter(ProctoringEventModel.attempt_id == attempt_id)
            .order_by(ProctoringEventModel.created_at)
            .all()
        )
        return [
            ProctoringEvent(
                id=m.id,
                attempt_id=m.attempt_id,
                event_type=m.event_type,
                confidence=m.confidence,
                metadata=m.event_metadata or {},
                created_at=m.created_at,
            )
            for m in models
        ]


class SQLAlchemyAttemptSnapshotRepository(AttemptSnapshotRepository):
    def __init__(self, session: Session):
        self._session = session

    def create(self, snapshot: AttemptSnapshot) -> AttemptSnapshot:
        model = AttemptSnapshotModel(
            id=snapshot.id,
            attempt_id=snapshot.attempt_id,
            snapshot_type=snapshot.snapshot_type,
            image_url=snapshot.image_url,
            captured_at=snapshot.captured_at,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return AttemptSnapshot(
            id=model.id,
            attempt_id=model.attempt_id,
            snapshot_type=model.snapshot_type,
            image_url=model.image_url,
            captured_at=model.captured_at,
        )

    def list_by_attempt(self, attempt_id: UUID) -> list[AttemptSnapshot]:
        models = (
            self._session.query(AttemptSnapshotModel)
            .filter(AttemptSnapshotModel.attempt_id == attempt_id)
            .order_by(AttemptSnapshotModel.captured_at)
            .all()
        )
        return [
            AttemptSnapshot(
                id=m.id,
                attempt_id=m.attempt_id,
                snapshot_type=m.snapshot_type,
                image_url=m.image_url,
                captured_at=m.captured_at,
            )
            for m in models
        ]

    def count_by_type(self, attempt_id: UUID, snapshot_type: SnapshotType) -> int:
        return (
            self._session.query(AttemptSnapshotModel)
            .filter(
                AttemptSnapshotModel.attempt_id == attempt_id,
                AttemptSnapshotModel.snapshot_type == snapshot_type,
            )
            .count()
        )


class SQLAlchemyAttemptSnapshotRepository(AttemptSnapshotRepository):
    def __init__(self, session: Session):
        self._session = session

    def create(self, snapshot: AttemptSnapshot) -> AttemptSnapshot:
        model = AttemptSnapshotModel(
            id=snapshot.id,
            attempt_id=snapshot.attempt_id,
            snapshot_type=snapshot.snapshot_type,
            image_url=snapshot.image_url,
            captured_at=snapshot.captured_at,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return AttemptSnapshot(
            id=model.id,
            attempt_id=model.attempt_id,
            snapshot_type=model.snapshot_type,
            image_url=model.image_url,
            captured_at=model.captured_at,
        )

    def list_by_attempt(self, attempt_id: UUID) -> list[AttemptSnapshot]:
        models = (
            self._session.query(AttemptSnapshotModel)
            .filter(AttemptSnapshotModel.attempt_id == attempt_id)
            .order_by(AttemptSnapshotModel.captured_at)
            .all()
        )
        return [
            AttemptSnapshot(
                id=m.id,
                attempt_id=m.attempt_id,
                snapshot_type=m.snapshot_type,
                image_url=m.image_url,
                captured_at=m.captured_at,
            )
            for m in models
        ]

    def count_by_type(self, attempt_id: UUID, snapshot_type: SnapshotType) -> int:
        return (
            self._session.query(AttemptSnapshotModel)
            .filter(
                AttemptSnapshotModel.attempt_id == attempt_id,
                AttemptSnapshotModel.snapshot_type == snapshot_type,
            )
            .count()
        )
