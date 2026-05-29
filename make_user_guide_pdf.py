"""
에이텍모빌리티 자재관리시스템 — 사용자 가이드 PDF 생성
실행: py -3 make_user_guide_pdf.py
"""
from fpdf import FPDF
from datetime import datetime

FONT_REG  = r"C:\Windows\Fonts\malgun.ttf"
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"

C_PRIMARY = (211,   0,  79)
C_BLUE    = (  2, 132, 199)
C_DARK    = ( 30,  41,  59)
C_GRAY    = (100, 116, 139)
C_LGRAY   = (241, 245, 249)
C_WHITE   = (255, 255, 255)
C_BORDER  = (226, 232, 240)
C_GREEN   = ( 22, 163,  74)
C_TIP_BG  = (240, 253, 244)
C_WARN_BG = (255, 241, 242)


class UserGuidePDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("MG", "",  FONT_REG,  uni=True)
        self.add_font("MG", "B", FONT_BOLD, uni=True)
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 22, 18)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("MG", "B", 8)
        self.set_text_color(*C_GRAY)
        self.cell(0, 6, "에이텍모빌리티 자재관리시스템 -- 사용 가이드", align="L")
        self.set_text_color(*C_PRIMARY)
        self.cell(0, 6, str(self.page_no()), align="R", ln=True)
        self.set_draw_color(*C_BORDER)
        self.line(18, self.get_y(), 192, self.get_y())
        self.ln(3)
        self.set_text_color(*C_DARK)

    def footer(self):
        self.set_y(-12)
        self.set_font("MG", "", 8)
        self.set_text_color(*C_GRAY)
        self.cell(0, 6, "(c) 에이텍모빌리티 자재관리시스템 · 내부 사용 문서", align="C")

    def cover(self):
        self.add_page()
        self.set_fill_color(*C_PRIMARY)
        self.rect(0, 0, 210, 70, "F")
        self.set_y(16)
        self.set_font("MG", "B", 26)
        self.set_text_color(*C_WHITE)
        self.cell(0, 12, "에이텍모빌리티", align="C", ln=True)
        self.set_font("MG", "B", 18)
        self.cell(0, 10, "자재관리시스템", align="C", ln=True)
        self.set_font("MG", "", 12)
        self.cell(0, 8, "사용 가이드", align="C", ln=True)

        self.set_y(82)
        self.set_font("MG", "", 10)
        self.set_text_color(*C_GRAY)
        self.cell(0, 7, "처음 사용하시는 분도 쉽게 따라할 수 있도록 작성된 가이드입니다.", align="C", ln=True)
        self.ln(6)

        self.set_fill_color(*C_PRIMARY)
        self.set_text_color(*C_WHITE)
        self.set_font("MG", "B", 11)
        self.cell(0, 8, "  목  차", fill=True, ln=True)
        self.ln(2)

        toc = [
            ("1",  "처음 시작하기 -- 로그인"),
            ("2",  "화면 구성 이해하기"),
            ("3",  "재고 현황 보기"),
            ("4",  "자재 상세 정보 보기"),
            ("5",  "입고 처리하기 (자재센터)"),
            ("6",  "출고 처리하기 (자재센터)"),
            ("7",  "사용내역 업로드하기 (각 센터)"),
            ("8",  "자재 요청하기 (각 센터)"),
            ("9",  "자재 요청 처리하기 (자재파트·관리자)"),
            ("10", "이동 신청하기"),
            ("11", "이동 신청 승인하기"),
            ("12", "입출고 이력 조회하기"),
            ("13", "구매 요청하기"),
            ("14", "문의하기"),
            ("15", "내 정보 수정하기"),
            ("16", "관리자 기능 (관리자 전용)"),
            ("17", "자주 묻는 질문"),
        ]
        self.set_font("MG", "", 10)
        for num, title in toc:
            self.set_text_color(*C_GRAY)
            self.cell(12, 7, num + ".", align="R")
            self.set_text_color(*C_DARK)
            self.cell(0, 7, "  " + title, ln=True)

        self.set_y(-30)
        self.set_fill_color(*C_LGRAY)
        self.rect(18, self.get_y(), 174, 16, "F")
        self.set_y(self.get_y() + 4)
        self.set_font("MG", "", 9)
        self.set_text_color(*C_GRAY)
        self.cell(0, 5, "최종 업데이트: 2026년 5월", align="C", ln=True)
        self.cell(0, 5, "문의: 시스템 내 [문의하기] 메뉴 이용", align="C", ln=True)

    def section_title(self, num, title):
        self.ln(3)
        self.set_fill_color(*C_PRIMARY)
        self.rect(18, self.get_y(), 174, 9, "F")
        self.set_font("MG", "B", 12)
        self.set_text_color(*C_WHITE)
        self.cell(0, 9, "  " + str(num) + ". " + title, ln=True)
        self.set_text_color(*C_DARK)
        self.ln(3)

    def sub_title(self, title):
        self.set_fill_color(*C_BLUE)
        self.set_text_color(*C_WHITE)
        self.set_font("MG", "B", 10)
        self.cell(0, 7, "  " + title, fill=True, ln=True)
        self.set_text_color(*C_DARK)
        self.ln(2)

    def body(self, text):
        self.set_font("MG", "", 10)
        self.set_text_color(*C_DARK)
        self.multi_cell(0, 6, text)

    def tip(self, text):
        self.ln(1)
        y = self.get_y()
        lines = text.split("\n")
        h = len(lines) * 5.5 + 5
        self.set_fill_color(*C_TIP_BG)
        self.rect(19, y, 172, h, "F")
        self.set_draw_color(*C_GREEN)
        self.line(19, y, 19, y + h)
        self.set_y(y + 2)
        self.set_x(23)
        self.set_font("MG", "B", 9)
        self.set_text_color(*C_GREEN)
        self.cell(10, 5.5, "[TIP]")
        self.set_font("MG", "", 9)
        self.set_text_color(*C_DARK)
        self.multi_cell(0, 5.5, text)
        self.ln(2)
        self.set_draw_color(*C_BORDER)

    def warn(self, text):
        self.ln(1)
        y = self.get_y()
        lines = text.split("\n")
        h = len(lines) * 5.5 + 5
        self.set_fill_color(*C_WARN_BG)
        self.rect(19, y, 172, h, "F")
        self.set_draw_color(*C_PRIMARY)
        self.line(19, y, 19, y + h)
        self.set_y(y + 2)
        self.set_x(23)
        self.set_font("MG", "B", 9)
        self.set_text_color(*C_PRIMARY)
        self.cell(14, 5.5, "[주의]")
        self.set_font("MG", "", 9)
        self.set_text_color(*C_DARK)
        self.multi_cell(0, 5.5, text)
        self.ln(2)
        self.set_draw_color(*C_BORDER)

    def table(self, headers, rows, col_widths):
        self.set_fill_color(*C_DARK)
        self.set_text_color(*C_WHITE)
        self.set_font("MG", "B", 9)
        for h, w in zip(headers, col_widths):
            self.cell(w, 7, " " + h, border=1, fill=True)
        self.ln()
        for i, row in enumerate(rows):
            fill = i % 2 == 0
            self.set_fill_color(*C_LGRAY) if fill else self.set_fill_color(*C_WHITE)
            self.set_text_color(*C_DARK)
            self.set_font("MG", "", 9)
            for cell_txt, w in zip(row, col_widths):
                self.cell(w, 6, " " + cell_txt, border="LR", fill=fill)
            self.ln()
        self.set_fill_color(*C_BORDER)
        self.cell(sum(col_widths), 0.3, "", fill=True, ln=True)
        self.ln(3)

    def step_table(self, rows):
        col_w = [18, 156]
        self.set_fill_color(*C_DARK)
        self.set_text_color(*C_WHITE)
        self.set_font("MG", "B", 9)
        self.cell(col_w[0], 7, " 단계", border=1, fill=True, align="C")
        self.cell(col_w[1], 7, " 내용", border=1, fill=True)
        self.ln()
        for i, (step, desc) in enumerate(rows):
            fill = i % 2 == 0
            self.set_fill_color(*C_LGRAY) if fill else self.set_fill_color(*C_WHITE)
            self.set_font("MG", "B", 9)
            self.set_text_color(*C_PRIMARY)
            self.cell(col_w[0], 6, " " + step, border="LR", fill=fill, align="C")
            self.set_font("MG", "", 9)
            self.set_text_color(*C_DARK)
            self.cell(col_w[1], 6, " " + desc, border="LR", fill=fill)
            self.ln()
        self.set_fill_color(*C_BORDER)
        self.cell(sum(col_w), 0.3, "", fill=True, ln=True)
        self.ln(3)

    def bullet(self, items):
        for item in items:
            self.set_x(22)
            self.set_font("MG", "B", 9)
            self.set_text_color(*C_BLUE)
            self.cell(6, 6, ">")
            self.set_font("MG", "", 9)
            self.set_text_color(*C_DARK)
            self.multi_cell(0, 6, item)


def build():
    pdf = UserGuidePDF()
    pdf.cover()

    # ── 1. 처음 시작하기 ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1", "처음 시작하기 -- 로그인")

    pdf.sub_title("로그인 방법")
    pdf.body("웹 브라우저(크롬, 엣지 등)를 열고 관리자에게 받은 주소를 입력합니다.")
    pdf.ln(2)
    pdf.step_table([
        ("1", "아이디 입력란에 본인 아이디를 입력합니다."),
        ("2", "비밀번호 입력란에 비밀번호를 입력합니다."),
        ("3", "파란색 [로그인] 버튼을 누릅니다."),
    ])
    pdf.tip("'아이디 저장' 체크박스에 체크하면 다음에 접속할 때 아이디가 자동으로 채워집니다.")

    pdf.sub_title("처음 사용하시는 경우 -- 회원가입")
    pdf.body("화면 상단의 [회원가입] 탭을 클릭하고 아래 내용을 입력합니다.")
    pdf.ln(2)
    pdf.table(
        ["항목", "설명"],
        [
            ["아이디", "로그인할 때 쓸 아이디 (영문+숫자 조합)"],
            ["비밀번호", "6자 이상으로 설정하세요"],
            ["비밀번호 확인", "위에 입력한 비밀번호를 다시 입력"],
            ["이름", "본인 실명"],
            ["회사 이메일", "회사 이메일 주소 (필수)"],
            ["연락처", "휴대폰 번호 (선택사항)"],
            ["소속 센터", "본인이 근무하는 센터를 드롭다운에서 선택"],
        ],
        [50, 124]
    )
    pdf.body("입력 후 [회원가입 신청] 버튼을 누릅니다.")
    pdf.tip("관리자가 승인하면 가입 시 입력한 이메일로 알림이 옵니다. 승인 후 로그인 가능합니다.")

    pdf.sub_title("비밀번호를 잊어버린 경우")
    pdf.step_table([
        ("1", "[비밀번호 찾기] 탭을 클릭합니다."),
        ("2", "가입 시 사용한 회사 이메일을 입력합니다."),
        ("3", "[임시 비밀번호 발송] 버튼을 누릅니다."),
        ("4", "이메일로 임시 비밀번호가 전송됩니다."),
        ("5", "임시 비밀번호로 로그인 후, 마이페이지에서 비밀번호를 변경하세요."),
    ])

    # ── 2. 화면 구성 ─────────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("2", "화면 구성 이해하기")

    pdf.body("로그인 후 화면은 크게 두 부분으로 나뉩니다.")
    pdf.ln(2)
    pdf.table(
        ["구역", "설명"],
        [
            ["상단바", "현재 페이지 이름, 남은 세션 시간, 소속 센터, 이름이 표시됩니다."],
            ["왼쪽 사이드바", "메뉴 목록입니다. 원하는 메뉴를 클릭하여 이동합니다."],
            ["메인 화면", "선택한 메뉴의 내용이 표시됩니다."],
        ],
        [40, 134]
    )

    pdf.sub_title("왼쪽 메뉴(사이드바) 설명")
    pdf.table(
        ["메뉴", "설명"],
        [
            ["자재현황(전체)", "모든 센터 재고를 한눈에 보는 대시보드"],
            ["버스단말기 현황", "버스 단말기 이동 현황"],
            ["재고 현황", "자재 재고 조회, 입출고, 이동 신청 등 핵심 메뉴"],
            ["입출고 이력", "모든 입고, 출고, 이동 기록 조회"],
            ["사용내역", "각 센터의 자재 사용 기록"],
            ["자재요청현황", "자재 요청 신청 및 처리 현황"],
            ["구매 요청", "물품 구매 요청"],
            ["위치 지도", "자재 보관 위치 지도 (자재파트, 관리자)"],
            ["관리자", "회원 관리 (관리자 전용)"],
            ["문의하기", "시스템 관련 문의 작성, 확인"],
            ["마이페이지", "내 정보, 비밀번호 수정"],
            ["로그아웃", "시스템 로그아웃"],
        ],
        [50, 124]
    )
    pdf.warn("세션 시간 주의: 30분 동안 아무 작업도 하지 않으면 자동으로 로그아웃됩니다.\n상단바의 남은 시간을 확인하세요.")

    # ── 3. 재고 현황 보기 ────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("3", "재고 현황 보기")

    pdf.body("왼쪽 메뉴에서 [재고 현황]을 클릭합니다.")
    pdf.ln(2)

    pdf.sub_title("상단 요약 카드")
    pdf.body("화면 상단에 4개의 카드가 보입니다. 카드를 클릭하면 해당 자재만 골라볼 수 있습니다.")
    pdf.ln(2)
    pdf.table(
        ["카드", "의미"],
        [
            ["전체 품목", "현재 센터에 등록된 총 자재 종류 수"],
            ["재고 부족 (1~9개)", "수량이 1~9개인 자재 수 (주의 필요)"],
            ["재고 없음 (0개)", "수량이 0개인 자재 수 (보충 필요)"],
            ["이동 중", "이동 신청이 대기 중인 자재 수"],
        ],
        [50, 124]
    )
    pdf.tip("카드 아래 [필터] 버튼을 누르면 해당 자재만 골라서 볼 수 있습니다. 다시 누르면 해제됩니다.")

    pdf.sub_title("자재 검색하기")
    pdf.body("'자재 검색' 칸에 찾고 싶은 자재명, ERP코드, 또는 분류명을 입력합니다.\n입력하는 즉시 아래 목록이 자동으로 필터링됩니다.")
    pdf.ln(2)

    pdf.sub_title("분류로 찾기")
    pdf.body("자재명을 잘 모를 때는 분류 드롭다운으로 찾을 수 있습니다.")
    pdf.step_table([
        ("1", "대분류 드롭다운에서 큰 분류를 선택합니다. (예: 버스, 택시)"),
        ("2", "중분류 드롭다운에서 중간 분류를 선택합니다."),
        ("3", "소분류 드롭다운에서 세부 분류를 선택합니다."),
        ("4", "필터를 모두 지우려면 [초기화] 버튼을 누릅니다."),
    ])

    pdf.sub_title("자재 목록 보기")
    pdf.table(
        ["기능", "방법"],
        [
            ["페이지 이동", "왼쪽 [이전], 오른쪽 [다음] 버튼으로 페이지를 넘깁니다."],
            ["페이지 직접 이동", "페이지 숫자 드롭다운에서 원하는 번호를 선택합니다."],
            ["한 번에 볼 개수", "오른쪽 [개수] 드롭다운에서 20, 50, 100, 200 중 선택합니다."],
            ["표 정렬", "컬럼 헤더(자재명, 수량 등)를 클릭하면 정렬됩니다."],
            ["엑셀 다운로드", "[다운로드] 버튼으로 현재 재고를 엑셀 파일로 저장합니다."],
        ],
        [50, 124]
    )

    # ── 4. 자재 상세 정보 ────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("4", "자재 상세 정보 보기")

    pdf.body("자재 목록에서 보고 싶은 자재 행의 왼쪽 체크박스를 클릭하면 상세 팝업이 열립니다.")
    pdf.ln(2)
    pdf.table(
        ["탭", "내용"],
        [
            ["이력 조회", "해당 자재의 최근 입출고, 이동, 수정 이력 50건을 확인합니다."],
            ["위치 보기", "자재가 어떤 랙에 보관되어 있는지 표시됩니다. (자재센터)"],
            ["자재 수정", "자재 정보를 수정합니다. (관리자 전용) 수정 후 사유 입력 필수."],
        ],
        [35, 139]
    )

    # ── 5. 입고 처리 ─────────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("5", "입고 처리하기 (자재센터)")

    pdf.body("자재센터 소속이며 자재파트 또는 관리자 권한이 있는 경우에만 가능합니다.\n재고 현황 페이지에서 [입고] 버튼을 클릭하면 팝업 창이 열립니다.")
    pdf.ln(2)
    pdf.step_table([
        ("1", "드롭다운에서 입고할 자재를 선택합니다."),
        ("2", "입고할 수량을 숫자로 입력합니다."),
        ("3", "[추가] 버튼을 누릅니다."),
        ("4", "여러 자재를 입고할 경우 1~3을 반복합니다."),
        ("5", "입고 사유를 입력합니다. (예: 신규 구매, 반납)"),
        ("6", "[입고 확정] 버튼을 누르면 재고에 반영됩니다."),
    ])
    pdf.tip("사유 방식: '통합' 선택 시 전체에 같은 사유 입력.\n'개별' 선택 시 자재마다 다른 사유를 입력할 수 있습니다.")

    # ── 6. 출고 처리 ─────────────────────────────────────────────────────
    pdf.section_title("6", "출고 처리하기 (자재센터)")

    pdf.body("자재센터 소속이며 자재파트 또는 관리자 권한이 있는 경우에만 가능합니다.\n재고 현황 페이지에서 [출고] 버튼을 클릭합니다.")
    pdf.ln(2)
    pdf.step_table([
        ("1", "드롭다운에서 출고할 자재를 선택합니다."),
        ("2", "출고할 수량을 숫자로 입력합니다."),
        ("3", "[추가] 버튼을 누릅니다."),
        ("4", "여러 자재를 출고할 경우 1~3을 반복합니다."),
        ("5", "출고 사유를 입력합니다."),
        ("6", "[출고 확정] 버튼을 누릅니다."),
    ])
    pdf.warn("출고 수량이 현재 재고보다 많으면 오류가 발생합니다.\n재고 수량을 먼저 확인하고 진행하세요.")

    # ── 7. 사용내역 업로드 ───────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("7", "사용내역 업로드하기 (각 센터)")

    pdf.body("자재센터가 아닌 센터의 관리자 또는 센터장이 사용할 수 있습니다.\n자재를 사용한 내역을 엑셀로 업로드하면 재고에서 자동으로 수량이 차감됩니다.")
    pdf.ln(2)
    pdf.step_table([
        ("1", "[재고 현황] 페이지에서 [사용내역] 버튼을 클릭합니다."),
        ("2", "팝업에서 [사용내역 양식 다운로드] 버튼으로 양식을 받습니다."),
        ("3", "다운로드한 엑셀 파일을 열어 자재명과 사용수량(노란 칸)을 입력합니다."),
        ("4", "파일을 저장한 후, 팝업의 [파일 선택] 버튼으로 파일을 업로드합니다."),
        ("5", "미리보기에서 내용을 확인합니다."),
        ("6", "[차감 확정] 버튼을 누릅니다."),
    ])
    pdf.warn("자재명이나 ERP코드가 정확하지 않으면 매칭에 실패할 수 있습니다.\n재고 현황에서 정확한 자재명을 미리 확인하세요.")

    # ── 8. 자재 요청 ─────────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("8", "자재 요청하기 (각 센터)")

    pdf.body("자재센터가 아닌 센터의 센터장 또는 일반 사용자가 자재를 요청할 수 있습니다.")
    pdf.ln(2)
    pdf.step_table([
        ("1", "[재고 현황] 페이지에서 [자재 요청] 버튼을 클릭합니다."),
        ("2", "검색창에 원하는 자재명을 입력합니다."),
        ("3", "목록에서 자재를 선택하고 요청 수량을 입력합니다."),
        ("4", "[목록에 추가] 버튼을 누릅니다."),
        ("5", "필요한 자재를 모두 추가했으면 비고를 입력합니다. (선택사항)"),
        ("6", "[요청 발송] 버튼을 누릅니다."),
    ])
    pdf.tip("요청이 접수되면 자재파트와 관리자에게 자동으로 이메일이 발송됩니다.\n요청 결과는 [자재요청현황] 메뉴에서 확인할 수 있습니다.")

    # ── 9. 자재 요청 처리 ────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("9", "자재 요청 처리하기 (자재파트, 관리자)")

    pdf.body("왼쪽 메뉴에서 [자재요청현황]을 클릭합니다.\n[대기중] 탭에서 처리할 요청을 찾고, 요청 내용을 확인합니다.")
    pdf.ln(2)
    pdf.table(
        ["버튼", "의미", "절차"],
        [
            ["승인", "요청을 승인하고 재고 차감", "차감 위치 선택 -> 메일 내용 입력 -> [승인 + 발송]"],
            ["거절", "요청을 거절", "거절 사유 입력 -> [거절 + 발송]"],
            ["보류", "일단 보류", "보류 이유 입력 -> [보류 + 발송]"],
        ],
        [25, 35, 114]
    )
    pdf.tip("승인, 거절, 보류 처리 시 신청자에게 자동으로 이메일이 발송됩니다.")
    pdf.body("[보류] 탭에서 보류 요청을 찾아 [대기중으로 되돌리기] 버튼을 누르면 다시 대기 상태로 변경됩니다.")
    pdf.ln(2)
    pdf.sub_title("요청 취소하기 (신청자)")
    pdf.body("[자재요청현황] 메뉴에서 본인의 대기중 요청을 찾아 [요청 취소] 버튼을 누릅니다.\n취소 시 자재파트와 관리자에게 취소 알림 이메일이 발송됩니다.")

    # ── 10. 이동 신청 ────────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("10", "이동 신청하기")

    pdf.body("자재를 한 센터에서 다른 센터로 이동 신청할 때 사용합니다.")
    pdf.ln(2)
    pdf.step_table([
        ("1", "[재고 현황] 페이지에서 [이동 신청] 항목을 클릭하여 펼칩니다."),
        ("2", "도착 센터를 선택합니다."),
        ("3", "원하는 자재를 선택하고 수량을 입력합니다."),
        ("4", "[항목 추가] 버튼을 누릅니다."),
        ("5", "여러 자재를 신청할 경우 3~4를 반복합니다."),
        ("6", "신청 목록에서 수량 수정 또는 [X] 버튼으로 항목 삭제 가능합니다."),
        ("7", "[이동 신청] 버튼을 누릅니다."),
    ])
    pdf.tip("이동 신청 후 현황은 [이동 신청 현황] 탭에서 확인할 수 있습니다.")

    # ── 11. 이동 신청 승인 ───────────────────────────────────────────────
    pdf.section_title("11", "이동 신청 승인하기")

    pdf.body("관리자, 자재파트, 또는 해당 센터 센터장이 승인할 수 있습니다.\n[재고 현황] -> [이동 신청 현황] 탭 -> [대기중] 탭에서 처리할 신청을 찾습니다.")
    pdf.ln(2)
    pdf.table(
        ["버튼", "설명"],
        [
            ["승인", "이동을 승인하고 재고를 이동 처리합니다."],
            ["거절", "이동을 거절합니다."],
            ["취소", "신청자 본인이 대기중 신청을 취소할 수 있습니다."],
        ],
        [30, 144]
    )
    pdf.tip("자재센터로 도착하는 이동 승인 시, 어느 랙, 단, 박스에 넣을지\n위치를 입력하는 창이 추가로 나타납니다.")

    # ── 12. 입출고 이력 ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("12", "입출고 이력 조회하기")

    pdf.body("언제 어떤 자재가 입고, 출고, 이동되었는지 확인할 수 있습니다.\n왼쪽 메뉴에서 [입출고 이력]을 클릭합니다.")
    pdf.ln(2)
    pdf.table(
        ["필터", "설명"],
        [
            ["작업 유형", "전체 / 입고 / 출고 / 이동 / 수정 중 선택"],
            ["검색", "자재명, 작업자, 사유로 검색"],
            ["센터", "조회할 센터 선택"],
            ["표시 건수", "100 / 200 / 500 / 1000 중 선택"],
        ],
        [40, 134]
    )
    pdf.tip("[이력 엑셀 다운로드] 버튼을 누르면 엑셀 파일로 저장할 수 있습니다.")

    # ── 13. 구매 요청 ────────────────────────────────────────────────────
    pdf.section_title("13", "구매 요청하기")

    pdf.body("자재가 아닌 물품(사무용품, 장비 등)을 구매해야 할 때 사용합니다.\n왼쪽 메뉴에서 [구매 요청]을 클릭합니다.")
    pdf.ln(2)
    pdf.table(
        ["항목", "설명"],
        [
            ["구매 목록", "품명, 수량, 구매 링크를 입력합니다. [+] 버튼으로 항목 추가 가능."],
            ["구매사유", "왜 구매해야 하는지 입력합니다. (필수)"],
            ["원가반영", "원가 반영 여부, 방법을 입력합니다. (필수)"],
            ["비고", "추가 설명을 입력합니다. (선택)"],
            ["첨부파일", "관련 파일을 첨부합니다. (선택)"],
        ],
        [35, 139]
    )
    pdf.body("내용 확인 후 [요청 제출] 버튼을 누릅니다.")
    pdf.ln(2)
    pdf.tip("[내 요청 현황] 탭에서 처리 상태를 확인할 수 있습니다.\n처리 전이라면 [요청 취소] 버튼으로 취소 가능합니다.")

    # ── 14. 문의하기 ─────────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("14", "문의하기")

    pdf.body("시스템 사용 중 궁금한 점이 있으면 문의를 남길 수 있습니다.")
    pdf.ln(2)
    pdf.step_table([
        ("1", "왼쪽 메뉴에서 [문의하기]를 클릭합니다."),
        ("2", "제목과 내용을 입력합니다."),
        ("3", "[제출] 버튼을 누릅니다."),
        ("4", "오른쪽 [내 문의 내역]에서 접수된 문의와 답변을 확인합니다."),
    ])
    pdf.tip("관리자가 답변을 등록하면 이메일로 알림이 옵니다.")

    # ── 15. 마이페이지 ───────────────────────────────────────────────────
    pdf.section_title("15", "내 정보 수정하기")

    pdf.body("왼쪽 메뉴에서 [마이페이지]를 클릭합니다.")
    pdf.ln(2)
    pdf.sub_title("내 정보 수정")
    pdf.body("이름, 이메일, 연락처를 수정하고 [저장] 버튼을 누릅니다.")
    pdf.ln(2)
    pdf.sub_title("비밀번호 변경")
    pdf.step_table([
        ("1", "[비밀번호 변경] 탭을 클릭합니다."),
        ("2", "현재 비밀번호를 입력합니다."),
        ("3", "새 비밀번호를 입력합니다. (6자 이상)"),
        ("4", "새 비밀번호 확인 칸에 같은 비밀번호를 다시 입력합니다."),
        ("5", "[변경] 버튼을 누릅니다."),
    ])

    # ── 16. 관리자 기능 ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("16", "관리자 기능 (관리자 전용)")

    pdf.body("관리자(admin) 권한이 있는 경우에만 접근할 수 있습니다.\n왼쪽 메뉴에서 [관리자]를 클릭합니다.")
    pdf.ln(2)

    pdf.sub_title("회원 가입 승인")
    pdf.body("[가입 승인 대기] 탭에서 새로 가입 신청한 회원을 승인하거나 거절할 수 있습니다.")
    pdf.ln(2)
    pdf.step_table([
        ("1", "신청자 정보(이름, 이메일, 소속 센터)를 확인합니다."),
        ("2", "부여할 권한을 선택합니다. (관리자/자재파트/센터장/일반/게스트)"),
        ("3", "소속 센터를 선택합니다."),
        ("4", "[승인] 또는 [거절] 버튼을 누릅니다."),
    ])

    pdf.sub_title("권한(역할) 종류")
    pdf.table(
        ["권한", "설명"],
        [
            ["관리자", "모든 기능 사용 가능. 전 센터 접근."],
            ["자재파트", "자재센터 입출고, 자재 요청, 이동 신청 관리."],
            ["센터장", "사용내역 업로드, 이동 신청, 승인, 자재 요청 신청."],
            ["일반", "이동 신청, 자재 요청, 재고 조회."],
            ["게스트", "재고 조회만 가능 (읽기 전용)."],
        ],
        [30, 144]
    )

    pdf.sub_title("기존 회원 관리")
    pdf.body("[전체 회원 목록] 탭에서 회원을 선택하면 상세 관리 패널이 열립니다.")
    pdf.bullet([
        "이름, 권한, 소속 센터를 변경하고 [저장] 버튼을 누릅니다.",
        "승인 취소: 승인된 회원의 접근을 임시 차단합니다.",
        "삭제: 계정을 완전히 삭제합니다. (삭제 전 확인 필요)",
    ])

    # ── 17. 자주 묻는 질문 ───────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("17", "자주 묻는 질문")

    faqs = [
        ("로그인이 안 됩니다.",
         "아이디와 비밀번호를 다시 확인해보세요.\n비밀번호를 잊으셨다면 [비밀번호 찾기]를 이용하세요."),
        ("회원가입을 했는데 로그인이 안 됩니다.",
         "관리자가 아직 승인하지 않은 상태입니다.\n승인되면 가입 시 입력한 이메일로 알림이 옵니다."),
        ("재고가 실제와 다릅니다.",
         "최신 데이터를 불러오려면 [새로고침] 버튼을 누르거나 F5 키를 눌러 새로 고침하세요."),
        ("갑자기 로그인 화면으로 돌아갑니다.",
         "30분 동안 아무 작업도 하지 않으면 자동으로 로그아웃됩니다.\n다시 로그인하시면 됩니다."),
        ("자재 요청 후 현황을 어디서 볼 수 있나요?",
         "왼쪽 메뉴의 [자재요청현황]에서 확인할 수 있습니다."),
        ("버튼이 보이지 않습니다.",
         "권한에 따라 일부 버튼이 표시되지 않을 수 있습니다.\n필요한 경우 관리자에게 권한 변경을 요청하세요."),
        ("이동 신청을 했는데 취소하고 싶습니다.",
         "[이동 신청 현황] 탭에서 대기중 상태의 신청 건에 [취소] 버튼이 있습니다."),
        ("엑셀 파일 업로드가 안 됩니다.",
         "파일 형식이 .xlsx인지 확인하세요.\n양식 파일을 다시 다운로드하여 사용하면 오류를 줄일 수 있습니다."),
    ]

    for q, a in faqs:
        pdf.set_fill_color(*C_BLUE)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("MG", "B", 10)
        pdf.cell(8, 7, "Q", fill=True, align="C")
        pdf.set_fill_color(*C_LGRAY)
        pdf.set_text_color(*C_DARK)
        pdf.cell(0, 7, "  " + q, fill=True, ln=True)
        pdf.set_fill_color(*C_GREEN)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("MG", "B", 10)
        pdf.cell(8, 6, "A", fill=True, align="C")
        pdf.set_font("MG", "", 9)
        pdf.set_text_color(*C_DARK)
        pdf.multi_cell(0, 6, "  " + a)
        pdf.ln(3)

    return pdf


if __name__ == "__main__":
    out = r"C:\Users\junyo\Desktop\에이텍모빌리티_자재관리시스템_사용가이드_" + datetime.now().strftime("%Y%m%d") + ".pdf"
    pdf = build()
    pdf.output(out)
    print("PDF 생성 완료:", out)
