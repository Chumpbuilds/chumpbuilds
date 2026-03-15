# Server Setup Guide

## Requirements
- CentOS/RHEL Linux
- Python 3.9+
- Nginx
- Flask, Flask-CORS

## Services
Three Flask services run on the server:

| Service | File | Port |
|---------|------|------|
| Admin Panel | server/admin/admin_main.py | 5000 |
| Customer Portal | server/portal/portal_main.py | 5001 |
| Home Page | server/home/main.py | 5002 |

## Systemd Services
```bash
systemctl start x87-admin
systemctl start x87-portal
systemctl start x87-home
```

## Nginx
Config located at `server/x87player.conf`
