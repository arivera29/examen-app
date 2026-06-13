import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

from app.application.use_cases import (
    CreateExamUseCase,
    CreateQuestionBankUseCase,
    DeleteExamInvitationUseCase,
    DeleteInviteeExamResultsUseCase,
    DeleteExamUseCase,
    DeleteQuestionBankUseCase,
    DeleteQuestionUseCase,
    DuplicateQuestionUseCase,
    TerminateExamForTabSwitchUseCase,
    FinishExamEarlyUseCase,
    GetAttemptAnswersReportUseCase,
    GetExamReportUseCase,
    InviteToExamUseCase,
    LoginInput,
    LoginUseCase,
    NotFoundError,
    ProctoringAnalysisUseCase,
    RegisterUserInput,
    RegisterUserUseCase,
    SaveAttemptSnapshotUseCase,
    SaveAttemptProgressUseCase,
    SaveAttemptVideoUseCase,
    StartExamAttemptUseCase,
    SubmitAnswerUseCase,
    SubmitExamUseCase,
    UpdateExamUseCase,
    UpdateQuestionBankUseCase,
    UpdateQuestionUseCase,
    UnauthorizedError,
    ValidationError,
)
from app.domain.entities import Answer, AttemptSnapshot, Exam, ExamAttempt, ExamInvitation, ExamQuestionConfig, ProctoringEvent, Question, QuestionBank, QuestionOption, User
from app.domain.enums import AttemptStatus, ExamMode, InvitationStatus, ProctoringEventType, QuestionType, SnapshotType
from app.domain.services import ProctoringAnalysisResult, TokenPair

FUTURE_CLOSES_AT = datetime.now(timezone.utc) + timedelta(days=7)


@pytest.fixture
def mock_user_repo():
    return MagicMock()


@pytest.fixture
def mock_password_hasher():
    hasher = MagicMock()
    hasher.hash.return_value = "hashed_password"
    hasher.verify.return_value = True
    return hasher


@pytest.fixture
def mock_token_service():
    service = MagicMock()
    service.create_token_pair.return_value = TokenPair(
        access_token="access", refresh_token="refresh"
    )
    return service


@pytest.fixture
def mock_mfa_service():
    service = MagicMock()
    service.verify_code.return_value = True
    return service


class TestRegisterUserUseCase:
    def test_register_success(self, mock_user_repo, mock_password_hasher):
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.create.side_effect = lambda u: u

        use_case = RegisterUserUseCase(mock_user_repo, mock_password_hasher)
        user = use_case.execute(
            RegisterUserInput(email="test@test.com", password="password123", full_name="Test User")
        )

        assert user.email == "test@test.com"
        assert user.hashed_password == "hashed_password"
        mock_password_hasher.hash.assert_called_once_with("password123")

    def test_register_duplicate_email(self, mock_user_repo, mock_password_hasher):
        mock_user_repo.get_by_email.return_value = User(
            email="test@test.com", hashed_password="x", full_name="Existing"
        )

        use_case = RegisterUserUseCase(mock_user_repo, mock_password_hasher)
        with pytest.raises(ValidationError, match="already registered"):
            use_case.execute(
                RegisterUserInput(email="test@test.com", password="password123", full_name="Test")
            )


class TestLoginUseCase:
    def test_login_success(self, mock_user_repo, mock_password_hasher, mock_token_service, mock_mfa_service):
        user = User(email="test@test.com", hashed_password="hash", full_name="Test", mfa_enabled=False)
        mock_user_repo.get_by_email.return_value = user

        use_case = LoginUseCase(mock_user_repo, mock_password_hasher, mock_token_service, mock_mfa_service)
        tokens = use_case.execute(LoginInput(email="test@test.com", password="password123"))

        assert tokens.access_token == "access"
        assert tokens.refresh_token == "refresh"

    def test_login_invalid_credentials(self, mock_user_repo, mock_password_hasher, mock_token_service, mock_mfa_service):
        mock_user_repo.get_by_email.return_value = None

        use_case = LoginUseCase(mock_user_repo, mock_password_hasher, mock_token_service, mock_mfa_service)
        with pytest.raises(UnauthorizedError):
            use_case.execute(LoginInput(email="test@test.com", password="wrong"))

    def test_login_requires_mfa(self, mock_user_repo, mock_password_hasher, mock_token_service, mock_mfa_service):
        user = User(
            email="test@test.com",
            hashed_password="hash",
            full_name="Test",
            mfa_enabled=True,
            mfa_secret="SECRET",
        )
        mock_user_repo.get_by_email.return_value = user

        use_case = LoginUseCase(mock_user_repo, mock_password_hasher, mock_token_service, mock_mfa_service)
        with pytest.raises(UnauthorizedError, match="MFA code required"):
            use_case.execute(LoginInput(email="test@test.com", password="password123"))


class TestCreateQuestionBankUseCase:
    def test_create_bank(self):
        repo = MagicMock()
        repo.create.side_effect = lambda b: b

        use_case = CreateQuestionBankUseCase(repo)
        owner_id = uuid4()
        bank = use_case.execute(owner_id, "My Bank", "Description")

        assert bank.name == "My Bank"
        assert bank.owner_id == owner_id


class TestUpdateQuestionBankUseCase:
    def test_update_bank(self):
        owner_id = uuid4()
        bank_id = uuid4()
        bank = QuestionBank(name="Old", description="Old desc", owner_id=owner_id, id=bank_id)
        repo = MagicMock()
        repo.get_by_id.return_value = bank
        repo.update.side_effect = lambda b: b

        use_case = UpdateQuestionBankUseCase(repo)
        updated = use_case.execute(owner_id, bank_id, "New", "New desc")

        assert updated.name == "New"
        assert updated.description == "New desc"


class TestDeleteQuestionBankUseCase:
    def test_delete_bank_without_exams(self):
        owner_id = uuid4()
        bank_id = uuid4()
        bank = QuestionBank(name="Bank", description="", owner_id=owner_id, id=bank_id)
        bank_repo = MagicMock()
        bank_repo.get_by_id.return_value = bank
        bank_repo.delete.return_value = True
        exam_repo = MagicMock()
        exam_repo.count_by_question_bank.return_value = 0

        use_case = DeleteQuestionBankUseCase(bank_repo, exam_repo)
        use_case.execute(owner_id, bank_id)
        bank_repo.delete.assert_called_once_with(bank_id)

    def test_blocks_delete_when_used_by_exams(self):
        owner_id = uuid4()
        bank_id = uuid4()
        bank = QuestionBank(name="Bank", description="", owner_id=owner_id, id=bank_id)
        bank_repo = MagicMock()
        bank_repo.get_by_id.return_value = bank
        exam_repo = MagicMock()
        exam_repo.count_by_question_bank.return_value = 1

        use_case = DeleteQuestionBankUseCase(bank_repo, exam_repo)
        with pytest.raises(ValidationError, match="exámenes"):
            use_case.execute(owner_id, bank_id)


class TestUpdateQuestionUseCase:
    def test_update_question(self):
        owner_id = uuid4()
        bank_id = uuid4()
        question_id = uuid4()
        bank = QuestionBank(name="Bank", description="", owner_id=owner_id, id=bank_id)
        question = Question(
            id=question_id,
            text="Old",
            question_type=QuestionType.SINGLE_CHOICE,
            time_seconds=60,
            owner_id=owner_id,
            options=[QuestionOption(text="A", is_correct=True)],
        )
        bank_repo = MagicMock()
        bank_repo.get_by_id.return_value = bank
        question_repo = MagicMock()
        question_repo.get_by_id_in_bank.return_value = question
        question_repo.update.side_effect = lambda q: q
        topic_repo = MagicMock()

        use_case = UpdateQuestionUseCase(bank_repo, question_repo, topic_repo)
        updated = use_case.execute(
            owner_id,
            bank_id,
            question_id,
            "New text",
            QuestionType.SINGLE_CHOICE,
            90,
            [{"text": "B", "is_correct": True}],
        )
        assert updated.text == "New text"
        assert updated.time_seconds == 90


class TestDeleteQuestionUseCase:
    def test_delete_question_not_in_exam(self):
        owner_id = uuid4()
        bank_id = uuid4()
        question_id = uuid4()
        bank = QuestionBank(name="Bank", description="", owner_id=owner_id, id=bank_id)
        question = Question(
            id=question_id,
            text="Q",
            question_type=QuestionType.OPEN,
            time_seconds=60,
            owner_id=owner_id,
        )
        bank_repo = MagicMock()
        bank_repo.get_by_id.return_value = bank
        question_repo = MagicMock()
        question_repo.get_by_id_in_bank.return_value = question
        question_repo.delete.return_value = True
        exam_repo = MagicMock()
        exam_repo.count_exams_using_question.return_value = 0

        use_case = DeleteQuestionUseCase(bank_repo, question_repo, exam_repo)
        use_case.execute(owner_id, bank_id, question_id)
        question_repo.delete.assert_called_once_with(question_id)

    def test_blocks_delete_when_used_in_exam(self):
        owner_id = uuid4()
        bank_id = uuid4()
        question_id = uuid4()
        bank = QuestionBank(name="Bank", description="", owner_id=owner_id, id=bank_id)
        question = Question(
            id=question_id,
            text="Q",
            question_type=QuestionType.OPEN,
            time_seconds=60,
            owner_id=owner_id,
        )
        bank_repo = MagicMock()
        bank_repo.get_by_id.return_value = bank
        question_repo = MagicMock()
        question_repo.get_by_id_in_bank.return_value = question
        exam_repo = MagicMock()
        exam_repo.count_exams_using_question.return_value = 1

        use_case = DeleteQuestionUseCase(bank_repo, question_repo, exam_repo)
        with pytest.raises(ValidationError, match="exámenes"):
            use_case.execute(owner_id, bank_id, question_id)


class TestDuplicateQuestionUseCase:
    def test_duplicates_question_with_options_and_image(self):
        owner_id = uuid4()
        bank_id = uuid4()
        question_id = uuid4()
        bank = QuestionBank(name="Bank", description="", owner_id=owner_id, id=bank_id)
        source = Question(
            id=question_id,
            text="Pregunta original",
            question_type=QuestionType.SINGLE_CHOICE,
            time_seconds=90,
            owner_id=owner_id,
            image_url="/uploads/original.jpg",
            options=[
                QuestionOption(text="A", is_correct=True, order=0),
                QuestionOption(text="B", is_correct=False, order=1),
            ],
        )
        duplicated = Question(
            text="Pregunta original (copia)",
            question_type=QuestionType.SINGLE_CHOICE,
            time_seconds=90,
            owner_id=owner_id,
            image_url="/uploads/copy.jpg",
            options=[
                QuestionOption(text="A", is_correct=True, order=0),
                QuestionOption(text="B", is_correct=False, order=1),
            ],
        )

        bank_repo = MagicMock()
        bank_repo.get_by_id.return_value = bank
        question_repo = MagicMock()
        question_repo.get_by_id_in_bank.return_value = source
        question_repo.create_in_bank.return_value = duplicated

        use_case = DuplicateQuestionUseCase(bank_repo, question_repo, "/tmp/uploads")

        with pytest.MonkeyPatch.context() as mp:
            copy_mock = MagicMock(return_value="/uploads/copy.jpg")
            mp.setattr(
                "app.infrastructure.services.upload_cleanup.copy_uploaded_file",
                copy_mock,
            )
            result = use_case.execute(owner_id, bank_id, question_id)

        assert result.text == "Pregunta original (copia)"
        copy_mock.assert_called_once_with("/tmp/uploads", "/uploads/original.jpg")
        question_repo.create_in_bank.assert_called_once()
        created = question_repo.create_in_bank.call_args[0][1]
        assert created.text == "Pregunta original (copia)"
        assert len(created.options) == 2
        assert created.options[0].text == "A"
        assert created.options[0].is_correct is True

    def test_not_found_when_question_missing(self):
        owner_id = uuid4()
        bank_id = uuid4()
        bank = QuestionBank(name="Bank", description="", owner_id=owner_id, id=bank_id)
        bank_repo = MagicMock()
        bank_repo.get_by_id.return_value = bank
        question_repo = MagicMock()
        question_repo.get_by_id_in_bank.return_value = None

        use_case = DuplicateQuestionUseCase(bank_repo, question_repo, "/tmp/uploads")
        with pytest.raises(NotFoundError, match="Question not found"):
            use_case.execute(owner_id, bank_id, uuid4())


class TestCreateExamUseCase:
    def test_create_exam_random_selection(self):
        owner_id = uuid4()
        bank_id = uuid4()
        bank = QuestionBank(name="Bank", description="", owner_id=owner_id, id=bank_id)
        questions = [
            Question(
                text=f"Q{i}",
                question_type=QuestionType.SINGLE_CHOICE,
                time_seconds=60,
                owner_id=owner_id,
                options=[QuestionOption(text="A", is_correct=True)],
            )
            for i in range(5)
        ]

        exam_repo = MagicMock()
        exam_repo.create.side_effect = lambda e: e
        bank_repo = MagicMock()
        bank_repo.get_by_id.return_value = bank
        question_repo = MagicMock()
        question_repo.list_by_bank.return_value = questions

        use_case = CreateExamUseCase(exam_repo, bank_repo, question_repo)
        exam = use_case.execute(
            owner_id,
            {
                "title": "Test Exam",
                "question_bank_id": bank_id,
                "mode": ExamMode.REAL,
                "total_score": 100,
                "question_count": 3,
                "closes_at": FUTURE_CLOSES_AT,
                "random_selection": True,
            },
        )

        assert exam.title == "Test Exam"
        assert exam.question_count == 3
        assert len(exam.selected_question_ids) == 0
        assert exam.random_selection is True


class TestSubmitAnswerUseCase:
    def test_submit_correct_answer(self):
        owner_id = uuid4()
        question_id = uuid4()
        option_id = uuid4()
        exam_id = uuid4()
        attempt_id = uuid4()

        question = Question(
            id=question_id,
            text="Test",
            question_type=QuestionType.SINGLE_CHOICE,
            time_seconds=60,
            owner_id=owner_id,
            options=[QuestionOption(id=option_id, text="Correct", is_correct=True)],
        )
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=100,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
            selected_question_ids=[question_id],
            question_configs=[
                ExamQuestionConfig(
                    question_id=question_id,
                    order=0,
                    points=100,
                    time_seconds=60,
                )
            ],
        )
        attempt = ExamAttempt(
            id=attempt_id,
            invitation_id=uuid4(),
            exam_id=exam_id,
            status=AttemptStatus.IN_PROGRESS,
            selected_question_ids=[question_id],
            question_configs=[
                ExamQuestionConfig(
                    question_id=question_id,
                    order=0,
                    points=100,
                    time_seconds=60,
                )
            ],
        )

        attempt_repo = MagicMock()
        attempt_repo.get_by_id.return_value = attempt
        answer_repo = MagicMock()
        answer_repo.upsert.side_effect = lambda a: a
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        question_repo = MagicMock()
        question_repo.get_by_id.return_value = question

        use_case = SubmitAnswerUseCase(attempt_repo, answer_repo, exam_repo, question_repo)
        answer = use_case.execute(attempt_id, question_id, [option_id])

        assert answer.is_correct is True
        assert answer.points_earned > 0


class TestGetAttemptAnswersReportUseCase:
    def test_builds_answer_details_for_attempt(self):
        owner_id = uuid4()
        exam_id = uuid4()
        attempt_id = uuid4()
        invitation_id = uuid4()
        question_id = uuid4()
        option_id = uuid4()

        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=10,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
            selected_question_ids=[question_id],
            question_configs=[
                ExamQuestionConfig(question_id=question_id, order=0, points=10, time_seconds=60)
            ],
        )
        attempt = ExamAttempt(
            invitation_id=invitation_id,
            exam_id=exam_id,
            id=attempt_id,
            invitee_full_name="María López",
            score=10,
            selected_question_ids=[question_id],
            question_configs=[
                ExamQuestionConfig(question_id=question_id, order=0, points=10, time_seconds=60)
            ],
        )
        invitation = ExamInvitation(exam_id=exam_id, invitee_email="student@test.com", id=invitation_id)
        question = Question(
            text="2+2?",
            question_type=QuestionType.SINGLE_CHOICE,
            time_seconds=60,
            owner_id=owner_id,
            id=question_id,
            options=[QuestionOption(id=option_id, text="4", is_correct=True)],
        )
        answer = Answer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_option_ids=[option_id],
            is_correct=True,
            points_earned=10,
        )

        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        attempt_repo = MagicMock()
        attempt_repo.get_by_id.return_value = attempt
        invitation_repo = MagicMock()
        invitation_repo.get_by_id.return_value = invitation
        answer_repo = MagicMock()
        answer_repo.get_by_attempt.return_value = [answer]
        question_repo = MagicMock()
        question_repo.list_by_ids.return_value = [question]
        snapshot_repo = MagicMock()
        snapshot_repo.list_by_attempt.return_value = [
            AttemptSnapshot(
                attempt_id=attempt_id,
                snapshot_type=SnapshotType.START,
                image_url="/uploads/start.jpg",
            )
        ]

        use_case = GetAttemptAnswersReportUseCase(
            exam_repo, attempt_repo, invitation_repo, answer_repo, question_repo, snapshot_repo
        )
        report = use_case.execute(owner_id, exam_id, attempt_id)

        assert report["invitee_email"] == "student@test.com"
        assert report["invitee_full_name"] == "María López"
        assert len(report["answers"]) == 1
        assert report["answers"][0]["selected_options"] == ["4"]
        assert report["answers"][0]["is_correct"] is True
        assert len(report["snapshots"]) == 1
        assert report["snapshots"][0]["snapshot_type"] == "start"


class TestSaveAttemptVideoUseCase:
    def test_saves_video_url_for_required_exam(self):
        attempt_id = uuid4()
        exam_id = uuid4()
        attempt = ExamAttempt(
            id=attempt_id,
            invitation_id=uuid4(),
            exam_id=exam_id,
            status=AttemptStatus.IN_PROGRESS,
        )
        exam = Exam(
            title="Exam",
            description="",
            owner_id=uuid4(),
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=10,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            require_attempt_video=True,
            id=exam_id,
        )
        attempt_repo = MagicMock()
        attempt_repo.get_by_id.return_value = attempt
        attempt_repo.update.side_effect = lambda item: item
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam

        use_case = SaveAttemptVideoUseCase(attempt_repo, exam_repo)
        result = use_case.execute(attempt_id, "/uploads/videos/test.webm")

        assert result.attempt_video_url == "/uploads/videos/test.webm"


class TestInviteToExamUseCase:
    @pytest.mark.asyncio
    async def test_blocks_invite_when_email_already_completed(self):
        exam_id = uuid4()
        owner_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=100,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
        )
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        attempt_repo = MagicMock()
        attempt_repo.count_finished_for_email.return_value = 1
        attempt_repo.has_in_progress_attempt_for_email.return_value = False

        use_case = InviteToExamUseCase(
            exam_repo,
            MagicMock(),
            attempt_repo,
            MagicMock(),
            "http://localhost:4200",
        )
        with pytest.raises(ValidationError, match="agotó los intentos"):
            await use_case.execute(owner_id, exam_id, ["student@test.com"])

    @pytest.mark.asyncio
    async def test_blocks_invite_when_email_exam_in_progress(self):
        exam_id = uuid4()
        owner_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=100,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
        )
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        attempt_repo = MagicMock()
        attempt_repo.count_finished_for_email.return_value = 0
        attempt_repo.has_in_progress_attempt_for_email.return_value = True

        use_case = InviteToExamUseCase(
            exam_repo,
            MagicMock(),
            attempt_repo,
            MagicMock(),
            "http://localhost:4200",
        )
        with pytest.raises(ValidationError, match="en progreso"):
            await use_case.execute(owner_id, exam_id, ["student@test.com"])


class TestStartExamAttemptUseCase:
    def test_blocks_duplicate_email_after_completion(self):
        exam_id = uuid4()
        invitation = ExamInvitation(
            exam_id=exam_id,
            invitee_email="student@test.com",
            token="token-2",
        )
        invitation_repo = MagicMock()
        invitation_repo.get_by_token.return_value = invitation
        attempt_repo = MagicMock()
        finished_attempts = [
            ExamAttempt(
                invitation_id=invitation.id,
                exam_id=exam_id,
                status=AttemptStatus.SUBMITTED,
                attempt_number=1,
            )
        ]
        attempt_repo.list_by_email.return_value = finished_attempts
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = Exam(
            title="Exam",
            description="",
            owner_id=uuid4(),
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=100,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            max_attempts=1,
            id=exam_id,
        )

        use_case = StartExamAttemptUseCase(invitation_repo, attempt_repo, exam_repo, MagicMock())
        with pytest.raises(ValidationError, match="Agotó los intentos"):
            use_case.execute("token-2", camera_verified=True, full_name="Juan Pérez")

        attempt_repo.list_by_email.assert_called_once_with(exam_id, "student@test.com")

    def test_blocks_duplicate_email_while_in_progress(self):
        exam_id = uuid4()
        invitation = ExamInvitation(
            exam_id=exam_id,
            invitee_email="student@test.com",
            token="token-2",
        )
        other_invitation_id = uuid4()
        invitation_repo = MagicMock()
        invitation_repo.get_by_token.return_value = invitation
        attempt_repo = MagicMock()
        attempt_repo.list_by_email.return_value = [
            ExamAttempt(
                invitation_id=other_invitation_id,
                exam_id=exam_id,
                status=AttemptStatus.IN_PROGRESS,
                attempt_number=1,
            )
        ]
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = Exam(
            title="Exam",
            description="",
            owner_id=uuid4(),
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=100,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            max_attempts=3,
            id=exam_id,
        )

        use_case = StartExamAttemptUseCase(invitation_repo, attempt_repo, exam_repo, MagicMock())
        with pytest.raises(ValidationError, match="en progreso"):
            use_case.execute("token-2", camera_verified=True, full_name="Juan Pérez")


class TestUpdateExamUseCase:
    def test_update_metadata_when_has_attempts(self):
        exam_id = uuid4()
        owner_id = uuid4()
        exam = Exam(
            title="Old",
            description="Old desc",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=100,
            question_count=5,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
        )
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        exam_repo.update.side_effect = lambda e: e
        attempt_repo = MagicMock()
        attempt_repo.list_by_exam.return_value = [
            ExamAttempt(id=uuid4(), invitation_id=uuid4(), exam_id=exam_id, status=AttemptStatus.SUBMITTED)
        ]

        use_case = UpdateExamUseCase(exam_repo, MagicMock(), MagicMock(), attempt_repo)
        updated = use_case.execute(
            owner_id,
            exam_id,
            {"title": "New", "description": "New desc", "question_bank_id": exam.question_bank_id},
        )
        assert updated.title == "New"
        assert updated.description == "New desc"
        assert updated.total_score == 100

    def test_full_update_when_no_attempts(self):
        exam_id = uuid4()
        owner_id = uuid4()
        bank_id = uuid4()
        bank = QuestionBank(name="Bank", description="", owner_id=owner_id, id=bank_id)
        questions = [
            Question(
                text=f"Q{i}",
                question_type=QuestionType.SINGLE_CHOICE,
                time_seconds=60,
                owner_id=owner_id,
                options=[QuestionOption(text="A", is_correct=True)],
            )
            for i in range(3)
        ]
        exam = Exam(
            title="Old",
            description="",
            owner_id=owner_id,
            question_bank_id=bank_id,
            mode=ExamMode.SIMULATION,
            total_score=50,
            question_count=2,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
        )
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        exam_repo.update.side_effect = lambda e: e
        bank_repo = MagicMock()
        bank_repo.get_by_id.return_value = bank
        question_repo = MagicMock()
        question_repo.list_by_bank.return_value = questions
        question_repo.list_by_ids.return_value = questions[:2]
        attempt_repo = MagicMock()
        attempt_repo.list_by_exam.return_value = []

        use_case = UpdateExamUseCase(exam_repo, bank_repo, question_repo, attempt_repo)
        updated = use_case.execute(
            owner_id,
            exam_id,
            {
                "title": "Updated",
                "description": "Desc",
                "question_bank_id": bank_id,
                "mode": ExamMode.REAL,
                "total_score": 60,
                "question_count": 2,
                "closes_at": FUTURE_CLOSES_AT,
                "random_selection": False,
                "selected_question_ids": [questions[0].id, questions[1].id],
            },
        )
        assert updated.title == "Updated"
        assert updated.mode == ExamMode.REAL
        assert updated.total_score == 60
        assert len(updated.selected_question_ids) == 2


class TestDeleteExamUseCase:
    def test_delete_exam_without_attempts(self):
        exam_id = uuid4()
        owner_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=100,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
        )
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        exam_repo.delete.return_value = True
        attempt_repo = MagicMock()
        attempt_repo.list_by_exam.return_value = []
        snapshot_repo = MagicMock()

        use_case = DeleteExamUseCase(exam_repo, attempt_repo, snapshot_repo, "/tmp/uploads")
        use_case.execute(owner_id, exam_id)
        exam_repo.delete.assert_called_once_with(exam_id)

    def test_deletes_exam_with_attempts_and_cleans_files(self):
        exam_id = uuid4()
        owner_id = uuid4()
        attempt_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=100,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
        )
        attempt = ExamAttempt(
            id=attempt_id,
            invitation_id=uuid4(),
            exam_id=exam_id,
            status=AttemptStatus.SUBMITTED,
            attempt_video_url="/uploads/videos/test.webm",
        )
        snapshot = AttemptSnapshot(
            attempt_id=attempt_id,
            snapshot_type=SnapshotType.START,
            image_url="/uploads/start.jpg",
        )

        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        exam_repo.delete.return_value = True
        attempt_repo = MagicMock()
        attempt_repo.list_by_exam.return_value = [attempt]
        snapshot_repo = MagicMock()
        snapshot_repo.list_by_attempt.return_value = [snapshot]

        use_case = DeleteExamUseCase(exam_repo, attempt_repo, snapshot_repo, "/tmp/uploads")

        with pytest.MonkeyPatch.context() as mp:
            delete_mock = MagicMock()
            mp.setattr(
                "app.infrastructure.services.upload_cleanup.delete_uploaded_file",
                delete_mock,
            )
            use_case.execute(owner_id, exam_id)

        assert delete_mock.call_count == 2
        exam_repo.delete.assert_called_once_with(exam_id)


class TestDeleteExamInvitationUseCase:
    def test_delete_pending_invitation(self):
        exam_id = uuid4()
        owner_id = uuid4()
        invitation_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=100,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
        )
        invitation = ExamInvitation(
            id=invitation_id,
            exam_id=exam_id,
            invitee_email="student@test.com",
        )
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        invitation_repo = MagicMock()
        invitation_repo.get_by_id.return_value = invitation
        invitation_repo.delete.return_value = True
        attempt_repo = MagicMock()
        attempt_repo.list_by_invitation.return_value = []

        use_case = DeleteExamInvitationUseCase(exam_repo, invitation_repo, attempt_repo)
        use_case.execute(owner_id, exam_id, invitation_id)
        invitation_repo.delete.assert_called_once_with(invitation_id)

    def test_blocks_delete_when_exam_in_progress(self):
        exam_id = uuid4()
        owner_id = uuid4()
        invitation_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=100,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
        )
        invitation = ExamInvitation(id=invitation_id, exam_id=exam_id, invitee_email="student@test.com")
        attempt = ExamAttempt(
            id=uuid4(),
            invitation_id=invitation_id,
            exam_id=exam_id,
            status=AttemptStatus.IN_PROGRESS,
        )
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        invitation_repo = MagicMock()
        invitation_repo.get_by_id.return_value = invitation
        attempt_repo = MagicMock()
        attempt_repo.list_by_invitation.return_value = [attempt]

        use_case = DeleteExamInvitationUseCase(exam_repo, invitation_repo, attempt_repo)
        with pytest.raises(ValidationError, match="No se puede eliminar"):
            use_case.execute(owner_id, exam_id, invitation_id)


class TestDeleteInviteeExamResultsUseCase:
    def test_deletes_all_attempts_and_resets_invitation(self):
        exam_id = uuid4()
        owner_id = uuid4()
        invitation_id = uuid4()
        attempt_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=100,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
        )
        attempt = ExamAttempt(
            id=attempt_id,
            invitation_id=invitation_id,
            exam_id=exam_id,
            status=AttemptStatus.SUBMITTED,
            attempt_number=1,
            attempt_video_url="/uploads/videos/test.webm",
        )
        invitation = ExamInvitation(
            id=invitation_id,
            exam_id=exam_id,
            invitee_email="student@test.com",
            status=InvitationStatus.COMPLETED,
            sent_at=datetime.now(timezone.utc),
        )
        snapshot = AttemptSnapshot(
            attempt_id=attempt_id,
            snapshot_type=SnapshotType.START,
            image_url="/uploads/start.jpg",
        )

        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        attempt_repo = MagicMock()
        attempt_repo.list_by_email.return_value = [attempt]
        attempt_repo.delete.return_value = True
        invitation_repo = MagicMock()
        invitation_repo.get_by_exam_and_email.return_value = [invitation]
        snapshot_repo = MagicMock()
        snapshot_repo.list_by_attempt.return_value = [snapshot]

        use_case = DeleteInviteeExamResultsUseCase(
            exam_repo,
            attempt_repo,
            invitation_repo,
            snapshot_repo,
            upload_dir="/tmp/uploads",
        )

        with pytest.MonkeyPatch.context() as mp:
            delete_mock = MagicMock()
            mp.setattr(
                "app.infrastructure.services.upload_cleanup.delete_uploaded_file",
                delete_mock,
            )
            result = use_case.execute(owner_id, exam_id, "student@test.com")

        assert result == {"deleted_attempts": 1}
        attempt_repo.delete.assert_called_once_with(attempt_id)
        assert delete_mock.call_count == 2
        assert invitation.status == InvitationStatus.SENT
        invitation_repo.update.assert_called_once_with(invitation)

    def test_not_found_when_no_attempts(self):
        exam_id = uuid4()
        owner_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=100,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
        )
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        attempt_repo = MagicMock()
        attempt_repo.list_by_email.return_value = []

        use_case = DeleteInviteeExamResultsUseCase(
            exam_repo,
            attempt_repo,
            MagicMock(),
            MagicMock(),
            upload_dir="/tmp/uploads",
        )

        with pytest.raises(NotFoundError, match="No hay resultados"):
            use_case.execute(owner_id, exam_id, "student@test.com")


class TestProctoringAnalysisUseCase:
    def test_fraud_detected(self):
        attempt_id = uuid4()
        attempt = ExamAttempt(
            id=attempt_id,
            invitation_id=uuid4(),
            exam_id=uuid4(),
            status=AttemptStatus.IN_PROGRESS,
        )

        attempt_repo = MagicMock()
        attempt_repo.get_by_id.return_value = attempt
        proctoring_repo = MagicMock()
        proctoring_repo.create.side_effect = lambda e: e

        proctoring_service = MagicMock()
        proctoring_service.analyze_frame.return_value = ProctoringAnalysisResult(
            fraud_detected=True,
            fraud_score=0.8,
            event_type="eye_movement",
            confidence=0.8,
            details={},
        )

        use_case = ProctoringAnalysisUseCase(attempt_repo, proctoring_repo, proctoring_service)
        event = use_case.execute(attempt_id, b"frame_data", [])

        assert event is not None
        assert attempt.fraud_score == 0.8
        attempt_repo.update.assert_called()

    def test_fraud_score_uses_max_confidence_not_cumulative(self):
        attempt_id = uuid4()
        attempt = ExamAttempt(
            id=attempt_id,
            invitation_id=uuid4(),
            exam_id=uuid4(),
            status=AttemptStatus.IN_PROGRESS,
            fraud_score=0.3,
        )

        attempt_repo = MagicMock()
        attempt_repo.get_by_id.return_value = attempt
        proctoring_repo = MagicMock()
        proctoring_repo.create.side_effect = lambda e: e

        proctoring_service = MagicMock()
        proctoring_service.analyze_frame.return_value = ProctoringAnalysisResult(
            fraud_detected=True,
            fraud_score=0.8,
            event_type="eye_movement",
            confidence=0.55,
            details={},
        )

        use_case = ProctoringAnalysisUseCase(attempt_repo, proctoring_repo, proctoring_service)
        use_case.execute(attempt_id, b"frame_data", [])

        assert attempt.fraud_score == 0.55


class TestSubmitExamUseCase:
    def test_caps_score_at_exam_total(self):
        exam_id = uuid4()
        attempt_id = uuid4()
        invitation_id = uuid4()
        attempt = ExamAttempt(
            id=attempt_id,
            invitation_id=invitation_id,
            exam_id=exam_id,
            status=AttemptStatus.IN_PROGRESS,
            attempt_number=1,
        )
        exam = Exam(
            title="Exam",
            description="",
            owner_id=uuid4(),
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=5,
            question_count=5,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            max_attempts=2,
            id=exam_id,
        )
        invitation = ExamInvitation(
            id=invitation_id,
            exam_id=exam_id,
            invitee_email="student@test.com",
            token="token",
            status=InvitationStatus.STARTED,
        )

        attempt_repo = MagicMock()
        attempt_repo.get_by_id.return_value = attempt
        attempt_repo.update.side_effect = lambda item: item
        answer_repo = MagicMock()
        answer_repo.get_by_attempt.return_value = [
            Answer(attempt_id=attempt_id, question_id=uuid4(), points_earned=1.1),
            Answer(attempt_id=attempt_id, question_id=uuid4(), points_earned=1.1),
            Answer(attempt_id=attempt_id, question_id=uuid4(), points_earned=1.1),
            Answer(attempt_id=attempt_id, question_id=uuid4(), points_earned=1.1),
            Answer(attempt_id=attempt_id, question_id=uuid4(), points_earned=1.1),
        ]
        invitation_repo = MagicMock()
        invitation_repo.get_by_id.return_value = invitation
        invitation_repo.update.side_effect = lambda item: item
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        attempt_repo.list_by_email.return_value = []

        use_case = SubmitExamUseCase(attempt_repo, answer_repo, invitation_repo, exam_repo)
        result = use_case.execute(attempt_id)

        assert result.score == 5

    def test_allows_submit_without_video_when_skipped(self):
        exam_id = uuid4()
        attempt_id = uuid4()
        invitation_id = uuid4()
        attempt = ExamAttempt(
            id=attempt_id,
            invitation_id=invitation_id,
            exam_id=exam_id,
            status=AttemptStatus.IN_PROGRESS,
            attempt_number=1,
        )
        exam = Exam(
            title="Exam",
            description="",
            owner_id=uuid4(),
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=5,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            require_attempt_video=True,
            id=exam_id,
        )
        invitation = ExamInvitation(
            id=invitation_id,
            exam_id=exam_id,
            invitee_email="student@test.com",
            token="token",
            status=InvitationStatus.STARTED,
        )

        attempt_repo = MagicMock()
        attempt_repo.get_by_id.return_value = attempt
        attempt_repo.update.side_effect = lambda item: item
        answer_repo = MagicMock()
        answer_repo.get_by_attempt.return_value = []
        invitation_repo = MagicMock()
        invitation_repo.get_by_id.return_value = invitation
        invitation_repo.update.side_effect = lambda item: item
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        attempt_repo.list_by_email.return_value = [attempt]

        use_case = SubmitExamUseCase(attempt_repo, answer_repo, invitation_repo, exam_repo)

        with pytest.raises(ValidationError, match="video"):
            use_case.execute(attempt_id)

        result = use_case.execute(attempt_id, skip_video_required=True)

        assert result.status == AttemptStatus.SUBMITTED
        assert result.attempt_video_url is None


class TestFinishExamEarlyUseCase:
    def test_marks_invitation_completed_with_last_attempt_score(self):
        exam_id = uuid4()
        invitation = ExamInvitation(
            exam_id=exam_id,
            invitee_email="student@test.com",
            token="token-finish",
            status=InvitationStatus.STARTED,
        )
        attempts = [
            ExamAttempt(
                invitation_id=invitation.id,
                exam_id=exam_id,
                status=AttemptStatus.SUBMITTED,
                attempt_number=1,
                score=3.0,
            ),
            ExamAttempt(
                invitation_id=invitation.id,
                exam_id=exam_id,
                status=AttemptStatus.SUBMITTED,
                attempt_number=2,
                score=4.5,
            ),
        ]
        invitation_repo = MagicMock()
        invitation_repo.get_by_token.return_value = invitation
        invitation_repo.update.side_effect = lambda item: item
        attempt_repo = MagicMock()
        attempt_repo.list_by_email.return_value = attempts

        use_case = FinishExamEarlyUseCase(invitation_repo, attempt_repo)
        result = use_case.execute("token-finish")

        assert result["final_score"] == 4.5
        assert result["attempt_number"] == 2
        assert invitation.status == InvitationStatus.COMPLETED


class TestTerminateExamForTabSwitchUseCase:
    def test_submits_attempt_and_blocks_future_attempts(self):
        exam_id = uuid4()
        invitation_id = uuid4()
        attempt_id = uuid4()
        invitation = ExamInvitation(
            id=invitation_id,
            exam_id=exam_id,
            invitee_email="student@test.com",
            token="token-tab",
            status=InvitationStatus.STARTED,
        )
        attempt = ExamAttempt(
            id=attempt_id,
            invitation_id=invitation_id,
            exam_id=exam_id,
            status=AttemptStatus.IN_PROGRESS,
            attempt_number=1,
            score=None,
        )
        submitted = ExamAttempt(
            id=attempt_id,
            invitation_id=invitation_id,
            exam_id=exam_id,
            status=AttemptStatus.SUBMITTED,
            attempt_number=1,
            score=2.0,
        )

        invitation_repo = MagicMock()
        invitation_repo.get_by_token.return_value = invitation
        invitation_repo.get_by_exam_and_email.return_value = [invitation]
        invitation_repo.update.side_effect = lambda item: item

        attempt_repo = MagicMock()
        attempt_repo.list_by_email.side_effect = [
            [attempt],
            [submitted],
        ]
        attempt_repo.update.side_effect = lambda item: item

        proctoring_repo = MagicMock()
        submit_use_case = MagicMock()
        submit_use_case.execute.return_value = submitted

        use_case = TerminateExamForTabSwitchUseCase(
            invitation_repo,
            attempt_repo,
            proctoring_repo,
            submit_use_case,
        )
        result = use_case.execute("token-tab")

        submit_use_case.execute.assert_called_once_with(attempt_id, skip_video_required=True)
        proctoring_repo.create.assert_called_once()
        assert invitation.status == InvitationStatus.COMPLETED
        assert result["terminated_for_violation"] is True
        assert result["exam_finalized"] is True
        assert result["final_score"] == 2.0


class TestGetExamReportUseCase:
    def test_uses_last_attempt_score_per_invitee(self):
        owner_id = uuid4()
        exam_id = uuid4()
        invitation_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=5,
            question_count=2,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            max_attempts=3,
            id=exam_id,
        )
        invitation = ExamInvitation(
            id=invitation_id,
            exam_id=exam_id,
            invitee_email="student@test.com",
            token="token",
            status=InvitationStatus.STARTED,
        )
        attempt_one_id = uuid4()
        attempt_two_id = uuid4()
        attempts = [
            ExamAttempt(
                id=attempt_one_id,
                invitation_id=invitation_id,
                exam_id=exam_id,
                status=AttemptStatus.SUBMITTED,
                attempt_number=1,
                score=3.0,
            ),
            ExamAttempt(
                id=attempt_two_id,
                invitation_id=invitation_id,
                exam_id=exam_id,
                status=AttemptStatus.SUBMITTED,
                attempt_number=2,
                score=4.0,
            ),
        ]

        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        attempt_repo = MagicMock()
        attempt_repo.list_by_exam.return_value = attempts
        invitation_repo = MagicMock()
        invitation_repo.list_by_exam.return_value = [invitation]
        answer_repo = MagicMock()
        answer_repo.get_by_attempt.return_value = []
        proctoring_repo = MagicMock()
        proctoring_repo.list_by_attempt.return_value = []

        use_case = GetExamReportUseCase(
            exam_repo, attempt_repo, invitation_repo, answer_repo, proctoring_repo
        )
        report = use_case.execute(owner_id, exam_id)

        assert len(report["individual_reports"]) == 1
        assert report["individual_reports"][0]["score"] == 4.0
        assert report["individual_reports"][0]["attempt_number"] == 2
        assert report["individual_reports"][0]["attempt_id"] == str(attempt_two_id)
        assert report["summary"]["average_score"] == 4.0

    def test_uses_final_attempt_fraud_only(self):
        owner_id = uuid4()
        exam_id = uuid4()
        invitation_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=5,
            question_count=2,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            max_attempts=3,
            id=exam_id,
        )
        invitation = ExamInvitation(
            id=invitation_id,
            exam_id=exam_id,
            invitee_email="student@test.com",
            token="token",
            status=InvitationStatus.COMPLETED,
        )
        attempt_one_id = uuid4()
        attempt_two_id = uuid4()
        attempts = [
            ExamAttempt(
                id=attempt_one_id,
                invitation_id=invitation_id,
                exam_id=exam_id,
                status=AttemptStatus.SUBMITTED,
                attempt_number=1,
                score=3.0,
                fraud_score=0.95,
            ),
            ExamAttempt(
                id=attempt_two_id,
                invitation_id=invitation_id,
                exam_id=exam_id,
                status=AttemptStatus.SUBMITTED,
                attempt_number=2,
                score=4.0,
                fraud_score=0.15,
            ),
        ]

        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        attempt_repo = MagicMock()
        attempt_repo.list_by_exam.return_value = attempts
        invitation_repo = MagicMock()
        invitation_repo.list_by_exam.return_value = [invitation]
        answer_repo = MagicMock()
        answer_repo.get_by_attempt.return_value = []

        def list_events(attempt_id):
            if attempt_id == attempt_one_id:
                return [
                    ProctoringEvent(
                        attempt_id=attempt_one_id,
                        event_type=ProctoringEventType.EYE_MOVEMENT,
                        confidence=0.95,
                    )
                ]
            return [
                ProctoringEvent(
                    attempt_id=attempt_two_id,
                    event_type=ProctoringEventType.NO_FACE,
                    confidence=0.15,
                )
            ]

        proctoring_repo = MagicMock()
        proctoring_repo.list_by_attempt.side_effect = list_events

        use_case = GetExamReportUseCase(
            exam_repo, attempt_repo, invitation_repo, answer_repo, proctoring_repo
        )
        report = use_case.execute(owner_id, exam_id)

        row = report["individual_reports"][0]
        assert row["attempt_number"] == 2
        assert row["fraud_score"] == 0.15
        proctoring_repo.list_by_attempt.assert_called_with(attempt_two_id)

    def test_counts_only_attempt_questions(self):
        owner_id = uuid4()
        exam_id = uuid4()
        invitation_id = uuid4()
        question_ids = [uuid4() for _ in range(10)]
        extra_question_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=10,
            question_count=10,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=exam_id,
        )
        invitation = ExamInvitation(
            id=invitation_id,
            exam_id=exam_id,
            invitee_email="student@test.com",
            token="token",
            status=InvitationStatus.COMPLETED,
        )
        attempt = ExamAttempt(
            id=uuid4(),
            invitation_id=invitation_id,
            exam_id=exam_id,
            status=AttemptStatus.SUBMITTED,
            attempt_number=1,
            score=10.0,
            selected_question_ids=question_ids,
            question_configs=[
                ExamQuestionConfig(question_id=question_id, order=index, points=1, time_seconds=60)
                for index, question_id in enumerate(question_ids)
            ],
        )
        answers = [
            Answer(
                attempt_id=attempt.id,
                question_id=question_id,
                selected_option_ids=[],
                is_correct=True,
            )
            for question_id in question_ids
        ] + [
            Answer(
                attempt_id=attempt.id,
                question_id=extra_question_id,
                selected_option_ids=[],
                is_correct=True,
            )
        ]

        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        attempt_repo = MagicMock()
        attempt_repo.list_by_exam.return_value = [attempt]
        invitation_repo = MagicMock()
        invitation_repo.list_by_exam.return_value = [invitation]
        answer_repo = MagicMock()
        answer_repo.get_by_attempt.return_value = answers
        proctoring_repo = MagicMock()
        proctoring_repo.list_by_attempt.return_value = []

        use_case = GetExamReportUseCase(
            exam_repo, attempt_repo, invitation_repo, answer_repo, proctoring_repo
        )
        report = use_case.execute(owner_id, exam_id)

        row = report["individual_reports"][0]
        assert row["correct_answers_count"] == 10
        assert row["incorrect_answers_count"] == 0
        assert row["answers_count"] == 10


class TestSaveAttemptSnapshotUseCase:
    def test_saves_start_snapshot(self):
        attempt_id = uuid4()
        attempt = ExamAttempt(
            id=attempt_id,
            invitation_id=uuid4(),
            exam_id=uuid4(),
            status=AttemptStatus.IN_PROGRESS,
        )
        attempt_repo = MagicMock()
        attempt_repo.get_by_id.return_value = attempt
        snapshot_repo = MagicMock()
        snapshot_repo.count_by_type.return_value = 0
        snapshot_repo.create.side_effect = lambda snapshot: snapshot

        use_case = SaveAttemptSnapshotUseCase(attempt_repo, snapshot_repo)
        result = use_case.execute(attempt_id, SnapshotType.START, "/uploads/start.jpg")

        assert result.image_url == "/uploads/start.jpg"
        snapshot_repo.create.assert_called_once()

    def test_blocks_duplicate_start_snapshot(self):
        attempt_id = uuid4()
        attempt = ExamAttempt(
            id=attempt_id,
            invitation_id=uuid4(),
            exam_id=uuid4(),
            status=AttemptStatus.IN_PROGRESS,
        )
        attempt_repo = MagicMock()
        attempt_repo.get_by_id.return_value = attempt
        snapshot_repo = MagicMock()
        snapshot_repo.count_by_type.return_value = 1

        use_case = SaveAttemptSnapshotUseCase(attempt_repo, snapshot_repo)
        with pytest.raises(ValidationError, match="Start snapshot"):
            use_case.execute(attempt_id, SnapshotType.START, "/uploads/start.jpg")
