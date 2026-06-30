import base64
import logging
import os
from email.mime.text import MIMEText
from functools import lru_cache
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", "gmail_token.json")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
FRONTEND_RESET_URL = os.getenv(
    "FRONTEND_RESET_URL",
    "https://aiapi.kogrobo.com/auth/reset-password",
)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _load_credentials() -> Optional[Credentials]:
    if not os.path.isfile(GMAIL_TOKEN_FILE) or not EMAIL_FROM:
        return None
    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_FILE, GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(GMAIL_TOKEN_FILE, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())
    return creds


@lru_cache(maxsize=1)
def _get_gmail_service():
    creds = _load_credentials()
    if creds is None:
        return None
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def send_plain_email(to_email: str, subject: str, body: str) -> bool:
    """Gmail API로 일반 텍스트 메일 발송."""
    service = _get_gmail_service()
    if service is None:
        logger.error(
            "Gmail API is not configured (GMAIL_TOKEN_FILE, EMAIL_FROM required)"
        )
        return False

    message = MIMEText(body, "plain", "utf-8")
    message["To"] = to_email
    message["From"] = EMAIL_FROM
    message["Subject"] = subject
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()

    try:
        service.users().messages().send(
            userId="me",
            body={"raw": encoded},
        ).execute()
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def send_password_reset_email(to_email: str, plain_token: str) -> bool:
    """Gmail API로 비밀번호 재설정 메일 발송"""
    service = _get_gmail_service()
    if service is None:
        logger.error(
            "Gmail API is not configured (GMAIL_TOKEN_FILE, EMAIL_FROM required)"
        )
        return False

    reset_url = f"{FRONTEND_RESET_URL}?token={plain_token}"
    subject = "비밀번호 재설정"
    body = (
        "비밀번호 재설정 요청이 접수되었습니다.\n"
        "아래 링크를 클릭해 새 비밀번호를 설정해주세요.\n"
        f"{reset_url}\n"
        "이 링크는 30분 동안만 유효합니다.\n"
        "본인이 요청하지 않았다면 이 메일을 무시해주세요."
    )

    message = MIMEText(body, "plain", "utf-8")
    message["To"] = to_email
    message["From"] = EMAIL_FROM
    message["Subject"] = subject
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()

    try:
        service.users().messages().send(
            userId="me",
            body={"raw": encoded},
        ).execute()
        return True
    except Exception:
        logger.exception("Failed to send password reset email to %s", to_email)
        return False
