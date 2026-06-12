from datetime import datetime, timedelta, timezone

from app.application.attempt_access import is_finished_attempt
from app.domain.entities import Exam, ExamAttempt, ExamInvitation
from app.domain.enums import InvitationStatus

ATTEMPT_DECISION_TIMEOUT_SECONDS = 300


def get_last_finished_attempt(email_attempts: list[ExamAttempt]) -> ExamAttempt | None:
    finished = [attempt for attempt in email_attempts if is_finished_attempt(attempt)]
    if not finished:
        return None
    return max(finished, key=lambda attempt: attempt.attempt_number)


def pending_attempt_decision(
    invitation: ExamInvitation,
    in_progress: ExamAttempt | None,
    can_start_new_attempt: bool,
    can_finish_early: bool,
    last_finished: ExamAttempt | None,
) -> bool:
    if invitation.status == InvitationStatus.COMPLETED or in_progress is not None:
        return False
    if not can_finish_early and not can_start_new_attempt:
        return False
    if not last_finished or not last_finished.submitted_at:
        return False
    return True


def compute_decision_deadline(submitted_at: datetime) -> datetime:
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=timezone.utc)
    return submitted_at + timedelta(seconds=ATTEMPT_DECISION_TIMEOUT_SECONDS)


def compute_decision_seconds_remaining(submitted_at: datetime | None) -> int | None:
    if not submitted_at:
        return None
    deadline = compute_decision_deadline(submitted_at)
    now = datetime.now(timezone.utc)
    return max(0, int((deadline - now).total_seconds()))
