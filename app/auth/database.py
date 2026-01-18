"""SQLite database manager for user authentication."""

import os
import sqlite3
import threading
from typing import List, Tuple, Any, Optional


class DatabaseManager:
    """Thread-safe SQLite database manager."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default path: app/data/users.db
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(app_dir, 'data')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'users.db')

        self.db_path = db_path
        self._local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def init_database(self) -> None:
        """Initialize database with required tables."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(100) NOT NULL UNIQUE,
                password_hash VARCHAR(256) NOT NULL,
                salt VARCHAR(64) NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')

        # Verification codes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verification_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(100) NOT NULL,
                code VARCHAR(6) NOT NULL,
                code_type VARCHAR(20) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_used BOOLEAN DEFAULT FALSE
            )
        ''')

        # Sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token VARCHAR(256) NOT NULL UNIQUE,
                remember_me BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_verification_email ON verification_codes(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token)')

        # Add avatar_path column if not exists (migration)
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN avatar_path VARCHAR(256) DEFAULT NULL')
        except sqlite3.OperationalError:
            pass  # Column already exists

        conn.commit()

    def execute_query(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute a SELECT query and return results."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def execute_command(self, command: str, params: Tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE command and return lastrowid or rowcount."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(command, params)
        conn.commit()
        return cursor.lastrowid if cursor.lastrowid else cursor.rowcount

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
