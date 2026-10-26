from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.application.use_cases import (
    MouseIntegrityAnalysisUseCase,
    RecordIntegrityEventUseCase,
    ValidationError,
)
from app.domain.entities import Exam, ExamAttempt
from app.domain.enums import AttemptStatus, ExamMode, ProctoringEventType
from app.domain.services import ProctoringAnalysisResult

FUTURE_CLOSES_AT = datetime.now(timezone.utc) + timedelta(days=7)


def _exam(owner_id, require_camera: bool = False, sensitivity: float = 0.8):
    return Exam(
        title="Exam",
        description="",
        owner_id=owner_id,
        question_bank_id=uuid4(),
        mode=ExamMode.REAL,
        total_score=10,
        question_count=1,
        closes_at=FUTURE_CLOSES_AT,
        random_selection=True,
        require_camera=require_camera,
        proctoring_sensitivity=sensitivity,
        id=uuid4(),
    )


def _attempt(exam_id):
    return ExamAttempt(
        invitation_id=uuid4(),
        exam_id=exam_id,
        id=uuid4(),
        status=AttemptStatus.IN_PROGRESS,
        fraud_score=0.0,
    )


class TestRecordIntegrityEventUseCase:
    def test_records_clipboard_without_camera(self):
        owner_id = uuid4()
        exam = _exam(owner_id, require_camera=False)
        attempt = _attempt(exam.id)

        attempt_repo = MagicMock()
        attempt_repo.get_by_id.return_value = attempt
        attempt_repo.update.side_effect = lambda a: a
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        proctoring_repo = MagicMock()
        proctoring_repo.create.side_effect = lambda e: e

        use_case = RecordIntegrityEventUseCase(
            attempt_repo, exam_repo, proctoring_repo, fraud_threshold=0.5
        )
        event = use_case.execute(
            attempt.id,
            ProctoringEventType.CLIPBOARD_COPY.value,
            0.8,
            {"target": "exam_content"},
        )

        assert event is not None
        assert event.event_type == ProctoringEventType.CLIPBOARD_COPY
        assert attempt.fraud_score > 0
        proctoring_repo.create.assert_called_once()

    def test_rejects_camera_only_event_types(self):
        owner_id = uuid4()
        exam = _exam(owner_id)
        attempt = _attempt(exam.id)
        attempt_repo = MagicMock()
        attempt_repo.get_by_id.return_value = attempt
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam

        use_case = RecordIntegrityEventUseCase(
            attempt_repo, exam_repo, MagicMock(), fraud_threshold=0.5
        )
        with pytest.raises(ValidationError):
            use_case.execute(attempt.id, ProctoringEventType.NO_FACE.value, 0.9, {})


class TestMouseIntegrityAnalysisUseCase:
    def test_flags_mouse_anomaly_without_camera(self):
        owner_id = uuid4()
        exam = _exam(owner_id, require_camera=False, sensitivity=0.9)
        attempt = _attempt(exam.id)

        attempt_repo = MagicMock()
        attempt_repo.get_by_id.return_value = attempt
        attempt_repo.update.side_effect = lambda a: a
        exam_repo = MagicMock()
        exam_repo.get_by_id.return_value = exam
        proctoring_repo = MagicMock()
        proctoring_repo.create.side_effect = lambda e: e
        proctoring_service = MagicMock()
        proctoring_service.analyze_mouse_pattern.return_value = ProctoringAnalysisResult(
            fraud_detected=True,
            fraud_score=0.65,
            event_type=ProctoringEventType.MOUSE_ANOMALY.value,
            confidence=0.65,
            details={"max_velocity": 200},
        )

        use_case = MouseIntegrityAnalysisUseCase(
            attempt_repo,
            exam_repo,
            proctoring_repo,
            proctoring_service,
            fraud_threshold=0.5,
        )
        event = use_case.execute(attempt.id, [{"x": 0, "y": 0, "t": 0}, {"x": 500, "y": 0, "t": 1}])

        assert event is not None
        assert event.event_type == ProctoringEventType.MOUSE_ANOMALY
        assert attempt.fraud_score > 0
