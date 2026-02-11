"""User model and repository."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

from .database import DatabaseManager
from .security import PasswordSecurity


@dataclass
class User:
    """User data model."""
    id: int
    username: str
    email: str
    password_hash: str
    salt: str
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    avatar_path: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> 'User':
        """Create User from database row."""
        return cls(
            id=row['id'],
            username=row['username'],
            email=row['email'],
            password_hash=row['password_hash'],
            salt=row['salt'],
            is_verified=bool(row['is_verified']),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
            last_login=datetime.fromisoformat(row['last_login']) if row['last_login'] else None,
            avatar_path=row['avatar_path'] if 'avatar_path' in row.keys() else None,
        )


class UserRepository:
    """User data access layer."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def create_user(self, username: str, email: str, password: str) -> Optional[int]:
        """
        Create a new user.

        Args:
            username: User's username
            email: User's email
            password: Plain text password (will be hashed)

        Returns:
            User ID if successful, None otherwise
        """
        password_hash, salt = PasswordSecurity.create_password_hash(password)

        try:
            user_id = self.db.execute_command(
                '''INSERT INTO users (username, email, password_hash, salt, is_verified)
                   VALUES (?, ?, ?, ?, ?)''',
                (username, email, password_hash, salt, True)
            )
            return user_id
        except Exception as e:
            print(f"Error creating user: {e}")
            return None

    def find_by_username(self, username: str) -> Optional[User]:
        """Find user by username."""
        rows = self.db.execute_query(
            'SELECT * FROM users WHERE username = ?',
            (username,)
        )
        if rows:
            return User.from_row(rows[0])
        return None

    def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email."""
        rows = self.db.execute_query(
            'SELECT * FROM users WHERE email = ?',
            (email,)
        )
        if rows:
            return User.from_row(rows[0])
        return None

    def find_by_id(self, user_id: int) -> Optional[User]:
        """Find user by ID."""
        rows = self.db.execute_query(
            'SELECT * FROM users WHERE id = ?',
            (user_id,)
        )
        if rows:
            return User.from_row(rows[0])
        return None

    def verify_login(self, username: str, password: str) -> Optional[User]:
        """
        Verify user login credentials.

        Args:
            username: Username or email
            password: Plain text password

        Returns:
            User object if credentials are valid, None otherwise
        """
        # Try to find by username first, then by email
        user = self.find_by_username(username)
        if not user:
            user = self.find_by_email(username)

        if not user:
            return None

        if PasswordSecurity.verify_password(password, user.salt, user.password_hash):
            self.update_last_login(user.id)
            return user

        return None

    def update_last_login(self, user_id: int) -> bool:
        """Update user's last login time."""
        try:
            self.db.execute_command(
                'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?',
                (user_id,)
            )
            return True
        except Exception:
            return False

    def update_verification_status(self, user_id: int, status: bool) -> bool:
        """Update user's verification status."""
        try:
            self.db.execute_command(
                'UPDATE users SET is_verified = ? WHERE id = ?',
                (status, user_id)
            )
            return True
        except Exception:
            return False

    def username_exists(self, username: str) -> bool:
        """Check if username already exists."""
        return self.find_by_username(username) is not None

    def email_exists(self, email: str) -> bool:
        """Check if email already exists."""
        return self.find_by_email(email) is not None

    def verify_password(self, user_id: int, password: str) -> bool:
        """Verify user's password."""
        user = self.find_by_id(user_id)
        if not user:
            return False
        return PasswordSecurity.verify_password(password, user.salt, user.password_hash)

    def update_username(self, user_id: int, new_username: str) -> bool:
        """Update user's username."""
        try:
            self.db.execute_command(
                'UPDATE users SET username = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (new_username, user_id)
            )
            return True
        except Exception as e:
            print(f"Error updating username: {e}")
            return False

    def update_password(self, user_id: int, new_password: str) -> bool:
        """Update user's password."""
        try:
            password_hash, salt = PasswordSecurity.create_password_hash(new_password)
            self.db.execute_command(
                'UPDATE users SET password_hash = ?, salt = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (password_hash, salt, user_id)
            )
            return True
        except Exception as e:
            print(f"Error updating password: {e}")
            return False

    def update_email(self, user_id: int, new_email: str) -> bool:
        """Update user's email."""
        try:
            self.db.execute_command(
                'UPDATE users SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (new_email, user_id)
            )
            return True
        except Exception as e:
            print(f"Error updating email: {e}")
            return False

    def update_avatar(self, user_id: int, avatar_path: str) -> bool:
        """Update user's avatar path."""
        try:
            self.db.execute_command(
                'UPDATE users SET avatar_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (avatar_path, user_id)
            )
            return True
        except Exception as e:
            print(f"Error updating avatar: {e}")
            return False

    def get_all_users(self) -> List[User]:
        """Get all users."""
        rows = self.db.execute_query('SELECT * FROM users ORDER BY id')
        return [User.from_row(row) for row in rows]

    def delete_user(self, user_id: int) -> bool:
        """Delete a user and their sessions."""
        try:
            self.db.execute_command('DELETE FROM sessions WHERE user_id = ?', (user_id,))
            self.db.execute_command('DELETE FROM users WHERE id = ?', (user_id,))
            return True
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False

    def reset_user_ids(self) -> bool:
        """Reset user IDs to be sequential (1, 2, 3...)."""
        try:
            users = self.get_all_users()
            for new_id, user in enumerate(users, start=1):
                if user.id != new_id:
                    self.db.execute_command(
                        'UPDATE sessions SET user_id = ? WHERE user_id = ?',
                        (new_id, user.id)
                    )
                    self.db.execute_command(
                        'UPDATE users SET id = ? WHERE id = ?',
                        (new_id, user.id)
                    )
            self.db.execute_command(
                "UPDATE sqlite_sequence SET seq = ? WHERE name = 'users'",
                (len(users),)
            )
            return True
        except Exception as e:
            print(f"Error resetting user IDs: {e}")
            return False
