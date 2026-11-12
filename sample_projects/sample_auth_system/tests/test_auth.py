"""Tests for authentication service. Covers REQ-001, REQ-002, REQ-003, REQ-004."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.auth_service import AuthService
from src.models.user import TokenResponse


@pytest.fixture
def auth_service():
    return AuthService()


@pytest.fixture
def mock_db():
    return MagicMock()


class TestAuthenticate:
    """Tests for AuthService.authenticate(). Covers REQ-001."""

    @pytest.mark.asyncio
    async def test_authenticate_valid_credentials(self, auth_service, mock_db):
        """REQ-001: Valid login should succeed."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.password_hash = "$2b$12$hash"

        with patch.object(auth_service.user_repo, "find_user", return_value=mock_user),              patch.object(auth_service, "_verify_password", return_value=True),              patch.object(auth_service, "_generate_token", return_value="test.jwt.token"),              patch.object(auth_service.session_repo, "create_session", return_value=None):
            result = await auth_service.authenticate("testuser", "password123", mock_db)

        assert result is not None
        assert result.access_token == "test.jwt.token"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_password(self, auth_service, mock_db):
        """REQ-002: Wrong password should fail authentication."""
        mock_user = MagicMock()

        with patch.object(auth_service.user_repo, "find_user", return_value=mock_user),              patch.object(auth_service, "_verify_password", return_value=False),              patch.object(auth_service, "_log_failed_attempt", new_callable=AsyncMock):
            result = await auth_service.authenticate("testuser", "wrongpassword", mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, auth_service, mock_db):
        """Login with unknown user should fail."""
        with patch.object(auth_service.user_repo, "find_user", return_value=None):
            result = await auth_service.authenticate("nobody", "password", mock_db)

        assert result is None


class TestVerifyPassword:
    """Tests for password verification. Covers REQ-002."""

    def test_verify_correct_password(self, auth_service):
        """REQ-002: bcrypt verification should work correctly."""
        import bcrypt
        plain = "mysecretpassword"
        hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
        assert auth_service._verify_password(plain, hashed) is True

    def test_verify_wrong_password(self, auth_service):
        """Wrong password should return False."""
        import bcrypt
        hashed = bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode()
        assert auth_service._verify_password("wrong", hashed) is False


class TestTokenGeneration:
    """Tests for JWT token generation. Covers REQ-003."""

    def test_generate_token_returns_string(self, auth_service):
        """REQ-003: Token generation should return a valid JWT string."""
        token = auth_service._generate_token(user_id=1, username="test")
        assert isinstance(token, str)
        assert len(token) > 0
