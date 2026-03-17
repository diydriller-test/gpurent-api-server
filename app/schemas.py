from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str


class TokenData(BaseModel):
    email: Optional[str] = None


class ApiKeyIssueResponse(BaseModel):
    api_key: str
    message: str = "API 키는 이번에만 표시됩니다. 안전한 곳에 저장하세요."


class ApiKeyResponse(BaseModel):
    id: int
    api_key: str = Field(validation_alias="key")
    is_active: bool
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True
