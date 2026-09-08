from datetime import datetime, timezone
from uuid import UUID

import json
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.application.attempt_access import (
    count_finished_attempts,
    compute_attempt_cooldown_remaining_seconds,
    get_in_progress_attempt,
    has_exhausted_attempts,
    is_finished_attempt,
)
from app.application.attempt_decision import (
    compute_decision_seconds_remaining,
    get_last_finished_attempt,
    pending_attempt_decision,
)
from app.application.exam_session import (
    build_exam_session_payload,
    get_attempt_question_ids_ordered,
    order_questions_by_attempt,
)
from app.application.exam_timing import get_remaining_seconds, get_total_exam_seconds
from app.application.use_cases import (
    CreateExamUseCase,
    CreateQuestionBankUseCase,
    CreateQuestionUseCase,
    CreateTopicUseCase,
    DeleteExamInvitationUseCase,
    DeleteInviteeExamResultsUseCase,
    DeleteExamUseCase,
    DeleteQuestionBankUseCase,
    DeleteQuestionUseCase,
    DuplicateQuestionUseCase,
    DeleteTopicUseCase,
    DomainError,
    EnableMfaUseCase,
    ExportExamReportUseCase,
    ExportExamAttemptsAnswersUseCase,
    ExportQuestionBankBackupUseCase,
    ExportQuestionBankExcelUseCase,
    TerminateExamForTabSwitchUseCase,
    FinishExamEarlyUseCase,
    PrepareNextAttemptUseCase,
    GetAttemptAnswersReportUseCase,
    GetExamReportUseCase,
    InviteToExamUseCase,
    ListExamInvitationsUseCase,
    LoginInput,
    LoginUseCase,
    NotFoundError,
    ProctoringAnalysisUseCase,
    RegisterUserInput,
    RegisterUserUseCase,
    ResendExamInvitationUseCase,
    RestoreQuestionBankBackupUseCase,
    SaveAttemptProgressUseCase,
    SaveAttemptSnapshotUseCase,
    SaveAttemptVideoUseCase,
    SetupMfaUseCase,
    StartExamAttemptUseCase,
    SubmitAnswerUseCase,
    SubmitExamUseCase,
    UnauthorizedError,
    UpdateExamUseCase,
    UpdateQuestionBankUseCase,
    UpdateQuestionUseCase,
    UpdateTopicUseCase,
    ValidationError,
)
from app.config import settings
from app.domain.enums import ProctoringEventType, SnapshotType
from app.infrastructure.database.models import get_db
from app.infrastructure.repositories.sqlalchemy_repositories import (
    SQLAlchemyAnswerRepository,
    SQLAlchemyAttemptRepository,
    SQLAlchemyAttemptSnapshotRepository,
    SQLAlchemyExamRepository,
    SQLAlchemyInvitationRepository,
    SQLAlchemyProctoringRepository,
    SQLAlchemyQuestionBankRepository,
    SQLAlchemyQuestionRepository,
    SQLAlchemyTopicRepository,
    SQLAlchemyUserRepository,
)
from app.infrastructure.services.auth_services import (
    BcryptPasswordHasher,
    JwtTokenService,
    TotpMfaService,
)
from app.infrastructure.services.email_service import get_email_service
from app.infrastructure.services.proctoring_service import LocalFileStorageService, MLProctoringService
from app.presentation.dependencies import get_current_user_id
from app.presentation.frontend_url import resolve_invitation_base_url
from app.presentation.schemas import (
    AttemptAnswerDetailResponse,
    AttemptAnswersReportResponse,
    AttemptResponse,
    CreateExamRequest,
    CreateQuestionBankRequest,
    CreateTopicRequest,
    CreateQuestionRequest,
    ExamResponse,
    ExamSessionResponse,
    InvitationDetailResponse,
    InvitationResponse,
    InviteRequest,
    LoginRequest,
    MfaEnableRequest,
    MfaSetupResponse,
    QuestionBankResponse,
    QuestionOptionResponse,
    QuestionResponse,
    PaginatedQuestionsResponse,
    RegisterRequest,
    RestoreQuestionBackupResponse,
    SaveAttemptProgressRequest,
    SavedAnswerResponse,
    StartAttemptRequest,
    SubmitAnswerRequest,
    SubmitExamRequest,
    TokenResponse,
    TopicResponse,
    UpdateTopicRequest,
    UpdateQuestionBankRequest,
    UserResponse,
)

router = APIRouter()


def _handle_domain_error(e: DomainError):
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, UnauthorizedError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    if isinstance(e, ValidationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    use_case = RegisterUserUseCase(SQLAlchemyUserRepository(db), BcryptPasswordHasher())
    try:
        user = use_case.execute(RegisterUserInput(**request.model_dump()))
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            mfa_enabled=user.mfa_enabled,
            created_at=user.created_at,
        )
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    use_case = LoginUseCase(
        SQLAlchemyUserRepository(db),
        BcryptPasswordHasher(),
        JwtTokenService(),
        TotpMfaService(),
    )
    try:
        tokens = use_case.execute(LoginInput(**request.model_dump()))
        return TokenResponse(**tokens.__dict__)
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/auth/mfa/setup", response_model=MfaSetupResponse)
def setup_mfa(user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    use_case = SetupMfaUseCase(SQLAlchemyUserRepository(db), TotpMfaService())
    try:
        result = use_case.execute(user_id)
        return MfaSetupResponse(**result)
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/auth/mfa/enable", response_model=UserResponse)
def enable_mfa(
    request: MfaEnableRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = EnableMfaUseCase(SQLAlchemyUserRepository(db), TotpMfaService())
    try:
        user = use_case.execute(user_id, request.code)
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            mfa_enabled=user.mfa_enabled,
            created_at=user.created_at,
        )
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/auth/me", response_model=UserResponse)
def get_me(user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = SQLAlchemyUserRepository(db).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        mfa_enabled=user.mfa_enabled,
        created_at=user.created_at,
    )


@router.post("/question-banks", response_model=QuestionBankResponse, status_code=201)
def create_question_bank(
    request: CreateQuestionBankRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = CreateQuestionBankUseCase(SQLAlchemyQuestionBankRepository(db))
    bank = use_case.execute(user_id, request.name, request.description)
    return _bank_to_response(
        bank, SQLAlchemyExamRepository(db), SQLAlchemyQuestionRepository(db)
    )


@router.get("/question-banks", response_model=list[QuestionBankResponse])
def list_question_banks(user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    exam_repo = SQLAlchemyExamRepository(db)
    question_repo = SQLAlchemyQuestionRepository(db)
    banks = SQLAlchemyQuestionBankRepository(db).list_by_owner(user_id)
    return [_bank_to_response(b, exam_repo, question_repo) for b in banks]


@router.get("/question-banks/{bank_id}", response_model=QuestionBankResponse)
def get_question_bank(
    bank_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    bank = SQLAlchemyQuestionBankRepository(db).get_by_id(bank_id)
    if not bank or bank.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Question bank not found")
    return _bank_to_response(
        bank, SQLAlchemyExamRepository(db), SQLAlchemyQuestionRepository(db)
    )


@router.put("/question-banks/{bank_id}", response_model=QuestionBankResponse)
def update_question_bank(
    bank_id: UUID,
    request: UpdateQuestionBankRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = UpdateQuestionBankUseCase(SQLAlchemyQuestionBankRepository(db))
    try:
        bank = use_case.execute(user_id, bank_id, request.name, request.description)
        return _bank_to_response(
            bank, SQLAlchemyExamRepository(db), SQLAlchemyQuestionRepository(db)
        )
    except DomainError as e:
        _handle_domain_error(e)


@router.delete("/question-banks/{bank_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question_bank(
    bank_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = DeleteQuestionBankUseCase(
        SQLAlchemyQuestionBankRepository(db),
        SQLAlchemyExamRepository(db),
    )
    try:
        use_case.execute(user_id, bank_id)
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/topics", response_model=TopicResponse, status_code=201)
def create_topic(
    request: CreateTopicRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = CreateTopicUseCase(SQLAlchemyTopicRepository(db))
    try:
        topic = use_case.execute(user_id, request.name, request.description)
        return _topic_to_response(topic)
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/topics", response_model=list[TopicResponse])
def list_topics(user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    topics = SQLAlchemyTopicRepository(db).list_by_owner(user_id)
    return [_topic_to_response(t) for t in topics]


@router.put("/topics/{topic_id}", response_model=TopicResponse)
def update_topic(
    topic_id: UUID,
    request: UpdateTopicRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = UpdateTopicUseCase(SQLAlchemyTopicRepository(db))
    try:
        topic = use_case.execute(user_id, topic_id, request.name, request.description)
        return _topic_to_response(topic)
    except DomainError as e:
        _handle_domain_error(e)


@router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(
    topic_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = DeleteTopicUseCase(SQLAlchemyTopicRepository(db))
    try:
        use_case.execute(user_id, topic_id)
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/question-banks/{bank_id}/questions", response_model=QuestionResponse, status_code=201)
async def create_question(
    bank_id: UUID,
    text: str = Form(...),
    question_type: str = Form(...),
    time_seconds: int = Form(...),
    topic_id: str | None = Form(None),
    options: str = Form("[]"),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    image: UploadFile | None = File(None),
):
    from app.domain.enums import QuestionType

    image_url = None
    if image:
        content = await image.read()
        storage = LocalFileStorageService()
        image_url = await storage.save_image(content, image.filename or "image.jpg")

    parsed_options = json.loads(options) if options else []

    parsed_topic_id = UUID(topic_id) if topic_id else None

    use_case = CreateQuestionUseCase(
        SQLAlchemyQuestionBankRepository(db),
        SQLAlchemyQuestionRepository(db),
        SQLAlchemyTopicRepository(db),
    )
    try:
        question = use_case.execute(
            owner_id=user_id,
            bank_id=bank_id,
            text=text,
            question_type=QuestionType(question_type),
            time_seconds=time_seconds,
            topic_id=parsed_topic_id,
            options=parsed_options,
            image_url=image_url,
        )
        return _question_to_response(question, SQLAlchemyExamRepository(db))
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/question-banks/{bank_id}/questions", response_model=PaginatedQuestionsResponse)
def list_questions(
    bank_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    bank = SQLAlchemyQuestionBankRepository(db).get_by_id(bank_id)
    if not bank or bank.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Question bank not found")

    question_repo = SQLAlchemyQuestionRepository(db)
    exam_repo = SQLAlchemyExamRepository(db)
    normalized_search = search.strip() if search else None
    if normalized_search == "":
        normalized_search = None

    total = question_repo.count_by_bank(bank_id, normalized_search)
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 0
    if total > 0 and page > total_pages:
        page = total_pages

    questions = question_repo.list_by_bank_paginated(bank_id, page, page_size, normalized_search)
    return PaginatedQuestionsResponse(
        items=[_question_to_response(q, exam_repo) for q in questions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.put("/question-banks/{bank_id}/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    bank_id: UUID,
    question_id: UUID,
    text: str = Form(...),
    question_type: str = Form(...),
    time_seconds: int = Form(...),
    topic_id: str | None = Form(None),
    options: str = Form("[]"),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    image: UploadFile | None = File(None),
):
    from app.domain.enums import QuestionType

    image_url = None
    if image:
        content = await image.read()
        storage = LocalFileStorageService()
        image_url = await storage.save_image(content, image.filename or "image.jpg")

    parsed_options = json.loads(options) if options else []
    parsed_topic_id = UUID(topic_id) if topic_id else None

    use_case = UpdateQuestionUseCase(
        SQLAlchemyQuestionBankRepository(db),
        SQLAlchemyQuestionRepository(db),
        SQLAlchemyTopicRepository(db),
    )
    try:
        question = use_case.execute(
            owner_id=user_id,
            bank_id=bank_id,
            question_id=question_id,
            text=text,
            question_type=QuestionType(question_type),
            time_seconds=time_seconds,
            topic_id=parsed_topic_id,
            options=parsed_options,
            image_url=image_url,
        )
        return _question_to_response(question, SQLAlchemyExamRepository(db))
    except DomainError as e:
        _handle_domain_error(e)


@router.delete("/question-banks/{bank_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    bank_id: UUID,
    question_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = DeleteQuestionUseCase(
        SQLAlchemyQuestionBankRepository(db),
        SQLAlchemyQuestionRepository(db),
        SQLAlchemyExamRepository(db),
    )
    try:
        use_case.execute(user_id, bank_id, question_id)
    except DomainError as e:
        _handle_domain_error(e)


@router.post(
    "/question-banks/{bank_id}/questions/{question_id}/duplicate",
    response_model=QuestionResponse,
    status_code=201,
)
def duplicate_question(
    bank_id: UUID,
    question_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = DuplicateQuestionUseCase(
        SQLAlchemyQuestionBankRepository(db),
        SQLAlchemyQuestionRepository(db),
        settings.upload_dir,
    )
    try:
        question = use_case.execute(user_id, bank_id, question_id)
        return _question_to_response(question, SQLAlchemyExamRepository(db))
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/question-banks/{bank_id}/questions/backup")
def export_question_backup(
    bank_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = ExportQuestionBankBackupUseCase(
        SQLAlchemyQuestionBankRepository(db),
        SQLAlchemyQuestionRepository(db),
    )
    try:
        backup = use_case.execute(user_id, bank_id)
    except DomainError as e:
        _handle_domain_error(e)

    safe_name = re.sub(r"[^\w\-]+", "-", backup["bank_name"]).strip("-") or "banco"
    filename = f"backup-{safe_name}.json"
    content = json.dumps(backup, ensure_ascii=False, indent=2)
    return Response(
        content=content.encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/question-banks/{bank_id}/questions/export")
def export_question_bank_excel(
    bank_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = ExportQuestionBankExcelUseCase(
        SQLAlchemyQuestionBankRepository(db),
        SQLAlchemyQuestionRepository(db),
    )
    try:
        content, filename = use_case.execute(user_id, bank_id)
    except DomainError as e:
        _handle_domain_error(e)

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/question-banks/{bank_id}/questions/restore", response_model=RestoreQuestionBackupResponse)
async def restore_question_backup(
    bank_id: UUID,
    file: UploadFile = File(...),
    mode: str = Form("append"),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    try:
        backup_data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Archivo de backup inválido")

    use_case = RestoreQuestionBankBackupUseCase(
        SQLAlchemyQuestionBankRepository(db),
        SQLAlchemyQuestionRepository(db),
        SQLAlchemyTopicRepository(db),
        SQLAlchemyExamRepository(db),
    )
    try:
        return use_case.execute(user_id, bank_id, backup_data, mode=mode)
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/exams", response_model=ExamResponse, status_code=201)
def create_exam(
    request: CreateExamRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = CreateExamUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyQuestionBankRepository(db),
        SQLAlchemyQuestionRepository(db),
    )
    try:
        exam = use_case.execute(user_id, request.model_dump())
        return _exam_to_response(exam, SQLAlchemyAttemptRepository(db))
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/exams", response_model=list[ExamResponse])
def list_exams(user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    exam_repo = SQLAlchemyExamRepository(db)
    attempt_repo = SQLAlchemyAttemptRepository(db)
    exams = exam_repo.list_by_owner(user_id)
    return [_exam_to_response(e, attempt_repo) for e in exams]


@router.get("/exams/{exam_id}", response_model=ExamResponse)
def get_exam(
    exam_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    exam_repo = SQLAlchemyExamRepository(db)
    attempt_repo = SQLAlchemyAttemptRepository(db)
    exam = exam_repo.get_by_id(exam_id)
    if not exam or exam.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Exam not found")
    return _exam_to_response(exam, attempt_repo)


@router.put("/exams/{exam_id}", response_model=ExamResponse)
def update_exam(
    exam_id: UUID,
    request: CreateExamRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = UpdateExamUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyQuestionBankRepository(db),
        SQLAlchemyQuestionRepository(db),
        SQLAlchemyAttemptRepository(db),
    )
    try:
        exam = use_case.execute(user_id, exam_id, request.model_dump())
        return _exam_to_response(exam, SQLAlchemyAttemptRepository(db))
    except DomainError as e:
        _handle_domain_error(e)


@router.delete("/exams/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(
    exam_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = DeleteExamUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyAttemptSnapshotRepository(db),
        settings.upload_dir,
    )
    try:
        use_case.execute(user_id, exam_id)
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/exams/{exam_id}/invite", response_model=list[InvitationResponse])
async def invite_to_exam(
    exam_id: UUID,
    request: InviteRequest,
    http_request: Request,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    email_service = get_email_service()
    use_case = InviteToExamUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyAttemptRepository(db),
        email_service,
        resolve_invitation_base_url(),
    )
    try:
        invitations = await use_case.execute(user_id, exam_id, [str(e) for e in request.emails])
        return [
            InvitationResponse(
                id=i.id, invitee_email=i.invitee_email, token=i.token, status=i.status.value
            )
            for i in invitations
        ]
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/exams/{exam_id}/invitations", response_model=list[InvitationDetailResponse])
def list_exam_invitations(
    exam_id: UUID,
    http_request: Request,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = ListExamInvitationsUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyAttemptRepository(db),
        resolve_invitation_base_url(),
    )
    try:
        return use_case.execute(user_id, exam_id)
    except DomainError as e:
        _handle_domain_error(e)


@router.delete("/exams/{exam_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam_invitation(
    exam_id: UUID,
    invitation_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = DeleteExamInvitationUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyAttemptRepository(db),
    )
    try:
        use_case.execute(user_id, exam_id, invitation_id)
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/exams/{exam_id}/invitations/{invitation_id}/resend", response_model=InvitationDetailResponse)
async def resend_exam_invitation(
    exam_id: UUID,
    invitation_id: UUID,
    http_request: Request,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    email_service = get_email_service()
    frontend_url = resolve_invitation_base_url()
    use_case = ResendExamInvitationUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyInvitationRepository(db),
        email_service,
        frontend_url,
    )
    try:
        invitation = await use_case.execute(user_id, exam_id, invitation_id)
        exam = SQLAlchemyExamRepository(db).get_by_id(exam_id)
        attempt_repo = SQLAlchemyAttemptRepository(db)
        invitation_attempts = attempt_repo.list_by_invitation(invitation.id)
        in_progress = attempt_repo.get_in_progress_by_invitation(invitation.id)
        attempt_status = (
            in_progress.status.value
            if in_progress
            else invitation_attempts[-1].status.value
            if invitation_attempts
            else "not_started"
        )
        return InvitationDetailResponse(
            id=invitation.id,
            invitee_email=invitation.invitee_email,
            token=invitation.token,
            status=invitation.status.value,
            sent_at=invitation.sent_at,
            created_at=invitation.created_at,
            attempt_status=attempt_status,
            attempts_completed=count_finished_attempts(invitation_attempts),
            attempts_total=exam.max_attempts if exam else 1,
            invite_link=f"{frontend_url}/exam/take/{invitation.token}",
        )
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/exams/{exam_id}/report")
def get_exam_report(
    exam_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = GetExamReportUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyAnswerRepository(db),
        SQLAlchemyProctoringRepository(db),
    )
    try:
        return use_case.execute(user_id, exam_id)
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/exams/{exam_id}/report/export")
def export_exam_report(
    exam_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    report_use_case = GetExamReportUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyAnswerRepository(db),
        SQLAlchemyProctoringRepository(db),
    )
    use_case = ExportExamReportUseCase(report_use_case)
    try:
        content, filename = use_case.execute(user_id, exam_id)
    except DomainError as e:
        _handle_domain_error(e)

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/exams/{exam_id}/report/answers/export")
def export_exam_attempts_answers(
    exam_id: UUID,
    email: str | None = Query(None, min_length=1),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    report_use_case = GetExamReportUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyAnswerRepository(db),
        SQLAlchemyProctoringRepository(db),
    )
    answers_use_case = GetAttemptAnswersReportUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyAnswerRepository(db),
        SQLAlchemyQuestionRepository(db),
        SQLAlchemyAttemptSnapshotRepository(db),
    )
    use_case = ExportExamAttemptsAnswersUseCase(
        report_use_case,
        answers_use_case,
        SQLAlchemyAttemptRepository(db),
    )
    try:
        content, filename = use_case.execute(user_id, exam_id, email)
    except DomainError as e:
        _handle_domain_error(e)

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/exams/{exam_id}/invitee-results")
def delete_invitee_exam_results(
    exam_id: UUID,
    email: str = Query(..., min_length=1),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = DeleteInviteeExamResultsUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyAttemptSnapshotRepository(db),
        settings.upload_dir,
    )
    try:
        return use_case.execute(user_id, exam_id, email)
    except DomainError as e:
        _handle_domain_error(e)


@router.get(
    "/exams/{exam_id}/attempts/{attempt_id}/answers",
    response_model=AttemptAnswersReportResponse,
)
def get_attempt_answers_report(
    exam_id: UUID,
    attempt_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = GetAttemptAnswersReportUseCase(
        SQLAlchemyExamRepository(db),
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyAnswerRepository(db),
        SQLAlchemyQuestionRepository(db),
        SQLAlchemyAttemptSnapshotRepository(db),
    )
    try:
        return use_case.execute(user_id, exam_id, attempt_id)
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/exam-session/{token}/start", response_model=ExamSessionResponse)
def start_exam_session(token: str, request: StartAttemptRequest, db: Session = Depends(get_db)):
    question_repo = SQLAlchemyQuestionRepository(db)
    answer_repo = SQLAlchemyAnswerRepository(db)
    use_case = StartExamAttemptUseCase(
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyExamRepository(db),
        question_repo,
    )
    try:
        attempt = use_case.execute(token, request.camera_verified, request.full_name)
        exam = SQLAlchemyExamRepository(db).get_by_id(attempt.exam_id)
        saved_answers = answer_repo.get_by_attempt(attempt.id)
        resumed = bool(
            saved_answers
            or attempt.current_question_index > 0
            or attempt.locked_question_ids
        )
        return _build_exam_session_response(db, exam, attempt, resumed=resumed)
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/exam-session/{token}")
def get_exam_session(token: str, db: Session = Depends(get_db)):
    invitation_repo = SQLAlchemyInvitationRepository(db)
    attempt_repo = SQLAlchemyAttemptRepository(db)

    invitation = invitation_repo.get_by_token(token)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invalid token")

    exam = SQLAlchemyExamRepository(db).get_by_id(invitation.exam_id)
    email_attempts = attempt_repo.list_by_email(invitation.exam_id, invitation.invitee_email)
    finished_count = count_finished_attempts(email_attempts)
    in_progress = get_in_progress_attempt(email_attempts)
    attempt = in_progress or attempt_repo.get_in_progress_by_invitation(invitation.id)
    if not attempt:
        invitation_attempts = attempt_repo.list_by_invitation(invitation.id)
        attempt = invitation_attempts[-1] if invitation_attempts else None

    bank_questions = SQLAlchemyQuestionRepository(db).list_by_bank(exam.question_bank_id)
    total_time = get_total_exam_seconds(exam, attempt, bank_questions)
    remaining = get_remaining_seconds(exam, attempt, bank_questions)

    attempts_remaining = max(exam.max_attempts - finished_count, 0)
    from app.domain.enums import InvitationStatus

    exam_finalized = invitation.status == InvitationStatus.COMPLETED
    email_already_completed = exam_finalized or has_exhausted_attempts(exam, email_attempts)
    email_in_progress = (
        in_progress is not None and in_progress.invitation_id != invitation.id
    )

    finished_attempts = [
        attempt for attempt in email_attempts if is_finished_attempt(attempt)
    ]
    last_finished = get_last_finished_attempt(email_attempts)
    proctoring_repo = SQLAlchemyProctoringRepository(db)
    terminated_for_violation = any(
        any(
            event.event_type == ProctoringEventType.TAB_SWITCH
            for event in proctoring_repo.list_by_attempt(attempt.id)
        )
        for attempt in email_attempts
    )

    attempt_status = attempt.status.value if attempt else "not_started"
    if email_already_completed and attempt_status not in ("submitted", "timed_out", "in_progress"):
        attempt_status = "already_completed_by_email"
    elif email_in_progress and attempt_status != "in_progress":
        attempt_status = "already_in_progress_by_email"

    can_start_new_attempt = (
        not email_already_completed
        and not email_in_progress
        and attempt_status != "in_progress"
    )
    attempt_cooldown_remaining = compute_attempt_cooldown_remaining_seconds(exam, email_attempts)
    if attempt_cooldown_remaining > 0:
        can_start_new_attempt = False

    if in_progress:
        display_attempt_number = in_progress.attempt_number
    elif can_start_new_attempt and finished_count < exam.max_attempts:
        display_attempt_number = finished_count + 1
    elif attempt:
        display_attempt_number = attempt.attempt_number
    else:
        display_attempt_number = 1

    can_finish_early = (
        not exam_finalized
        and finished_count > 0
        and not has_exhausted_attempts(exam, email_attempts)
    )
    pending_decision = pending_attempt_decision(
        invitation,
        in_progress,
        can_start_new_attempt,
        can_finish_early,
        last_finished,
    )

    decision_seconds_remaining = None
    auto_finalized = False
    final_score = last_finished.score if last_finished else None
    if pending_decision and invitation.decision_deadline_at:
        decision_seconds_remaining = compute_decision_seconds_remaining(
            invitation.decision_deadline_at
        )
        if decision_seconds_remaining == 0:
            finish_use_case = FinishExamEarlyUseCase(invitation_repo, attempt_repo)
            try:
                finish_result = finish_use_case.execute(token)
            except DomainError:
                finish_result = None
            if finish_result:
                auto_finalized = True
                exam_finalized = True
                can_start_new_attempt = False
                can_finish_early = False
                pending_decision = False
                decision_seconds_remaining = 0
                final_score = finish_result.get("final_score", final_score)

    return {
        "exam_title": exam.title,
        "exam_total_score": exam.total_score,
        "require_attempt_video": exam.require_camera and exam.require_attempt_video,
        "require_camera": exam.require_camera,
        "mode": exam.mode.value,
        "question_count": exam.question_count,
        "max_attempts": exam.max_attempts,
        "attempt_policy": exam.attempt_policy.value,
        "attempt_cooldown_enabled": exam.attempt_cooldown_enabled,
        "attempt_cooldown_seconds": exam.attempt_cooldown_seconds if exam.attempt_cooldown_enabled else 0,
        "attempt_cooldown_remaining_seconds": attempt_cooldown_remaining,
        "attempts_used": finished_count,
        "attempts_remaining": attempts_remaining,
        "total_time_seconds": total_time,
        "remaining_seconds": remaining,
        "attempt_status": attempt_status,
        "current_attempt_number": display_attempt_number,
        "email_already_completed": email_already_completed,
        "email_in_progress": email_in_progress,
        "can_start_new_attempt": can_start_new_attempt,
        "can_finish_early": can_finish_early,
        "exam_finalized": exam_finalized,
        "final_score": final_score,
        "pending_decision": pending_decision,
        "decision_seconds_remaining": decision_seconds_remaining,
        "auto_finalized": auto_finalized,
        "requires_next_attempt": (
            exam.attempt_policy.value == "sequential"
            and finished_count > 0
            and not email_already_completed
        ),
        "invitee_email": invitation.invitee_email,
        "invitee_full_name": attempt.invitee_full_name if attempt else "",
        "has_in_progress_attempt": (
            in_progress is not None and in_progress.invitation_id == invitation.id
        ),
        "terminated_for_violation": terminated_for_violation,
    }


@router.post("/exam-session/{token}/prepare-next-attempt")
def prepare_next_attempt(token: str, db: Session = Depends(get_db)):
    use_case = PrepareNextAttemptUseCase(
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyExamRepository(db),
    )
    try:
        return use_case.execute(token)
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/exam-session/{token}/finish")
def finish_exam_session(token: str, db: Session = Depends(get_db)):
    use_case = FinishExamEarlyUseCase(
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyAttemptRepository(db),
    )
    try:
        return use_case.execute(token)
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/exam-session/{token}/tab-switch-violation")
def terminate_exam_for_tab_switch(token: str, db: Session = Depends(get_db)):
    attempt_repo = SQLAlchemyAttemptRepository(db)
    invitation_repo = SQLAlchemyInvitationRepository(db)
    answer_repo = SQLAlchemyAnswerRepository(db)
    exam_repo = SQLAlchemyExamRepository(db)
    submit_use_case = SubmitExamUseCase(
        attempt_repo,
        answer_repo,
        invitation_repo,
        exam_repo,
    )
    use_case = TerminateExamForTabSwitchUseCase(
        invitation_repo,
        attempt_repo,
        SQLAlchemyProctoringRepository(db),
        submit_use_case,
    )
    try:
        return use_case.execute(token)
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/attempts/{attempt_id}/answers")
def submit_answer(attempt_id: UUID, request: SubmitAnswerRequest, db: Session = Depends(get_db)):
    use_case = SubmitAnswerUseCase(
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyAnswerRepository(db),
        SQLAlchemyExamRepository(db),
        SQLAlchemyQuestionRepository(db),
    )
    try:
        answer = use_case.execute(
            attempt_id, request.question_id, request.selected_option_ids, request.open_text
        )
        return {
            "question_id": str(answer.question_id),
            "is_correct": answer.is_correct,
            "points_earned": answer.points_earned,
        }
    except DomainError as e:
        _handle_domain_error(e)


@router.put("/attempts/{attempt_id}/progress")
def save_attempt_progress(
    attempt_id: UUID,
    request: SaveAttemptProgressRequest,
    db: Session = Depends(get_db),
):
    use_case = SaveAttemptProgressUseCase(
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyExamRepository(db),
    )
    try:
        attempt = use_case.execute(
            attempt_id,
            request.current_question_index,
            request.locked_question_ids,
        )
        return {
            "current_question_index": attempt.current_question_index,
            "locked_question_ids": [str(question_id) for question_id in attempt.locked_question_ids],
        }
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptResponse)
def submit_exam(
    attempt_id: UUID,
    request: SubmitExamRequest = SubmitExamRequest(),
    db: Session = Depends(get_db),
):
    use_case = SubmitExamUseCase(
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyAnswerRepository(db),
        SQLAlchemyInvitationRepository(db),
        SQLAlchemyExamRepository(db),
    )
    try:
        attempt = use_case.execute(attempt_id, skip_video_required=request.skip_video_required)
        return AttemptResponse(
            id=attempt.id,
            exam_id=attempt.exam_id,
            status=attempt.status.value,
            attempt_number=attempt.attempt_number,
            started_at=attempt.started_at,
            score=attempt.score,
            fraud_score=attempt.fraud_score,
        )
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/attempts/{attempt_id}/video")
async def save_attempt_video(
    attempt_id: UUID,
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    video_data = await video.read()
    max_bytes = settings.max_video_upload_size_mb * 1024 * 1024
    if not video_data:
        raise HTTPException(status_code=400, detail="Empty video")
    if len(video_data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"El video supera el tamaño máximo de {settings.max_video_upload_size_mb} MB",
        )

    storage = LocalFileStorageService()
    video_url = await storage.save_video(video_data, video.filename or "attempt.webm")

    use_case = SaveAttemptVideoUseCase(
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyExamRepository(db),
    )
    try:
        attempt = use_case.execute(attempt_id, video_url)
        return {
            "attempt_id": str(attempt.id),
            "video_url": attempt.attempt_video_url,
        }
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/attempts/{attempt_id}/snapshots")
async def save_attempt_snapshot(
    attempt_id: UUID,
    snapshot_type: str = Form(...),
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        parsed_type = SnapshotType(snapshot_type)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid snapshot type") from error

    frame_data = await frame.read()
    if not frame_data:
        raise HTTPException(status_code=400, detail="Empty frame")

    storage = LocalFileStorageService()
    image_url = await storage.save_image(frame_data, frame.filename or "snapshot.jpg")

    use_case = SaveAttemptSnapshotUseCase(
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyExamRepository(db),
        SQLAlchemyAttemptSnapshotRepository(db),
    )
    try:
        snapshot = use_case.execute(attempt_id, parsed_type, image_url)
        return {
            "id": str(snapshot.id),
            "snapshot_type": snapshot.snapshot_type.value,
            "image_url": snapshot.image_url,
            "captured_at": snapshot.captured_at.isoformat() if snapshot.captured_at else None,
        }
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/attempts/{attempt_id}/proctoring")
async def analyze_proctoring(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    frame: UploadFile = File(...),
    mouse_events: str = "[]",
):
    import json

    frame_data = await frame.read()
    events = json.loads(mouse_events)
    use_case = ProctoringAnalysisUseCase(
        SQLAlchemyAttemptRepository(db),
        SQLAlchemyExamRepository(db),
        SQLAlchemyProctoringRepository(db),
        MLProctoringService(),
        settings.proctoring_fraud_threshold,
    )
    try:
        event = use_case.execute(attempt_id, frame_data, events)
        return {"fraud_detected": event is not None, "event": event.event_type.value if event else None}
    except DomainError as e:
        _handle_domain_error(e)


def _build_exam_session_response(db: Session, exam, attempt, *, resumed: bool = False) -> ExamSessionResponse:
    question_repo = SQLAlchemyQuestionRepository(db)
    answer_repo = SQLAlchemyAnswerRepository(db)
    bank_questions = question_repo.list_by_bank(exam.question_bank_id)
    question_ids = get_attempt_question_ids_ordered(exam, attempt)
    questions = order_questions_by_attempt(question_repo, question_ids)
    answers = answer_repo.get_by_attempt(attempt.id)
    payload = build_exam_session_payload(
        exam,
        attempt,
        questions,
        bank_questions,
        answers,
        resumed=resumed,
    )
    return ExamSessionResponse(
        attempt=AttemptResponse(
            id=attempt.id,
            exam_id=attempt.exam_id,
            status=attempt.status.value,
            attempt_number=attempt.attempt_number,
            started_at=attempt.started_at,
            score=attempt.score,
            fraud_score=attempt.fraud_score,
        ),
        exam=_exam_to_response(exam),
        questions=[_question_to_response(question, hide_correct=True) for question in questions],
        total_time_seconds=payload["total_time_seconds"],
        remaining_seconds=payload["remaining_seconds"],
        saved_answers=[
            SavedAnswerResponse(
                question_id=UUID(item["question_id"]),
                selected_option_ids=[UUID(option_id) for option_id in item["selected_option_ids"]],
                open_text=item["open_text"],
            )
            for item in payload["saved_answers"]
        ],
        current_question_index=payload["current_question_index"],
        locked_question_ids=[UUID(question_id) for question_id in payload["locked_question_ids"]],
        question_remaining_seconds=payload["question_remaining_seconds"],
        resumed=payload["resumed"],
    )


def _question_to_response(
    question,
    exam_repo: SQLAlchemyExamRepository | None = None,
    hide_correct: bool = False,
) -> QuestionResponse:
    options = []
    for o in question.options:
        opt = QuestionOptionResponse(id=o.id, text=o.text, is_correct=o.is_correct, order=o.order)
        if hide_correct:
            opt.is_correct = False
        options.append(opt)
    used_in_exam = False
    if exam_repo:
        used_in_exam = exam_repo.count_exams_using_question(question.id) > 0
    return QuestionResponse(
        id=question.id,
        text=question.text,
        question_type=question.question_type,
        topic_id=question.topic_id,
        topic_name=question.topic_name,
        time_seconds=question.time_seconds,
        image_url=question.image_url,
        options=options,
        used_in_exam=used_in_exam,
    )


def _exam_to_response(exam, attempt_repo: SQLAlchemyAttemptRepository | None = None) -> ExamResponse:
    has_attempts = False
    if attempt_repo:
        has_attempts = len(attempt_repo.list_by_exam(exam.id)) > 0
    return ExamResponse(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        mode=exam.mode,
        status=exam.status.value,
        total_score=exam.total_score,
        question_count=exam.question_count,
        closes_at=exam.closes_at,
        random_selection=exam.random_selection,
        enforce_question_time=exam.enforce_question_time,
        require_camera=exam.require_camera,
        require_attempt_video=exam.require_camera and exam.require_attempt_video,
        max_attempts=exam.max_attempts,
        attempt_policy=exam.attempt_policy,
        proctoring_sensitivity=exam.proctoring_sensitivity,
        attempt_cooldown_enabled=exam.attempt_cooldown_enabled,
        attempt_cooldown_seconds=exam.attempt_cooldown_seconds,
        question_bank_id=exam.question_bank_id,
        has_attempts=has_attempts,
    )


def _bank_to_response(
    bank,
    exam_repo: SQLAlchemyExamRepository | None = None,
    question_repo: SQLAlchemyQuestionRepository | None = None,
) -> QuestionBankResponse:
    has_exams = False
    if exam_repo:
        has_exams = exam_repo.count_by_question_bank(bank.id) > 0
    question_count = question_repo.count_by_bank(bank.id) if question_repo else 0
    return QuestionBankResponse(
        id=bank.id,
        name=bank.name,
        description=bank.description,
        owner_id=bank.owner_id,
        created_at=bank.created_at,
        has_exams=has_exams,
        question_count=question_count,
    )


def _topic_to_response(topic) -> TopicResponse:
    return TopicResponse(
        id=topic.id,
        name=topic.name,
        description=topic.description,
        owner_id=topic.owner_id,
        created_at=topic.created_at,
    )
