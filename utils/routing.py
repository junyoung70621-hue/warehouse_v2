# utils/routing.py

CENTERS = [
    "자재센터", "강서센터", "강북센터",
    "강동센터", "강남센터", "택시지원파트", "리페어팀", "AFC지원파트", "고속/시외",
    "대전센터", "토스", "고객지원사업부",
    "에이텍본사", "티머니", "외부창고",
]

REGIONAL = {"강서센터", "강북센터", "강동센터", "강남센터"}
SPECIAL  = {"택시지원파트", "리페어팀", "AFC지원파트", "고속/시외", "대전센터", "토스", "고객지원사업부"}
# 외부 창고 — 자재센터·admin만 이동 가능
EXTERNAL = {"에이텍본사", "티머니", "외부창고"}

# 재고 없음 — 창고 뷰·이동 대상에서 제외
NO_WAREHOUSE_CENTERS = {"고객지원사업부"}

# 권한별 입출고 가능 여부
# 자재센터만 입출고 가능, 나머지는 이동 신청만 가능
CAN_STOCK = {"admin", "materials", "manager"}


def get_allowed_destinations(from_center: str) -> list[str]:
    """
    출발 센터에 따라 이동 가능한 목적지 목록 반환.
    경로 1: 자재센터     → 모든 센터(외부창고 포함)
    경로 2: 외부창고     → 자재센터만 (반납)
    경로 3: 지역 센터   → 자재센터 + 지역 센터끼리 (외부창고 제외)
    경로 4: 특수 파트   → 자재센터만
    """
    if from_center == "자재센터":
        return [c for c in CENTERS if c != "자재센터" and c not in NO_WAREHOUSE_CENTERS]

    if from_center in EXTERNAL:
        return ["자재센터"]

    if from_center in REGIONAL:
        allowed = {"자재센터"} | (REGIONAL - {from_center})
        return [c for c in CENTERS if c in allowed and c not in NO_WAREHOUSE_CENTERS]

    if from_center in SPECIAL:
        return ["자재센터"]

    return []


def can_do_stock(role: str) -> bool:
    """입출고 권한 여부 (자재센터 전용 기능)"""
    return role in CAN_STOCK


def can_approve(role: str) -> bool:
    """이동 신청 승인 권한 여부"""
    return role in {"admin", "materials", "manager"}