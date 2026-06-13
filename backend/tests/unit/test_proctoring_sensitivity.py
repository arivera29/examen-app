import pytest

from app.application.proctoring_sensitivity import (
    DEFAULT_PROCTORING_SENSITIVITY,
    detection_threshold,
    normalize_proctoring_sensitivity,
    scale_fraud_confidence,
    should_flag_fraud,
)


class TestProctoringSensitivity:
    def test_default_sensitivity_is_moderate_low(self):
        assert DEFAULT_PROCTORING_SENSITIVITY == 0.4

    def test_lower_sensitivity_raises_detection_threshold(self):
        low = detection_threshold(0.3)
        medium = detection_threshold(0.5)
        high = detection_threshold(0.8)

        assert low > medium > high

    def test_lower_sensitivity_reduces_reported_score(self):
        assert scale_fraud_confidence(0.8, 0.3) < scale_fraud_confidence(0.8, 0.5)
        assert scale_fraud_confidence(0.8, 0.5) == pytest.approx(0.8)
        assert scale_fraud_confidence(0.8, 0.8) > scale_fraud_confidence(0.8, 0.5)

    def test_should_flag_respects_sensitivity(self):
        confidence = 0.75
        assert should_flag_fraud(confidence, 0.8) is True
        assert should_flag_fraud(confidence, 0.3) is False

    def test_normalize_clamps_values(self):
        assert normalize_proctoring_sensitivity(0.01) == 0.1
        assert normalize_proctoring_sensitivity(2.0) == 1.0
        assert normalize_proctoring_sensitivity(None) == DEFAULT_PROCTORING_SENSITIVITY
