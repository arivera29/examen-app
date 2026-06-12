from io import BytesIO

from openpyxl import load_workbook

from app.application.question_bank_export import build_export_filename, build_question_bank_workbook


class TestQuestionBankExport:
    def test_build_workbook_contains_summary_and_questions(self):
        payload = {
            "bank_name": "Matemáticas",
            "bank_description": "Preguntas de álgebra",
            "total_questions": 2,
            "questions": [
                {
                    "text": "¿Cuánto es 2+2?",
                    "question_type": "single_choice",
                    "time_seconds": 60,
                    "topic_name": "Aritmética",
                    "image_url": None,
                    "options": [
                        {"text": "3", "is_correct": False},
                        {"text": "4", "is_correct": True},
                    ],
                },
                {
                    "text": "Explique el teorema de Pitágoras",
                    "question_type": "open",
                    "time_seconds": 120,
                    "topic_name": "Geometría",
                    "image_url": "/uploads/diagram.png",
                    "options": [],
                },
            ],
        }

        content = build_question_bank_workbook(payload)
        workbook = load_workbook(BytesIO(content))

        summary = workbook["Resumen"]
        questions = workbook["Preguntas"]

        assert summary["A1"].value.startswith("Banco de preguntas:")
        assert summary["A3"].value.startswith("Descripción:")
        assert questions["A3"].value == "#"
        assert questions["B4"].value == "¿Cuánto es 2+2?"
        assert questions["G4"].value == "4"
        assert questions["H4"].value == "A) 3\nB) 4 ✓"
        assert questions["G5"].value == "Evaluación manual"
        assert "banco-preguntas-Matem" in build_export_filename(payload)
