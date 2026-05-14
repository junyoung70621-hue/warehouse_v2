# utils/mail.py
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import streamlit as st

load_dotenv()
try:
    GMAIL_ADDRESS      = st.secrets["GMAIL_ADDRESS"]
    GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]
except Exception:
    GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

def _send_email(to: str, subject: str, body_html: str):
    """내부 공통 발송 함수."""
    msg = MIMEMultipart("alternative")
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)


def send_temp_password(to_email: str, name: str, temp_pw: str):
    subject = "[에이텍모빌리티 자재관리] 임시 비밀번호 안내"
    body = f"""
    <p>안녕하세요, <b>{name}</b>님.</p>
    <p>요청하신 임시 비밀번호를 안내드립니다.</p>
    <p style="font-size:20px;font-weight:bold;color:#1a73e8;">{temp_pw}</p>
    <p>로그인 후 <b>마이페이지</b>에서 반드시 비밀번호를 변경해 주세요.</p>
    <hr><p style="color:gray;font-size:12px;">에이텍모빌리티 자재관리 자동발송 메일입니다.</p>
    """
    _send_email(to_email, subject, body)


def send_register_complete(to_email: str, name: str, center: str):
    """회원가입 완료 시 신청자에게 발송."""
    subject = "[에이텍모빌리티 자재관리] 회원가입 신청이 완료되었습니다"
    body = f"""
    <p>안녕하세요, <b>{name}</b>님.</p>
    <p>에이텍모빌리티 자재관리 시스템에 회원가입 신청이 정상적으로 접수되었습니다.</p>
    <table border="1" cellpadding="6" cellspacing="0"
           style="border-collapse:collapse; margin:12px 0; font-size:14px;">
      <tr style="background:#e8edf5; color:#1a237e;">
        <th style="padding:6px 14px;">항목</th>
        <th style="padding:6px 14px;">내용</th>
      </tr>
      <tr><td style="padding:5px 14px;">이름</td><td style="padding:5px 14px;"><b>{name}</b></td></tr>
      <tr><td style="padding:5px 14px;">소속 센터</td><td style="padding:5px 14px;">{center}</td></tr>
      <tr><td style="padding:5px 14px;">상태</td><td style="padding:5px 14px; color:#e65100;"><b>관리자 승인 대기 중</b></td></tr>
    </table>
    <p>관리자 승인 후 로그인이 가능합니다. 승인까지 잠시 기다려 주세요.</p>
    <hr>
    <p style="color:gray; font-size:12px;">에이텍모빌리티 자재관리 자동발송 메일입니다.</p>
    """
    _send_email(to_email, subject, body)


def send_register_approved(to_email: str, name: str, center: str):
    """관리자 승인 완료 시 신청자에게 발송."""
    subject = "[에이텍모빌리티 자재관리] 회원가입이 승인되었습니다"
    body = f"""
    <p>안녕하세요, <b>{name}</b>님.</p>
    <p>에이텍모빌리티 자재관리 시스템 회원가입이 <b style="color:#2e7d32;">승인</b>되었습니다.</p>
    <table border="1" cellpadding="6" cellspacing="0"
           style="border-collapse:collapse; margin:12px 0; font-size:14px;">
      <tr style="background:#e8edf5; color:#1a237e;">
        <th style="padding:6px 14px;">항목</th>
        <th style="padding:6px 14px;">내용</th>
      </tr>
      <tr><td style="padding:5px 14px;">이름</td><td style="padding:5px 14px;"><b>{name}</b></td></tr>
      <tr><td style="padding:5px 14px;">소속 센터</td><td style="padding:5px 14px;">{center or '미지정'}</td></tr>
    </table>
    <p>지금 바로 로그인하여 서비스를 이용하실 수 있습니다.</p>
    <hr>
    <p style="color:gray; font-size:12px;">에이텍모빌리티 자재관리 자동발송 메일입니다.</p>
    """
    _send_email(to_email, subject, body)


def send_register_notify_admin(
    to_emails: list,
    name: str,
    username: str,
    email: str,
    center: str,
):
    """회원가입 신청 시 관리자에게 발송."""
    subject = f"[에이텍모빌리티 자재관리] 새 회원가입 신청 — {name} ({center})"
    body = f"""
    <p>안녕하세요.</p>
    <p>새로운 회원가입 신청이 접수되었습니다. WMS 시스템에서 승인 처리해 주세요.</p>
    <table border="1" cellpadding="6" cellspacing="0"
           style="border-collapse:collapse; margin:12px 0; font-size:14px;">
      <tr style="background:#e8edf5; color:#1a237e;">
        <th style="padding:6px 14px;">항목</th>
        <th style="padding:6px 14px;">내용</th>
      </tr>
      <tr><td style="padding:5px 14px;">이름</td><td style="padding:5px 14px;"><b>{name}</b></td></tr>
      <tr><td style="padding:5px 14px;">아이디</td><td style="padding:5px 14px;">{username}</td></tr>
      <tr><td style="padding:5px 14px;">이메일</td><td style="padding:5px 14px;">{email}</td></tr>
      <tr><td style="padding:5px 14px;">소속 센터</td><td style="padding:5px 14px;">{center}</td></tr>
    </table>
    <hr>
    <p style="color:gray; font-size:12px;">에이텍모빌리티 자재관리 자동발송 메일입니다.</p>
    """
    for to in to_emails:
        try:
            _send_email(to, subject, body)
        except Exception:
            pass


def send_material_request(
    to_emails: list,
    from_center: str,
    requester_name: str,
    items: list,
):
    """
    자재 요청 알림 메일.
    items: [{"item_name", "erp_code", "current_qty", "requested_qty"}, ...]
    """
    subject = f"[에이텍모빌리티 자재관리] {from_center} 자재 요청"

    rows_html = ""
    any_short = False
    for it in items:
        short = it["current_qty"] < it["requested_qty"]
        if short:
            any_short = True
        color  = "red"   if short else "green"
        status = "⚠️ 재고부족" if short else "✅ 재고있음"
        rows_html += f"""
        <tr>
          <td style="padding:5px 10px;">{it['item_name']}</td>
          <td style="padding:5px 10px;">{it.get('erp_code') or ''}</td>
          <td style="padding:5px 10px; text-align:right;">{it['current_qty']}</td>
          <td style="padding:5px 10px; text-align:right;"><b>{it['requested_qty']}</b></td>
          <td style="padding:5px 10px; color:{color};">{status}</td>
        </tr>"""

    shortage_block = ""
    if any_short:
        shortage_block = """
        <p style="color:red; font-weight:bold; margin-top:14px;">
          ⚠️ 재고가 부족한 자재가 포함되어 있습니다. 구매 검토가 필요합니다.
        </p>"""

    body = f"""
    <p>안녕하세요.</p>
    <p><b>{from_center}</b>에서 자재 요청이 접수되었습니다.</p>
    <p style="color:#555; font-size:13px;">요청자: {requester_name}</p>
    <table border="1" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse; margin:12px 0; font-size:14px;">
      <thead>
        <tr style="background:#e8edf5; color:#1a237e;">
          <th style="padding:6px 12px;">자재명</th>
          <th style="padding:6px 12px;">ERP코드</th>
          <th style="padding:6px 12px;">현재재고</th>
          <th style="padding:6px 12px;">요청수량</th>
          <th style="padding:6px 12px;">재고상태</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    {shortage_block}
    <p>WMS 시스템에서 확인 후 처리해 주세요.</p>
    <hr>
    <p style="color:gray; font-size:12px;">에이텍모빌리티 자재관리 자동발송 메일입니다.</p>
    """

    for email in to_emails:
        try:
            _send_email(email, subject, body)
        except Exception:
            pass


def send_material_request_approved_to_center(
    to_emails: list,
    from_center: str,
    items: list,
    processed_by_name: str,
):
    """자재 요청 승인 완료 시 해당 센터 전체 인원에게 발송."""
    subject = f"[에이텍모빌리티 자재관리] {from_center} 자재 입고 완료"

    rows_html = ""
    for it in items:
        rows_html += f"""
        <tr>
          <td style="padding:5px 10px;">{it.get('item_name','')}</td>
          <td style="padding:5px 10px; text-align:right;"><b>{it.get('requested_qty',0)}</b></td>
        </tr>"""

    body = f"""
    <p>안녕하세요.</p>
    <p><b>{from_center}</b>의 자재 요청이 승인되어 재고가 업데이트되었습니다.</p>
    <table border="1" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse; margin:12px 0; font-size:14px;">
      <thead>
        <tr style="background:#e8edf5; color:#1a237e;">
          <th style="padding:6px 12px;">자재명</th>
          <th style="padding:6px 12px;">입고수량</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    <p style="color:#555; font-size:13px;">처리자: {processed_by_name}</p>
    <p>WMS 시스템에서 재고를 확인해 주세요.</p>
    <hr>
    <p style="color:gray; font-size:12px;">에이텍모빌리티 자재관리 자동발송 메일입니다.</p>
    """
    for email in to_emails:
        try:
            _send_email(email, subject, body)
        except Exception:
            pass


def send_material_request_cancelled(
    to_emails: list,
    from_center: str,
    requester_name: str,
    items: list,
):
    """자재 요청 취소 시 자재파트·관리자에게 발송."""
    subject = f"[에이텍모빌리티 자재관리] {from_center} 자재 요청 취소"

    rows_html = ""
    for it in items:
        rows_html += f"""
        <tr>
          <td style="padding:5px 10px;">{it.get('item_name','')}</td>
          <td style="padding:5px 10px; text-align:right;">{it.get('requested_qty',0)}</td>
        </tr>"""

    body = f"""
    <p>안녕하세요.</p>
    <p><b>{from_center}</b>의 자재 요청이 신청자에 의해 <b style="color:#c62828;">취소</b>됐습니다.</p>
    <p style="color:#555; font-size:13px;">취소자: {requester_name}</p>
    <table border="1" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse; margin:12px 0; font-size:14px;">
      <thead>
        <tr style="background:#e8edf5; color:#1a237e;">
          <th style="padding:6px 12px;">자재명</th>
          <th style="padding:6px 12px;">요청수량</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    <p>해당 요청은 처리하지 않으셔도 됩니다.</p>
    <hr>
    <p style="color:gray; font-size:12px;">에이텍모빌리티 자재관리 자동발송 메일입니다.</p>
    """
    for email in to_emails:
        try:
            _send_email(email, subject, body)
        except Exception:
            pass


def send_material_request_reply(
    to_email: str,
    requester_name: str,
    from_center: str,
    status: str,
    items: list,
    reply_message: str = "",
):
    """자재 요청 처리 결과 회신 메일."""
    STATUS_KO = {
        "approved": ("✅ 승인", "#2e7d32"),
        "rejected": ("❌ 거절", "#c62828"),
        "on_hold":  ("⏸️ 보류",  "#e65100"),
        "pending":  ("⏳ 대기중", "#555"),
    }
    label, color = STATUS_KO.get(status, (status, "#555"))
    subject = f"[에이텍모빌리티 자재관리] 자재 요청 처리 결과 — {label}"

    rows_html = ""
    for it in items:
        short  = it.get("current_qty", 0) < it.get("requested_qty", 0)
        s_col  = "red"   if short else "green"
        s_text = "⚠️ 재고부족" if short else "✅ 충분"
        rows_html += f"""
        <tr>
          <td style="padding:5px 10px;">{it.get('item_name','')}</td>
          <td style="padding:5px 10px; text-align:right;">{it.get('requested_qty',0)}</td>
          <td style="padding:5px 10px; color:{s_col};">{s_text}</td>
        </tr>"""

    reply_block = ""
    if reply_message and reply_message.strip():
        reply_block = f"""
        <p style="margin-top:14px;"><b>담당자 메시지:</b></p>
        <p style="background:#f5f5f5; padding:10px 14px;
                  border-left:4px solid #7986cb; font-size:14px;">
          {reply_message}
        </p>"""

    body = f"""
    <p>안녕하세요, <b>{requester_name}</b>님.</p>
    <p><b>{from_center}</b>의 자재 요청이 처리되었습니다.</p>
    <p style="font-size:20px; font-weight:bold; color:{color};">{label}</p>
    <table border="1" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse; margin:12px 0; font-size:14px;">
      <thead>
        <tr style="background:#e8edf5; color:#1a237e;">
          <th style="padding:6px 12px;">자재명</th>
          <th style="padding:6px 12px;">요청수량</th>
          <th style="padding:6px 12px;">재고상태</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    {reply_block}
    <hr>
    <p style="color:gray; font-size:12px;">에이텍모빌리티 자재관리 자동발송 메일입니다.</p>
    """
    _send_email(to_email, subject, body)


def send_purchase_request(
    to_emails: list,
    requester_name: str,
    requester_center: str,
    items: list,
    reason: str,
    requested_at: str,
):
    """구매 요청 알림 메일. items: [{"품명", "수량", "링크"}, ...]"""
    subject = f"[에이텍모빌리티 자재관리] 구매 요청 — {requester_name} ({requester_center})"

    rows_html = ""
    for i, it in enumerate(items, 1):
        link = str(it.get("링크") or "")
        link_cell = (f'<a href="{link}">{link[:60]}{"..." if len(link) > 60 else ""}</a>'
                     if link else "-")
        rows_html += f"""
        <tr>
          <td style="padding:5px 10px;text-align:center;">{i}</td>
          <td style="padding:5px 10px;">{it.get("품명","")}</td>
          <td style="padding:5px 10px;text-align:right;">{it.get("수량","")}</td>
          <td style="padding:5px 10px;font-size:12px;">{link_cell}</td>
        </tr>"""

    reason_block = (f'<p style="margin-top:10px;"><b>구매사유:</b> {reason}</p>'
                    if reason else "")
    body = f"""
    <p>안녕하세요.</p>
    <p><b>{requester_name}</b> ({requester_center})님으로부터 구매 요청이 접수되었습니다.</p>
    <p style="color:#555;font-size:13px;">요청일시: {requested_at}</p>
    {reason_block}
    <table border="1" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;margin:12px 0;font-size:14px;">
      <thead>
        <tr style="background:#e8edf5;color:#1a237e;">
          <th style="padding:6px 12px;">No</th>
          <th style="padding:6px 12px;">품명</th>
          <th style="padding:6px 12px;">수량</th>
          <th style="padding:6px 12px;">링크</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    <p>WMS 시스템에서 확인해 주세요.</p>
    <hr>
    <p style="color:gray;font-size:12px;">에이텍모빌리티 자재관리 자동발송 메일입니다.</p>
    """
    for email in to_emails:
        try:
            _send_email(email, subject, body)
        except Exception:
            pass


def send_purchase_request_reply(
    to_email: str,
    requester_name: str,
    items: list,
    status: str,
    reply_msg: str = "",
):
    """구매 요청 처리 결과 회신 메일."""
    STATUS_KO = {
        "in_progress": ("🔄 처리중", "#1565c0"),
        "completed":   ("✅ 완료",   "#2e7d32"),
        "rejected":    ("❌ 거절",   "#c62828"),
    }
    label, color = STATUS_KO.get(status, (status, "#555"))
    subject = f"[에이텍모빌리티 자재관리] 구매 요청 처리 결과 — {label}"

    rows_html = ""
    for i, it in enumerate(items, 1):
        link = str(it.get("링크") or "")
        link_cell = (f'<a href="{link}">{link[:60]}{"..." if len(link) > 60 else ""}</a>'
                     if link else "-")
        rows_html += f"""
        <tr>
          <td style="padding:5px 10px;text-align:center;">{i}</td>
          <td style="padding:5px 10px;">{it.get("품명","")}</td>
          <td style="padding:5px 10px;text-align:right;">{it.get("수량","")}</td>
          <td style="padding:5px 10px;font-size:12px;">{link_cell}</td>
        </tr>"""

    msg_block = ""
    if reply_msg and reply_msg.strip():
        msg_block = f"""
        <p style="margin-top:14px;"><b>담당자 메시지:</b></p>
        <p style="background:#f5f5f5;padding:10px 14px;
                  border-left:4px solid #7986cb;font-size:14px;">
          {reply_msg.strip()}
        </p>"""

    body = f"""
    <p>안녕하세요, <b>{requester_name}</b>님.</p>
    <p>구매 요청이 처리되었습니다.</p>
    <p style="font-size:20px;font-weight:bold;color:{color};">{label}</p>
    <table border="1" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;margin:12px 0;font-size:14px;">
      <thead>
        <tr style="background:#e8edf5;color:#1a237e;">
          <th style="padding:6px 12px;">No</th>
          <th style="padding:6px 12px;">품명</th>
          <th style="padding:6px 12px;">수량</th>
          <th style="padding:6px 12px;">링크</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    {msg_block}
    <hr>
    <p style="color:gray;font-size:12px;">에이텍모빌리티 자재관리 자동발송 메일입니다.</p>
    """
    try:
        _send_email(to_email, subject, body)
    except Exception:
        pass


def send_transfer_request(to_email: str, item_name: str,
                           from_center: str, to_center: str, qty: int):
    subject = "[에이텍모빌리티 자재관리] 자재 이동 신청 알림"
    body = f"""
    <p>자재 이동 신청이 접수되었습니다.</p>
    <table border="1" cellpadding="6" style="border-collapse:collapse;">
      <tr><td>자재명</td><td><b>{item_name}</b></td></tr>
      <tr><td>출발 센터</td><td>{from_center}</td></tr>
      <tr><td>도착 센터</td><td>{to_center}</td></tr>
      <tr><td>수량</td><td>{qty}개</td></tr>
    </table>
    <p>WMS 시스템에서 승인 처리해 주세요.</p>
    <hr><p style="color:gray;font-size:12px;">에이텍모빌리티 자재관리 자동발송 메일입니다.</p>
    """
    _send_email(to_email, subject, body)