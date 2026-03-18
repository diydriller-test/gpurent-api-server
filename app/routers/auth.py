from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app import models, schemas, auth
from app.database import get_db
from app import redis_client as redis_store

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    """회원가입"""
    db_user = auth.get_user_by_email(db, email=user_data.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    db_user = auth.get_user_by_username(db, username=user_data.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    hashed_password = auth.get_password_hash(user_data.password)
    db_user = models.User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


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
    """현재 로그인한 사용자 정보 조회 (선택한 플랜 포함)"""
    db.refresh(current_user, ["plan"])
    return current_user


@router.patch("/me/plan", response_model=schemas.UserResponse)
def update_my_plan(
    body: schemas.PlanSelect,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """플랜 선택/변경 (로그인 필요)"""
    plan = db.query(models.Plan).filter(
        models.Plan.id == body.plan_id,
        models.Plan.is_active == True,
    ).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan_id. Use GET /plans to see available plans.",
        )
    current_user.plan_id = body.plan_id
    db.add(current_user)
    db.commit()
    db.refresh(current_user, ["plan"])
    # 게이트웨이용 Redis에 플랜 정보 반영 (plan:{account_id})
    redis_store.set_plan_for_account(
        account_id=current_user.id,
        max_rps=plan.max_rps,
        plan_id=plan.id,
        plan_name=plan.name,
    )
    return current_user


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
    existing = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="API key already exists",
        )

    api_key_jwt = auth.create_api_key_jwt(current_user.id)
    db_api_key = models.ApiKey(user_id=current_user.id, key=api_key_jwt, is_active=True)
    db.add(db_api_key)
    db.commit()

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
    api_key = (
        db.query(models.ApiKey)
        .filter(
            models.ApiKey.user_id == current_user.id,
            models.ApiKey.is_active == True,
        )
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
    """API 키 삭제 (hard delete)"""
    db_api_key = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == current_user.id)
        .first()
    )
    if not db_api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    db.delete(db_api_key)
    db.commit()
