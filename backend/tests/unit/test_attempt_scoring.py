from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.application.attempt_questions import distribute_question_points
from app.application.attempt_scoring import compute_attempt_score, points_for_question
from app.domain.entities import Answer, Exam, ExamAttempt, ExamQuestionConfig
from app.domain.enums import ExamMode


FUTURE_CLOSES_AT = datetime.now(timezone.utc) + timedelta(days=7)


def test_distribute_ten_questions_over_five_points():
    shares = distribute_question_points(5.0, 10)
    assert shares == [0.5] * 10
    assert sum(shares) == 5.0


def test_distribute_uneven_total_sums_exactly():
    shares = distribute_question_points(5.0, 3)
    assert len(shares) == 3
    assert round(sum(shares), 2) == 5.0
    assert shares == [1.67, 1.67, 1.66]


def test_compute_score_seven_of_ten_equals_three_point_five():
    exam_id = uuid4()
    question_ids = [uuid4() for _ in range(10)]
    shares = distribute_question_points(5.0, 10)
    exam = Exam(
        title="Exam",
        description="",
        owner_id=uuid4(),
        question_bank_id=uuid4(),
        mode=ExamMode.REAL,
        total_score=5.0,
        question_count=10,
        closes_at=FUTURE_CLOSES_AT,
        random_selection=True,
        id=exam_id,
    )
    attempt = ExamAttempt(
        invitation_id=uuid4(),
        exam_id=exam_id,
        selected_question_ids=question_ids,
        question_configs=[
            ExamQuestionConfig(
                question_id=question_id,
                order=index,
                points=shares[index],
                time_seconds=60,
            )
            for index, question_id in enumerate(question_ids)
        ],
    )
    answers = [
        Answer(
            attempt_id=attempt.id,
            question_id=question_id,
            is_correct=index < 7,
            points_earned=shares[index] if index < 7 else 0.0,
        )
        for index, question_id in enumerate(question_ids)
    ]

    assert compute_attempt_score(exam, attempt, answers) == 3.5


def test_unanswered_questions_do_not_add_points_or_change_correct_score():
    exam_id = uuid4()
    question_ids = [uuid4() for _ in range(10)]
    shares = distribute_question_points(5.0, 10)
    exam = Exam(
        title="Exam",
        description="",
        owner_id=uuid4(),
        question_bank_id=uuid4(),
        mode=ExamMode.REAL,
        total_score=5.0,
        question_count=10,
        closes_at=FUTURE_CLOSES_AT,
        random_selection=True,
        id=exam_id,
    )
    attempt = ExamAttempt(
        invitation_id=uuid4(),
        exam_id=exam_id,
        selected_question_ids=question_ids,
        question_configs=[
            ExamQuestionConfig(
                question_id=question_id,
                order=index,
                points=shares[index],
                time_seconds=60,
            )
            for index, question_id in enumerate(question_ids)
        ],
    )
    # 7 correct, 1 incorrect, 2 unanswered (no answer rows)
    answers = [
        Answer(
            attempt_id=attempt.id,
            question_id=question_ids[index],
            is_correct=True,
            points_earned=shares[index],
        )
        for index in range(7)
    ] + [
        Answer(
            attempt_id=attempt.id,
            question_id=question_ids[7],
            is_correct=False,
            points_earned=0.0,
        )
    ]

    assert compute_attempt_score(exam, attempt, answers) == 3.5


def test_points_for_question_uses_attempt_config():
    question_id = uuid4()
    exam = Exam(
        title="Exam",
        description="",
        owner_id=uuid4(),
        question_bank_id=uuid4(),
        mode=ExamMode.REAL,
        total_score=5.0,
        question_count=10,
        closes_at=FUTURE_CLOSES_AT,
        random_selection=True,
    )
    attempt = ExamAttempt(
        invitation_id=uuid4(),
        exam_id=exam.id,
        selected_question_ids=[question_id],
        question_configs=[
            ExamQuestionConfig(
                question_id=question_id,
                order=0,
                points=0.5,
                time_seconds=60,
            )
        ],
    )

    assert points_for_question(exam, attempt, question_id) == 0.5
