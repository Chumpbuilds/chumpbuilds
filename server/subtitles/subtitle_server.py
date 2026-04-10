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
import io
import logging
import os
import time
import zipfile
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response

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

# Suppress httpx request/response logs at INFO level to prevent sensitive URLs
# (e.g. those that might contain tokens or keys) from appearing in the log stream.
logging.getLogger("httpx").setLevel(logging.WARNING)

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
SUBSRO_BASE = "https://api.subs.ro/v1.0"

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
    """Search subs.ro API v1.0. Returns list of subtitle result dicts."""
    # Choose the most specific search field available.
    # Prefer imdbid when present; fall back to title search.
    if imdb_id:
        search_field = "imdbid"
        search_value = imdb_id
    else:
        search_field = "title"
        search_value = title

    params: dict = {}
    if lang:
        params["language"] = lang

    logger.info(
        "subs.ro search: field=%s value='%s' lang=%s",
        search_field, search_value, lang,
    )

    resp = httpx.get(
        f"{SUBSRO_BASE}/search/{search_field}/{search_value}",
        params=params,
        headers={"X-Subs-Api-Key": SUBSRO_API_KEY},
        timeout=20,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()
    # v1.0 API returns {"status": ..., "items": [...], "count": ...}
    if isinstance(data, list):
        return data
    return data.get("items", data.get("subtitles", data.get("data", [])))


_ZIP_MAGIC = b"PK\x03\x04"


def _extract_srt_from_zip(data: bytes) -> str:
    """Extract the best .srt file from a ZIP archive (in-memory).

    Selection rules:
    - Only considers entries whose names end with ``.srt`` (case-insensitive).
    - Ignores directory entries.
    - If multiple candidates exist, picks the largest by uncompressed size
      (most likely the main subtitle track).

    Returns the decoded SRT text (UTF-8 with fallback to latin-1).
    Raises ``zipfile.BadZipFile`` if ``data`` is not a valid ZIP.
    Raises ``ValueError`` if no ``.srt`` entry is found.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        candidates = [
            info for info in zf.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".srt")
        ]
        if not candidates:
            raise ValueError("ZIP archive contains no .srt file")

        # Pick the largest uncompressed entry
        best = max(candidates, key=lambda info: info.file_size)
        logger.info(
            "subs.ro: ZIP archive detected — extracting '%s' (%d bytes)",
            best.filename,
            best.file_size,
        )
        raw = zf.read(best.filename)

    # Decode: try UTF-8, then cp1250 (common for Romanian/Eastern European subs), then latin-1
    for encoding in ("utf-8", "cp1250", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    # latin-1 is a superset of all single bytes, so this should never be reached
    return raw.decode("latin-1", errors="replace")


def _subsro_download(download_url: str) -> str:
    """Download subtitle content from the URL returned by subs.ro. Returns SRT text.

    subs.ro occasionally returns a ZIP archive even when ``Content-Type`` is
    ``text/plain``.  This function detects the ZIP magic bytes and transparently
    extracts the largest ``.srt`` entry so callers always receive plain SRT text.
    """
    resp = httpx.get(
        download_url,
        headers={"X-Subs-Api-Key": SUBSRO_API_KEY},
        timeout=30,
        follow_redirects=True,
    )
    resp.raise_for_status()

    raw = resp.content
    if raw[:4] == _ZIP_MAGIC:
        logger.info("subs.ro: response is a ZIP archive — extracting .srt")
        return _extract_srt_from_zip(raw)

    # Plain text (or other encoding) — decode via httpx charset detection
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

    # Resolve download URL — subs.ro v1.0 provides a downloadLink field or an id
    download_url = best.get("downloadLink") or best.get("url") or best.get("download_url") or ""
    if not download_url:
        sub_id = best.get("id")
        if sub_id:
            download_url = f"{SUBSRO_BASE}/subtitle/{sub_id}/download"
    if not download_url:
        logger.warning("subs.ro: selected result has no download URL for '%s'", title)
        return None

    logger.info(
        "subs.ro: downloading subtitle for '%s' (release='%s')",
        title, best.get("release", best.get("title", "")),
    )

    try:
        srt_text = _subsro_download(download_url)
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
        content = path.read_text(errors="replace")
        # Guard against cache entries that were written before ZIP extraction was
        # implemented (i.e. raw ZIP bytes stored as text).  The first four
        # characters map 1-to-1 to the ZIP local-file-header magic PK\x03\x04.
        if content.startswith("PK\x03\x04"):
            logger.warning(
                "Cache file %s contains ZIP bytes — deleting poisoned entry",
                path.name,
            )
            path.unlink(missing_ok=True)
            return None
        return content
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
        # Defense-in-depth: _cache_read already evicts poisoned entries, but
        # guard here too in case the check is bypassed (e.g. in tests or future
        # refactors).
        if cached.startswith("PK\x03\x04"):
            logger.error(
                "Cached content for '%s' (%s) starts with ZIP magic bytes — refusing",
                title, lang,
            )
            return Response(
                content="Cached subtitle data is corrupt (ZIP bytes); please retry",
                media_type="text/plain; charset=utf-8",
                status_code=502,
            )
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

    # Safety guard: a provider must never return raw ZIP bytes.  This catches
    # any edge case (e.g. a broken provider, or a result that slipped through
    # the subs.ro extraction path) before the bytes reach the client or cache.
    if srt_text.startswith("PK\x03\x04"):
        logger.error(
            "Provider '%s' returned ZIP bytes for '%s' (%s) — refusing to pass through",
            provider_used, title, lang,
        )
        return Response(
            content="Subtitle provider returned a ZIP archive; SRT extraction failed",
            media_type="text/plain; charset=utf-8",
            status_code=502,
        )

    # Strip UTF-8 BOM if present — some providers encode files with a BOM
    # which causes Android/ExoPlayer to fail to parse the first cue index.
    srt_text = srt_text.lstrip("\ufeff")

    logger.info("Subtitle fetched via %s for '%s' (%s)", provider_used, title, lang)
    _cache_write(key, srt_text)
    return PlainTextResponse(srt_text, media_type="text/plain; charset=utf-8", status_code=200)


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

    srt_text = srt_text.lstrip("\ufeff")
    _cache_write(cache_key, srt_text)
    logger.info("Downloaded subtitle file_id=%s (%d bytes)", file_id, len(srt_text))
    return PlainTextResponse(srt_text, media_type="text/plain; charset=utf-8", status_code=200)


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
