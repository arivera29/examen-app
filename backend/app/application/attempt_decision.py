from datetime import datetime, timedelta, timezone

from app.application.attempt_access import is_finished_attempt
from app.domain.entities import ExamAttempt, ExamInvitation
from app.domain.enums import InvitationStatus

ATTEMPT_DECISION_TIMEOUT_SECONDS = 300


def get_last_finished_attempt(email_attempts: list[ExamAttempt]) -> ExamAttempt | None:
    finished = [attempt for attempt in email_attempts if is_finished_attempt(attempt)]
    if not finished:
        return None
    return max(finished, key=lambda attempt: attempt.attempt_number)


def build_decision_deadline(from_time: datetime | None = None) -> datetime:
    base = from_time or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(seconds=ATTEMPT_DECISION_TIMEOUT_SECONDS)


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
    if not last_finished:
        return False
    return invitation.decision_deadline_at is not None


def compute_decision_seconds_remaining(deadline: datetime | None) -> int | None:
    if not deadline:
        return None
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max(0, int((deadline - now).total_seconds()))
