"""
Database module — handles PostgreSQL connection and basic ORM operations.
This is a sample project for testing the reverse engineering platform.
"""
import os
from typing import Optional, List
import hashlib


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/bankapp")


class DatabaseConnection:
    """Manages database connection pooling."""

    _instance: Optional["DatabaseConnection"] = None

    def __init__(self, url: str = DATABASE_URL):
        self.url = url
        self.pool = None
        self._connected = False

    @classmethod
    def get_instance(cls) -> "DatabaseConnection":
        """Singleton pattern for database connection."""
        if cls._instance is None:
            cls._instance = DatabaseConnection()
        return cls._instance

    def connect(self) -> bool:
        """Establish database connection."""
        try:
            # In real app: self.pool = create_pool(self.url)
            self._connected = True
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Close all connections in pool."""
        if self.pool:
            self.pool = None
        self._connected = False

    def execute(self, query: str, params: dict = None) -> List[dict]:
        """Execute a parameterized query."""
        if not self._connected:
            raise RuntimeError("Database not connected")
        # Stub implementation
        return []

    def find_user(self, username: str) -> Optional[dict]:
        """Find a user by username."""
        result = self.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = :username",
            {"username": username}
        )
        return result[0] if result else None

    def get_account(self, user_id: int) -> Optional[dict]:
        """Retrieve account information for a user."""
        result = self.execute(
            "SELECT id, balance, account_type FROM accounts WHERE user_id = :user_id",
            {"user_id": user_id}
        )
        return result[0] if result else None

    def record_transaction(self, account_id: int, amount: float, tx_type: str) -> bool:
        """Record a financial transaction."""
        self.execute(
            "INSERT INTO transactions (account_id, amount, type) VALUES (:account_id, :amount, :type)",
            {"account_id": account_id, "amount": amount, "type": tx_type}
        )
        return True
