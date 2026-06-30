"""
스프레드시트 신청자 일괄 등록 스크립트.

users, api_keys, user_api_plans 테이블에 데이터를 삽입합니다.
비밀번호는 모두 '20260701!' (bcrypt 해시)로 통일합니다.

실행 (프로젝트 루트):
  python scripts/register_user.py
  python scripts/register_user.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session, joinedload

from app import auth, models, redis_client
from app.database import SessionLocal

DEFAULT_PASSWORD = "20260701!"

# (솔루션명, 월 가격) -> (api_id, plan_id)
# api: 1=LLM, 2=Embedding, 3=Reranker, 4=TTS, 5=STT, 6=VoiceClone,
#      12=Vision OCR, 13=Image Generation, 14=Music Generation
PLAN_MAP: dict[tuple[str, int], tuple[int, int]] = {
    # LLM
    ("대규모 언어 모델(LLM)", 150_000): (1, 1),   # Starter
    ("대규모 언어 모델(LLM)", 450_000): (1, 2),   # Pro
    ("대규모 언어 모델(LLM)", 0): (1, 3),         # Enterprise

    # Embedding
    ("텍스트 임베딩(Embedding)", 20_000): (2, 4),  # Starter
    ("텍스트 임베딩(Embedding)", 60_000): (2, 5),  # Pro
    ("텍스트 임베딩(Embedding)", 0): (2, 6),       # Enterprise

    # Reranker
    ("문장 재순위(Reranking)", 30_000): (3, 7),    # Starter
    ("문장 재순위(Reranking)", 90_000): (3, 8),    # Pro
    ("문장 재순위(Reranking)", 0): (3, 9),         # Enterprise

    # TTS
    ("텍스트를 음성으로 변환(TTS)", 30_000): (4, 10),  # Starter
    ("텍스트를 음성으로 변환(TTS)", 90_000): (4, 11),  # Pro
    ("텍스트를 음성으로 변환(TTS)", 0): (4, 12),       # Enterprise

    # STT
    ("음성을 텍스트로 변환(STT)", 30_000): (5, 13),  # Starter
    ("음성을 텍스트로 변환(STT)", 90_000): (5, 14),  # Pro
    ("음성을 텍스트로 변환(STT)", 0): (5, 15),       # Enterprise

    # Voice Clone
    ("목소리 복제(Voice Clone)", 30_000): (6, 16),  # Starter
    ("목소리 복제(Voice Clone)", 90_000): (6, 17),  # Pro
    ("목소리 복제(Voice Clone)", 0): (6, 18),       # Enterprise

    # Vision OCR / Image-to-Text
    ("이미지를 문장으로 변환(Image-to-Text)", 80_000): (12, 37),   # Starter
    ("이미지를 문장으로 변환(Image-to-Text)", 240_000): (12, 38),  # Pro
    ("이미지를 문장으로 변환(Image-to-Text)", 0): (12, 39),        # Enterprise

    # Image Generation
    ("이미지 생성(Image Generation)", 100_000): (13, 40),  # Starter
    ("이미지 생성(Image Generation)", 300_000): (13, 41),  # Pro
    ("이미지 생성(Image Generation)", 0): (13, 42),        # Enterprise

    # Music Generation
    ("문장을 음악으로 변환(Text-to-Music)", 50_000): (14, 43),   # Starter
    ("문장을 음악으로 변환(Text-to-Music)", 180_000): (14, 44),  # Pro
    ("문장을 음악으로 변환(Text-to-Music)", 0): (14, 45),        # Enterprise
}

# email, username(닉네임), subscriptions: [(솔루션명, 가격), ...]
USERS: list[dict] = [
    {"email": "kohsangbaek@naver.com", "username": "고상백", "subscriptions": [("이미지를 문장으로 변환(Image-to-Text)", 240_000)]},
    {"email": "osyang45@gmail.com", "username": "양오석", "subscriptions": [("대규모 언어 모델(LLM)", 450_000)]},
    {"email": "goodeye2001@naver.com", "username": "해피아이", "subscriptions": [("목소리 복제(Voice Clone)", 90_000)]},
    {"email": "namyeogi@naver.com", "username": "남쪽자작", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "goldenboyhhd21@gmail.com", "username": "goldenboy", "subscriptions": [
        ("음성을 텍스트로 변환(STT)", 90_000),
        ("텍스트를 음성으로 변환(TTS)", 90_000),
        ("대규모 언어 모델(LLM)", 450_000),
    ]},
    {"email": "08doyun@naver.com", "username": "kakilla", "subscriptions": [("텍스트를 음성으로 변환(TTS)", 90_000)]},
    {"email": "fsxking77@naver.com", "username": "매트님", "subscriptions": [
        ("텍스트 임베딩(Embedding)", 60_000),
        ("대규모 언어 모델(LLM)", 450_000),
    ]},
    {"email": "kimdan2@nate.com", "username": "미츠하시", "subscriptions": [("이미지를 문장으로 변환(Image-to-Text)", 240_000)]},
    {"email": "dlwhdals1399@naver.com", "username": "서비서", "subscriptions": [("텍스트를 음성으로 변환(TTS)", 90_000)]},
    {"email": "magic_eia@kakao.com", "username": "슬래시", "subscriptions": [
        ("음성을 텍스트로 변환(STT)", 90_000),
        ("텍스트 임베딩(Embedding)", 60_000),
    ]},
    {"email": "dongmin7575@naver.com", "username": "윤동민", "subscriptions": [
        ("음성을 텍스트로 변환(STT)", 90_000),
        ("텍스트를 음성으로 변환(TTS)", 90_000),
    ]},
    {"email": "lsupertopl@naver.com", "username": "프로슈머", "subscriptions": [("대규모 언어 모델(LLM)", 450_000)]},
    {"email": "ilustrated@kakao.com", "username": "아이보리15", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "dudhksl@naver.com", "username": "윤여완", "subscriptions": [("대규모 언어 모델(LLM)", 450_000)]},
    {"email": "xprren@gmail.com", "username": "엑시", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "dlaxoals1106@naver.com", "username": "임태민", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "umtelex@naver.com", "username": "aidbwiki", "subscriptions": [
        ("대규모 언어 모델(LLM)", 450_000),
        ("텍스트 임베딩(Embedding)", 60_000),
        ("문장 재순위(Reranking)", 90_000),
    ]},
    {"email": "casex@naver.com", "username": "crossover_moon", "subscriptions": [("텍스트를 음성으로 변환(TTS)", 90_000)]},
    {"email": "soonecally@kakao.com", "username": "김군순", "subscriptions": [("대규모 언어 모델(LLM)", 450_000)]},
    {"email": "wonjung815@naver.com", "username": "챙이똥이", "subscriptions": [
        ("음성을 텍스트로 변환(STT)", 90_000),
        ("텍스트를 음성으로 변환(TTS)", 90_000),
        ("목소리 복제(Voice Clone)", 90_000),
        ("문장을 음악으로 변환(Text-to-Music)", 180_000),
    ]},
    {"email": "chulpjssung@naver.com", "username": "pjssung", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "talkingo@hotmail.com", "username": "고본석", "subscriptions": [("대규모 언어 모델(LLM)", 450_000)]},
    {"email": "celina0822@naver.com", "username": "똑또기", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "temp131130@naver.com", "username": "로랍틱", "subscriptions": [("이미지 생성(Image Generation)", 300_000)]},
    {"email": "wlghtnwl@nate.com", "username": "안지호", "subscriptions": [("대규모 언어 모델(LLM)", 450_000)]},
    {"email": "kmlim5122@naver.com", "username": "without_임규민", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "dudgjs4248@naver.com", "username": "김영헌_", "subscriptions": [("이미지를 문장으로 변환(Image-to-Text)", 240_000)]},
    {"email": "lsunwoo2207@naver.com", "username": "떠두로", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "ykpark68@gmail.com", "username": "밥아자씨", "subscriptions": [("텍스트를 음성으로 변환(TTS)", 90_000)]},
    {"email": "luke7574@naver.com", "username": "박문욱", "subscriptions": [
        ("텍스트 임베딩(Embedding)", 60_000),
        ("음성을 텍스트로 변환(STT)", 90_000),
        ("텍스트를 음성으로 변환(TTS)", 90_000),
    ]},
    {"email": "qkrdmlwhd10@nate.com", "username": "sentia", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "klsej2468@naver.com", "username": "에몽", "subscriptions": [
        ("음성을 텍스트로 변환(STT)", 90_000),
        ("텍스트 임베딩(Embedding)", 60_000),
        ("문장 재순위(Reranking)", 90_000),
    ]},
    {"email": "cinnamonflavor@kakao.com", "username": "cinnamon", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "luvsh0@naver.com", "username": "ophtheon", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "khy9941@hanmail.net", "username": "sotera", "subscriptions": [
        ("음성을 텍스트로 변환(STT)", 90_000),
        ("텍스트를 음성으로 변환(TTS)", 90_000),
    ]},
    {"email": "tak1933@hanmail.net", "username": "김.영.탁", "subscriptions": [("대규모 언어 모델(LLM)", 450_000)]},
    {"email": "whdrbs3300@naver.com", "username": "김종균", "subscriptions": [("이미지 생성(Image Generation)", 300_000)]},
    {"email": "ckstn9896@hanmail.net", "username": "김찬수", "subscriptions": [("텍스트 임베딩(Embedding)", 60_000)]},
    {"email": "yeon97@gmail.com", "username": "말벗", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "chenjingjun89@gmail.com", "username": "진경군", "subscriptions": [("대규모 언어 모델(LLM)", 450_000)]},
    {"email": "joeun0614@gmail.com", "username": "트리플리", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "7101ehdus@naver.com", "username": "포르코", "subscriptions": [
        ("텍스트 임베딩(Embedding)", 60_000),
        ("문장 재순위(Reranking)", 90_000),
    ]},
    {"email": "josh.hwang1@gmail.com", "username": "황코치파이팅", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "mmtsd@naver.com", "username": "타로랩스", "subscriptions": [("대규모 언어 모델(LLM)", 450_000)]},
    {"email": "justpis@naver.com", "username": "damien", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "kimyeongseok@kakao.com", "username": "와츠인", "subscriptions": [
        ("텍스트 임베딩(Embedding)", 60_000),
        ("문장 재순위(Reranking)", 90_000),
    ]},
    {"email": "multi618@gmail.com", "username": "시중", "subscriptions": [
        ("음성을 텍스트로 변환(STT)", 90_000),
        ("대규모 언어 모델(LLM)", 450_000),
    ]},
    {"email": "cat4510@kakao.com", "username": "로보메타핏", "subscriptions": [("대규모 언어 모델(LLM)", 450_000)]},
    {"email": "tlsfldks@naver.com", "username": "류소나", "subscriptions": [
        ("음성을 텍스트로 변환(STT)", 90_000),
        ("텍스트를 음성으로 변환(TTS)", 90_000),
    ]},
    {"email": "kimjibin050716@daum.net", "username": "지빈", "subscriptions": [("텍스트를 음성으로 변환(TTS)", 90_000)]},
    {"email": "ena0939@naver.com", "username": "yina", "subscriptions": [("이미지를 문장으로 변환(Image-to-Text)", 240_000)]},
    {"email": "k0809s@gmail.com", "username": "luke4", "subscriptions": [
        ("목소리 복제(Voice Clone)", 90_000),
        ("이미지를 문장으로 변환(Image-to-Text)", 240_000),
    ]},
    {"email": "cantstop@hoseo.edu", "username": "cantstop", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "ahyean0726@naver.com", "username": "길재원", "subscriptions": [
        ("텍스트를 음성으로 변환(TTS)", 90_000),
        ("문장을 음악으로 변환(Text-to-Music)", 180_000),
    ]},
    {"email": "soosoo6@naver.com", "username": "밀레투스", "subscriptions": [
        ("음성을 텍스트로 변환(STT)", 90_000),
        ("텍스트를 음성으로 변환(TTS)", 90_000),
    ]},
    {"email": "l5soo@naver.com", "username": "주진명", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "99rain@hanmail.net", "username": "강옥선", "subscriptions": [("음성을 텍스트로 변환(STT)", 90_000)]},
    {"email": "ehc0503@hanmail.net", "username": "채은하", "subscriptions": [("이미지 생성(Image Generation)", 300_000)]},
    {"email": "aou8908@gmail.com", "username": "훈대표", "subscriptions": [("대규모 언어 모델(LLM)", 450_000)]},
    {"email": "seoun200517@naver.com", "username": "은채채", "subscriptions": [
        ("텍스트를 음성으로 변환(TTS)", 90_000),
    ]},
    {"email": "jackey117@naver.com", "username": "03황제영", "subscriptions": [
        ("이미지 생성(Image Generation)", 300_000),
    ]},
    {"email": "a33876935@gmail.com", "username": "문영재", "subscriptions": [
        ("음성을 텍스트로 변환(STT)", 90_000),
    ]},
    {"email": "jinseo8008@naver.com", "username": "플루처", "subscriptions": [
        ("대규모 언어 모델(LLM)", 450_000),
        ("음성을 텍스트로 변환(STT)", 90_000),
        ("이미지를 문장으로 변환(Image-to-Text)", 240_000),
        ("텍스트 임베딩(Embedding)", 60_000),
    ]},
    {"email": "yerim06072@naver.com", "username": "예림님", "subscriptions": [
        ("음성을 텍스트로 변환(STT)", 90_000),
    ]},
]


def resolve_plan(db: Session, solution: str, price: int) -> tuple[int, int]:
    key = (solution, price)
    if key in PLAN_MAP:
        return PLAN_MAP[key]

    raise ValueError(f"알 수 없는 솔루션/가격: {solution!r}, {price}")


def unique_username(db: Session, username: str, email: str) -> str:
    if not db.query(models.User).filter(models.User.username == username).first():
        return username

    local = email.split("@", 1)[0]
    if not db.query(models.User).filter(models.User.username == local).first():
        return local

    candidate = f"{username}_{local}"
    if not db.query(models.User).filter(models.User.username == candidate).first():
        return candidate

    for i in range(2, 100):
        candidate = f"{username}_{local}_{i}"
        if not db.query(models.User).filter(models.User.username == candidate).first():
            return candidate

    raise ValueError(f"고유 username을 만들 수 없습니다: {username!r}, {email!r}")


def sync_user_redis(db: Session, user: models.User) -> None:
    latest_key = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == user.id, models.ApiKey.is_active.is_(True))
        .order_by(models.ApiKey.created_at.desc(), models.ApiKey.id.desc())
        .first()
    )
    if latest_key:
        redis_client.set_account_meta(
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
    for uap in uaps:
        api_slug = (uap.api.slug or "").strip() or str(uap.api.id)
        redis_client.set_plan_for_account_api(
            account_id=user.id,
            api_id=uap.api_id,
            api_slug_name=api_slug,
            max_rps=uap.plan.max_rps,
            max_ip_count=getattr(uap.plan, "max_ip_count", 0),
            plan_id=uap.plan_id,
            plan_name=uap.plan.name,
        )


def register_users(db: Session, *, dry_run: bool = False, sync_redis: bool = True) -> None:
    hashed_password = auth.get_password_hash(DEFAULT_PASSWORD)
    created = skipped = errors = 0

    for entry in USERS:
        email = entry["email"]
        username = entry["username"]
        subscriptions = entry["subscriptions"]

        existing = auth.get_user_by_email(db, email)
        if existing:
            print(f"[SKIP] 이미 등록됨: {email}")
            skipped += 1
            continue

        try:
            username = unique_username(db, username, email)
            resolved_plans: list[tuple[int, int, str, int]] = []
            for solution, price in subscriptions:
                api_id, plan_id = resolve_plan(db, solution, price)
                resolved_plans.append((api_id, plan_id, solution, price))

            plan_summary = ", ".join(
                f"api={a} plan={p} ({s})" for a, p, s, _ in resolved_plans
            )
            print(f"[{'DRY' if dry_run else 'ADD'}] {email} ({username}) -> {plan_summary}")

            if dry_run:
                created += 1
                continue

            user = models.User(
                email=email,
                username=username,
                hashed_password=hashed_password,
                is_active=True,
                is_approved=True,
            )
            db.add(user)
            db.flush()

            api_key_jwt = auth.create_api_key_jwt(user.id)
            db.add(models.ApiKey(user_id=user.id, key=api_key_jwt))

            seen_api_ids: set[int] = set()
            for api_id, plan_id, _, _ in resolved_plans:
                if api_id in seen_api_ids:
                    print(f"  [WARN] 중복 api_id 무시: user={email}, api_id={api_id}")
                    continue
                seen_api_ids.add(api_id)
                db.add(models.UserApiPlan(user_id=user.id, api_id=api_id, plan_id=plan_id))

            db.commit()
            db.refresh(user)

            if sync_redis:
                sync_user_redis(db, user)

            created += 1
        except Exception as exc:
            db.rollback()
            print(f"[ERROR] {email}: {exc}")
            errors += 1

    print(f"\n완료: 생성={created}, 건너뜀={skipped}, 오류={errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="스프레드시트 신청자 일괄 등록")
    parser.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않고 매핑만 확인")
    parser.add_argument("--no-redis", action="store_true", help="Redis 동기화 생략")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        register_users(db, dry_run=args.dry_run, sync_redis=not args.no_redis)
    finally:
        db.close()


if __name__ == "__main__":
    main()
