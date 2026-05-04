from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, joinedload
from app import models, schemas, auth
from app.database import get_db
from app import redis_client as redis_store

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    """회원가입"""
    # 이메일 중복 체크
    db_user = auth.get_user_by_email(db, email=user_data.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    # 이름 중복 체크
    db_user = auth.get_user_by_username(db, username=user_data.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    # 유저 생성
    hashed_password = auth.get_password_hash(user_data.password)
    db_user = models.User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    db.flush()
    # API 키 생성
    ver = auth.next_api_key_token_version(db, db_user.id)
    api_key_jwt = auth.create_api_key_jwt(db_user.id, ver)
    db_api_key = models.ApiKey(
        user_id=db_user.id,
        key=api_key_jwt,
        token_version=ver,
    )
    db.add(db_api_key)
    db.commit()
    db.refresh(db_user)
    db.refresh(db_api_key)
    # Redis에 계정 메타 정보 설정
    redis_store.set_account_meta(
        account_id=db_user.id,
        approved=db_api_key.is_approved,
        token_version=db_api_key.token_version,
    )

    return schemas.UserResponse(
        id=db_user.id,
        email=db_user.email,
        username=db_user.username,
        api_plans=[],
        is_active=db_user.is_active,
        created_at=db_user.created_at,
    )


@router.post("/login", response_model=schemas.Token)
def login_with_email(
    login_data: schemas.UserLogin,
    db: Session = Depends(get_db)
):
    """이메일과 비밀번호로 로그인"""
    user = auth.authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    access_token_expires = timedelta(days=auth.ACCESS_TOKEN_EXPIRE_DAYS)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token}


@router.get("/me", response_model=schemas.UserResponse)
def read_users_me(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """현재 로그인한 사용자 정보 조회 (API별 구독 플랜 목록 포함)"""
    user = (
        db.query(models.User)
        .options(
            joinedload(models.User.user_api_plans).joinedload(models.UserApiPlan.api).joinedload(models.Api.company),
            joinedload(models.User.user_api_plans).joinedload(models.UserApiPlan.plan),
        )
        .filter(models.User.id == current_user.id)
        .first()
    )
    api_plans = [
        schemas.UserApiPlanItem(
            api_id=uap.api_id,
            api_name=uap.api.name,
            company_id=uap.api.company_id,
            company_name=uap.api.company.name,
            plan_id=uap.plan_id,
            plan_name=uap.plan.name,
            max_rps=uap.plan.max_rps,
        )
        for uap in user.user_api_plans
    ]
    return schemas.UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        api_plans=api_plans,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.patch("/me/plan", response_model=schemas.UserResponse)
def update_my_plan(
    body: schemas.PlanSelect,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """API별 플랜 선택/변경 (로그인 필요). api_id + plan_id 로 해당 API에 대한 플랜 설정."""
    api = db.query(models.Api).filter(models.Api.id == body.api_id).first()
    if not api:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid api_id. Use GET /apis to see available APIs.",
        )
    plan = db.query(models.Plan).filter(
        models.Plan.id == body.plan_id,
        models.Plan.api_id == body.api_id,
        models.Plan.is_active == True,
    ).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan_id or plan does not belong to this API. Use GET /plans?api_id=... to see available plans.",
        )
    uap = (
        db.query(models.UserApiPlan)
        .filter(
            models.UserApiPlan.user_id == current_user.id,
            models.UserApiPlan.api_id == body.api_id,
        )
        .first()
    )
    if uap:
        uap.plan_id = body.plan_id
        db.add(uap)
    else:
        uap = models.UserApiPlan(
            user_id=current_user.id,
            api_id=body.api_id,
            plan_id=body.plan_id,
        )
        db.add(uap)
    db.commit()
    # 게이트웨이용 Redis: plan:{account_id}:{api_id}
    redis_store.set_plan_for_account_api(
        account_id=current_user.id,
        api_id=body.api_id,
        api_name=api.name,
        max_rps=plan.max_rps,
        plan_id=plan.id,
        plan_name=plan.name,
    )
    # 응답은 GET /me 와 동일한 형태 (joinedload로 재조회)
    user = (
        db.query(models.User)
        .options(
            joinedload(models.User.user_api_plans).joinedload(models.UserApiPlan.api).joinedload(models.Api.company),
            joinedload(models.User.user_api_plans).joinedload(models.UserApiPlan.plan),
        )
        .filter(models.User.id == current_user.id)
        .first()
    )
    api_plans = [
        schemas.UserApiPlanItem(
            api_id=uap.api_id,
            api_name=uap.api.name,
            company_id=uap.api.company_id,
            company_name=uap.api.company.name,
            plan_id=uap.plan_id,
            plan_name=uap.plan.name,
            max_rps=uap.plan.max_rps,
        )
        for uap in user.user_api_plans
    ]
    return schemas.UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        api_plans=api_plans,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post(
    "/accounts/approve",
    response_model=schemas.AccountApproveResponse,
    status_code=status.HTTP_200_OK,
)
def approve_account(body: schemas.AccountApproveRequest, db: Session = Depends(get_db)):
    """
    사용자 계정 승인
    """
    # 사용자 조회
    user = db.query(models.User).filter(models.User.id == body.account_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    # 가장 최근 발급분 조회
    latest_key = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == body.account_id)
        .order_by(models.ApiKey.token_version.desc())
        .first()
    )
    if not latest_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found for this account",
        )
    # 승인
    latest_key.is_approved = True
    db.commit()
    # Redis에 계정 메타 정보 설정
    redis_store.set_account_meta(
        account_id=body.account_id,
        approved=True,
        token_version=latest_key.token_version,
    )
    return schemas.AccountApproveResponse(
        account_id=body.account_id,
        approved=True,
        token_version=latest_key.token_version,
    )


@router.post(
    "/api-keys",
    response_model=schemas.ApiKeyIssueResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_api_key(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """API 키 발급"""
    # 토큰 버전 증가
    ver = auth.next_api_key_token_version(db, current_user.id)
    api_key_jwt = auth.create_api_key_jwt(current_user.id, ver)
    db_api_key = models.ApiKey(
        user_id=current_user.id,
        key=api_key_jwt,
        token_version=ver,
    )
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)
    # Redis에 계정 메타 정보 설정
    redis_store.set_account_meta(
        account_id=current_user.id,
        approved=db_api_key.is_approved,
        token_version=db_api_key.token_version,
    )

    return {
        "api_key": api_key_jwt,
        "message": "API 키가 발급되었습니다. 조회 API로 언제든 확인할 수 있습니다.",
    }


@router.get("/api-keys", response_model=schemas.ApiKeyResponse)
def get_api_key(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """API 키 조회"""
    # 가장 최근 발급분 조회
    api_key = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == current_user.id)
        .order_by(models.ApiKey.token_version.desc())
        .first()
    )
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    return api_key


@router.delete("/api-keys", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """API 키 삭제"""
    rows = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == current_user.id)
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    for row in rows:
        db.delete(row)
    db.commit()
    redis_store.delete_account_meta(current_user.id)
