from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.application.attempt_decision import build_decision_deadline
from app.application.use_cases import PrepareNextAttemptUseCase, ValidationError
from app.domain.entities import Exam, ExamAttempt, ExamInvitation
from app.domain.enums import AttemptStatus, ExamMode, InvitationStatus


FUTURE_CLOSES_AT = None


class TestPrepareNextAttemptUseCase:
    def test_clears_decision_deadline(self):
        exam_id = uuid4()
        invitation = ExamInvitation(
            id=uuid4(),
            exam_id=exam_id,
            invitee_email="student@test.com",
            token="token",
            status=InvitationStatus.STARTED,
            decision_deadline_at=build_decision_deadline(),
        )
        finished_attempt = ExamAttempt(
            invitation_id=invitation.id,
            exam_id=exam_id,
            status=AttemptStatus.SUBMITTED,
            attempt_number=1,
        )

        invitation_repo = MagicMock()
        invitation_repo.get_by_token.return_value = invitation
        invitation_repo.update.side_effect = lambda item: item
        attempt_repo = MagicMock()
        attempt_repo.list_by_email.return_value = [finished_attempt]
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = Exam(
            title="Exam",
            description="",
            owner_id=uuid4(),
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=5,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            max_attempts=3,
            id=exam_id,
        )

        use_case = PrepareNextAttemptUseCase(invitation_repo, attempt_repo, exam_repo)
        result = use_case.execute("token")

        assert result == {"prepared": True}
        assert invitation.decision_deadline_at is None
        invitation_repo.update.assert_called_once()

    def test_rejects_when_attempt_in_progress(self):
        exam_id = uuid4()
        invitation = ExamInvitation(
            id=uuid4(),
            exam_id=exam_id,
            invitee_email="student@test.com",
            token="token",
            status=InvitationStatus.STARTED,
        )
        in_progress = ExamAttempt(
            invitation_id=invitation.id,
            exam_id=exam_id,
            status=AttemptStatus.IN_PROGRESS,
            attempt_number=2,
        )

        invitation_repo = MagicMock()
        invitation_repo.get_by_token.return_value = invitation
        attempt_repo = MagicMock()
        attempt_repo.list_by_email.return_value = [
            ExamAttempt(
                invitation_id=invitation.id,
                exam_id=exam_id,
                status=AttemptStatus.SUBMITTED,
                attempt_number=1,
            ),
            in_progress,
        ]
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = Exam(
            title="Exam",
            description="",
            owner_id=uuid4(),
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=5,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            max_attempts=3,
            id=exam_id,
        )

        use_case = PrepareNextAttemptUseCase(invitation_repo, attempt_repo, exam_repo)
        with pytest.raises(ValidationError, match="en progreso"):
            use_case.execute("token")
