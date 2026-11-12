"""Session data access layer."""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from src.models.database_models import SessionModel, FailedLoginModel
from datetime import datetime


class SessionRepository:
    """Handles database operations for session and authentication tracking."""

    async def create_session(self, user_id: int, token: str, db: Session) -> SessionModel:
        """Create a new user session record."""
        session = SessionModel(user_id=user_id, token=token, created_at=datetime.utcnow())
        db.add(session)
        db.commit()
        return session

    async def find_session(self, token: str, db: Session) -> Optional[SessionModel]:
        """Find an active session by token."""
        result = db.execute(select(SessionModel).where(SessionModel.token == token))
        return result.scalar_one_or_none()

    async def delete_session(self, token: str, db: Session) -> bool:
        """Delete a session (logout)."""
        db.execute(delete(SessionModel).where(SessionModel.token == token))
        db.commit()
        return True

    async def update_session(self, old_token: str, new_token: str, db: Session):
        """Update session token (refresh)."""
        session = await self.find_session(token=old_token, db=db)
        if session:
            session.token = new_token
            db.commit()

    async def log_failed_attempt(self, username: str, db: Session):
        """Log a failed login attempt. REQ-004."""
        entry = FailedLoginModel(username=username, attempted_at=datetime.utcnow())
        db.add(entry)
        db.commit()
