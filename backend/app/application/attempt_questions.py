import random
from collections import defaultdict
from uuid import UUID

from app.domain.entities import Answer, Exam, ExamAttempt, ExamQuestionConfig, Question
from app.domain.repositories import QuestionRepository


def get_attempt_question_configs(exam: Exam, attempt: ExamAttempt | None) -> list[ExamQuestionConfig]:
    if attempt and attempt.question_configs:
        return attempt.question_configs
    if not exam.random_selection:
        return exam.question_configs
    return []


def get_attempt_question_ids(exam: Exam, attempt: ExamAttempt | None) -> list[UUID]:
    if attempt and attempt.selected_question_ids:
        return attempt.selected_question_ids
    if not exam.random_selection:
        return exam.selected_question_ids
    return []


def select_questions_balanced_by_topic(
    questions: list[Question],
    count: int,
) -> list[Question]:
    """Select `count` questions with proportional balance across topics.

    Allocation uses the largest-remainder method over the bank composition.
    Within each topic the pick is random. The final order is shuffled.
    """
    if count <= 0:
        return []
    if len(questions) < count:
        raise ValueError("Not enough questions in bank")
    if count == len(questions):
        selected = list(questions)
        random.shuffle(selected)
        return selected

    by_topic: dict[UUID | None, list[Question]] = defaultdict(list)
    for question in questions:
        by_topic[question.topic_id].append(question)

    topics = list(by_topic.keys())
    for topic_id in topics:
        random.shuffle(by_topic[topic_id])

    if len(topics) == 1:
        return random.sample(questions, count)

    total = len(questions)
    raw_shares = {topic_id: (len(by_topic[topic_id]) / total) * count for topic_id in topics}
    floors = {topic_id: int(raw_shares[topic_id]) for topic_id in topics}
    allocated = dict(floors)
    remaining_slots = count - sum(floors.values())
    remainder_order = sorted(
        topics,
        key=lambda topic_id: (raw_shares[topic_id] - floors[topic_id], len(by_topic[topic_id])),
        reverse=True,
    )
    for topic_id in remainder_order:
        if remaining_slots <= 0:
            break
        allocated[topic_id] += 1
        remaining_slots -= 1

    selected: list[Question] = []
    shortfall = 0
    leftovers: list[Question] = []
    for topic_id in topics:
        available = by_topic[topic_id]
        take = min(allocated[topic_id], len(available))
        shortfall += allocated[topic_id] - take
        selected.extend(available[:take])
        leftovers.extend(available[take:])

    if shortfall > 0:
        random.shuffle(leftovers)
        if len(leftovers) < shortfall:
            raise ValueError("Not enough questions in bank")
        selected.extend(leftovers[:shortfall])

    random.shuffle(selected)
    return selected


def assign_attempt_questions(
    exam: Exam,
    attempt: ExamAttempt,
    question_repo: QuestionRepository,
) -> ExamAttempt:
    if attempt.selected_question_ids:
        return attempt

    if exam.random_selection:
        bank_questions = question_repo.list_by_bank(exam.question_bank_id)
        if len(bank_questions) < exam.question_count:
            raise ValueError("Not enough questions in bank")
        selected = select_questions_balanced_by_topic(bank_questions, exam.question_count)
    else:
        selected = question_repo.list_by_ids(exam.selected_question_ids)
        if len(selected) != exam.question_count:
            raise ValueError("Exam question configuration is invalid")

    points_per_question = exam.total_score / exam.question_count
    attempt.selected_question_ids = [question.id for question in selected]
    configs: list[ExamQuestionConfig] = []
    assigned_points = 0.0
    for index, question in enumerate(selected):
        if index == len(selected) - 1:
            points = round(exam.total_score - assigned_points, 2)
        else:
            points = round(points_per_question, 2)
            assigned_points += points
        configs.append(
            ExamQuestionConfig(
                question_id=question.id,
                order=index,
                points=points,
                time_seconds=question.time_seconds,
            )
        )
    attempt.question_configs = configs
    return attempt


def resolve_attempt_question_configs(exam: Exam, attempt: ExamAttempt) -> list[ExamQuestionConfig]:
    configs = get_attempt_question_configs(exam, attempt)
    if configs:
        return sorted(configs, key=lambda config: config.order)
    if attempt.selected_question_ids:
        default_points = exam.total_score / exam.question_count if exam.question_count else 0
        return [
            ExamQuestionConfig(
                question_id=question_id,
                order=index,
                points=default_points,
                time_seconds=0,
            )
            for index, question_id in enumerate(attempt.selected_question_ids)
        ]
    return []


def get_attempt_question_id_set(exam: Exam, attempt: ExamAttempt) -> set[UUID]:
    configs = resolve_attempt_question_configs(exam, attempt)
    if configs:
        return {config.question_id for config in configs}
    return set(attempt.selected_question_ids)


def summarize_attempt_answers(
    exam: Exam,
    attempt: ExamAttempt,
    answers: list[Answer],
) -> dict[str, int]:
    answers_by_question = {answer.question_id: answer for answer in answers}
    configs = resolve_attempt_question_configs(exam, attempt)
    seen: set[UUID] = set()
    correct = incorrect = answered = 0

    for config in configs:
        if config.question_id in seen:
            continue
        seen.add(config.question_id)
        answer = answers_by_question.get(config.question_id)
        if not answer:
            continue
        answered += 1
        if answer.is_correct is True:
            correct += 1
        elif answer.is_correct is False:
            incorrect += 1

    return {
        "correct_count": correct,
        "incorrect_count": incorrect,
        "answered_count": answered,
        "question_count": len(seen),
    }
