import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

OUT_DIR = ROOT / "out"

NAVER_BASE_URL = "https://naverapihub.apigw.ntruss.com"


@dataclass(frozen=True)
class Brand:
    name: str
    url: str
    channel: str
    purpose: str
    auto_collect: bool = True


# SPEC.md §10 cashmere-reference seed data 그대로. 값 임의 변경 금지.
BRANDS: list[Brand] = [
    Brand("guestinresidence", "https://guestinresidence.com/", "공식몰", "Young & Trendy 캐시미어 디자인"),
    Brand("Extreme cashmere", "https://extreme-cashmere.com/", "공식몰", "컬러 조합"),
    Brand("&Daughter", "https://www.and-daughter.com/", "공식몰", "룩북, 브랜드 컨셉, 브루클린 감성"),
    Brand("Lisa Yang", "https://us.lisa-yang.com/", "공식몰", "아시아 고객 선호 가능 디자인"),
    Brand("Arch4", "https://www.arch4.co.uk/", "공식몰", "베이직과 차별화된 디테일"),
    Brand("Le Cashmere", "https://www.kolonmall.com/Brands/LECASHMERE", "유통몰", "룩북 컬러 조합"),
    Brand("Iris Von Arnim", "https://irisvonarnim.com/us/", "공식몰", "Brushed Cashmere 라인"),
    Brand("LE17 SEPTEMBRE", "https://en.le17septembre.com/", "공식몰", "베이직과 차별화된 디테일"),
    Brand("Quince", "https://www.quince.com/women/cashmere", "공식몰", "소재와 기본 아이템 구성"),
    Brand("cashmereinlove", "https://www.cashmereinlove.com/", "공식몰", "브라렛, 레깅스 등 독특한 아이템"),
    Brand("COS", "https://www.cos.com/en-us/women/knitwear", "공식몰", "다양한 니트웨어 아이디어"),
    Brand("PLUSH'MERE", "https://www.instagram.com/plushmere/?hl=en", "Instagram", "Colorblock 스타일", auto_collect=False),
]

# --- NAVER 연령 코드 (SPEC.md DataLab Client 절. 두 API 코드 체계 혼용 금지) ---
SEARCH_TREND_AGES = ["4", "5", "6"]   # Search Trend 25~39세
SHOPPING_AGES = ["20", "30"]          # Shopping Insight 20~39세 (25~39 정확 표현 불가)

# Search Trend: 최대 5개 그룹, 그룹당 최대 20개 검색어
SEARCH_KEYWORD_GROUPS = [
    {"groupName": "캐시미어", "keywords": ["캐시미어", "캐시미어니트", "캐시미어스웨터"]},
    {"groupName": "니트웨어", "keywords": ["니트", "스웨터", "가디건"]},
    {"groupName": "프리미엄소재", "keywords": ["홀가먼트", "램스울", "메리노울"]},
]

# Shopping Insight 키워드별: 최대 5개 그룹, 그룹당 검색어 1개
SHOPPING_KEYWORDS = ["캐시미어니트", "캐시미어가디건", "캐시미어스웨터", "여성니트", "캐시미어코트"]

# 네이버쇼핑 cat_id: 패션의류 > 여성의류 > 니트/스웨터.
# 2026-07-20 live 검증됨: shopping_category 200 + title "여성 니트/스웨터" 반환 확인.
SHOPPING_CAT_ID = "50000804"
SHOPPING_CAT_NAME = "여성 니트/스웨터"

TAVILY_QUERIES = [
    "cashmere knitwear trends 2026 women",
    "여성 캐시미어 니트 트렌드 2026",
    "cashmere sweater color trends fall winter 2026",
    "캐시미어 브랜드 니트 신상",
    "extreme cashmere new collection",
    "quince cashmere women sweater review",
    "홀가먼트 캐시미어 니트",
    "cashmere knitwear silhouette trend",
]

# 소스 권위 티어 (MDA-10). 트렌드 근거는 T1·T2만 인정 — T3=벤치마크(공식몰), T4=저권위(웹·블로그).
# 국내 동향은 별도 축(NAVER datalab/API)에서만 근거로 취급, 웹 크롤 근거로는 T4.
TIER1_DOMAINS = (  # 업계지 (trade)
    "businessoffashion.com", "voguebusiness.com", "wwd.com",
)
TIER2_DOMAINS = (  # 에디토리얼
    "vogue.com", "harpersbazaar.com", "elle.com", "graziamagazine.com", "grazia.co.uk",
)

# 분석 조건 (POC_SPEC §5 고정)
ANALYSIS = {
    "category": "여성 니트웨어 (캐시미어 중심)",
    "target": "한국 여성 25~39세",
    "price_range": "20만~70만원",
    "period_weeks": 8,
    "focus": "경쟁 아이템, 컬러 조합, 주요 소재, 독특한 캐시미어 아이템",
}


def period() -> tuple[str, str]:
    """최근 8주. (start, end) ISO date 문자열."""
    end = date.today()
    start = end - timedelta(weeks=ANALYSIS["period_weeks"])
    return start.isoformat(), end.isoformat()


# --- 예산 (POC_SPEC §7. 초과 시 자르고 진행) ---
MAX_TAVILY_QUERIES = 8
MAX_CRAWL_URLS = 20
MAX_NAVER_CALLS = 6
CRAWL_TIMEOUT_SEC = 60
MAX_PER_DOMAIN = 5
