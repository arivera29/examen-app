DEFAULT_PROCTORING_SENSITIVITY = 0.4
REFERENCE_PROCTORING_SENSITIVITY = 0.5


def normalize_proctoring_sensitivity(value: float | None) -> float:
    if value is None:
        return DEFAULT_PROCTORING_SENSITIVITY
    return min(1.0, max(0.1, float(value)))


def detection_threshold(
    sensitivity: float | None,
    base_threshold: float = 0.7,
) -> float:
    """
    Lower sensitivity requires higher raw confidence to flag fraud.
    At reference sensitivity (0.5) the base threshold is unchanged.
    """
    normalized = normalize_proctoring_sensitivity(sensitivity)
    return min(0.95, base_threshold * (REFERENCE_PROCTORING_SENSITIVITY / normalized))


def scale_fraud_confidence(confidence: float, sensitivity: float | None) -> float:
    """
    Scale confidence into the attempt fraud score.
    Lower sensitivity reduces the reported fraud percentage.
    """
    normalized = normalize_proctoring_sensitivity(sensitivity)
    scaled = confidence * (normalized / REFERENCE_PROCTORING_SENSITIVITY)
    return min(1.0, max(0.0, scaled))


def should_flag_fraud(
    confidence: float,
    sensitivity: float | None,
    base_threshold: float = 0.7,
) -> bool:
    return confidence >= detection_threshold(sensitivity, base_threshold)
