# 🎥 Server 02 – Video Worker: `townlit-video-worker`

## 1. General Info

| Key              | Value                                     |
| ---------------- | ----------------------------------------- |
| Hostname         | townlit-video-worker                      |
| Public IP        | 91.99.148.173                             |
| OS               | Ubuntu 22.04 LTS                          |
| Docker Version   | 24.x                                      |
| Docker Compose   | 2.x (custom: `docker-compose.worker.yml`) |
| Main Role        | Celery video worker only                  |
| Environment File | `/srv/townlit/.env.production`            |
| Code Path        | `/srv/townlit/`                           |

---

## 2. Running Services (via Docker)

| Service      | Container Name | Exposed Ports | Notes                         |
| ------------ | -------------- | ------------- | ----------------------------- |
| Video Worker | `video_worker` | —             | Celery worker for video queue |

* Docker Compose file: `docker-compose.worker.yml`
* Entrypoint: `/entrypoint_worker.sh`

---

## 3. SSH Access

```bash
ssh -i ~/.ssh/townlit_video_worker_2025 root@91.99.148.173
ssh -p 2222 adminuser@91.99.148.173
ssh -p 8822 adminuser@91.99.148.173
```

---

## 4. ENV File – `.env.production`

* MySQL host: `127.0.0.1` with port `3307` (via SSH tunnel)
* Redis URL: `redis://:PASSWORD@127.0.0.1:6379/0` (via SSH tunnel)
* S3 enabled: `USE_S3=True`
* AWS region: `us-east-1`
* Secret, FERNET, Master keys present

---

## 5. Entrypoint – `/entrypoint_worker.sh`

This script:

* Creates SSH tunnel to Redis on server-01 (`91.99.114.147:6379` → `127.0.0.1:6379`)
* Creates SSH tunnel to MySQL on server-01 (`91.99.114.147:3306` → `127.0.0.1:3307`)
* Waits for MySQL to be accessible
* Launches Celery with provided command

SSH tunnel port on server-01: **2222**

---

## 6. Dockerfile

* Base: `python:3.11-slim`
* Packages:

  * `ffmpeg`, `mysql-client`, `redis-tools`, `openssh-client`, `curl`
  * Build tools: `build-essential`, `pkg-config`, `libmysqlclient`
* Copies and uses both `entrypoint_worker.sh` and `entrypoint_backend.sh`
* Entrypoint: `entrypoint_worker.sh` used exclusively

---

## 7. UFW Firewall Rules

| Rule             | Action | From          |
| ---------------- | ------ | ------------- |
| Default Incoming | DENY   | —             |
| Default Outgoing | ALLOW  | —             |
| Port 2222 (SSH)  | ALLOW  | 91.99.114.147 |
| Port 8822 (SSH)  | ALLOW  | Anywhere      |

* UFW reset, configured with:

  ```bash
  sudo ufw --force reset
  sudo ufw default deny incoming
  sudo ufw default allow outgoing
  sudo ufw allow from <IP_HOME> to any port 2222 proto tcp
  sudo ufw allow from <IP_MOBILE> to any port 2222 proto tcp
  sudo ufw allow 8822/tcp
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw enable
  sudo ufw status verbose
  ```
* Replace `<IP_HOME>` and `<IP_MOBILE>` with your trusted IPs.
* Ensures primary SSH is limited, with a backup port open.

---

## 8. Fail2Ban Configuration

Fail2Ban monitors and bans malicious SSH attempts.

### Installation & Activation:

```bash
sudo apt update
sudo apt install fail2ban -y
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
```

### jail.local Configuration (`/etc/fail2ban/jail.local`):

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
ignoreip = 127.0.0.1 <IP_HOME> <IP_MOBILE>
```

* `ignoreip` prevents banning home and mobile IP addresses.

### Activation:

```bash
sudo systemctl restart fail2ban
sudo systemctl enable fail2ban
sudo fail2ban-client status sshd
```

### Logs:

* Authentication log: `/var/log/auth.log`
* Fail2Ban status: `sudo fail2ban-client status sshd`

---

## 9. File Tree (`/srv/townlit/`)

Includes core application and these relevant files:

```
entrypoint_worker.sh
Dockerfile
.env.production
docker-compose.worker.yml
requirements.txt
apps/, utils/, services/, templates/, static/
```

No need for `entrypoint_backend.sh` or `docker-compose.yml` on this server.

---

## ✅ Conclusion

This documentation outlines all critical configurations for **Server 02** (`townlit-video-worker`), responsible only for video Celery processing via secure tunnels to `Server 01`.

Ensure this file is stored in:

* Git private repo: `infrastructure/servers/server-02-video-worker.md`
* Or internal Wiki/Docs (e.g., Wiki.js)

Keep in sync with future changes to tunnel setup, security rules, or container structure.

---

### 🔍 Log Reference:

* `/var/log/auth.log` — connection and authentication attempts
