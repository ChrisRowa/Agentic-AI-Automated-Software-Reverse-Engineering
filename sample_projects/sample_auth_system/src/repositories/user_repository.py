"""User data access layer - database operations for User entities."""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.models.database_models import UserModel


class UserRepository:
    """Handles all database operations for User entities."""

    async def find_user(self, username: str, db: Session) -> Optional[UserModel]:
        """Find user by username."""
        result = db.execute(select(UserModel).where(UserModel.username == username))
        return result.scalar_one_or_none()

    async def find_user_by_id(self, user_id: int, db: Session) -> Optional[UserModel]:
        """Find user by primary key ID."""
        return db.get(UserModel, user_id)

    async def create_user(
        self, username: str, email: str, password_hash: str, db: Session
    ) -> UserModel:
        """Create and persist a new user record."""
        user = UserModel(username=username, email=email, password_hash=password_hash)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    async def update_user(
        self, user_id: int, updates: dict, db: Session
    ) -> Optional[UserModel]:
        """Update user record fields."""
        user = await self.find_user_by_id(user_id=user_id, db=db)
        if not user:
            return None
        for key, value in updates.items():
            setattr(user, key, value)
        db.commit()
        db.refresh(user)
        return user

    async def delete_user(self, user_id: int, db: Session) -> bool:
        """Delete a user record."""
        user = await self.find_user_by_id(user_id=user_id, db=db)
        if not user:
            return False
        db.delete(user)
        db.commit()
        return True
