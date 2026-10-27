import hashlib
import hmac
import logging
import os
import re
import secrets
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pwdlib import PasswordHash

from backend.app.database import (
    DatabaseConnection,
    begin_immediate,
    create_board as create_project_board,
    create_personal_workspace,
    create_project,
    connect_database,
    database_integrity_errors,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("nonexistent-account-password")
SESSION_COOKIE = "pm_session"
SESSION_SECONDS = 60 * 60 * 24 * 7
CODE_SECONDS = 60 * 10
RESEND_SECONDS = 60
MAX_CODE_ATTEMPTS = 5
USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,30}$")
COMMON_PASSWORDS = {"password1234", "qwerty123456", "letmein12345"}


def now() -> datetime:
    return datetime.now(UTC)


def timestamp(value: datetime) -> str:
    return value.isoformat()


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def session_secret() -> bytes:
    configured = os.getenv("SESSION_SECRET", "")
    if len(configured) < 32:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured.",
        )
    return configured.encode()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def keyed_digest(value: str, secret: bytes) -> str:
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


def validate_password_strength(value: str) -> str:
    if value.casefold() in COMMON_PASSWORDS:
        raise ValueError("Choose a less common password.")
    if len(value) < 20:
        categories = (
            bool(re.search(r"[a-z]", value)),
            bool(re.search(r"[A-Z]", value)),
            bool(re.search(r"\d", value)),
            bool(re.search(r"[^A-Za-z0-9]", value)),
        )
        if sum(categories) < 3:
            raise ValueError(
                "Use at least three character types or a 20-character passphrase."
            )
    return value


def get_connection(request: Request) -> DatabaseConnection:
    connection = connect_database(request.app.state.database_path)
    return connection


def rate_limit(
    connection: DatabaseConnection,
    key: str,
    maximum: int,
    seconds: int,
) -> None:
    current_time = now()
    with connection:
        begin_immediate(connection, f"rate-limit:{key}")
        row = connection.execute(
            "SELECT count, window_started_at FROM rate_limits WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None or (
            current_time - parse_timestamp(row["window_started_at"])
        ).total_seconds() >= seconds:
            connection.execute(
                """
                INSERT INTO rate_limits (key, count, window_started_at)
                VALUES (?, 1, ?)
                ON CONFLICT(key) DO UPDATE SET
                    count = 1, window_started_at = excluded.window_started_at
                """,
                (key, timestamp(current_time)),
            )
            return
        if row["count"] >= maximum:
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Please try again later.",
            )
        connection.execute(
            "UPDATE rate_limits SET count = count + 1 WHERE key = ?",
            (key,),
        )


def client_key(request: Request, action: str) -> str:
    address = request.client.host if request.client else "unknown"
    return digest(f"{action}:{address}")


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(status_code=403, detail="Invalid request origin.")
    configured_origin = (
        os.getenv("FRONTEND_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or str(request.base_url)
    ).rstrip("/")
    if origin.rstrip("/") != configured_origin:
        raise HTTPException(status_code=403, detail="Invalid request origin.")


def send_code_email(email: str, code: str, purpose: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("EMAIL_FROM_ADDRESS", "").strip()
    if not host or not sender or not parseaddr(sender)[1]:
        raise RuntimeError("Email delivery is not configured.")

    subject = (
        "Verify your Kanban Studio email"
        if purpose == "verify_email"
        else "Reset your Kanban Studio password"
    )
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"Your one-time code is {code}. It expires in 10 minutes. "
        "If you did not request this, you can ignore this email."
    )

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    context = ssl.create_default_context()
    if use_tls:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls(context=context)
            if username:
                server.login(username, smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=10) as server:
            if username:
                server.login(username, smtp_password)
            server.send_message(message)


def send_new_code(
    connection: DatabaseConnection,
    user_id: str,
    email: str,
    purpose: Literal["verify_email", "reset_password"],
) -> None:
    secret = session_secret()
    current_time = now()
    code = f"{secrets.randbelow(1_000_000):06d}"
    with connection:
        begin_immediate(connection, f"email-code:{user_id}:{purpose}")
        previous = connection.execute(
            "SELECT created_at FROM email_codes WHERE user_id = ? AND purpose = ?",
            (user_id, purpose),
        ).fetchone()
        if previous and (
            current_time - parse_timestamp(previous["created_at"])
        ).total_seconds() < RESEND_SECONDS:
            raise HTTPException(
                status_code=429,
                detail="Please wait before requesting another code.",
            )
        connection.execute(
            """
            INSERT INTO email_codes
                (id, user_id, purpose, code_hash, expires_at, attempts, consumed_at, created_at)
            VALUES (?, ?, ?, ?, ?, 0, NULL, ?)
            ON CONFLICT(user_id, purpose) DO UPDATE SET
                id = excluded.id,
                code_hash = excluded.code_hash,
                expires_at = excluded.expires_at,
                attempts = 0,
                consumed_at = NULL,
                created_at = excluded.created_at
            """,
            (
                uuid4().hex,
                user_id,
                purpose,
                keyed_digest(f"{purpose}:{user_id}:{code}", secret),
                timestamp(current_time + timedelta(seconds=CODE_SECONDS)),
                timestamp(current_time),
            ),
        )
    try:
        send_code_email(email, code, purpose)
    except (OSError, RuntimeError, smtplib.SMTPException, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Email delivery is unavailable. Please try again later.",
        ) from error


def verify_code(
    connection: DatabaseConnection,
    user_id: str,
    purpose: Literal["verify_email", "reset_password"],
    code: str,
) -> bool:
    with connection:
        begin_immediate(connection, f"email-code:{user_id}:{purpose}")
        row = connection.execute(
            """
            SELECT id, code_hash, expires_at, attempts, consumed_at
            FROM email_codes WHERE user_id = ? AND purpose = ?
            """,
            (user_id, purpose),
        ).fetchone()
        if (
            row is None
            or row["consumed_at"] is not None
            or parse_timestamp(row["expires_at"]) <= now()
            or row["attempts"] >= MAX_CODE_ATTEMPTS
        ):
            return False

        expected = keyed_digest(f"{purpose}:{user_id}:{code}", session_secret())
        if hmac.compare_digest(row["code_hash"], expected):
            connection.execute(
                "UPDATE email_codes SET consumed_at = ? WHERE id = ?",
                (timestamp(now()), row["id"]),
            )
            return True
        connection.execute(
            "UPDATE email_codes SET attempts = attempts + 1 WHERE id = ?",
            (row["id"],),
        )
    return False


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=12, max_length=128)
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        result = " ".join(value.split())
        if not result:
            raise ValueError("Full name is required.")
        return result

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        result = value.strip().lower()
        if not USERNAME_PATTERN.fullmatch(result):
            raise ValueError("Use 3-30 letters, numbers, or underscores.")
        return result

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).strip().lower() if value is not None else None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class EmailCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reset_token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


def create_board(connection: DatabaseConnection, user_id: str) -> None:
    workspace_id = create_personal_workspace(connection, user_id)
    project_id = create_project(
        connection,
        workspace_id,
        user_id,
        "Kanban Studio",
    )
    create_project_board(connection, user_id, project_id)


def clear_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=os.getenv("AUTH_COOKIE_SECURE", "true").lower() == "true",
        httponly=True,
        samesite="strict",
    )


def set_session_cookie(response: Response, raw_session: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        raw_session,
        max_age=SESSION_SECONDS,
        path="/",
        secure=os.getenv("AUTH_COOKIE_SECURE", "true").lower() == "true",
        httponly=True,
        samesite="strict",
    )


def current_user(request: Request) -> dict[str, str]:
    raw_session = request.cookies.get(SESSION_COOKIE)
    if not raw_session:
        raise HTTPException(status_code=401, detail="Authentication required.")
    connection = get_connection(request)
    try:
        row = connection.execute(
            """
            SELECT users.id, users.username, users.email, users.full_name, users.role
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.id = ? AND sessions.expires_at > ?
                AND (users.email IS NULL OR users.email_verified_at IS NOT NULL)
            """,
            (digest(raw_session), timestamp(now())),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        return dict(row)
    finally:
        connection.close()


AuthenticatedUser = Annotated[dict[str, str], Depends(current_user)]


def enforce_login_origin(request: Request) -> None:
    check_origin(request)


OriginCheck = Annotated[None, Depends(enforce_login_origin)]


@router.post("/register", status_code=201)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    _: OriginCheck,
) -> dict[str, str]:
    connection = get_connection(request)
    try:
        rate_limit(connection, client_key(request, "register"), 5, 3600)
        duplicate_query = "SELECT 1 FROM users WHERE lower(username) = ?"
        duplicate_values = (body.username,)
        if body.email is not None:
            duplicate_query += " OR lower(email) = ?"
            duplicate_values += (body.email,)
        if connection.execute(
            duplicate_query,
            duplicate_values,
        ).fetchone():
            raise HTTPException(
                status_code=409,
                detail="That username is already registered.",
            )

        user_id = uuid4().hex
        email_verified_at = timestamp(now()) if body.email is None else None
        with connection:
            connection.execute(
                """
                INSERT INTO users
                    (id, username, full_name, email, password_hash, role,
                        email_verified_at, created_at)
                VALUES (?, ?, ?, ?, ?, 'member', ?, ?)
                """,
                (
                    user_id,
                    body.username,
                    body.full_name or body.username,
                    body.email,
                    password_hash.hash(body.password),
                    email_verified_at,
                    timestamp(now()),
                ),
            )
            create_board(connection, user_id)
        if body.email is not None:
            send_new_code(connection, user_id, body.email, "verify_email")
            response.status_code = 202
            return {"message": "Check your email for a verification code."}

        raw_session = secrets.token_urlsafe(32)
        with connection:
            connection.execute(
                "INSERT INTO sessions (id, user_id, expires_at, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    digest(raw_session),
                    user_id,
                    timestamp(now() + timedelta(seconds=SESSION_SECONDS)),
                    timestamp(now()),
                ),
            )
        set_session_cookie(response, raw_session)
        return {"message": "Account created."}
    except database_integrity_errors() as error:
        raise HTTPException(
            status_code=409,
            detail="That username is already registered.",
        ) from error
    finally:
        connection.close()


@router.post("/verify-email")
def verify_email(
    body: EmailCodeRequest,
    request: Request,
    _: OriginCheck,
) -> dict[str, str]:
    connection = get_connection(request)
    try:
        rate_limit(connection, client_key(request, "verify"), 10, 900)
        user = connection.execute(
            "SELECT id, email_verified_at FROM users WHERE lower(email) = ?",
            (body.email,),
        ).fetchone()
        if user is None or user["email_verified_at"] is not None:
            raise HTTPException(status_code=400, detail="Invalid or expired code.")
        if not verify_code(connection, user["id"], "verify_email", body.code):
            raise HTTPException(status_code=400, detail="Invalid or expired code.")
        with connection:
            connection.execute(
                "UPDATE users SET email_verified_at = ? WHERE id = ?",
                (timestamp(now()), user["id"]),
            )
        return {"message": "Email verified. You can now sign in."}
    finally:
        connection.close()


@router.post("/resend-verification", status_code=202)
def resend_verification(
    body: EmailRequest,
    request: Request,
    _: OriginCheck,
) -> dict[str, str]:
    connection = get_connection(request)
    try:
        rate_limit(connection, client_key(request, "resend-verification"), 5, 3600)
        user = connection.execute(
            "SELECT id, email_verified_at FROM users WHERE lower(email) = ?",
            (body.email,),
        ).fetchone()
        if user and user["email_verified_at"] is None:
            try:
                send_new_code(connection, user["id"], body.email, "verify_email")
            except HTTPException as error:
                if error.status_code == 503:
                    logging.warning("Verification email delivery failed.")
                elif error.status_code != 429:
                    raise
        return {"message": "If the account needs verification, a code has been sent."}
    finally:
        connection.close()


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    _: OriginCheck,
) -> dict[str, object]:
    connection = get_connection(request)
    try:
        identifier = body.identifier.strip().casefold()
        rate_limit(connection, client_key(request, "login"), 10, 900)
        rate_limit(
            connection,
            digest(f"login-identifier:{identifier}"),
            8,
            900,
        )
        user = connection.execute(
            """
            SELECT id, username, email, full_name, role, password_hash,
                email_verified_at
            FROM users WHERE lower(username) = ? OR lower(email) = ?
            """,
            (identifier, identifier),
        ).fetchone()
        stored_hash = user["password_hash"] if user else DUMMY_PASSWORD_HASH
        password_matches = password_hash.verify(body.password, stored_hash)
        if (
            user is None
            or user["password_hash"] is None
            or not password_matches
            or (
                user["email"] is not None
                and user["email_verified_at"] is None
            )
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid username/email or password.",
            )

        raw_session = secrets.token_urlsafe(32)
        with connection:
            connection.execute(
                "INSERT INTO sessions (id, user_id, expires_at, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    digest(raw_session),
                    user["id"],
                    timestamp(now() + timedelta(seconds=SESSION_SECONDS)),
                    timestamp(now()),
                ),
            )
        set_session_cookie(response, raw_session)
        return {
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"],
            }
        }
    finally:
        connection.close()


@router.get("/me")
def me(user: AuthenticatedUser) -> dict[str, object]:
    return {"user": user}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, _: OriginCheck) -> Response:
    raw_session = request.cookies.get(SESSION_COOKIE)
    if raw_session:
        connection = get_connection(request)
        try:
            with connection:
                connection.execute(
                    "DELETE FROM sessions WHERE id = ?",
                    (digest(raw_session),),
                )
        finally:
            connection.close()
    clear_cookie(response)
    response.status_code = 204
    return response


@router.post("/forgot-password", status_code=202)
def forgot_password(
    body: EmailRequest,
    request: Request,
    _: OriginCheck,
) -> dict[str, str]:
    connection = get_connection(request)
    try:
        rate_limit(connection, client_key(request, "forgot-password"), 5, 3600)
        rate_limit(
            connection,
            digest(f"forgot-email:{body.email}"),
            3,
            3600,
        )
        user = connection.execute(
            "SELECT id FROM users WHERE lower(email) = ? AND email_verified_at IS NOT NULL",
            (body.email,),
        ).fetchone()
        if user:
            try:
                send_new_code(
                    connection,
                    user["id"],
                    body.email,
                    "reset_password",
                )
            except HTTPException as error:
                if error.status_code == 503:
                    logging.warning("Password reset email delivery failed.")
                elif error.status_code != 429:
                    raise
        return {"message": "If the account exists, a reset code has been sent."}
    finally:
        connection.close()


@router.post("/verify-reset-code")
def verify_reset_code(
    body: EmailCodeRequest,
    request: Request,
    _: OriginCheck,
) -> dict[str, str]:
    connection = get_connection(request)
    try:
        rate_limit(connection, client_key(request, "verify-reset"), 10, 900)
        user = connection.execute(
            "SELECT id FROM users WHERE lower(email) = ? AND email_verified_at IS NOT NULL",
            (body.email,),
        ).fetchone()
        if user is None or not verify_code(
            connection,
            user["id"],
            "reset_password",
            body.code,
        ):
            raise HTTPException(status_code=400, detail="Invalid or expired code.")

        raw_token = secrets.token_urlsafe(32)
        with connection:
            connection.execute(
                "INSERT INTO reset_challenges (token_hash, user_id, expires_at) "
                "VALUES (?, ?, ?)",
                (
                    digest(raw_token),
                    user["id"],
                    timestamp(now() + timedelta(minutes=10)),
                ),
            )
        return {"reset_token": raw_token}
    finally:
        connection.close()


@router.post("/reset-password")
def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    _: OriginCheck,
) -> dict[str, str]:
    connection = get_connection(request)
    try:
        with connection:
            token_hash = digest(body.reset_token)
            begin_immediate(connection, f"reset-challenge:{token_hash}")
            current_time = timestamp(now())
            challenge = connection.execute(
                """
                SELECT user_id FROM reset_challenges
                WHERE token_hash = ? AND consumed_at IS NULL AND expires_at > ?
                """,
                (token_hash, current_time),
            ).fetchone()
            if challenge is None:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid or expired reset.",
                )
            consumed = connection.execute(
                """
                UPDATE reset_challenges SET consumed_at = ?
                WHERE token_hash = ? AND consumed_at IS NULL AND expires_at > ?
                """,
                (current_time, token_hash, current_time),
            )
            if consumed.rowcount != 1:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid or expired reset.",
                )
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash.hash(body.password), challenge["user_id"]),
            )
            connection.execute(
                "DELETE FROM sessions WHERE user_id = ?",
                (challenge["user_id"],),
            )
        return {"message": "Password reset. Please sign in with your new password."}
    finally:
        connection.close()


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: AuthenticatedUser,
    _: OriginCheck,
) -> dict[str, str]:
    connection = get_connection(request)
    try:
        row = connection.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
        if (
            row is None
            or not row["password_hash"]
            or not password_hash.verify(body.current_password, row["password_hash"])
        ):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        with connection:
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash.hash(body.new_password), user["id"]),
            )
            connection.execute(
                "DELETE FROM sessions WHERE user_id = ? AND id != ?",
                (
                    user["id"],
                    digest(request.cookies.get(SESSION_COOKIE, "")),
                ),
            )
        return {"message": "Password updated."}
    finally:
        connection.close()


def require_role(required_role: str):
    def check(user: AuthenticatedUser) -> dict[str, str]:
        if user["role"] != required_role:
            raise HTTPException(status_code=403, detail="Insufficient permissions.")
        return user

    return check


AdminUser = Annotated[dict[str, str], Depends(require_role("admin"))]


@router.get("/admin/users")
def list_users(request: Request, _: AdminUser) -> list[dict[str, str]]:
    connection = get_connection(request)
    try:
        rows = connection.execute(
            "SELECT id, username, email, full_name, role FROM users ORDER BY username"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()
