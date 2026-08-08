import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from .config import get_settings
from .database import get_db
from .models import Membership, Organization, User

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return base64.b64encode(salt + digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        raw = base64.b64decode(encoded.encode())
        return hmac.compare_digest(hashlib.scrypt(password.encode(), salt=raw[:16], n=2**14, r=8, p=1), raw[16:])
    except (ValueError, TypeError):
        return False


def create_access_token(user: User, organization: Organization) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user.id), "org": organization.id, "email": user.email, "iat": now, "exp": now + timedelta(minutes=settings.jwt_expiry_minutes)}, settings.jwt_secret, algorithm="HS256")


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: DbSession = Depends(get_db)) -> User | None:
    settings = get_settings()
    if credentials is None:
        if not settings.auth_required:
            return None
        raise HTTPException(401, "Authentication required.", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(401, "Invalid or expired authentication token.", headers={"WWW-Authenticate": "Bearer"}) from exc
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User account is inactive.")
    return user


def assert_org_access(db: DbSession, user: User | None, organization_id: int | None) -> None:
    settings = get_settings()
    if not settings.auth_required or user is None or organization_id is None:
        return
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.organization_id == organization_id))
    if not membership:
        raise HTTPException(403, "You do not have access to this organization.")
