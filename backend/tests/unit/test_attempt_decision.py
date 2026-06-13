from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.application.attempt_decision import (
    ATTEMPT_DECISION_TIMEOUT_SECONDS,
    build_decision_deadline,
    compute_decision_seconds_remaining,
    pending_attempt_decision,
)
from app.domain.entities import ExamAttempt, ExamInvitation
from app.domain.enums import AttemptStatus, InvitationStatus


class TestAttemptDecision:
    def test_pending_when_deadline_is_set(self):
        invitation = ExamInvitation(
            exam_id=uuid4(),
            invitee_email="student@test.com",
            status=InvitationStatus.STARTED,
            decision_deadline_at=build_decision_deadline(),
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

    def test_not_pending_when_deadline_cleared(self):
        invitation = ExamInvitation(
            exam_id=uuid4(),
            invitee_email="student@test.com",
            status=InvitationStatus.STARTED,
            decision_deadline_at=None,
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
            can_start_new_attempt=True,
            can_finish_early=True,
            last_finished=last_finished,
        )

    def test_seconds_remaining_decreases_over_time(self):
        deadline = datetime.now(timezone.utc) + timedelta(seconds=60)
        remaining = compute_decision_seconds_remaining(deadline)
        assert remaining is not None
        assert 59 <= remaining <= 61

    def test_seconds_remaining_is_zero_after_timeout(self):
        deadline = datetime.now(timezone.utc) - timedelta(seconds=5)
        assert compute_decision_seconds_remaining(deadline) == 0
