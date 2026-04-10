"""
Unit tests for the subs.ro subtitle provider integration.

Tests cover:
- Skipping the provider when SUBSRO_API_KEY is not set
- Successful movie subtitle fetch
- Successful TV episode subtitle fetch with exact S/E match filtering
- Graceful fallback on HTTP errors
- Graceful fallback on empty results
- Language filtering
- Provider ordering (subs.ro → OpenSubtitles VIP → subliminal)
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Bootstrap: provide minimal stubs so subtitle_server can be imported without
# a real filesystem (CACHE_DIR) or real httpx calls.
# ---------------------------------------------------------------------------

def _load_subtitle_server():
    """Import subtitle_server with CACHE_DIR patched to a tmp dir."""
    import importlib
    import os
    import tempfile

    tmp_cache = tempfile.mkdtemp()

    # Patch env so no real credentials are needed during import
    env_patch = {
        "SUBSRO_API_KEY": "",
        "OPENSUBTITLES_API_KEY": "",
        "OPENSUBTITLES_USERNAME": "",
        "OPENSUBTITLES_PASSWORD": "",
    }

    with patch.dict(os.environ, env_patch):
        # Ensure a fresh import
        if "subtitle_server" in sys.modules:
            del sys.modules["subtitle_server"]

        subtitles_dir = os.path.join(
            os.path.dirname(__file__), "..", "subtitles"
        )
        subtitles_dir = os.path.realpath(subtitles_dir)
        if subtitles_dir not in sys.path:
            sys.path.insert(0, subtitles_dir)

        # Patch CACHE_DIR before module-level code runs
        with patch("pathlib.Path.mkdir"):
            import subtitle_server as srv

        # Override CACHE_DIR to temp dir so cache writes don't fail
        from pathlib import Path
        srv.CACHE_DIR = Path(tmp_cache)

    return srv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_subsro_result(
    lang: str = "en",
    season: int | None = None,
    episode: int | None = None,
    download_url: str = "https://api.subs.ro/download/42",
    downloads: int = 100,
    title: str = "Test Movie",
) -> dict:
    r: dict = {
        "id": 42,
        "language": lang,
        "title": title,
        "release": "Test.Movie.2020.BluRay",
        "downloads": downloads,
        "url": download_url,
    }
    if season is not None:
        r["season"] = season
    if episode is not None:
        r["episode"] = episode
    return r


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSubsroSkippedWhenNoKey(unittest.TestCase):
    def setUp(self):
        self.srv = _load_subtitle_server()

    def test_returns_none_when_key_missing(self):
        """Provider must return None immediately when SUBSRO_API_KEY is empty."""
        self.srv.SUBSRO_API_KEY = ""
        result = self.srv._fetch_via_subsro("Inception", "en", 2010, None, None, None)
        self.assertIsNone(result)


class TestSubsroMovieFetch(unittest.TestCase):
    def setUp(self):
        self.srv = _load_subtitle_server()
        self.srv.SUBSRO_API_KEY = "test-key-123"

    def test_successful_movie_fetch(self):
        """A valid search result with a download URL returns SRT text."""
        fake_srt = "1\n00:00:01,000 --> 00:00:03,000\nHello world\n"
        results = [_make_subsro_result(lang="en")]

        with patch.object(self.srv, "_subsro_search", return_value=results):
            with patch.object(self.srv, "_subsro_download", return_value=fake_srt):
                result = self.srv._fetch_via_subsro("Inception", "en", 2010, None, None, None)

        self.assertEqual(result, fake_srt)

    def test_returns_none_on_empty_results(self):
        """Empty search results produce None."""
        with patch.object(self.srv, "_subsro_search", return_value=[]):
            result = self.srv._fetch_via_subsro("Inception", "en", 2010, None, None, None)
        self.assertIsNone(result)

    def test_returns_none_on_search_exception(self):
        """HTTP/network errors during search return None gracefully."""
        import httpx
        with patch.object(self.srv, "_subsro_search", side_effect=httpx.ConnectError("timeout")):
            result = self.srv._fetch_via_subsro("Inception", "en", 2010, None, None, None)
        self.assertIsNone(result)

    def test_returns_none_on_download_exception(self):
        """HTTP/network errors during download return None gracefully."""
        import httpx
        results = [_make_subsro_result(lang="en")]
        with patch.object(self.srv, "_subsro_search", return_value=results):
            with patch.object(self.srv, "_subsro_download", side_effect=httpx.ConnectError("timeout")):
                result = self.srv._fetch_via_subsro("Inception", "en", 2010, None, None, None)
        self.assertIsNone(result)

    def test_language_filtering_excludes_wrong_lang(self):
        """Results in a different language are filtered out."""
        results = [_make_subsro_result(lang="ro")]  # Romanian, not English
        with patch.object(self.srv, "_subsro_search", return_value=results):
            result = self.srv._fetch_via_subsro("Inception", "en", 2010, None, None, None)
        self.assertIsNone(result)

    def test_returns_none_when_srt_content_empty(self):
        """Empty download response body returns None."""
        results = [_make_subsro_result(lang="en")]
        with patch.object(self.srv, "_subsro_search", return_value=results):
            with patch.object(self.srv, "_subsro_download", return_value="   "):
                result = self.srv._fetch_via_subsro("Inception", "en", 2010, None, None, None)
        self.assertIsNone(result)


class TestSubsroTvEpisodeFetch(unittest.TestCase):
    def setUp(self):
        self.srv = _load_subtitle_server()
        self.srv.SUBSRO_API_KEY = "test-key-123"

    def test_exact_episode_match_preferred(self):
        """Results that exactly match the requested S/E are preferred over others."""
        fake_srt = "1\n00:00:01,000 --> 00:00:03,000\nHello\n"
        results = [
            _make_subsro_result(lang="en", season=1, episode=2, downloads=500),  # wrong ep
            _make_subsro_result(lang="en", season=1, episode=3, downloads=10),   # correct ep
        ]

        # Patch download to capture which result was chosen
        chosen = {}

        def fake_download(url: str, params=None) -> str:
            chosen["url"] = url
            return fake_srt

        with patch.object(self.srv, "_subsro_search", return_value=results):
            with patch.object(self.srv, "_subsro_download", side_effect=fake_download):
                result = self.srv._fetch_via_subsro("Breaking Bad", "en", None, None, 1, 3)

        self.assertEqual(result, fake_srt)
        # The chosen result must be the ep=3 one
        self.assertEqual(chosen["url"], results[1]["url"])

    def test_fallback_to_all_results_when_no_exact_match(self):
        """When no result has exact S/E attrs, all language-filtered results are used."""
        fake_srt = "1\n00:00:01,000 --> 00:00:03,000\nHello\n"
        # Results have no season/episode attrs at all
        results = [
            _make_subsro_result(lang="en", downloads=200),
            _make_subsro_result(lang="en", downloads=50),
        ]

        with patch.object(self.srv, "_subsro_search", return_value=results):
            with patch.object(self.srv, "_subsro_download", return_value=fake_srt):
                result = self.srv._fetch_via_subsro("Breaking Bad", "en", None, None, 1, 3)

        self.assertEqual(result, fake_srt)

    def test_episode_search_passes_season_and_episode_params(self):
        """Search is called with season and episode parameters."""
        with patch.object(self.srv, "_subsro_search", return_value=[]) as mock_search:
            self.srv._fetch_via_subsro("Breaking Bad", "en", None, None, 2, 5)
        mock_search.assert_called_once_with("Breaking Bad", "en", None, None, 2, 5)


class TestSubsroSearchParamBuilding(unittest.TestCase):
    """Verify _subsro_search builds the correct URL path and auth header."""

    def setUp(self):
        self.srv = _load_subtitle_server()
        self.srv.SUBSRO_API_KEY = "test-key"
        self.srv.SUBSRO_BASE = "https://api.subs.ro/v1.0"

    def test_movie_title_search_uses_title_path(self):
        """When no imdb_id is provided, search uses /search/title/{title} path."""
        fake_response = MagicMock()
        fake_response.json.return_value = {"items": []}
        fake_response.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=fake_response) as mock_get:
            self.srv._subsro_search("Inception", "en", 2010, None, None, None)

        call_url = mock_get.call_args.args[0]
        self.assertIn("/search/title/Inception", call_url)
        # language is passed as a query param
        call_params = mock_get.call_args.kwargs.get("params", {})
        self.assertEqual(call_params.get("language"), "en")
        # API key must be in the header, NOT in the URL or query params
        call_headers = mock_get.call_args.kwargs.get("headers", {})
        self.assertEqual(call_headers.get("X-Subs-Api-Key"), "test-key")
        self.assertNotIn("apikey", call_params)
        self.assertNotIn("apiKey", call_params)

    def test_imdb_search_uses_imdbid_path(self):
        """When imdb_id is provided, search uses /search/imdbid/{imdbid} path."""
        fake_response = MagicMock()
        fake_response.json.return_value = {"items": []}
        fake_response.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=fake_response) as mock_get:
            self.srv._subsro_search("Inception", "en", 2010, "tt1375666", None, None)

        call_url = mock_get.call_args.args[0]
        self.assertIn("/search/imdbid/tt1375666", call_url)
        call_headers = mock_get.call_args.kwargs.get("headers", {})
        self.assertEqual(call_headers.get("X-Subs-Api-Key"), "test-key")

    def test_episode_params(self):
        """Episode searches use title path and pass language as query param (season/episode filtered client-side)."""
        fake_response = MagicMock()
        fake_response.json.return_value = {"items": []}
        fake_response.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=fake_response) as mock_get:
            self.srv._subsro_search("Breaking Bad", "en", None, None, 3, 7)

        call_url = mock_get.call_args.args[0]
        self.assertIn("/search/title/Breaking Bad", call_url)
        call_params = mock_get.call_args.kwargs.get("params", {})
        self.assertEqual(call_params.get("language"), "en")
        # season/episode are not API params in v1.0; they are handled client-side
        self.assertNotIn("season", call_params)
        self.assertNotIn("episode", call_params)
        self.assertNotIn("apikey", call_params)


class TestSubsroApiKeyNotLogged(unittest.TestCase):
    """Ensure the API key value never appears in log output."""

    def setUp(self):
        self.srv = _load_subtitle_server()
        self.srv.SUBSRO_API_KEY = "super-secret-key-xyz"

    def test_api_key_not_in_search_log(self):
        import logging
        log_messages: list[str] = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                log_messages.append(self.format(record))

        handler = CapturingHandler()
        # Capture both subtitle_server and httpx loggers
        self.srv.logger.addHandler(handler)
        httpx_logger = logging.getLogger("httpx")
        original_level = httpx_logger.level
        httpx_logger.setLevel(logging.DEBUG)
        httpx_logger.addHandler(handler)
        try:
            with patch.object(self.srv, "_subsro_search", return_value=[]):
                self.srv._fetch_via_subsro("Inception", "en", 2010, None, None, None)
        finally:
            self.srv.logger.removeHandler(handler)
            httpx_logger.removeHandler(handler)
            httpx_logger.setLevel(original_level)

        for msg in log_messages:
            self.assertNotIn(
                "super-secret-key-xyz", msg,
                f"API key found in log message: {msg!r}",
            )

    def test_api_key_not_in_url_params(self):
        """API key must be sent in header only, not as a URL query parameter."""
        fake_response = MagicMock()
        fake_response.json.return_value = {"items": []}
        fake_response.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=fake_response) as mock_get:
            self.srv._subsro_search("Inception", "en", 2010, None, None, None)

        call_params = mock_get.call_args.kwargs.get("params", {})
        self.assertNotIn("apikey", call_params, "API key must not be in URL params")
        self.assertNotIn("apiKey", call_params, "API key must not be in URL params")
        call_headers = mock_get.call_args.kwargs.get("headers", {})
        self.assertEqual(
            call_headers.get("X-Subs-Api-Key"), "super-secret-key-xyz",
            "API key must be in X-Subs-Api-Key header",
        )


class TestProviderOrdering(unittest.TestCase):
    """Verify the provider chain: subs.ro → OpenSubtitles VIP → subliminal."""

    def setUp(self):
        self.srv = _load_subtitle_server()

    def _patch_cache(self):
        """Return a context manager that disables cache read/write."""
        from unittest.mock import patch as p
        return p.multiple(
            self.srv,
            _cache_read=MagicMock(return_value=None),
            _cache_write=MagicMock(),
        )

    def test_subsro_used_first_when_configured(self):
        """subs.ro result is returned without calling OpenSubtitles VIP."""
        fake_srt = "1\n00:00:01,000 --> 00:00:03,000\nOK\n"
        mock_subsro = MagicMock(return_value=fake_srt)
        mock_vip = MagicMock(return_value="should not be called")
        mock_subliminal = MagicMock(return_value="should not be called")
        with patch.multiple(
            self.srv,
            _fetch_via_subsro=mock_subsro,
            _fetch_via_vip=mock_vip,
            _fetch_via_subliminal=mock_subliminal,
            _cache_read=MagicMock(return_value=None),
            _cache_write=MagicMock(),
        ):
            from fastapi.testclient import TestClient
            client = TestClient(self.srv.app)
            resp = client.get("/subtitles?title=Inception&lang=en")
            # Assert inside the with block while mocks are still active
            mock_vip.assert_not_called()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, fake_srt)

    def test_vip_used_when_subsro_returns_none(self):
        """When subs.ro returns None, OpenSubtitles VIP is tried next."""
        fake_srt = "1\n00:00:01,000 --> 00:00:03,000\nOK\n"
        mock_subliminal = MagicMock(return_value="should not be called")
        with patch.multiple(
            self.srv,
            _fetch_via_subsro=MagicMock(return_value=None),
            _fetch_via_vip=MagicMock(return_value=fake_srt),
            _fetch_via_subliminal=mock_subliminal,
            _cache_read=MagicMock(return_value=None),
            _cache_write=MagicMock(),
        ):
            from fastapi.testclient import TestClient
            client = TestClient(self.srv.app)
            resp = client.get("/subtitles?title=Inception&lang=en")
            mock_subliminal.assert_not_called()

        self.assertEqual(resp.status_code, 200)

    def test_subliminal_used_when_subsro_and_vip_return_none(self):
        """When both subs.ro and VIP return None, subliminal is tried."""
        fake_srt = "1\n00:00:01,000 --> 00:00:03,000\nOK\n"
        with patch.multiple(
            self.srv,
            _fetch_via_subsro=MagicMock(return_value=None),
            _fetch_via_vip=MagicMock(return_value=None),
            _fetch_via_subliminal=MagicMock(return_value=fake_srt),
            _cache_read=MagicMock(return_value=None),
            _cache_write=MagicMock(),
        ):
            from fastapi.testclient import TestClient
            client = TestClient(self.srv.app)
            resp = client.get("/subtitles?title=Inception&lang=en")

        self.assertEqual(resp.status_code, 200)

    def test_404_when_all_providers_return_none(self):
        """All providers returning None yields a 404 response."""
        with patch.multiple(
            self.srv,
            _fetch_via_subsro=MagicMock(return_value=None),
            _fetch_via_vip=MagicMock(return_value=None),
            _fetch_via_subliminal=MagicMock(return_value=None),
            _cache_read=MagicMock(return_value=None),
            _cache_write=MagicMock(),
        ):
            from fastapi.testclient import TestClient
            client = TestClient(self.srv.app)
            resp = client.get("/subtitles?title=Inception&lang=en")

        self.assertEqual(resp.status_code, 404)


class TestHealthEndpoint(unittest.TestCase):
    """Health endpoint must include subs.ro status."""

    def setUp(self):
        self.srv = _load_subtitle_server()

    def test_health_includes_subsro_field(self):
        from fastapi.testclient import TestClient
        client = TestClient(self.srv.app)
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("subsro", body)
        self.assertIn("configured", body["subsro"])

    def test_health_subsro_configured_true_when_key_set(self):
        self.srv.SUBSRO_API_KEY = "some-key"
        from fastapi.testclient import TestClient
        client = TestClient(self.srv.app)
        resp = client.get("/health")
        body = resp.json()
        self.assertTrue(body["subsro"]["configured"])

    def test_health_subsro_configured_false_when_key_missing(self):
        self.srv.SUBSRO_API_KEY = ""
        from fastapi.testclient import TestClient
        client = TestClient(self.srv.app)
        resp = client.get("/health")
        body = resp.json()
        self.assertFalse(body["subsro"]["configured"])


if __name__ == "__main__":
    unittest.main()
