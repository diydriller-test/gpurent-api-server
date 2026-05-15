import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.database import get_db
from app.schemas import TRACKED_PAGE_PATHS


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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _page_view_path_filter(path_expr, page: str):
    """properties.path 가 해당 페이지(쿼리·해시 접두)인 page_view 조건."""
    if page == "/":
        return or_(path_expr == "/", path_expr.like("/?%"), path_expr.like("/#%"))
    return or_(
        path_expr == page,
        path_expr.like(f"{page}?%"),
        path_expr.like(f"{page}#%"),
    )


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


@router.get(
    f"{_route_path}/visitors",
    response_model=schemas.BehaviorVisitorListResponse,
)
def list_behavior_visitors(
    db: Session = Depends(get_db),
    window_minutes: int = Query(1440, ge=1, le=60 * 24 * 30),
):
    """접속(이벤트) 이력이 있는 user_id 또는 client_ip 목록."""
    since = _utc_now() - timedelta(minutes=window_minutes)
    base = db.query(models.BehaviorEvent).filter(
        models.BehaviorEvent.occurred_at >= since
    )

    visitors: list[schemas.BehaviorVisitorItem] = []

    user_rows = (
        base.filter(models.BehaviorEvent.user_id.isnot(None))
        .with_entities(
            models.BehaviorEvent.user_id,
            func.max(models.BehaviorEvent.occurred_at).label("last_seen_at"),
            func.count(models.BehaviorEvent.id).label("event_count"),
            func.max(models.BehaviorEvent.client_ip).label("client_ip"),
        )
        .group_by(models.BehaviorEvent.user_id)
        .order_by(func.max(models.BehaviorEvent.occurred_at).desc())
        .all()
    )
    for row in user_rows:
        visitors.append(
            schemas.BehaviorVisitorItem(
                key=f"user:{row.user_id}",
                user_id=row.user_id,
                client_ip=row.client_ip,
                last_seen_at=row.last_seen_at,
                event_count=row.event_count,
            )
        )

    ip_rows = (
        base.filter(
            models.BehaviorEvent.user_id.is_(None),
            models.BehaviorEvent.client_ip.isnot(None),
        )
        .with_entities(
            models.BehaviorEvent.client_ip,
            func.max(models.BehaviorEvent.occurred_at).label("last_seen_at"),
            func.count(models.BehaviorEvent.id).label("event_count"),
        )
        .group_by(models.BehaviorEvent.client_ip)
        .order_by(func.max(models.BehaviorEvent.occurred_at).desc())
        .all()
    )
    for row in ip_rows:
        visitors.append(
            schemas.BehaviorVisitorItem(
                key=f"ip:{row.client_ip}",
                user_id=None,
                client_ip=row.client_ip,
                last_seen_at=row.last_seen_at,
                event_count=row.event_count,
            )
        )

    visitors.sort(key=lambda v: v.last_seen_at, reverse=True)
    return schemas.BehaviorVisitorListResponse(
        visitors=visitors,
        window_minutes=window_minutes,
    )


@router.get(
    f"{_route_path}/visitors/timeline",
    response_model=schemas.BehaviorVisitorTimelineResponse,
)
def get_visitor_timeline(
    db: Session = Depends(get_db),
    user_id: Optional[int] = Query(None),
    client_ip: Optional[str] = Query(None),
    window_minutes: int = Query(10, ge=1, le=60),
):
    """방문자 선택 시 최근 N분(기본 10분) 행동 이벤트."""
    if (user_id is None) == (client_ip is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one of user_id or client_ip is required",
        )

    since = _utc_now() - timedelta(minutes=window_minutes)
    q = db.query(models.BehaviorEvent).filter(
        models.BehaviorEvent.occurred_at >= since
    )
    if user_id is not None:
        q = q.filter(models.BehaviorEvent.user_id == user_id)
    else:
        q = q.filter(
            models.BehaviorEvent.client_ip == client_ip,
            models.BehaviorEvent.user_id.is_(None),
        )

    events = q.order_by(models.BehaviorEvent.occurred_at.desc()).all()
    return schemas.BehaviorVisitorTimelineResponse(
        user_id=user_id,
        client_ip=client_ip,
        window_minutes=window_minutes,
        events=[schemas.BehaviorEventRecord.model_validate(e) for e in events],
    )


@router.get(
    f"{_route_path}/pages/stats",
    response_model=schemas.BehaviorPageStatsResponse,
)
def get_page_visit_stats(
    db: Session = Depends(get_db),
    window_minutes: Optional[int] = Query(
        None,
        ge=1,
        le=60 * 24 * 365,
        description="미지정 시 전체 기간",
    ),
):
    """지정 페이지(/, /api-test, /plans, /docs)별 page_view 접속 횟수."""
    path_expr = models.BehaviorEvent.properties["path"].astext
    since = None
    if window_minutes is not None:
        since = _utc_now() - timedelta(minutes=window_minutes)

    pages: list[schemas.BehaviorPageStatItem] = []
    for page in TRACKED_PAGE_PATHS:
        q = db.query(func.count(models.BehaviorEvent.id)).filter(
            models.BehaviorEvent.event_type == "page_view",
            _page_view_path_filter(path_expr, page),
        )
        if since is not None:
            q = q.filter(models.BehaviorEvent.occurred_at >= since)
        pages.append(
            schemas.BehaviorPageStatItem(path=page, visit_count=q.scalar() or 0)
        )

    return schemas.BehaviorPageStatsResponse(pages=pages)
