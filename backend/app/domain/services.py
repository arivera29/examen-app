from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass
class ProctoringAnalysisResult:
    fraud_detected: bool
    fraud_score: float
    event_type: str
    confidence: float
    details: dict


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, plain: str, hashed: str) -> bool: ...


class TokenService(ABC):
    @abstractmethod
    def create_access_token(self, user_id: UUID, email: str) -> str: ...

    @abstractmethod
    def create_refresh_token(self, user_id: UUID) -> str: ...

    @abstractmethod
    def decode_token(self, token: str) -> Optional[dict]: ...

    @abstractmethod
    def create_token_pair(self, user_id: UUID, email: str) -> TokenPair: ...


class MfaService(ABC):
    @abstractmethod
    def generate_secret(self) -> str: ...

    @abstractmethod
    def get_provisioning_uri(self, secret: str, email: str) -> str: ...

    @abstractmethod
    def verify_code(self, secret: str, code: str) -> bool: ...


class EmailService(ABC):
    @abstractmethod
    async def send_exam_invitation(
        self, to_email: str, exam_title: str, invite_link: str, mode: str
    ) -> bool: ...


class ProctoringService(ABC):
    @abstractmethod
    def analyze_frame(
        self, frame_data: bytes, mouse_events: list[dict]
    ) -> ProctoringAnalysisResult: ...

    @abstractmethod
    def analyze_mouse_pattern(self, mouse_events: list[dict]) -> ProctoringAnalysisResult: ...


class FileStorageService(ABC):
    @abstractmethod
    async def save_image(self, content: bytes, filename: str) -> str: ...

    @abstractmethod
    async def save_video(self, content: bytes, filename: str) -> str: ...
