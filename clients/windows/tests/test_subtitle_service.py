import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

_windows_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
if _windows_dir not in sys.path:
    sys.path.insert(0, _windows_dir)

from services import subtitle_service


class TestSubtitleService(unittest.TestCase):
    @patch("services.subtitle_service._http_get")
    def test_search_subtitles_passes_expected_params(self, mock_get):
        response = MagicMock()
        response.json.return_value = [{"file_id": "123"}]
        mock_get.return_value = response

        results = subtitle_service.search_subtitles(
            title="The Matrix",
            lang="en",
            year=1999,
            tmdb_id=603,
            imdb_id="tt0133093",
            season=1,
            episode=2,
        )

        self.assertEqual(results, [{"file_id": "123"}])
        mock_get.assert_called_once_with(
            f"{subtitle_service.SUBTITLE_API_BASE}/subtitles/search",
            params={
                "title": "The Matrix",
                "lang": "en",
                "year": 1999,
                "tmdb_id": 603,
                "imdb_id": "tt0133093",
                "season": 1,
                "episode": 2,
            },
            timeout=30,
        )
        response.raise_for_status.assert_called_once()

    @patch("services.subtitle_service._http_get")
    def test_download_subtitle_returns_text(self, mock_get):
        response = MagicMock()
        response.text = "1\n00:00:01,000 --> 00:00:02,000\nHello\n"
        mock_get.return_value = response

        srt = subtitle_service.download_subtitle("abc")

        self.assertIn("Hello", srt)
        mock_get.assert_called_once_with(
            f"{subtitle_service.SUBTITLE_API_BASE}/subtitles/download",
            params={"file_id": "abc"},
            timeout=30,
        )
        response.raise_for_status.assert_called_once()

    def test_save_srt_to_temp_writes_file(self):
        file_id = "test-file"
        text = "1\n00:00:01,000 --> 00:00:02,000\nHi\n"
        path = subtitle_service.save_srt_to_temp(text, file_id)
        self.assertTrue(path.startswith(tempfile.gettempdir()))
        self.assertTrue(path.endswith(f"x87_sub_{file_id}.srt"))
        with open(path, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), text)
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
