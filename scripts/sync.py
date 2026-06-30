"""
DB users → Redis 동기화 스크립트.

POST /auth/accounts/redis-rebuild 와 동일한 로직:
  1. plan:{account_id}:*, account:{account_id} 삭제
  2. DB(user, 활성 api_keys, user_api_plans) 기준으로 Redis 재기록

실행 (프로젝트 루트):
  python scripts/sync.py
  python scripts/sync.py --dry-run
  python scripts/sync.py --min-id 20
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

DEFAULT_REDIS_URL = "redis://192.168.1.20:6379"
if not os.getenv("REDIS_URL"):
    os.environ["REDIS_URL"] = DEFAULT_REDIS_URL

from sqlalchemy.orm import Session, joinedload

from app import models, redis_client
from app.database import SessionLocal

DEFAULT_MIN_ID = 20

# apis.id -> apis.slug (public.apis 기준)
API_SLUG_BY_ID: dict[int, str] = {
    1: "llm",
    2: "embedding",
    3: "reranker",
    4: "tts",
    5: "stt",
    6: "voiceclone",
    7: "copywrite",
    8: "summary",
    9: "sentiment",
    10: "ner",
    11: "sql",
    12: "ocr",
    13: "image",
    14: "music",
}


def resolve_api_slug(api_id: int, db_slug: str | None) -> str:
    if api_id in API_SLUG_BY_ID:
        return API_SLUG_BY_ID[api_id]
    if db_slug and db_slug.strip():
        return db_slug.strip()
    return str(api_id)


def rebuild_user_redis(db: Session, user: models.User) -> tuple[bool, int]:
    """단일 유저 Redis 재동기화. (account_meta_refreshed, plans_written) 반환."""
    if not redis_client.delete_all_account_redis_keys(user.id):
        raise RuntimeError("Redis 키 삭제 실패")

    latest_key = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == user.id, models.ApiKey.is_active.is_(True))
        .order_by(models.ApiKey.created_at.desc(), models.ApiKey.id.desc())
        .first()
    )

    account_meta_refreshed = False
    if latest_key:
        account_meta_refreshed = redis_client.set_account_meta(
            account_id=user.id,
            approved=user.is_approved,
            token=latest_key.key,
        )

    uaps = (
        db.query(models.UserApiPlan)
        .options(joinedload(models.UserApiPlan.api), joinedload(models.UserApiPlan.plan))
        .filter(models.UserApiPlan.user_id == user.id)
        .all()
    )

    plans_written = 0
    for uap in uaps:
        api_slug = resolve_api_slug(uap.api_id, uap.api.slug)
        if redis_client.set_plan_for_account_api(
            account_id=user.id,
            api_id=uap.api_id,
            api_slug_name=api_slug,
            max_rps=uap.plan.max_rps,
            max_ip_count=getattr(uap.plan, "max_ip_count", 0),
            plan_id=uap.plan_id,
            plan_name=uap.plan.name,
        ):
            plans_written += 1

    return account_meta_refreshed, plans_written


def sync_users(db: Session, *, min_id: int = DEFAULT_MIN_ID, dry_run: bool = False) -> None:
    redis_url = os.getenv("REDIS_URL", DEFAULT_REDIS_URL)
    if redis_client.get_redis() is None and not dry_run:
        print(f"오류: Redis 연결 실패 ({redis_url})")
        sys.exit(1)
    if not dry_run:
        print(f"Redis: {redis_url}")

    users = (
        db.query(models.User)
        .filter(models.User.id >= min_id)
        .order_by(models.User.id)
        .all()
    )

    if not users:
        print(f"id >= {min_id} 인 유저가 없습니다.")
        return

    synced = skipped = errors = 0

    for user in users:
        label = f"id={user.id} {user.email}"
        if dry_run:
            print(f"[DRY] {label}")
            synced += 1
            continue

        try:
            meta_ok, plans = rebuild_user_redis(db, user)
            print(f"[OK] {label} -> account_meta={meta_ok}, plans={plans}")
            synced += 1
        except Exception as exc:
            print(f"[ERROR] {label}: {exc}")
            errors += 1

    print(f"\n완료: 동기화={synced}, 건너뜀={skipped}, 오류={errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DB users → Redis 동기화")
    parser.add_argument(
        "--min-id",
        type=int,
        default=DEFAULT_MIN_ID,
        help=f"동기화할 최소 user id (기본: {DEFAULT_MIN_ID})",
    )
    parser.add_argument("--dry-run", action="store_true", help="대상 유저만 출력, Redis에 쓰지 않음")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        sync_users(db, min_id=args.min_id, dry_run=args.dry_run)
    finally:
        db.close()


if __name__ == "__main__":
    main()
