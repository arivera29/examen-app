from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.application.use_cases import DomainError
from app.application.whiteboards import (
    CreateWhiteboardUseCase,
    DeleteWhiteboardUseCase,
    DuplicateWhiteboardUseCase,
    GetWhiteboardUseCase,
    ListWhiteboardsUseCase,
    UpdateWhiteboardUseCase,
)
from app.domain.entities import Whiteboard
from app.infrastructure.database.models import get_db
from app.infrastructure.repositories.sqlalchemy_repositories import SQLAlchemyWhiteboardRepository
from app.presentation.api.routes import _handle_domain_error
from app.presentation.dependencies import get_current_user_id
from app.presentation.schemas import (
    CreateWhiteboardRequest,
    DuplicateWhiteboardRequest,
    UpdateWhiteboardRequest,
    WhiteboardResponse,
    WhiteboardSummaryResponse,
)

router = APIRouter(prefix="/whiteboards", tags=["whiteboards"])


def _to_summary(whiteboard: Whiteboard) -> WhiteboardSummaryResponse:
    return WhiteboardSummaryResponse(
        id=whiteboard.id,
        name=whiteboard.name,
        background_color=whiteboard.background_color,
        width=whiteboard.width,
        height=whiteboard.height,
        thumbnail=whiteboard.thumbnail,
        created_at=whiteboard.created_at,
        updated_at=whiteboard.updated_at,
    )


def _to_response(whiteboard: Whiteboard) -> WhiteboardResponse:
    return WhiteboardResponse(
        **_to_summary(whiteboard).model_dump(),
        content=whiteboard.content,
    )


@router.get("", response_model=list[WhiteboardSummaryResponse])
def list_whiteboards(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    whiteboards = ListWhiteboardsUseCase(SQLAlchemyWhiteboardRepository(db)).execute(user_id)
    return [_to_summary(w) for w in whiteboards]


@router.post("", response_model=WhiteboardResponse, status_code=status.HTTP_201_CREATED)
def create_whiteboard(
    request: CreateWhiteboardRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = CreateWhiteboardUseCase(SQLAlchemyWhiteboardRepository(db))
    try:
        whiteboard = use_case.execute(
            user_id,
            request.name,
            background_color=request.background_color,
            width=request.width,
            height=request.height,
        )
        return _to_response(whiteboard)
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/{whiteboard_id}", response_model=WhiteboardResponse)
def get_whiteboard(
    whiteboard_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = GetWhiteboardUseCase(SQLAlchemyWhiteboardRepository(db))
    try:
        return _to_response(use_case.execute(user_id, whiteboard_id))
    except DomainError as e:
        _handle_domain_error(e)


@router.put("/{whiteboard_id}", response_model=WhiteboardResponse)
def update_whiteboard(
    whiteboard_id: UUID,
    request: UpdateWhiteboardRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = UpdateWhiteboardUseCase(SQLAlchemyWhiteboardRepository(db))
    clear_thumbnail = "thumbnail" in request.model_fields_set and request.thumbnail is None
    try:
        whiteboard = use_case.execute(
            user_id,
            whiteboard_id,
            name=request.name,
            background_color=request.background_color,
            width=request.width,
            height=request.height,
            content=request.content,
            thumbnail=request.thumbnail,
            clear_thumbnail=clear_thumbnail,
        )
        return _to_response(whiteboard)
    except DomainError as e:
        _handle_domain_error(e)


@router.post(
    "/{whiteboard_id}/duplicate",
    response_model=WhiteboardSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_whiteboard(
    whiteboard_id: UUID,
    request: DuplicateWhiteboardRequest | None = None,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = DuplicateWhiteboardUseCase(SQLAlchemyWhiteboardRepository(db))
    try:
        whiteboard = use_case.execute(user_id, whiteboard_id, request.name if request else None)
        return _to_summary(whiteboard)
    except DomainError as e:
        _handle_domain_error(e)


@router.delete("/{whiteboard_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_whiteboard(
    whiteboard_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    use_case = DeleteWhiteboardUseCase(SQLAlchemyWhiteboardRepository(db))
    try:
        use_case.execute(user_id, whiteboard_id)
    except DomainError as e:
        _handle_domain_error(e)
