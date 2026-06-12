from datetime import datetime, timezone

from app.domain.entities import Question, QuestionBank
from app.domain.enums import QuestionType

BACKUP_VERSION = 1


def question_to_backup_item(question: Question) -> dict:
    return {
        "text": question.text,
        "question_type": question.question_type.value,
        "time_seconds": question.time_seconds,
        "topic_name": question.topic_name,
        "image_url": question.image_url,
        "options": [
            {"text": opt.text, "is_correct": opt.is_correct}
            for opt in question.options
        ],
    }


def build_backup_payload(bank: QuestionBank, questions: list[Question]) -> dict:
    return {
        "version": BACKUP_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "bank_name": bank.name,
        "questions": [question_to_backup_item(q) for q in questions],
    }


def parse_backup_payload(data: dict) -> list[dict]:
    if not isinstance(data, dict):
        raise ValueError("El backup debe ser un objeto JSON")
    version = data.get("version")
    if version != BACKUP_VERSION:
        raise ValueError(f"Versión de backup no soportada: {version}")
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("El backup no contiene una lista de preguntas")
    return questions


def parse_question_item(item: dict) -> dict:
    if not isinstance(item, dict):
        raise ValueError("Cada pregunta del backup debe ser un objeto")
    text = str(item.get("text", "")).strip()
    if not text:
        raise ValueError("Cada pregunta debe tener un enunciado")
    try:
        question_type = QuestionType(item.get("question_type"))
    except (ValueError, TypeError) as exc:
        raise ValueError("Tipo de pregunta inválido en el backup") from exc
    time_seconds = item.get("time_seconds")
    if not isinstance(time_seconds, int) or time_seconds <= 0:
        raise ValueError("Tiempo de respuesta inválido en el backup")
    options = item.get("options", [])
    if not isinstance(options, list):
        raise ValueError("Las opciones deben ser una lista")
    parsed_options = []
    for opt in options:
        if not isinstance(opt, dict):
            raise ValueError("Opción inválida en el backup")
        opt_text = str(opt.get("text", "")).strip()
        if not opt_text:
            raise ValueError("Cada opción debe tener texto")
        parsed_options.append(
            {"text": opt_text, "is_correct": bool(opt.get("is_correct", False))}
        )
    topic_name = item.get("topic_name")
    if topic_name is not None:
        topic_name = str(topic_name).strip() or None
    return {
        "text": text,
        "question_type": question_type,
        "time_seconds": time_seconds,
        "topic_name": topic_name,
        "options": parsed_options,
    }
