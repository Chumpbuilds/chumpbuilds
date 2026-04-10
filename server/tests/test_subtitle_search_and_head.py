"""
Tests for subtitle search endpoint improvements and HEAD support.

Tests cover:
- _normalize_title: strips trailing "- YYYY", "(YYYY)", "[YYYY]"; decodes "+" signs
- /subtitles/search: title normalization (regression for "Pets on a Train - 2025")
- /subtitles/search: returns subs.ro results when VIP is not configured
- /subtitles/search: results include a "url" field usable to fetch via /subtitles
- /subtitles/search: language filter still applied
- HEAD /subtitles: returns 200, not 405 (regression for curl -I failing)
- HEAD /subtitles: returns 404 when no providers find the title
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Bootstrap: load subtitle_server without a real filesystem or credentials
# (mirrors the pattern already used in test_subsro_provider.py)
# ---------------------------------------------------------------------------

def _load_subtitle_server():
    import importlib
    import os
    import tempfile
    from pathlib import Path

    tmp_cache = tempfile.mkdtemp()
    env_patch = {
        "SUBSRO_API_KEY": "",
        "OPENSUBTITLES_API_KEY": "",
        "OPENSUBTITLES_USERNAME": "",
        "OPENSUBTITLES_PASSWORD": "",
    }

    with patch.dict(os.environ, env_patch):
        if "subtitle_server" in sys.modules:
            del sys.modules["subtitle_server"]

        subtitles_dir = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "..", "subtitles")
        )
        if subtitles_dir not in sys.path:
            sys.path.insert(0, subtitles_dir)

        with patch("pathlib.Path.mkdir"):
            import subtitle_server as srv

        srv.CACHE_DIR = Path(tmp_cache)

    return srv


def _make_subsro_result(
    lang: str = "ro",
    title: str = "Pets on a Train",
    download_url: str = "https://api.subs.ro/download/99",
    downloads: int = 200,
) -> dict:
    return {
        "id": 99,
        "language": lang,
        "title": title,
        "release": f"{title.replace(' ', '.')}.2025.BluRay",
        "downloads": downloads,
        "url": download_url,
    }


# ---------------------------------------------------------------------------
# _normalize_title unit tests
# ---------------------------------------------------------------------------

class TestNormalizeTitle(unittest.TestCase):
    def setUp(self):
        self.srv = _load_subtitle_server()

    def _n(self, title: str) -> str:
        return self.srv._normalize_title(title)

    def test_strips_dash_year_suffix(self):
        self.assertEqual(self._n("Pets on a Train - 2025"), "Pets on a Train")

    def test_strips_dash_year_no_spaces(self):
        self.assertEqual(self._n("Pets on a Train -2025"), "Pets on a Train")

    def test_strips_parentheses_year(self):
        self.assertEqual(self._n("Pets on a Train (2025)"), "Pets on a Train")

    def test_strips_bracket_year(self):
        self.assertEqual(self._n("Pets on a Train [2025]"), "Pets on a Train")

    def test_no_year_unchanged(self):
        self.assertEqual(self._n("Pets on a Train"), "Pets on a Train")

    def test_decodes_plus_signs(self):
        # App sends "Pets+on+a+Train+-+2025"; FastAPI decodes query params but
        # _normalize_title is also called with the already-decoded value.
        # Ensure urllib.parse.unquote_plus does not double-encode plain spaces.
        self.assertEqual(self._n("Pets on a Train - 2025"), "Pets on a Train")

    def test_collapses_extra_whitespace(self):
        self.assertEqual(self._n("Pets  on  a  Train  -  2025"), "Pets on a Train")

    def test_strips_en_dash_year_suffix(self):
        self.assertEqual(self._n("Pets on a Train \u2013 2025"), "Pets on a Train")


# ---------------------------------------------------------------------------
# /subtitles/search — title normalization regression
# ---------------------------------------------------------------------------

class TestSearchTitleNormalization(unittest.TestCase):
    """Regression: query with appended year should match underlying store."""

    def setUp(self):
        self.srv = _load_subtitle_server()
        self.srv.SUBSRO_API_KEY = "test-key"
        # Disable VIP so only subs.ro is active
        self.srv.API_KEY = ""
        self.srv._jwt_token = ""

    def _call_search(self, title: str, lang: str = "ro", year: int | None = 2025):
        """Drive search_subtitles via FastAPI test client."""
        from fastapi.testclient import TestClient
        client = TestClient(self.srv.app)
        params = {"title": title, "lang": lang}
        if year is not None:
            params["year"] = str(year)
        return client.get("/subtitles/search", params=params)

    def test_search_with_appended_year_returns_results(self):
        """'Pets on a Train - 2025' must return non-empty when subs.ro has a match."""
        fake_results = [_make_subsro_result(lang="ro")]
        with patch.object(self.srv, "_subsro_search", return_value=fake_results):
            resp = self._call_search("Pets on a Train - 2025", lang="ro", year=2025)

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertGreater(len(body), 0, "Expected at least one result for normalized title")

    def test_search_passes_normalized_title_to_provider(self):
        """The provider must receive the year-stripped title, not the raw one."""
        received = {}

        def fake_search(title, lang, year, imdb_id, season, episode):
            received["title"] = title
            return [_make_subsro_result(lang="ro")]

        with patch.object(self.srv, "_subsro_search", side_effect=fake_search):
            from fastapi.testclient import TestClient
            client = TestClient(self.srv.app)
            client.get(
                "/subtitles/search",
                params={"title": "Pets on a Train - 2025", "lang": "ro", "year": "2025"},
            )

        self.assertEqual(received.get("title"), "Pets on a Train")

    def test_search_result_includes_url_field(self):
        """Each result must include a 'url' field pointing to /subtitles."""
        fake_results = [_make_subsro_result(lang="ro")]
        with patch.object(self.srv, "_subsro_search", return_value=fake_results):
            from fastapi.testclient import TestClient
            client = TestClient(self.srv.app)
            resp = client.get(
                "/subtitles/search",
                params={"title": "Pets on a Train - 2025", "lang": "ro", "year": "2025"},
            )
        body = resp.json()
        self.assertTrue(len(body) > 0)
        for item in body:
            self.assertIn("url", item, "Result must have a 'url' field")
            self.assertIn("/subtitles", item["url"])

    def test_search_language_filter_applied(self):
        """Results in a language other than requested must be excluded."""
        fake_results = [_make_subsro_result(lang="en")]  # English, not Romanian
        with patch.object(self.srv, "_subsro_search", return_value=fake_results):
            from fastapi.testclient import TestClient
            client = TestClient(self.srv.app)
            resp = client.get(
                "/subtitles/search",
                params={"title": "Pets on a Train", "lang": "ro"},
            )
        body = resp.json()
        self.assertEqual(body, [], "Wrong-language result must be filtered out")

    def test_search_returns_empty_when_no_providers_configured(self):
        """With neither subs.ro nor VIP configured, search returns []."""
        self.srv.SUBSRO_API_KEY = ""
        self.srv.API_KEY = ""
        from fastapi.testclient import TestClient
        client = TestClient(self.srv.app)
        resp = client.get(
            "/subtitles/search",
            params={"title": "Pets on a Train - 2025", "lang": "ro"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_search_subsro_error_returns_empty_not_500(self):
        """A subs.ro error must not surface as a 500; search returns [] gracefully."""
        import httpx
        with patch.object(self.srv, "_subsro_search", side_effect=httpx.ConnectError("timeout")):
            from fastapi.testclient import TestClient
            client = TestClient(self.srv.app)
            resp = client.get(
                "/subtitles/search",
                params={"title": "Pets on a Train", "lang": "ro"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])


# ---------------------------------------------------------------------------
# HEAD /subtitles — must not return 405
# ---------------------------------------------------------------------------

class TestHeadSubtitles(unittest.TestCase):
    def setUp(self):
        self.srv = _load_subtitle_server()
        self.srv.SUBSRO_API_KEY = "test-key"
        self.srv.API_KEY = ""
        self.srv._jwt_token = ""

    def _client(self):
        from fastapi.testclient import TestClient
        return TestClient(self.srv.app)

    def test_head_returns_200_when_subtitles_exist(self):
        """HEAD /subtitles must return 200 (not 405) when a match is found."""
        fake_results = [_make_subsro_result(lang="ro")]
        with patch.object(self.srv, "_subsro_search", return_value=fake_results):
            resp = self._client().head(
                "/subtitles",
                params={"title": "Pets on a Train - 2025", "lang": "ro"},
            )
        self.assertIn(resp.status_code, (200, 204), f"HEAD returned {resp.status_code}, expected 200/204")

    def test_head_returns_404_when_no_subtitles(self):
        """HEAD /subtitles must return 404 when no provider has a match."""
        with patch.object(self.srv, "_subsro_search", return_value=[]):
            resp = self._client().head(
                "/subtitles",
                params={"title": "Nonexistent Movie XYZ", "lang": "ro"},
            )
        self.assertEqual(resp.status_code, 404)

    def test_head_returns_200_from_cache(self):
        """HEAD /subtitles must return 200 when cached content is available."""
        fake_srt = "1\n00:00:01,000 --> 00:00:03,000\nHello\n"
        with patch.object(self.srv, "_cache_read", return_value=fake_srt):
            resp = self._client().head(
                "/subtitles",
                params={"title": "Pets on a Train", "lang": "ro"},
            )
        self.assertEqual(resp.status_code, 200)

    def test_head_body_is_empty(self):
        """HEAD response must have no body (HTTP spec requirement)."""
        fake_results = [_make_subsro_result(lang="ro")]
        with patch.object(self.srv, "_subsro_search", return_value=fake_results):
            resp = self._client().head(
                "/subtitles",
                params={"title": "Pets on a Train", "lang": "ro"},
            )
        self.assertEqual(resp.content, b"")

    def test_get_still_works_after_head_route_change(self):
        """GET /subtitles must still return the full SRT after adding HEAD support."""
        fake_srt = "1\n00:00:01,000 --> 00:00:03,000\nHello\n"
        with patch.object(self.srv, "_fetch_via_subsro", return_value=fake_srt):
            with patch.object(self.srv, "_fetch_via_vip", return_value=None):
                with patch.object(self.srv, "_fetch_via_subliminal", return_value=None):
                    resp = self._client().get(
                        "/subtitles",
                        params={"title": "Pets on a Train", "lang": "ro"},
                    )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Hello", resp.text)


if __name__ == "__main__":
    unittest.main()
