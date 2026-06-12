from unittest.mock import patch
from uuid import uuid4

import pytest

from app.application.attempt_questions import assign_attempt_questions, summarize_attempt_answers
from app.domain.entities import Answer, Exam, ExamAttempt, ExamQuestionConfig, Question, QuestionOption
from app.domain.enums import ExamMode, QuestionType
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

FUTURE_CLOSES_AT = datetime.now(timezone.utc) + timedelta(days=7)


class TestAssignAttemptQuestions:
    @patch("app.application.attempt_questions.random.sample")
    def test_assigns_different_questions_per_attempt(self, mock_sample):
        owner_id = uuid4()
        bank_id = uuid4()
        questions = [
            Question(
                text=f"Q{i}",
                question_type=QuestionType.SINGLE_CHOICE,
                time_seconds=60,
                owner_id=owner_id,
                options=[QuestionOption(text="A", is_correct=True)],
            )
            for i in range(6)
        ]
        mock_sample.side_effect = [questions[:3], questions[3:6]]

        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=bank_id,
            mode=ExamMode.REAL,
            total_score=30,
            question_count=3,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=uuid4(),
        )
        question_repo = MagicMock()
        question_repo.list_by_bank.return_value = questions

        attempt_one = ExamAttempt(invitation_id=uuid4(), exam_id=exam.id)
        attempt_two = ExamAttempt(invitation_id=uuid4(), exam_id=exam.id)

        assign_attempt_questions(exam, attempt_one, question_repo)
        assign_attempt_questions(exam, attempt_two, question_repo)

        assert attempt_one.selected_question_ids != attempt_two.selected_question_ids
        assert len(attempt_one.selected_question_ids) == 3
        assert len(attempt_two.selected_question_ids) == 3

    def test_keeps_existing_assignment_when_resuming(self):
        owner_id = uuid4()
        question_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=10,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
        )
        attempt = ExamAttempt(
            invitation_id=uuid4(),
            exam_id=uuid4(),
            selected_question_ids=[question_id],
            question_configs=[],
        )
        question_repo = MagicMock()

        assign_attempt_questions(exam, attempt, question_repo)

        question_repo.list_by_bank.assert_not_called()
        assert attempt.selected_question_ids == [question_id]

    @patch("app.application.attempt_questions.random.sample")
    def test_points_sum_equals_total_score(self, mock_sample):
        owner_id = uuid4()
        bank_id = uuid4()
        questions = [
            Question(
                text=f"Q{i}",
                question_type=QuestionType.SINGLE_CHOICE,
                time_seconds=60,
                owner_id=owner_id,
                options=[QuestionOption(text="A", is_correct=True)],
            )
            for i in range(5)
        ]
        mock_sample.return_value = questions

        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=bank_id,
            mode=ExamMode.REAL,
            total_score=5,
            question_count=5,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=uuid4(),
        )
        question_repo = MagicMock()
        question_repo.list_by_bank.return_value = questions
        attempt = ExamAttempt(invitation_id=uuid4(), exam_id=exam.id)

        assign_attempt_questions(exam, attempt, question_repo)

        total_points = sum(config.points for config in attempt.question_configs)
        assert total_points == exam.total_score


class TestSummarizeAttemptAnswers:
    def test_ignores_answers_outside_attempt_questions(self):
        owner_id = uuid4()
        question_ids = [uuid4() for _ in range(10)]
        extra_question_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=10,
            question_count=10,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=uuid4(),
        )
        attempt = ExamAttempt(
            invitation_id=uuid4(),
            exam_id=exam.id,
            selected_question_ids=question_ids,
            question_configs=[
                ExamQuestionConfig(question_id=question_id, order=index, points=1, time_seconds=60)
                for index, question_id in enumerate(question_ids)
            ],
        )
        answers = [
            Answer(
                attempt_id=attempt.id,
                question_id=question_id,
                selected_option_ids=[],
                is_correct=True,
            )
            for question_id in question_ids
        ] + [
            Answer(
                attempt_id=attempt.id,
                question_id=extra_question_id,
                selected_option_ids=[],
                is_correct=True,
            )
        ]

        stats = summarize_attempt_answers(exam, attempt, answers)

        assert stats == {
            "correct_count": 10,
            "incorrect_count": 0,
            "answered_count": 10,
            "question_count": 10,
        }

    def test_deduplicates_repeated_question_configs(self):
        owner_id = uuid4()
        question_id = uuid4()
        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=uuid4(),
            mode=ExamMode.REAL,
            total_score=1,
            question_count=1,
            closes_at=FUTURE_CLOSES_AT,
            random_selection=True,
            id=uuid4(),
        )
        attempt = ExamAttempt(
            invitation_id=uuid4(),
            exam_id=exam.id,
            selected_question_ids=[question_id],
            question_configs=[
                ExamQuestionConfig(question_id=question_id, order=0, points=1, time_seconds=60),
                ExamQuestionConfig(question_id=question_id, order=1, points=1, time_seconds=60),
            ],
        )
        answers = [
            Answer(
                attempt_id=attempt.id,
                question_id=question_id,
                selected_option_ids=[],
                is_correct=True,
            )
        ]

        stats = summarize_attempt_answers(exam, attempt, answers)

        assert stats["correct_count"] == 1
        assert stats["question_count"] == 1
