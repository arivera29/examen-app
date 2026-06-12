from app.domain.entities import Exam, ExamAttempt, ExamInvitation
from app.domain.enums import AttemptPolicy, AttemptStatus

FINISHED_STATUSES = frozenset({AttemptStatus.SUBMITTED, AttemptStatus.TIMED_OUT})


def is_finished_attempt(attempt: ExamAttempt) -> bool:
    return attempt.status in FINISHED_STATUSES


def count_finished_attempts(attempts: list[ExamAttempt]) -> int:
    return sum(1 for attempt in attempts if is_finished_attempt(attempt))


def get_in_progress_attempt(attempts: list[ExamAttempt]) -> ExamAttempt | None:
    return next((attempt for attempt in attempts if attempt.status == AttemptStatus.IN_PROGRESS), None)


def resolve_attempt_start(
    exam: Exam,
    invitation: ExamInvitation,
    email_attempts: list[ExamAttempt],
) -> tuple[str, ExamAttempt | None, int | None]:
    in_progress = get_in_progress_attempt(email_attempts)
    if in_progress:
        if in_progress.invitation_id != invitation.id:
            return "blocked_other_progress", in_progress, None
        return "resume", in_progress, None

    finished = sorted(
        [attempt for attempt in email_attempts if is_finished_attempt(attempt)],
        key=lambda attempt: attempt.attempt_number,
    )
    if len(finished) >= exam.max_attempts:
        return "blocked_exhausted", None, None

    next_number = len(finished) + 1
    if exam.attempt_policy == AttemptPolicy.SEQUENTIAL:
        expected_numbers = list(range(1, len(finished) + 1))
        actual_numbers = [attempt.attempt_number for attempt in finished]
        if actual_numbers != expected_numbers:
            return "blocked_sequence", None, None

    return "create", None, next_number


def has_exhausted_attempts(exam: Exam, email_attempts: list[ExamAttempt]) -> bool:
    return count_finished_attempts(email_attempts) >= exam.max_attempts
