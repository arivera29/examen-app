from uuid import uuid4

from app.application.exam_session import resolve_resume_state
from app.domain.entities import Answer, Exam, ExamAttempt, ExamQuestionConfig
from app.domain.enums import ExamMode
from datetime import datetime, timedelta, timezone

FUTURE_CLOSES_AT = datetime.now(timezone.utc) + timedelta(days=7)


class TestResolveResumeState:
    def test_uses_saved_progress_when_available(self):
        question_ids = [uuid4(), uuid4(), uuid4()]
        attempt = ExamAttempt(
            invitation_id=uuid4(),
            exam_id=uuid4(),
            current_question_index=2,
            locked_question_ids=[question_ids[0], question_ids[1]],
            current_question_started_at=datetime.now(timezone.utc),
        )
        exam = Exam(
            title="Exam",
            description="",
            owner_id=uuid4(),
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=3,
            question_count=3,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            enforce_question_time=True,
        )

        current_index, locked = resolve_resume_state(exam, attempt, question_ids, [])

        assert current_index == 2
        assert locked == [question_ids[0], question_ids[1]]

    def test_infers_first_unanswered_for_free_navigation(self):
        question_ids = [uuid4(), uuid4(), uuid4()]
        attempt = ExamAttempt(invitation_id=uuid4(), exam_id=uuid4())
        exam = Exam(
            title="Exam",
            description="",
            owner_id=uuid4(),
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=3,
            question_count=3,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            enforce_question_time=False,
        )
        answers = [
            Answer(attempt_id=attempt.id, question_id=question_ids[0], selected_option_ids=[uuid4()]),
            Answer(attempt_id=attempt.id, question_id=question_ids[1], selected_option_ids=[uuid4()]),
        ]

        current_index, locked = resolve_resume_state(exam, attempt, question_ids, answers)

        assert current_index == 2
        assert locked == []
