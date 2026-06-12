import hashlib
import math
import os
import uuid

import aiofiles

from app.config import settings
from app.domain.enums import ProctoringEventType
from app.domain.services import FileStorageService, ProctoringAnalysisResult, ProctoringService


def delete_uploaded_file(upload_dir: str, public_url: str | None) -> None:
    if not public_url or not public_url.startswith("/uploads/"):
        return
    relative = public_url[len("/uploads/") :].lstrip("/")
    if not relative or ".." in relative.replace("\\", "/").split("/"):
        return
    path = os.path.join(upload_dir, relative)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


class LocalFileStorageService(FileStorageService):
    def __init__(self, upload_dir: str | None = None):
        self._upload_dir = upload_dir or settings.upload_dir

    async def save_image(self, content: bytes, filename: str) -> str:
        os.makedirs(self._upload_dir, exist_ok=True)
        ext = os.path.splitext(filename)[1] or ".jpg"
        unique_name = f"{uuid.uuid4()}{ext}"
        path = os.path.join(self._upload_dir, unique_name)
        async with aiofiles.open(path, "wb") as f:
            await f.write(content)
        return f"/uploads/{unique_name}"

    async def save_video(self, content: bytes, filename: str) -> str:
        video_dir = os.path.join(self._upload_dir, "videos")
        os.makedirs(video_dir, exist_ok=True)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in {".webm", ".mp4", ".mov"}:
            ext = ".webm"
        unique_name = f"{uuid.uuid4()}{ext}"
        path = os.path.join(video_dir, unique_name)
        async with aiofiles.open(path, "wb") as f:
            await f.write(content)
        return f"/uploads/videos/{unique_name}"


class MLProctoringService(ProctoringService):
    """
    Servicio de proctoring con heurísticas simuladas.
    En producción, reemplazar por modelo ML real (MediaPipe, OpenCV, etc.).
    """

    def analyze_frame(
        self, frame_data: bytes, mouse_events: list[dict]
    ) -> ProctoringAnalysisResult:
        frame_hash = hashlib.md5(frame_data[:1024] if frame_data else b"").hexdigest()
        hash_int = int(frame_hash[:8], 16)

        eye_anomaly = (hash_int % 100) > 92
        face_anomaly = (hash_int % 100) > 95
        no_face = len(frame_data) < 100 if frame_data else True

        if no_face:
            return ProctoringAnalysisResult(
                fraud_detected=True,
                fraud_score=0.9,
                event_type=ProctoringEventType.NO_FACE.value,
                confidence=0.9,
                details={"reason": "No face detected in frame"},
            )

        if eye_anomaly:
            return ProctoringAnalysisResult(
                fraud_detected=True,
                fraud_score=0.75,
                event_type=ProctoringEventType.EYE_MOVEMENT.value,
                confidence=0.75,
                details={"reason": "Suspicious eye movement detected"},
            )

        if face_anomaly:
            return ProctoringAnalysisResult(
                fraud_detected=True,
                fraud_score=0.7,
                event_type=ProctoringEventType.FACIAL_EXPRESSION.value,
                confidence=0.7,
                details={"reason": "Abnormal facial expression"},
            )

        mouse_result = self.analyze_mouse_pattern(mouse_events)
        if mouse_result.fraud_detected:
            return mouse_result

        return ProctoringAnalysisResult(
            fraud_detected=False,
            fraud_score=0.0,
            event_type="normal",
            confidence=0.0,
            details={},
        )

    def analyze_mouse_pattern(self, mouse_events: list[dict]) -> ProctoringAnalysisResult:
        if len(mouse_events) < 5:
            return ProctoringAnalysisResult(
                fraud_detected=False,
                fraud_score=0.0,
                event_type="normal",
                confidence=0.0,
                details={},
            )

        velocities = []
        for i in range(1, len(mouse_events)):
            prev, curr = mouse_events[i - 1], mouse_events[i]
            dx = curr.get("x", 0) - prev.get("x", 0)
            dy = curr.get("y", 0) - prev.get("y", 0)
            dt = max(curr.get("t", 1) - prev.get("t", 0), 1)
            velocities.append(math.sqrt(dx * dx + dy * dy) / dt)

        if not velocities:
            return ProctoringAnalysisResult(
                fraud_detected=False,
                fraud_score=0.0,
                event_type="normal",
                confidence=0.0,
                details={},
            )

        avg_velocity = sum(velocities) / len(velocities)
        max_velocity = max(velocities)
        suspicious = max_velocity > avg_velocity * 5 and max_velocity > 100

        if suspicious:
            return ProctoringAnalysisResult(
                fraud_detected=True,
                fraud_score=0.65,
                event_type=ProctoringEventType.MOUSE_ANOMALY.value,
                confidence=0.65,
                details={"max_velocity": max_velocity, "avg_velocity": avg_velocity},
            )

        return ProctoringAnalysisResult(
            fraud_detected=False,
            fraud_score=0.0,
            event_type="normal",
            confidence=0.0,
            details={},
        )
