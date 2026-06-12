from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from app.application.exam_attempts_answers_export import (
    build_attempts_answers_filename,
    build_attempts_answers_workbook,
)
from app.application.use_cases import ExportExamAttemptsAnswersUseCase, ValidationError
from app.domain.entities import ExamAttempt
from app.domain.enums import AttemptStatus


class TestExamAttemptsAnswersExport:
    def test_build_workbook_contains_summary_and_answer_rows(self):
        attempt_reports = [
            {
                "invitee_full_name": "Ana Pérez",
                "invitee_email": "ana@test.com",
                "attempt_number": 1,
                "score": 8.0,
                "total_score": 10,
                "answers": [
                    {
                        "order": 1,
                        "question_text": "¿Capital de España?",
                        "question_type": "single_choice",
                        "selected_options": ["Madrid"],
                        "correct_options": ["Madrid"],
                        "open_text": None,
                        "is_correct": True,
                        "points_earned": 5,
                        "max_points": 5,
                        "answered": True,
                    },
                    {
                        "order": 2,
                        "question_text": "Explique la fotosíntesis",
                        "question_type": "open",
                        "selected_options": [],
                        "correct_options": [],
                        "open_text": "Proceso de las plantas",
                        "is_correct": None,
                        "points_earned": 3,
                        "max_points": 5,
                        "answered": True,
                    },
                ],
            }
        ]

        content = build_attempts_answers_workbook("Examen Final", attempt_reports)
        workbook = load_workbook(BytesIO(content))

        summary = workbook["Resumen invitados"]
        answers = workbook["Respuestas detalladas"]

        assert summary["A1"].value.startswith("Respuestas del examen:")
        assert summary["A5"].value == "Ana Pérez"
        assert answers["E4"].value == "¿Capital de España?"
        assert answers["G4"].value == "Madrid"
        assert answers["I4"].value == "Correcta"
        assert answers["I5"].value == "Pendiente de revisión"
        assert "respuestas-Examen-Final" in build_attempts_answers_filename("Examen Final")
        assert "student" in build_attempts_answers_filename("Examen Final", "student@test.com")


class TestExportExamAttemptsAnswersUseCase:
    def test_exports_all_finished_attempts(self):
        exam_id = uuid4()
        owner_id = uuid4()
        attempt_id = uuid4()

        report = {"exam_title": "Examen", "individual_reports": []}
        attempt = ExamAttempt(
            id=attempt_id,
            invitation_id=uuid4(),
            exam_id=exam_id,
            status=AttemptStatus.SUBMITTED,
            attempt_number=1,
            score=10,
        )
        attempt_report = {
            "invitee_full_name": "Ana",
            "invitee_email": "ana@test.com",
            "attempt_number": 1,
            "score": 10,
            "total_score": 10,
            "answers": [],
        }

        report_use_case = type("ReportUseCase", (), {"execute": lambda self, o, e: report})()
        answers_use_case = type(
            "AnswersUseCase",
            (),
            {"execute": lambda self, o, e, a: attempt_report},
        )()
        attempt_repo = type(
            "AttemptRepo",
            (),
            {"list_by_exam": lambda self, e: [attempt], "list_by_email": lambda self, e, email: [attempt]},
        )()

        use_case = ExportExamAttemptsAnswersUseCase(report_use_case, answers_use_case, attempt_repo)
        content, filename = use_case.execute(owner_id, exam_id)

        assert content
        assert filename.startswith("respuestas-Examen-")

    def test_raises_when_no_finished_attempts(self):
        report = {"exam_title": "Examen", "individual_reports": []}
        report_use_case = type("ReportUseCase", (), {"execute": lambda self, o, e: report})()
        answers_use_case = type("AnswersUseCase", (), {})()
        attempt_repo = type(
            "AttemptRepo",
            (),
            {"list_by_exam": lambda self, e: [], "list_by_email": lambda self, e, email: []},
        )()

        use_case = ExportExamAttemptsAnswersUseCase(report_use_case, answers_use_case, attempt_repo)
        with pytest.raises(ValidationError, match="No hay intentos finalizados"):
            use_case.execute(uuid4(), uuid4())
