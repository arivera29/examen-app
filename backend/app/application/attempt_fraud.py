from app.domain.entities import ExamAttempt, ProctoringEvent


from app.application.proctoring_sensitivity import scale_fraud_confidence


def resolve_final_attempt(finished_attempts: list[ExamAttempt]) -> ExamAttempt | None:
    """Return the attempt whose score is used when the exam is finalized."""
    if not finished_attempts:
        return None
    return max(finished_attempts, key=lambda attempt: attempt.attempt_number)


def compute_attempt_fraud_score(
    attempt: ExamAttempt,
    events: list[ProctoringEvent],
    sensitivity: float | None = None,
) -> float:
    """
    Fraud score for a single attempt only.

    Event confidences are stored already scaled by exam sensitivity.
    """
    if events:
        return min(1.0, max(event.confidence for event in events))
    if sensitivity is None:
        return min(1.0, max(0.0, attempt.fraud_score))
    return scale_fraud_confidence(attempt.fraud_score, sensitivity)
