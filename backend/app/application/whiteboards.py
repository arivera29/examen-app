"""Casos de uso del módulo de pizarras (whiteboards) por usuario."""

import re
from copy import deepcopy
from typing import Any, Optional
from uuid import UUID

from app.application.use_cases import NotFoundError, ValidationError
from app.domain.entities import Whiteboard
from app.domain.repositories import WhiteboardRepository

DEFAULT_BACKGROUND_COLOR = "#ffffff"
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
MIN_DIMENSION = 320
MAX_DIMENSION = 4096
MAX_NAME_LENGTH = 255
MAX_ELEMENTS = 20000
MAX_THUMBNAIL_LENGTH = 1_500_000

ALLOWED_ELEMENT_TYPES = frozenset(
    {"pen", "highlighter", "eraser", "line", "arrow", "rect", "ellipse", "triangle", "diamond", "text"}
)
ALLOWED_THUMBNAIL_PREFIXES = ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_name(name: Optional[str]) -> str:
    value = (name or "").strip()
    if not value:
        raise ValidationError("Whiteboard name is required")
    if len(value) > MAX_NAME_LENGTH:
        raise ValidationError(f"Whiteboard name must be at most {MAX_NAME_LENGTH} characters")
    return value


def normalize_color(color: Optional[str]) -> str:
    value = (color or DEFAULT_BACKGROUND_COLOR).strip()
    if not _HEX_COLOR_RE.match(value):
        raise ValidationError("Background color must be a hex color like #ffffff")
    return value.lower()


def validate_dimension(value: Optional[int], default: int, label: str) -> int:
    if value is None:
        return default
    if value < MIN_DIMENSION or value > MAX_DIMENSION:
        raise ValidationError(f"Whiteboard {label} must be between {MIN_DIMENSION} and {MAX_DIMENSION}")
    return value


def validate_content(content: Any) -> list[dict]:
    if not isinstance(content, list):
        raise ValidationError("Whiteboard content must be a list of elements")
    if len(content) > MAX_ELEMENTS:
        raise ValidationError(f"Whiteboard cannot have more than {MAX_ELEMENTS} elements")
    for element in content:
        if not isinstance(element, dict):
            raise ValidationError("Each whiteboard element must be an object")
        if element.get("type") not in ALLOWED_ELEMENT_TYPES:
            raise ValidationError(f"Unsupported whiteboard element type: {element.get('type')!r}")
    return content


def validate_thumbnail(thumbnail: Optional[str]) -> Optional[str]:
    if thumbnail is None or thumbnail == "":
        return None
    if not thumbnail.startswith(ALLOWED_THUMBNAIL_PREFIXES):
        raise ValidationError("Thumbnail must be a PNG, JPEG or WEBP data URL")
    if len(thumbnail) > MAX_THUMBNAIL_LENGTH:
        raise ValidationError("Thumbnail is too large")
    return thumbnail


def _get_owned(repo: WhiteboardRepository, owner_id: UUID, whiteboard_id: UUID) -> Whiteboard:
    whiteboard = repo.get_by_id(whiteboard_id)
    if not whiteboard or whiteboard.owner_id != owner_id:
        raise NotFoundError("Whiteboard not found")
    return whiteboard


class ListWhiteboardsUseCase:
    def __init__(self, repo: WhiteboardRepository):
        self._repo = repo

    def execute(self, owner_id: UUID) -> list[Whiteboard]:
        return self._repo.list_by_owner(owner_id)


class GetWhiteboardUseCase:
    def __init__(self, repo: WhiteboardRepository):
        self._repo = repo

    def execute(self, owner_id: UUID, whiteboard_id: UUID) -> Whiteboard:
        return _get_owned(self._repo, owner_id, whiteboard_id)


class CreateWhiteboardUseCase:
    def __init__(self, repo: WhiteboardRepository):
        self._repo = repo

    def execute(
        self,
        owner_id: UUID,
        name: str,
        background_color: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Whiteboard:
        whiteboard = Whiteboard(
            name=normalize_name(name),
            owner_id=owner_id,
            background_color=normalize_color(background_color),
            width=validate_dimension(width, DEFAULT_WIDTH, "width"),
            height=validate_dimension(height, DEFAULT_HEIGHT, "height"),
            content=[],
        )
        return self._repo.create(whiteboard)


class UpdateWhiteboardUseCase:
    """Actualiza parcialmente una pizarra: solo se modifican los campos enviados."""

    def __init__(self, repo: WhiteboardRepository):
        self._repo = repo

    def execute(
        self,
        owner_id: UUID,
        whiteboard_id: UUID,
        *,
        name: Optional[str] = None,
        background_color: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        content: Optional[list[dict]] = None,
        thumbnail: Optional[str] = None,
        clear_thumbnail: bool = False,
    ) -> Whiteboard:
        whiteboard = _get_owned(self._repo, owner_id, whiteboard_id)
        if name is not None:
            whiteboard.name = normalize_name(name)
        if background_color is not None:
            whiteboard.background_color = normalize_color(background_color)
        if width is not None:
            whiteboard.width = validate_dimension(width, whiteboard.width, "width")
        if height is not None:
            whiteboard.height = validate_dimension(height, whiteboard.height, "height")
        if content is not None:
            whiteboard.content = validate_content(content)
        if clear_thumbnail:
            whiteboard.thumbnail = None
        elif thumbnail is not None:
            whiteboard.thumbnail = validate_thumbnail(thumbnail)
        return self._repo.update(whiteboard)


class DuplicateWhiteboardUseCase:
    def __init__(self, repo: WhiteboardRepository):
        self._repo = repo

    def execute(self, owner_id: UUID, whiteboard_id: UUID, name: Optional[str] = None) -> Whiteboard:
        source = _get_owned(self._repo, owner_id, whiteboard_id)
        copy_name = name if name and name.strip() else f"{source.name} (copia)"
        duplicate = Whiteboard(
            name=normalize_name(copy_name[:MAX_NAME_LENGTH]),
            owner_id=owner_id,
            background_color=source.background_color,
            width=source.width,
            height=source.height,
            content=deepcopy(source.content),
            thumbnail=source.thumbnail,
        )
        return self._repo.create(duplicate)


class DeleteWhiteboardUseCase:
    def __init__(self, repo: WhiteboardRepository):
        self._repo = repo

    def execute(self, owner_id: UUID, whiteboard_id: UUID) -> None:
        _get_owned(self._repo, owner_id, whiteboard_id)
        if not self._repo.delete(whiteboard_id):
            raise NotFoundError("Whiteboard not found")
