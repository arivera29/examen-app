import pytest
from app.infrastructure.services.proctoring_service import MLProctoringService


class TestMLProctoringService:
    @pytest.fixture
    def service(self):
        return MLProctoringService()

    def test_no_face_detected(self, service):
        result = service.analyze_frame(b"", [])
        assert result.fraud_detected is True
        assert result.event_type == "no_face"

    def test_normal_frame(self, service):
        frame = b"x" * 200
        result = service.analyze_frame(frame, [{"x": 0, "y": 0, "t": 0}, {"x": 1, "y": 1, "t": 100}])
        assert result.fraud_detected is False or result.event_type != "no_face"

    def test_mouse_anomaly(self, service):
        events = [{"x": 0, "y": 0, "t": i * 100} for i in range(8)]
        events.append({"x": 10000, "y": 10000, "t": 801})
        result = service.analyze_mouse_pattern(events)
        assert result.fraud_detected is True
        assert result.event_type == "mouse_anomaly"
