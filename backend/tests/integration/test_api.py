import pytest
from datetime import datetime, timedelta, timezone

pytestmark = pytest.mark.skip(reason="Requiere PostgreSQL. Ejecutar con: docker compose up postgres -d && DATABASE_URL=postgresql://...")
from sqlalchemy import String, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.infrastructure.database.models import Base, get_db
from app.main import app


@pytest.fixture
def test_client():
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PGUUID):
                column.type = String(36)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(test_client):
    test_client.post(
        "/api/v1/auth/register",
        json={"email": "integration@test.com", "password": "password123", "full_name": "Integration Test"},
    )
    response = test_client.post(
        "/api/v1/auth/login",
        json={"email": "integration@test.com", "password": "password123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAuthIntegration:
    def test_register_and_login(self, test_client):
        response = test_client.post(
            "/api/v1/auth/register",
            json={"email": "user@test.com", "password": "password123", "full_name": "User Test"},
        )
        assert response.status_code == 201
        assert response.json()["email"] == "user@test.com"

        login_response = test_client.post(
            "/api/v1/auth/login",
            json={"email": "user@test.com", "password": "password123"},
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()

    def test_protected_route_without_token(self, test_client):
        response = test_client.get("/api/v1/auth/me")
        assert response.status_code == 403


class TestQuestionBankIntegration:
    def test_create_and_list_banks(self, test_client, auth_headers):
        create_response = test_client.post(
            "/api/v1/question-banks",
            json={"name": "Programming Bank", "description": "Questions about programming"},
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        bank_id = create_response.json()["id"]

        list_response = test_client.get("/api/v1/question-banks", headers=auth_headers)
        assert list_response.status_code == 200
        assert len(list_response.json()) >= 1
        assert any(b["id"] == bank_id for b in list_response.json())


class TestExamFlowIntegration:
    def test_full_exam_flow(self, test_client, auth_headers):
        bank_resp = test_client.post(
            "/api/v1/question-banks",
            json={"name": "Exam Bank", "description": "Test"},
            headers=auth_headers,
        )
        bank_id = bank_resp.json()["id"]

        for i in range(3):
            test_client.post(
                f"/api/v1/question-banks/{bank_id}/questions",
                data={
                    "text": f"Question {i}?",
                    "question_type": "single_choice",
                    "time_seconds": "60",
                    "options": '[{"text": "Correct", "is_correct": true}, {"text": "Wrong", "is_correct": false}]',
                },
                headers=auth_headers,
            )

        exam_resp = test_client.post(
            "/api/v1/exams",
            json={
                "title": "Integration Exam",
                "question_bank_id": bank_id,
                "mode": "simulation",
                "total_score": 30,
                "question_count": 3,
                "closes_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "random_selection": True,
            },
            headers=auth_headers,
        )
        assert exam_resp.status_code == 201
        exam_id = exam_resp.json()["id"]

        invite_resp = test_client.post(
            f"/api/v1/exams/{exam_id}/invite",
            json={"emails": ["invitee@test.com"]},
            headers=auth_headers,
        )
        assert invite_resp.status_code == 200
        token = invite_resp.json()[0]["token"]

        session_resp = test_client.get(f"/api/v1/exam-session/{token}")
        assert session_resp.status_code == 200
        assert session_resp.json()["exam_title"] == "Integration Exam"
