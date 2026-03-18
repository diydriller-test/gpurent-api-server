from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[schemas.PlanResponse])
def list_plans(db: Session = Depends(get_db)):
    """가입 시 선택 가능한 플랜 목록 (3가지)"""
    plans = (
        db.query(models.Plan)
        .filter(models.Plan.is_active == True)
        .order_by(models.Plan.sort_order, models.Plan.id)
        .all()
    )
    return plans
