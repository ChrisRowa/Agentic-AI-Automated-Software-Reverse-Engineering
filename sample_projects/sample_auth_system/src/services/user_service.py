"""User management service."""
import bcrypt
from typing import Optional
from src.repositories.user_repository import UserRepository
from src.models.user import UserCreate, UserResponse


class UserService:
    """Handles user creation and retrieval operations."""

    def __init__(self):
        self.user_repo = UserRepository()

    async def create_user(self, user_data: UserCreate, db) -> Optional[UserResponse]:
        """Create a new user with hashed password."""
        existing = await self.user_repo.find_user(username=user_data.username, db=db)
        if existing:
            return None
        hashed = self._hash_password(user_data.password)
        user = await self.user_repo.create_user(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed,
            db=db,
        )
        return UserResponse(id=user.id, username=user.username, email=user.email)

    async def get_user_by_id(self, user_id: int, db) -> Optional[UserResponse]:
        """Retrieve user by ID."""
        user = await self.user_repo.find_user_by_id(user_id=user_id, db=db)
        if not user:
            return None
        return UserResponse(id=user.id, username=user.username, email=user.email)

    def _hash_password(self, plain_password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(plain_password.encode(), salt).decode()
