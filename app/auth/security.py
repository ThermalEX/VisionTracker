"""Password security and token generation utilities."""

import hashlib
import secrets
from typing import Tuple


class PasswordSecurity:
    """Password hashing and verification using PBKDF2-SHA256."""

    ITERATIONS = 100000
    HASH_ALGORITHM = 'sha256'
    SALT_LENGTH = 32

    @staticmethod
    def generate_salt(length: int = 32) -> str:
        """Generate a random salt value."""
        return secrets.token_hex(length)

    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        """
        Hash password using PBKDF2-SHA256.

        Args:
            password: Plain text password
            salt: Salt value

        Returns:
            Hexadecimal hash string
        """
        password_bytes = password.encode('utf-8')
        salt_bytes = salt.encode('utf-8')

        dk = hashlib.pbkdf2_hmac(
            PasswordSecurity.HASH_ALGORITHM,
            password_bytes,
            salt_bytes,
            PasswordSecurity.ITERATIONS
        )
        return dk.hex()

    @staticmethod
    def verify_password(password: str, salt: str, password_hash: str) -> bool:
        """Verify if password matches the hash."""
        computed_hash = PasswordSecurity.hash_password(password, salt)
        return secrets.compare_digest(computed_hash, password_hash)

    @staticmethod
    def create_password_hash(password: str) -> Tuple[str, str]:
        """
        Create a new password hash with a random salt.

        Returns:
            Tuple of (password_hash, salt)
        """
        salt = PasswordSecurity.generate_salt()
        password_hash = PasswordSecurity.hash_password(password, salt)
        return password_hash, salt


class TokenGenerator:
    """Secure token and code generation."""

    @staticmethod
    def generate_session_token(length: int = 64) -> str:
        """Generate a secure session token."""
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_verification_code(length: int = 6) -> str:
        """Generate a numeric verification code."""
        return ''.join([str(secrets.randbelow(10)) for _ in range(length)])
