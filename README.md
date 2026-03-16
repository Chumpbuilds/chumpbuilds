# X87 Player

Professional IPTV player platform with license management, admin panel and customer portal.

## Live Services

| Service | URL |
|---------|-----|
| 🏠 Home | https://x87player.xyz |
| 🔧 Admin | https://admin.x87player.xyz |
| 👤 Portal | https://portal.x87player.xyz |

## Repository Structure

```
X87/
├── server/          # Server-side code (Admin, Portal, Home page)
├── clients/
│   ├── windows/     # Windows desktop app (Python + PyQt6)
│   ├── android/     # Android app (Coming Soon)
│   └── ios/         # iOS app (Coming Soon)
├── releases/        # Built binaries (.exe, .apk, .ipa)
└── docs/            # Additional docs (may be incomplete vs this README)
```

---

# Server Setup / Deployment (Linux)

## Requirements

- CentOS/RHEL (or compatible Linux)
- Python 3.9+
- Nginx
- systemd

## Production install path

Clone/check out the repo to:

- `/opt/iptv-panel`

Example:

```bash
cd /opt
git clone https://github.com/Electro26/X87.git iptv-panel
cd /opt/iptv-panel
```

## Server services (ports + entry files)

Three Flask services run on the server:

| Service | File | Port | Public URL |
|---------|------|------|------------|
| Admin Panel | `server/admin/admin_main.py` | 5000 | https://admin.x87player.xyz |
| Customer Portal | `server/portal/portal_main.py` | 5001 | https://portal.x87player.xyz |
| Home Page | `server/home/main.py` | 5002 | https://x87player.xyz |

## systemd service names

Expected service names:

- `x87-admin`
- `x87-portal`
- `x87-home`

Common commands:

```bash
systemctl status x87-admin x87-portal x87-home
systemctl start x87-admin x87-portal x87-home
systemctl restart x87-admin x87-portal x87-home
```

## Troubleshooting: 502 Bad Gateway (nginx) + `status=200/CHDIR`

If nginx shows **502 Bad Gateway**, check service status:

```bash
systemctl status x87-admin x87-portal x87-home
```

If you see `status=200/CHDIR`, it means systemd cannot `chdir` into the `WorkingDirectory` (or the path in `ExecStart` is wrong).

Check your unit files:

- `/etc/systemd/system/x87-admin.service`
- `/etc/systemd/system/x87-portal.service`
- `/etc/systemd/system/x87-home.service`

Paths must reference the repo layout under `/opt/iptv-panel/server/...`, e.g.:

- `/opt/iptv-panel/server/admin/admin_main.py`
- `/opt/iptv-panel/server/portal/portal_main.py`
- `/opt/iptv-panel/server/home/main.py`

After fixing:

```bash
systemctl daemon-reload
systemctl restart x87-admin x87-portal x87-home
```

## Nginx reverse proxy

Nginx proxies requests to the above ports.

Because nginx layouts differ by distro, check configs in one of:

- `/etc/nginx/nginx.conf`
- `/etc/nginx/conf.d/*.conf`
- `/etc/nginx/sites-available/*` + `/etc/nginx/sites-enabled/*`

Test + reload:

```bash
nginx -t
systemctl reload nginx
```

## Updating the server (manual pull)

Sometimes `.pyc` compiled Python files or cache files change locally and will block `git pull`.
Safe workflow:

```bash
cd /opt/iptv-panel
git status

# discard local changes (commonly .pyc / cache)
git checkout -- .

# pull latest
git pull

# restart services
systemctl restart x87-admin x87-portal x87-home
```

---

# Windows Client – Local Data & Security

## "Deactivate License" = FULL WIPE (Public PC safe)

The Windows app Settings dialog includes a **🔑 Deactivate License** button intended for shared/public PCs.

When confirmed, it wipes ALL locally stored settings and saved credentials using Qt `QSettings`, then closes the app.

Namespaces cleared:

- `QSettings('IPTVPlayer', 'License')` — activation/license info
- `QSettings('IPTVPlayer', 'LoginSettings')` — saved IPTV profiles, usernames, passwords, server URLs
- `QSettings('IPTVPlayer', 'Settings')` — app settings
- `QSettings('IPTVPlayer', 'VLCSettings')` — buffer/VLC settings

On Windows, `QSettings` typically maps to Registry under:

- `HKEY_CURRENT_USER\Software\IPTVPlayer\...`

After deactivation, the device is left in a "fresh install" state:

- no saved IPTV usernames/passwords
- no saved profiles
- no app settings
- user must re-enter activation code on next launch

---

# Additional Docs

> This root README is the **source of truth**. The docs below may have more detail but could be out of date.

- [Server Setup](docs/server-setup.md)
- [Windows Build](docs/windows-build.md)
- [Mobile Build](docs/mobile-build.md)