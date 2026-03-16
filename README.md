# GPU Rent API Server

FastAPI와 PostgreSQL을 사용한 회원가입 및 로그인 기능을 제공하는 API 서버입니다.

## 설치 방법

1. 가상환경 생성 및 활성화:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

2. 의존성 설치:
```bash
pip install -r requirements.txt
```

3. PostgreSQL 데이터베이스 생성:
```sql
CREATE DATABASE gpurent;
```

4. 환경변수 설정:
`.env` 파일을 생성하고 다음 내용을 추가하세요 (`.env.example` 파일을 참고):
```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=gpurent
SECRET_KEY=your-secret-key-change-this-in-production
```

또는 `DATABASE_URL`을 직접 사용할 수도 있습니다:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/gpurent
SECRET_KEY=your-secret-key-change-this-in-production
```

## 실행 방법

```bash
uvicorn app.main:app --reload
```

서버가 실행되면 http://localhost:8000 에서 API를 사용할 수 있습니다.

API 문서는 다음 주소에서 확인할 수 있습니다:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 엔드포인트

### 회원가입
- **POST** `/auth/signup`
- Request Body:
```json
{
  "email": "user@example.com",
  "username": "username",
  "password": "password123"
}
```

### 로그인
- **POST** `/auth/login` (OAuth2 형식)
- **POST** `/auth/login/email` (이메일/비밀번호 형식)
- Request Body (login/email):
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

### 현재 사용자 정보 조회
- **GET** `/auth/me`
- Header에 Bearer 토큰 필요: `Authorization: Bearer <token>`

## 보안 주의사항

- 운영 환경에서는 반드시 `SECRET_KEY`를 환경변수로 관리하세요
- 데이터베이스 비밀번호를 안전하게 관리하세요
- HTTPS를 사용하세요
