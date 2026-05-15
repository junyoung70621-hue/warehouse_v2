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
    """전체 페이지 공통 CSS — Industrial Precision 다크 테마."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    html, body, * { font-family:'Noto Sans KR', sans-serif !important; }
    /* ── 0. 사이드바 헤더/네비 제거 ── */
    [data-testid="stSidebarNav"] {
        display: none !important; height: 0 !important; min-height: 0 !important;
        overflow: hidden !important; padding: 0 !important; margin: 0 !important;
    }
    /* display:none 대신 visibility:hidden — position:fixed 자식이 탈출 가능하도록 */
    [data-testid="stSidebarHeader"] {
        visibility: hidden !important; height: 0 !important; min-height: 0 !important;
        overflow: hidden !important; padding: 0 !important; margin: 0 !important;
    }
    button[data-testid="baseButton-headerNoPadding"] { display: none !important; }
    header[data-testid="stHeader"] { visibility: hidden !important; }
    footer, [data-testid="stFooter"] { display: none !important; }
    #MainMenu { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    button[title*="Streamlit"] { display: none !important; }
    a[href*="streamlit.io"] { display: none !important; }

    /* ── 사이드바 폭 고정 (드래그 리사이즈 비활성) ── */
    section[data-testid="stSidebar"] {
        min-width: 220px !important;
        max-width: 220px !important;
    }

    /* ── 사이드바 닫기 버튼 ‹ — collapsedControl과 동일한 div>button 패턴 ── */
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
        visibility: visible !important;
        position: fixed !important;
        top: 78px !important;
        left: 218px !important;
        width: 20px !important;
        height: 36px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        background: #080e1d !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-left: none !important;
        border-radius: 0 5px 5px 0 !important;
        cursor: pointer !important;
        z-index: 1010 !important;
        padding: 0 !important;
        margin: 0 !important;
        transition: background 0.15s, border-color 0.15s !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]:hover {
        background: rgba(225,29,72,0.12) !important;
        border-color: rgba(225,29,72,0.5) !important;
    }
    /* 내부 button: 투명하게, 컨테이너 꽉 채움 */
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {
        background: transparent !important;
        border: none !important;
        width: 100% !important;
        height: 100% !important;
        min-height: 0 !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
        margin: 0 !important;
        white-space: nowrap !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] svg { display: none !important; }
    /* ‹ 문자: 내부 button::after에 부착 (collapsedControl과 동일 패턴) */
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button::after {
        content: "‹";
        color: #64748b;
        font-size: 20px;
        font-weight: 500;
        line-height: 1;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]:hover button::after { color: #e11d48; }
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]::after { content: "" !important; display: none !important; }

    /* ── 사이드바 열기 버튼 › ── */
    [data-testid="collapsedControl"] {
        display: flex !important;
        position: fixed !important;
        top: 78px !important;
        left: 0 !important;
        width: 20px !important;
        height: 36px !important;
        align-items: center !important;
        justify-content: center !important;
        background: #080e1d !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-left: none !important;
        border-radius: 0 5px 5px 0 !important;
        cursor: pointer !important;
        z-index: 1010 !important;
        padding: 0 !important;
        margin: 0 !important;
        transition: background 0.15s, border-color 0.15s !important;
    }
    [data-testid="collapsedControl"]:hover {
        background: rgba(225,29,72,0.12) !important;
        border-color: rgba(225,29,72,0.5) !important;
    }
    [data-testid="collapsedControl"] button {
        background: transparent !important;
        border: none !important;
        width: 100% !important;
        height: 100% !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    [data-testid="collapsedControl"] button svg { display: none !important; }
    [data-testid="collapsedControl"] button::after {
        content: "›";
        color: #64748b;
        font-size: 20px;
        font-weight: 500;
        line-height: 1;
    }
    [data-testid="collapsedControl"]:hover button::after { color: #e11d48; }

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

    /* ── 4. 사이드바 (Industrial Dark) ── */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div,
    section[data-testid="stSidebar"] > div > div { background:#080e1d !important; }
    section[data-testid="stSidebar"] {
        border-right:1px solid rgba(255,255,255,0.06) !important;
        overflow-y:auto !important;
    }
    [data-testid="stSidebarContent"]    { padding-top:0 !important; margin-top:0 !important; }
    [data-testid="stSidebarUserContent"]{ padding-top:0 !important; margin-top:0 !important; }
    section[data-testid="stSidebar"] .block-container  { padding-top:0 !important; margin-top:0 !important; }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { padding-top:0 !important; gap:2px !important; }
    section[data-testid="stSidebar"] > div > div { overflow-y:auto !important; scrollbar-width:none !important; }
    section[data-testid="stSidebar"] > div > div::-webkit-scrollbar { display:none !important; }

    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label { color:#475569 !important; font-size:12px !important; }
    section[data-testid="stSidebar"] hr    { border-color:rgba(255,255,255,0.06) !important; margin:6px 0 !important; }

    section[data-testid="stSidebar"] [data-testid="stSelectbox"] *,
    section[data-testid="stSidebar"] [data-baseweb="select"] * { font-size:13px !important; }
    section[data-testid="stSidebar"] [data-baseweb="select"] > div {
        background:#0f1829 !important; border-color:rgba(255,255,255,0.1) !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] span,
    section[data-testid="stSidebar"] [data-baseweb="select"] div,
    section[data-testid="stSidebar"] [data-baseweb="singleValue"],
    section[data-testid="stSidebar"] [data-baseweb="select"] input { color:#e2e8f0 !important; }
    section[data-testid="stSidebar"] [data-baseweb="select"] svg   { fill:#475569 !important; }

    section[data-testid="stSidebar"] button {
        background:transparent !important; border:none !important;
        color:#ffffff !important; font-weight:400 !important;
        text-align:left !important; justify-content:flex-start !important;
        padding:5px 14px 5px 12px !important; border-radius:4px !important;
        font-size:15px !important; height:auto !important;
        min-height:34px !important; white-space:nowrap !important;
        margin:1px 6px !important; width:calc(100% - 12px) !important;
        border-left:3px solid transparent !important;
    }
    section[data-testid="stSidebar"] button p,
    section[data-testid="stSidebar"] button span,
    section[data-testid="stSidebar"] button div {
        color:#ffffff !important; font-weight:400 !important; font-size:15px !important;
    }
    section[data-testid="stSidebar"] button:hover,
    section[data-testid="stSidebar"] button:hover p,
    section[data-testid="stSidebar"] button:hover span {
        background:rgba(255,255,255,0.06) !important; color:#fff !important;
        border-left-color:rgba(225,29,72,0.4) !important;
    }
    section[data-testid="stSidebar"] button[kind="primary"] {
        background: transparent !important;
        border: none !important; outline: none !important; box-shadow: none !important;
        color: #fff !important; font-weight: 700 !important;
        position: relative !important;
    }
    section[data-testid="stSidebar"] button[kind="primary"] p,
    section[data-testid="stSidebar"] button[kind="primary"] span {
        color: #fff !important; font-weight: 700 !important;
        position: relative !important; z-index: 1 !important;
    }
    section[data-testid="stSidebar"] button[kind="primary"]::before {
        content: "" !important;
        position: absolute !important;
        inset: 0 !important;
        background: rgba(225,29,72,0.25) !important;
        border-radius: 4px !important;
        pointer-events: none !important;
        z-index: 0 !important;
    }

    /* ── 5. 스크롤 ── */
    html, body { overflow-y:auto !important; min-height:100vh !important; }
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewBlockContainer"] { overflow-y:auto !important; height:auto !important; }
    .main { overflow-y:auto !important; min-height:100vh !important; }
    [data-testid="stTabsContent"] { overflow-y:visible !important; padding-bottom:2rem !important; }
    .main .block-container { overflow:visible !important; padding-top:0.6rem !important; padding-bottom:3rem !important; max-width:100% !important; }
    hr { margin:2px 0 4px 0 !important; border-color:rgba(255,255,255,0.07) !important; }

    /* ── 6. 입력/셀렉트 다크 ── */
    div[data-testid="stTextInput"] input {
        font-size:12px !important; height:34px !important;
        background:#1e2d45 !important; border-color:rgba(255,255,255,0.25) !important;
        color:#f1f5f9 !important; border-radius:4px !important;
    }
    div[data-testid="stTextInput"] input::placeholder { color:rgba(255,255,255,0.35) !important; }
    div[data-testid="stTextInput"] input:focus {
        border-color:rgba(225,29,72,0.7) !important;
        box-shadow:0 0 0 2px rgba(225,29,72,0.15) !important;
    }
    div[data-testid="stHorizontalBlock"] button,
    div[data-testid="stHorizontalBlock"] [data-testid="stDownloadButton"] button {
        white-space:nowrap !important; font-size:12px !important;
        padding:0 8px !important; height:32px !important; min-height:32px !important;
        border-radius:4px !important;
    }

    /* ── 7. 데이터 에디터 ── */
    [data-testid="stDataEditor"] { border:1px solid rgba(255,255,255,0.08) !important; border-radius:4px !important; }
    [data-testid="stDataEditor"] th {
        background:#080e1d !important; color:#475569 !important;
        font-weight:700 !important; font-size:11px !important;
        text-transform:uppercase !important; letter-spacing:0.07em !important;
        border-bottom:1px solid rgba(255,255,255,0.1) !important; white-space:nowrap !important;
        position:sticky !important; top:0 !important; z-index:10 !important;
    }
    [data-testid="stDataEditor"] td {
        font-size:12px !important; padding:3px 8px !important;
        color:#cbd5e1 !important; border-bottom:1px solid rgba(255,255,255,0.04) !important;
    }

    /* ── 8. 공통 컴포넌트 ── */
    div[data-testid="stRadio"] label      { font-size:12px !important; }
    div[data-testid="stCaptionContainer"] p { font-size:11px !important; color:#475569 !important; }
    div[data-testid="column"]             { padding:0 2px !important; }
    div[data-testid="stSelectbox"] label  { font-size:12px !important; }
    [data-testid="stMetricValue"]         { font-size:16px !important; }
    [data-testid="stMetricLabel"]         { font-size:11px !important; color:#475569 !important; }
    [data-testid="stVerticalBlockBorderWrapper"] { margin-bottom:4px !important; }

    /* ── 9. 역할 배지 ── */
    .wms-role-badge {
        background:#e11d48 !important; color:#fff !important;
        font-size:10px !important; font-weight:600 !important;
        padding:2px 7px !important; border-radius:10px !important; display:inline-block;
    }

    /* ── 10. 애니메이션 ── */
    @keyframes wms-fadein { from { opacity:0; } to { opacity:1; } }
    @keyframes wms-pulse  {
        0%,100% { opacity:1; box-shadow:0 0 4px #22d3ee; }
        50%     { opacity:0.6; box-shadow:0 0 10px #22d3ee; }
    }
    [data-testid="stAppViewContainer"] { animation:wms-fadein 0.1s ease-out !important; }
    </style>
    """, unsafe_allow_html=True)


def render_sidebar_header():
    """사이드바 헤더 — 별도 렌더링 없음 (JS는 render_top_bar에서 주입)"""
    pass


def render_sidebar_section(label: str):
    """SNB 섹션 구분 레이블 — Industrial Precision."""
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:8px;"
        f"padding:14px 12px 19px 14px;margin-top:2px;'>"
        f"<div style='width:14px;height:1px;background:rgba(225,29,72,0.5);flex-shrink:0;'></div>"
        f"<span style='color:#e2e8f0;font-size:11px;font-weight:700;"
        f"letter-spacing:0.15em;text-transform:uppercase;white-space:nowrap;'>{label}</span>"
        f"<div style='flex:1;height:1px;background:rgba(255,255,255,0.05);'></div>"
        f"</div>",
        unsafe_allow_html=True
    )


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
    section[data-testid="stSidebar"] { top:58px!important; height:calc(100vh - 58px)!important; min-width:220px!important; max-width:220px!important; }
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

    })();
    </script>
    """, unsafe_allow_html=True)
    # 상단바 HTML — Industrial Precision
    st.markdown(f"""
    <div style="position:fixed;top:0;left:0;right:0;height:58px;
                background:rgba(8,14,29,0.95);
                backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
                display:flex;align-items:stretch;z-index:1001;
                border-bottom:1px solid rgba(255,255,255,0.07);
                box-shadow:0 2px 24px rgba(0,0,0,0.5);">
        <div style="width:220px;flex-shrink:0;background:#050b17;
                    display:flex;align-items:center;justify-content:center;
                    padding:0 14px;border-right:1px solid rgba(255,255,255,0.06);">
            {_logo}
        </div>
        <div style="flex:1;display:flex;align-items:center;
                    justify-content:space-between;padding:0 20px;">
            <span style="font-family:'Noto Sans KR',sans-serif;font-size:15px;
                         font-weight:700;color:#e2e8f0;user-select:none;letter-spacing:0.01em;
                         cursor:pointer;" title="사이드바 열기/닫기">
                ≡&nbsp; {title}
            </span>
            <div style="display:flex;align-items:center;gap:18px;">
                <div style="display:flex;align-items:center;gap:7px;">
                    <div style="width:7px;height:7px;border-radius:50%;background:#22d3ee;
                                animation:wms-pulse 2s ease-in-out infinite;"></div>
                    <span style="font-size:9px;color:#22d3ee;font-weight:700;
                                 letter-spacing:0.12em;font-family:'JetBrains Mono',monospace;">
                        SYSTEM: OPERATIONAL
                    </span>
                </div>
                <div style="width:1px;height:20px;background:rgba(255,255,255,0.1);"></div>
                <div style="display:flex;align-items:center;gap:6px;">
                    <span style="font-size:13px;color:#e2e8f0;font-weight:600;">{_uc}</span>
                    <span style="color:#334155;font-size:13px;">·</span>
                    <span style="font-size:13px;color:#e2e8f0;font-weight:600;">{_nm}</span>
                    <span style="color:#334155;font-size:13px;">·</span>
                    <span style="font-size:13px;color:#475569;">{_rl}</span>
                </div>
                <span style="font-size:12px;color:#e2e8f0;font-weight:700;
                             font-family:'JetBrains Mono',monospace;">{_date}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 시범운영 배너 ──────────────────────────────────────────────────────
    st.markdown("""
    <style>
    #wms-notice-banner {
        position: fixed;
        top: 58px; left: 0; right: 0; height: 28px;
        background: linear-gradient(90deg,
            rgba(225,29,72,0.06), rgba(225,29,72,0.13), rgba(225,29,72,0.06));
        border-bottom: 1px solid rgba(225,29,72,0.22);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        z-index: 1000;
    }
    #wms-notice-banner .nb-dot {
        width: 5px; height: 5px; border-radius: 50%;
        background: #e11d48;
        animation: wms-pulse 2s ease-in-out infinite;
        flex-shrink: 0;
    }
    #wms-notice-banner .nb-text {
        font-size: 11px; color: rgba(252,165,165,0.85);
        font-family: 'Noto Sans KR', sans-serif;
        letter-spacing: 0.05em; font-weight: 500;
        user-select: none;
    }
    #wms-notice-banner .nb-close {
        position: absolute; right: 14px;
        background: none; border: none;
        color: rgba(255,255,255,0.28);
        font-size: 14px; cursor: pointer;
        line-height: 1; padding: 2px 5px;
        border-radius: 3px;
        transition: color 0.15s, background 0.15s;
    }
    #wms-notice-banner .nb-close:hover {
        color: rgba(255,255,255,0.8);
        background: rgba(255,255,255,0.06);
    }
    /* 배너 표시 시 사이드바·본문 위치 조정 */
    body.wms-notice-on section[data-testid="stSidebar"] {
        top: 86px !important;
        height: calc(100vh - 86px) !important;
    }
    body.wms-notice-on .main .block-container {
        padding-top: calc(0.8rem + 28px) !important;
    }
    </style>

    <div id="wms-notice-banner">
        <div class="nb-dot"></div>
        <span class="nb-text">시범운영 중 &mdash; 오류 발생 시 관리자에게 문의해 주세요.</span>
        <button id="wms-notice-close" class="nb-close" title="닫기">&#x2715;</button>
    </div>

    <script>
    (function(){
        var KEY = 'wms_notice_v1';
        function lsGet(){ try{ return localStorage.getItem(KEY); }catch(e){ return null; } }
        function lsSet(){ try{ localStorage.setItem(KEY,'1'); }catch(e){} }

        function hideAll(){
            document.querySelectorAll('#wms-notice-banner').forEach(function(el){
                el.style.setProperty('display','none','important');
            });
            document.body.classList.remove('wms-notice-on');
        }
        function showAll(){
            document.querySelectorAll('#wms-notice-banner').forEach(function(el){
                el.style.removeProperty('display');
            });
            document.body.classList.add('wms-notice-on');
        }
        function apply(){
            lsGet() === '1' ? hideAll() : showAll();
        }

        /* document 캡처 이벤트 위임 — 요소 교체/중복에 무관하게 동작 */
        if(!window._wmsNoticeInit){
            window._wmsNoticeInit = true;
            document.addEventListener('click', function(e){
                var t = e.target;
                if(t.id === 'wms-notice-close' ||
                   (t.parentElement && t.parentElement.id === 'wms-notice-close')){
                    e.stopPropagation();
                    e.preventDefault();
                    lsSet();
                    hideAll();
                }
            }, true);
        }

        apply();
        [150,500,1200].forEach(function(t){ setTimeout(apply, t); });
        new MutationObserver(apply).observe(document.body,{childList:true,subtree:true});
    })();
    </script>
    """, unsafe_allow_html=True)


def render_sidebar_user(user: dict):
    """사이드바 하단: 유저 카드 — Industrial Precision."""
    _rl_map = {"admin":"ADMIN","materials":"MATERIALS",
               "manager":"MANAGER","user":"USER","guest":"GUEST"}
    _rl = _rl_map.get(user.get("role","guest"), user.get("role","guest").upper())
    _uc = user.get("assigned_center") or user.get("center","")
    _nm = user.get("name","")
    _init = _nm[:1] if _nm else "U"
    st.markdown(f"""
    <div style="margin:6px 6px 10px 6px;padding:8px 10px;
                background:#0d1526;border:1px solid rgba(255,255,255,0.07);
                border-radius:4px;border-left:3px solid #e11d48;box-sizing:border-box;">
        <div style="display:flex;align-items:center;gap:8px;min-width:0;overflow:hidden;">
            <div style="width:26px;height:26px;border-radius:4px;flex-shrink:0;
                        background:rgba(225,29,72,0.18);border:1px solid rgba(225,29,72,0.35);
                        display:flex;align-items:center;justify-content:center;
                        font-size:12px;font-weight:700;color:#e11d48;">{_init}</div>
            <div style="min-width:0;flex:1;overflow:hidden;">
                <div style="color:#e2e8f0;font-size:11px;font-weight:600;
                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_nm}</div>
                <div style="display:flex;align-items:center;gap:4px;margin-top:2px;
                            min-width:0;overflow:hidden;">
                    <span style="font-size:9px;font-weight:700;color:#e11d48;
                                 letter-spacing:0.06em;font-family:'JetBrains Mono',monospace;
                                 flex-shrink:0;">{_rl}</span>
                    <span style="color:#334155;font-size:9px;flex-shrink:0;">·</span>
                    <span style="color:#475569;font-size:9px;min-width:0;
                                 white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_uc}</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
