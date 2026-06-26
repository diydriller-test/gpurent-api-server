"""
Gmail API 토큰 파일 발급 (최초 1회).

사전 준비:
1. Google Cloud Console에서 Gmail API 활성화
2. OAuth 클라이언트 ID(데스크톱 앱) 생성 후 credentials.json 다운로드
3. pip install google-auth-oauthlib

실행:
  python scripts/get_gmail_refresh_token.py
  python scripts/get_gmail_refresh_token.py credentials.json gmail_token.json
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def main() -> None:
    secrets_file = sys.argv[1] if len(sys.argv) > 1 else "credentials.json"
    token_file = sys.argv[2] if len(sys.argv) > 2 else "gmail_token.json"
    flow = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)
    creds = flow.run_local_server(port=9080)
    with open(token_file, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print(f"\n토큰 파일 저장: {token_file}")
    print("\n.env에 추가하세요:")
    print(f"GMAIL_TOKEN_FILE={token_file}")
    print("EMAIL_FROM=발신용@gmail.com")


if __name__ == "__main__":
    main()
