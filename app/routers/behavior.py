from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.database import get_db

router = APIRouter(prefix="/analytics", tags=["behavior"])


@router.post(
    "/behavior",
    response_model=schemas.BehaviorIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_behavior(
    body: schemas.BehaviorBatchRequest,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user_optional),
):
    """유저 행동 이벤트 배치 수집. JWT가 있으면 user_id는 토큰 사용자와 일치해야 함."""
    if current_user is not None:
        resolved_user_id = current_user.id
        if body.user_id is not None and body.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_id does not match authenticated user",
            )
    else:
        resolved_user_id = body.user_id
        if resolved_user_id is not None:
            exists = (
                db.query(models.User.id)
                .filter(models.User.id == resolved_user_id)
                .first()
            )
            if not exists:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="user_id not found",
                )

    rows = [
        models.BehaviorEvent(
            user_id=resolved_user_id,
            client_ip=body.client_ip,
            event_type=e.type,
            name=e.name,
            occurred_at=e.occurred_at,
            properties=e.properties,
        )
        for e in body.events
    ]
    db.add_all(rows)
    db.commit()
    return schemas.BehaviorIngestResponse(accepted=len(rows))
