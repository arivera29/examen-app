from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.application.use_cases import NotFoundError, ValidationError
from app.application.whiteboards import (
    MAX_ELEMENTS,
    CreateWhiteboardUseCase,
    DeleteWhiteboardUseCase,
    DuplicateWhiteboardUseCase,
    GetWhiteboardUseCase,
    ListWhiteboardsUseCase,
    UpdateWhiteboardUseCase,
)
from app.domain.entities import Whiteboard


@pytest.fixture
def repo():
    mock = MagicMock()
    mock.create.side_effect = lambda w: w
    mock.update.side_effect = lambda w: w
    mock.delete.return_value = True
    return mock


@pytest.fixture
def owner_id():
    return uuid4()


@pytest.fixture
def whiteboard(owner_id):
    return Whiteboard(
        name="Clase 1",
        owner_id=owner_id,
        background_color="#ffffff",
        content=[{"id": "a", "type": "pen", "points": [[0, 0], [10, 10]]}],
    )


class TestCreateWhiteboard:
    def test_creates_with_defaults(self, repo, owner_id):
        result = CreateWhiteboardUseCase(repo).execute(owner_id, "  Mi pizarra  ")

        assert result.name == "Mi pizarra"
        assert result.owner_id == owner_id
        assert result.background_color == "#ffffff"
        assert (result.width, result.height) == (1920, 1080)
        assert result.content == []
        repo.create.assert_called_once()

    def test_normalizes_background_color(self, repo, owner_id):
        result = CreateWhiteboardUseCase(repo).execute(owner_id, "Pizarra", background_color="#1E1E1E")
        assert result.background_color == "#1e1e1e"

    @pytest.mark.parametrize("color", ["red", "#fff", "#gggggg", "1e1e1e"])
    def test_rejects_invalid_color(self, repo, owner_id, color):
        with pytest.raises(ValidationError):
            CreateWhiteboardUseCase(repo).execute(owner_id, "Pizarra", background_color=color)

    def test_rejects_blank_name(self, repo, owner_id):
        with pytest.raises(ValidationError):
            CreateWhiteboardUseCase(repo).execute(owner_id, "   ")

    @pytest.mark.parametrize("width", [100, 10000])
    def test_rejects_out_of_range_dimensions(self, repo, owner_id, width):
        with pytest.raises(ValidationError):
            CreateWhiteboardUseCase(repo).execute(owner_id, "Pizarra", width=width)


class TestGetAndListWhiteboards:
    def test_get_returns_owned_whiteboard(self, repo, owner_id, whiteboard):
        repo.get_by_id.return_value = whiteboard
        assert GetWhiteboardUseCase(repo).execute(owner_id, whiteboard.id) is whiteboard

    def test_get_hides_whiteboard_of_other_user(self, repo, whiteboard):
        repo.get_by_id.return_value = whiteboard
        with pytest.raises(NotFoundError):
            GetWhiteboardUseCase(repo).execute(uuid4(), whiteboard.id)

    def test_get_missing_whiteboard(self, repo, owner_id):
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            GetWhiteboardUseCase(repo).execute(owner_id, uuid4())

    def test_list_delegates_to_repository(self, repo, owner_id, whiteboard):
        repo.list_by_owner.return_value = [whiteboard]
        assert ListWhiteboardsUseCase(repo).execute(owner_id) == [whiteboard]
        repo.list_by_owner.assert_called_once_with(owner_id)


class TestUpdateWhiteboard:
    def test_updates_only_provided_fields(self, repo, owner_id, whiteboard):
        repo.get_by_id.return_value = whiteboard
        original_content = whiteboard.content

        result = UpdateWhiteboardUseCase(repo).execute(owner_id, whiteboard.id, name="Nuevo nombre")

        assert result.name == "Nuevo nombre"
        assert result.background_color == "#ffffff"
        assert result.content == original_content

    def test_updates_content_background_and_thumbnail(self, repo, owner_id, whiteboard):
        repo.get_by_id.return_value = whiteboard
        content = [
            {"id": "r", "type": "rect", "x": 1, "y": 2, "w": 3, "h": 4},
            {"id": "t", "type": "text", "x": 5, "y": 6, "text": "Hola"},
        ]

        result = UpdateWhiteboardUseCase(repo).execute(
            owner_id,
            whiteboard.id,
            background_color="#000000",
            content=content,
            thumbnail="data:image/png;base64,AAAA",
        )

        assert result.background_color == "#000000"
        assert result.content == content
        assert result.thumbnail == "data:image/png;base64,AAAA"

    def test_clears_thumbnail(self, repo, owner_id, whiteboard):
        whiteboard.thumbnail = "data:image/png;base64,AAAA"
        repo.get_by_id.return_value = whiteboard
        result = UpdateWhiteboardUseCase(repo).execute(owner_id, whiteboard.id, clear_thumbnail=True)
        assert result.thumbnail is None

    def test_rejects_unknown_element_type(self, repo, owner_id, whiteboard):
        repo.get_by_id.return_value = whiteboard
        with pytest.raises(ValidationError):
            UpdateWhiteboardUseCase(repo).execute(owner_id, whiteboard.id, content=[{"type": "script"}])

    def test_rejects_too_many_elements(self, repo, owner_id, whiteboard):
        repo.get_by_id.return_value = whiteboard
        content = [{"type": "pen", "points": []}] * (MAX_ELEMENTS + 1)
        with pytest.raises(ValidationError):
            UpdateWhiteboardUseCase(repo).execute(owner_id, whiteboard.id, content=content)

    def test_rejects_non_image_thumbnail(self, repo, owner_id, whiteboard):
        repo.get_by_id.return_value = whiteboard
        with pytest.raises(ValidationError):
            UpdateWhiteboardUseCase(repo).execute(
                owner_id, whiteboard.id, thumbnail="data:text/html;base64,PHNjcmlwdD4="
            )

    def test_cannot_update_whiteboard_of_other_user(self, repo, whiteboard):
        repo.get_by_id.return_value = whiteboard
        with pytest.raises(NotFoundError):
            UpdateWhiteboardUseCase(repo).execute(uuid4(), whiteboard.id, name="Hack")
        repo.update.assert_not_called()


class TestDuplicateWhiteboard:
    def test_duplicates_with_default_name_and_independent_content(self, repo, owner_id, whiteboard):
        repo.get_by_id.return_value = whiteboard

        copy = DuplicateWhiteboardUseCase(repo).execute(owner_id, whiteboard.id)

        assert copy.id != whiteboard.id
        assert copy.name == "Clase 1 (copia)"
        assert copy.content == whiteboard.content
        copy.content[0]["points"].append([20, 20])
        assert len(whiteboard.content[0]["points"]) == 2

    def test_duplicates_with_custom_name(self, repo, owner_id, whiteboard):
        repo.get_by_id.return_value = whiteboard
        copy = DuplicateWhiteboardUseCase(repo).execute(owner_id, whiteboard.id, "Otra")
        assert copy.name == "Otra"


class TestDeleteWhiteboard:
    def test_deletes_owned_whiteboard(self, repo, owner_id, whiteboard):
        repo.get_by_id.return_value = whiteboard
        DeleteWhiteboardUseCase(repo).execute(owner_id, whiteboard.id)
        repo.delete.assert_called_once_with(whiteboard.id)

    def test_cannot_delete_whiteboard_of_other_user(self, repo, whiteboard):
        repo.get_by_id.return_value = whiteboard
        with pytest.raises(NotFoundError):
            DeleteWhiteboardUseCase(repo).execute(uuid4(), whiteboard.id)
        repo.delete.assert_not_called()
