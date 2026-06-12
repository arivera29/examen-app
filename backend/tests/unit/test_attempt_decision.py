from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.application.attempt_decision import (
    ATTEMPT_DECISION_TIMEOUT_SECONDS,
    compute_decision_seconds_remaining,
    pending_attempt_decision,
)
from app.domain.entities import ExamAttempt, ExamInvitation
from app.domain.enums import AttemptStatus, InvitationStatus


class TestAttemptDecision:
    def test_pending_when_choice_available(self):
        invitation = ExamInvitation(
            exam_id=uuid4(),
            invitee_email="student@test.com",
            status=InvitationStatus.STARTED,
        )
        last_finished = ExamAttempt(
            invitation_id=invitation.id,
            exam_id=invitation.exam_id,
            status=AttemptStatus.SUBMITTED,
            submitted_at=datetime.now(timezone.utc),
        )

        assert pending_attempt_decision(
            invitation,
            None,
            can_start_new_attempt=True,
            can_finish_early=True,
            last_finished=last_finished,
        )

    def test_not_pending_when_exam_finalized(self):
        invitation = ExamInvitation(
            exam_id=uuid4(),
            invitee_email="student@test.com",
            status=InvitationStatus.COMPLETED,
        )
        last_finished = ExamAttempt(
            invitation_id=invitation.id,
            exam_id=invitation.exam_id,
            status=AttemptStatus.SUBMITTED,
            submitted_at=datetime.now(timezone.utc),
        )

        assert not pending_attempt_decision(
            invitation,
            None,
            can_start_new_attempt=False,
            can_finish_early=False,
            last_finished=last_finished,
        )

    def test_seconds_remaining_decreases_over_time(self):
        submitted_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        remaining = compute_decision_seconds_remaining(submitted_at)
        assert remaining is not None
        assert ATTEMPT_DECISION_TIMEOUT_SECONDS - 61 <= remaining <= ATTEMPT_DECISION_TIMEOUT_SECONDS - 59

    def test_seconds_remaining_is_zero_after_timeout(self):
        submitted_at = datetime.now(timezone.utc) - timedelta(
            seconds=ATTEMPT_DECISION_TIMEOUT_SECONDS + 5
        )
        assert compute_decision_seconds_remaining(submitted_at) == 0
