from pydantic import BaseModel, ConfigDict, EmailStr, Field
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
    max_ip_count: int = 0
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
    """API 목록 응답."""

    model_config = ConfigDict(
        from_attributes=True,
        protected_namespaces=(),  # model_display 가 Pydantic 의 model_ 보호 충돌 방지
    )

    id: int
    name: str
    slug: Optional[str] = None
    company_id: int
    company_name: Optional[str] = None
    task_key: Optional[str] = None
    task_label: Optional[str] = None
    card_sublabel: Optional[str] = None
    model_display: Optional[str] = None
    tags: List[str] = []
    is_active: bool = True
    sort_order: int = 0


class UserApiPlanItem(BaseModel):
    """유저가 특정 API에 대해 선택한 플랜 한 건 (라우터에서 api/plan 조인 후 구성)."""
    api_id: int
    api_name: str
    company_id: int
    company_name: str
    plan_id: int
    plan_name: str
    max_rps: int
    max_ip_count: int = 0


class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str


class PlanSelect(BaseModel):
    """API별 플랜 선택/변경 요청 (api_id + plan_id + api_slug_name)"""
    api_id: int
    plan_id: int
    api_slug_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    api_plans: List[UserApiPlanItem] = []  # API별 구독 플랜 목록
    is_active: bool
    is_approved: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    user_id: int


class TokenData(BaseModel):
    email: Optional[str] = None


class AccountApproveRequest(BaseModel):
    """계정 승인 요청."""

    account_id: int


class AccountApproveResponse(BaseModel):
    account_id: int
    approved: bool


class ApiKeyIssueResponse(BaseModel):
    api_key: str
    message: str = "API 키는 이번에만 표시됩니다. 안전한 곳에 저장하세요."


class ApiKeyResponse(BaseModel):
    id: int
    api_key: str = Field(validation_alias="key")
    is_approved: bool = False
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True
