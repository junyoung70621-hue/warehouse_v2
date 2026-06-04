# utils/notice.py
import os
import base64
import streamlit as st

NEW_URL = "https://amwarehouse.vercel.app/"


def _logo_b64(filename: str = "logo.png") -> str:
    _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filename)
    try:
        with open(_p, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""


def render_migration_notice():
    """Vercel 이전 안내 화면을 렌더링한다 (로그인 화면 대체용)."""
    st.markdown("""
    <style>
    #MainMenu, header, footer { visibility: hidden; }
    [data-testid="stSidebar"], [data-testid="stSidebarNav"],
    [data-testid="collapsedControl"] { display: none !important; }
    .main .block-container { max-width: 520px !important; padding-top: 4rem !important; }
    .notice-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-top: 4px solid #D3004F;
        border-radius: 12px;
        padding: 32px 28px;
        text-align: center;
        box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    }
    .notice-card h2 { color: #F8FAFC; font-size: 22px; margin: 8px 0 4px 0; }
    .notice-card p  { color: #CBD5E1; font-size: 15px; line-height: 1.7; margin: 6px 0; }
    .notice-url {
        display: inline-block;
        background: #0F172A;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 8px 14px;
        color: #38BDF8;
        font-size: 14px;
        margin: 12px 0 4px 0;
        word-break: break-all;
    }
    .notice-badge {
        display: inline-block;
        background: rgba(211,0,79,0.15);
        color: #FF4D8A;
        font-size: 12px;
        font-weight: 600;
        padding: 4px 12px;
        border-radius: 999px;
        letter-spacing: 0.5px;
    }
    div[data-testid="stLinkButton"] a {
        background: #D3004F !important;
        color: #FFFFFF !important;
        border: none !important;
        font-size: 16px !important;
        font-weight: 700 !important;
        height: 48px !important;
        border-radius: 8px !important;
    }
    div[data-testid="stLinkButton"] a:hover { background: #B00043 !important; }
    </style>
    """, unsafe_allow_html=True)

    logo = _logo_b64("logo.png")
    if logo:
        st.markdown(
            f'<img src="data:image/png;base64,{logo}" '
            f'style="max-width:240px;width:100%;height:auto;display:block;margin:0 auto 24px auto;">',
            unsafe_allow_html=True
        )

    st.markdown(f"""
    <div class="notice-card">
        <span class="notice-badge">📢 시스템 이전 안내</span>
        <h2>자재관리 시스템이 이전되었습니다</h2>
        <p>더 빠르고 편리한 새 시스템으로 이전 작업이 완료되었습니다.<br>
        아래 버튼을 눌러 새 주소로 접속해 주세요.</p>
        <div class="notice-url">{NEW_URL}</div>
        <p style="color:#94A3B8;font-size:13px;">
        🔑 <b>아이디 / 비밀번호는 기존과 동일</b>하게 사용하실 수 있습니다.</p>
    </div>
    """, unsafe_allow_html=True)

    st.write("")
    st.link_button("🚀 새 시스템으로 이동하기", NEW_URL, use_container_width=True)

    st.markdown(
        "<p style='text-align:center;color:#64748B;font-size:12px;margin-top:16px;'>"
        "즐겨찾기(북마크)를 새 주소로 변경해 주시기 바랍니다.</p>",
        unsafe_allow_html=True
    )
