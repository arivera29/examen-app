from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from uuid import UUID

from app.application.attempt_access import (
    count_finished_attempts,
    get_in_progress_attempt,
    has_exhausted_attempts,
    is_finished_attempt,
    resolve_attempt_start,
)
from app.application.attempt_questions import (
    assign_attempt_questions,
    get_attempt_question_configs,
    get_attempt_question_id_set,
    resolve_attempt_question_configs,
    summarize_attempt_answers,
)
from app.application.exam_timing import get_remaining_seconds, get_total_exam_seconds, is_exam_closed, is_exam_time_expired
from app.application.question_backup import build_backup_payload, parse_backup_payload, parse_question_item
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
from app.domain.enums import (
    AttemptPolicy,
    AttemptStatus,
    ExamStatus,
    InvitationStatus,
    ProctoringEventType,
    QuestionType,
    SnapshotType,
)
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
from app.domain.services import (
    EmailService,
    MfaService,
    PasswordHasher,
    ProctoringService,
    TokenService,
)


logger = logging.getLogger(__name__)


class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class UnauthorizedError(DomainError):
    pass


class ValidationError(DomainError):
    pass


@dataclass
class RegisterUserInput:
    email: str
    password: str
    full_name: str


@dataclass
class LoginInput:
    email: str
    password: str
    mfa_code: str | None = None


class RegisterUserUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
    ):
        self._user_repo = user_repo
        self._password_hasher = password_hasher

    def execute(self, input_data: RegisterUserInput) -> User:
        if self._user_repo.get_by_email(input_data.email):
            raise ValidationError("Email already registered")
        user = User(
            email=input_data.email,
            hashed_password=self._password_hasher.hash(input_data.password),
            full_name=input_data.full_name,
        )
        return self._user_repo.create(user)


class LoginUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
        mfa_service: MfaService,
    ):
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._token_service = token_service
        self._mfa_service = mfa_service

    def execute(self, input_data: LoginInput):
        user = self._user_repo.get_by_email(input_data.email)
        if not user or not self._password_hasher.verify(input_data.password, user.hashed_password):
            raise UnauthorizedError("Invalid credentials")
        if not user.is_active:
            raise UnauthorizedError("Account disabled")
        if user.mfa_enabled:
            if not input_data.mfa_code or not user.mfa_secret:
                raise UnauthorizedError("MFA code required")
            if not self._mfa_service.verify_code(user.mfa_secret, input_data.mfa_code):
                raise UnauthorizedError("Invalid MFA code")
        return self._token_service.create_token_pair(user.id, user.email)


class SetupMfaUseCase:
    def __init__(self, user_repo: UserRepository, mfa_service: MfaService):
        self._user_repo = user_repo
        self._mfa_service = mfa_service

    def execute(self, user_id: UUID) -> dict:
        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        secret = self._mfa_service.generate_secret()
        user.mfa_secret = secret
        self._user_repo.update(user)
        return {
            "secret": secret,
            "provisioning_uri": self._mfa_service.get_provisioning_uri(secret, user.email),
        }


class EnableMfaUseCase:
    def __init__(self, user_repo: UserRepository, mfa_service: MfaService):
        self._user_repo = user_repo
        self._mfa_service = mfa_service

    def execute(self, user_id: UUID, code: str) -> User:
        user = self._user_repo.get_by_id(user_id)
        if not user or not user.mfa_secret:
            raise NotFoundError("MFA not set up")
        if not self._mfa_service.verify_code(user.mfa_secret, code):
            raise ValidationError("Invalid MFA code")
        user.mfa_enabled = True
        return self._user_repo.update(user)


class CreateQuestionBankUseCase:
    def __init__(self, bank_repo: QuestionBankRepository):
        self._bank_repo = bank_repo

    def execute(self, owner_id: UUID, name: str, description: str = "") -> QuestionBank:
        name = name.strip()
        if not name:
            raise ValidationError("Bank name is required")
        bank = QuestionBank(name=name, description=description, owner_id=owner_id)
        return self._bank_repo.create(bank)


class UpdateQuestionBankUseCase:
    def __init__(self, bank_repo: QuestionBankRepository):
        self._bank_repo = bank_repo

    def execute(self, owner_id: UUID, bank_id: UUID, name: str, description: str = "") -> QuestionBank:
        bank = self._bank_repo.get_by_id(bank_id)
        if not bank or bank.owner_id != owner_id:
            raise NotFoundError("Question bank not found")
        name = name.strip()
        if not name:
            raise ValidationError("Bank name is required")
        bank.name = name
        bank.description = description
        return self._bank_repo.update(bank)


class DeleteQuestionBankUseCase:
    def __init__(
        self,
        bank_repo: QuestionBankRepository,
        exam_repo: ExamRepository,
    ):
        self._bank_repo = bank_repo
        self._exam_repo = exam_repo

    def execute(self, owner_id: UUID, bank_id: UUID) -> None:
        bank = self._bank_repo.get_by_id(bank_id)
        if not bank or bank.owner_id != owner_id:
            raise NotFoundError("Question bank not found")

        if self._exam_repo.count_by_question_bank(bank_id) > 0:
            raise ValidationError("No se puede eliminar un banco usado por exámenes")

        if not self._bank_repo.delete(bank_id):
            raise NotFoundError("Question bank not found")


class CreateTopicUseCase:
    def __init__(self, topic_repo: TopicRepository):
        self._topic_repo = topic_repo

    def execute(self, owner_id: UUID, name: str, description: str = "") -> Topic:
        name = name.strip()
        if not name:
            raise ValidationError("Topic name is required")
        topic = Topic(name=name, description=description, owner_id=owner_id)
        return self._topic_repo.create(topic)


class UpdateTopicUseCase:
    def __init__(self, topic_repo: TopicRepository):
        self._topic_repo = topic_repo

    def execute(self, owner_id: UUID, topic_id: UUID, name: str, description: str = "") -> Topic:
        topic = self._topic_repo.get_by_id(topic_id)
        if not topic or topic.owner_id != owner_id:
            raise NotFoundError("Topic not found")
        name = name.strip()
        if not name:
            raise ValidationError("Topic name is required")
        topic.name = name
        topic.description = description
        return self._topic_repo.update(topic)


class DeleteTopicUseCase:
    def __init__(self, topic_repo: TopicRepository):
        self._topic_repo = topic_repo

    def execute(self, owner_id: UUID, topic_id: UUID) -> None:
        topic = self._topic_repo.get_by_id(topic_id)
        if not topic or topic.owner_id != owner_id:
            raise NotFoundError("Topic not found")
        self._topic_repo.delete(topic_id)


class CreateQuestionUseCase:
    def __init__(
        self,
        bank_repo: QuestionBankRepository,
        question_repo: QuestionRepository,
        topic_repo: TopicRepository,
    ):
        self._bank_repo = bank_repo
        self._question_repo = question_repo
        self._topic_repo = topic_repo

    def execute(
        self,
        owner_id: UUID,
        bank_id: UUID,
        text: str,
        question_type: QuestionType,
        time_seconds: int,
        options: list[dict],
        topic_id: UUID | None = None,
        image_url: str | None = None,
    ) -> Question:
        bank = self._bank_repo.get_by_id(bank_id)
        if not bank or bank.owner_id != owner_id:
            raise NotFoundError("Question bank not found")
        if topic_id:
            topic = self._topic_repo.get_by_id(topic_id)
            if not topic or topic.owner_id != owner_id:
                raise NotFoundError("Topic not found")
        if question_type != QuestionType.OPEN and not options:
            raise ValidationError("Options required for non-open questions")
        question_options = [
            QuestionOption(text=o["text"], is_correct=o.get("is_correct", False), order=i)
            for i, o in enumerate(options)
        ]
        question = Question(
            text=text,
            question_type=question_type,
            topic_id=topic_id,
            time_seconds=time_seconds,
            owner_id=owner_id,
            image_url=image_url,
            options=question_options,
        )
        return self._question_repo.create_in_bank(bank_id, question)


class UpdateQuestionUseCase:
    def __init__(
        self,
        bank_repo: QuestionBankRepository,
        question_repo: QuestionRepository,
        topic_repo: TopicRepository,
    ):
        self._bank_repo = bank_repo
        self._question_repo = question_repo
        self._topic_repo = topic_repo

    def execute(
        self,
        owner_id: UUID,
        bank_id: UUID,
        question_id: UUID,
        text: str,
        question_type: QuestionType,
        time_seconds: int,
        options: list[dict],
        topic_id: UUID | None = None,
        image_url: str | None = None,
    ) -> Question:
        bank = self._bank_repo.get_by_id(bank_id)
        if not bank or bank.owner_id != owner_id:
            raise NotFoundError("Question bank not found")

        question = self._question_repo.get_by_id_in_bank(bank_id, question_id)
        if not question or question.owner_id != owner_id:
            raise NotFoundError("Question not found")

        if topic_id:
            topic = self._topic_repo.get_by_id(topic_id)
            if not topic or topic.owner_id != owner_id:
                raise NotFoundError("Topic not found")

        if question_type != QuestionType.OPEN and not options:
            raise ValidationError("Options required for non-open questions")

        question.text = text
        question.question_type = question_type
        question.topic_id = topic_id
        question.time_seconds = time_seconds
        if image_url is not None:
            question.image_url = image_url
        question.options = [
            QuestionOption(text=o["text"], is_correct=o.get("is_correct", False), order=i)
            for i, o in enumerate(options)
        ]
        return self._question_repo.update(question)


class DeleteQuestionUseCase:
    def __init__(
        self,
        bank_repo: QuestionBankRepository,
        question_repo: QuestionRepository,
        exam_repo: ExamRepository,
    ):
        self._bank_repo = bank_repo
        self._question_repo = question_repo
        self._exam_repo = exam_repo

    def execute(self, owner_id: UUID, bank_id: UUID, question_id: UUID) -> None:
        bank = self._bank_repo.get_by_id(bank_id)
        if not bank or bank.owner_id != owner_id:
            raise NotFoundError("Question bank not found")

        question = self._question_repo.get_by_id_in_bank(bank_id, question_id)
        if not question or question.owner_id != owner_id:
            raise NotFoundError("Question not found")

        if self._exam_repo.count_exams_using_question(question_id) > 0:
            raise ValidationError("No se puede eliminar una pregunta usada en exámenes")

        if not self._question_repo.delete(question_id):
            raise NotFoundError("Question not found")


class DuplicateQuestionUseCase:
    def __init__(
        self,
        bank_repo: QuestionBankRepository,
        question_repo: QuestionRepository,
        upload_dir: str,
    ):
        self._bank_repo = bank_repo
        self._question_repo = question_repo
        self._upload_dir = upload_dir

    def execute(self, owner_id: UUID, bank_id: UUID, question_id: UUID) -> Question:
        from app.infrastructure.services.upload_cleanup import copy_uploaded_file

        bank = self._bank_repo.get_by_id(bank_id)
        if not bank or bank.owner_id != owner_id:
            raise NotFoundError("Question bank not found")

        source = self._question_repo.get_by_id_in_bank(bank_id, question_id)
        if not source or source.owner_id != owner_id:
            raise NotFoundError("Question not found")

        image_url = copy_uploaded_file(self._upload_dir, source.image_url)

        duplicate = Question(
            text=f"{source.text} (copia)",
            question_type=source.question_type,
            topic_id=source.topic_id,
            time_seconds=source.time_seconds,
            owner_id=owner_id,
            image_url=image_url,
            options=[
                QuestionOption(text=opt.text, is_correct=opt.is_correct, order=opt.order)
                for opt in source.options
            ],
        )
        return self._question_repo.create_in_bank(bank_id, duplicate)


class ExportQuestionBankBackupUseCase:
    def __init__(
        self,
        bank_repo: QuestionBankRepository,
        question_repo: QuestionRepository,
    ):
        self._bank_repo = bank_repo
        self._question_repo = question_repo

    def execute(self, owner_id: UUID, bank_id: UUID) -> dict:
        bank = self._bank_repo.get_by_id(bank_id)
        if not bank or bank.owner_id != owner_id:
            raise NotFoundError("Question bank not found")
        questions = self._question_repo.list_by_bank(bank_id)
        return build_backup_payload(bank, questions)


class ExportQuestionBankExcelUseCase:
    def __init__(
        self,
        bank_repo: QuestionBankRepository,
        question_repo: QuestionRepository,
    ):
        self._bank_repo = bank_repo
        self._question_repo = question_repo

    def execute(self, owner_id: UUID, bank_id: UUID) -> tuple[bytes, str]:
        from app.application.question_bank_export import build_export_filename, build_question_bank_workbook
        from app.application.question_backup import build_backup_payload

        bank = self._bank_repo.get_by_id(bank_id)
        if not bank or bank.owner_id != owner_id:
            raise NotFoundError("Question bank not found")

        questions = self._question_repo.list_by_bank(bank_id)
        payload = build_backup_payload(bank, questions)
        payload["bank_description"] = bank.description
        payload["total_questions"] = len(questions)
        content = build_question_bank_workbook(payload)
        filename = build_export_filename(payload)
        return content, filename


class RestoreQuestionBankBackupUseCase:
    def __init__(
        self,
        bank_repo: QuestionBankRepository,
        question_repo: QuestionRepository,
        topic_repo: TopicRepository,
        exam_repo: ExamRepository,
    ):
        self._bank_repo = bank_repo
        self._question_repo = question_repo
        self._topic_repo = topic_repo
        self._exam_repo = exam_repo

    def execute(
        self,
        owner_id: UUID,
        bank_id: UUID,
        backup_data: dict,
        mode: str = "append",
    ) -> dict:
        if mode not in ("append", "replace"):
            raise ValidationError("Modo de restauración inválido")

        bank = self._bank_repo.get_by_id(bank_id)
        if not bank or bank.owner_id != owner_id:
            raise NotFoundError("Question bank not found")

        try:
            raw_questions = parse_backup_payload(backup_data)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        deleted_count = 0
        if mode == "replace":
            for question in self._question_repo.list_by_bank(bank_id):
                if self._exam_repo.count_exams_using_question(question.id) == 0:
                    self._question_repo.delete(question.id)
                    deleted_count += 1

        imported_count = 0
        errors: list[str] = []
        topic_cache: dict[str, UUID | None] = {"": None}

        for index, raw_item in enumerate(raw_questions, start=1):
            try:
                item = parse_question_item(raw_item)
            except ValueError as exc:
                errors.append(f"Pregunta {index}: {exc}")
                continue

            if item["question_type"] != QuestionType.OPEN and not item["options"]:
                errors.append(f"Pregunta {index}: se requieren opciones")
                continue

            topic_id = self._resolve_topic_id(owner_id, item["topic_name"], topic_cache)
            question_options = [
                QuestionOption(text=o["text"], is_correct=o.get("is_correct", False), order=i)
                for i, o in enumerate(item["options"])
            ]
            question = Question(
                text=item["text"],
                question_type=item["question_type"],
                topic_id=topic_id,
                time_seconds=item["time_seconds"],
                owner_id=owner_id,
                image_url=None,
                options=question_options,
            )
            self._question_repo.create_in_bank(bank_id, question)
            imported_count += 1

        if imported_count == 0 and errors:
            raise ValidationError(errors[0])

        return {
            "imported_count": imported_count,
            "deleted_count": deleted_count,
            "skipped_count": len(errors),
            "errors": errors,
        }

    def _resolve_topic_id(
        self,
        owner_id: UUID,
        topic_name: str | None,
        cache: dict[str, UUID | None],
    ) -> UUID | None:
        if not topic_name:
            return None
        key = topic_name.lower()
        if key in cache:
            return cache[key]
        topics = self._topic_repo.list_by_owner(owner_id)
        for topic in topics:
            if topic.name.lower() == key:
                cache[key] = topic.id
                return topic.id
        created = self._topic_repo.create(Topic(name=topic_name, owner_id=owner_id))
        cache[key] = created.id
        return created.id


class CreateExamUseCase:
    def __init__(
        self,
        exam_repo: ExamRepository,
        bank_repo: QuestionBankRepository,
        question_repo: QuestionRepository,
    ):
        self._exam_repo = exam_repo
        self._bank_repo = bank_repo
        self._question_repo = question_repo

    def execute(self, owner_id: UUID, exam_data: dict) -> Exam:
        bank = self._bank_repo.get_by_id(exam_data["question_bank_id"])
        if not bank or bank.owner_id != owner_id:
            raise NotFoundError("Question bank not found")

        bank_questions = self._question_repo.list_by_bank(bank.id)
        if len(bank_questions) < exam_data["question_count"]:
            raise ValidationError("Not enough questions in bank")

        if exam_data.get("random_selection", True):
            selected = []
            configs = []
        else:
            selected_ids = exam_data.get("selected_question_ids", [])
            if len(selected_ids) != exam_data["question_count"]:
                raise ValidationError("Must select exact question count")
            selected = self._question_repo.list_by_ids(selected_ids)
            points_per_question = exam_data["total_score"] / exam_data["question_count"]
            configs = [
                ExamQuestionConfig(
                    question_id=q.id,
                    order=i,
                    points=points_per_question,
                    time_seconds=q.time_seconds,
                )
                for i, q in enumerate(selected)
            ]

        closes_at = exam_data["closes_at"]
        if closes_at.tzinfo is None:
            closes_at = closes_at.replace(tzinfo=timezone.utc)
        if closes_at <= datetime.now(timezone.utc):
            raise ValidationError("Close date must be in the future")

        exam = Exam(
            title=exam_data["title"],
            description=exam_data.get("description", ""),
            owner_id=owner_id,
            question_bank_id=bank.id,
            mode=exam_data["mode"],
            total_score=exam_data["total_score"],
            question_count=exam_data["question_count"],
            closes_at=closes_at,
            random_selection=exam_data.get("random_selection", True),
            enforce_question_time=exam_data.get("enforce_question_time", False),
            require_attempt_video=exam_data.get("require_attempt_video", False),
            max_attempts=exam_data.get("max_attempts", 1),
            attempt_policy=exam_data.get("attempt_policy", AttemptPolicy.FLEXIBLE),
            selected_question_ids=[q.id for q in selected],
            question_configs=configs,
        )
        return self._exam_repo.create(exam)


class UpdateExamUseCase:
    def __init__(
        self,
        exam_repo: ExamRepository,
        bank_repo: QuestionBankRepository,
        question_repo: QuestionRepository,
        attempt_repo: AttemptRepository,
    ):
        self._exam_repo = exam_repo
        self._bank_repo = bank_repo
        self._question_repo = question_repo
        self._attempt_repo = attempt_repo

    def execute(self, owner_id: UUID, exam_id: UUID, exam_data: dict) -> Exam:
        exam = self._exam_repo.get_by_id(exam_id)
        if not exam or exam.owner_id != owner_id:
            raise NotFoundError("Exam not found")

        attempts = self._attempt_repo.list_by_exam(exam_id)
        has_attempts = len(attempts) > 0

        if has_attempts:
            exam.title = exam_data["title"]
            exam.description = exam_data.get("description", "")
            return self._exam_repo.update(exam)

        bank = self._bank_repo.get_by_id(exam_data["question_bank_id"])
        if not bank or bank.owner_id != owner_id:
            raise NotFoundError("Question bank not found")

        bank_questions = self._question_repo.list_by_bank(bank.id)
        if len(bank_questions) < exam_data["question_count"]:
            raise ValidationError("Not enough questions in bank")

        if exam_data.get("random_selection", True):
            selected = []
            configs = []
        else:
            selected_ids = exam_data.get("selected_question_ids", [])
            if len(selected_ids) != exam_data["question_count"]:
                raise ValidationError("Must select exact question count")
            selected = self._question_repo.list_by_ids(selected_ids)
            points_per_question = exam_data["total_score"] / exam_data["question_count"]
            configs = [
                ExamQuestionConfig(
                    question_id=q.id,
                    order=i,
                    points=points_per_question,
                    time_seconds=q.time_seconds,
                )
                for i, q in enumerate(selected)
            ]

        closes_at = exam_data["closes_at"]
        if closes_at.tzinfo is None:
            closes_at = closes_at.replace(tzinfo=timezone.utc)
        if closes_at <= datetime.now(timezone.utc):
            raise ValidationError("Close date must be in the future")

        exam.title = exam_data["title"]
        exam.description = exam_data.get("description", "")
        exam.question_bank_id = bank.id
        exam.mode = exam_data["mode"]
        exam.total_score = exam_data["total_score"]
        exam.question_count = exam_data["question_count"]
        exam.closes_at = closes_at
        exam.random_selection = exam_data.get("random_selection", True)
        exam.enforce_question_time = exam_data.get("enforce_question_time", False)
        exam.require_attempt_video = exam_data.get("require_attempt_video", False)
        exam.max_attempts = exam_data.get("max_attempts", 1)
        exam.attempt_policy = exam_data.get("attempt_policy", AttemptPolicy.FLEXIBLE)
        exam.selected_question_ids = [q.id for q in selected]
        exam.question_configs = configs
        return self._exam_repo.update(exam)


class DeleteExamUseCase:
    def __init__(
        self,
        exam_repo: ExamRepository,
        attempt_repo: AttemptRepository,
        snapshot_repo: AttemptSnapshotRepository,
        upload_dir: str,
    ):
        self._exam_repo = exam_repo
        self._attempt_repo = attempt_repo
        self._snapshot_repo = snapshot_repo
        self._upload_dir = upload_dir

    def execute(self, owner_id: UUID, exam_id: UUID) -> None:
        from app.infrastructure.services.upload_cleanup import delete_uploaded_file

        exam = self._exam_repo.get_by_id(exam_id)
        if not exam or exam.owner_id != owner_id:
            raise NotFoundError("Exam not found")

        attempts = self._attempt_repo.list_by_exam(exam_id)
        for attempt in attempts:
            snapshots = self._snapshot_repo.list_by_attempt(attempt.id)
            for snapshot in snapshots:
                delete_uploaded_file(self._upload_dir, snapshot.image_url)
            delete_uploaded_file(self._upload_dir, attempt.attempt_video_url)

        if not self._exam_repo.delete(exam_id):
            raise NotFoundError("Exam not found")


class InviteToExamUseCase:
    def __init__(
        self,
        exam_repo: ExamRepository,
        invitation_repo: InvitationRepository,
        attempt_repo: AttemptRepository,
        email_service: EmailService,
        frontend_url: str,
    ):
        self._exam_repo = exam_repo
        self._invitation_repo = invitation_repo
        self._attempt_repo = attempt_repo
        self._email_service = email_service
        self._frontend_url = frontend_url

    async def execute(self, owner_id: UUID, exam_id: UUID, emails: list[str]) -> list[ExamInvitation]:
        exam = self._exam_repo.get_by_id(exam_id)
        if not exam or exam.owner_id != owner_id:
            raise NotFoundError("Exam not found")

        invitations = []
        for email in emails:
            normalized_email = email.lower().strip()
            if self._attempt_repo.count_finished_for_email(exam_id, normalized_email) >= exam.max_attempts:
                raise ValidationError(f"El correo {email} agotó los intentos del examen")
            if self._attempt_repo.has_in_progress_attempt_for_email(exam_id, normalized_email):
                raise ValidationError(f"El correo {email} ya tiene este examen en progreso")

            invitation = ExamInvitation(exam_id=exam_id, invitee_email=normalized_email)
            invitation = self._invitation_repo.create(invitation)
            invite_link = f"{self._frontend_url}/exam/take/{invitation.token}"
            logger.info(
                "Procesando invitación: exam_id=%s email=%s link=%s",
                exam_id,
                normalized_email,
                invite_link,
            )
            sent = await self._email_service.send_exam_invitation(
                email, exam.title, invite_link, exam.mode.value
            )
            invitation.status = InvitationStatus.SENT if sent else InvitationStatus.PENDING
            invitation.sent_at = datetime.now(timezone.utc) if sent else None
            if sent:
                logger.info("Invitación marcada como enviada: email=%s", normalized_email)
            else:
                logger.warning(
                    "Invitación quedó pendiente (correo no enviado): email=%s",
                    normalized_email,
                )
            invitation = self._invitation_repo.update(invitation)
            invitations.append(invitation)
        return invitations


class ListExamInvitationsUseCase:
    def __init__(
        self,
        exam_repo: ExamRepository,
        invitation_repo: InvitationRepository,
        attempt_repo: AttemptRepository,
        frontend_url: str,
    ):
        self._exam_repo = exam_repo
        self._invitation_repo = invitation_repo
        self._attempt_repo = attempt_repo
        self._frontend_url = frontend_url

    def execute(self, owner_id: UUID, exam_id: UUID) -> list[dict]:
        exam = self._exam_repo.get_by_id(exam_id)
        if not exam or exam.owner_id != owner_id:
            raise NotFoundError("Exam not found")

        invitations = self._invitation_repo.list_by_exam(exam_id)
        attempts_by_invitation: dict[UUID, list[ExamAttempt]] = {}
        for attempt in self._attempt_repo.list_by_exam(exam_id):
            attempts_by_invitation.setdefault(attempt.invitation_id, []).append(attempt)

        return [
            {
                "id": str(invitation.id),
                "invitee_email": invitation.invitee_email,
                "token": invitation.token,
                "status": invitation.status.value,
                "sent_at": invitation.sent_at.isoformat() if invitation.sent_at else None,
                "created_at": invitation.created_at.isoformat() if invitation.created_at else None,
                "attempt_status": self._invitation_attempt_status(
                    attempts_by_invitation.get(invitation.id, [])
                ),
                "attempts_completed": count_finished_attempts(
                    attempts_by_invitation.get(invitation.id, [])
                ),
                "attempts_total": exam.max_attempts,
                "invite_link": f"{self._frontend_url}/exam/take/{invitation.token}",
            }
            for invitation in sorted(invitations, key=lambda i: i.created_at, reverse=True)
        ]

    @staticmethod
    def _invitation_attempt_status(attempts: list[ExamAttempt]) -> str:
        in_progress = next(
            (attempt for attempt in attempts if attempt.status == AttemptStatus.IN_PROGRESS),
            None,
        )
        if in_progress:
            return in_progress.status.value
        if attempts:
            return attempts[-1].status.value
        return "not_started"


class DeleteExamInvitationUseCase:
    def __init__(
        self,
        exam_repo: ExamRepository,
        invitation_repo: InvitationRepository,
        attempt_repo: AttemptRepository,
    ):
        self._exam_repo = exam_repo
        self._invitation_repo = invitation_repo
        self._attempt_repo = attempt_repo

    def execute(self, owner_id: UUID, exam_id: UUID, invitation_id: UUID) -> None:
        exam = self._exam_repo.get_by_id(exam_id)
        if not exam or exam.owner_id != owner_id:
            raise NotFoundError("Exam not found")

        invitation = self._invitation_repo.get_by_id(invitation_id)
        if not invitation or invitation.exam_id != exam_id:
            raise NotFoundError("Invitation not found")

        attempts = self._attempt_repo.list_by_invitation(invitation_id)
        if any(
            attempt.status in (
                AttemptStatus.IN_PROGRESS,
                AttemptStatus.SUBMITTED,
                AttemptStatus.TIMED_OUT,
            )
            for attempt in attempts
        ):
            raise ValidationError("No se puede eliminar una invitación con examen iniciado o completado")

        if not self._invitation_repo.delete(invitation_id):
            raise NotFoundError("Invitation not found")


class DeleteInviteeExamResultsUseCase:
    def __init__(
        self,
        exam_repo: ExamRepository,
        attempt_repo: AttemptRepository,
        invitation_repo: InvitationRepository,
        snapshot_repo: AttemptSnapshotRepository,
        upload_dir: str,
    ):
        self._exam_repo = exam_repo
        self._attempt_repo = attempt_repo
        self._invitation_repo = invitation_repo
        self._snapshot_repo = snapshot_repo
        self._upload_dir = upload_dir

    def execute(self, owner_id: UUID, exam_id: UUID, invitee_email: str) -> dict:
        from app.infrastructure.services.upload_cleanup import delete_uploaded_file

        exam = self._exam_repo.get_by_id(exam_id)
        if not exam or exam.owner_id != owner_id:
            raise NotFoundError("Exam not found")

        normalized_email = invitee_email.strip()
        if not normalized_email:
            raise ValidationError("Correo inválido")

        attempts = self._attempt_repo.list_by_email(exam_id, normalized_email)
        if not attempts:
            raise NotFoundError("No hay resultados de examen para este invitado")

        deleted_count = 0
        for attempt in attempts:
            snapshots = self._snapshot_repo.list_by_attempt(attempt.id)
            for snapshot in snapshots:
                delete_uploaded_file(self._upload_dir, snapshot.image_url)
            delete_uploaded_file(self._upload_dir, attempt.attempt_video_url)
            if self._attempt_repo.delete(attempt.id):
                deleted_count += 1

        invitations = self._invitation_repo.get_by_exam_and_email(exam_id, normalized_email)
        for invitation in invitations:
            if invitation.status in (InvitationStatus.STARTED, InvitationStatus.COMPLETED):
                invitation.status = (
                    InvitationStatus.SENT if invitation.sent_at else InvitationStatus.PENDING
                )
                self._invitation_repo.update(invitation)

        return {"deleted_attempts": deleted_count}


class ResendExamInvitationUseCase:
    def __init__(
        self,
        exam_repo: ExamRepository,
        invitation_repo: InvitationRepository,
        email_service: EmailService,
        frontend_url: str,
    ):
        self._exam_repo = exam_repo
        self._invitation_repo = invitation_repo
        self._email_service = email_service
        self._frontend_url = frontend_url

    async def execute(self, owner_id: UUID, exam_id: UUID, invitation_id: UUID) -> ExamInvitation:
        exam = self._exam_repo.get_by_id(exam_id)
        if not exam or exam.owner_id != owner_id:
            raise NotFoundError("Exam not found")

        invitation = self._invitation_repo.get_by_id(invitation_id)
        if not invitation or invitation.exam_id != exam_id:
            raise NotFoundError("Invitation not found")

        invite_link = f"{self._frontend_url}/exam/take/{invitation.token}"
        sent = await self._email_service.send_exam_invitation(
            invitation.invitee_email, exam.title, invite_link, exam.mode.value
        )
        invitation.status = InvitationStatus.SENT if sent else InvitationStatus.PENDING
        invitation.sent_at = datetime.now(timezone.utc) if sent else invitation.sent_at
        return self._invitation_repo.update(invitation)


class StartExamAttemptUseCase:
    def __init__(
        self,
        invitation_repo: InvitationRepository,
        attempt_repo: AttemptRepository,
        exam_repo: ExamRepository,
        question_repo: QuestionRepository,
    ):
        self._invitation_repo = invitation_repo
        self._attempt_repo = attempt_repo
        self._exam_repo = exam_repo
        self._question_repo = question_repo

    def execute(self, token: str, camera_verified: bool, full_name: str) -> ExamAttempt:
        if not camera_verified:
            raise ValidationError("Camera verification required")

        normalized_name = full_name.strip()
        if len(normalized_name) < 2:
            raise ValidationError("El nombre completo es obligatorio")

        invitation = self._invitation_repo.get_by_token(token)
        if not invitation:
            raise NotFoundError("Invalid invitation token")
        if invitation.status == InvitationStatus.COMPLETED:
            raise ValidationError("El examen ya fue finalizado")

        exam = self._exam_repo.get_by_id(invitation.exam_id)
        if not exam or exam.status == ExamStatus.CLOSED:
            raise ValidationError("Exam is not available")
        if is_exam_closed(exam):
            raise ValidationError("Exam has closed")

        email_attempts = self._attempt_repo.list_by_email(
            invitation.exam_id, invitation.invitee_email
        )
        action, existing, next_attempt_number = resolve_attempt_start(
            exam, invitation, email_attempts
        )

        if action == "blocked_exhausted":
            raise ValidationError("Agotó los intentos disponibles para este examen")
        if action == "blocked_other_progress":
            raise ValidationError("Este correo ya tiene un examen en progreso")
        if action == "blocked_sequence":
            raise ValidationError("Debe completar los intentos en orden secuencial")

        if action == "resume" and existing:
            existing.status = AttemptStatus.IN_PROGRESS
            existing.started_at = existing.started_at or datetime.now(timezone.utc)
            existing.camera_verified = True
            if not existing.invitee_full_name:
                existing.invitee_full_name = normalized_name
            try:
                assign_attempt_questions(exam, existing, self._question_repo)
            except ValueError as error:
                raise ValidationError(str(error)) from error
            attempt = self._attempt_repo.update(existing)
        elif action == "create" and next_attempt_number is not None:
            now = datetime.now(timezone.utc)
            attempt = ExamAttempt(
                invitation_id=invitation.id,
                exam_id=invitation.exam_id,
                status=AttemptStatus.IN_PROGRESS,
                attempt_number=next_attempt_number,
                invitee_full_name=normalized_name,
                started_at=now,
                camera_verified=True,
                current_question_index=0,
                locked_question_ids=[],
                current_question_started_at=now,
            )
            try:
                assign_attempt_questions(exam, attempt, self._question_repo)
            except ValueError as error:
                raise ValidationError(str(error)) from error
            attempt = self._attempt_repo.create(attempt)
        else:
            raise ValidationError("No se pudo iniciar el examen")

        invitation.status = InvitationStatus.STARTED
        invitation.decision_deadline_at = None
        self._invitation_repo.update(invitation)
        return attempt


class SubmitAnswerUseCase:
    def __init__(
        self,
        attempt_repo: AttemptRepository,
        answer_repo: AnswerRepository,
        exam_repo: ExamRepository,
        question_repo: QuestionRepository,
    ):
        self._attempt_repo = attempt_repo
        self._answer_repo = answer_repo
        self._exam_repo = exam_repo
        self._question_repo = question_repo

    def execute(
        self,
        attempt_id: UUID,
        question_id: UUID,
        selected_option_ids: list[UUID],
        open_text: str | None = None,
    ) -> Answer:
        attempt = self._attempt_repo.get_by_id(attempt_id)
        if not attempt or attempt.status != AttemptStatus.IN_PROGRESS:
            raise ValidationError("Attempt not in progress")

        exam = self._exam_repo.get_by_id(attempt.exam_id)
        if not exam:
            raise NotFoundError("Exam not found")

        self._check_time_limit(attempt, exam)

        question = self._question_repo.get_by_id(question_id)
        if not question:
            raise NotFoundError("Question not found")

        allowed_question_ids = get_attempt_question_id_set(exam, attempt)
        if allowed_question_ids and question_id not in allowed_question_ids:
            raise ValidationError("La pregunta no pertenece a este intento")

        is_correct, points = self._grade_answer(
            question, selected_option_ids, open_text, exam, attempt
        )

        answer = Answer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_option_ids=selected_option_ids,
            open_text=open_text,
            is_correct=is_correct,
            points_earned=points,
        )
        return self._answer_repo.upsert(answer)

    def _check_time_limit(self, attempt: ExamAttempt, exam: Exam):
        if not attempt.started_at:
            return
        if is_exam_time_expired(exam, attempt):
            attempt.status = AttemptStatus.TIMED_OUT
            self._attempt_repo.update(attempt)
            raise ValidationError("Exam time expired")

    def _grade_answer(
        self,
        question: Question,
        selected_option_ids: list[UUID],
        open_text: str | None,
        exam: Exam,
        attempt: ExamAttempt,
    ) -> tuple[bool | None, float]:
        configs = get_attempt_question_configs(exam, attempt)
        config = next((item for item in configs if item.question_id == question.id), None)
        points_value = config.points if config else 0.0

        if question.question_type == QuestionType.OPEN:
            return None, 0.0

        correct_ids = {o.id for o in question.options if o.is_correct}
        selected_set = set(selected_option_ids)

        if question.question_type == QuestionType.SINGLE_CHOICE:
            is_correct = selected_set == correct_ids and len(correct_ids) == 1
        elif question.question_type == QuestionType.MULTIPLE_CHOICE:
            is_correct = selected_set == correct_ids
        elif question.question_type == QuestionType.TRUE_FALSE:
            is_correct = selected_set == correct_ids
        else:
            is_correct = False

        return is_correct, points_value if is_correct else 0.0


class SaveAttemptProgressUseCase:
    def __init__(
        self,
        attempt_repo: AttemptRepository,
        exam_repo: ExamRepository,
    ):
        self._attempt_repo = attempt_repo
        self._exam_repo = exam_repo

    def execute(
        self,
        attempt_id: UUID,
        current_question_index: int,
        locked_question_ids: list[UUID],
    ) -> ExamAttempt:
        attempt = self._attempt_repo.get_by_id(attempt_id)
        if not attempt or attempt.status != AttemptStatus.IN_PROGRESS:
            raise ValidationError("Attempt not in progress")

        exam = self._exam_repo.get_by_id(attempt.exam_id)
        if not exam:
            raise NotFoundError("Exam not found")

        max_index = max(exam.question_count - 1, 0)
        if current_question_index > max_index:
            raise ValidationError("Invalid question index")

        if current_question_index != attempt.current_question_index:
            attempt.current_question_started_at = datetime.now(timezone.utc)

        attempt.current_question_index = current_question_index
        attempt.locked_question_ids = locked_question_ids
        return self._attempt_repo.update(attempt)


class SubmitExamUseCase:
    def __init__(
        self,
        attempt_repo: AttemptRepository,
        answer_repo: AnswerRepository,
        invitation_repo: InvitationRepository,
        exam_repo: ExamRepository,
    ):
        self._attempt_repo = attempt_repo
        self._answer_repo = answer_repo
        self._invitation_repo = invitation_repo
        self._exam_repo = exam_repo

    def execute(self, attempt_id: UUID, skip_video_required: bool = False) -> ExamAttempt:
        attempt = self._attempt_repo.get_by_id(attempt_id)
        if not attempt:
            raise NotFoundError("Attempt not found")
        if attempt.status == AttemptStatus.SUBMITTED:
            return attempt
        if attempt.status not in (AttemptStatus.IN_PROGRESS, AttemptStatus.TIMED_OUT):
            raise ValidationError("Attempt cannot be submitted")

        answers = self._answer_repo.get_by_attempt(attempt_id)
        exam = self._exam_repo.get_by_id(attempt.exam_id)
        if (
            exam
            and exam.require_attempt_video
            and not attempt.attempt_video_url
            and not skip_video_required
        ):
            raise ValidationError("Debe enviar el video del intento antes de finalizar")

        if exam:
            allowed_question_ids = get_attempt_question_id_set(exam, attempt)
            if allowed_question_ids:
                answers = [answer for answer in answers if answer.question_id in allowed_question_ids]

        total_score = sum(a.points_earned for a in answers)
        if exam:
            total_score = min(round(total_score, 2), exam.total_score)

        attempt.score = total_score
        attempt.status = AttemptStatus.SUBMITTED
        attempt.submitted_at = datetime.now(timezone.utc)
        attempt = self._attempt_repo.update(attempt)

        invitation = self._invitation_repo.get_by_id(attempt.invitation_id)
        if invitation:
            email_attempts = self._attempt_repo.list_by_email(
                attempt.exam_id, invitation.invitee_email
            )
            if exam and has_exhausted_attempts(exam, email_attempts):
                invitation.status = InvitationStatus.COMPLETED
                invitation.decision_deadline_at = None
            else:
                invitation.status = InvitationStatus.STARTED
                from app.application.attempt_decision import build_decision_deadline

                invitation.decision_deadline_at = build_decision_deadline()
            self._invitation_repo.update(invitation)

        return attempt


class TerminateExamForTabSwitchUseCase:
    def __init__(
        self,
        invitation_repo: InvitationRepository,
        attempt_repo: AttemptRepository,
        proctoring_repo: ProctoringRepository,
        submit_exam_use_case: SubmitExamUseCase,
    ):
        self._invitation_repo = invitation_repo
        self._attempt_repo = attempt_repo
        self._proctoring_repo = proctoring_repo
        self._submit_exam_use_case = submit_exam_use_case

    def execute(self, token: str) -> dict:
        invitation = self._invitation_repo.get_by_token(token)
        if not invitation:
            raise NotFoundError("Invalid invitation token")

        email_attempts = self._attempt_repo.list_by_email(
            invitation.exam_id, invitation.invitee_email
        )
        in_progress = get_in_progress_attempt(email_attempts)

        if invitation.status == InvitationStatus.COMPLETED and not in_progress:
            return self._build_response(email_attempts, terminated_now=False)

        if in_progress:
            self._proctoring_repo.create(
                ProctoringEvent(
                    attempt_id=in_progress.id,
                    event_type=ProctoringEventType.TAB_SWITCH,
                    confidence=1.0,
                    metadata={"reason": "Cambio de pestaña o ventana detectado"},
                )
            )
            in_progress.fraud_score = min(1.0, in_progress.fraud_score + 0.5)
            self._attempt_repo.update(in_progress)
            self._submit_exam_use_case.execute(in_progress.id, skip_video_required=True)
            email_attempts = self._attempt_repo.list_by_email(
                invitation.exam_id, invitation.invitee_email
            )

        for invite in self._invitation_repo.get_by_exam_and_email(
            invitation.exam_id, invitation.invitee_email
        ):
            if invite.status != InvitationStatus.COMPLETED:
                invite.status = InvitationStatus.COMPLETED
                self._invitation_repo.update(invite)

        return self._build_response(email_attempts, terminated_now=True)

    def _build_response(self, email_attempts: list[ExamAttempt], *, terminated_now: bool) -> dict:
        finished = [attempt for attempt in email_attempts if is_finished_attempt(attempt)]
        last_attempt = (
            max(finished, key=lambda attempt: attempt.attempt_number) if finished else None
        )
        return {
            "final_score": last_attempt.score if last_attempt else None,
            "attempt_number": last_attempt.attempt_number if last_attempt else None,
            "exam_finalized": True,
            "terminated_for_violation": True,
            "terminated_now": terminated_now,
            "message": (
                "El examen fue cerrado por cambiar de pestaña o ventana. "
                "No podrás realizar más intentos."
            ),
        }


class FinishExamEarlyUseCase:
    def __init__(
        self,
        invitation_repo: InvitationRepository,
        attempt_repo: AttemptRepository,
    ):
        self._invitation_repo = invitation_repo
        self._attempt_repo = attempt_repo

    def execute(self, token: str) -> dict:
        invitation = self._invitation_repo.get_by_token(token)
        if not invitation:
            raise NotFoundError("Invalid invitation token")
        if invitation.status == InvitationStatus.COMPLETED:
            raise ValidationError("El examen ya fue finalizado")

        email_attempts = self._attempt_repo.list_by_email(
            invitation.exam_id, invitation.invitee_email
        )
        finished = [attempt for attempt in email_attempts if is_finished_attempt(attempt)]
        if not finished:
            raise ValidationError("Debe completar al menos un intento antes de finalizar")

        last_attempt = max(finished, key=lambda attempt: attempt.attempt_number)
        invitation.status = InvitationStatus.COMPLETED
        invitation.decision_deadline_at = None
        self._invitation_repo.update(invitation)

        return {
            "final_score": last_attempt.score,
            "attempt_number": last_attempt.attempt_number,
            "exam_finalized": True,
        }


class PrepareNextAttemptUseCase:
    def __init__(
        self,
        invitation_repo: InvitationRepository,
        attempt_repo: AttemptRepository,
        exam_repo: ExamRepository,
    ):
        self._invitation_repo = invitation_repo
        self._attempt_repo = attempt_repo
        self._exam_repo = exam_repo

    def execute(self, token: str) -> dict:
        invitation = self._invitation_repo.get_by_token(token)
        if not invitation:
            raise NotFoundError("Invalid invitation token")
        if invitation.status == InvitationStatus.COMPLETED:
            raise ValidationError("El examen ya fue finalizado")

        exam = self._exam_repo.get_by_id(invitation.exam_id)
        email_attempts = self._attempt_repo.list_by_email(
            invitation.exam_id, invitation.invitee_email
        )
        if exam and has_exhausted_attempts(exam, email_attempts):
            raise ValidationError("Agotó los intentos disponibles para este examen")
        if get_in_progress_attempt(email_attempts):
            raise ValidationError("Ya hay un intento en progreso")

        finished = [attempt for attempt in email_attempts if is_finished_attempt(attempt)]
        if not finished:
            raise ValidationError("Debe completar al menos un intento antes de continuar")

        invitation.decision_deadline_at = None
        self._invitation_repo.update(invitation)
        return {"prepared": True}


class ProctoringAnalysisUseCase:
    def __init__(
        self,
        attempt_repo: AttemptRepository,
        proctoring_repo: ProctoringRepository,
        proctoring_service: ProctoringService,
        fraud_threshold: float = 0.7,
    ):
        self._attempt_repo = attempt_repo
        self._proctoring_repo = proctoring_repo
        self._proctoring_service = proctoring_service
        self._fraud_threshold = fraud_threshold

    def execute(
        self, attempt_id: UUID, frame_data: bytes, mouse_events: list[dict]
    ) -> ProctoringEvent | None:
        attempt = self._attempt_repo.get_by_id(attempt_id)
        if not attempt or attempt.status != AttemptStatus.IN_PROGRESS:
            raise ValidationError("Attempt not in progress")

        result = self._proctoring_service.analyze_frame(frame_data, mouse_events)

        if result.fraud_detected:
            event = ProctoringEvent(
                attempt_id=attempt_id,
                event_type=ProctoringEventType(result.event_type),
                confidence=result.confidence,
                metadata=result.details,
            )
            event = self._proctoring_repo.create(event)
            attempt.fraud_score = min(1.0, attempt.fraud_score + result.fraud_score * 0.1)
            self._attempt_repo.update(attempt)
            return event
        return None


MAX_PROGRESS_SNAPSHOTS = 5


class SaveAttemptVideoUseCase:
    def __init__(
        self,
        attempt_repo: AttemptRepository,
        exam_repo: ExamRepository,
    ):
        self._attempt_repo = attempt_repo
        self._exam_repo = exam_repo

    def execute(self, attempt_id: UUID, video_url: str) -> ExamAttempt:
        attempt = self._attempt_repo.get_by_id(attempt_id)
        if not attempt or attempt.status != AttemptStatus.IN_PROGRESS:
            raise ValidationError("Attempt not in progress")

        exam = self._exam_repo.get_by_id(attempt.exam_id)
        if not exam or not exam.require_attempt_video:
            raise ValidationError("Este examen no requiere video del intento")

        if attempt.attempt_video_url:
            return attempt

        attempt.attempt_video_url = video_url
        return self._attempt_repo.update(attempt)


class SaveAttemptSnapshotUseCase:
    def __init__(
        self,
        attempt_repo: AttemptRepository,
        snapshot_repo: AttemptSnapshotRepository,
    ):
        self._attempt_repo = attempt_repo
        self._snapshot_repo = snapshot_repo

    def execute(self, attempt_id: UUID, snapshot_type: SnapshotType, image_url: str) -> AttemptSnapshot:
        attempt = self._attempt_repo.get_by_id(attempt_id)
        if not attempt or attempt.status != AttemptStatus.IN_PROGRESS:
            raise ValidationError("Attempt not in progress")

        if snapshot_type == SnapshotType.START:
            if self._snapshot_repo.count_by_type(attempt_id, SnapshotType.START) >= 1:
                raise ValidationError("Start snapshot already captured")
        elif snapshot_type == SnapshotType.PROGRESS:
            if self._snapshot_repo.count_by_type(attempt_id, SnapshotType.PROGRESS) >= MAX_PROGRESS_SNAPSHOTS:
                raise ValidationError("Maximum progress snapshots reached")
        else:
            raise ValidationError("Invalid snapshot type")

        snapshot = AttemptSnapshot(
            attempt_id=attempt_id,
            snapshot_type=snapshot_type,
            image_url=image_url,
            captured_at=datetime.now(timezone.utc),
        )
        return self._snapshot_repo.create(snapshot)


class GetExamReportUseCase:
    def __init__(
        self,
        exam_repo: ExamRepository,
        attempt_repo: AttemptRepository,
        invitation_repo: InvitationRepository,
        answer_repo: AnswerRepository,
        proctoring_repo: ProctoringRepository,
    ):
        self._exam_repo = exam_repo
        self._attempt_repo = attempt_repo
        self._invitation_repo = invitation_repo
        self._answer_repo = answer_repo
        self._proctoring_repo = proctoring_repo

    def execute(self, owner_id: UUID, exam_id: UUID) -> dict:
        exam = self._exam_repo.get_by_id(exam_id)
        if not exam or exam.owner_id != owner_id:
            raise NotFoundError("Exam not found")

        attempts = self._attempt_repo.list_by_exam(exam_id)
        invitations = {i.id: i for i in self._invitation_repo.list_by_exam(exam_id)}

        attempts_by_email: dict[str, list[ExamAttempt]] = {}
        for attempt in attempts:
            invitation = invitations.get(attempt.invitation_id)
            if not invitation:
                continue
            email_key = invitation.invitee_email.lower()
            attempts_by_email.setdefault(email_key, []).append(attempt)

        individual_reports = []
        final_scores: list[float] = []
        completed_correct_counts: list[int] = []
        completed_incorrect_counts: list[int] = []

        for email_attempts in attempts_by_email.values():
            finished = sorted(
                [attempt for attempt in email_attempts if is_finished_attempt(attempt)],
                key=lambda attempt: attempt.attempt_number,
            )
            if finished:
                last_attempt = finished[-1]
            else:
                last_attempt = max(email_attempts, key=lambda attempt: attempt.attempt_number)

            invitation = invitations.get(last_attempt.invitation_id)
            answers = self._answer_repo.get_by_attempt(last_attempt.id)
            events = self._proctoring_repo.list_by_attempt(last_attempt.id)
            answer_stats = summarize_attempt_answers(exam, last_attempt, answers)
            correct_answers_count = answer_stats["correct_count"]
            incorrect_answers_count = answer_stats["incorrect_count"]
            answers_count = answer_stats["answered_count"]
            if last_attempt.status == AttemptStatus.SUBMITTED and last_attempt.score is not None:
                final_scores.append(last_attempt.score)
                completed_correct_counts.append(correct_answers_count)
                completed_incorrect_counts.append(incorrect_answers_count)

            individual_reports.append(
                {
                    "attempt_id": str(last_attempt.id),
                    "attempt_number": last_attempt.attempt_number,
                    "attempts_used": len(finished),
                    "invitee_email": invitation.invitee_email if invitation else "",
                    "invitee_full_name": last_attempt.invitee_full_name,
                    "score": last_attempt.score,
                    "total_score": exam.total_score,
                    "percentage": (
                        (last_attempt.score / exam.total_score * 100)
                        if last_attempt.score is not None and exam.total_score
                        else 0
                    ),
                    "status": last_attempt.status.value,
                    "fraud_score": last_attempt.fraud_score,
                    "proctoring_events_count": len(events),
                    "answers_count": answers_count,
                    "correct_answers_count": correct_answers_count,
                    "incorrect_answers_count": incorrect_answers_count,
                    "started_at": last_attempt.started_at.isoformat() if last_attempt.started_at else None,
                    "submitted_at": (
                        last_attempt.submitted_at.isoformat() if last_attempt.submitted_at else None
                    ),
                    "is_final_score": True,
                }
            )

        individual_reports.sort(key=lambda row: row["invitee_email"].lower())

        return {
            "exam_id": str(exam.id),
            "exam_title": exam.title,
            "total_score": exam.total_score,
            "question_count": exam.question_count,
            "individual_reports": individual_reports,
            "summary": {
                "total_invitees": len(invitations),
                "completed": sum(
                    1 for invitation in invitations.values() if invitation.status == InvitationStatus.COMPLETED
                ),
                "average_score": sum(final_scores) / len(final_scores) if final_scores else 0,
                "highest_score": max(final_scores) if final_scores else 0,
                "lowest_score": min(final_scores) if final_scores else 0,
                "average_correct_answers": (
                    sum(completed_correct_counts) / len(completed_correct_counts)
                    if completed_correct_counts
                    else 0
                ),
                "average_incorrect_answers": (
                    sum(completed_incorrect_counts) / len(completed_incorrect_counts)
                    if completed_incorrect_counts
                    else 0
                ),
            },
        }


class ExportExamReportUseCase:
    def __init__(self, report_use_case: GetExamReportUseCase):
        self._report_use_case = report_use_case

    def execute(self, owner_id: UUID, exam_id: UUID) -> tuple[bytes, str]:
        from app.application.exam_report_export import build_exam_report_workbook, build_export_filename

        report = self._report_use_case.execute(owner_id, exam_id)
        content = build_exam_report_workbook(report)
        filename = build_export_filename(report)
        return content, filename


class GetAttemptAnswersReportUseCase:
    def __init__(
        self,
        exam_repo: ExamRepository,
        attempt_repo: AttemptRepository,
        invitation_repo: InvitationRepository,
        answer_repo: AnswerRepository,
        question_repo: QuestionRepository,
        snapshot_repo: AttemptSnapshotRepository,
    ):
        self._exam_repo = exam_repo
        self._attempt_repo = attempt_repo
        self._invitation_repo = invitation_repo
        self._answer_repo = answer_repo
        self._question_repo = question_repo
        self._snapshot_repo = snapshot_repo

    def execute(self, owner_id: UUID, exam_id: UUID, attempt_id: UUID) -> dict:
        exam = self._exam_repo.get_by_id(exam_id)
        if not exam or exam.owner_id != owner_id:
            raise NotFoundError("Exam not found")

        attempt = self._attempt_repo.get_by_id(attempt_id)
        if not attempt or attempt.exam_id != exam_id:
            raise NotFoundError("Attempt not found")

        invitation = self._invitation_repo.get_by_id(attempt.invitation_id)
        answers_by_question = {
            answer.question_id: answer for answer in self._answer_repo.get_by_attempt(attempt_id)
        }

        configs = resolve_attempt_question_configs(exam, attempt)
        question_ids = [config.question_id for config in configs]
        questions = {question.id: question for question in self._question_repo.list_by_ids(question_ids)}

        answer_details = []
        seen_question_ids: set[UUID] = set()
        for config in configs:
            if config.question_id in seen_question_ids:
                continue
            seen_question_ids.add(config.question_id)
            question = questions.get(config.question_id)
            if not question:
                continue
            answer = answers_by_question.get(config.question_id)
            selected_options = self._selected_option_texts(question, answer)
            answer_details.append(
                {
                    "question_id": str(question.id),
                    "order": config.order + 1,
                    "question_text": question.text,
                    "question_type": question.question_type.value,
                    "selected_options": selected_options,
                    "correct_options": [option.text for option in question.options if option.is_correct],
                    "open_text": answer.open_text if answer else None,
                    "is_correct": answer.is_correct if answer else None,
                    "points_earned": answer.points_earned if answer else 0,
                    "max_points": config.points,
                    "answered": answer is not None,
                }
            )

        snapshots = self._snapshot_repo.list_by_attempt(attempt_id)

        return {
            "attempt_id": str(attempt.id),
            "attempt_number": attempt.attempt_number,
            "invitee_email": invitation.invitee_email if invitation else "",
            "invitee_full_name": attempt.invitee_full_name,
            "exam_title": exam.title,
            "score": attempt.score,
            "total_score": exam.total_score,
            "answers": answer_details,
            "video_url": attempt.attempt_video_url,
            "require_attempt_video": exam.require_attempt_video,
            "snapshots": [
                {
                    "id": str(snapshot.id),
                    "snapshot_type": snapshot.snapshot_type.value,
                    "image_url": snapshot.image_url,
                    "captured_at": snapshot.captured_at.isoformat() if snapshot.captured_at else None,
                }
                for snapshot in snapshots
            ],
        }

    @staticmethod
    def _selected_option_texts(question: Question, answer: Answer | None) -> list[str]:
        if not answer or not answer.selected_option_ids:
            return []
        selected_ids = set(answer.selected_option_ids)
        return [option.text for option in question.options if option.id in selected_ids]


class ExportExamAttemptsAnswersUseCase:
    def __init__(
        self,
        report_use_case: GetExamReportUseCase,
        answers_use_case: GetAttemptAnswersReportUseCase,
        attempt_repo: AttemptRepository,
    ):
        self._report_use_case = report_use_case
        self._answers_use_case = answers_use_case
        self._attempt_repo = attempt_repo

    def execute(
        self, owner_id: UUID, exam_id: UUID, invitee_email: str | None = None
    ) -> tuple[bytes, str]:
        from app.application.attempt_access import is_finished_attempt
        from app.application.exam_attempts_answers_export import (
            build_attempts_answers_filename,
            build_attempts_answers_workbook,
        )

        report = self._report_use_case.execute(owner_id, exam_id)
        normalized_email = invitee_email.strip() if invitee_email else None
        if normalized_email == "":
            normalized_email = None

        if normalized_email:
            attempts = self._attempt_repo.list_by_email(exam_id, normalized_email)
        else:
            attempts = self._attempt_repo.list_by_exam(exam_id)

        finished_attempts = sorted(
            [attempt for attempt in attempts if is_finished_attempt(attempt)],
            key=lambda attempt: attempt.attempt_number,
        )
        if not finished_attempts:
            raise ValidationError("No hay intentos finalizados para exportar")

        attempt_reports = [
            self._answers_use_case.execute(owner_id, exam_id, attempt.id)
            for attempt in finished_attempts
        ]
        attempt_reports.sort(
            key=lambda item: (item["invitee_email"].lower(), item.get("attempt_number") or 1)
        )

        content = build_attempts_answers_workbook(report["exam_title"], attempt_reports)
        filename = build_attempts_answers_filename(report["exam_title"], normalized_email)
        return content, filename
