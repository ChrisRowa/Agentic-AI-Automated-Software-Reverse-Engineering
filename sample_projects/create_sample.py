"""
Creates a realistic sample auth system repository and packages it as a ZIP
for end-to-end testing of the reverse engineering platform.
"""
import os
import zipfile
from pathlib import Path

BASE = Path(__file__).parent / "sample_auth_system"

FILES = {}

FILES["README.md"] = """# Sample Auth System

A sample authentication system for testing the reverse engineering platform.

## Requirements
- REQ-001: Users must be able to login with username and password
- REQ-002: Passwords must be hashed using bcrypt
- REQ-003: Sessions must expire after 30 minutes
- REQ-004: Failed login attempts must be logged

## Architecture
The system follows a layered architecture:
- Controllers: Handle HTTP requests
- Services: Business logic
- Repositories: Data access layer
- Models: Data structures
"""

FILES["requirements.txt"] = """fastapi==0.100.0
bcrypt==4.0.1
sqlalchemy==2.0.0
pydantic==2.0.0
PyJWT==2.8.0
"""

FILES["src/__init__.py"] = ""

FILES["src/main.py"] = '''"""Main application entry point."""
from fastapi import FastAPI
from src.controllers.login_controller import router as login_router
from src.controllers.user_controller import router as user_router
from src.core.database import init_database

app = FastAPI(title="Auth System")

app.include_router(login_router, prefix="/auth")
app.include_router(user_router, prefix="/users")


@app.on_event("startup")
async def startup():
    await init_database()


@app.get("/health")
def health_check():
    return {"status": "healthy"}
'''

FILES["src/controllers/__init__.py"] = ""

FILES["src/controllers/login_controller.py"] = '''"""Login HTTP controller - handles authentication requests."""
from fastapi import APIRouter, HTTPException, Depends
from src.services.auth_service import AuthService
from src.models.user import LoginRequest, TokenResponse
from src.core.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()
auth_service = AuthService()


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    result = await auth_service.authenticate(
        username=request.username,
        password=request.password,
        db=db
    )
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return result


@router.post("/logout")
async def logout(token: str, db: Session = Depends(get_db)):
    """Invalidate session token."""
    await auth_service.invalidate_session(token=token, db=db)
    return {"message": "Logged out successfully"}


@router.post("/refresh")
async def refresh_token(token: str, db: Session = Depends(get_db)):
    """Refresh an expiring JWT token."""
    new_token = await auth_service.refresh_token(token=token, db=db)
    if not new_token:
        raise HTTPException(status_code=401, detail="Token expired or invalid")
    return new_token
'''

FILES["src/controllers/user_controller.py"] = '''"""User management controller."""
from fastapi import APIRouter, HTTPException, Depends
from src.services.user_service import UserService
from src.models.user import UserCreate, UserResponse
from src.core.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()
user_service = UserService()


@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account."""
    user = await user_service.create_user(user_data=user_data, db=db)
    if not user:
        raise HTTPException(status_code=400, detail="User already exists")
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user profile by ID."""
    user = await user_service.get_user_by_id(user_id=user_id, db=db)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
'''

FILES["src/services/__init__.py"] = ""

FILES["src/services/auth_service.py"] = '''"""Authentication business logic service."""
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
'''

FILES["src/services/user_service.py"] = '''"""User management service."""
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
'''

FILES["src/repositories/__init__.py"] = ""

FILES["src/repositories/user_repository.py"] = '''"""User data access layer - database operations for User entities."""
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
'''

FILES["src/repositories/session_repository.py"] = '''"""Session data access layer."""
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
'''

FILES["src/models/__init__.py"] = ""

FILES["src/models/user.py"] = '''"""User domain models and API schemas."""
from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
'''

FILES["src/models/database_models.py"] = '''"""SQLAlchemy ORM models for database tables."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)


class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(512), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


class FailedLoginModel(Base):
    __tablename__ = "failed_logins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False)
    attempted_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(50), nullable=True)
'''

FILES["src/core/__init__.py"] = ""

FILES["src/core/database.py"] = '''"""Database configuration and connection management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.models.database_models import Base

DATABASE_URL = "sqlite:///./auth_system.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


async def init_database():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
'''

FILES["tests/__init__.py"] = ""

FILES["tests/test_auth.py"] = '''"""Tests for authentication service. Covers REQ-001, REQ-002, REQ-003, REQ-004."""
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

        with patch.object(auth_service.user_repo, "find_user", return_value=mock_user), \
             patch.object(auth_service, "_verify_password", return_value=True), \
             patch.object(auth_service, "_generate_token", return_value="test.jwt.token"), \
             patch.object(auth_service.session_repo, "create_session", return_value=None):
            result = await auth_service.authenticate("testuser", "password123", mock_db)

        assert result is not None
        assert result.access_token == "test.jwt.token"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_password(self, auth_service, mock_db):
        """REQ-002: Wrong password should fail authentication."""
        mock_user = MagicMock()

        with patch.object(auth_service.user_repo, "find_user", return_value=mock_user), \
             patch.object(auth_service, "_verify_password", return_value=False), \
             patch.object(auth_service, "_log_failed_attempt", new_callable=AsyncMock):
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
'''

FILES["tests/test_user_service.py"] = '''"""Tests for UserService."""
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

        with patch.object(user_service.user_repo, "find_user", return_value=None), \
             patch.object(user_service.user_repo, "create_user", return_value=mock_created):
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
'''


def main():
    print(f"Creating sample auth system at: {BASE}")

    # Write all files
    for filepath, content in FILES.items():
        full_path = BASE / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        print(f"  Created: {filepath}")

    # Create ZIP archive
    zip_path = BASE.parent / "realistic_auth_system.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filepath in FILES:
            full_path = BASE / filepath
            zf.write(full_path, filepath)

    print(f"\nZIP created: {zip_path}")
    print(f"  Size: {zip_path.stat().st_size:,} bytes")
    print(f"  Files: {len(FILES)}")
    print("\nDone!")


if __name__ == "__main__":
    main()
