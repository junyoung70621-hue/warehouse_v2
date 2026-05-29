"""
에이텍모빌리티 자재관리시스템 — 구현기능 & 권한별 R&R PDF
실행: py -3 make_feature_pdf.py
"""
from fpdf import FPDF
from datetime import datetime

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
    "guest":     (170, 180, 190),
}
ROLE_KO = {
    "admin":     "관리자",
    "materials": "자재파트",
    "manager":   "센터장",
    "user":      "일반 사용자",
    "guest":     "게스트",
}

PAGES = [
    {
        "name": "재고 현황  (15_combined.py)",
        "desc": "자재 재고 조회, 입출고, 이동신청, 자재요청 등 핵심 기능 통합 페이지",
        "features": [
            ("KPI 카드 (4종)", "전체 품목 / 재고 부족(1~9) / 재고 없음 / 이동 중. 클릭 시 해당 조건 필터링."),
            ("검색 / 필터 / 정렬", "자재명·ERP코드·분류명 통합 검색. 대/중/소분류 캐스케이딩 드롭다운. 컬럼 클릭 정렬."),
            ("페이지네이션", "20/50/100/200개씩 보기. 페이지 번호 드롭다운 직접 선택."),
            ("엑셀 다운로드", "현재 센터 재고를 .xlsx로 저장. 게스트 제외 전원 가능."),
            ("엑셀 업로드 (자재 등록)", "렉/단/박스 기준 매칭 후 수량 합산. 신규 위치는 새 row 등록. admin·자재파트 전용."),
            ("입고 처리", "자재 선택 + 수량 입력 후 일괄 입고. 통합/개별 사유 선택. 이력 자동 기록."),
            ("출고 처리", "자재 선택 + 수량 입력 후 일괄 출고. 통합/개별 사유 선택. 이력 자동 기록."),
            ("사용내역 업로드", "엑셀 업로드 -> 자재명/ERP코드 매칭 -> 수량 차감 + 이력. admin·센터장 전용."),
            ("자재 요청", "자재센터 재고 검색 -> 카트 담기 -> 요청 발송. 자재파트/관리자 메일 자동 발송."),
            ("이동 신청", "도착 센터 선택 -> 자재+수량 카트 담기 -> 신청. 이동 경로 규칙 자동 적용."),
            ("이동 신청 현황 탭", "대기중/승인됨/거절됨/전체 탭. 역할별 필터링. 승인/거절/취소 처리."),
            ("자재 상세 팝업", "이력 조회(50건) / 위치 보기(자재센터) / 자재 수정(admin) / 삭제(admin)."),
            ("관리자 탭", "내보내기(센터 선택 + 엑셀 다운로드) / 삭제(백업 + 2단계 확인). admin 전용."),
            ("자재센터 추가 컬럼", "자재센터 선택 시 렉번호·단·박스·지역·ERP품명 컬럼 추가 표시."),
        ],
    },
    {
        "name": "입출고 이력  (04_history.py)",
        "desc": "전체 입고/출고/이동/수정 이력 조회 및 엑셀 다운로드",
        "features": [
            ("이력 조회", "작업유형 필터(입고/출고/이동/수정), 자재명/작업자/사유 검색, 센터 선택."),
            ("표시 건수", "100/200/500/1000건 선택."),
            ("엑셀 다운로드", "필터 적용된 이력 전체를 .xlsx로 저장."),
        ],
    },
    {
        "name": "자재요청 현황  (07_material_requests.py)",
        "desc": "자재 요청 접수, 처리(승인/거절/보류), 취소 및 현황 조회",
        "features": [
            ("자재 요청 접수", "자재센터 재고 검색(센터별 분류 제한) -> 카트 담기 -> 발송."),
            ("승인 처리", "차감할 렉/단/박스 row 선택 팝업 -> 자재센터 차감 + 요청센터 증가 + 이력 + 메일."),
            ("거절 / 보류", "메시지 작성 -> 신청자 메일 발송. 보류는 대기중으로 되돌리기 가능."),
            ("취소 (신청자)", "대기중 본인 요청 취소 -> 자재파트/관리자 취소 알림 메일."),
            ("상태 탭", "대기중/승인됨/거절됨/보류/취소됨/전체 탭 제공."),
            ("삭제 (admin)", "요청 기록 완전 삭제. 2단계 확인."),
        ],
    },
    {
        "name": "사용내역  (08_usage_history.py)  /  자재현황 대시보드  (10_dashboard.py)",
        "desc": "사용내역 조회 및 대시보드 KPI/차트/이력",
        "features": [
            ("사용내역 조회", "기간 필터(기본 최근 30일), 자재명/담당자/사유 검색. admin·자재파트: 전 센터 선택."),
            ("사용내역 엑셀", "필터된 사용내역 .xlsx 저장."),
            ("대시보드 KPI", "자재 종류 수, 총 재고 수량, 품절 항목, 재고 부족(1~3개) 카드."),
            ("대분류별/센터별 현황", "표 형태로 자재수·총수량·품절 수 표시. 전체 선택 시 센터별 표."),
            ("대분류별 차트", "재고 수량 막대 차트 (상위 15개)."),
            ("최근 이력", "최근 30건 입출고 이력 표시."),
        ],
    },
    {
        "name": "구매 요청  (11_purchase_requests.py)",
        "desc": "물품 구매 요청 제출, 상태 관리, 엑셀 요청서 자동 생성",
        "features": [
            ("요청 작성", "품명/수량/링크 동적 테이블. 구매사유·원가반영 필수. 파일 첨부 가능. 60초 중복 방지."),
            ("요청서 자동 생성", "제출 시 엑셀 요청서 생성 -> 관리자/자재파트/본인 메일 첨부 발송."),
            ("상태 관리", "대기중 -> 처리중 -> 완료/거절. 단계별 메일 발송. admin·자재파트 전용."),
            ("취소 / 삭제", "본인 취소 -> 관련 인원 메일. admin 삭제 -> 2단계 확인."),
            ("내 요청 현황", "본인 요청 목록 조회. 각 요청별 엑셀 다운로드."),
        ],
    },
    {
        "name": "버스단말기 현황  (14_terminal_dashboard.py)",
        "desc": "버스 단말기 출고/입고 현황 조회, 업로드, 인수인계증 생성",
        "features": [
            ("현황 조회", "날짜별 단말기 출고/입고 수량. 기종 x 센터 크로스 표."),
            ("자동 분류", "TRCN ID -> B800/B700/B710/B620/한강버스 자동 분류. 모뎀은 6자리 번호 대역 기준."),
            ("업로드", "출고: admin·자재파트 전용. 입고: 게스트 제외 전원. 중복 제거 후 저장."),
            ("인수인계증 생성", "날짜/방향/센터 필터 후 엑셀 인수인계증 자동 생성 (비고란/로고/서명란 포함)."),
            ("관리 탭", "기존 레코드 재분류 일괄 수정. admin 전용."),
        ],
    },
    {
        "name": "위치 지도  (09_rack_map.py)  /  관리자  (05_admin.py)  /  공통",
        "desc": "랙 위치 시각화, 회원 관리, 마이페이지, 문의하기, 로그인",
        "features": [
            ("위치 지도", "랙 번호 선택 -> 창고 지도 위에 위치 마커 표시. admin·자재파트 전용."),
            ("회원 승인 / 거절", "신규 가입 요청 처리. 권한·센터 지정 후 승인. 승인 시 메일 발송."),
            ("권한 / 센터 변경", "기존 회원 역할·소속 센터·이름 수정."),
            ("회원 삭제", "계정 삭제. 관련 이력/신청 데이터 NULL 처리."),
            ("마이페이지", "이름/이메일/연락처 수정, 비밀번호 변경. 전 권한 사용 가능."),
            ("문의하기", "문의 작성/조회. 관리자 답변 -> 신청자 메일 자동 발송."),
            ("로그인 / 회원가입", "아이디 저장, 임시 비밀번호 발급, 세션 30분 자동 만료."),
        ],
    },
]

ROLE_RR = {
    "admin": {
        "summary": "시스템 전체 최고 권한. 모든 센터 접근 및 전체 기능 사용 가능.",
        "resp": [
            "전 센터 재고 조회, 수정, 입출고 처리",
            "자재 일괄 업로드 / 내보내기 / 삭제",
            "자재 요청 승인·거절·보류 (차감 위치 선택)",
            "이동 신청 승인·거절 (자재센터 입고 시 위치 지정)",
            "구매 요청 상태 관리 및 삭제",
            "회원 가입 승인·거절·권한 변경·삭제",
            "버스단말기 업로드 및 관리 탭 재분류",
            "전 센터 사용내역·이력 조회, 문의 답변",
        ],
        "caution": "고객지원사업부 소속 admin은 내보내기·삭제 패널 사용 불가.",
    },
    "materials": {
        "summary": "자재센터 소속 자재파트. 자재 입출고 및 요청 관리 담당.",
        "resp": [
            "자재센터 입고·출고 처리 및 일괄 업로드",
            "자재 요청 승인·거절·보류 (차감 위치 선택, 메일 발송)",
            "이동 신청 승인·거절 (자재센터 관련)",
            "구매 요청 상태 관리 (메일 발송)",
            "버스단말기 업로드 (출고/입고)",
            "전 센터 사용내역·이력 조회",
        ],
        "caution": "자재 수정·삭제·내보내기 불가. 자재 요청 신청 불가. 회원 관리 불가.",
    },
    "manager": {
        "summary": "각 센터 센터장. 본인 센터 운영 및 관리 담당.",
        "resp": [
            "본인 센터 재고 조회 및 엑셀 다운로드",
            "본인 센터 사용내역 업로드 (재고 자동 차감)",
            "이동 신청 및 본인 센터 수신 이동 승인·거절",
            "자재 요청·구매 요청 신청 및 취소",
            "본인 센터 사용내역·이력 조회",
        ],
        "caution": "입고·출고 처리 불가. 자재 수정·삭제 불가. 회원 관리 불가.",
    },
    "user": {
        "summary": "일반 사용자. 기본 조회 및 요청 기능만 사용 가능.",
        "resp": [
            "본인 센터 재고 조회·검색·엑셀 다운로드",
            "이동 신청 및 본인 신청 취소",
            "자재 요청·구매 요청 신청 및 취소",
            "입출고 이력·사용내역·단말기 현황 조회",
            "문의하기",
        ],
        "caution": "입출고 처리, 사용내역 업로드, 자재 수정·삭제, 이동 승인 불가.",
    },
    "guest": {
        "summary": "승인 대기 중이거나 열람만 허용된 계정.",
        "resp": [
            "재고 현황 조회 (읽기 전용, 다운로드 불가)",
            "단말기 현황 조회",
            "마이페이지 (비밀번호 변경)",
            "문의하기",
        ],
        "caution": "요청·신청·업로드 등 모든 쓰기 기능 사용 불가.",
    },
}

MATRIX = [
    ("-- 재고 현황 --",               None, None, None, None, None),
    ("재고 조회·검색·필터",           True, True, True, True, True),
    ("엑셀 다운로드",                 True, True, True, True, False),
    ("자재 상세 이력 조회",           True, True, True, True, False),
    ("자재 수정·삭제 (상세팝업)",     True, False, False, False, False),
    ("엑셀 업로드 (자재 등록)",       True, True, False, False, False),
    ("입고 / 출고 처리",              True, True, False, False, False),
    ("사용내역 업로드",               True, False, True, False, False),
    ("자재 요청 신청",                True, False, True, True, False),
    ("내보내기·삭제 (admin탭)",       True, False, False, False, False),
    ("-- 이동 신청 --",               None, None, None, None, None),
    ("이동 신청",                     True, True, True, True, False),
    ("이동 신청 승인·거절",           True, True, True, False, False),
    ("이동 신청 취소 (본인)",         True, True, True, True, False),
    ("-- 자재 요청 --",               None, None, None, None, None),
    ("자재 요청 신청·취소",           True, False, True, True, False),
    ("자재 요청 승인·거절·보류",      True, True, False, False, False),
    ("자재 요청 삭제 (admin)",        True, False, False, False, False),
    ("-- 구매 요청 --",               None, None, None, None, None),
    ("구매 요청 신청·취소",           True, False, True, True, False),
    ("구매 요청 상태 관리",           True, True, False, False, False),
    ("구매 요청 삭제 (admin)",        True, False, False, False, False),
    ("-- 이력 / 사용내역 --",         None, None, None, None, None),
    ("입출고 이력 조회",              True, True, True, True, False),
    ("사용내역 조회 (전 센터)",       True, True, False, False, False),
    ("사용내역 조회 (본인 센터)",     True, True, True, True, False),
    ("-- 단말기 대시보드 --",         None, None, None, None, None),
    ("단말기 현황 조회",              True, True, True, True, True),
    ("단말기 업로드 (출고)",          True, True, False, False, False),
    ("단말기 업로드 (입고)",          True, True, True, True, False),
    ("인수인계증 생성",               True, True, True, True, False),
    ("단말기 관리 탭 (재분류)",       True, False, False, False, False),
    ("-- 관리 / 공통 --",             None, None, None, None, None),
    ("위치 지도 조회",                True, True, False, False, False),
    ("회원 승인·권한 변경·삭제",      True, False, False, False, False),
    ("마이페이지",                    True, True, True, True, True),
    ("문의하기",                      True, True, True, True, True),
    ("문의 답변 (관리자)",            True, False, False, False, False),
]

MAILS = [
    ("임시 비밀번호",         "신청자",                      "비밀번호 찾기 시"),
    ("가입 신청 확인",        "신청자",                      "회원가입 제출 시"),
    ("신규 가입 알림",        "관리자 전체",                 "신규 가입 신청 시"),
    ("회원가입 승인",         "신청자",                      "관리자 승인 시"),
    ("이동 신청 알림",        "도착 센터 담당자",            "이동 신청 제출 시"),
    ("자재 요청 접수",        "자재파트, 관리자",            "자재 요청 제출 시"),
    ("자재 요청 승인",        "요청 센터 전체 인원",         "자재 요청 승인 시"),
    ("자재 요청 결과",        "신청자",                      "승인/거절/보류 처리 시"),
    ("자재 요청 취소",        "자재파트, 관리자",            "신청자 취소 시"),
    ("구매 요청 접수",        "자재파트, 관리자 (엑셀첨부)", "구매 요청 제출 시"),
    ("구매 요청 확인",        "신청자 (엑셀 첨부)",          "구매 요청 제출 시"),
    ("구매 요청 상태 변경",   "신청자",                      "처리중/완료/거절 시"),
    ("구매 요청 취소",        "신청자, 자재파트, 관리자",    "취소 시"),
    ("문의 답변",             "신청자",                      "관리자 답변 등록 시"),
]


class FeaturePDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("MG", "",  FONT_REG,  uni=True)
        self.add_font("MG", "B", FONT_BOLD, uni=True)
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(15, 20, 15)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("MG", "B", 7.5)
        self.set_text_color(*C_GRAY)
        self.cell(0, 5, "에이텍모빌리티 자재관리시스템 -- 구현기능 & 권한별 R&R", align="L")
        self.set_text_color(*C_PRIMARY)
        self.cell(0, 5, str(self.page_no()), align="R", ln=True)
        self.set_draw_color(*C_BORDER)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(2)
        self.set_text_color(*C_DARK)

    def footer(self):
        self.set_y(-10)
        self.set_font("MG", "", 7)
        self.set_text_color(*C_GRAY)
        self.cell(0, 5, "(c) 에이텍모빌리티 WMS v2 -- 내부 문서", align="C")

    def cover(self):
        self.add_page()
        self.set_fill_color(*C_PRIMARY)
        self.rect(0, 0, 210, 62, "F")
        self.set_y(13)
        self.set_font("MG", "B", 22)
        self.set_text_color(*C_WHITE)
        self.cell(0, 10, "에이텍모빌리티 자재관리시스템", align="C", ln=True)
        self.set_font("MG", "B", 14)
        self.cell(0, 8, "구현 기능 명세  &  권한별 R&R", align="C", ln=True)
        self.set_font("MG", "", 9)
        self.cell(0, 6, "WMS v2  |  Streamlit + Supabase  |  " + datetime.now().strftime("%Y.%m.%d"), align="C", ln=True)

        self.set_y(72)
        self.set_text_color(*C_DARK)
        self.set_font("MG", "B", 11)
        self.cell(0, 7, "목차", ln=True)
        self.set_draw_color(*C_PRIMARY)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(2)

        toc = [
            ("1", "구현 기능 명세 (페이지별)"),
            ("2", "기능 권한 매트릭스"),
            ("3", "권한별 R&R"),
            ("4", "메일 발송 자동화 목록"),
        ]
        self.set_font("MG", "", 10)
        for num, title in toc:
            self.set_text_color(*C_GRAY)
            self.cell(10, 7, num + ".", align="R")
            self.set_text_color(*C_DARK)
            self.cell(0, 7, "  " + title, ln=True)

        self.set_y(-32)
        self.set_fill_color(*C_LGRAY)
        self.rect(15, self.get_y(), 180, 18, "F")
        self.set_y(self.get_y() + 3)
        self.set_font("MG", "", 8.5)
        self.set_text_color(*C_GRAY)
        self.cell(0, 5, "페이지 12개  |  DB 테이블 6개  |  권한 5종  |  메일 자동화 14종", align="C", ln=True)
        self.cell(0, 5, "기술 스택: Streamlit 1.57 / Supabase (PostgreSQL) / Python 3.11", align="C", ln=True)

    def section_title(self, num, title):
        self.ln(2)
        self.set_fill_color(*C_PRIMARY)
        self.rect(15, self.get_y(), 180, 8, "F")
        self.set_font("MG", "B", 11)
        self.set_text_color(*C_WHITE)
        self.cell(0, 8, "  " + str(num) + ". " + title, ln=True)
        self.set_text_color(*C_DARK)
        self.ln(2)

    def feature_section(self, page):
        # 페이지 헤더
        self.set_fill_color(*C_BLUE)
        self.set_text_color(*C_WHITE)
        self.set_font("MG", "B", 9)
        self.cell(0, 6.5, "  " + page["name"], fill=True, ln=True)
        self.set_font("MG", "", 7.5)
        self.set_text_color(*C_GRAY)
        self.set_x(17)
        self.cell(0, 4.5, page["desc"], ln=True)
        self.set_text_color(*C_DARK)
        self.ln(0.5)

        # 기능 목록 — 번호 + 기능명(굵게): 설명 형태로 한 행에
        col_w = 180
        for i, (fname, fdesc) in enumerate(page["features"]):
            fill = i % 2 == 0
            bg = C_LGRAY if fill else C_WHITE
            self.set_fill_color(*bg)

            y0 = self.get_y()
            # 번호
            self.set_font("MG", "B", 7.5)
            self.set_text_color(*C_PRIMARY)
            self.set_x(15)
            num_w = 7
            self.cell(num_w, 5.5, str(i + 1) + ".", fill=False)
            # 기능명
            self.set_text_color(*C_DARK)
            name_w = 42
            self.cell(name_w, 5.5, fname, fill=False)
            # 설명
            self.set_font("MG", "", 7.5)
            self.set_text_color(*C_GRAY)
            self.multi_cell(0, 5.5, fdesc, fill=False)

        self.ln(3)

    def matrix_table(self):
        roles  = ["admin", "materials", "manager", "user", "guest"]
        rko    = ["관리자", "자재파트", "센터장", "일반", "게스트"]
        cw_f   = 88   # 기능명 컬럼
        cw_r   = 18   # 역할 컬럼 (18*5=90, 총 178)
        total  = cw_f + cw_r * len(roles)

        # 헤더
        self.set_fill_color(*C_DARK)
        self.set_text_color(*C_WHITE)
        self.set_font("MG", "B", 8)
        self.cell(cw_f, 7, "  기능", border=1, fill=True)
        for role, name in zip(roles, rko):
            self.set_fill_color(*ROLE_COLORS[role])
            self.cell(cw_r, 7, name, border=1, fill=True, align="C")
        self.ln()

        for i, (feat, *vals) in enumerate(MATRIX):
            if vals[0] is None:
                self.set_fill_color(*C_DARK)
                self.set_text_color(*C_WHITE)
                self.set_font("MG", "B", 7.5)
                self.cell(total, 5, "  " + feat, border=1, fill=True, align="L", ln=True)
                continue
            fill = i % 2 == 0
            self.set_fill_color(*C_LGRAY) if fill else self.set_fill_color(*C_WHITE)
            self.set_text_color(*C_DARK)
            self.set_font("MG", "", 7.5)
            self.cell(cw_f, 5.5, "  " + feat, border="LR", fill=fill)
            for val in vals:
                if val is True:
                    self.set_text_color(*C_GREEN)
                    self.cell(cw_r, 5.5, "O", border="LR", fill=fill, align="C")
                else:
                    self.set_text_color(*C_BORDER)
                    self.cell(cw_r, 5.5, "-", border="LR", fill=fill, align="C")
                self.set_text_color(*C_DARK)
            self.ln()

        self.set_fill_color(*C_BORDER)
        self.cell(total, 0.3, "", fill=True, ln=True)
        self.ln(1)
        self.set_font("MG", "", 7.5)
        self.set_text_color(*C_GRAY)
        self.cell(0, 5, "O = 사용 가능  |  - = 사용 불가", ln=True)

    def rr_section(self):
        roles_order = ["admin", "materials", "manager", "user", "guest"]
        sub = 1
        for role in roles_order:
            info = ROLE_RR[role]
            color = ROLE_COLORS[role]

            # 역할 헤더
            self.set_fill_color(*color)
            self.set_text_color(*C_WHITE)
            self.set_font("MG", "B", 9.5)
            self.cell(0, 7, "  " + str(sub) + ".  " + ROLE_KO[role] + "  (" + role + ")", fill=True, ln=True)
            sub += 1

            # 요약
            self.set_font("MG", "", 8.5)
            self.set_text_color(*C_DARK)
            self.set_x(17)
            self.multi_cell(0, 5.5, info["summary"])
            self.ln(0.5)

            # 책임 목록 (2컬럼 레이아웃)
            resp = info["resp"]
            half = (len(resp) + 1) // 2
            col_w = 87
            for row_i in range(half):
                left  = resp[row_i]
                right = resp[row_i + half] if row_i + half < len(resp) else ""
                self.set_x(17)
                self.set_font("MG", "B", 8)
                self.set_text_color(*color)
                self.cell(5, 5.5, ">")
                self.set_font("MG", "", 8)
                self.set_text_color(*C_DARK)
                self.cell(col_w, 5.5, left)
                if right:
                    self.set_font("MG", "B", 8)
                    self.set_text_color(*color)
                    self.cell(5, 5.5, ">")
                    self.set_font("MG", "", 8)
                    self.set_text_color(*C_DARK)
                    self.multi_cell(0, 5.5, right)
                else:
                    self.ln()

            self.ln(0.5)
            # 주의사항
            self.set_x(17)
            self.set_font("MG", "B", 8)
            self.set_text_color(*C_PRIMARY)
            self.cell(14, 5, "[주의]  ")
            self.set_font("MG", "", 8)
            self.set_text_color(*C_DARK)
            self.multi_cell(0, 5, info["caution"])
            self.ln(4)

    def mail_table(self):
        cw = [52, 66, 62]
        self.set_fill_color(*C_DARK)
        self.set_text_color(*C_WHITE)
        self.set_font("MG", "B", 8)
        self.cell(cw[0], 6.5, "  메일 종류", border=1, fill=True)
        self.cell(cw[1], 6.5, "  수신자", border=1, fill=True)
        self.cell(cw[2], 6.5, "  발송 시점", border=1, fill=True)
        self.ln()
        for i, (kind, recv, timing) in enumerate(MAILS):
            fill = i % 2 == 0
            self.set_fill_color(*C_LGRAY) if fill else self.set_fill_color(*C_WHITE)
            self.set_text_color(*C_DARK)
            self.set_font("MG", "", 8)
            self.cell(cw[0], 5.5, "  " + kind, border="LR", fill=fill)
            self.cell(cw[1], 5.5, "  " + recv, border="LR", fill=fill)
            self.cell(cw[2], 5.5, "  " + timing, border="LR", fill=fill)
            self.ln()
        self.set_fill_color(*C_BORDER)
        self.cell(sum(cw), 0.3, "", fill=True, ln=True)


def build():
    pdf = FeaturePDF()
    pdf.cover()

    # 1. 구현 기능 명세
    pdf.add_page()
    pdf.section_title("1", "구현 기능 명세 (페이지별)")
    for pg in PAGES:
        pdf.feature_section(pg)

    # 2. 기능 권한 매트릭스
    pdf.add_page()
    pdf.section_title("2", "기능 권한 매트릭스")
    pdf.set_font("MG", "", 8.5)
    pdf.set_text_color(*C_DARK)
    pdf.multi_cell(0, 5.5, "역할(Role)별 기능 접근 가능 여부. 컬러 헤더는 역할 구분.")
    pdf.ln(2)
    pdf.matrix_table()

    # 3. 권한별 R&R
    pdf.add_page()
    pdf.section_title("3", "권한별 R&R  (Roles & Responsibilities)")
    pdf.rr_section()

    # 4. 메일 발송 목록
    pdf.section_title("4", "메일 발송 자동화 목록")
    pdf.set_font("MG", "", 8.5)
    pdf.set_text_color(*C_DARK)
    pdf.multi_cell(0, 5.5, "시스템에서 자동 발송되는 이메일 목록. Gmail SMTP 기반.")
    pdf.ln(2)
    pdf.mail_table()

    return pdf


if __name__ == "__main__":
    out = (
        r"C:\Users\junyo\Desktop\에이텍모빌리티_구현기능_권한RR_"
        + datetime.now().strftime("%Y%m%d_%H%M")
        + ".pdf"
    )
    pdf = build()
    pdf.output(out)
    print("PDF 생성 완료:", out)
