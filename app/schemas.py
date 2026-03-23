from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class PlanResponse(BaseModel):
    """Plan 모델과 동일 필드. api_id 로 소속 API 식별."""
    id: int
    name: str
    api_id: int
    api_name: Optional[str] = None
    price_monthly: Decimal
    description: Optional[str] = None
    max_rps: int = 0
    period: str = "/월"
    features: Optional[List[str]] = None
    is_active: bool = True
    sort_order: int = 0

    class Config:
        from_attributes = True


class CompanyResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class CompanyCreate(BaseModel):
    """회사 등록 요청"""
    name: str


class ApiCreate(BaseModel):
    """회사가 API 등록 요청"""
    name: str
    company_id: int


class ApiResponse(BaseModel):
    """API(기능) 목록용. 등록 회사(company) 포함."""
    id: int
    name: str
    company_id: int
    company_name: Optional[str] = None

    class Config:
        from_attributes = True


class UserApiPlanItem(BaseModel):
    """유저가 특정 API에 대해 선택한 플랜 한 건 (라우터에서 api/plan 조인 후 구성)."""
    api_id: int
    api_name: str
    company_id: int
    company_name: str
    plan_id: int
    plan_name: str
    max_rps: int


class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str


class PlanSelect(BaseModel):
    """API별 플랜 선택/변경 요청 (api_id + plan_id)"""
    api_id: int
    plan_id: int


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    api_plans: List[UserApiPlanItem] = []  # API별 구독 플랜 목록
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
