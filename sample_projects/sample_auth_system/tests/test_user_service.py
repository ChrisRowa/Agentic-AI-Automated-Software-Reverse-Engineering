"""Tests for UserService."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.user_service import UserService


@pytest.fixture
def user_service():
    return UserService()


class TestCreateUser:
    """Tests for user creation flow."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, user_service):
        """New user with unique username should be created."""
        mock_db = MagicMock()
        mock_created = MagicMock(id=1, username="alice", email="alice@example.com")

        with patch.object(user_service.user_repo, "find_user", return_value=None),              patch.object(user_service.user_repo, "create_user", return_value=mock_created):
            from src.models.user import UserCreate
            result = await user_service.create_user(
                user_data=UserCreate(username="alice", email="alice@example.com", password="pass"),
                db=mock_db
            )

        assert result is not None
        assert result.username == "alice"

    @pytest.mark.asyncio
    async def test_create_user_duplicate(self, user_service):
        """Duplicate username should return None."""
        mock_db = MagicMock()
        existing = MagicMock()

        with patch.object(user_service.user_repo, "find_user", return_value=existing):
            from src.models.user import UserCreate
            result = await user_service.create_user(
                user_data=UserCreate(username="alice", email="alice@example.com", password="pass"),
                db=mock_db
            )

        assert result is None
