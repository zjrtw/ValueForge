from __future__ import annotations

from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from src.utils.logger import get_logger

log = get_logger(__name__)

_NEWS_URL = "https://finance.naver.com/item/news_news.nhn"
_BASE_URL = "https://finance.naver.com"
_DEFAULT_MAX_ARTICLES = 10
_REQUEST_TIMEOUT = 15
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}


@dataclass
class NewsArticle:
    title: str
    link: str
    published_at: str  # 형식: YYYY.MM.DD HH:MM (네이버 금융 표시 형식)


def fetch_stock_news(
    stock_code: str,
    company_name: str = "",
    max_articles: int = _DEFAULT_MAX_ARTICLES,
) -> list[NewsArticle]:
    """네이버 금융에서 종목 뉴스 헤드라인을 수집합니다.

    Args:
        stock_code:   6자리 종목코드 (예: '005930')
        company_name: 종목명 — 로그 출력용
        max_articles: 최대 수집 기사 수 (기본 10, 최대 의미 있는 범위 5~10)

    Returns:
        NewsArticle 리스트. 수집·파싱 실패 시 빈 리스트 반환 (graceful fallback).
    """
    try:
        articles = _fetch_naver_finance_news(stock_code, max_articles)
        log.info(
            "news_fetched",
            stock_code=stock_code,
            company_name=company_name,
            count=len(articles),
        )
        return articles
    except Exception as exc:
        log.warning(
            "news_fetch_failed",
            stock_code=stock_code,
            company_name=company_name,
            error=str(exc),
        )
        return []


def _fetch_naver_finance_news(stock_code: str, max_articles: int) -> list[NewsArticle]:
    """네이버 금융 뉴스 페이지를 HTTP 요청 후 파싱합니다."""
    response = requests.get(
        _NEWS_URL,
        params={"code": stock_code, "page": "1"},
        headers=_HEADERS,
        timeout=_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    response.encoding = "euc-kr"  # 네이버 금융 인코딩
    return _parse_news_html(response.text, max_articles)


def _parse_news_html(html: str, max_articles: int) -> list[NewsArticle]:
    """네이버 금융 뉴스 HTML에서 기사 제목·링크·날짜를 추출합니다.

    네이버 금융 뉴스 테이블 구조 (type5):
        <table class="type5">
          <tbody>
            <tr>
              <td class="title"><a href="/item/news_read.naver?...">헤드라인</a></td>
              <td class="info">언론사명</td>
              <td class="date">YYYY.MM.DD HH:MM</td>
            </tr>
          </tbody>
        </table>
    """
    soup = BeautifulSoup(html, "lxml")
    articles: list[NewsArticle] = []

    table = soup.select_one("table.type5")
    if table is None:
        log.debug("news_table_not_found", html_snippet=html[:200])
        return []

    for row in table.select("tbody tr"):
        title_tag = row.select_one("td.title a")
        date_tag = row.select_one("td.date")

        if title_tag is None:
            continue

        title = title_tag.get_text(strip=True)
        if not title:
            continue

        href = str(title_tag.get("href", ""))
        link = href if href.startswith("http") else f"{_BASE_URL}{href}"
        published_at = date_tag.get_text(strip=True) if date_tag else ""

        articles.append(NewsArticle(title=title, link=link, published_at=published_at))

        if len(articles) >= max_articles:
            break

    return articles
