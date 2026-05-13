# WMS V2.0 — 전사 자재창고 통합 관리 시스템

## 기술 스택
- **앱**: Streamlit 1.35 (Python 3.11)
- **DB**: Supabase (PostgreSQL) — `utils/db.py`에서 `get_supabase()` 싱글턴
- **인증**: bcrypt 해싱 (`utils/auth.py`)
- **메일**: Gmail SMTP (`utils/mail.py`)
- **기타**: pandas, openpyxl

## 프로젝트 구조

```
wms_v2/
├── app.py                      # 진입점 — 로그인 여부로 라우팅
├── .streamlit/
│   ├── secrets.toml            # SUPABASE_URL, SUPABASE_KEY, GMAIL_ADDRESS, GMAIL_APP_PASSWORD
│   └── config.toml             # hideSidebarNav = true
├── pages/
│   ├── 01_login.py             # 로그인 / 회원가입 / 임시 비밀번호
│   ├── 02_warehouse.py         # 창고 재고 현황 (핵심 페이지)
│   ├── 03_transfers.py         # 센터 간 이동 신청 현황
│   ├── 04_history.py           # 전체 입출고 이력
│   ├── 05_admin.py             # 관리자 — 회원 승인·권한·삭제
│   ├── 06_mypage.py            # 마이페이지 — 정보·비밀번호 수정
│   ├── 07_material_requests.py # 자재 요청 관리
│   └── 08_usage_history.py     # 센터 사용내역 조회
└── utils/
    ├── auth.py                 # login, register, require_login, require_role, is_role
    ├── db.py                   # Supabase 쿼리 및 캐시 함수
    ├── mail.py                 # Gmail SMTP 메일 발송 함수
    ├── permissions.py          # RBAC 권한 계산 함수
    ├── routing.py              # CENTERS 목록, 센터 간 이동 경로
    └── ui.py                   # apply_global_css() — 전 페이지 공통 CSS
```

## DB 테이블

### `users`
```
id(uuid), username, password_hash, name, email, phone,
center, assigned_center, role, is_approved
```

### `warehouse`
```
id, item_name, quantity, rack_no, shelf, box_no,
category_large, category_mid, category_small,
location(센터), erp_name, erp_code,
repair_manager, item_location(지역), notes,
last_modified_by → users(ON DELETE SET NULL),
last_modified_at
```

### `transfers`
```
id, requester_id → users(ON DELETE SET NULL),
item_id → warehouse(ON DELETE SET NULL),
from_center, to_center, quantity,
status(pending/approved/rejected/cancelled),
requested_at, processed_at
```

### `history`
```
id, actor_id → users(ON DELETE SET NULL),
item_id → warehouse(ON DELETE SET NULL),
action_type(in/out/transfer/edit),
quantity, reason, from_center, to_center,
snapshot_qty_before, snapshot_qty_after, acted_at
```

### `material_requests`
```
id, requester_id → users(ON DELETE SET NULL),
requester_name, requester_email, from_center,
status(pending/approved/rejected/on_hold/cancelled),
items(JSONB), requested_at, processed_at,
processed_by → users(ON DELETE SET NULL),
reply_message
```

> **모든 FK는 ON DELETE SET NULL 적용** — 계정·자재 삭제 시 참조 자동 NULL 처리

## 역할(Role) 권한 체계

| 역할 | 입고/출고 | 사용내역 업로드 | 이동 신청 | 이동 승인 | 자재 요청 | 자재요청 관리 |
|------|----------|--------------|----------|----------|----------|------------|
| admin | 전 센터 | 전 센터 | 전 센터 | 전체 | ✅ | ✅ |
| materials | 자재센터만 | ❌ | 자재센터만 | 자재센터 관련 | ❌ | ✅ |
| manager | ❌ | 본인 센터 | 본인 센터 | 본인 센터 수신 | ✅ | ❌ |
| user | ❌ | ❌ | 본인 센터 | ❌ | ✅ | ❌ |
| guest | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

## 센터 구성 (7개)

```python
CENTERS = ["자재센터", "강서센터", "강북센터", "강동센터", "강남센터", "택시지원파트", "리페어팀"]
```

**이동 경로 규칙**
- 자재센터 → 나머지 6개 전부
- 지역센터(강서·강북·강동·강남) → 자재센터 + 지역센터끼리
- 특수파트(택시지원·리페어) → 자재센터만

## 주요 기능 상세

### 02_warehouse.py (창고 관리)
- 대/중/소분류 필터, 자재명·ERP코드·분류명 검색
- 컬럼 헤더 클릭 정렬 (자재명·수량·대분류·중분류·소분류)
- 페이지네이션 (기본 20개씩, 20·50·100·200 선택)
- **자재명 클릭 → 상세 팝업**: 이력 조회(본인 센터) + 수정(admin 전용, 대/중/소분류 캐스케이딩 드롭다운)
- 체크박스 선택 → 일괄 입고/출고 (자재센터, admin·materials)
- **사용내역 업로드** (비자재센터, admin·manager): 자재명/ERP코드 매칭 → 수량 차감 → history 기록
- **자재 요청** (비자재센터, guest·materials 제외): 자재센터 재고 검색 → 장바구니 → 메일 발송 + DB 저장
- **내보내기** (admin): 다운로드만 / 삭제 포함(2단계 확인 → warehouse 레코드 삭제 + history 기록)

### 07_material_requests.py (자재 요청)
**관리자/자재파트 뷰**
- 승인 → 팝업(메일 작성) → 자재센터 수량 차감 + 요청센터 증가 + 이력 + 메일 발송
- 거절/보류 → 팝업(메일 작성) → 상태 변경 + 신청자 회신 메일
- 보류 → 대기중 되돌리기 가능

**센터 사용자 뷰**
- 본인 센터 요청 현황 읽기 전용
- 대기중 본인 요청 취소 → 취소 알림 메일 발송

### 08_usage_history.py (사용내역)
- admin·materials: 센터 선택 가능 / 그 외: 본인 센터 고정
- 기간 필터 (시작일~종료일, 기본 최근 30일)
- 자재명·담당자·사유 검색, 엑셀 다운로드

## 메일 발송 함수 (utils/mail.py)

| 함수 | 발송 대상 | 발송 시점 |
|------|----------|----------|
| `send_temp_password` | 신청자 | 비밀번호 찾기 |
| `send_transfer_request` | 담당자 | 이동 신청 |
| `send_material_request` | 자재파트 + 관리자 | 자재 요청 접수 |
| `send_material_request_approved_to_center` | 해당 센터 전체 인원 | 자재 요청 승인 |
| `send_material_request_reply` | 신청자 | 승인/거절/보류 처리 결과 |
| `send_material_request_cancelled` | 자재파트 + 관리자 | 자재 요청 취소 |

## UI/UX 규칙
- **ERP 스타일**: 사이드바 165px, 전체 폰트 12px, 버튼 높이 28~34px
- **사이드바 고정**: `initial_sidebar_state="expanded"` + CSS로 닫기 버튼 제거
- **영어 네비게이션 숨김**: `.streamlit/config.toml` → `hideSidebarNav = true`
- **스크롤**: `html, body, .main` overflow-y: auto 전 페이지 적용
- `apply_global_css()` — 02_warehouse.py 제외 모든 페이지에서 호출
- 02_warehouse.py는 자체 CSS 블록 보유 (동일 규칙 인라인 적용)

## 캐시 전략
- `fetch_warehouse`: TTL 60초
- `fetch_categories`: TTL 60초
- `fetch_transfers`: TTL 30초
- `fetch_history`: TTL 30초
- `fetch_material_requests`: TTL 30초
- `fetch_usage_history`: TTL 30초
- 데이터 변경 후 반드시 해당 `clear_*_cache()` 호출

## 개발 시 주의사항
- 센터 권한 체크는 항상 `utils/permissions.py`의 함수를 사용
- DB 직접 삭제 시 FK 참조 해제 순서: transfers → history → warehouse/users
- `@st.experimental_dialog` 사용 (Streamlit 1.35 기준)
- 다이얼로그 내 위젯 key는 `f"prefix_{item_id}_field"` 형태로 item별 고유하게
- 동일 페이지에서 같은 레이블+속성의 버튼이 여러 개면 반드시 `key` 명시
- 탭별로 반복 렌더링되는 위젯 key는 `f"{tab_key}_{item_id}"` 형태로 탭 구분
