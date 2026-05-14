from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from typing import Optional, List, Literal, Any
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


class AccountRedisRebuildResponse(BaseModel):
    """계정별 Redis(plan·account) 삭제 후 DB 기준 재동기화 결과."""

    account_id: int
    cleared: bool
    account_meta_refreshed: bool
    plans_written: int


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


BehaviorEventType = Literal["page_view", "element_click", "custom"]


class PageViewProperties(BaseModel):
    """page_view 이벤트 properties (path·title + 확장 필드)."""

    model_config = ConfigDict(extra="allow")

    path: Optional[str] = None
    title: Optional[str] = None


class ElementClickProperties(BaseModel):
    """element_click 이벤트 properties. DOM 의 type 은 dom_element_type 으로 파싱해 이벤트 최상위 type 과 구분."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    dom_element_type: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("type", "dom_element_type"),
        serialization_alias="type",
    )
    text: Optional[str] = None
    href: Optional[str] = None
    data_behavior: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("data_behavior", "dataBehavior"),
        serialization_alias="data_behavior",
    )
    element_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("id", "element_id"),
        serialization_alias="id",
    )
    class_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("className", "class_name"),
        serialization_alias="className",
    )
    role: Optional[str] = None
    page_path: Optional[str] = None


class BehaviorEventItem(BaseModel):
    """단일 행동 이벤트 (Next 정규화 형태). 구 click 은 element_click 으로만 수신."""

    type: BehaviorEventType
    name: str = ""
    occurred_at: datetime
    properties: Optional[dict[str, Any]] = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: Any) -> str:
        if v is None:
            return "unknown"
        s = str(v).strip()
        return s if s else "unknown"

    @model_validator(mode="after")
    def validate_properties_by_type(self) -> "BehaviorEventItem":
        props = self.properties
        if props is None:
            return self
        if not isinstance(props, dict):
            raise ValueError("properties must be an object")
        if self.type == "page_view":
            parsed = PageViewProperties.model_validate(props)
            return self.model_copy(
                update={
                    "properties": parsed.model_dump(
                        mode="json",
                        by_alias=True,
                        exclude_none=True,
                    )
                }
            )
        if self.type == "element_click":
            parsed = ElementClickProperties.model_validate(props)
            return self.model_copy(
                update={
                    "properties": parsed.model_dump(
                        mode="json",
                        by_alias=True,
                        exclude_none=True,
                    )
                }
            )
        # custom: 자유 형태, 검증만 dict
        return self


class BehaviorBatchRequest(BaseModel):
    events: List[BehaviorEventItem] = Field(..., min_length=1, max_length=100)
    user_id: Optional[int] = None
    client_ip: Optional[str] = None


class BehaviorIngestResponse(BaseModel):
    accepted: int
