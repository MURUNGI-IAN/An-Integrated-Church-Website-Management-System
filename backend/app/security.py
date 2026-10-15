import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AdminUser

bearer = HTTPBearer(auto_error=False)
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"scrypt${SCRYPT_N}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, cost, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "scrypt":
            return False
        derived = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=int(cost), r=SCRYPT_R, p=SCRYPT_P)
        return hmac.compare_digest(derived.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def get_fernet() -> Fernet:
    key = get_settings().data_encryption_key
    if not key:
        raise HTTPException(status_code=503, detail="Secure form intake is not configured")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Secure form intake is not configured") from exc


def encrypt_text(value: str) -> str:
    return get_fernet().encrypt(value.encode()).decode()


def keyed_digest(value: str, purpose: str) -> str:
    encryption_key = get_settings().data_encryption_key
    if not encryption_key:
        raise HTTPException(status_code=503, detail="Secure form intake is not configured")
    try:
        key_material = base64.urlsafe_b64decode(encryption_key.encode())
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Secure form intake is not configured") from exc
    purpose_key = hmac.new(key_material, purpose.encode(), hashlib.sha256).digest()
    return hmac.new(purpose_key, value.encode(), hashlib.sha256).hexdigest()


def decrypt_text(value: str) -> str:
    try:
        return get_fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(status_code=500, detail="Encrypted record could not be read") from exc


def create_access_token(user: AdminUser) -> str:
    settings = get_settings()
    if len(settings.jwt_secret) < 32:
        raise HTTPException(status_code=503, detail="Admin authentication is not configured")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user.id), "role": user.role, "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes)},
        settings.jwt_secret,
        algorithm="HS256",
    )


def require_roles(*roles: str):
    def dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
        db: Session = Depends(get_db),
    ) -> AdminUser:
        unauthorized = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid staff sign-in required",
            headers={"WWW-Authenticate": "Bearer"},
        )
        settings = get_settings()
        if not credentials or len(settings.jwt_secret) < 32:
            raise unauthorized
        try:
            payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
            user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
            raise unauthorized
        user = db.get(AdminUser, user_id)
        if not user or not user.is_active:
            raise unauthorized
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency