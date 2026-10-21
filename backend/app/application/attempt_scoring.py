"""Scoring helpers for exam attempts."""

from uuid import UUID

from app.application.attempt_questions import (
    distribute_question_points,
    resolve_attempt_question_configs,
)
from app.domain.entities import Answer, Exam, ExamAttempt

__all__ = [
    "compute_attempt_score",
    "distribute_question_points",
    "points_for_question",
]


def points_for_question(exam: Exam, attempt: ExamAttempt, question_id: UUID) -> float:
    configs = resolve_attempt_question_configs(exam, attempt)
    for config in configs:
        if config.question_id == question_id:
            return float(config.points)
    if exam.question_count > 0:
        return float(exam.total_score) / float(exam.question_count)
    return 0.0


def compute_attempt_score(
    exam: Exam,
    attempt: ExamAttempt,
    answers: list[Answer],
) -> float:
    """Authoritative score: sum config points for correct answers only.

    Unanswered questions (no answer, or is_correct is None) contribute 0.
    Incorrect answers contribute 0.
    """
    configs = resolve_attempt_question_configs(exam, attempt)
    configs_by_id = {config.question_id: config for config in configs}
    allowed_ids = set(configs_by_id.keys())

    total = 0.0
    seen: set[UUID] = set()
    for answer in answers:
        if answer.question_id in seen:
            continue
        if allowed_ids and answer.question_id not in allowed_ids:
            continue
        seen.add(answer.question_id)
        if answer.is_correct is not True:
            continue
        config = configs_by_id.get(answer.question_id)
        if config is not None:
            total += float(config.points)
        else:
            total += float(answer.points_earned)

    return min(round(total, 2), float(exam.total_score))
