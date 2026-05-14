import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.database import get_db


def _split_analytics_path() -> tuple[str, str]:
    """INTERNAL_ANALYTICS_PATH 예: /analytics/behavior → ("/analytics", "/behavior")."""
    default = "/analytics/behavior"
    raw = (os.getenv("INTERNAL_ANALYTICS_PATH") or default).strip()
    if not raw.startswith("/"):
        raw = "/" + raw
    raw = raw.rstrip("/")
    if not raw:
        raw = default
    segments = [p for p in raw.split("/") if p]
    if len(segments) == 1:
        return "", f"/{segments[0]}"
    *rest, last = segments
    return "/" + "/".join(rest), f"/{last}"


def _element_dom_type(event_type: str, props: Optional[dict]) -> Optional[str]:
    """properties JSON 의 DOM type 키(`type`)를 컬럼으로 분리 저장."""
    if event_type != "element_click" or not props:
        return None
    v = props.get("type")
    if v is None:
        return None
    s = str(v).strip()
    return s[:50] if s else None


_route_prefix, _route_path = _split_analytics_path()
router = APIRouter(prefix=_route_prefix, tags=["behavior"])


@router.post(
    _route_path,
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
            element_dom_type=_element_dom_type(e.type, e.properties),
            name=e.name,
            occurred_at=e.occurred_at,
            properties=e.properties,
        )
        for e in body.events
    ]
    db.add_all(rows)
    db.commit()
    return schemas.BehaviorIngestResponse(accepted=len(rows))
