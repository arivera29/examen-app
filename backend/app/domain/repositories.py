from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from app.domain.entities import (
    Answer,
    Exam,
    ExamAttempt,
    ExamInvitation,
    AttemptSnapshot,
    ProctoringEvent,
    Question,
    QuestionBank,
    Topic,
    User,
)


class UserRepository(ABC):
    @abstractmethod
    def create(self, user: User) -> User: ...

    @abstractmethod
    def get_by_id(self, user_id: UUID) -> Optional[User]: ...

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]: ...

    @abstractmethod
    def update(self, user: User) -> User: ...


class QuestionBankRepository(ABC):
    @abstractmethod
    def create(self, bank: QuestionBank) -> QuestionBank: ...

    @abstractmethod
    def get_by_id(self, bank_id: UUID) -> Optional[QuestionBank]: ...

    @abstractmethod
    def list_by_owner(self, owner_id: UUID) -> list[QuestionBank]: ...

    @abstractmethod
    def update(self, bank: QuestionBank) -> QuestionBank: ...

    @abstractmethod
    def delete(self, bank_id: UUID) -> bool: ...


class TopicRepository(ABC):
    @abstractmethod
    def create(self, topic: Topic) -> Topic: ...

    @abstractmethod
    def get_by_id(self, topic_id: UUID) -> Optional[Topic]: ...

    @abstractmethod
    def list_by_owner(self, owner_id: UUID) -> list[Topic]: ...

    @abstractmethod
    def update(self, topic: Topic) -> Topic: ...

    @abstractmethod
    def delete(self, topic_id: UUID) -> bool: ...


class QuestionRepository(ABC):
    @abstractmethod
    def create(self, question: Question) -> Question: ...

    @abstractmethod
    def get_by_id(self, question_id: UUID) -> Optional[Question]: ...

    @abstractmethod
    def get_by_id_in_bank(self, bank_id: UUID, question_id: UUID) -> Optional[Question]: ...

    @abstractmethod
    def list_by_bank(self, bank_id: UUID) -> list[Question]: ...

    @abstractmethod
    def count_by_bank(self, bank_id: UUID, search: str | None = None) -> int: ...

    @abstractmethod
    def list_by_bank_paginated(
        self, bank_id: UUID, page: int, page_size: int, search: str | None = None
    ) -> list[Question]: ...

    @abstractmethod
    def list_by_ids(self, question_ids: list[UUID]) -> list[Question]: ...

    @abstractmethod
    def update(self, question: Question) -> Question: ...

    @abstractmethod
    def delete(self, question_id: UUID) -> bool: ...


class ExamRepository(ABC):
    @abstractmethod
    def create(self, exam: Exam) -> Exam: ...

    @abstractmethod
    def get_by_id(self, exam_id: UUID) -> Optional[Exam]: ...

    @abstractmethod
    def list_by_owner(self, owner_id: UUID) -> list[Exam]: ...

    @abstractmethod
    def count_by_question_bank(self, question_bank_id: UUID) -> int: ...

    @abstractmethod
    def count_exams_using_question(self, question_id: UUID) -> int: ...

    @abstractmethod
    def update(self, exam: Exam) -> Exam: ...

    @abstractmethod
    def delete(self, exam_id: UUID) -> bool: ...


class InvitationRepository(ABC):
    @abstractmethod
    def create(self, invitation: ExamInvitation) -> ExamInvitation: ...

    @abstractmethod
    def get_by_id(self, invitation_id: UUID) -> Optional[ExamInvitation]: ...

    @abstractmethod
    def get_by_token(self, token: str) -> Optional[ExamInvitation]: ...

    @abstractmethod
    def list_by_exam(self, exam_id: UUID) -> list[ExamInvitation]: ...

    @abstractmethod
    def get_by_exam_and_email(self, exam_id: UUID, email: str) -> list[ExamInvitation]: ...

    @abstractmethod
    def update(self, invitation: ExamInvitation) -> ExamInvitation: ...

    @abstractmethod
    def delete(self, invitation_id: UUID) -> bool: ...


class AttemptRepository(ABC):
    @abstractmethod
    def create(self, attempt: ExamAttempt) -> ExamAttempt: ...

    @abstractmethod
    def get_by_id(self, attempt_id: UUID) -> Optional[ExamAttempt]: ...

    @abstractmethod
    def get_by_invitation(self, invitation_id: UUID) -> Optional[ExamAttempt]: ...

    @abstractmethod
    def list_by_invitation(self, invitation_id: UUID) -> list[ExamAttempt]: ...

    @abstractmethod
    def list_by_email(self, exam_id: UUID, email: str) -> list[ExamAttempt]: ...

    @abstractmethod
    def count_finished_for_email(self, exam_id: UUID, email: str) -> int: ...

    @abstractmethod
    def list_by_exam(self, exam_id: UUID) -> list[ExamAttempt]: ...

    @abstractmethod
    def has_completed_attempt_for_email(self, exam_id: UUID, email: str) -> bool: ...

    @abstractmethod
    def has_in_progress_attempt_for_email(
        self, exam_id: UUID, email: str, exclude_invitation_id: UUID | None = None
    ) -> bool: ...

    @abstractmethod
    def update(self, attempt: ExamAttempt) -> ExamAttempt: ...

    @abstractmethod
    def delete(self, attempt_id: UUID) -> bool: ...


class AnswerRepository(ABC):
    @abstractmethod
    def create(self, answer: Answer) -> Answer: ...

    @abstractmethod
    def get_by_attempt(self, attempt_id: UUID) -> list[Answer]: ...

    @abstractmethod
    def upsert(self, answer: Answer) -> Answer: ...


class ProctoringRepository(ABC):
    @abstractmethod
    def create(self, event: ProctoringEvent) -> ProctoringEvent: ...

    @abstractmethod
    def list_by_attempt(self, attempt_id: UUID) -> list[ProctoringEvent]: ...


class AttemptSnapshotRepository(ABC):
    @abstractmethod
    def create(self, snapshot: AttemptSnapshot) -> AttemptSnapshot: ...

    @abstractmethod
    def list_by_attempt(self, attempt_id: UUID) -> list[AttemptSnapshot]: ...

    @abstractmethod
    def count_by_type(self, attempt_id: UUID, snapshot_type) -> int: ...
