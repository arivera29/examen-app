import random
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
        selected = random.sample(bank_questions, exam.question_count)
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
