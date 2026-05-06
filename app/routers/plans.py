from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[schemas.PlanResponse])
def list_plans(
    api_id: int | None = Query(None, description="특정 API의 플랜만 조회. 미지정 시 전체"),
    db: Session = Depends(get_db),
):
    """플랜 목록. api_id 지정 시 해당 API의 플랜만 반환."""
    q = (
        db.query(models.Plan)
        .options(joinedload(models.Plan.api))
        .filter(models.Plan.is_active == True)
    )
    if api_id is not None:
        q = q.filter(models.Plan.api_id == api_id)
    plans = q.order_by(models.Plan.sort_order, models.Plan.id).all()
    return [
        schemas.PlanResponse(
            id=p.id,
            name=p.name,
            api_id=p.api_id,
            api_name=p.api.name,
            price_monthly=p.price_monthly,
            description=p.description,
            max_rps=p.max_rps,
            max_ip_count=getattr(p, "max_ip_count", 0),
            period=p.period,
            features=p.features,
            is_active=p.is_active,
            sort_order=p.sort_order,
        )
        for p in plans
    ]
