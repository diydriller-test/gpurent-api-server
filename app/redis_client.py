"""
게이트웨이와 공유하는 Redis 클라이언트.
- API별 플랜: plan:{account_id}:{api_name}
- 계정 메타(API 키 승인·버전): account:{account_id}
"""
import json
import os
from typing import Optional

try:
    import redis
except ImportError:
    redis = None  # type: ignore

_REDIS_CLIENT: Optional["redis.Redis"] = None


def get_redis_url() -> Optional[str]:
    """REDIS_URL 환경변수. 예: redis://localhost:6379/0"""
    return os.getenv("REDIS_URL")


def get_redis():
    """Redis 클라이언트 (설정 없거나 연결 실패 시 None)."""
    global _REDIS_CLIENT
    if redis is None:
        return None
    url = get_redis_url()
    if not url:
        return None
    if _REDIS_CLIENT is None:
        try:
            _REDIS_CLIENT = redis.from_url(url, decode_responses=True)
        except Exception:
            return None
    return _REDIS_CLIENT


def set_plan_for_account_api(
    account_id: int,
    api_id: int,
    api_name: str,
    max_rps: int,
    plan_id: int,
    plan_name: str,
) -> bool:
    """
    API별 플랜 정보를 Redis에 저장. 키: plan:{account_id}:{api_name_lower}
    값: {"max_rps": 50, "plan_id": 2, "plan_name": "Pro"}
    게이트웨이가 이 키를 읽어 API별 rate limit 등에 사용.
    """
    client = get_redis()
    if not client:
        return False
    key = f"plan:{account_id}:{api_name.lower()}"
    value = json.dumps({
        "max_rps": max_rps,
        "api_name": api_name,
        "plan_id": plan_id,
        "plan_name": plan_name,
    }, ensure_ascii=False)
    try:
        client.set(key, value)
        return True
    except Exception:
        return False


def set_account_meta(
    account_id: int,
    approved: bool,
    token_version: int,
) -> bool:
    """
    계정별 API 키 메타 저장. 키: account:{account_id}
    값: {"account_id", "approved", "token_version"} (현재 발급분 기준)
    """
    client = get_redis()
    if not client:
        return False
    key = f"account:{account_id}"
    value = json.dumps(
        {
            "account_id": account_id,
            "approved": approved,
            "token_version": token_version,
        },
        ensure_ascii=False,
    )
    try:
        client.set(key, value)
        return True
    except Exception:
        return False


def delete_account_meta(account_id: int) -> bool:
    """account:{account_id} 키 제거 (API 키 전부 삭제 시 등)."""
    client = get_redis()
    if not client:
        return False
    try:
        client.delete(f"account:{account_id}")
        return True
    except Exception:
        return False
