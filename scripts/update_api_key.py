"""
기존 유저 API key 재발급 및 Redis 계정 동기화.

POST /auth/api-keys 와 동일하게 기존 키를 비활성화한 뒤 새 JWT를 발급하고,
scripts/sync.py 와 동일하게 account/plan Redis 키를 재기록합니다.

실행 (프로젝트 루트):
  python scripts/update_api_key.py
  python scripts/update_api_key.py --dry-run
  python scripts/update_api_key.py --min-id 20
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

from app import auth, models, redis_client
from app.database import SessionLocal

DEFAULT_MIN_ID = 1


def reissue_api_key(db: Session, user: models.User) -> str:
    """기존 키 비활성화 후 새 API key JWT 발급."""
    db.query(models.ApiKey).filter(
        models.ApiKey.user_id == user.id,
    ).update({"is_active": False}, synchronize_session=False)
    api_key_jwt = auth.create_api_key_jwt(user.id)
    db.add(
        models.ApiKey(
            user_id=user.id,
            key=api_key_jwt,
            is_active=True,
        )
    )
    db.commit()
    return api_key_jwt


def sync_user_redis(db: Session, user: models.User) -> tuple[bool, int]:
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
        api_slug = (uap.api.slug or "").strip() or str(uap.api.id)
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


def update_api_keys(
    db: Session,
    *,
    min_id: int = DEFAULT_MIN_ID,
    dry_run: bool = False,
    sync_redis: bool = True,
) -> None:
    redis_url = os.getenv("REDIS_URL", DEFAULT_REDIS_URL)
    if sync_redis and redis_client.get_redis() is None and not dry_run:
        print(f"오류: Redis 연결 실패 ({redis_url})")
        sys.exit(1)
    if sync_redis and not dry_run:
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

    updated = errors = 0

    for user in users:
        label = f"id={user.id} {user.email}"
        if dry_run:
            print(f"[DRY] {label}")
            updated += 1
            continue

        try:
            reissue_api_key(db, user)
            meta_ok = False
            plans = 0
            if sync_redis:
                meta_ok, plans = sync_user_redis(db, user)
            print(f"[OK] {label} -> account_meta={meta_ok}, plans={plans}")
            updated += 1
        except Exception as exc:
            db.rollback()
            print(f"[ERROR] {label}: {exc}")
            errors += 1

    print(f"\n완료: 재발급={updated}, 오류={errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="기존 유저 API key 재발급 및 Redis 동기화")
    parser.add_argument(
        "--min-id",
        type=int,
        default=DEFAULT_MIN_ID,
        help=f"대상 최소 user id (기본: {DEFAULT_MIN_ID})",
    )
    parser.add_argument("--dry-run", action="store_true", help="대상 유저만 출력, DB/Redis에 쓰지 않음")
    parser.add_argument("--no-redis", action="store_true", help="Redis 동기화 생략")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        update_api_keys(
            db,
            min_id=args.min_id,
            dry_run=args.dry_run,
            sync_redis=not args.no_redis,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
