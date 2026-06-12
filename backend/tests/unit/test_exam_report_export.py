from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from openpyxl import load_workbook

from app.application.exam_report_export import build_exam_report_workbook, build_export_filename


class TestExamReportExport:
    def test_build_workbook_contains_summary_and_rows(self):
        report = {
            "exam_id": "exam-1",
            "exam_title": "Examen Final",
            "total_score": 10,
            "question_count": 5,
            "individual_reports": [
                {
                    "invitee_full_name": "Ana Pérez",
                    "invitee_email": "ana@test.com",
                    "attempt_number": 1,
                    "attempts_used": 1,
                    "score": 8.5,
                    "total_score": 10,
                    "percentage": 85,
                    "status": "submitted",
                    "fraud_score": 0.1,
                    "proctoring_events_count": 2,
                    "correct_answers_count": 4,
                    "incorrect_answers_count": 1,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "summary": {
                "total_invitees": 1,
                "completed": 1,
                "average_score": 8.5,
                "highest_score": 8.5,
                "lowest_score": 8.5,
                "average_correct_answers": 4,
                "average_incorrect_answers": 1,
            },
        }

        content = build_exam_report_workbook(report)
        workbook = load_workbook(BytesIO(content))
        sheet = workbook.active

        assert sheet["A1"].value.startswith("Informe de examen:")
        assert sheet["A9"].value == "Nombre"
        assert sheet["A10"].value == "Ana Pérez"
        assert "informe-Examen-Final" in build_export_filename(report)
