# X87 Server

All server-side code for the X87 Player platform. Three Flask services and one FastAPI service run behind an Nginx reverse proxy on a CentOS/RHEL Linux server.

## Services

| Service | Entry file | Port | URL | systemd unit | Framework |
|---------|-----------|------|-----|--------------|-----------|
| Admin Panel | `admin/admin_main.py` | 5000 | https://admin.x87player.xyz | `x87-admin` | Flask |
| Customer Portal | `portal/portal_main.py` | 5001 | https://portal.x87player.xyz | `x87-portal` | Flask |
| Home Page | `home/main.py` | 5002 | https://x87player.xyz | `x87-home` | Flask |
| Subtitle Service | `subtitles/subtitle_server.py` | 8642 | https://x87player.xyz/subtitles | `x87-subtitles` | FastAPI |

## Directory Structure

```
server/
├── admin/                       # Admin Panel Flask app
│   └── admin_main.py            # Entry point (port 5000)
├── portal/                      # Customer Portal Flask app
│   └── portal_main.py           # Entry point (port 5001)
├── home/                        # Public Home Page Flask app
│   └── main.py                  # Entry point (port 5002)
├── subtitles/                   # Subtitle search FastAPI service
│   └── subtitle_server.py       # Entry point (port 8642)
├── instance/                    # Flask instance folder (database, config — gitignored on prod)
├── tests/                       # Server-side tests
├── license_manager.py           # Shared license management logic
├── complete_service_manager.py  # Service orchestration / management utilities
├── x87player.conf               # Nginx configuration file
└── README.md                    # This file
```

## Production Deployment

### Install path

```bash
cd /opt
git clone https://github.com/Electro26/X87.git iptv-panel
cd /opt/iptv-panel
```

All service paths reference `/opt/iptv-panel/server/...`.

### Common commands

```bash
# Check status of all services
systemctl status x87-admin x87-portal x87-home x87-subtitles

# Start / restart all services
systemctl start x87-admin x87-portal x87-home x87-subtitles
systemctl restart x87-admin x87-portal x87-home x87-subtitles

# Reload after unit file changes
systemctl daemon-reload
```

### Nginx

The included `x87player.conf` configures Nginx to reverse-proxy each subdomain to the correct Flask port. Copy or symlink it to your Nginx config directory:

```bash
# Example (adjust for your distro)
cp /opt/iptv-panel/server/x87player.conf /etc/nginx/conf.d/x87player.conf
nginx -t
systemctl reload nginx
```

### Updating

```bash
cd /opt/iptv-panel
git checkout -- .        # discard local changes (.pyc, cache, etc.)
git pull
systemctl restart x87-admin x87-portal x87-home x87-subtitles
```

---

## Subtitle Service

The subtitle service provides on-demand SRT subtitle fetching for the X87 desktop player. It is a standalone **FastAPI** app served by **uvicorn** on port **8642** (localhost only), exposed publicly via Nginx at `https://x87player.xyz/subtitles`.

### How it works

1. The desktop app sends a GET request with the movie/show title, year, and language.
2. The service checks the local SRT cache first — if a match exists it is returned immediately.
3. If not cached, the service queries the **OpenSubtitles VIP REST API** (primary).
4. If the VIP API returns no results or is not configured, the service falls back to the **subliminal** library (opensubtitles XML-RPC, podnapisi, gestdown, tvsubtitles).
5. The best-matching SRT is returned as plain text and written to the cache.
6. Subsequent requests for the same title/language are served instantly from cache.

### Providers

| Priority | Provider | Requires config |
|----------|----------|-----------------|
| Primary | **OpenSubtitles VIP REST API** (`vip-api.opensubtitles.com`) | Yes — see env vars below |
| Fallback | **subliminal** (opensubtitles XML-RPC, podnapisi, gestdown, tvsubtitles) | No |

### Environment Variables

Set these on the server to enable the VIP API. If they are absent, the service runs in subliminal-only mode.

| Variable | Description |
|----------|-------------|
| `OPENSUBTITLES_API_KEY` | Consumer API key from your OpenSubtitles profile |
| `OPENSUBTITLES_USERNAME` | OpenSubtitles account username |
| `OPENSUBTITLES_PASSWORD` | OpenSubtitles account password |

Copy `server/subtitles/.env.example` to `server/subtitles/.env` and fill in your values, or set the variables in the systemd unit file:

```bash
sudo systemctl edit x87-subtitles
# Add under [Service]:
# Environment="OPENSUBTITLES_API_KEY=your_key"
# Environment="OPENSUBTITLES_USERNAME=your_username"
# Environment="OPENSUBTITLES_PASSWORD=your_password"
sudo systemctl daemon-reload && sudo systemctl restart x87-subtitles
```

### API

**Endpoint:** `GET /subtitles`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `title` | string | yes | Movie or episode title |
| `year` | int | no | Release year |
| `tmdb_id` | int | no | TMDb ID (improves matching) |
| `imdb_id` | string | no | IMDb ID, e.g. `tt1234567` |
| `season` | int | no | Season number (for TV shows) |
| `episode` | int | no | Episode number (for TV shows) |
| `lang` | string | no | Language code, default `en` |

**Examples:**

```bash
# Movie
curl "https://x87player.xyz/subtitles?title=The%20Matrix&year=1999&lang=en"

# TV episode
curl "https://x87player.xyz/subtitles?title=Breaking%20Bad&season=1&episode=1&lang=en"

# With TMDb ID for better matching
curl "https://x87player.xyz/subtitles?title=Inception&year=2010&tmdb_id=27205&lang=en"
```

**Responses:**

| Status | Body | Meaning |
|--------|------|---------|
| 200 | SRT text | Subtitle found and returned |
| 404 | `No subtitles found` | No match from any provider |
| 500 | `Error: ...` | Server-side error |

**Health check:** `GET /health`

```bash
curl "https://x87player.xyz/subtitles/../health"
# or directly:
curl "http://127.0.0.1:8642/health"
```

### Cache

- Cached SRT files are stored in `/opt/iptv-panel/subtitle_cache/`
- Each file is named by an MD5 hash of the query parameters
- Cache is permanent — delete files manually to force a re-fetch:

```bash
# View cached files
ls -la /opt/iptv-panel/subtitle_cache/

# Clear all cached subtitles
rm -f /opt/iptv-panel/subtitle_cache/*.srt
```

### Dependencies

Installed via pip3 (system-wide):

- `fastapi`
- `uvicorn`
- `httpx` (HTTP client for the OpenSubtitles VIP REST API)
- `python-dotenv` (loads `.env` file on startup)
- `subliminal` (fallback provider — includes `babelfish`, `dogpile.cache`, `guessit`, etc.)

Install / update:

```bash
pip3 install httpx python-dotenv
# subliminal and fastapi/uvicorn should already be installed
```

### Service management

```bash
# Status / logs
systemctl status x87-subtitles
journalctl -u x87-subtitles -f        # live logs

# Restart
systemctl restart x87-subtitles

# Unit file location
/etc/systemd/system/x87-subtitles.service
```

### Firewall

Port 8642/tcp is open in firewalld (added permanently):

```bash
firewall-cmd --list-ports              # verify
firewall-cmd --permanent --add-port=8642/tcp  # (already done)
```

> **Note:** The service binds to `127.0.0.1` only — external access goes through Nginx on port 443. The firewall rule is a safety net in case the bind address changes.

### Nginx routing

The subtitle location block was added to the main `x87player.xyz` server block in `x87player.conf`:

```nginx
location /subtitles {
    proxy_pass http://127.0.0.1:8642/subtitles;
    proxy_read_timeout 120s;
    ...
}
```

The 120s timeout accommodates slow provider searches on first requests (before caching).

---

## Troubleshooting

**502 Bad Gateway** — Flask/FastAPI services aren't running or systemd can't find the working directory:

```bash
systemctl status x87-admin x87-portal x87-home x87-subtitles
```

If you see `status=200/CHDIR`, the `WorkingDirectory` in the unit file is wrong. Check:

- `/etc/systemd/system/x87-admin.service`
- `/etc/systemd/system/x87-portal.service`
- `/etc/systemd/system/x87-home.service`
- `/etc/systemd/system/x87-subtitles.service`

Fix paths, then `systemctl daemon-reload && systemctl restart x87-admin x87-portal x87-home x87-subtitles`.

**Subtitles returning 404 for new movies** — Free providers may not have subtitles for very recent releases. With the OpenSubtitles VIP API configured, results are significantly better. Without VIP credentials the service falls back to the free XML-RPC and other subliminal providers, which may lag on brand-new titles.

**Subtitles slow on first request** — First requests search the VIP API and/or multiple subliminal providers (up to ~30-60s). Subsequent requests for the same title are instant from cache.

## Full Setup

See the [root README](../README.md) for complete server setup instructions, or [docs/server-setup.md](../docs/server-setup.md) for the extended guide.