"""
Authentication module — handles user login, registration, session management.
Sample banking application — for testing the reverse engineering platform.
"""
import hashlib
import secrets
import time
from typing import Optional, Tuple
from database import DatabaseConnection


# Session store (in-memory for simplicity)
_sessions: dict = {}

# Maximum failed login attempts
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # seconds
_failed_attempts: dict = {}
_lockout_time: dict = {}


class AuthService:
    """Core authentication service."""

    def __init__(self):
        self.db = DatabaseConnection.get_instance()

    def hash_password(self, password: str, salt: str = None) -> Tuple[str, str]:
        """Hash a password with PBKDF2."""
        if salt is None:
            salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return key.hex(), salt

    def verify_password(self, password: str, stored_hash: str, salt: str) -> bool:
        """Verify a password against stored hash."""
        computed, _ = self.hash_password(password, salt)
        return computed == stored_hash

    def login(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate a user and return a session token.
        Returns None if authentication fails.
        """
        if self._is_locked_out(username):
            raise PermissionError(f"Account '{username}' is temporarily locked.")

        user = self.db.find_user(username)
        if not user:
            self._record_failed_attempt(username)
            return None

        if not self.verify_password(password, user["password_hash"], user.get("salt", "")):
            self._record_failed_attempt(username)
            return None

        # Successful login — reset failed attempts
        _failed_attempts[username] = 0

        # Create session
        token = self._create_session(user["id"], user["username"], user["role"])
        return token

    def logout(self, token: str) -> bool:
        """Invalidate a session token."""
        if token in _sessions:
            del _sessions[token]
            return True
        return False

    def validate_session(self, token: str) -> Optional[dict]:
        """Validate a session token and return user data."""
        session = _sessions.get(token)
        if not session:
            return None
        if time.time() > session["expires_at"]:
            del _sessions[token]
            return None
        return session

    def register(self, username: str, password: str, role: str = "user") -> bool:
        """Register a new user account."""
        if self.db.find_user(username):
            raise ValueError(f"Username '{username}' already exists")

        password_hash, salt = self.hash_password(password)
        self.db.execute(
            "INSERT INTO users (username, password_hash, salt, role) VALUES (:u, :h, :s, :r)",
            {"u": username, "h": password_hash, "s": salt, "r": role}
        )
        return True

    def change_password(self, token: str, old_password: str, new_password: str) -> bool:
        """Change a user's password after verifying the old one."""
        session = self.validate_session(token)
        if not session:
            raise PermissionError("Invalid session")

        user = self.db.find_user(session["username"])
        if not self.verify_password(old_password, user["password_hash"], user.get("salt", "")):
            raise ValueError("Current password is incorrect")

        new_hash, new_salt = self.hash_password(new_password)
        self.db.execute(
            "UPDATE users SET password_hash = :h, salt = :s WHERE id = :id",
            {"h": new_hash, "s": new_salt, "id": user["id"]}
        )
        return True

    def _create_session(self, user_id: int, username: str, role: str) -> str:
        """Create a new session token."""
        token = secrets.token_urlsafe(32)
        _sessions[token] = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "created_at": time.time(),
            "expires_at": time.time() + 3600,  # 1 hour
        }
        return token

    def _is_locked_out(self, username: str) -> bool:
        """Check if a user is currently locked out."""
        if username not in _lockout_time:
            return False
        if time.time() > _lockout_time[username] + LOCKOUT_DURATION:
            del _lockout_time[username]
            _failed_attempts[username] = 0
            return False
        return True

    def _record_failed_attempt(self, username: str):
        """Record a failed login attempt."""
        count = _failed_attempts.get(username, 0) + 1
        _failed_attempts[username] = count
        if count >= MAX_FAILED_ATTEMPTS:
            _lockout_time[username] = time.time()
