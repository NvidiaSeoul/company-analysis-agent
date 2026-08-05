from langchain_tavily import TavilySearch
import os
from dotenv import load_dotenv
load_dotenv()

def tavily_search(query):
    # 검색
    tv_search = TavilySearch(max_results = 5)
    search_docs = tv_search.invoke(query + " 기사")

    #print("="*80)
    # url 만 별도 저장
    url_list = [res['url'] for res in search_docs['results']]
    #print(url_list)

    # news가 있는 url 만 필터링
    #news_urls = [u for u in url_list if 'news' in u.lower()]

    return url_list
