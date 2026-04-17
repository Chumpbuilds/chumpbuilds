import os
import tempfile

try:
    import httpx
except Exception:  # pragma: no cover - fallback for environments without httpx
    httpx = None
    import requests

SUBTITLE_API_BASE = "https://x87player.xyz"


def _http_get(url, params, timeout):
    if httpx is not None:
        return httpx.get(url, params=params, timeout=timeout)
    return requests.get(url, params=params, timeout=timeout)


def search_subtitles(
    title,
    lang="en",
    year=None,
    tmdb_id=None,
    imdb_id=None,
    season=None,
    episode=None,
):
    """Call GET /subtitles/search and return list of results."""
    params = {"title": title, "lang": lang}
    if year:
        params["year"] = year
    if tmdb_id:
        params["tmdb_id"] = tmdb_id
    if imdb_id:
        params["imdb_id"] = imdb_id
    if season is not None:
        params["season"] = season
    if episode is not None:
        params["episode"] = episode
    resp = _http_get(f"{SUBTITLE_API_BASE}/subtitles/search", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def download_subtitle(file_id):
    """Call GET /subtitles/download?file_id=<id> and return SRT text."""
    resp = _http_get(f"{SUBTITLE_API_BASE}/subtitles/download", params={"file_id": file_id}, timeout=30)
    resp.raise_for_status()
    return resp.text


def save_srt_to_temp(srt_text, file_id):
    """Write SRT text to a temp file, return the file path."""
    path = os.path.join(tempfile.gettempdir(), f"x87_sub_{file_id}.srt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(srt_text)
    return path
