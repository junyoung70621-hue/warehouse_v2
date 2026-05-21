# utils/permissions.py
"""
WMS V2.0 역할 기반 권한 제어 (RBAC)
======================================
admin     : 전체 7개 센터 모든 기능
materials : 자재센터 입출고 + 자재센터發 이동 신청 + 자재센터 관련 승인
manager   : 소속 센터(assigned_center) 이동 신청 + 본인 센터로 들어오는 이동 승인
user      : 이동 신청만 (자기 센터)
guest     : 읽기 전용
"""

from __future__ import annotations

MAIN_HUB = "자재센터"


def get_role(user: dict) -> str:
    return user.get("role", "guest")


def get_center(user: dict) -> str:
    """소속 센터: assigned_center 우선, 없으면 center"""
    return user.get("assigned_center") or user.get("center") or ""


# ══════════════════════════════════════════════════════════════════════════
# 입출고 권한
# ══════════════════════════════════════════════════════════════════════════

def can_stock_in_out(user: dict, target_center: str) -> bool:
    """
    직접 입출고(수량 수정) 가능 여부.
    - admin     : 모든 센터 가능
    - materials : 자재센터만 가능
    - manager/user/guest : 불가 (이동으로만 재고 변경)
    """
    role = get_role(user)
    if role == "admin":
        return True
    if role == "materials":
        return target_center == MAIN_HUB
    return False


# ══════════════════════════════════════════════════════════════════════════
# 이동 신청 권한
# ══════════════════════════════════════════════════════════════════════════

def can_request_transfer(user: dict, from_center: str) -> bool:
    """
    이동 신청 가능 여부 — 보내는 쪽(from_center) 기준.
    - admin     : 모든 센터에서 신청 가능 (외부창고 포함)
    - materials : 자재센터 + 외부창고에서 신청 가능 (외부→자재센터 반납)
    - manager   : 본인 소속 센터에서만 (외부창고 제외)
    - user      : 본인 소속 센터에서만 (외부창고 제외)
    - guest     : 불가
    """
    from utils.routing import EXTERNAL
    role   = get_role(user)
    center = get_center(user)

    if role == "admin":
        return True
    if role == "materials":
        return from_center == MAIN_HUB or from_center in EXTERNAL
    if role in ("manager", "user"):
        return from_center == center and from_center not in EXTERNAL
    return False


# ══════════════════════════════════════════════════════════════════════════
# 이동 승인 권한 — 받는 쪽(to_center) 기준
# ══════════════════════════════════════════════════════════════════════════

def can_approve_transfer(user: dict, from_center: str, to_center: str) -> bool:
    """
    이동 신청 승인 가능 여부.

    [핵심 규칙] 승인은 '받는 센터' 담당자가 눌러야 한다.
    - admin     : 모든 이동 승인 가능
    - materials : 자재센터가 받는(to) 이동만 승인
                  (자재센터→타센터는 자재파트가 신청하므로 별도 승인 불필요)
                  예외: admin이 없을 때를 대비해 자재센터 발신도 승인 가능
    - manager   : 본인 소속 센터가 받는(to_center) 이동만 승인 가능
    - user/guest: 불가
    """
    role   = get_role(user)
    center = get_center(user)

    if role == "admin":
        return True
    if role == "materials":
        # 자재센터 또는 외부창고가 관여된 이동 승인 가능
        from utils.routing import EXTERNAL
        return (to_center == MAIN_HUB or from_center == MAIN_HUB
                or to_center in EXTERNAL or from_center in EXTERNAL)
    if role == "manager":
        # 본인 센터로 들어오는 이동만 승인 (외부창고 제외)
        from utils.routing import EXTERNAL
        return to_center == center and center not in EXTERNAL
    return False


# ══════════════════════════════════════════════════════════════════════════
# 이동 내역 필터링
# ══════════════════════════════════════════════════════════════════════════

def filter_transfers_for_user(user: dict, transfers: list) -> list:
    """
    권한에 따라 보여줄 이동 신청 목록 필터링.
    - admin     : 전체
    - materials : 자재센터 관련 전체 (from 또는 to가 자재센터)
    - manager   : 본인 센터 관련만 (from 또는 to가 본인 센터)
    - user      : 본인이 신청한 것만
    - guest     : 빈 목록
    """
    role    = get_role(user)
    center  = get_center(user)
    user_id = user.get("id", "")

    if role == "admin":
        return transfers
    if role == "materials":
        return [t for t in transfers
                if t.get("from_center") == MAIN_HUB
                or t.get("to_center")   == MAIN_HUB]
    if role == "manager":
        return [t for t in transfers
                if t.get("from_center") == center
                or t.get("to_center")   == center]
    if role == "user":
        return [t for t in transfers
                if t.get("requester_id") == user_id]
    return []


# ══════════════════════════════════════════════════════════════════════════
# 센터 선택 제한
# ══════════════════════════════════════════════════════════════════════════

def get_viewable_centers(user: dict) -> list:
    """
    사이드바 센터 선택 드롭다운에 표시할 센터 목록.
    - admin/materials : 외부창고 포함 전체 (NO_WAREHOUSE 제외)
    - guest           : 외부창고 제외 전체
    - manager/user    : 본인 소속 센터만 (외부창고 소속 불가)
    """
    from utils.routing import CENTERS, NO_WAREHOUSE_CENTERS, EXTERNAL
    role   = get_role(user)
    center = get_center(user)

    if role in ("admin", "materials"):
        return [c for c in CENTERS if c not in NO_WAREHOUSE_CENTERS]
    if role in ("manager", "user"):
        base = [c for c in CENTERS if c not in NO_WAREHOUSE_CENTERS and c not in EXTERNAL]
        return [center] if center in CENTERS and center not in EXTERNAL else base
    # guest
    return [c for c in CENTERS if c not in NO_WAREHOUSE_CENTERS and c not in EXTERNAL]
