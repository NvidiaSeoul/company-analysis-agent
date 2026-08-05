import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse, parse_qs, urlunparse, urlencode

# -----------------------------
# 1) 기사로 인정할 패턴(필요시 계속 추가)
# -----------------------------
ARTICLE_REGEXES = [
    # 네이버 뉴스
    re.compile(r"^https?://n\.news\.naver\.com/(article|mnews/article)/\d+/\d+"),
    re.compile(r"^https?://m\.news\.naver\.com/(article|mnews/article)/\d+/\d+"),

    # 예: 뉴스프라임 (newsprime) - 사용자가 준 예시
    re.compile(r"^https?://www\.newsprime\.co\.kr/news/article/\?no=\d+"),

    # 흔한 언론사/뉴스 사이트 기사 경로 패턴들(범용)
    re.compile(r"^https?://[^/]+/news/article/"),         # /news/article/...
    re.compile(r"^https?://[^/]+/article/"),              # /article/...
    re.compile(r"^https?://[^/]+/news/view/"),            # /news/view/...
    re.compile(r"^https?://[^/]+/view/"),                 # /view/...
]

# -----------------------------
# 2) 제외할 패턴(비기사/노이즈)
# -----------------------------
EXCLUDE_REGEXES = [
    re.compile(r"/(login|logout|join|signup)(/|$)", re.I),
    re.compile(r"/(search|query)(/|$)", re.I),
    re.compile(r"/(comment|comments)(/|$)", re.I),
    re.compile(r"/(photo|gallery|video)(/|$)", re.I),  # 필요시 조정
]

EXCLUDE_SCHEMES = {"javascript", "mailto", "tel", "data"}

# -----------------------------
# 3) URL 정규화 (중복 제거를 더 잘하기 위해)
#    - fragment(#...) 제거
#    - utm_*, fbclid 등 트래킹 파라미터 제거
#    - (옵션) 쿼리 정렬
# -----------------------------
TRACKING_KEYS_PREFIX = ("utm_",)
TRACKING_KEYS_EXACT = {"fbclid", "gclid", "igshid", "ref", "spm", "from"}

def normalize_url(url: str) -> str:
    try:
        p = urlparse(url)
        if p.scheme and p.scheme.lower() in EXCLUDE_SCHEMES:
            return ""

        # fragment 제거
        p = p._replace(fragment="")

        # 쿼리 파라미터 정리
        qs = parse_qs(p.query, keep_blank_values=True)

        cleaned = {}
        for k, v in qs.items():
            lk = k.lower()
            if lk in TRACKING_KEYS_EXACT:
                continue
            if any(lk.startswith(pref) for pref in TRACKING_KEYS_PREFIX):
                continue
            cleaned[k] = v

        # 정렬 + 재조립
        query = urlencode(sorted((k, vv) for k, vals in cleaned.items() for vv in vals))
        p = p._replace(query=query)

        return urlunparse(p)
    except Exception:
        return ""

# -----------------------------
# 4) "기사 URL" 판별기
#    - 정규식 매치
#    - 그리고 제외 패턴 걸러내기
# -----------------------------
def is_article_url(url: str) -> bool:
    try:
        p = urlparse(url)
        if not p.scheme or not p.netloc:
            return False
        if p.scheme.lower() in EXCLUDE_SCHEMES:
            return False

        # 제외 먼저
        for ex in EXCLUDE_REGEXES:
            if ex.search(url):
                return False

        # 기사 패턴 확인
        for rx in ARTICLE_REGEXES:
            if rx.search(url):
                return True

        # ---- 추가 휴리스틱 (정규식에 안 걸려도 기사 가능성이 높은 경우) ----
        # 1) path에 article/news가 있고 숫자 id가 들어간 경우 (너무 공격적이면 끄세요)
        path = p.path.lower()
        if ("article" in path or "news" in path) and re.search(r"\d{5,}", url):
            return True

        # 2) 쿼리에 no= / idx= / id= 같은 숫자 키가 있는 경우
        qs = parse_qs(p.query)
        for key in ("no", "idx", "id", "aid"):
            if key in qs and any(re.fullmatch(r"\d{3,}", x) for x in qs[key]):
                return True

        return False
    except Exception:
        return False

# -----------------------------
# 5) BeautifulSoup soup에서 기사 링크만 추출
# -----------------------------
def extract_article_links(new_query) -> list[str]:
    base_url = 'https://search.naver.com/search.naver?where=news&ie=utf8&sm=nws_hty&query={}'.format(new_query)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    # 1) HTML 가져오기
    resp = requests.get(base_url, headers=headers, timeout=10)
    resp.raise_for_status()

    # 2) soup 생성
    soup = BeautifulSoup(resp.text, "lxml")


    found = []
    seen = set()

    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue

        full = urljoin(base_url, href)
        norm = normalize_url(full)
        if not norm:
            continue

        if not is_article_url(norm):
            continue

        if norm in seen:
            continue
        seen.add(norm)
        found.append(norm)

    return found


if __name__ == "__main__":

    # 3) 기사 링크 추출
    article_links = extract_article_links()

    print(f"기사 수: {len(article_links)}")
    for link in article_links[:10]:
        print(link)