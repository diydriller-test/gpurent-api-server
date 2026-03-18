from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class PlanResponse(BaseModel):
    """Plan 모델과 동일 필드. 프론트: id, name, description, maxRps, price, period, features."""
    id: int
    name: str
    price_monthly: Decimal
    description: Optional[str] = None
    max_rps: int = 0
    period: str = "/월"
    features: Optional[List[str]] = None
    is_active: bool = True
    sort_order: int = 0

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str


class PlanSelect(BaseModel):
    """플랜 선택/변경 요청"""
    plan_id: int


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    plan_id: Optional[int] = None 
    plan: Optional[PlanResponse] = None
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
