from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app import models, schemas, auth
from app.database import get_db

router = APIRouter(prefix="/apis", tags=["apis"])


@router.get("", response_model=list[schemas.ApiResponse])
def list_apis(db: Session = Depends(get_db)):
    """API(기능) 목록. 등록 회사(company) 포함. 플랜 페이지에서 API별 플랜 선택 시 사용."""
    apis = (
        db.query(models.Api)
        .options(joinedload(models.Api.company))
        .order_by(models.Api.id)
        .all()
    )
    return [
        schemas.ApiResponse(
            id=api.id,
            name=api.name,
            company_id=api.company_id,
            company_name=api.company.name,
        )
        for api in apis
    ]
