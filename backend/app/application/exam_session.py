from uuid import UUID

from app.application.attempt_questions import resolve_attempt_question_configs
from app.application.exam_timing import get_remaining_seconds, get_total_exam_seconds
from app.domain.entities import Answer, Exam, ExamAttempt, Question
from app.domain.repositories import QuestionRepository


def order_questions_by_attempt(
    question_repo: QuestionRepository,
    question_ids: list[UUID],
) -> list[Question]:
    if not question_ids:
        return []
    questions_by_id = {
        question.id: question for question in question_repo.list_by_ids(question_ids)
    }
    return [questions_by_id[question_id] for question_id in question_ids if question_id in questions_by_id]


def get_attempt_question_ids_ordered(exam: Exam, attempt: ExamAttempt) -> list[UUID]:
    configs = resolve_attempt_question_configs(exam, attempt)
    if configs:
        return [config.question_id for config in configs]
    return list(attempt.selected_question_ids)


def build_saved_answers(answers: list[Answer]) -> list[dict]:
    return [
        {
            "question_id": str(answer.question_id),
            "selected_option_ids": [str(option_id) for option_id in answer.selected_option_ids],
            "open_text": answer.open_text,
        }
        for answer in answers
    ]


def _is_answered(answer: Answer | None) -> bool:
    if not answer:
        return False
    if answer.selected_option_ids:
        return True
    return bool((answer.open_text or "").strip())


def resolve_resume_state(
    exam: Exam,
    attempt: ExamAttempt,
    question_ids: list[UUID],
    answers: list[Answer],
) -> tuple[int, list[UUID]]:
    if (
        attempt.current_question_index > 0
        or attempt.locked_question_ids
        or attempt.current_question_started_at
    ):
        return attempt.current_question_index, list(attempt.locked_question_ids)

    answers_by_question = {answer.question_id: answer for answer in answers}
    if exam.enforce_question_time:
        locked: list[UUID] = []
        current_index = 0
        for index, question_id in enumerate(question_ids):
            if _is_answered(answers_by_question.get(question_id)):
                locked.append(question_id)
                current_index = min(index + 1, len(question_ids) - 1)
            else:
                current_index = index
                break
        return current_index, locked

    for index, question_id in enumerate(question_ids):
        if not _is_answered(answers_by_question.get(question_id)):
            return index, []
    return max(len(question_ids) - 1, 0), []


def build_exam_session_payload(
    exam: Exam,
    attempt: ExamAttempt,
    questions: list[Question],
    bank_questions: list[Question],
    answers: list[Answer],
    *,
    resumed: bool = False,
) -> dict:
    from app.application.exam_timing import get_current_question_remaining_seconds

    question_ids = [question.id for question in questions]
    current_question_index, locked_question_ids = resolve_resume_state(
        exam,
        attempt,
        question_ids,
        answers,
    )
    resume_attempt = ExamAttempt(
        invitation_id=attempt.invitation_id,
        exam_id=attempt.exam_id,
        id=attempt.id,
        status=attempt.status,
        attempt_number=attempt.attempt_number,
        invitee_full_name=attempt.invitee_full_name,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
        score=attempt.score,
        fraud_score=attempt.fraud_score,
        camera_verified=attempt.camera_verified,
        attempt_video_url=attempt.attempt_video_url,
        selected_question_ids=attempt.selected_question_ids,
        question_configs=attempt.question_configs,
        current_question_index=current_question_index,
        locked_question_ids=locked_question_ids,
        current_question_started_at=attempt.current_question_started_at,
    )
    question_remaining = get_current_question_remaining_seconds(exam, resume_attempt, questions)

    return {
        "attempt": attempt,
        "exam": exam,
        "questions": questions,
        "total_time_seconds": get_total_exam_seconds(exam, attempt, bank_questions),
        "remaining_seconds": get_remaining_seconds(exam, attempt, bank_questions),
        "saved_answers": build_saved_answers(answers),
        "current_question_index": current_question_index,
        "locked_question_ids": [str(question_id) for question_id in locked_question_ids],
        "question_remaining_seconds": question_remaining,
        "resumed": resumed,
    }
