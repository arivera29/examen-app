from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.application.exam_timing import (
    get_remaining_seconds,
    get_total_exam_seconds,
    is_exam_closed,
    is_exam_not_yet_open,
)
from app.domain.entities import Exam, ExamAttempt, ExamQuestionConfig
from app.domain.enums import ExamMode


def _exam_with_configs(total_time: int, closes_in_hours: int | None = 24) -> Exam:
    closes_at = datetime.now(timezone.utc) + timedelta(hours=closes_in_hours or 24)
    return Exam(
        title="Exam",
        description="",
        owner_id=uuid4(),
        question_bank_id=uuid4(),
        mode=ExamMode.REAL,
        total_score=100,
        question_count=2,
        closes_at=closes_at,
        random_selection=True,
        question_configs=[
            ExamQuestionConfig(question_id=uuid4(), order=0, points=50, time_seconds=60),
            ExamQuestionConfig(question_id=uuid4(), order=1, points=50, time_seconds=90),
        ],
    )


def test_total_exam_seconds_sums_question_times():
    exam = _exam_with_configs(150)
    assert get_total_exam_seconds(exam) == 150


def test_remaining_seconds_before_start_uses_total():
    exam = _exam_with_configs(150)
    assert get_remaining_seconds(exam) == 150


def test_remaining_seconds_after_start():
    exam = _exam_with_configs(150)
    attempt = ExamAttempt(
        invitation_id=uuid4(),
        exam_id=uuid4(),
        started_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    remaining = get_remaining_seconds(exam, attempt)
    assert 115 <= remaining <= 125


def test_is_exam_closed():
    exam = _exam_with_configs(150, closes_in_hours=-1)
    assert is_exam_closed(exam) is True


def test_is_exam_not_yet_open():
    exam = _exam_with_configs(150, closes_in_hours=24)
    exam.starts_at = datetime.now(timezone.utc) + timedelta(hours=2)
    assert is_exam_not_yet_open(exam) is True
    assert is_exam_closed(exam) is False


def test_exam_within_window_after_start():
    exam = _exam_with_configs(150, closes_in_hours=24)
    exam.starts_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert is_exam_not_yet_open(exam) is False
    assert is_exam_closed(exam) is False
