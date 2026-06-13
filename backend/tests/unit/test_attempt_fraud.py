from uuid import uuid4

from app.application.attempt_fraud import compute_attempt_fraud_score, resolve_final_attempt
from app.domain.entities import ExamAttempt, ProctoringEvent
from app.domain.enums import AttemptStatus, ProctoringEventType


class TestResolveFinalAttempt:
    def test_returns_highest_attempt_number(self):
        attempts = [
            ExamAttempt(
                invitation_id=uuid4(),
                exam_id=uuid4(),
                attempt_number=1,
                status=AttemptStatus.SUBMITTED,
            ),
            ExamAttempt(
                invitation_id=uuid4(),
                exam_id=uuid4(),
                attempt_number=2,
                status=AttemptStatus.SUBMITTED,
            ),
        ]

        final_attempt = resolve_final_attempt(attempts)

        assert final_attempt is not None
        assert final_attempt.attempt_number == 2

    def test_returns_none_when_no_attempts(self):
        assert resolve_final_attempt([]) is None


class TestComputeAttemptFraudScore:
    def test_uses_max_confidence_instead_of_accumulating_events(self):
        attempt = ExamAttempt(
            invitation_id=uuid4(),
            exam_id=uuid4(),
            status=AttemptStatus.SUBMITTED,
            fraud_score=0.95,
        )
        events = [
            ProctoringEvent(
                attempt_id=attempt.id,
                event_type=ProctoringEventType.EYE_MOVEMENT,
                confidence=0.4,
            ),
            ProctoringEvent(
                attempt_id=attempt.id,
                event_type=ProctoringEventType.NO_FACE,
                confidence=0.55,
            ),
        ]

        assert compute_attempt_fraud_score(attempt, events) == 0.55

    def test_falls_back_to_attempt_score_without_events(self):
        attempt = ExamAttempt(
            invitation_id=uuid4(),
            exam_id=uuid4(),
            status=AttemptStatus.SUBMITTED,
            fraud_score=0.35,
        )

        assert compute_attempt_fraud_score(attempt, []) == 0.35

    def test_caps_score_at_one(self):
        attempt = ExamAttempt(
            invitation_id=uuid4(),
            exam_id=uuid4(),
            status=AttemptStatus.SUBMITTED,
            fraud_score=1.4,
        )

        assert compute_attempt_fraud_score(attempt, []) == 1.0
