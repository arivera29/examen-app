from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.application.attempt_questions import (
    assign_attempt_questions,
    select_questions_balanced_by_topic,
    summarize_attempt_answers,
)
from app.domain.entities import Answer, Exam, ExamAttempt, ExamQuestionConfig, Question, QuestionOption
from app.domain.enums import ExamMode, QuestionType
from datetime import datetime, timedelta, timezone

FUTURE_CLOSES_AT = datetime.now(timezone.utc) + timedelta(days=7)


def _question(owner_id, text: str, topic_id=None) -> Question:
    return Question(
        text=text,
        question_type=QuestionType.SINGLE_CHOICE,
        time_seconds=60,
        owner_id=owner_id,
        topic_id=topic_id,
        options=[QuestionOption(text="A", is_correct=True)],
    )


class TestSelectQuestionsBalancedByTopic:
    def test_balances_proportionally_across_topics(self):
        owner_id = uuid4()
        topic_a = uuid4()
        topic_b = uuid4()
        topic_c = uuid4()
        questions = (
            [_question(owner_id, f"A{i}", topic_a) for i in range(6)]
            + [_question(owner_id, f"B{i}", topic_b) for i in range(3)]
            + [_question(owner_id, f"C{i}", topic_c) for i in range(3)]
        )

        selected = select_questions_balanced_by_topic(questions, 6)

        counts = {}
        for question in selected:
            counts[question.topic_id] = counts.get(question.topic_id, 0) + 1

        assert len(selected) == 6
        assert counts[topic_a] == 3
        assert counts[topic_b] + counts[topic_c] == 3
        assert counts[topic_b] in (1, 2)
        assert counts[topic_c] in (1, 2)

    def test_single_topic_uses_random_sample(self):
        owner_id = uuid4()
        topic_id = uuid4()
        questions = [_question(owner_id, f"Q{i}", topic_id) for i in range(8)]

        selected = select_questions_balanced_by_topic(questions, 4)

        assert len(selected) == 4
        assert all(question.topic_id == topic_id for question in selected)

    def test_includes_questions_without_topic(self):
        owner_id = uuid4()
        topic_id = uuid4()
        questions = (
            [_question(owner_id, f"T{i}", topic_id) for i in range(4)]
            + [_question(owner_id, f"N{i}", None) for i in range(4)]
        )

        selected = select_questions_balanced_by_topic(questions, 4)

        counts = {}
        for question in selected:
            counts[question.topic_id] = counts.get(question.topic_id, 0) + 1

        assert len(selected) == 4
        assert counts.get(topic_id, 0) == 2
        assert counts.get(None, 0) == 2

    def test_raises_when_not_enough_questions(self):
        owner_id = uuid4()
        questions = [_question(owner_id, "Q1", uuid4())]

        with pytest.raises(ValueError, match="Not enough questions"):
            select_questions_balanced_by_topic(questions, 3)


class TestAssignAttemptQuestions:
    def test_assigns_balanced_questions_per_attempt(self):
        owner_id = uuid4()
        bank_id = uuid4()
        topic_a = uuid4()
        topic_b = uuid4()
        questions = (
            [_question(owner_id, f"A{i}", topic_a) for i in range(4)]
            + [_question(owner_id, f"B{i}", topic_b) for i in range(4)]
        )

        exam = Exam(
            title="Exam",
            description="",
            owner_id=owner_id,
            question_bank_id=bank_id,
            mode=ExamMode.REAL,
            total_score=30,
            question_count=4,
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

        assert len(attempt_one.selected_question_ids) == 4
        assert len(attempt_two.selected_question_ids) == 4
        assert set(attempt_one.selected_question_ids).issubset({q.id for q in questions})
        assert set(attempt_two.selected_question_ids).issubset({q.id for q in questions})

        by_id = {q.id: q for q in questions}
        for attempt in (attempt_one, attempt_two):
            counts = {}
            for question_id in attempt.selected_question_ids:
                topic_id = by_id[question_id].topic_id
                counts[topic_id] = counts.get(topic_id, 0) + 1
            assert counts[topic_a] == 2
            assert counts[topic_b] == 2

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

    def test_points_sum_equals_total_score(self):
        owner_id = uuid4()
        bank_id = uuid4()
        topic_id = uuid4()
        questions = [_question(owner_id, f"Q{i}", topic_id) for i in range(5)]

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
