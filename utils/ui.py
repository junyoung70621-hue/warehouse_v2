# utils/ui.py
import os
import base64
import streamlit as st

# ── ATEC 로고 base64 (모듈 로드 시 1회만 읽음) ────────────────────────────
def _load_logo() -> str:
    _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "atec_logo.png")
    try:
        with open(_p, "rb") as _f:
            return base64.b64encode(_f.read()).decode()
    except Exception:
        return ""

_LOGO_B64 = _load_logo()


def apply_global_css():
    """전체 페이지 공통 CSS — WMS 스타일."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap');
    html, body, * { font-family:'Noto Sans KR', sans-serif !important; }
    /* ── 0. 사이드바 내부 헤더/네비 완전 제거 ── */
    [data-testid="stSidebarNav"],
    [data-testid="stSidebarHeader"] {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        overflow: hidden !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    /* 사이드바 접기/펼치기 버튼 — JS 클릭용으로 DOM에 유지, 시각적으로만 숨김 */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="collapsedControl"] { visibility:hidden !important; }
    button[data-testid="baseButton-headerNoPadding"] { display: none !important; }

    /* ── 1. 페이지 전환 오버레이 (별도 div로 처리) ── */

    /* ── 2. 전체 세로 스크롤 ── */
    html, body {
        overflow-y: auto !important;
        height: auto !important;
        min-height: 100vh !important;
    }
    [data-testid="stAppViewContainer"] {
        overflow-y: auto !important;
        height: auto !important;
        min-height: 100vh !important;
    }
    [data-testid="stAppViewBlockContainer"] {
        overflow-y: auto !important;
        height: auto !important;
    }
    .main {
        overflow-y: auto !important;
        height: auto !important;
        min-height: 100vh !important;
    }
    .main .block-container {
        overflow: visible !important;
        padding-top: 2.8rem !important;
        padding-bottom: 4rem !important;
        max-width: 100% !important;
    }

    /* ── 3. 타이틀 ── */
    h1, h2, h3 {
        overflow: visible !important;
        line-height: 1.8 !important;
        padding: 4px 0 2px 0 !important;
        margin-bottom: 2px !important;
    }
    hr { margin: 3px 0 8px 0 !important; }

    /* ── 4. 다크 사이드바 (#212529) ── */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div,
    section[data-testid="stSidebar"] > div > div { background: #212529 !important; }
    section[data-testid="stSidebar"] { width:220px !important; min-width:220px !important; overflow-y:auto !important; }

    /* ── 상/하단 공백 제거 (Streamlit 전용 타겟팅) ── */
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    [data-testid="stSidebarContent"] {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    [data-testid="stSidebarUserContent"] {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        padding-top: 0 !important;
        gap: 4px !important;
    }
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label { color:#adb5bd !important; font-size:16px !important; }
    section[data-testid="stSidebar"] hr { border-color:#343a40 !important; margin:8px 0 !important; }
    /* 드롭다운(셀렉트박스) 폰트 크기 고정 — 제외 */
    section[data-testid="stSidebar"] [data-testid="stSelectbox"] *,
    section[data-testid="stSidebar"] [data-baseweb="select"] * { font-size:13px !important; }
    section[data-testid="stSidebar"] [data-baseweb="select"] > div {
        background:#2b3035 !important; border-color:#495057 !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] span,
    section[data-testid="stSidebar"] [data-baseweb="select"] div,
    section[data-testid="stSidebar"] [data-baseweb="singleValue"],
    section[data-testid="stSidebar"] [data-baseweb="select"] input { color:#fff !important; }
    section[data-testid="stSidebar"] [data-baseweb="select"] svg  { fill:#adb5bd !important; }
    section[data-testid="stSidebar"] button {
        background:transparent !important; border:none !important;
        color:#adb5bd !important; text-align:left !important;
        justify-content:flex-start !important;
        padding:6px 12px !important; border-radius:8px !important;
        font-size:16px !important; height:auto !important;
        min-height:36px !important; white-space:nowrap !important;
        margin:2px 0 !important; width:100% !important;
    }
    section[data-testid="stSidebar"] button:hover {
        background:rgba(255,255,255,0.07) !important; color:#f8f9fa !important;
    }
    section[data-testid="stSidebar"] button[kind="primary"] {
        background:#D81B60 !important; color:#fff !important;
        font-weight:600 !important; border-left:3px solid #ff4081 !important;
    }
    /* 사이드바 스크롤 없음 */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div,
    section[data-testid="stSidebar"] > div > div { overflow:hidden !important; }

    /* ── 5. 상단 툴바 버튼 ── */
    div[data-testid="stHorizontalBlock"] button,
    div[data-testid="stHorizontalBlock"] [data-testid="stDownloadButton"] button {
        white-space: nowrap !important;
        font-size: 12px !important;
        padding: 0 8px !important;
        height: 34px !important;
        min-height: 34px !important;
        line-height: 34px !important;
    }
    div[data-testid="stTextInput"] input {
        font-size: 12px !important;
        height: 34px !important;
    }

    /* ── 6. data_editor (팝업 내 미니 테이블) ── */
    [data-testid="stDataEditor"] th {
        background-color: #e8edf5 !important;
        color: #1a237e !important;
        font-weight: 700 !important;
        font-size: 12px !important;
        border-bottom: 2px solid #7986cb !important;
        white-space: nowrap !important;
        position: sticky !important;
        top: 0 !important;
        z-index: 10 !important;
    }
    [data-testid="stDataEditor"] td {
        font-size: 13px !important;
        padding: 2px 8px !important;
    }

    /* ── 7. 공통 컴포넌트 ── */
    div[data-testid="stRadio"] label     { font-size: 12px !important; }
    div[data-testid="stCaptionContainer"] p { font-size: 11px !important; }
    div[data-testid="column"]             { padding: 0 2px !important; }
    div[data-testid="stSelectbox"] label  { font-size: 12px !important; }

    [data-testid="stTabsContent"] {
        overflow-y: visible !important;
        padding-bottom: 2rem !important;
    }

    [data-testid="stMetricValue"] { font-size: 16px !important; }
    [data-testid="stMetricLabel"] { font-size: 11px !important; }

    [data-testid="stVerticalBlockBorderWrapper"] { margin-bottom: 4px !important; }

    /* 역할 배지 흰색 텍스트 */
    .wms-role-badge {
        background: #d81b60 !important;
        color: #ffffff !important;
        font-size: 10px !important;
        font-weight: 600 !important;
        padding: 2px 7px !important;
        border-radius: 10px !important;
        display: inline-block;
    }

    /* ── 페이지 전환 페이드인 ── */
    @keyframes wms-fadein {
        from { opacity: 0; }
        to   { opacity: 1; }
    }
    [data-testid="stAppViewContainer"] {
        animation: wms-fadein 0.1s ease-out !important;
    }
    </style>
    """, unsafe_allow_html=True)


def render_sidebar_header():
    """사이드바 헤더 — 별도 렌더링 없음 (JS는 render_top_bar에서 주입)"""
    pass


def render_top_bar(title: str, user: dict):
    """공통 고정 상단바: ATEC 로고 | 페이지 제목 | 유저 정보/날짜.
    상단바 위치 CSS(header 숨김, sidebar top 58px, 본문 패딩)도 함께 주입."""
    from datetime import datetime
    _now  = datetime.now()
    _days = ["월","화","수","목","금","토","일"]
    _date = f"{_now.year}.{_now.month:02d}.{_now.day:02d} ({_days[_now.weekday()]})"
    _rl_map = {"admin":"관리자","materials":"자재파트",
               "manager":"센터장","user":"일반","guest":"게스트"}
    _rl = _rl_map.get(user.get("role",""), user.get("role",""))
    _uc = user.get("assigned_center") or user.get("center","")
    _nm = user.get("name","")
    _logo = (
        f'<img src="data:image/png;base64,{_LOGO_B64}" '
        f'style="max-width:192px;width:100%;height:auto;display:block;">'
        if _LOGO_B64 else
        '<span style="color:#ced4da;font-size:12px;font-weight:700;">ATEC</span>'
    )
    # 상단바 관련 CSS + 사이드바 패딩 제거 JS 주입
    st.markdown("""
    <style>
    header[data-testid="stHeader"]   { visibility:hidden!important; }
    section[data-testid="stSidebar"] { top:58px!important; height:calc(100vh - 58px)!important; }
    .main .block-container           { padding-top:0.8rem!important; padding-bottom:3rem!important; max-width:100%!important; overflow:visible!important; }
    html, body                       { overflow-y:auto!important; min-height:100vh!important; }
    [data-testid="stAppViewContainer"] { overflow-y:auto!important; }
    </style>
    <script>
    (function(){
        function zapSidebar(){
            var hdr=document.querySelector('[data-testid="stSidebarHeader"]');
            if(hdr){ hdr.style.setProperty('display','none','important'); }
            var nav=document.querySelector('[data-testid="stSidebarNav"]');
            if(nav){ nav.style.setProperty('display','none','important'); }
            var sels=[
                'section[data-testid="stSidebar"] > div',
                'section[data-testid="stSidebar"] > div > div',
                '[data-testid="stSidebarContent"]',
                '[data-testid="stSidebarContent"] > div',
                '[data-testid="stSidebarUserContent"]',
                '[data-testid="stSidebarUserContent"] > div',
                'section[data-testid="stSidebar"] .block-container'
            ];
            sels.forEach(function(s){
                var el=document.querySelector(s);
                if(el){
                    el.style.setProperty('padding-top','0px','important');
                    el.style.setProperty('margin-top','0px','important');
                    el.style.setProperty('padding-bottom','0px','important');
                }
            });
        }
        zapSidebar();
        [200,600,1500].forEach(function(t){setTimeout(zapSidebar,t);});

        /* ── 사이드바 토글 (≡ 클릭) ── */
        function doToggle(){
            var btn=document.querySelector('[data-testid="stSidebarCollapseButton"] button')||
                    document.querySelector('[data-testid="stSidebarCollapseButton"]')||
                    document.querySelector('[data-testid="collapsedControl"] button')||
                    document.querySelector('[data-testid="collapsedControl"]');
            if(btn) btn.click();
        }
        function bindToggle(){
            document.querySelectorAll('[data-wms-menu]').forEach(function(el){
                if(el._wmsBound) return;
                el._wmsBound=true;
                el.addEventListener('click', doToggle);
            });
        }
        bindToggle();
        [200,600,1500].forEach(function(t){setTimeout(bindToggle,t);});
    })();
    </script>
    """, unsafe_allow_html=True)
    # 상단바 HTML
    st.markdown(f"""
    <div style="position:fixed;top:0;left:0;right:0;height:58px;
                display:flex;align-items:stretch;z-index:1001;
                box-shadow:0 2px 8px rgba(0,0,0,0.12);">
        <div style="width:220px;flex-shrink:0;background:#212529;
                    display:flex;align-items:center;justify-content:center;
                    padding:0 14px;border-bottom:1px solid #343a40;">
            {_logo}
        </div>
        <div style="flex:1;background:#ffffff;display:flex;align-items:center;
                    justify-content:space-between;padding:0 24px;
                    border-bottom:1px solid #e0e5ee;">
            <span data-wms-menu="1"
                  style="font-family:'Noto Sans KR',sans-serif;font-size:16px;
                         font-weight:700;color:#1a2035;cursor:pointer;user-select:none;"
                  title="사이드바 열기/닫기">
                ≡&nbsp; {title}
            </span>
            <div style="display:flex;align-items:center;gap:16px;">
                <span style="font-size:13px;color:#333;font-weight:500;">
                    {_uc} {_nm} ({_rl})
                </span>
                <span style="font-size:12px;color:#999;">{_date}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar_user(user: dict):
    """사이드바 하단: 유저 이름·센터·역할 배지"""
    _rl_map = {"admin":"관리자","materials":"자재파트",
               "manager":"센터장","user":"일반","guest":"게스트"}
    _rl = _rl_map.get(user.get("role","guest"), user.get("role","guest"))
    _uc = user.get("assigned_center") or user.get("center","")
    _nm = user.get("name","")
    st.divider()
    st.markdown(f"""
    <div style="padding:4px 4px 10px 4px;">
        <div style="display:flex;align-items:center;gap:6px;">
            <span style="color:#c8cdd8;font-size:13px;font-weight:600;">{_nm}</span>
            <span class="wms-role-badge">{_rl}</span>
        </div>
        <div style="color:#6c757d;font-size:11px;margin-top:3px;">{_uc}</div>
    </div>
    """, unsafe_allow_html=True)
