# X87 Server

All server-side code for the X87 Player platform. Three Flask services run behind an Nginx reverse proxy on a CentOS/RHEL Linux server.

## Services

| Service | Entry file | Port | URL | systemd unit |
|---------|-----------|------|-----|--------------|
| Admin Panel | `admin/admin_main.py` | 5000 | https://admin.x87player.xyz | `x87-admin` |
| Customer Portal | `portal/portal_main.py` | 5001 | https://portal.x87player.xyz | `x87-portal` |
| Home Page | `home/main.py` | 5002 | https://x87player.xyz | `x87-home` |

## Directory Structure

```
server/
├── admin/                       # Admin Panel Flask app
│   └── admin_main.py            # Entry point (port 5000)
├── portal/                      # Customer Portal Flask app
│   └── portal_main.py           # Entry point (port 5001)
├── home/                        # Public Home Page Flask app
│   └── main.py                  # Entry point (port 5002)
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
# Check status
systemctl status x87-admin x87-portal x87-home

# Start / restart
systemctl start x87-admin x87-portal x87-home
systemctl restart x87-admin x87-portal x87-home

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
systemctl restart x87-admin x87-portal x87-home
```

## Troubleshooting

**502 Bad Gateway** — Flask services aren't running or systemd can't find the working directory:

```bash
systemctl status x87-admin x87-portal x87-home
```

If you see `status=200/CHDIR`, the `WorkingDirectory` in the unit file is wrong. Check:

- `/etc/systemd/system/x87-admin.service`
- `/etc/systemd/system/x87-portal.service`
- `/etc/systemd/system/x87-home.service`

Fix paths, then `systemctl daemon-reload && systemctl restart x87-admin x87-portal x87-home`.

## Full Setup

See the [root README](../README.md) for complete server setup instructions, or [docs/server-setup.md](../docs/server-setup.md) for the extended guide.