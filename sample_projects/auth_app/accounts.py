"""
Account management module — handles balance, transactions, transfer logic.
Sample banking application — for testing the reverse engineering platform.
"""
from typing import Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from database import DatabaseConnection
from auth import AuthService


@dataclass
class Transaction:
    """Represents a single financial transaction."""
    id: int
    account_id: int
    amount: float
    tx_type: str  # DEPOSIT, WITHDRAWAL, TRANSFER
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: str = "COMPLETED"


@dataclass
class Account:
    """User account model."""
    id: int
    user_id: int
    balance: float
    account_type: str  # CHECKING, SAVINGS
    account_number: str
    is_active: bool = True


class AccountService:
    """Manages bank accounts and transactions."""

    DAILY_TRANSFER_LIMIT = 10_000.0
    MIN_BALANCE = 0.0

    def __init__(self):
        self.db = DatabaseConnection.get_instance()
        self.auth = AuthService()

    def get_balance(self, token: str, account_id: int) -> float:
        """Get current account balance for an authenticated user."""
        session = self.auth.validate_session(token)
        if not session:
            raise PermissionError("Unauthorized")

        account = self._get_account(account_id)
        self._verify_account_ownership(account, session["user_id"])
        return account.balance

    def deposit(self, token: str, account_id: int, amount: float) -> Transaction:
        """Deposit funds into an account."""
        session = self.auth.validate_session(token)
        if not session:
            raise PermissionError("Unauthorized")

        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        account = self._get_account(account_id)
        self._verify_account_ownership(account, session["user_id"])

        new_balance = account.balance + amount
        self._update_balance(account_id, new_balance)
        self.db.record_transaction(account_id, amount, "DEPOSIT")

        return Transaction(
            id=0,
            account_id=account_id,
            amount=amount,
            tx_type="DEPOSIT",
            description=f"Deposit of ${amount:.2f}",
        )

    def withdraw(self, token: str, account_id: int, amount: float) -> Transaction:
        """Withdraw funds from an account."""
        session = self.auth.validate_session(token)
        if not session:
            raise PermissionError("Unauthorized")

        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")

        account = self._get_account(account_id)
        self._verify_account_ownership(account, session["user_id"])

        if account.balance - amount < self.MIN_BALANCE:
            raise ValueError("Insufficient funds")

        new_balance = account.balance - amount
        self._update_balance(account_id, new_balance)
        self.db.record_transaction(account_id, -amount, "WITHDRAWAL")

        return Transaction(
            id=0,
            account_id=account_id,
            amount=amount,
            tx_type="WITHDRAWAL",
            description=f"Withdrawal of ${amount:.2f}",
        )

    def transfer(
        self,
        token: str,
        from_account_id: int,
        to_account_id: int,
        amount: float,
        description: str = ""
    ) -> Transaction:
        """Transfer funds between two accounts."""
        session = self.auth.validate_session(token)
        if not session:
            raise PermissionError("Unauthorized")

        if amount <= 0:
            raise ValueError("Transfer amount must be positive")

        if amount > self.DAILY_TRANSFER_LIMIT:
            raise ValueError(f"Amount exceeds daily transfer limit of ${self.DAILY_TRANSFER_LIMIT}")

        from_account = self._get_account(from_account_id)
        self._verify_account_ownership(from_account, session["user_id"])

        to_account = self._get_account(to_account_id)
        if not to_account.is_active:
            raise ValueError("Target account is inactive")

        if from_account.balance < amount:
            raise ValueError("Insufficient funds for transfer")

        # Atomic transfer (simplified)
        self._update_balance(from_account_id, from_account.balance - amount)
        self._update_balance(to_account_id, to_account.balance + amount)

        self.db.record_transaction(from_account_id, -amount, "TRANSFER")
        self.db.record_transaction(to_account_id, amount, "TRANSFER_IN")

        return Transaction(
            id=0,
            account_id=from_account_id,
            amount=amount,
            tx_type="TRANSFER",
            description=description or f"Transfer to account {to_account_id}",
        )

    def get_transaction_history(
        self, token: str, account_id: int, limit: int = 50
    ) -> List[Transaction]:
        """Retrieve transaction history for an account."""
        session = self.auth.validate_session(token)
        if not session:
            raise PermissionError("Unauthorized")

        account = self._get_account(account_id)
        self._verify_account_ownership(account, session["user_id"])

        rows = self.db.execute(
            "SELECT * FROM transactions WHERE account_id = :id ORDER BY timestamp DESC LIMIT :limit",
            {"id": account_id, "limit": limit}
        )
        return [
            Transaction(
                id=r["id"],
                account_id=r["account_id"],
                amount=r["amount"],
                tx_type=r["type"],
            )
            for r in rows
        ]

    def close_account(self, token: str, account_id: int) -> bool:
        """Close a bank account (must have zero balance)."""
        session = self.auth.validate_session(token)
        if not session:
            raise PermissionError("Unauthorized")

        account = self._get_account(account_id)
        self._verify_account_ownership(account, session["user_id"])

        if account.balance != 0:
            raise ValueError("Account must have zero balance before closing")

        self.db.execute(
            "UPDATE accounts SET is_active = false WHERE id = :id",
            {"id": account_id}
        )
        return True

    def _get_account(self, account_id: int) -> Account:
        """Internal method to fetch an account by ID."""
        row = self.db.get_account(account_id)
        if not row:
            raise ValueError(f"Account {account_id} not found")
        return Account(
            id=row["id"],
            user_id=row.get("user_id", 0),
            balance=row.get("balance", 0.0),
            account_type=row.get("account_type", "CHECKING"),
            account_number=str(row.get("id", account_id)).zfill(10),
        )

    def _verify_account_ownership(self, account: Account, user_id: int):
        """Verify that the account belongs to the given user."""
        if account.user_id != user_id:
            raise PermissionError("Account does not belong to this user")

    def _update_balance(self, account_id: int, new_balance: float):
        """Update account balance in database."""
        self.db.execute(
            "UPDATE accounts SET balance = :balance WHERE id = :id",
            {"balance": new_balance, "id": account_id}
        )
