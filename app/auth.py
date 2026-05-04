from datetime import datetime, timedelta, timezone
from typing import Optional
import os
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy import func
from sqlalchemy.orm import Session
from app import models
from app.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

AUTH_SECRET = os.getenv("AUTH_SECRET", "")
API_KEY_SECRET = os.getenv("API_KEY_SECRET", "")
ISSUER = os.getenv("ISSUER", "")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 1

bearer_scheme = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """비밀번호 해싱"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta):
    """JWT 토큰 생성"""
    to_encode = data.copy()
    to_encode.setdefault("iss", ISSUER)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode["exp"] = expire
    encoded_jwt = jwt.encode(to_encode, AUTH_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


def get_user_by_email(db: Session, email: str):
    """이메일로 사용자 조회"""
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_username(db: Session, username: str):
    """사용자명으로 사용자 조회"""
    return db.query(models.User).filter(models.User.username == username).first()


def authenticate_user(db: Session, email: str, password: str):
    """사용자 인증"""
    user = get_user_by_email(db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
):
    """현재 로그인한 사용자 가져오기"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, AUTH_SECRET, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user


def next_api_key_token_version(db: Session, user_id: int) -> int:
    """해당 사용자의 다음 API 키 token_version (기존 최댓값 + 1, 없으면 1)."""
    m = (
        db.query(func.max(models.ApiKey.token_version))
        .filter(models.ApiKey.user_id == user_id)
        .scalar()
    )
    return (m or 0) + 1


def create_api_key_jwt(user_id: int, token_version: int) -> str:
    """API 키용 JWT 생성 (검증 시 DB의 최신 token_version·승인 여부와 함께 확인)."""
    to_encode = {
        "sub": str(user_id),
        "iss": ISSUER,
        "ver": token_version,
    }
    return jwt.encode(to_encode, API_KEY_SECRET, algorithm=ALGORITHM)

