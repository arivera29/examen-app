from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.application.attempt_access import (
    compute_attempt_cooldown_remaining_seconds,
    resolve_attempt_start,
)
from app.domain.entities import Exam, ExamAttempt, ExamInvitation
from app.domain.enums import AttemptPolicy, AttemptStatus, ExamMode


def _exam(max_attempts: int = 3, policy: AttemptPolicy = AttemptPolicy.FLEXIBLE) -> Exam:
    return Exam(
        title="Test",
        description="",
        owner_id=uuid4(),
        question_bank_id=uuid4(),
        mode=ExamMode.SIMULATION,
        total_score=100,
        question_count=1,
        closes_at=__import__("datetime").datetime(2099, 1, 1, tzinfo=__import__("datetime").timezone.utc),
        random_selection=True,
        max_attempts=max_attempts,
        attempt_policy=policy,
    )


def _invitation() -> ExamInvitation:
    return ExamInvitation(exam_id=uuid4(), invitee_email="student@test.com")


def test_resolve_attempt_start_creates_first_attempt():
    exam = _exam()
    invitation = _invitation()
    action, attempt, next_number = resolve_attempt_start(exam, invitation, [])

    assert action == "create"
    assert attempt is None
    assert next_number == 1


def test_resolve_attempt_start_resumes_in_progress():
    exam = _exam()
    invitation = _invitation()
    in_progress = ExamAttempt(
        invitation_id=invitation.id,
        exam_id=invitation.exam_id,
        status=AttemptStatus.IN_PROGRESS,
        attempt_number=1,
    )
    action, attempt, next_number = resolve_attempt_start(exam, invitation, [in_progress])

    assert action == "resume"
    assert attempt == in_progress
    assert next_number is None


def test_resolve_attempt_start_blocks_when_exhausted():
    exam = _exam(max_attempts=2)
    invitation = _invitation()
    finished = [
        ExamAttempt(
            invitation_id=invitation.id,
            exam_id=invitation.exam_id,
            status=AttemptStatus.SUBMITTED,
            attempt_number=1,
        ),
        ExamAttempt(
            invitation_id=invitation.id,
            exam_id=invitation.exam_id,
            status=AttemptStatus.SUBMITTED,
            attempt_number=2,
        ),
    ]
    action, _, _ = resolve_attempt_start(exam, invitation, finished)

    assert action == "blocked_exhausted"


def test_resolve_attempt_start_allows_second_attempt():
    exam = _exam(max_attempts=2)
    invitation = _invitation()
    finished = [
        ExamAttempt(
            invitation_id=invitation.id,
            exam_id=invitation.exam_id,
            status=AttemptStatus.SUBMITTED,
            attempt_number=1,
        )
    ]
    action, _, next_number = resolve_attempt_start(exam, invitation, finished)

    assert action == "create"
    assert next_number == 2


def test_compute_attempt_cooldown_remaining_zero_when_disabled():
    exam = _exam(max_attempts=3)
    exam.attempt_cooldown_enabled = False
    exam.attempt_cooldown_seconds = 60
    finished = [
        ExamAttempt(
            invitation_id=uuid4(),
            exam_id=exam.id,
            status=AttemptStatus.SUBMITTED,
            attempt_number=1,
            submitted_at=datetime.now(timezone.utc),
        )
    ]

    assert compute_attempt_cooldown_remaining_seconds(exam, finished) == 0


def test_compute_attempt_cooldown_remaining_after_submission():
    exam = _exam(max_attempts=3)
    exam.attempt_cooldown_enabled = True
    exam.attempt_cooldown_seconds = 60
    now = datetime(2025, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    finished = [
        ExamAttempt(
            invitation_id=uuid4(),
            exam_id=exam.id,
            status=AttemptStatus.SUBMITTED,
            attempt_number=1,
            submitted_at=now - timedelta(seconds=25),
        )
    ]

    assert compute_attempt_cooldown_remaining_seconds(exam, finished, now=now) == 35


def test_compute_attempt_cooldown_remaining_zero_when_elapsed():
    exam = _exam(max_attempts=3)
    exam.attempt_cooldown_enabled = True
    exam.attempt_cooldown_seconds = 60
    now = datetime(2025, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    finished = [
        ExamAttempt(
            invitation_id=uuid4(),
            exam_id=exam.id,
            status=AttemptStatus.SUBMITTED,
            attempt_number=1,
            submitted_at=now - timedelta(seconds=90),
        )
    ]

    assert compute_attempt_cooldown_remaining_seconds(exam, finished, now=now) == 0
