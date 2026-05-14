-- PostgreSQL: 행동 분석 수집 테이블
-- 기본 수신 경로: POST /analytics/behavior (환경변수 INTERNAL_ANALYTICS_PATH 로 변경 가능)
--
-- 이미 behavior_events 가 있는 경우: 아래 "마이그레이션" 블록만 실행.

-- ---------------------------------------------------------------------------
-- 신규 설치 (테이블 없을 때)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS behavior_events (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NULL REFERENCES users (id),
    client_ip       VARCHAR(45) NULL,
    event_type      VARCHAR(20) NOT NULL,
    element_dom_type VARCHAR(50) NULL,
    name            VARCHAR(500) NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL,
    properties      JSONB NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_behavior_events_user_id ON behavior_events (user_id);
CREATE INDEX IF NOT EXISTS ix_behavior_events_event_type ON behavior_events (event_type);
CREATE INDEX IF NOT EXISTS ix_behavior_events_occurred_at ON behavior_events (occurred_at);
CREATE INDEX IF NOT EXISTS ix_behavior_events_element_dom_type ON behavior_events (element_dom_type);

-- 선택: 이벤트 최상위 type 과 구분된 DOM 타입만 강제 (element_click 일 때)
-- ALTER TABLE behavior_events
--   ADD CONSTRAINT ck_behavior_events_event_type
--   CHECK (event_type IN ('page_view', 'element_click', 'custom'));

-- ---------------------------------------------------------------------------
-- 마이그레이션: 구 스키마에 element_dom_type 컬럼이 없을 때
-- ---------------------------------------------------------------------------
-- ALTER TABLE behavior_events
--   ADD COLUMN IF NOT EXISTS element_dom_type VARCHAR(50) NULL;
-- CREATE INDEX IF NOT EXISTS ix_behavior_events_element_dom_type
--   ON behavior_events (element_dom_type);
--
-- 기존 element_click 행에서 properties->>'type' 으로 백필 (선택)
-- UPDATE behavior_events
-- SET element_dom_type = LEFT(properties->>'type', 50)
-- WHERE event_type = 'element_click'
--   AND element_dom_type IS NULL
--   AND properties ? 'type';
