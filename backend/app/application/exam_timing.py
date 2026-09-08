from datetime import datetime, timezone

from app.application.attempt_questions import get_attempt_question_configs
from app.domain.entities import Exam, ExamAttempt, Question


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_total_exam_seconds(
    exam: Exam,
    attempt: ExamAttempt | None = None,
    bank_questions: list[Question] | None = None,
) -> int:
    configs = get_attempt_question_configs(exam, attempt)
    if configs:
        return sum(config.time_seconds for config in configs)

    if exam.random_selection and bank_questions and exam.question_count:
        average_time = sum(question.time_seconds for question in bank_questions) / len(bank_questions)
        return int(average_time * exam.question_count)

    return sum(config.time_seconds for config in exam.question_configs)


def get_remaining_seconds(
    exam: Exam,
    attempt: ExamAttempt | None = None,
    bank_questions: list[Question] | None = None,
) -> int:
    total = get_total_exam_seconds(exam, attempt, bank_questions)
    now = datetime.now(timezone.utc)

    remaining_until_close = total
    if exam.closes_at:
        closes = _ensure_utc(exam.closes_at)
        remaining_until_close = max(0, int((closes - now).total_seconds()))

    if not attempt or not attempt.started_at:
        return min(total, remaining_until_close) if exam.closes_at else total

    started = _ensure_utc(attempt.started_at)
    elapsed = (now - started).total_seconds()
    remaining_from_duration = max(0, int(total - elapsed))

    if exam.closes_at:
        return min(remaining_from_duration, remaining_until_close)
    return remaining_from_duration


def get_current_question_remaining_seconds(
    exam: Exam,
    attempt: ExamAttempt,
    questions: list[Question],
) -> int | None:
    if not exam.enforce_question_time or not attempt.current_question_started_at:
        return None
    if not questions:
        return None

    index = min(max(attempt.current_question_index, 0), len(questions) - 1)
    question = questions[index]
    started = _ensure_utc(attempt.current_question_started_at)
    elapsed = int((datetime.now(timezone.utc) - started).total_seconds())
    return max(0, question.time_seconds - elapsed)


def is_exam_time_expired(
    exam: Exam,
    attempt: ExamAttempt,
    bank_questions: list[Question] | None = None,
) -> bool:
    return get_remaining_seconds(exam, attempt, bank_questions) <= 0


def is_exam_closed(exam: Exam, now: datetime | None = None) -> bool:
    if not exam.closes_at:
        return False
    reference = now or datetime.now(timezone.utc)
    return reference >= _ensure_utc(exam.closes_at)


def is_exam_not_yet_open(exam: Exam, now: datetime | None = None) -> bool:
    if not exam.starts_at:
        return False
    reference = now or datetime.now(timezone.utc)
    return reference < _ensure_utc(exam.starts_at)


def is_exam_within_access_window(exam: Exam, now: datetime | None = None) -> bool:
    reference = now or datetime.now(timezone.utc)
    return not is_exam_not_yet_open(exam, reference) and not is_exam_closed(exam, reference)
