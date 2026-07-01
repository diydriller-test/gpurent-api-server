"""
API 키 정정 안내 메일 일괄 발송.

id >= 20 유저 대상으로 DB의 활성 API key(is_active=True)를 조회해 발송합니다.

실행 (프로젝트 루트):
  python scripts/send_mail.py --dry-run
  python scripts/send_mail.py
  python scripts/send_mail.py --email user@example.com
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app import email_service, models
from app.database import SessionLocal

DEFAULT_MIN_ID = 20

SUBJECT = "[AI API 오마카세] API 키 정정 안내"

BODY_TEMPLATE = """\
안녕하세요, {name}님.

AI API 오마카세 운영팀입니다.

앞서 보내드린 구매 확인 및 계정 안내 메일에서 API 키 정보가 잘못 기재되어 다시 안내드립니다. 이용에 혼선을 드려 죄송합니다.

아래 정정된 API 키를 사용해 주시기 바랍니다.

──────────────────────────────
정정된 API 키: {api_key}
──────────────────────────────

기존에 전달드린 API 키는 사용하지 마시고, 반드시 위의 정정된 API 키로 이용해 주시기 바랍니다.

또한 보안을 위해 로그인 후 비밀번호 찾기 또는 비밀번호 재설정 기능을 통해 비밀번호를 변경해 주시기 바랍니다.

이용 중 문의 사항이 있으시면 언제든지 본 메일로 답장 주세요.

감사합니다.
AI API 오마카세 운영팀 드림
"""


def get_active_api_key(db, user_id: int) -> str | None:
    row = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == user_id, models.ApiKey.is_active.is_(True))
        .order_by(models.ApiKey.created_at.desc(), models.ApiKey.id.desc())
        .first()
    )
    return row.key if row else None


def build_body(*, name: str, api_key: str) -> str:
    return BODY_TEMPLATE.format(name=name, api_key=api_key)


def send_correction_mails(
    *,
    min_id: int = DEFAULT_MIN_ID,
    dry_run: bool = False,
    only_email: str | None = None,
) -> None:
    sent = skipped = errors = 0
    db = SessionLocal()

    try:
        query = db.query(models.User).filter(models.User.id >= min_id).order_by(models.User.id)
        if only_email:
            query = query.filter(models.User.email == only_email)

        users = query.all()
        if only_email and not users:
            print(f"조건에 맞는 유저 없음: {only_email} (min_id >= {min_id})")
            sys.exit(1)

        if not users:
            print(f"id >= {min_id} 인 유저가 없습니다.")
            return

        for user in users:
            email = user.email
            display_name = user.username

            api_key = get_active_api_key(db, user.id)
            if not api_key:
                print(f"[SKIP] API 키 없음: id={user.id} {email}")
                skipped += 1
                continue

            body = build_body(name=display_name, api_key=api_key)

            if dry_run:
                print(f"[DRY] id={user.id} {email} ({display_name})")
                print(f"  subject: {SUBJECT}")
                print(f"  body preview: api_key={api_key[:20]}...")
                sent += 1
                continue

            if email_service.send_plain_email(email, SUBJECT, body):
                print(f"[SENT] id={user.id} {email} ({display_name})")
                sent += 1
            else:
                print(f"[ERROR] 발송 실패: id={user.id} {email}")
                errors += 1
    finally:
        db.close()

    print(f"\n완료: 발송={sent}, 건너뜀={skipped}, 오류={errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="API 키 정정 안내 메일 발송")
    parser.add_argument(
        "--min-id",
        type=int,
        default=DEFAULT_MIN_ID,
        help=f"대상 최소 user id (기본: {DEFAULT_MIN_ID})",
    )
    parser.add_argument("--dry-run", action="store_true", help="발송 없이 대상·내용만 확인")
    parser.add_argument("--email", help="특정 이메일 1명만 발송")
    args = parser.parse_args()

    send_correction_mails(
        min_id=args.min_id,
        dry_run=args.dry_run,
        only_email=args.email,
    )


if __name__ == "__main__":
    main()
