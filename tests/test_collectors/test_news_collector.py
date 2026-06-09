from __future__ import annotations

import pytest
import requests

from src.collectors.news_collector import (
    NewsArticle,
    _parse_news_html,
    fetch_stock_news,
)

# ---------------------------------------------------------------------------
# HTML 픽스처
# ---------------------------------------------------------------------------

_VALID_HTML = """
<table class="type5">
  <tbody>
    <tr>
      <td class="title">
        <a href="/item/news_read.naver?code=005930&amp;officeId=001&amp;articleId=123">
          삼성전자 실적 호조
        </a>
      </td>
      <td class="info">연합뉴스</td>
      <td class="date">2026.06.04 09:30</td>
    </tr>
    <tr>
      <td class="title">
        <a href="https://n.news.naver.com/article/001/456">반도체 업황 개선</a>
      </td>
      <td class="info">한국경제</td>
      <td class="date">2026.06.03 15:20</td>
    </tr>
    <tr>
      <td class="title">
        <a href="/item/news_read.naver?code=005930&amp;officeId=001&amp;articleId=789">
          주가 신고가 갱신
        </a>
      </td>
      <td class="info">매일경제</td>
      <td class="date">2026.06.03 10:15</td>
    </tr>
  </tbody>
</table>
"""

_NO_TABLE_HTML = "<html><body><p>뉴스 테이블 없음</p></body></html>"
_EMPTY_TABLE_HTML = '<table class="type5"><tbody></tbody></table>'
_ROW_NO_TITLE_HTML = """
<table class="type5">
  <tbody>
    <tr>
      <td class="info">언론사</td>
      <td class="date">2026.06.04 09:30</td>
    </tr>
    <tr>
      <td class="title"><a href="/news/1">정상 기사</a></td>
      <td class="date">2026.06.04 08:00</td>
    </tr>
  </tbody>
</table>
"""


# ---------------------------------------------------------------------------
# _parse_news_html 단위 테스트
# ---------------------------------------------------------------------------


class TestParseNewsHtml:
    def test_parses_all_articles(self):
        articles = _parse_news_html(_VALID_HTML, max_articles=10)
        assert len(articles) == 3

    def test_article_fields(self):
        articles = _parse_news_html(_VALID_HTML, max_articles=10)
        first = articles[0]
        assert first.title == "삼성전자 실적 호조"
        assert first.published_at == "2026.06.04 09:30"

    def test_relative_link_prepended_with_base_url(self):
        articles = _parse_news_html(_VALID_HTML, max_articles=10)
        assert articles[0].link.startswith("https://finance.naver.com")

    def test_absolute_link_unchanged(self):
        articles = _parse_news_html(_VALID_HTML, max_articles=10)
        assert articles[1].link == "https://n.news.naver.com/article/001/456"

    def test_max_articles_limit(self):
        articles = _parse_news_html(_VALID_HTML, max_articles=2)
        assert len(articles) == 2

    def test_no_table_returns_empty_list(self):
        assert _parse_news_html(_NO_TABLE_HTML, max_articles=10) == []

    def test_empty_table_returns_empty_list(self):
        assert _parse_news_html(_EMPTY_TABLE_HTML, max_articles=10) == []

    def test_row_without_title_skipped(self):
        articles = _parse_news_html(_ROW_NO_TITLE_HTML, max_articles=10)
        assert len(articles) == 1
        assert articles[0].title == "정상 기사"

    def test_returns_news_article_instances(self):
        articles = _parse_news_html(_VALID_HTML, max_articles=10)
        assert all(isinstance(a, NewsArticle) for a in articles)


# ---------------------------------------------------------------------------
# fetch_stock_news 통합 테스트 (requests 모킹)
# ---------------------------------------------------------------------------


class TestFetchStockNews:
    def _mock_response(self, mocker, html: str, status_code: int = 200):
        mock_resp = mocker.MagicMock()
        mock_resp.status_code = status_code
        mock_resp.text = html
        mock_resp.encoding = "euc-kr"
        mock_resp.raise_for_status = mocker.MagicMock()
        if status_code >= 400:
            mock_resp.raise_for_status.side_effect = requests.HTTPError(
                response=mock_resp
            )
        return mock_resp

    def test_returns_articles_on_success(self, mocker):
        mock_resp = self._mock_response(mocker, _VALID_HTML)
        mocker.patch("src.collectors.news_collector.requests.get", return_value=mock_resp)

        articles = fetch_stock_news("005930", company_name="삼성전자", max_articles=10)
        assert len(articles) == 3
        assert articles[0].title == "삼성전자 실적 호조"

    def test_passes_stock_code_as_query_param(self, mocker):
        mock_get = mocker.patch(
            "src.collectors.news_collector.requests.get",
            return_value=self._mock_response(mocker, _VALID_HTML),
        )
        fetch_stock_news("005930")
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs["params"]["code"] == "005930"

    def test_graceful_fallback_on_http_error(self, mocker):
        mocker.patch(
            "src.collectors.news_collector.requests.get",
            side_effect=requests.HTTPError("404"),
        )
        result = fetch_stock_news("000000")
        assert result == []

    def test_graceful_fallback_on_connection_error(self, mocker):
        mocker.patch(
            "src.collectors.news_collector.requests.get",
            side_effect=requests.ConnectionError("network error"),
        )
        result = fetch_stock_news("000000")
        assert result == []

    def test_graceful_fallback_on_timeout(self, mocker):
        mocker.patch(
            "src.collectors.news_collector.requests.get",
            side_effect=requests.Timeout("timeout"),
        )
        result = fetch_stock_news("000000")
        assert result == []

    def test_graceful_fallback_on_empty_table(self, mocker):
        mock_resp = self._mock_response(mocker, _EMPTY_TABLE_HTML)
        mocker.patch("src.collectors.news_collector.requests.get", return_value=mock_resp)
        result = fetch_stock_news("000001")
        assert result == []

    def test_max_articles_respected(self, mocker):
        mock_resp = self._mock_response(mocker, _VALID_HTML)
        mocker.patch("src.collectors.news_collector.requests.get", return_value=mock_resp)
        result = fetch_stock_news("005930", max_articles=1)
        assert len(result) == 1
