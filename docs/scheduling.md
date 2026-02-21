# Scheduling (Cron or systemd)

This project includes a scheduler-friendly runner at `src/cli/scheduled_run.py`.

It runs `src/main.py`, parses this line from output:

`Total abertura concursos (keywords: abertura, inicio, iniciado): <number>`

If `<number> >= threshold` (default `1`), it sends a notification.

Notification priority:
1. SMTP email (`DOU_SMTP_*` + `DOU_NOTIFY_*`)
2. Webhook (`DOU_WEBHOOK_URL`)
3. Desktop notification (`notify-send`)

---

## 1) Manual test

From project root:

```bash
python src/cli/scheduled_run.py --days 7 --threshold 1 --save-output logs/weekly_run.log
```

---

## 2) Email configuration (recommended)

Export these variables in your shell profile or scheduler environment:

```bash
export DOU_SMTP_HOST="smtp.gmail.com"
export DOU_SMTP_PORT="587"
export DOU_SMTP_USER="you@example.com"
export DOU_SMTP_PASS="your_app_password"
export DOU_NOTIFY_FROM="you@example.com"
export DOU_NOTIFY_TO="you@example.com"
```

Notes:
- For Gmail, use an App Password (not your normal login password).
- If SMTP variables are missing, the script falls back to webhook or desktop notifications.

---

## 3) Weekly cron job (every 7 days)

Edit your crontab:

```bash
crontab -e
```

Add this line (runs every Monday at 08:00):

```cron
0 8 * * 1 cd /home/moonpie/Documents/GitProjects/dou-monitor && /usr/bin/env DOU_SMTP_HOST="smtp.gmail.com" DOU_SMTP_PORT="587" DOU_SMTP_USER="you@example.com" DOU_SMTP_PASS="your_app_password" DOU_NOTIFY_FROM="you@example.com" DOU_NOTIFY_TO="you@example.com" python src/cli/scheduled_run.py --days 7 --threshold 1 --save-output logs/cron_weekly.log >> logs/cron.log 2>&1
```

If you use a virtualenv, replace `python` with your venv interpreter (example):

```cron
0 8 * * 1 cd /home/moonpie/Documents/GitProjects/dou-monitor && /home/moonpie/Documents/GitProjects/dou-monitor/.venv/bin/python src/cli/scheduled_run.py --days 7 --threshold 1 --save-output logs/cron_weekly.log >> logs/cron.log 2>&1
```

---

## 4) Weekly systemd timer (recommended over cron)

Create user service:

`~/.config/systemd/user/dou-monitor.service`

```ini
[Unit]
Description=Run DOU monitor weekly

[Service]
Type=oneshot
WorkingDirectory=/home/moonpie/Documents/GitProjects/dou-monitor
Environment=DOU_SMTP_HOST=smtp.gmail.com
Environment=DOU_SMTP_PORT=587
Environment=DOU_SMTP_USER=you@example.com
Environment=DOU_SMTP_PASS=your_app_password
Environment=DOU_NOTIFY_FROM=you@example.com
Environment=DOU_NOTIFY_TO=you@example.com
ExecStart=/home/moonpie/Documents/GitProjects/dou-monitor/.venv/bin/python /home/moonpie/Documents/GitProjects/dou-monitor/src/cli/scheduled_run.py --days 7 --threshold 1 --save-output /home/moonpie/Documents/GitProjects/dou-monitor/logs/systemd_weekly.log
```

Create timer:

`~/.config/systemd/user/dou-monitor.timer`

```ini
[Unit]
Description=Run DOU monitor every 7 days

[Timer]
OnBootSec=10min
OnUnitActiveSec=7d
Persistent=true
Unit=dou-monitor.service

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now dou-monitor.timer
systemctl --user list-timers | grep dou-monitor
```

Test the service immediately (debugging/testing):

```bash
systemctl --user start dou-monitor.service
systemctl --user status dou-monitor.service
```

Inspect logs:

```bash
journalctl --user -u dou-monitor.service -n 100 --no-pager
```

---

## 5) Alternative notifications

- Webhook: set `DOU_WEBHOOK_URL` (Slack/Discord/custom endpoint that accepts plain text).
- Desktop: install `notify-send` (package `libnotify-bin` on Debian/Ubuntu).
- Existing services (Gotify, ntfy, Pushover, Telegram bot) can be integrated via webhook endpoint.
