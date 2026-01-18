"""Email service for sending verification codes."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Tuple, Optional

from .database import DatabaseManager
from .security import TokenGenerator


@dataclass
class SMTPConfig:
    """SMTP configuration."""
    host: str = "smtp.qq.com"
    port: int = 587
    username: str = ""
    password: str = ""  # Authorization code for QQ mail
    use_tls: bool = True
    sender_name: str = "Vision Tracker"


class EmailService:
    """Email service for verification codes."""

    CODE_EXPIRY_MINUTES = 5

    def __init__(self, config: SMTPConfig, db_manager: DatabaseManager):
        self.config = config
        self.db = db_manager

    def send_verification_code(self, email: str, code_type: str = "register") -> Tuple[bool, str]:
        """
        Send verification code to email.

        Args:
            email: Target email address
            code_type: Type of verification (register/reset_password)

        Returns:
            Tuple of (success, message/code)
        """
        try:
            # Generate verification code
            code = TokenGenerator.generate_verification_code(6)

            # Calculate expiry time
            expires_at = datetime.now() + timedelta(minutes=self.CODE_EXPIRY_MINUTES)

            # Store code in database
            self.db.execute_command(
                '''INSERT INTO verification_codes (email, code, code_type, expires_at)
                   VALUES (?, ?, ?, ?)''',
                (email, code, code_type, expires_at.isoformat())
            )

            # Build and send email
            subject, content = self._build_email_content(code, code_type)
            success = self._send_email(email, subject, content)

            if success:
                return True, code
            else:
                return False, "Failed to send email"

        except Exception as e:
            print(f"Error sending verification code: {e}")
            return False, str(e)

    def verify_code(self, email: str, code: str, code_type: str = "register") -> bool:
        """
        Verify if the code is valid and not expired.

        Args:
            email: Email address
            code: Verification code
            code_type: Type of verification

        Returns:
            True if code is valid
        """
        rows = self.db.execute_query(
            '''SELECT id FROM verification_codes
               WHERE email = ? AND code = ? AND code_type = ?
               AND expires_at > ? AND is_used = FALSE
               ORDER BY created_at DESC LIMIT 1''',
            (email, code, code_type, datetime.now().isoformat())
        )

        if rows:
            # Mark code as used
            self.db.execute_command(
                'UPDATE verification_codes SET is_used = TRUE WHERE id = ?',
                (rows[0]['id'],)
            )
            return True
        return False

    def _build_email_content(self, code: str, code_type: str) -> Tuple[str, str]:
        """Build email subject and content."""
        if code_type == "register":
            subject = "Vision Tracker – Email Verification Code"
            content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>Vision Tracker Verification</title>
            </head>
            <body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial, sans-serif;">
                <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                        <td align="center" style="padding:40px 0;">
                            <table width="420" cellpadding="0" cellspacing="0"
                                   style="background-color:#ffffff; border-radius:12px;
                                          box-shadow:0 8px 24px rgba(0,0,0,0.08);
                                          padding:32px; text-align:center;">

                                <tr>
                                    <td>
                                        <h2 style="margin:0 0 12px; color:#222;">
                                            Welcome to Vision Tracker
                                        </h2>
                                        <p style="margin:0 0 24px; color:#555; font-size:14px;">
                                            Please use the verification code below to complete your registration
                                        </p>
                                    </td>
                                </tr>

                                <tr>
                                    <td>
                                        <div style="
                                            display:inline-block;
                                            padding:16px 28px;
                                            background-color:#f7f2fb;
                                            border-radius:10px;
                                            margin-bottom:24px;">
                                            <span style="
                                                font-size:36px;
                                                font-weight:700;
                                                color:#D087DF;
                                                letter-spacing:10px;">
                                                {code}
                                            </span>
                                        </div>
                                    </td>
                                </tr>

                                <tr>
                                    <td>
                                        <p style="margin:0 0 8px; color:#444; font-size:14px;">
                                            This code will expire in
                                            <strong>{self.CODE_EXPIRY_MINUTES} minutes</strong>.
                                        </p>
                                        <p style="margin:0; color:#888; font-size:12px;">
                                            If you did not request this verification, please ignore this email.
                                        </p>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding-top:32px;">
                                        <p style="margin:0; color:#aaa; font-size:12px;">
                                            © Vision Tracker
                                        </p>
                                    </td>
                                </tr>

                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
        elif code_type == "change_email":
            subject = "Vision Tracker - Email Change Verification"
            content = f'''
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #333;">Email Change Request</h2>
                <p>Your verification code is:</p>
                <h1 style="color: #D087DF; letter-spacing: 8px; font-size: 36px;">{code}</h1>
                <p>This code will expire in {self.CODE_EXPIRY_MINUTES} minutes.</p>
                <p style="color: #666; font-size: 12px;">If you didn't request this change, please secure your account immediately.</p>
            </body>
            </html>
            '''
        else:  # reset_password
            subject = "Vision Tracker - Password Reset Code"
            content = f'''
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #333;">Password Reset Request</h2>
                <p>Your verification code is:</p>
                <h1 style="color: #D087DF; letter-spacing: 8px; font-size: 36px;">{code}</h1>
                <p>This code will expire in {self.CODE_EXPIRY_MINUTES} minutes.</p>
                <p style="color: #666; font-size: 12px;">If you didn't request this, please secure your account immediately.</p>
            </body>
            </html>
            '''
        return subject, content

    def _send_email(self, to_email: str, subject: str, content: str) -> bool:
        """Send email via SMTP."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.config.sender_name} <{self.config.username}>"
            msg['To'] = to_email

            html_part = MIMEText(content, 'html', 'utf-8')
            msg.attach(html_part)

            with smtplib.SMTP(self.config.host, self.config.port) as server:
                if self.config.use_tls:
                    server.starttls()
                server.login(self.config.username, self.config.password)
                server.sendmail(self.config.username, to_email, msg.as_string())

            return True
        except Exception as e:
            print(f"Email send failed: {e}")
            return False
