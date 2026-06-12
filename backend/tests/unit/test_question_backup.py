import pytest
from uuid import uuid4

from app.application.question_backup import (
    BACKUP_VERSION,
    build_backup_payload,
    parse_backup_payload,
    parse_question_item,
    question_to_backup_item,
)
from app.application.use_cases import RestoreQuestionBankBackupUseCase, ValidationError
from app.domain.entities import Question, QuestionBank, QuestionOption, Topic
from app.domain.enums import QuestionType
from unittest.mock import MagicMock


class TestQuestionBackupHelpers:
    def test_build_and_parse_backup(self):
        owner_id = uuid4()
        bank = QuestionBank(name="Mi banco", description="", owner_id=owner_id)
        question = Question(
            text="¿Cuál es 2+2?",
            question_type=QuestionType.SINGLE_CHOICE,
            time_seconds=60,
            owner_id=owner_id,
            topic_name="Matemáticas",
            options=[QuestionOption(text="4", is_correct=True), QuestionOption(text="5", is_correct=False)],
        )
        payload = build_backup_payload(bank, [question])
        assert payload["version"] == BACKUP_VERSION
        assert payload["bank_name"] == "Mi banco"
        assert len(payload["questions"]) == 1
        parsed = parse_backup_payload(payload)
        assert len(parsed) == 1
        item = parse_question_item(parsed[0])
        assert item["text"] == "¿Cuál es 2+2?"
        assert item["question_type"] == QuestionType.SINGLE_CHOICE

    def test_rejects_unsupported_version(self):
        with pytest.raises(ValueError, match="Versión"):
            parse_backup_payload({"version": 99, "questions": []})


class TestRestoreQuestionBankBackupUseCase:
    def test_restore_append_creates_questions(self):
        owner_id = uuid4()
        bank_id = uuid4()
        bank = QuestionBank(name="Bank", description="", owner_id=owner_id, id=bank_id)
        bank_repo = MagicMock()
        bank_repo.get_by_id.return_value = bank
        question_repo = MagicMock()
        question_repo.list_by_bank.return_value = []
        question_repo.create_in_bank.side_effect = lambda _bank_id, q: q
        topic_repo = MagicMock()
        topic_repo.list_by_owner.return_value = []
        topic_repo.create.side_effect = lambda t: t
        exam_repo = MagicMock()

        use_case = RestoreQuestionBankBackupUseCase(bank_repo, question_repo, topic_repo, exam_repo)
        result = use_case.execute(
            owner_id,
            bank_id,
            {
                "version": BACKUP_VERSION,
                "questions": [
                    {
                        "text": "Pregunta importada",
                        "question_type": "open",
                        "time_seconds": 30,
                        "options": [],
                    }
                ],
            },
            mode="append",
        )
        assert result["imported_count"] == 1
        question_repo.create_in_bank.assert_called_once()

    def test_restore_replace_deletes_unused_questions(self):
        owner_id = uuid4()
        bank_id = uuid4()
        bank = QuestionBank(name="Bank", description="", owner_id=owner_id, id=bank_id)
        existing = Question(
            id=uuid4(),
            text="Old",
            question_type=QuestionType.OPEN,
            time_seconds=60,
            owner_id=owner_id,
        )
        bank_repo = MagicMock()
        bank_repo.get_by_id.return_value = bank
        question_repo = MagicMock()
        question_repo.list_by_bank.return_value = [existing]
        question_repo.delete.return_value = True
        question_repo.create_in_bank.side_effect = lambda _bank_id, q: q
        topic_repo = MagicMock()
        topic_repo.list_by_owner.return_value = []
        exam_repo = MagicMock()
        exam_repo.count_exams_using_question.return_value = 0

        use_case = RestoreQuestionBankBackupUseCase(bank_repo, question_repo, topic_repo, exam_repo)
        result = use_case.execute(
            owner_id,
            bank_id,
            {
                "version": BACKUP_VERSION,
                "questions": [
                    {
                        "text": "Nueva",
                        "question_type": "open",
                        "time_seconds": 45,
                        "options": [],
                    }
                ],
            },
            mode="replace",
        )
        assert result["deleted_count"] == 1
        assert result["imported_count"] == 1
        question_repo.delete.assert_called_once_with(existing.id)

    def test_invalid_mode(self):
        use_case = RestoreQuestionBankBackupUseCase(MagicMock(), MagicMock(), MagicMock(), MagicMock())
        with pytest.raises(ValidationError, match="Modo"):
            use_case.execute(uuid4(), uuid4(), {"version": BACKUP_VERSION, "questions": []}, mode="invalid")
