from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/apis", tags=["apis"])


@router.get("", response_model=list[schemas.ApiResponse])
def list_apis(db: Session = Depends(get_db)):
    """API(기능) 목록. 등록 회사와 카드 메타 포함."""
    apis = (
        db.query(models.Api)
        .options(joinedload(models.Api.company))
        .order_by(models.Api.sort_order, models.Api.id)
        .all()
    )
    return [
        schemas.ApiResponse(
            id=api.id,
            name=api.name,
            company_id=api.company_id,
            company_name=api.company.name,
            task_key=api.task_key,
            task_label=api.task_label,
            card_sublabel=api.card_sublabel,
            model_display=api.model_display,
            tags=api.tags or [],
            is_active=api.is_active,
            sort_order=api.sort_order,
        )
        for api in apis
    ]
