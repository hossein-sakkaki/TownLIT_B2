# 👨‍💻 Server 01 – Production: `townlit-prod-cpx21-de1`

## 1. General Info

| Key              | Value                          |
| ---------------- | ------------------------------ |
| Hostname         | townlit-prod-cpx21-de1         |
| Public IP        | 91.99.114.147                  |
| OS               | Ubuntu 22.04 LTS               |
| Docker Version   | 24.x                           |
| Docker Compose   | 2.x                            |
| Main Role        | Backend + DB + Redis           |
| Environment File | `/srv/townlit/.env.production` |
| Code Path        | `/srv/townlit/`                |

---

## 2. Running Services (via Docker)

| Service       | Container Name        | Exposed Ports   | Notes                                         |
| ------------- | --------------------- | --------------- | --------------------------------------------- |
| Backend       | `townlit_backend`     | Internal (8000) | Python 3.11, Gunicorn, connected to Nginx     |
| MySQL 8       | `townlit_mysql`       | 127.0.0.1:3306  | Bound to localhost only                       |
| Redis 7       | `townlit_redis`       | 127.0.0.1:6379  | Internal, password-protected                  |
| Celery Worker | `townlit_celery`      | —               | Handles task queues                           |
| Celery Beat   | `townlit_celery_beat` | —               | Periodic tasks                                |
| Nginx         | systemd (external)    | 80, 443         | Handles TLS, frontend & backend reverse proxy |

---

## 3. Nginx Config – `/etc/nginx/sites-available/townlit`

* All HTTP requests are redirected to HTTPS.
* HTTPS is secured via Let’s Encrypt certificates.
* Proxy rules:

  * `/api/` and `/admin/` → backend container at `172.18.0.4:8000`
  * `/` → frontend container at `172.19.0.2:3000`
  * `/static/` → `/srv/townlit/staticfiles/`
  * `/media/` → `/srv/townlit/media/`
  * `/static/admin/` → restricted to IP `172.218.33.146`

---

## 4. ENV File – `.env.production`

* Redis URL: `redis://:********@townlit_redis:6379/0`
* Celery backend: Redis
* S3: `townlit-media` in `us-east-1`
* SES: `no-reply@townlit.com`
* SNS, Stripe, PayPal keys included
* CORS allowed: `https://www.townlit.com`
* Veriff key set
* Secure cookie settings for production enabled

---

## 5. Dockerfile – `/srv/townlit/Dockerfile`

* Based on: `python:3.11-slim`
* Installs:

  * `ffmpeg` (for video conversion)
  * `netcat`, `curl`, `build-essential`, `libmysqlclient`
* Entrypoints: `entrypoint_backend.sh` and `entrypoint_worker.sh`
* Uses `pip install -r requirements.txt`

---

## 6. Django `settings.py` Summary

* `ASGI_APPLICATION` and `WSGI_APPLICATION` set
* CORS enabled with credentials and allowed origins
* Session and CSRF cookies set to secure
* MySQL database via env config:

  * host: `mysql` (Docker network alias)
* Celery via Redis (`townlit_redis`)
* `STATIC_ROOT`: `BASE_DIR/staticfiles/`
* Media:

  * If `USE_S3=True`: uses Amazon S3
  * Else: `/media/` in local file system
* Channels (WebSocket) via `channels_redis`

---

## 7. Redis Configuration – `/srv/redis/redis.conf`

```ini
bind 0.0.0.0
protected-mode yes
port 6379
requirepass XXXXXX (hint: without start and edn)
```

---

## 8. UFW Firewall Rules

| Rule             | Action | From                 |
| ---------------- | ------ | -------------------- |
| Port 80/443      | ALLOW  | Anywhere             |
| Port 6379        | ALLOW  | 91.99.148.173        |
| Port 3306        | ALLOW  | 91.99.148.173        |
| Port 6379        | DENY   | Anywhere (default)   |
| Port 22 (SSH)    | ALLOW  | 91.99.148.173        |
| Port 22 (SSH)    | DENY   | Anywhere             |
| Port 2222 (SSH)  | ALLOW  | Anywhere             |
| Port 8822 (SSH)  | ALLOW  | Anywhere             |
| IPv6 Ports       | Mixed  | Includes 22, 80, 443, 2222, 8822 (v6) |

* Logging: `on (low)`
* Default policy: `deny (incoming)`, `allow (outgoing)`, `deny (routed)`

---

## 9. Fail2Ban Configuration

| Setting       | Value                                           |
| ------------- | ----------------------------------------------- |
| Enabled Jail  | sshd                                            |
| Ports Monitored | 2222, 8822                                   |
| Backend       | systemd                                         |
| Log Path      | Default (%(sshd_log)s → `/var/log/auth.log`)    |
| Max Retry     | 3 attempts                                      |
| Find Time     | 10 minutes                                     |
| Ban Time      | 1 hour                                         |
| Whitelisted IPs | 127.0.0.1, ::1, 172.218.33.146, 2001:...b7   |
| Currently Banned | 4 IPs (`91.99.148.173`, `45.134.26.79`, ...) |
| Total Failed Attempts | 473                                    |

**Fail2Ban jail configuration (excerpt from `/etc/fail2ban/jail.local`)**:
```ini
[sshd]
enabled = true
port = 2222,8822
filter = sshd
logpath = %(sshd_log)s
backend = systemd
maxretry = 3
findtime = 10m
bantime = 1h
ignoreip = 127.0.0.1 ::1 172.218.33.146 2001:569:5a40:6100:4531:4fe0:798a:45b7
```

---

## 10. Docker Volumes

| Volume Name             | Purpose                                    |
| ----------------------- | ------------------------------------------ |
| `townlit_media_volume`  | Mounted at `/app/media/` in backend/celery |
| `townlit_mysql_data`    | MySQL data storage                         |
| `townlit_static_volume` | Static admin files                         |
| Host static path        | `/srv/townlit/static/`                     |
| Host template path      | `/srv/townlit/templates/`                  |

---

## 11. Logs

* **Nginx error log** path: `/var/log/nginx/error.log`
* Common issues seen:

  * SSL handshake errors from bots or unsupported clients
  * 404 errors for missing static files (`og-image.jpg`)
* **Backend logs**: logged to Docker stdout (`docker logs townlit_backend`)

---

## 12. Healthchecks

* No `healthcheck` defined yet in `docker-compose.yml`
* Recommended to add basic `curl`-based healthchecks for backend and MySQL in future

---

## 13. Deployment

* Command used: `docker-compose up -d`
* All containers are launched with proper resource limits (CPU/RAM)
* Entrypoints used:

  * `entrypoint_backend.sh`: wait for DB → migrate → collectstatic → start Gunicorn (ASGI)
  * `entrypoint_worker.sh`: wait for DB → run Celery or Beat

---

## ✅ Conclusion

This documentation provides a complete, centralized DevOps reference for **Server 01**. It should be stored in:

* GitHub private repo (e.g., `infrastructure/servers/server-01-prod.md`)
* Or in internal tools like Notion, Wiki.js, etc.
* Keep this synced with any future changes to Redis, MySQL, Nginx, volumes, or healthchecks.

---