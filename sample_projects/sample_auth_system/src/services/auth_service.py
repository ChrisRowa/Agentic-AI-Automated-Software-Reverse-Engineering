"""Authentication business logic service."""
import bcrypt
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional
from src.repositories.user_repository import UserRepository
from src.repositories.session_repository import SessionRepository
from src.models.user import TokenResponse

logger = logging.getLogger(__name__)

SECRET_KEY = "super-secret-key"
TOKEN_EXPIRY_MINUTES = 30


class AuthService:
    """Handles authentication, session management, and token operations."""

    def __init__(self):
        self.user_repo = UserRepository()
        self.session_repo = SessionRepository()

    async def authenticate(self, username: str, password: str, db) -> Optional[TokenResponse]:
        """Authenticate user credentials and create a session.

        REQ-001: Users must be able to login with username and password
        REQ-002: Passwords must be verified using bcrypt
        """
        logger.info("Authentication attempt for user: %s", username)

        user = await self.user_repo.find_user(username=username, db=db)
        if not user:
            logger.warning("User not found: %s", username)
            return None

        is_valid = self._verify_password(password, user.password_hash)
        if not is_valid:
            logger.warning("Invalid password for user: %s", username)
            await self._log_failed_attempt(username=username, db=db)
            return None

        token = self._generate_token(user_id=user.id, username=username)
        await self.session_repo.create_session(user_id=user.id, token=token, db=db)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=TOKEN_EXPIRY_MINUTES * 60
        )

    async def invalidate_session(self, token: str, db) -> bool:
        """Invalidate a user session token."""
        return await self.session_repo.delete_session(token=token, db=db)

    async def refresh_token(self, token: str, db) -> Optional[TokenResponse]:
        """Refresh an active token before expiry."""
        session = await self.session_repo.find_session(token=token, db=db)
        if not session:
            return None
        user = await self.user_repo.find_user_by_id(user_id=session.user_id, db=db)
        new_token = self._generate_token(user_id=user.id, username=user.username)
        await self.session_repo.update_session(old_token=token, new_token=new_token, db=db)
        return TokenResponse(
            access_token=new_token,
            token_type="bearer",
            expires_in=TOKEN_EXPIRY_MINUTES * 60
        )

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against bcrypt hash. REQ-002."""
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

    def _generate_token(self, user_id: int, username: str) -> str:
        """Generate JWT token with expiry. REQ-003."""
        payload = {
            "user_id": user_id,
            "username": username,
            "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRY_MINUTES),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    async def _log_failed_attempt(self, username: str, db) -> None:
        """Log failed login attempt. REQ-004."""
        logger.warning("Failed login attempt logged for: %s", username)
        await self.session_repo.log_failed_attempt(username=username, db=db)
