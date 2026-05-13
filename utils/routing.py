# utils/routing.py

CENTERS = [
    "자재센터", "강서센터", "강북센터",
    "강동센터", "강남센터", "택시지원파트", "리페어팀"
]

REGIONAL = {"강서센터", "강북센터", "강동센터", "강남센터"}
SPECIAL  = {"택시지원파트", "리페어팀"}

# 권한별 입출고 가능 여부
# 자재센터만 입출고 가능, 나머지는 이동 신청만 가능
CAN_STOCK = {"admin", "materials", "manager"}


def get_allowed_destinations(from_center: str) -> list[str]:
    """
    출발 센터에 따라 이동 가능한 목적지 목록 반환.
    경로 1: 자재센터 → 나머지 6개 전부
    경로 2: 지역 센터 → 자재센터 + 지역 센터끼리
    경로 3: 특수 파트 → 자재센터만
    """
    if from_center == "자재센터":
        return [c for c in CENTERS if c != "자재센터"]

    if from_center in REGIONAL:
        allowed = {"자재센터"} | (REGIONAL - {from_center})
        return [c for c in CENTERS if c in allowed]

    if from_center in SPECIAL:
        return ["자재센터"]

    return []


def can_do_stock(role: str) -> bool:
    """입출고 권한 여부 (자재센터 전용 기능)"""
    return role in CAN_STOCK


def can_approve(role: str) -> bool:
    """이동 신청 승인 권한 여부"""
    return role in {"admin", "materials", "manager"}