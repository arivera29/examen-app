from app.domain.entities import ExamAttempt, ProctoringEvent


def resolve_final_attempt(finished_attempts: list[ExamAttempt]) -> ExamAttempt | None:
    """Return the attempt whose score is used when the exam is finalized."""
    if not finished_attempts:
        return None
    return max(finished_attempts, key=lambda attempt: attempt.attempt_number)


def compute_attempt_fraud_score(
    attempt: ExamAttempt,
    events: list[ProctoringEvent],
) -> float:
    """
    Fraud score for a single attempt only.

    Uses the highest proctoring confidence detected during the attempt instead of
    summing incremental penalties across events or prior attempts.
    """
    if events:
        return min(1.0, max(event.confidence for event in events))
    return min(1.0, max(0.0, attempt.fraud_score))
