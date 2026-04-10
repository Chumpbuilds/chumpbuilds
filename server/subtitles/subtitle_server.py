"""
X87 Subtitle Service — FastAPI app on port 8642.

Provider priority (highest first):
  1. subs.ro REST API            (requires SUBSRO_API_KEY)
  2. OpenSubtitles VIP REST API  (requires OPENSUBTITLES_API_KEY + credentials)
  3. subliminal fallback          (always available when subliminal is installed)

Environment variables (all optional — omit providers to skip them):
    SUBSRO_API_KEY            subs.ro API key
    OPENSUBTITLES_API_KEY     OpenSubtitles consumer API key
    OPENSUBTITLES_USERNAME    OpenSubtitles account username
    OPENSUBTITLES_PASSWORD    OpenSubtitles account password

A .env file at the same directory as this script is loaded automatically if
python-dotenv is installed.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

# ---------------------------------------------------------------------------
# Load .env from the same directory as this script (best-effort)
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("subtitle_server")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CACHE_DIR = Path("/opt/iptv-panel/subtitle_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

VIP_BASE = "https://vip-api.opensubtitles.com/api/v1"
USER_AGENT = "X87Player v1.0"

API_KEY = os.getenv("OPENSUBTITLES_API_KEY", "")
OS_USERNAME = os.getenv("OPENSUBTITLES_USERNAME", "")
OS_PASSWORD = os.getenv("OPENSUBTITLES_PASSWORD", "")

# subs.ro — set SUBSRO_API_KEY to enable (empty string = disabled)
SUBSRO_API_KEY = os.getenv("SUBSRO_API_KEY", "")
SUBSRO_BASE = "https://api.subs.ro"

# In-memory JWT token store
_jwt_token: str = ""
_jwt_expires: float = -1.0  # epoch seconds; -1 means not yet authenticated

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="X87 Subtitle Service")


# ---------------------------------------------------------------------------
# OpenSubtitles VIP REST client helpers
# ---------------------------------------------------------------------------

def _vip_headers() -> dict:
    headers = {
        "User-Agent": USER_AGENT,
        "Api-Key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if _jwt_token:
        headers["Authorization"] = f"Bearer {_jwt_token}"
    return headers


def _vip_login() -> bool:
    """Login to the VIP API and store the JWT token. Returns True on success."""
    global _jwt_token, _jwt_expires
    if not API_KEY or not OS_USERNAME or not OS_PASSWORD:
        logger.warning("OpenSubtitles VIP credentials not configured — skipping login")
        return False
    try:
        logger.info("OpenSubtitles VIP: logging in as %s", OS_USERNAME)
        resp = httpx.post(
            f"{VIP_BASE}/login",
            json={"username": OS_USERNAME, "password": OS_PASSWORD},
            headers={"User-Agent": USER_AGENT, "Api-Key": API_KEY, "Content-Type": "application/json"},
            timeout=15,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
        _jwt_token = data.get("token", "")
        # OpenSubtitles tokens expire after 24 h; store expiry as now + 23 h
        _jwt_expires = time.time() + 23 * 3600
        logger.info("OpenSubtitles VIP: login successful")
        return True
    except Exception as exc:
        logger.error("OpenSubtitles VIP: login failed — %s", exc)
        _jwt_token = ""
        return False


def _ensure_authenticated() -> bool:
    """Ensure we have a valid JWT. Returns True if authenticated."""
    global _jwt_token, _jwt_expires
    if not API_KEY:
        return False
    if _jwt_token and time.time() < _jwt_expires:
        return True
    return _vip_login()


def _vip_search_subtitles(
    title: str,
    lang: str,
    year: int | None,
    tmdb_id: int | None,
    imdb_id: str | None,
    season: int | None,
    episode: int | None,
) -> list[dict]:
    """Search VIP API. Returns list of subtitle result dicts from the `data` array."""
    is_episode = season is not None and episode is not None
    params: dict = {"query": title, "languages": lang}
    if is_episode:
        # Use episode-specific search type to avoid returning movie subtitles.
        params["type"] = "episode"
    if tmdb_id:
        params["tmdb_id"] = tmdb_id
    if imdb_id:
        # Strip 'tt' prefix if present — the API wants the numeric ID
        numeric = imdb_id.lstrip("t")
        if numeric:
            params["imdb_id"] = numeric
    if year:
        params["year"] = year
    if season:
        params["season_number"] = season
    if episode:
        params["episode_number"] = episode

    logger.info(
        "VIP search params: title='%s' lang=%s season=%s episode=%s tmdb_id=%s year=%s",
        title, lang, season, episode, tmdb_id, year,
    )

    resp = httpx.get(
        f"{VIP_BASE}/subtitles",
        params=params,
        headers=_vip_headers(),
        timeout=20,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def _vip_download_subtitle(file_id: int) -> str:
    """Download a subtitle by file_id. Returns the SRT text."""
    resp = httpx.post(
        f"{VIP_BASE}/download",
        json={"file_id": file_id},
        headers=_vip_headers(),
        timeout=20,
        follow_redirects=True,
    )
    resp.raise_for_status()
    link = resp.json().get("link", "")
    if not link:
        raise ValueError("VIP download response contained no link")
    srt_resp = httpx.get(link, timeout=30, follow_redirects=True)
    srt_resp.raise_for_status()
    return srt_resp.text


def _fetch_via_vip(
    title: str,
    lang: str,
    year: int | None,
    tmdb_id: int | None,
    imdb_id: str | None,
    season: int | None,
    episode: int | None,
) -> str | None:
    """Try to fetch subtitle via VIP API. Returns SRT text or None."""
    if not _ensure_authenticated():
        logger.info("OpenSubtitles VIP: not configured or auth failed — skipping")
        return None

    try:
        results = _vip_search_subtitles(title, lang, year, tmdb_id, imdb_id, season, episode)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            logger.warning("OpenSubtitles VIP: 401 on search — refreshing token")
            if not _vip_login():
                return None
            try:
                results = _vip_search_subtitles(title, lang, year, tmdb_id, imdb_id, season, episode)
            except Exception as exc2:
                logger.error("OpenSubtitles VIP: search failed after token refresh — %s", exc2)
                return None
        else:
            logger.error("OpenSubtitles VIP: search HTTP error — %s", exc)
            return None
    except Exception as exc:
        logger.error("OpenSubtitles VIP: search error — %s", exc)
        return None

    if not results:
        logger.info("OpenSubtitles VIP: no results for '%s' (%s)", title, lang)
        return None

    # Filter results to only include the requested language
    filtered = [
        r for r in results
        if r.get("attributes", {}).get("language", "").lower() == lang.lower()
    ]

    logger.info(
        "OpenSubtitles VIP: %d total results, %d matching lang='%s' for '%s'",
        len(results), len(filtered), lang, title,
    )

    if not filtered:
        logger.info("OpenSubtitles VIP: no results matching language '%s' for '%s'", lang, title)
        return None

    # For TV episodes, prefer results whose season/episode attributes match exactly.
    # This avoids picking up subtitles for the wrong episode of the same series.
    if season is not None and episode is not None:
        episode_matches = [
            r for r in filtered
            if (
                r.get("attributes", {}).get("season_number") == season
                and r.get("attributes", {}).get("episode_number") == episode
            )
        ]
        if episode_matches:
            logger.info(
                "OpenSubtitles VIP: %d exact S%02dE%02d matches for '%s'",
                len(episode_matches), season, episode, title,
            )
            filtered = episode_matches
        else:
            logger.warning(
                "OpenSubtitles VIP: no exact S%02dE%02d attribute match for '%s' — "
                "using all %d language-filtered results (API may not return episode attrs)",
                season, episode, title, len(filtered),
            )

    # Pick best result: highest download_count
    best = max(
        filtered,
        key=lambda r: r.get("attributes", {}).get("download_count", 0),
    )
    best_attrs = best.get("attributes", {})
    logger.info(
        "OpenSubtitles VIP: selected release='%s' downloads=%d season_attr=%s episode_attr=%s",
        best_attrs.get("release", ""),
        best_attrs.get("download_count", 0),
        best_attrs.get("season_number"),
        best_attrs.get("episode_number"),
    )
    files = best_attrs.get("files", [])
    if not files:
        logger.warning("OpenSubtitles VIP: chosen result has no files")
        return None
    file_id = files[0].get("file_id")
    if not file_id:
        logger.warning("OpenSubtitles VIP: file entry has no file_id")
        return None

    logger.info("OpenSubtitles VIP: downloading file_id=%s", file_id)
    try:
        srt_text = _vip_download_subtitle(file_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            logger.warning("OpenSubtitles VIP: 401 on download — refreshing token")
            if not _vip_login():
                return None
            try:
                srt_text = _vip_download_subtitle(file_id)
            except Exception as exc2:
                logger.error("OpenSubtitles VIP: download failed after token refresh — %s", exc2)
                return None
        else:
            logger.error("OpenSubtitles VIP: download HTTP error — %s", exc)
            return None
    except Exception as exc:
        logger.error("OpenSubtitles VIP: download error — %s", exc)
        return None

    logger.info("OpenSubtitles VIP: subtitle fetched successfully for '%s'", title)
    return srt_text


# ---------------------------------------------------------------------------
# subs.ro provider
# ---------------------------------------------------------------------------

def _subsro_search(
    title: str,
    lang: str,
    year: int | None,
    imdb_id: str | None,
    season: int | None,
    episode: int | None,
) -> list[dict]:
    """Search subs.ro API. Returns list of subtitle result dicts."""
    params: dict = {
        "apikey": SUBSRO_API_KEY,
        "query": title,
        "language": lang,
    }
    if year:
        params["year"] = year
    if imdb_id:
        params["imdb_id"] = imdb_id
    if season is not None:
        params["season"] = season
    if episode is not None:
        params["episode"] = episode

    logger.info(
        "subs.ro search params: title='%s' lang=%s season=%s episode=%s year=%s",
        title, lang, season, episode, year,
    )

    resp = httpx.get(
        f"{SUBSRO_BASE}/subtitles",
        params=params,
        timeout=20,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()
    # The API may return {"subtitles": [...]} or a bare list
    if isinstance(data, list):
        return data
    return data.get("subtitles", data.get("data", []))


def _subsro_download(download_url: str, params: dict | None = None) -> str:
    """Download subtitle content from the URL returned by subs.ro. Returns SRT text."""
    resp = httpx.get(download_url, params=params, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _fetch_via_subsro(
    title: str,
    lang: str,
    year: int | None,
    imdb_id: str | None,
    season: int | None,
    episode: int | None,
) -> str | None:
    """Try to fetch subtitle via subs.ro. Returns SRT text or None."""
    if not SUBSRO_API_KEY:
        logger.info("subs.ro: SUBSRO_API_KEY not configured — skipping")
        return None

    try:
        results = _subsro_search(title, lang, year, imdb_id, season, episode)
    except Exception as exc:
        logger.error("subs.ro: search error — %s", exc)
        return None

    if not results:
        logger.info("subs.ro: no results for '%s' (%s)", title, lang)
        return None

    # Normalise language field: filter to requested language
    filtered = [
        r for r in results
        if str(r.get("language", r.get("lang", ""))).lower() == lang.lower()
    ]

    logger.info(
        "subs.ro: %d total results, %d matching lang='%s' for '%s'",
        len(results), len(filtered), lang, title,
    )

    if not filtered:
        logger.info("subs.ro: no results matching language '%s' for '%s'", lang, title)
        return None

    # For TV episodes, prefer exact season/episode attribute match
    if season is not None and episode is not None:
        episode_matches = [
            r for r in filtered
            if (
                r.get("season") == season or r.get("season_number") == season
            ) and (
                r.get("episode") == episode or r.get("episode_number") == episode
            )
        ]
        if episode_matches:
            logger.info(
                "subs.ro: %d exact S%02dE%02d matches for '%s'",
                len(episode_matches), season, episode, title,
            )
            filtered = episode_matches
        else:
            logger.warning(
                "subs.ro: no exact S%02dE%02d attribute match for '%s' — "
                "using all %d language-filtered results",
                season, episode, title, len(filtered),
            )

    # Pick best result: prefer highest download count, then first result
    best = max(
        filtered,
        key=lambda r: r.get("download_count", r.get("downloads", 0)),
        default=filtered[0],
    )

    # Resolve download URL — subs.ro may return 'url', 'download_url', or 'id'
    download_url = best.get("url") or best.get("download_url") or ""
    download_params: dict | None = None
    if not download_url:
        sub_id = best.get("id")
        if sub_id:
            # Pass the API key via httpx params so it is never concatenated into
            # the URL string (avoids key leakage in exception tracebacks).
            download_url = f"{SUBSRO_BASE}/subtitles/{sub_id}/download"
            download_params = {"apikey": SUBSRO_API_KEY}
    if not download_url:
        logger.warning("subs.ro: selected result has no download URL for '%s'", title)
        return None

    logger.info(
        "subs.ro: downloading subtitle for '%s' (release='%s')",
        title, best.get("release", best.get("title", "")),
    )

    try:
        srt_text = _subsro_download(download_url, params=download_params)
    except Exception as exc:
        logger.error("subs.ro: download error — %s", exc)
        return None

    if not srt_text or not srt_text.strip():
        logger.warning("subs.ro: empty subtitle content for '%s'", title)
        return None

    logger.info("subs.ro: subtitle fetched successfully for '%s'", title)
    return srt_text


# ---------------------------------------------------------------------------
# Subliminal fallback
# ---------------------------------------------------------------------------

def _fetch_via_subliminal(
    title: str,
    lang: str,
    year: int | None,
    season: int | None,
    episode: int | None,
) -> str | None:
    """Search subtitle providers via subliminal. Returns SRT text or None."""
    try:
        import babelfish
        import subliminal
    except ImportError:
        logger.error("subliminal is not installed — cannot use fallback")
        return None

    try:
        lang_obj = babelfish.Language.fromietf(lang)
    except Exception:
        logger.warning("subliminal: unrecognised language '%s', defaulting to English", lang)
        lang_obj = babelfish.Language("eng")

    providers = ["opensubtitles", "podnapisi", "tvsubtitles"]

    try:
        if season is not None and episode is not None:
            video = subliminal.Episode(title, season, episode, year=year)
        else:
            video = subliminal.Movie(title, year=year)
    except Exception as exc:
        logger.error("subliminal: failed to build video object — %s", exc)
        return None

    try:
        subtitles = subliminal.download_best_subtitles(
            [video],
            {lang_obj},
            providers=providers,
        )
    except Exception as exc:
        logger.error("subliminal: download_best_subtitles failed — %s", exc)
        return None

    video_subs = subtitles.get(video, [])
    if not video_subs:
        logger.info("subliminal: no subtitles found for '%s'", title)
        return None

    try:
        subliminal.save_subtitles(video, video_subs)
        srt_file = Path(str(video.name) + ".srt")
        if srt_file.exists():
            text = srt_file.read_text(errors="replace")
            srt_file.unlink(missing_ok=True)
            logger.info("subliminal: subtitle found for '%s'", title)
            return text
        # If save_subtitles wrote content directly, try composing from subtitle object
        srt_content = video_subs[0].content
        if isinstance(srt_content, bytes):
            return srt_content.decode("utf-8", errors="replace")
        if isinstance(srt_content, str):
            return srt_content
    except Exception as exc:
        logger.error("subliminal: failed to retrieve subtitle content — %s", exc)

    return None


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_key(
    title: str,
    lang: str,
    year: int | None,
    tmdb_id: int | None,
    imdb_id: str | None,
    season: int | None,
    episode: int | None,
) -> str:
    raw = f"{title}|{lang}|{year}|{tmdb_id}|{imdb_id}|{season}|{episode}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_read(key: str) -> str | None:
    path = CACHE_DIR / f"{key}.srt"
    if path.exists():
        return path.read_text(errors="replace")
    return None


def _cache_write(key: str, content: str) -> None:
    path = CACHE_DIR / f"{key}.srt"
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/subtitles", response_class=PlainTextResponse)
async def get_subtitles(
    title: str = Query(..., description="Movie or episode title"),
    year: int | None = Query(None),
    tmdb_id: int | None = Query(None),
    imdb_id: str | None = Query(None),
    season: int | None = Query(None),
    episode: int | None = Query(None),
    lang: str = Query("en"),
) -> PlainTextResponse:
    logger.info(
        "Subtitle request: title='%s' season=%s episode=%s lang=%s year=%s",
        title, season, episode, lang, year,
    )
    key = _cache_key(title, lang, year, tmdb_id, imdb_id, season, episode)
    cached = _cache_read(key)
    if cached:
        ep_info = f" S{season:02d}E{episode:02d}" if (season is not None and episode is not None) else ""
        logger.info("Cache hit for '%s'%s (%s)", title, ep_info, lang)
        return PlainTextResponse(cached, status_code=200)

    # --- Priority 1: subs.ro ---
    srt_text = _fetch_via_subsro(title, lang, year, imdb_id, season, episode)
    provider_used = "subs.ro"

    # --- Priority 2: OpenSubtitles VIP REST API ---
    if srt_text is None:
        logger.info("Falling back to OpenSubtitles VIP for '%s' (%s)", title, lang)
        srt_text = _fetch_via_vip(title, lang, year, tmdb_id, imdb_id, season, episode)
        provider_used = "OpenSubtitles VIP"

    # --- Priority 3: subliminal ---
    if srt_text is None:
        logger.info("Falling back to subliminal for '%s' (%s)", title, lang)
        srt_text = _fetch_via_subliminal(title, lang, year, season, episode)
        provider_used = "subliminal"

    if srt_text is None:
        logger.info("No subtitles found for '%s' (%s)", title, lang)
        return PlainTextResponse("No subtitles found", status_code=404)

    logger.info("Subtitle fetched via %s for '%s' (%s)", provider_used, title, lang)
    _cache_write(key, srt_text)
    return PlainTextResponse(srt_text, status_code=200)


@app.get("/subtitles/search")
async def search_subtitles(
    title: str = Query(..., description="Movie or episode title"),
    year: int | None = Query(None),
    tmdb_id: int | None = Query(None),
    imdb_id: str | None = Query(None),
    season: int | None = Query(None),
    episode: int | None = Query(None),
    lang: str = Query("en"),
) -> JSONResponse:
    """Return a JSON list of subtitle results with metadata for the given content."""
    if not _ensure_authenticated():
        logger.info("OpenSubtitles VIP: not configured or auth failed")
        return JSONResponse([], status_code=200)

    try:
        results = _vip_search_subtitles(title, lang, year, tmdb_id, imdb_id, season, episode)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            logger.warning("OpenSubtitles VIP: 401 on search — refreshing token")
            if not _vip_login():
                return JSONResponse([], status_code=200)
            try:
                results = _vip_search_subtitles(title, lang, year, tmdb_id, imdb_id, season, episode)
            except Exception as exc2:
                logger.error("OpenSubtitles VIP: search failed after token refresh — %s", exc2)
                return JSONResponse([], status_code=200)
        else:
            logger.error("OpenSubtitles VIP: search HTTP error — %s", exc)
            return JSONResponse([], status_code=200)
    except Exception as exc:
        logger.error("OpenSubtitles VIP: search error — %s", exc)
        return JSONResponse([], status_code=200)

    output = []
    for r in results:
        attrs = r.get("attributes", {})
        # Skip results that don't match the requested language
        if attrs.get("language", "").lower() != lang.lower():
            continue
        files = attrs.get("files", [])
        if not files:
            continue
        file_id = files[0].get("file_id")
        if not file_id:
            continue
        output.append({
            "file_id": file_id,
            "language": attrs.get("language", lang),
            "release": attrs.get("release", ""),
            "download_count": attrs.get("download_count", 0),
            "season_number": attrs.get("season_number"),
            "episode_number": attrs.get("episode_number"),
            "provider": "OpenSubtitles VIP",
        })

    logger.info(
        "Search returned %d results for '%s' season=%s episode=%s (%s)",
        len(output), title, season, episode, lang,
    )
    return JSONResponse(output, status_code=200)


@app.get("/subtitles/download", response_class=PlainTextResponse)
async def download_subtitle(
    file_id: int = Query(..., description="OpenSubtitles file_id to download"),
) -> PlainTextResponse:
    """Download a specific subtitle by file_id and return its SRT content."""
    cache_key = f"file_{file_id}"
    cached = _cache_read(cache_key)
    if cached:
        logger.info("Cache hit for file_id=%s", file_id)
        return PlainTextResponse(cached, status_code=200)

    if not _ensure_authenticated():
        raise HTTPException(status_code=503, detail="OpenSubtitles VIP not configured or auth failed")

    try:
        srt_text = _vip_download_subtitle(file_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            logger.warning("OpenSubtitles VIP: 401 on download — refreshing token")
            if not _vip_login():
                raise HTTPException(status_code=503, detail="OpenSubtitles VIP authentication failed")
            try:
                srt_text = _vip_download_subtitle(file_id)
            except Exception as exc2:
                logger.error("OpenSubtitles VIP: download failed after token refresh — %s", exc2)
                raise HTTPException(status_code=502, detail=str(exc2))
        else:
            logger.error("OpenSubtitles VIP: download HTTP error — %s", exc)
            raise HTTPException(status_code=exc.response.status_code, detail=str(exc))
    except Exception as exc:
        logger.error("OpenSubtitles VIP: download error — %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    _cache_write(cache_key, srt_text)
    logger.info("Downloaded subtitle file_id=%s (%d bytes)", file_id, len(srt_text))
    return PlainTextResponse(srt_text, status_code=200)


@app.get("/health")
async def health() -> dict:
    vip_configured = bool(API_KEY and OS_USERNAME and OS_PASSWORD)
    vip_authenticated = bool(_jwt_token and time.time() < _jwt_expires)
    subsro_configured = bool(SUBSRO_API_KEY)
    return {
        "status": "ok",
        "subsro": {
            "configured": subsro_configured,
        },
        "opensubtitles_vip": {
            "configured": vip_configured,
            "authenticated": vip_authenticated,
        },
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("subtitle_server:app", host="127.0.0.1", port=8642, reload=False)
