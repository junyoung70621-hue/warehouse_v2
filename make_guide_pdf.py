"""
WMS v2 사용 가이드 PDF 생성 스크립트
실행: python make_guide_pdf.py
"""
from fpdf import FPDF

FONT_REG  = r"C:\Windows\Fonts\malgun.ttf"
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"

C_PRIMARY = (211,   0,  79)
C_BLUE    = (  2, 132, 199)
C_GREEN   = ( 22, 163,  74)
C_DARK    = ( 30,  41,  59)
C_GRAY    = (100, 116, 139)
C_LGRAY   = (241, 245, 249)
C_WHITE   = (255, 255, 255)
C_BORDER  = (226, 232, 240)

ROLE_COLORS = {
    "admin":     (211,   0,  79),
    "materials": ( 22, 163,  74),
    "manager":   (  2, 132, 199),
    "user":      (100, 116, 139),
    "guest":     (203, 213, 225),
}
ROLE_NAMES = {
    "admin":     "관리자 (admin)",
    "materials": "자재파트 (materials)",
    "manager":   "센터장 (manager)",
    "user":      "일반 사용자 (user)",
    "guest":     "게스트 (guest)",
}

# (기능, admin, materials, manager, user, guest)
FEATURE_MATRIX = [
    ("── 재고 현황 ──────────────────────────────",  None, None, None, None, None),
    ("재고 현황 조회",           True,  True,  True,  True,  True),
    ("자재 검색·필터·정렬",      True,  True,  True,  True,  True),
    ("KPI 카드 클릭 필터",       True,  True,  True,  True,  True),
    ("자재명 클릭 → 상세·이력",  True,  True,  True,  True,  False),
    ("재고 엑셀 다운로드",       True,  True,  True,  True,  False),
    ("자재 일괄 업로드 (엑셀)",  True,  True,  False, False, False),
    ("입고 / 출고",             True,  True,  False, False, False),
    ("사용내역 업로드",          True,  False, True,  False, False),
    ("자재 요청 신청",           True,  False, True,  True,  False),
    ("자재 수정 (상세 팝업)",    True,  False, False, False, False),
    ("전체 내보내기 (다운로드)", True,  False, False, False, False),
    ("데이터 삭제 (삭제 패널)",  True,  False, False, False, False),
    ("── 이동 신청 ──────────────────────────────", None, None, None, None, None),
    ("이동 신청",                True,  True,  True,  True,  False),
    ("이동 신청 승인·거절",      True,  True,  True,  False, False),
    ("이동 신청 취소 (본인)",    True,  True,  True,  True,  False),
    ("이동 신청 삭제",           True,  False, False, False, False),
    ("── 자재 요청 ──────────────────────────────", None, None, None, None, None),
    ("자재 요청 신청",           True,  False, True,  True,  False),
    ("자재 요청 승인·거절·보류", True,  True,  False, False, False),
    ("자재 요청 취소 (본인)",    True,  False, True,  True,  False),
    ("자재 요청 삭제",           True,  False, False, False, False),
    ("── 구매 요청 ──────────────────────────────", None, None, None, None, None),
    ("구매 요청 신청",           True,  False, True,  True,  False),
    ("구매 요청 관리 (상태 변경)", True, True,  False, False, False),
    ("구매 요청 취소 (본인)",    True,  False, True,  True,  False),
    ("구매 요청 삭제",           True,  False, False, False, False),
    ("── 기타 ───────────────────────────────────", None, None, None, None, None),
    ("입출고 이력 조회",         True,  True,  True,  True,  True),
    ("사용내역 조회",            True,  True,  True,  True,  False),
    ("단말기 대시보드 조회",     True,  True,  True,  True,  True),
    ("단말기 업로드",            True,  True,  False, False, False),
    ("단말기 관리 탭",           True,  False, False, False, False),
    ("회원 승인·권한·삭제",      True,  False, False, False, False),
    ("마이페이지",               True,  True,  True,  True,  True),
    ("문의하기",                 True,  True,  True,  True,  True),
]

PAGES = {
    "재고 현황 (02_warehouse.py)": [
        ("KPI 카드",       "총 SKU·부족재고·이동대기·재고없음 4개 카드. 클릭 시 해당 조건으로 목록 필터링."),
        ("검색·필터·정렬", "자재명·ERP코드·분류명·랙번호 통합 검색. 대/중/소분류 드롭다운 + 컬럼 클릭 정렬."),
        ("다운로드",       "현재 센터 재고 목록을 엑셀로 저장. 게스트 제외 사용 가능."),
        ("입고 / 출고",    "체크박스로 자재 선택 후 수량 입력 처리. 이력 자동 기록. admin·자재파트 전용."),
        ("엑셀 업로드",    "렉/단수/박스번호 기준으로 기존 row 매칭 → 수량 추가. 신규 위치는 새 row 등록. 500건 단위 청크 삽입으로 대용량 처리."),
        ("사용내역 업로드", "엑셀 업로드 → 자재명·ERP코드 매칭 → 수량 자동 차감. admin·센터장 전용."),
        ("자재 요청",      "자재센터 재고를 자재명 기준 합산 수량으로 표시. 선택 후 장바구니 담기 → 요청 발송. 자재파트·관리자에게 메일 발송."),
        ("이동 신청",      "재고 목록에서 자재 선택 후 대상 센터·수량 입력. 센터 이동 경로 규칙 적용."),
        ("[내보내기]",    "센터 선택 후 전체 데이터 엑셀 다운로드. admin 전용."),
        ("[삭제 패널]",   "센터 선택 → 삭제 전 백업 파일 생성 → 2단계 확인 후 전체 삭제. admin 전용."),
        ("자재 수정",      "자재명 클릭 → 상세 팝업에서 입출고 이력 조회 + 자재 정보 수정. 수정은 admin 전용."),
    ],
    "이동 신청 현황 (03_transfers.py)": [
        ("목록 조회",      "대기중·승인됨·거절됨·전체 탭 구분. 역할에 따라 본인 관련 신청만 표시."),
        ("자재센터→타센터 승인", "타센터 담당자(manager/admin)가 승인. 자재센터 수량 차감, 타센터 수량 증가."),
        ("타센터→자재센터 승인", "자재파트·admin이 승인 시 위치 지정 팝업 표시 → 렉/단수/박스 선택 또는 신규 위치 입력 후 확정."),
        ("거절",           "권한 있는 담당자만 거절 버튼 활성화."),
        ("취소",           "대기중인 본인 신청 건 취소 가능."),
        ("삭제",           "admin만 이동 신청 기록 완전 삭제 (2단계 확인)."),
    ],
    "입출고 이력 (04_history.py)": [
        ("이력 조회",      "전체 입고·출고·이동·수정 이력. 자재명·작업자·사유 검색 및 기간 필터."),
        ("엑셀 다운로드",  "필터 적용된 이력 엑셀 저장."),
    ],
    "자재 요청 (07_material_requests.py)": [
        ("요청 신청",      "자재센터 재고(합산 수량)에서 필요 자재 선택 → 요청. 자재파트·관리자에게 알림 메일."),
        ("승인",           "자재파트·admin이 승인 시 차감할 렉/단수/박스 row 선택 팝업 표시 → 자재센터 차감 + 요청센터 증가 + 양측 이력 기록 + 메일 발송."),
        ("거절 / 보류",    "자재파트·admin 처리. 메일 발송. 보류는 대기중으로 되돌리기 가능."),
        ("취소",           "대기중인 본인 요청 취소 → 자재파트·관리자에게 취소 알림 메일."),
        ("삭제",           "admin만 요청 기록 완전 삭제 (2단계 확인)."),
    ],
    "사용내역 (08_usage_history.py)": [
        ("조회",           "admin·자재파트: 센터 선택 가능. 그 외: 본인 센터 고정."),
        ("필터",           "기간(기본 최근 30일)·자재명·담당자·사유 검색."),
        ("엑셀 다운로드",  "필터된 사용내역 엑셀 저장."),
    ],
    "구매 요청 (11_purchase_requests.py)": [
        ("요청 작성",      "품명·수량·링크 입력, 구매사유·원가반영 필수. 60초 중복 방지."),
        ("메일 발송",      "제출 시 구매요청서 엑셀 첨부 → 관리자·자재파트·본인에게 자동 발송."),
        ("상태 관리",      "자재파트·admin이 대기중→처리중→완료·거절 순으로 상태 변경. 각 단계 메일 발송."),
        ("취소",           "대기중·처리중 상태 본인 취소 → 관련 인원 취소 메일."),
        ("삭제",           "admin만 구매 요청 기록 삭제 (2단계 확인)."),
    ],
    "단말기 대시보드 (14_terminal_dashboard.py)": [
        ("현황 조회",      "날짜별 출고·입고 수량, 단말기 기종×센터 크로스표 표시."),
        ("기종 분류",      "B800·B700·B710·B620·한강버스 자동 분류. 모뎀은 6자리 번호 대역 기준."),
        ("업로드",         "엑셀(.xls/.xlsx) 업로드 → 자동 분류·중복 제거 저장. 비고 입력 가능."),
        ("인수인계증",     "날짜·방향·센터 필터 후 Excel 인수인계증 생성 (비고란·로고·서명란 포함)."),
        ("관리 탭",        "기존 레코드 재분류 일괄 수정. admin 전용."),
    ],
    "관리자 (05_admin.py)": [
        ("회원 승인",      "신규 가입 요청 승인·거절. 승인 시 안내 메일 발송."),
        ("권한·센터 변경", "역할(role)·소속 센터 변경."),
        ("이름 변경",      "사원 이름 수정."),
        ("회원 삭제",      "관련 이력·신청 데이터 NULL 처리 후 계정 삭제."),
    ],
}

ROLE_GUIDE = {
    "admin": {
        "desc": "시스템 전체를 관리하는 최고 권한. 모든 센터 접근 가능.",
        "features": [
            "모든 센터 재고 조회·수정·입출고",
            "엑셀 일괄 업로드 (자재센터)",
            "전체 내보내기 및 데이터 삭제",
            "자재·이동·자재요청·구매요청 삭제",
            "자재 요청 승인·거절·보류 (차감 위치 선택)",
            "타→자재센터 이동 승인 (렉/단수/박스 지정)",
            "회원 관리 (승인·권한·삭제)",
            "단말기 관리 탭 (재분류)",
            "사용내역 조회 (전 센터 선택)",
        ],
        "caution": "고객지원사업부 소속 admin은 전체 내보내기·삭제 패널 사용 불가.",
    },
    "materials": {
        "desc": "자재센터 소속 자재파트. 자재센터 입출고 및 요청 관리 담당.",
        "features": [
            "자재센터 재고 입고·출고",
            "자재 일괄 엑셀 업로드",
            "자재 요청 승인·거절·보류 (차감 위치 선택)",
            "타→자재센터 이동 승인 (렉/단수/박스 지정)",
            "구매 요청 관리 (상태 변경·메일)",
            "단말기 업로드 (입고·출고)",
            "사용내역 조회 (전 센터 선택)",
        ],
        "caution": "재고 다운로드·내보내기·삭제·수정 불가. 자재 요청 신청 불가.",
    },
    "manager": {
        "desc": "각 센터의 센터장. 본인 센터 운영 관리 담당.",
        "features": [
            "본인 센터 사용내역 업로드 (재고 차감)",
            "본인 센터 수신 이동 신청 승인·거절",
            "이동 신청 및 본인 신청 취소",
            "자재 요청 신청·취소",
            "구매 요청 신청·취소",
            "재고 엑셀 다운로드",
            "사용내역 조회 (본인 센터 고정)",
        ],
        "caution": "입고·출고 버튼 없음. 재고 수정·삭제 불가.",
    },
    "user": {
        "desc": "일반 사용자. 기본 조회 및 요청 기능만 사용 가능.",
        "features": [
            "재고 현황 조회·검색·필터·다운로드",
            "이동 신청 및 본인 신청 취소",
            "자재 요청 신청·취소",
            "구매 요청 신청·취소",
            "입출고 이력 조회",
            "단말기 대시보드 조회",
            "문의하기",
        ],
        "caution": "입출고·수정·사용내역 업로드·승인 권한 없음.",
    },
    "guest": {
        "desc": "관리자 승인 대기 중이거나 제한적 열람만 허용된 계정.",
        "features": [
            "재고 현황 조회 (읽기 전용, 다운로드 불가)",
            "단말기 대시보드 조회 (읽기 전용)",
            "입출고 이력 조회",
            "마이페이지 (비밀번호 변경)",
            "문의하기",
        ],
        "caution": "요청·신청·업로드 등 모든 쓰기 기능 사용 불가.",
    },
}

CENTERS_INFO = [
    {
        "name": "자재센터",
        "type": "hub",
        "desc": "전체 자재 보관·관리 거점. 모든 이동의 출발 또는 경유지.",
        "rules": [
            "렉번호·단수·박스번호 조합으로 자재를 위치별 개별 row로 관리.",
            "같은 자재명이어도 위치(박스)가 다르면 별도 행으로 존재.",
            "입고: 외부(공장·구매)에서 자재센터로 들어오는 수량 증가.",
            "출고: 외부 소모 처리. 타센터 이동이 아닌 자재센터 자체 차감.",
            "이동신청: 자재센터 → 타센터로 보내는 경우에만 사용.",
            "자재요청 승인 시 차감할 렉/단수/박스 row를 직접 선택.",
            "타센터 반납(타→자재센터 이동) 승인 시 보관 위치(렉/단수/박스) 지정 필수.",
        ],
    },
    {
        "name": "지역센터 (강서·강북·강동·강남)",
        "type": "region",
        "desc": "버스 관련 지역 운영 센터.",
        "rules": [
            "자재는 위치 정보(렉/박스) 없이 자재명 기준으로 관리.",
            "사용내역 업로드로 사용 수량 차감 (센터장·admin).",
            "자재 요청 시 버스 자재만 요청 가능.",
            "이동 경로: 자재센터 포함 지역센터끼리 상호 이동 가능.",
            "이동 신청 승인: 본인 센터로 수신되는 건만 승인 가능.",
        ],
    },
    {
        "name": "고속/시외",
        "type": "special",
        "desc": "고속·시외버스 관련 파트.",
        "rules": [
            "자재 요청 시 버스 자재만 요청 가능.",
            "이동 경로: 자재센터 ↔ 고속/시외만 가능.",
            "사용내역 업로드 가능 (센터장·admin).",
        ],
    },
    {
        "name": "대전센터",
        "type": "special",
        "desc": "대전 지역 운영 센터.",
        "rules": [
            "자재 요청 시 대분류 제한 없음.",
            "이동 경로: 자재센터 ↔ 대전센터만 가능.",
            "사용내역 업로드 가능 (센터장·admin).",
        ],
    },
    {
        "name": "택시지원파트",
        "type": "special",
        "desc": "택시 단말기 관련 특수 파트.",
        "rules": [
            "자재 요청 시 택시 자재만 요청 가능.",
            "이동 경로: 자재센터 ↔ 택시지원파트만 가능.",
            "사용내역 업로드 가능 (센터장·admin).",
        ],
    },
    {
        "name": "리페어팀",
        "type": "special",
        "desc": "단말기 수리 전담 파트.",
        "rules": [
            "자재 요청 시 대분류 제한 없음 (버스·택시 모두 요청 가능).",
            "이동 경로: 자재센터 ↔ 리페어팀만 가능.",
            "사용내역 업로드 가능 (센터장·admin).",
        ],
    },
    {
        "name": "AFC지원파트",
        "type": "special",
        "desc": "AFC(자동요금징수시스템) 관련 파트.",
        "rules": [
            "자재 요청 시 철도 자재만 요청 가능.",
            "이동 경로: 자재센터 ↔ AFC지원파트만 가능.",
            "사용내역 업로드 가능 (센터장·admin).",
        ],
    },
    {
        "name": "토스",
        "type": "special",
        "desc": "토스 관련 파트.",
        "rules": [
            "자재 요청 시 대분류 제한 없음.",
            "이동 경로: 자재센터 ↔ 토스만 가능.",
            "사용내역 업로드 가능 (센터장·admin).",
        ],
    },
    {
        "name": "고객지원사업부",
        "type": "none",
        "desc": "재고 관리 대상 외 부서. 창고 뷰·이동 대상에서 제외.",
        "rules": [
            "재고 현황 페이지에 표시되지 않음.",
            "이동 신청 대상에서 제외.",
            "admin 계정이어도 전체 내보내기·삭제 패널 사용 불가.",
        ],
    },
]

TRANSFER_ROUTES = [
    ("자재센터",    "강서·강북·강동·강남·고속/시외·대전·택시지원·리페어·AFC·토스 (전체)"),
    ("강서센터",    "자재센터, 강북·강동·강남센터"),
    ("강북센터",    "자재센터, 강서·강동·강남센터"),
    ("강동센터",    "자재센터, 강서·강북·강남센터"),
    ("강남센터",    "자재센터, 강서·강북·강동센터"),
    ("고속/시외",   "자재센터만"),
    ("대전센터",    "자재센터만"),
    ("택시지원파트", "자재센터만"),
    ("리페어팀",    "자재센터만"),
    ("AFC지원파트", "자재센터만"),
    ("토스",        "자재센터만"),
    ("고객지원사업부", "이동 불가 (재고 관리 대상 외)"),
]

MAIL_ROWS = [
    ("임시 비밀번호",      "신청자",                     "비밀번호 찾기 요청 시"),
    ("회원가입 접수 확인", "신청자",                     "회원가입 제출 시"),
    ("회원가입 알림",      "관리자 전체",                "신규 가입 신청 시"),
    ("회원가입 승인",      "신청자",                     "관리자가 승인 처리 시"),
    ("이동 신청 알림",     "도착 센터 담당자",           "이동 신청 제출 시"),
    ("자재 요청 접수",     "자재파트·관리자",            "자재 요청 제출 시"),
    ("자재 요청 승인",     "요청 센터 전체 인원",        "자재 요청 승인 시"),
    ("자재 요청 결과",     "신청자",                     "승인·거절·보류 처리 시"),
    ("자재 요청 취소",     "자재파트·관리자",            "신청자가 취소 시"),
    ("구매 요청 접수",     "자재파트·관리자 (엑셀 첨부)", "구매 요청 제출 시"),
    ("구매 요청 확인",     "신청자 (엑셀 첨부)",         "구매 요청 제출 시"),
    ("구매 요청 결과",     "신청자",                     "상태 변경(처리중·완료·거절) 시"),
    ("구매 요청 취소",     "신청자·자재파트·관리자",     "구매 요청 취소 시"),
]


class WMSGuidePDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("MG", "",  FONT_REG,  uni=True)
        self.add_font("MG", "B", FONT_BOLD, uni=True)
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 20, 18)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("MG", "B", 8)
        self.set_text_color(*C_GRAY)
        self.cell(0, 6, "에이텍모빌리티 자재관리시스템 (WMS v2) — 사용 가이드", align="L")
        self.set_text_color(*C_PRIMARY)
        self.cell(0, 6, f"- {self.page_no()} -", align="R", ln=True)
        self.set_draw_color(*C_BORDER)
        self.line(18, self.get_y(), 192, self.get_y())
        self.ln(3)
        self.set_text_color(*C_DARK)

    def footer(self):
        self.set_y(-12)
        self.set_font("MG", "", 8)
        self.set_text_color(*C_GRAY)
        self.cell(0, 6, "© 에이텍모빌리티 WMS v2 · 내부 문서", align="C")

    def section_title(self, num, title):
        self.ln(4)
        self.set_fill_color(*C_PRIMARY)
        self.rect(18, self.get_y(), 174, 8, "F")
        self.set_font("MG", "B", 11)
        self.set_text_color(*C_WHITE)
        self.cell(0, 8, f"  {num}. {title}", ln=True)
        self.set_text_color(*C_DARK)
        self.ln(3)

    def sub_title(self, title, color=None):
        c = color or C_BLUE
        self.set_fill_color(*c)
        self.set_text_color(*C_WHITE)
        self.set_font("MG", "B", 9)
        self.cell(0, 6, f"  {title}", fill=True, ln=True)
        self.set_text_color(*C_DARK)
        self.ln(1)

    def check_sym(self, val):
        if val is True:
            self.set_text_color(*C_GREEN)
            return "●"
        elif val is False:
            self.set_text_color(*C_BORDER)
            return "○"
        else:
            return ""

    def cover_page(self):
        self.add_page()
        self.set_fill_color(*C_PRIMARY)
        self.rect(0, 0, 210, 58, "F")
        self.set_y(14)
        self.set_font("MG", "B", 22)
        self.set_text_color(*C_WHITE)
        self.cell(0, 10, "에이텍모빌리티", align="C", ln=True)
        self.set_font("MG", "B", 16)
        self.cell(0, 8, "자재관리시스템 (WMS v2)", align="C", ln=True)
        self.ln(2)
        self.set_font("MG", "", 11)
        self.cell(0, 7, "페이지별 · 권한별 · 센터별 사용 가이드", align="C", ln=True)

        self.set_y(72)
        self.set_text_color(*C_DARK)
        self.set_font("MG", "B", 13)
        self.cell(0, 8, "목차", ln=True)
        self.set_draw_color(*C_PRIMARY)
        self.line(18, self.get_y(), 192, self.get_y())
        self.ln(3)

        toc = [
            ("1", "권한(Role) 개요"),
            ("2", "권한별 기능 매트릭스"),
            ("3", "역할별 상세 가이드"),
            ("  3-1", "관리자 (admin)"),
            ("  3-2", "자재파트 (materials)"),
            ("  3-3", "센터장 (manager)"),
            ("  3-4", "일반 사용자 (user)"),
            ("  3-5", "게스트 (guest)"),
            ("4", "센터별 규칙 및 이동 경로"),
            ("5", "페이지별 기능 설명"),
            ("6", "메일 발송 정리"),
            ("7", "Supabase DB 마이그레이션 안내"),
        ]
        self.set_font("MG", "", 10)
        for num, title in toc:
            self.set_text_color(*C_GRAY)
            self.cell(18, 7, num)
            self.set_text_color(*C_DARK)
            self.cell(0, 7, title, ln=True)

        self.set_y(-52)
        self.set_fill_color(*C_LGRAY)
        self.rect(18, self.get_y(), 174, 30, "F")
        self.set_y(self.get_y() + 5)
        self.set_font("MG", "", 9)
        self.set_text_color(*C_GRAY)
        self.cell(0, 6, "기술 스택: Streamlit / Supabase (PostgreSQL) / Python 3.11", align="C", ln=True)
        self.cell(0, 6, "센터 구성: 자재센터 / 강서·강북·강동·강남센터 / 택시지원파트 / 리페어팀", align="C", ln=True)
        self.cell(0, 6, "대상 독자: 시스템 사용자 전체 (역할별 해당 섹션 참고)", align="C", ln=True)
        self.cell(0, 6, "작성일: 2026-05-19", align="C", ln=True)


def build_pdf():
    pdf = WMSGuidePDF()
    pdf.cover_page()

    # ── 1. 권한 개요 ──────────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1", "권한(Role) 개요")
    pdf.set_font("MG", "", 10)
    pdf.set_text_color(*C_DARK)
    pdf.multi_cell(0, 6,
        "WMS v2는 5가지 역할(Role)을 기반으로 기능 접근 권한을 제어합니다. "
        "로그인 후 본인 역할에 해당하는 섹션을 참고하세요.")
    pdf.ln(4)

    for role in ["admin", "materials", "manager", "user", "guest"]:
        info = ROLE_GUIDE[role]
        color = ROLE_COLORS[role]
        pdf.set_fill_color(*color)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("MG", "B", 10)
        pdf.cell(0, 7, f"  {ROLE_NAMES[role]}", fill=True, ln=True)
        pdf.set_text_color(*C_DARK)
        pdf.set_font("MG", "", 9)
        pdf.set_x(22)
        pdf.multi_cell(0, 5.5, info["desc"])
        pdf.ln(1)
        pdf.set_fill_color(*C_LGRAY)
        pdf.rect(20, pdf.get_y(), 170, 5, "F")
        pdf.set_font("MG", "B", 8)
        pdf.set_x(22)
        pdf.cell(0, 5, "주의사항", ln=True)
        pdf.set_font("MG", "", 9)
        pdf.set_x(22)
        pdf.set_text_color(*C_PRIMARY)
        pdf.multi_cell(0, 5, info["caution"])
        pdf.set_text_color(*C_DARK)
        pdf.ln(3)

    # ── 2. 기능 매트릭스 ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("2", "권한별 기능 매트릭스")

    col_w = [76, 20, 20, 20, 20, 18]
    headers = ["기능", "관리자", "자재파트", "센터장", "일반", "게스트"]

    pdf.set_fill_color(*C_DARK)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("MG", "B", 8)
    for h, w in zip(headers, col_w):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    for idx, (feat, *vals) in enumerate(FEATURE_MATRIX):
        is_header = vals[0] is None
        if is_header:
            pdf.set_fill_color(*C_DARK)
            pdf.set_text_color(*C_WHITE)
            pdf.set_font("MG", "B", 8)
            pdf.cell(sum(col_w), 5, f"  {feat}", border=1, fill=True, align="L", ln=True)
            continue
        fill = idx % 2 == 0
        pdf.set_fill_color(*C_LGRAY) if fill else pdf.set_fill_color(*C_WHITE)
        pdf.set_text_color(*C_DARK)
        pdf.set_font("MG", "", 8)
        pdf.cell(col_w[0], 6, f"  {feat}", border="LR", fill=fill)
        for val, w in zip(vals, col_w[1:]):
            sym = pdf.check_sym(val)
            if sym:
                pdf.cell(w, 6, sym, border="LR", fill=fill, align="C")
            else:
                pdf.cell(w, 6, "", border="LR", fill=fill)
            pdf.set_text_color(*C_DARK)
        pdf.ln()

    pdf.set_fill_color(*C_BORDER)
    pdf.cell(sum(col_w), 0.3, "", fill=True, ln=True)
    pdf.ln(2)
    pdf.set_font("MG", "", 8)
    pdf.set_text_color(*C_GRAY)
    pdf.cell(0, 5, "● = 사용 가능  ○ = 사용 불가", ln=True)

    # ── 3. 역할별 상세 가이드 ────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("3", "역할별 상세 가이드")

    for i, role in enumerate(["admin", "materials", "manager", "user", "guest"], 1):
        info = ROLE_GUIDE[role]
        color = ROLE_COLORS[role]
        pdf.set_fill_color(*color)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("MG", "B", 10)
        pdf.cell(0, 7, f"  3-{i}. {ROLE_NAMES[role]}", fill=True, ln=True)
        pdf.set_text_color(*C_DARK)
        pdf.ln(1)
        pdf.set_font("MG", "", 9)
        pdf.set_x(22)
        pdf.multi_cell(0, 5.5, info["desc"])
        pdf.ln(1)
        pdf.set_font("MG", "B", 9)
        pdf.set_x(22)
        pdf.cell(0, 5, "주요 사용 기능:", ln=True)
        pdf.set_font("MG", "", 9)
        for feat in info["features"]:
            pdf.set_x(26)
            pdf.set_text_color(*color)
            pdf.cell(4, 5, "▶")
            pdf.set_text_color(*C_DARK)
            pdf.cell(0, 5, feat, ln=True)
        pdf.ln(1)
        pdf.set_x(22)
        pdf.set_fill_color(255, 243, 243)
        pdf.rect(20, pdf.get_y(), 170, 6, "F")
        pdf.set_font("MG", "B", 8)
        pdf.set_text_color(*C_PRIMARY)
        pdf.set_x(23)
        pdf.cell(0, 6, "[!] " + info["caution"], ln=True)
        pdf.set_text_color(*C_DARK)
        pdf.ln(4)

    # ── 4. 센터별 규칙 ───────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("4", "센터별 규칙 및 이동 경로")

    TYPE_COLORS = {"hub": C_PRIMARY, "region": C_BLUE, "special": C_GREEN, "none": C_GRAY}
    TYPE_LABELS = {"hub": "자재 거점", "region": "지역 센터", "special": "특수 파트", "none": "재고 외"}

    for cinfo in CENTERS_INFO:
        color = TYPE_COLORS.get(cinfo["type"], C_DARK)
        pdf.set_fill_color(*color)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("MG", "B", 10)
        badge = TYPE_LABELS.get(cinfo["type"], "")
        pdf.cell(0, 7, f"  {cinfo['name']}  [{badge}]", fill=True, ln=True)
        pdf.set_text_color(*C_DARK)
        pdf.set_font("MG", "", 9)
        pdf.set_x(22)
        pdf.multi_cell(0, 5.5, cinfo["desc"])
        pdf.ln(1)
        for rule in cinfo["rules"]:
            pdf.set_x(26)
            pdf.set_text_color(*color)
            pdf.cell(4, 5.5, "·")
            pdf.set_text_color(*C_DARK)
            pdf.multi_cell(0, 5.5, rule)
        pdf.ln(4)

    # 이동 경로 표
    pdf.sub_title("센터 간 이동 가능 경로", C_DARK)
    pdf.set_fill_color(*C_DARK)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("MG", "B", 8)
    pdf.cell(52, 7, "출발 센터", border=1, fill=True, align="C")
    pdf.cell(122, 7, "이동 가능 도착 센터", border=1, fill=True, align="C")
    pdf.ln()
    for idx, (src, dsts) in enumerate(TRANSFER_ROUTES):
        fill = idx % 2 == 0
        pdf.set_fill_color(*C_LGRAY) if fill else pdf.set_fill_color(*C_WHITE)
        pdf.set_text_color(*C_DARK)
        pdf.set_font("MG", "", 8)
        pdf.cell(52, 6, f"  {src}", border="LR", fill=fill)
        pdf.cell(122, 6, dsts, border="LR", fill=fill)
        pdf.ln()
    pdf.set_fill_color(*C_BORDER)
    pdf.cell(174, 0.3, "", fill=True, ln=True)
    pdf.ln(2)

    # 자재요청 분류 제한
    pdf.ln(2)
    pdf.sub_title("센터별 자재 요청 분류 제한", C_DARK)
    req_restrict = [
        ("강서·강북·강동·강남, 고속/시외", "버스 자재만 요청 가능"),
        ("택시지원파트",                   "택시 자재만 요청 가능"),
        ("AFC지원파트",                    "철도 자재만 요청 가능"),
        ("리페어팀, 대전센터, 토스",       "제한 없음 (모든 대분류 요청 가능)"),
    ]
    pdf.set_fill_color(*C_DARK)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("MG", "B", 8)
    pdf.cell(80, 7, "센터", border=1, fill=True, align="C")
    pdf.cell(94, 7, "요청 가능 자재 분류", border=1, fill=True, align="C")
    pdf.ln()
    for idx, (ctr, rule) in enumerate(req_restrict):
        fill = idx % 2 == 0
        pdf.set_fill_color(*C_LGRAY) if fill else pdf.set_fill_color(*C_WHITE)
        pdf.set_text_color(*C_DARK)
        pdf.set_font("MG", "", 8)
        pdf.cell(80, 6, f"  {ctr}", border="LR", fill=fill)
        pdf.cell(94, 6, rule, border="LR", fill=fill)
        pdf.ln()
    pdf.set_fill_color(*C_BORDER)
    pdf.cell(174, 0.3, "", fill=True, ln=True)

    # ── 5. 페이지별 기능 설명 ────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("5", "페이지별 기능 설명")

    for page_name, features in PAGES.items():
        pdf.sub_title(page_name)
        for feat_name, feat_desc in features:
            pdf.set_font("MG", "B", 9)
            pdf.set_x(22)
            pdf.set_text_color(*C_BLUE)
            pdf.cell(40, 5.5, feat_name)
            pdf.set_text_color(*C_DARK)
            pdf.set_font("MG", "", 9)
            pdf.multi_cell(0, 5.5, feat_desc)
        pdf.ln(3)

    # ── 6. 메일 발송 정리 ────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("6", "메일 발송 정리")

    pdf.set_fill_color(*C_DARK)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("MG", "B", 8)
    pdf.cell(50, 7, "메일 종류",  border=1, fill=True, align="C")
    pdf.cell(60, 7, "수신자",     border=1, fill=True, align="C")
    pdf.cell(64, 7, "발송 시점",  border=1, fill=True, align="C")
    pdf.ln()

    for idx, (kind, recv, timing) in enumerate(MAIL_ROWS):
        fill = idx % 2 == 0
        pdf.set_fill_color(*C_LGRAY) if fill else pdf.set_fill_color(*C_WHITE)
        pdf.set_text_color(*C_DARK)
        pdf.set_font("MG", "", 8)
        pdf.cell(50, 6, f"  {kind}",  border="LR", fill=fill)
        pdf.cell(60, 6, recv,          border="LR", fill=fill)
        pdf.cell(64, 6, timing,        border="LR", fill=fill)
        pdf.ln()
    pdf.set_fill_color(*C_BORDER)
    pdf.cell(174, 0.3, "", fill=True, ln=True)
    pdf.ln(2)
    pdf.set_font("MG", "", 8)
    pdf.set_text_color(*C_GRAY)
    pdf.multi_cell(0, 5, "※ 고객지원사업부 소속 계정은 관리자·자재파트 알림 메일 수신 제외.")

    # ── 7. DB 마이그레이션 ───────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("7", "Supabase DB 마이그레이션 안내")
    pdf.set_font("MG", "", 9)
    pdf.set_text_color(*C_DARK)
    pdf.multi_cell(0, 6,
        "아래 SQL은 신규 기능 추가 시 Supabase SQL Editor에서 한 번만 실행하면 됩니다. "
        "IF NOT EXISTS 조건이 있어 중복 실행해도 안전합니다.")
    pdf.ln(3)

    sqls = [
        ("terminal_movements 테이블 생성", """\
CREATE TABLE IF NOT EXISTS terminal_movements (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    upload_id   uuid NOT NULL,
    trcn_id     text NOT NULL,
    device_type text NOT NULL,
    sub_type    text NOT NULL,
    from_center text NOT NULL,
    to_center   text NOT NULL,
    direction   text NOT NULL CHECK (direction IN ('in','out')),
    uploaded_by uuid REFERENCES users(id) ON DELETE SET NULL,
    uploaded_at timestamptz DEFAULT now(),
    upload_date date NOT NULL,
    file_name   text,
    notes       text
);"""),
        ("terminal_movements notes 컬럼 추가 (기존 테이블)",
         "ALTER TABLE terminal_movements ADD COLUMN IF NOT EXISTS notes text;"),
        ("purchase_requests cost_note 컬럼 추가",
         "ALTER TABLE purchase_requests ADD COLUMN IF NOT EXISTS cost_note text;"),
        ("Supabase Max Rows 설정 (대시보드)",
         "Settings > API > Max Rows 를 2000 이상으로 설정 (현재 2000 적용됨).\n"
         "자재 종류가 2000을 초과하면 추가 상향 필요."),
    ]

    for title, sql in sqls:
        pdf.set_fill_color(*C_LGRAY)
        pdf.set_text_color(*C_DARK)
        pdf.set_font("MG", "B", 9)
        pdf.cell(0, 6, f"  {title}", fill=True, ln=True)
        pdf.set_font("MG", "", 8)
        pdf.set_fill_color(245, 245, 245)
        pdf.set_text_color(50, 50, 50)
        pdf.set_x(22)
        pdf.multi_cell(166, 5, sql, border=1, fill=True)
        pdf.ln(3)

    return pdf


if __name__ == "__main__":
    from datetime import datetime
    out_path = rf"C:\Users\junyo\Desktop\WMS_사용가이드_{datetime.now().strftime('%m%d_%H%M')}.pdf"
    pdf = build_pdf()
    pdf.output(out_path)
    print(f"PDF 생성 완료: {out_path}")
