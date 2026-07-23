import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

OUT_DIR = ROOT / "out"

NAVER_BASE_URL = "https://naverapihub.apigw.ntruss.com"

# --- Pinterest v5 (수요신호 보조 축, NAVER와 별개 스케일). ad account US/USD. ---
PINTEREST_BASE_URL = "https://api.pinterest.com"
PINTEREST_REGION = "US"            # KR 리전 없음 — US 프록시. note에 명기.
PINTEREST_AD_ACCOUNT = "549770618335"
# keyword metrics: 임의 키워드 월간 검색량 버킷. cashmere/merino류는 코퍼스 갭(EMPTY) —
# 요청/응답 diff로 미검출 신호를 정직 표기. Pinterest US 영문 코퍼스라 영문 키워드.
PINTEREST_KW_METRICS_KEYWORDS = [
    "cashmere sweater", "cashmere cardigan", "knitwear", "cardigan",
    "cashmere", "merino wool", "quince cashmere",
]
# 니트 관련 카테고리 enum (53주 시계열 수요). SPEC_V2 검증 목록.
PINTEREST_CATEGORIES = ["SWEATERS_AND_CARDIGANS", "SCARVES_AND_SHAWLS"]


@dataclass(frozen=True)
class Brand:
    name: str
    url: str
    channel: str
    purpose: str
    auto_collect: bool = True


# SPEC_V2 §9.1 cashmere-reference target 11개. §9.2: Le Cashmere 제외(정확한 활성
# 상품 소스 미확보 — Brand.md 확인). PLUSH'MERE는 Instagram 대신 코오롱몰 target으로 이동.
BRANDS: list[Brand] = [
    Brand("guestinresidence", "https://guestinresidence.com/", "공식몰", "Young & Trendy 캐시미어 디자인"),
    Brand("Extreme cashmere", "https://extreme-cashmere.com/", "공식몰", "컬러 조합"),
    Brand("&Daughter", "https://www.and-daughter.com/", "공식몰", "룩북, 브랜드 컨셉, 브루클린 감성"),
    Brand("Lisa Yang", "https://us.lisa-yang.com/", "공식몰", "아시아 고객 선호 가능 디자인"),
    Brand("Arch4", "https://www.arch4.co.uk/", "공식몰", "베이직과 차별화된 디테일"),
    Brand("Iris Von Arnim", "https://irisvonarnim.com/us/", "공식몰", "Brushed Cashmere 라인"),
    Brand("LE17 SEPTEMBRE", "https://en.le17septembre.com/", "공식몰", "베이직과 차별화된 디테일"),
    Brand("Quince", "https://www.quince.com/women/cashmere", "공식몰", "소재와 기본 아이템 구성"),
    Brand("cashmereinlove", "https://www.cashmereinlove.com/", "공식몰", "브라렛, 레깅스 등 독특한 아이템"),
    Brand("COS", "https://www.cos.com/en-us/women/knitwear", "공식몰", "다양한 니트웨어 아이디어"),
    Brand("PLUSH'MERE", "https://www.kolonmall.com/Brands/PLUSHMERE", "코오롱몰", "Colorblock 스타일"),
]

# §9.2 제외 브랜드 — 상품 분석 target 아님. NAVER 수요 축(BRAND_KEYWORD_GROUPS)에서는
# 별도 신호로 유지.
EXCLUDED_BRANDS: list[Brand] = [
    Brand("Le Cashmere", "https://www.kolonmall.com/Brands/LECASHMERE", "유통몰",
          "정확한 활성 상품 소스 미확보(§9.2)", auto_collect=False),
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

# Search Trend 아이템 수요 — 시그니처·유사 상품 축. Shopping Insight 키워드 집계가
# 데이터 0을 반환(실측 2026-07-21)해 search_trend로 측정. 별도 요청(정규화 분리).
ITEM_KEYWORD_GROUPS = [
    {"groupName": "캐시미어 니트", "keywords": ["캐시미어니트", "캐시미어 니트"]},
    {"groupName": "캐시미어 가디건", "keywords": ["캐시미어가디건", "캐시미어 가디건"]},
    {"groupName": "캐시미어 스웨터", "keywords": ["캐시미어스웨터", "캐시미어 스웨터"]},
    {"groupName": "니트 베스트", "keywords": ["니트베스트", "니트조끼"]},
    {"groupName": "니트 원피스", "keywords": ["니트원피스", "캐시미어원피스"]},
]

# Search Trend 브랜드 수요 — 별도 요청 (카테고리 키워드와 한 요청에 섞으면
# ratio 최대=100 정규화에 브랜드 신호가 묻힘). 벤치마크 브랜드 국문 검색어.
BRAND_KEYWORD_GROUPS = [
    {"groupName": "COS", "keywords": ["COS니트", "코스니트", "COS가디건", "코스 니트"]},
    {"groupName": "Le Cashmere", "keywords": ["르캐시미어", "르캐시미어니트", "르캐시미어 니트"]},
    {"groupName": "Quince", "keywords": ["퀸스캐시미어", "퀸스 캐시미어", "퀸스니트"]},
    {"groupName": "Lisa Yang", "keywords": ["리사양니트", "리사양 니트", "리사양캐시미어", "리사양 캐시미어"]},
    {"groupName": "Extreme Cashmere", "keywords": ["익스트림캐시미어", "익스트림 캐시미어"]},
]

# 네이버쇼핑 cat_id: 패션의류 > 여성의류 > 니트/스웨터.
# 2026-07-20 live 검증됨: shopping_category 200 + title "여성 니트/스웨터" 반환 확인.
SHOPPING_CAT_ID = "50000804"
SHOPPING_CAT_NAME = "여성 니트/스웨터"

# 권위 매체 타겟 쿼리 — include_domains=T1+T2로 직격 (트렌드 근거 확보용, 영문 매체라 영문).
# generic 쿼리는 아무 도메인이나 물어와 §2 근거가 전멸했던 실측(2026-07-21) 교정.
AUTHORITY_QUERIES = [
    "cashmere knitwear trends fall winter 2026",
    "knitwear color trend 2026",
    "sweater silhouette trend 2026",
    "luxury cashmere brands market",
    "fall winter 2026 runway knitwear",
    "best knitwear fashion week 2026",
]

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
TIER2_DOMAINS = (  # 에디토리얼 (ccTLD 변종 포함 — 실측서 vogue.co.uk/graziadaily.co.uk 발견)
    "vogue.com", "vogue.co.uk", "harpersbazaar.com", "harpersbazaar.co.uk",
    "elle.com", "graziamagazine.com", "grazia.co.uk", "graziadaily.co.uk",
)

# 스테디셀러 신호 전용 커머스-에디토리얼 화이트리스트 (오너 승인 2026-07-21).
# 판매신호("best-selling" 등) 근거로만 인정 — 트렌드 근거로는 여전히 불가(T4 유지).
STEADY_SOURCES = (
    "realsimple.com", "instyle.com", "whowhatwear.com", "refinery29.com",
    "glamour.com", "marieclaire.com",
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
MAX_CRAWL_URLS = 26
MAX_NAVER_CALLS = 6
CRAWL_TIMEOUT_SEC = 60
MAX_PER_DOMAIN = 5

# --- RSS (SPEC_V3 §5.1) ---
# WWD 태그피드가 유일한 타깃 소스. crochet/sweaters/cardigan은 WWD 태그 어휘가
# 아니라 빈 200을 반환하므로 넣지 않는다(2026-07-23 실측).
WWD_TAG_FEEDS = {
    "cashmere": "https://wwd.com/tag/cashmere/feed/",
    "knitwear": "https://wwd.com/tag/knitwear/feed/",
    "wool": "https://wwd.com/tag/wool/feed/",
}
# 글로시는 전체 피드만 살아있음(섹션 피드 전부 404) — 키워드 필터 필수.
GLOSSY_FEEDS = {
    "vogue": "https://www.vogue.com/feed/rss",
    "harpersbazaar": "https://www.harpersbazaar.com/rss/all.xml/",
    "elle": "https://www.elle.com/rss/all.xml/",
}
KNIT_FILTER_TERMS = [
    "knit", "knitwear", "cashmere", "sweater", "cardigan", "wool",
    "crochet", "pointelle", "mohair", "alpaca", "merino",
]
ARTICLES_PATH = OUT_DIR / "articles.jsonl"
MAX_CONCEPTS = 20  # LLM#1 concept 상한 (V2 §21.2 예산 파생)

# --- M2 concept 측정 (SPEC_V3 §7) ---
MAX_CONCEPT_TREND_CALLS = 4   # concepts ≤20 ÷ 요청당 5그룹 = 4 (V2 §21 weekly 예산)

# --- 방향/델타 경계값 (SPEC_V3 §8.3 — 판정 정합은 결정론 소유, §9.2 소량 베이스 캡) ---
DELTA_FLAT_BAND_PCT = 10.0   # |delta| < 10% → flat(→). 오너 튜닝 가능 상수.
SMALL_BASE_MEAN = 3.0        # 직전4주 평균 < 3 → small_base(△), delta_pct 미산출(과장 금지)

# --- M4 저장 (SPEC_V3 §9) ---
DB_PATH = OUT_DIR / "trend.db"   # sqlite 파일 1개. 배포 전환 시 pgvector — driver 뒤 (§9.3)

# --- M3 합성 3분류 경계 (SPEC_V3 §8.3 — 판정 정합은 결정론 소유) ---
SUPPLY_SCARCE_MAX = 2       # 수요 상승 + 공급 count ≤ 2 = 수요-공급 갭(기회 신호)
DELTA_TOLERANCE_PCT = 0.1   # validator 숫자(변동%) 대조 허용 오차
