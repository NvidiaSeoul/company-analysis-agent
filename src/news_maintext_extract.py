import requests
import trafilatura
from playwright.sync_api import sync_playwright
import re

def extract_main_text(html: str) -> str:
    return trafilatura.extract(html, favor_recall=True) or ""


def fetch_html_requests(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MyCrawler/1.0)"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text

def fetch_html_playwright(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=20000)
        html = page.content()
        browser.close()
    return html



def crawl_article(url: str) -> str:
    # 1) 빠른 방법 먼저
    html = fetch_html_requests(url)
    text = extract_main_text(html)
    if text and len(text) > 200:   # 본문 최소 길이 기준(임의)
        return text

    # 2) JS 렌더링 fallback
    html = fetch_html_playwright(url)
    text = extract_main_text(html)
    return text or ""

def crawl_maintext_extract(news_urls):
    newsmaintextlist = []
    for u in news_urls:
        try:
            t = crawl_article(u)
            #print(u, "=>", len(t), "chars")
            # print(t)
            # print("\n" + "-" * 80)
            newsmaintextlist.append(t)
        except Exception as e:
            #print("FAIL", u, e)
            pass

    return newsmaintextlist

def filter_valid_strings(items: list[str]) -> list[str]:
    korean_pattern = re.compile(r'[가-힣]')

    return [
        s for s in items
        if isinstance(s, str) and korean_pattern.search(s)
    ]


if __name__ == "__main__":
    urls = [
        "https://www.sedaily.com/NewsView/2H1S0MPQJ4",
        "https://www.segye.com/newsView/20251218505285?OutUrl=google",
    ]

    result = crawl_maintext_extract(urls)
    print(result)