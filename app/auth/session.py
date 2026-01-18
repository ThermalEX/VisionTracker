"""Session management for user authentication."""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from .database import DatabaseManager
from .security import TokenGenerator
from .models import User, UserRepository


class SessionManager:
    """Manages user sessions and auto-login functionality."""

    DEFAULT_EXPIRY_DAYS = 7
    REMEMBER_ME_EXPIRY_DAYS = 30

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.user_repo = UserRepository(db_manager)

        # Session file path - use pathlib for cross-platform compatibility
        app_dir = Path(__file__).resolve().parent.parent
        data_dir = app_dir / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = data_dir / 'session.json'

    def create_session(self, user_id: int, remember_me: bool = False) -> str:
        """
        Create a new session for the user.

        Args:
            user_id: User's ID
            remember_me: Whether to extend session expiry

        Returns:
            Session token
        """
        token = TokenGenerator.generate_session_token()
        expiry_days = self.REMEMBER_ME_EXPIRY_DAYS if remember_me else self.DEFAULT_EXPIRY_DAYS
        expires_at = datetime.now() + timedelta(days=expiry_days)

        self.db.execute_command(
            '''INSERT INTO sessions (user_id, session_token, remember_me, expires_at)
               VALUES (?, ?, ?, ?)''',
            (user_id, token, remember_me, expires_at.isoformat())
        )

        # If remember_me, save to local file
        if remember_me:
            self.save_local_session(token)

        return token

    def validate_session(self, token: str) -> Optional[int]:
        """
        Validate session token.

        Args:
            token: Session token

        Returns:
            User ID if valid, None otherwise
        """
        rows = self.db.execute_query(
            '''SELECT user_id FROM sessions
               WHERE session_token = ? AND expires_at > ?''',
            (token, datetime.now().isoformat())
        )

        if rows:
            return rows[0]['user_id']
        return None

    def save_local_session(self, token: str) -> None:
        """Save session token to local file for auto-login."""
        try:
            data = {'session_token': token, 'saved_at': datetime.now().isoformat()}
            with open(self.session_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Failed to save local session: {e}")

    def load_local_session(self) -> Optional[str]:
        """Load session token from local file."""
        try:
            if self.session_file.exists():
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                    return data.get('session_token')
        except Exception as e:
            print(f"Failed to load local session: {e}")
        return None

    def clear_session(self) -> None:
        """Clear current session (logout)."""
        # Clear local session file
        try:
            if self.session_file.exists():
                self.session_file.unlink()
        except Exception as e:
            print(f"Failed to clear session file: {e}")

    def check_auto_login(self) -> Optional[User]:
        """
        Check if auto-login is possible.

        Returns:
            User object if auto-login successful, None otherwise
        """
        token = self.load_local_session()
        if not token:
            return None

        user_id = self.validate_session(token)
        if not user_id:
            # Invalid session, clear local file
            self.clear_session()
            return None

        user = self.user_repo.find_by_id(user_id)
        if user:
            self.user_repo.update_last_login(user_id)
        return user

    def invalidate_session(self, token: str) -> None:
        """Invalidate a specific session."""
        self.db.execute_command(
            'DELETE FROM sessions WHERE session_token = ?',
            (token,)
        )

    def invalidate_user_sessions(self, user_id: int) -> None:
        """Invalidate all sessions for a user."""
        self.db.execute_command(
            'DELETE FROM sessions WHERE user_id = ?',
            (user_id,)
        )
