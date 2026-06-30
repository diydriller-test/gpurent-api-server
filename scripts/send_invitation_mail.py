"""
구매 확인 및 계정·API 키 안내 메일 일괄 발송.

register_user.py USERS 목록의 이메일 대상으로 DB에서 계정·API 키를 조회해 발송합니다.

실행 (프로젝트 루트):
  python scripts/send_invitation_mail.py --dry-run
  python scripts/send_invitation_mail.py
  python scripts/send_invitation_mail.py --email user@example.com
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app import auth, email_service, models
from app.database import SessionLocal

SUBJECT = "[AI API 오마카세] 구매 확인 및 계정·API 키 안내"

BODY_TEMPLATE = """\
안녕하세요, {name}님.

AI API 오마카세를 구매해 주셔서 진심으로 감사드립니다.

아래는 {name}님의 계정 정보와 API 키입니다.

──────────────────────────────
아이디: {login_id}
비밀번호: {password}
API 키: {api_key}
──────────────────────────────

보안을 위해 비밀번호 찾기를 눌러 재설정해 주시기 바랍니다.

이용 중 문의 사항이 있으시면 언제든지 답장 주세요.

감사합니다.
AI API 오마카세 팀 드림
"""


def _load_register_user_module():
    path = ROOT / "scripts" / "register_user.py"
    spec = importlib.util.spec_from_file_location("register_user", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"register_user.py 를 불러올 수 없습니다: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_active_api_key(db, user_id: int) -> str | None:
    row = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == user_id, models.ApiKey.is_active.is_(True))
        .order_by(models.ApiKey.created_at.desc(), models.ApiKey.id.desc())
        .first()
    )
    return row.key if row else None


def build_body(*, name: str, login_id: str, password: str, api_key: str) -> str:
    return BODY_TEMPLATE.format(
        name=name,
        login_id=login_id,
        password=password,
        api_key=api_key,
    )


def send_invitations(
    *,
    dry_run: bool = False,
    only_email: str | None = None,
) -> None:
    register_user = _load_register_user_module()
    users_list = register_user.USERS
    default_password = register_user.DEFAULT_PASSWORD

    if only_email:
        users_list = [u for u in users_list if u["email"] == only_email]
        if not users_list:
            print(f"목록에 없는 이메일: {only_email}")
            sys.exit(1)

    sent = skipped = errors = 0
    db = SessionLocal()

    try:
        for entry in users_list:
            email = entry["email"]
            display_name = entry["username"]

            user = auth.get_user_by_email(db, email)
            if not user:
                print(f"[SKIP] DB에 없음: {email}")
                skipped += 1
                continue

            api_key = get_active_api_key(db, user.id)
            if not api_key:
                print(f"[SKIP] API 키 없음: {email}")
                skipped += 1
                continue

            body = build_body(
                name=display_name,
                login_id=email,
                password=default_password,
                api_key=api_key,
            )

            if dry_run:
                print(f"[DRY] {email} ({display_name})")
                print(f"  subject: {SUBJECT}")
                print(f"  body preview: 아이디={email}, api_key={api_key[:20]}...")
                sent += 1
                continue

            if email_service.send_plain_email(email, SUBJECT, body):
                print(f"[SENT] {email} ({display_name})")
                sent += 1
            else:
                print(f"[ERROR] 발송 실패: {email}")
                errors += 1
    finally:
        db.close()

    print(f"\n완료: 발송={sent}, 건너뜀={skipped}, 오류={errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="구매 확인·계정 안내 메일 발송")
    parser.add_argument("--dry-run", action="store_true", help="발송 없이 대상·내용만 확인")
    parser.add_argument("--email", help="특정 이메일 1명만 발송")
    args = parser.parse_args()

    send_invitations(dry_run=args.dry_run, only_email=args.email)


if __name__ == "__main__":
    main()
