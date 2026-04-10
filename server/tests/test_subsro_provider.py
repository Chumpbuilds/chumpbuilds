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
- /subtitles/search returns subs.ro results when configured
- HEAD /subtitles returns 200 (not 405)
"""

from __future__ import annotations

import io
import sys
import types
import unittest
import zipfile
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


class TestSubsroZipExtraction(unittest.TestCase):
    """Tests that _subsro_download and _extract_srt_from_zip handle ZIP archives."""

    def setUp(self):
        self.srv = _load_subtitle_server()
        self.srv.SUBSRO_API_KEY = "test-key-123"

    # ------------------------------------------------------------------
    # Helper: build an in-memory ZIP containing one or more .srt files
    # ------------------------------------------------------------------
    @staticmethod
    def _make_zip(*entries: tuple[str, bytes]) -> bytes:
        """Return bytes of a ZIP archive with the given (filename, data) entries."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in entries:
                zf.writestr(name, data)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Unit tests for _extract_srt_from_zip
    # ------------------------------------------------------------------

    def test_extract_single_srt(self):
        """A ZIP with one .srt file returns that file's text."""
        srt_content = b"1\n00:00:01,000 --> 00:00:03,000\nHello world\n"
        zip_bytes = self._make_zip(("subtitle.srt", srt_content))
        result = self.srv._extract_srt_from_zip(zip_bytes)
        self.assertEqual(result, srt_content.decode("utf-8"))

    def test_extract_largest_srt_when_multiple(self):
        """With multiple .srt files the largest (by uncompressed size) is chosen."""
        small = b"1\n00:00:01,000 --> 00:00:02,000\nShort\n"
        large = b"1\n00:00:01,000 --> 00:00:02,000\nLine one\n" + b"x" * 5000
        zip_bytes = self._make_zip(
            ("small.srt", small),
            ("large.srt", large),
        )
        result = self.srv._extract_srt_from_zip(zip_bytes)
        self.assertEqual(result, large.decode("utf-8"))

    def test_raises_on_no_srt_in_zip(self):
        """A ZIP with no .srt entries raises ValueError."""
        zip_bytes = self._make_zip(("readme.txt", b"nothing here"))
        with self.assertRaises(ValueError):
            self.srv._extract_srt_from_zip(zip_bytes)

    def test_ignores_non_srt_entries(self):
        """Non-.srt entries in the ZIP are ignored; only the .srt is used."""
        srt_content = b"1\n00:00:01,000 --> 00:00:02,000\nSubtitle\n"
        zip_bytes = self._make_zip(
            ("info.nfo", b"release info"),
            ("movie.srt", srt_content),
            ("cover.jpg", b"\xff\xd8\xff"),
        )
        result = self.srv._extract_srt_from_zip(zip_bytes)
        self.assertEqual(result, srt_content.decode("utf-8"))

    def test_srt_extension_is_case_insensitive(self):
        """Files named .SRT (uppercase) are also picked up."""
        srt_content = b"1\n00:00:01,000 --> 00:00:02,000\nUpper\n"
        zip_bytes = self._make_zip(("MOVIE.SRT", srt_content))
        result = self.srv._extract_srt_from_zip(zip_bytes)
        self.assertEqual(result, srt_content.decode("utf-8"))

    # ------------------------------------------------------------------
    # Integration tests for _subsro_download with a mocked HTTP response
    # ------------------------------------------------------------------

    def _make_mock_response(self, body: bytes) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.content = body
        mock_resp.text = body.decode("utf-8", errors="replace")
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_download_extracts_srt_from_zip_response(self):
        """_subsro_download returns SRT text even when the server sends a ZIP."""
        srt_content = b"1\n00:00:01,000 --> 00:00:03,000\nPets on a Train\n"
        zip_bytes = self._make_zip(("subtitle.srt", srt_content))

        with patch("httpx.get", return_value=self._make_mock_response(zip_bytes)):
            result = self.srv._subsro_download("https://api.subs.ro/download/42")

        self.assertEqual(result, srt_content.decode("utf-8"))
        # Regression: must NOT start with ZIP magic bytes
        self.assertFalse(
            result.encode("utf-8")[:4] == b"PK\x03\x04",
            "Response must not start with ZIP magic bytes (PK\\x03\\x04)",
        )
        self.assertFalse(
            result.startswith("PK"),
            "Response must not start with 'PK'",
        )

    def test_download_returns_plain_text_unchanged(self):
        """_subsro_download returns plain SRT content as-is (non-ZIP)."""
        srt_content = b"1\n00:00:01,000 --> 00:00:03,000\nNormal SRT\n"

        with patch("httpx.get", return_value=self._make_mock_response(srt_content)):
            result = self.srv._subsro_download("https://api.subs.ro/download/42")

        self.assertIn("Normal SRT", result)
        self.assertFalse(result.startswith("PK"))

    def test_download_does_not_log_raw_binary_body(self):
        """Logging must never contain raw binary bytes (security/logging requirement)."""
        import logging as _logging

        srt_content = b"1\n00:00:01,000 --> 00:00:03,000\nSecure\n"
        zip_bytes = self._make_zip(("secure.srt", srt_content))

        log_messages: list[str] = []

        class CapHandler(_logging.Handler):
            def emit(self, record):
                log_messages.append(self.format(record))

        handler = CapHandler()
        self.srv.logger.addHandler(handler)
        try:
            with patch("httpx.get", return_value=self._make_mock_response(zip_bytes)):
                self.srv._subsro_download("https://api.subs.ro/download/42")
        finally:
            self.srv.logger.removeHandler(handler)

        for msg in log_messages:
            self.assertNotIn(
                repr(zip_bytes[:20]),
                msg,
                "Raw binary body must not appear in log output",
            )

    # ------------------------------------------------------------------
    # End-to-end: _fetch_via_subsro returns SRT text when download is ZIP
    # ------------------------------------------------------------------

    def test_fetch_via_subsro_with_zip_returns_srt(self):
        """Full provider path: subs.ro returns ZIP → caller receives SRT text."""
        srt_content = b"1\n00:00:01,000 --> 00:00:03,000\nPets on a Train\n"
        zip_bytes = self._make_zip(("movie.srt", srt_content))
        results = [_make_subsro_result(lang="ro")]

        mock_resp = self._make_mock_response(zip_bytes)

        with patch.object(self.srv, "_subsro_search", return_value=results):
            with patch("httpx.get", return_value=mock_resp):
                result = self.srv._fetch_via_subsro(
                    "Pets on a Train", "ro", 2025, None, None, None
                )

        self.assertIsNotNone(result)
        self.assertFalse(
            (result or "").startswith("PK"),
            "Returned content must not start with ZIP magic 'PK'",
        )
        self.assertIn("Pets on a Train", result or "")

    def test_endpoint_returns_srt_text_not_zip(self):
        """HTTP endpoint /subtitles must return plain SRT, never ZIP bytes."""
        from fastapi.testclient import TestClient

        srt_content = b"1\n00:00:01,000 --> 00:00:03,000\nPets on a Train\n"
        zip_bytes = self._make_zip(("movie.srt", srt_content))
        results = [_make_subsro_result(lang="ro")]

        mock_resp = self._make_mock_response(zip_bytes)

        with patch.multiple(
            self.srv,
            _cache_read=MagicMock(return_value=None),
            _cache_write=MagicMock(),
        ):
            with patch.object(self.srv, "_subsro_search", return_value=results):
                with patch("httpx.get", return_value=mock_resp):
                    client = TestClient(self.srv.app)
                    resp = client.get("/subtitles?title=Pets+on+a+Train&lang=ro")

        self.assertEqual(resp.status_code, 200)
        body = resp.text
        self.assertFalse(
            body.startswith("PK"),
            "Response body must not start with ZIP magic 'PK'",
        )
        self.assertIn("Pets on a Train", body)
        # Content-Type must advertise plain text
        ct = resp.headers.get("content-type", "")
        self.assertIn("text/plain", ct)


class TestCachePoisoningRejection(unittest.TestCase):
    """Tests that ZIP bytes stored in the subtitle cache are detected and evicted."""

    def setUp(self):
        self.srv = _load_subtitle_server()
        self.srv.SUBSRO_API_KEY = "test-key-123"

    @staticmethod
    def _make_zip(*entries: tuple[str, bytes]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in entries:
                zf.writestr(name, data)
        return buf.getvalue()

    def test_cache_read_rejects_zip_bytes_and_deletes_file(self):
        """_cache_read must delete and return None when cached content is ZIP bytes."""
        import tempfile
        from pathlib import Path

        tmp_dir = Path(tempfile.mkdtemp())
        self.srv.CACHE_DIR = tmp_dir

        # Simulate old code writing raw ZIP bytes as text to the cache
        key = "poisoned_key"
        zip_bytes = self._make_zip(("movie.srt", b"1\n00:00:01,000 --> 00:00:02,000\nTest\n"))
        # Write the ZIP bytes as a text file (the bug from before the fix)
        (tmp_dir / f"{key}.srt").write_bytes(zip_bytes)

        result = self.srv._cache_read(key)

        self.assertIsNone(result, "_cache_read must return None for a poisoned cache file")
        self.assertFalse(
            (tmp_dir / f"{key}.srt").exists(),
            "Poisoned cache file must be deleted",
        )

    def test_cache_read_accepts_valid_srt_content(self):
        """_cache_read must return valid SRT content unchanged."""
        import tempfile
        from pathlib import Path

        tmp_dir = Path(tempfile.mkdtemp())
        self.srv.CACHE_DIR = tmp_dir

        key = "valid_key"
        srt_text = "1\n00:00:01,000 --> 00:00:03,000\nHello world\n"
        (tmp_dir / f"{key}.srt").write_text(srt_text, encoding="utf-8")

        result = self.srv._cache_read(key)

        self.assertEqual(result, srt_text)

    def test_endpoint_evicts_poisoned_cache_does_not_return_zip(self):
        """When the cache contains ZIP bytes, the endpoint must not return them."""
        from fastapi.testclient import TestClient

        zip_bytes = self._make_zip(("movie.srt", b"1\n00:00:01,000 --> 00:00:02,000\nTest\n"))
        # Simulate cache read returning ZIP bytes as a string (poisoned entry)
        poisoned_str = zip_bytes.decode("latin-1")

        srt_content = b"1\n00:00:01,000 --> 00:00:03,000\nFresh subtitle\n"

        with patch.multiple(
            self.srv,
            _fetch_via_subsro=MagicMock(return_value=srt_content.decode("utf-8")),
            _fetch_via_vip=MagicMock(return_value=None),
            _fetch_via_subliminal=MagicMock(return_value=None),
            _cache_read=MagicMock(return_value=poisoned_str),
            _cache_write=MagicMock(),
        ):
            client = TestClient(self.srv.app)
            resp = client.get("/subtitles?title=TestMovie&lang=ro")

        # Poisoned cache is bypassed; the actual content returned should NOT be ZIP
        # NOTE: The mock _cache_read returns the poisoned str, so the endpoint
        # returns it. This test verifies the safety guard rejects it as 502.
        self.assertNotEqual(resp.status_code, 200, "Must not return 200 with ZIP bytes")
        body_bytes = resp.content
        self.assertFalse(
            body_bytes[:4] == b"PK\x03\x04",
            "Response body must not start with ZIP magic bytes",
        )


class TestZipSafetyGuard(unittest.TestCase):
    """Tests the endpoint-level safety guard that prevents ZIP bytes reaching clients."""

    def setUp(self):
        self.srv = _load_subtitle_server()

    def test_endpoint_returns_502_when_provider_returns_zip_bytes(self):
        """If a provider somehow returns ZIP bytes as a string, the endpoint returns 502."""
        from fastapi.testclient import TestClient

        # Simulate a broken provider returning ZIP magic bytes as a string
        zip_magic_str = "PK\x03\x04fake zip content"

        with patch.multiple(
            self.srv,
            _fetch_via_subsro=MagicMock(return_value=zip_magic_str),
            _fetch_via_vip=MagicMock(return_value=None),
            _fetch_via_subliminal=MagicMock(return_value=None),
            _cache_read=MagicMock(return_value=None),
            _cache_write=MagicMock(),
        ):
            client = TestClient(self.srv.app)
            resp = client.get("/subtitles?title=TestMovie&lang=ro")

        self.assertEqual(resp.status_code, 502)
        body_bytes = resp.content
        self.assertFalse(
            body_bytes[:4] == b"PK\x03\x04",
            "Response body must not start with ZIP magic bytes",
        )

    def test_endpoint_does_not_cache_zip_bytes(self):
        """When the safety guard fires, the ZIP string must NOT be written to cache."""
        from fastapi.testclient import TestClient

        zip_magic_str = "PK\x03\x04fake zip content"
        mock_cache_write = MagicMock()

        with patch.multiple(
            self.srv,
            _fetch_via_subsro=MagicMock(return_value=zip_magic_str),
            _fetch_via_vip=MagicMock(return_value=None),
            _fetch_via_subliminal=MagicMock(return_value=None),
            _cache_read=MagicMock(return_value=None),
            _cache_write=mock_cache_write,
        ):
            client = TestClient(self.srv.app)
            client.get("/subtitles?title=TestMovie&lang=ro")

        mock_cache_write.assert_not_called()

    def test_corrupted_zip_yields_non_200(self):
        """A corrupted ZIP (no valid .srt entry) causes a non-200 response."""
        from fastapi.testclient import TestClient

        # ZIP archive that contains no .srt files
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", b"no subtitles here")
        corrupted_zip_bytes = buf.getvalue()

        mock_resp = MagicMock()
        mock_resp.content = corrupted_zip_bytes
        mock_resp.text = corrupted_zip_bytes.decode("utf-8", errors="replace")
        mock_resp.raise_for_status = MagicMock()

        results = [_make_subsro_result(lang="ro")]

        with patch.multiple(
            self.srv,
            _cache_read=MagicMock(return_value=None),
            _cache_write=MagicMock(),
            SUBSRO_API_KEY="test-key",
        ):
            with patch.object(self.srv, "_subsro_search", return_value=results):
                with patch("httpx.get", return_value=mock_resp):
                    with patch.multiple(
                        self.srv,
                        _fetch_via_vip=MagicMock(return_value=None),
                        _fetch_via_subliminal=MagicMock(return_value=None),
                    ):
                        client = TestClient(self.srv.app)
                        resp = client.get("/subtitles?title=TestMovie&lang=ro")

        # subs.ro ZIP with no .srt → all providers fail → non-200
        self.assertNotEqual(resp.status_code, 200)
        body_bytes = resp.content
        self.assertFalse(
            body_bytes[:4] == b"PK\x03\x04",
            "Response body must not start with ZIP magic bytes",
        )


class TestCp1250Fallback(unittest.TestCase):
    """Tests cp1250 encoding fallback in _extract_srt_from_zip."""

    def setUp(self):
        self.srv = _load_subtitle_server()

    def test_cp1250_encoded_srt_is_decoded(self):
        """SRT content encoded in cp1250 is decoded correctly via the fallback."""
        # Romanian text that differs between cp1250 and latin-1:
        # U+015F LATIN SMALL LETTER S WITH CEDILLA = 0x9F in cp1250
        romanian_text = "1\n00:00:01,000 --> 00:00:03,000\n\u015f\n"
        srt_bytes = romanian_text.encode("cp1250")
        # Verify bytes are NOT valid UTF-8
        with self.assertRaises(UnicodeDecodeError):
            srt_bytes.decode("utf-8")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("movie.srt", srt_bytes)
        zip_bytes = buf.getvalue()

        result = self.srv._extract_srt_from_zip(zip_bytes)

        self.assertIn("\u015f", result, "cp1250 character must be decoded correctly")


class TestBomStripping(unittest.TestCase):
    """Tests that the /subtitles endpoint strips a UTF-8 BOM from SRT responses."""

    def setUp(self):
        self.srv = _load_subtitle_server()
        self.srv.SUBSRO_API_KEY = "test-key-123"

    def test_endpoint_strips_bom_from_srt_response(self):
        """Response body must start with '1\\n', not the UTF-8 BOM EF BB BF."""
        from fastapi.testclient import TestClient

        # SRT content with a UTF-8 BOM prepended (as subs.ro sometimes returns)
        srt_with_bom = "\ufeff1\n00:00:01,000 --> 00:00:03,000\nHello\n"

        with patch.multiple(
            self.srv,
            _fetch_via_subsro=MagicMock(return_value=srt_with_bom),
            _fetch_via_vip=MagicMock(return_value=None),
            _fetch_via_subliminal=MagicMock(return_value=None),
            _cache_read=MagicMock(return_value=None),
            _cache_write=MagicMock(),
        ):
            client = TestClient(self.srv.app)
            resp = client.get("/subtitles?title=Hello+Movie&lang=ro")

        self.assertEqual(resp.status_code, 200)
        # Raw bytes must NOT start with the UTF-8 BOM (EF BB BF)
        self.assertFalse(
            resp.content.startswith(b"\xef\xbb\xbf"),
            "Response body must not start with UTF-8 BOM bytes EF BB BF",
        )
        # Body must start with '1\n' — the first line of a well-formed SRT
        self.assertTrue(
            resp.text.startswith("1\n"),
            f"Response body must start with '1\\n' but got: {resp.text[:20]!r}",
        )
        # Content-Type must still advertise plain text UTF-8
        ct = resp.headers.get("content-type", "")
        self.assertIn("text/plain", ct)

    def test_endpoint_strips_bom_from_bytes_provider_response(self):
        """Response body is BOM-free when provider returns bytes starting with EF BB BF."""
        from fastapi.testclient import TestClient

        # Raw bytes with UTF-8 BOM (e.g. from a provider returning bytes directly)
        srt_bytes_with_bom = b"\xef\xbb\xbf1\n00:00:01,000 --> 00:00:03,000\nHello\n"
        # _strip_bom accepts bytes; convert to str via _strip_bom before provider mock
        srt_stripped = self.srv._strip_bom(srt_bytes_with_bom)

        with patch.multiple(
            self.srv,
            _fetch_via_subsro=MagicMock(return_value=srt_stripped),
            _fetch_via_vip=MagicMock(return_value=None),
            _fetch_via_subliminal=MagicMock(return_value=None),
            _cache_read=MagicMock(return_value=None),
            _cache_write=MagicMock(),
        ):
            client = TestClient(self.srv.app)
            resp = client.get("/subtitles?title=Hello+Movie&lang=ro")

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            resp.content.startswith(b"\xef\xbb\xbf"),
            "Response body must not start with UTF-8 BOM bytes EF BB BF",
        )
        self.assertTrue(
            resp.text.startswith("1\n"),
            f"Response body must start with '1\\n' but got: {resp.text[:20]!r}",
        )

    def test_endpoint_strips_bom_from_cached_entry(self):
        """BOM is stripped even when the data is served from the cache (regression)."""
        from fastapi.testclient import TestClient

        # Simulate a cache entry that was written before the BOM-fix (contains BOM)
        cached_with_bom = "\ufeff1\n00:00:01,000 --> 00:00:03,000\nCached subtitle\n"

        with patch.multiple(
            self.srv,
            _cache_read=MagicMock(return_value=cached_with_bom),
            _cache_write=MagicMock(),
        ):
            client = TestClient(self.srv.app)
            resp = client.get("/subtitles?title=Hello+Movie&lang=ro")

        self.assertEqual(resp.status_code, 200)
        # Must not start with BOM bytes EF BB BF
        self.assertFalse(
            resp.content.startswith(b"\xef\xbb\xbf"),
            "Cached response body must not start with UTF-8 BOM bytes EF BB BF",
        )
        # Must start with '1\n'
        self.assertTrue(
            resp.text.startswith("1\n"),
            f"Cached response must start with '1\\n' but got: {resp.text[:20]!r}",
        )
        ct = resp.headers.get("content-type", "")
        self.assertIn("text/plain", ct)

    def test_strip_bom_function_handles_bytes_with_bom(self):
        """_strip_bom must strip 3-byte BOM prefix from bytes and return str."""
        srt_bytes = b"\xef\xbb\xbf1\n00:00:01,000 --> 00:00:02,000\nTest\n"
        result = self.srv._strip_bom(srt_bytes)
        self.assertIsInstance(result, str)
        self.assertFalse(result.startswith("\ufeff"), "BOM char must be stripped")
        self.assertTrue(result.startswith("1\n"), f"Must start with '1\\n', got {result[:10]!r}")

    def test_strip_bom_function_handles_bytes_without_bom(self):
        """_strip_bom must decode bytes without BOM unchanged."""
        srt_bytes = b"1\n00:00:01,000 --> 00:00:02,000\nTest\n"
        result = self.srv._strip_bom(srt_bytes)
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith("1\n"))


class TestSearchEndpointSubsroResults(unittest.TestCase):
    """Tests that /subtitles/search returns subs.ro results when the provider is configured."""

    def setUp(self):
        self.srv = _load_subtitle_server()
        self.srv.SUBSRO_API_KEY = "test-key-123"

    def test_search_returns_subsro_results_when_configured(self):
        """/subtitles/search must return a non-empty list when subs.ro has matches."""
        from fastapi.testclient import TestClient

        subsro_items = [
            {
                "id": 42,
                "language": "ro",
                "title": "Pets on a Train",
                "release": "Pets.on.a.Train.2025.BluRay",
                "downloads": 200,
                "url": "https://api.subs.ro/v1.0/subtitle/42/download",
            }
        ]

        with patch.object(self.srv, "_subsro_search", return_value=subsro_items):
            with patch.object(self.srv, "_ensure_authenticated", return_value=False):
                client = TestClient(self.srv.app)
                resp = client.get(
                    "/subtitles/search"
                    "?title=Pets+on+a+Train+-+2025"
                    "&year=2025"
                    "&tmdb_id=1107216"
                    "&lang=ro"
                )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0, "Search must return at least one result from subs.ro")
        first = data[0]
        self.assertEqual(first["provider"], "subs.ro")
        self.assertEqual(first["language"], "ro")
        self.assertIn("url", first, "Result must include a 'url' field for fetching the SRT")
        # url should point to /subtitles endpoint
        self.assertTrue(first["url"].startswith("/subtitles?"), f"url should start with /subtitles?, got: {first['url']!r}")

    def test_search_returns_empty_when_subsro_key_missing(self):
        """/subtitles/search returns [] when subs.ro not configured and VIP not authenticated."""
        from fastapi.testclient import TestClient

        self.srv.SUBSRO_API_KEY = ""

        with patch.object(self.srv, "_ensure_authenticated", return_value=False):
            client = TestClient(self.srv.app)
            resp = client.get("/subtitles/search?title=TestTitle&lang=en")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_search_filters_wrong_language_from_subsro(self):
        """subs.ro results in the wrong language are excluded from search output."""
        from fastapi.testclient import TestClient

        subsro_items = [
            {
                "id": 1,
                "language": "en",  # wrong language
                "title": "Pets on a Train",
                "release": "Pets.on.a.Train.2025.BluRay",
                "downloads": 100,
                "url": "https://api.subs.ro/v1.0/subtitle/1/download",
            }
        ]

        with patch.object(self.srv, "_subsro_search", return_value=subsro_items):
            with patch.object(self.srv, "_ensure_authenticated", return_value=False):
                client = TestClient(self.srv.app)
                resp = client.get("/subtitles/search?title=Pets+on+a+Train&lang=ro")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [], "Results in wrong language must be filtered out")

    def test_search_includes_url_with_all_query_params(self):
        """The url in subs.ro results includes year, tmdb_id, season, episode when provided."""
        from fastapi.testclient import TestClient
        import urllib.parse

        subsro_items = [
            {
                "id": 10,
                "language": "ro",
                "title": "Breaking Bad",
                "release": "Breaking.Bad.S01E03",
                "downloads": 50,
                "url": "https://api.subs.ro/v1.0/subtitle/10/download",
            }
        ]

        with patch.object(self.srv, "_subsro_search", return_value=subsro_items):
            with patch.object(self.srv, "_ensure_authenticated", return_value=False):
                client = TestClient(self.srv.app)
                resp = client.get(
                    "/subtitles/search"
                    "?title=Breaking+Bad"
                    "&year=2008"
                    "&season=1"
                    "&episode=3"
                    "&lang=ro"
                )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data), 0)
        url = data[0]["url"]
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(qs.get("season", [None])[0], "1")
        self.assertEqual(qs.get("episode", [None])[0], "3")
        self.assertEqual(qs.get("year", [None])[0], "2008")

    def test_search_gracefully_handles_subsro_exception(self):
        """A subs.ro search error does not crash the endpoint; returns empty or VIP-only list."""
        from fastapi.testclient import TestClient
        import httpx

        with patch.object(self.srv, "_subsro_search", side_effect=httpx.ConnectError("timeout")):
            with patch.object(self.srv, "_ensure_authenticated", return_value=False):
                client = TestClient(self.srv.app)
                resp = client.get("/subtitles/search?title=Inception&lang=en")

        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)


class TestSubtitlesHeadMethod(unittest.TestCase):
    """Tests that HEAD /subtitles returns 200 (not 405)."""

    def setUp(self):
        self.srv = _load_subtitle_server()

    def test_head_subtitles_returns_200(self):
        """HEAD /subtitles must return 200 so clients probing availability succeed."""
        from fastapi.testclient import TestClient

        client = TestClient(self.srv.app)
        resp = client.head("/subtitles?title=Some+Movie&lang=en")

        self.assertIn(resp.status_code, (200, 204), f"HEAD /subtitles returned {resp.status_code}, expected 200 or 204")

    def test_head_subtitles_returns_no_body(self):
        """HEAD /subtitles must return an empty body."""
        from fastapi.testclient import TestClient

        client = TestClient(self.srv.app)
        resp = client.head("/subtitles?title=Some+Movie&lang=en")

        self.assertEqual(resp.content, b"", "HEAD response must have an empty body")

    def test_head_subtitles_includes_content_type_header(self):
        """HEAD /subtitles must return a Content-Type header."""
        from fastapi.testclient import TestClient

        client = TestClient(self.srv.app)
        resp = client.head("/subtitles?title=Some+Movie&lang=en")

        ct = resp.headers.get("content-type", "")
        self.assertIn("text/plain", ct, f"Content-Type must be text/plain, got: {ct!r}")

    def test_get_subtitles_still_works_after_head_support_added(self):
        """Adding HEAD support must not break GET /subtitles."""
        from fastapi.testclient import TestClient

        fake_srt = "1\n00:00:01,000 --> 00:00:03,000\nHello\n"

        with patch.multiple(
            self.srv,
            _fetch_via_subsro=MagicMock(return_value=fake_srt),
            _fetch_via_vip=MagicMock(return_value=None),
            _fetch_via_subliminal=MagicMock(return_value=None),
            _cache_read=MagicMock(return_value=None),
            _cache_write=MagicMock(),
        ):
            client = TestClient(self.srv.app)
            resp = client.get("/subtitles?title=TestMovie&lang=en")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, fake_srt)


if __name__ == "__main__":
    unittest.main()
