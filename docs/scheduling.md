# Agendamento (Cron ou systemd)

Este projeto inclui um executor amigável para agendamento em `src/cli/scheduled_run.py`.

Ele executa `src/main.py`, analisa esta linha da saída:

`Total abertura concursos (keywords: abertura, inicio, iniciado): <número>`

Se `<número> >= threshold` (padrão `1`), ele envia uma notificação.

Prioridade de notificação:
1. Email SMTP (`DOU_SMTP_*` + `DOU_NOTIFY_*`)
2. Webhook (`DOU_WEBHOOK_URL`)
3. Notificação desktop (`notify-send`)

---

## 1) Teste manual

Da raiz do projeto:

```bash
python src/cli/scheduled_run.py --days 7 --threshold 1 --save-output logs/weekly_run.log
```

---

## 2) Configuração de email (recomendado)

Exporte estas variáveis no perfil do seu shell ou ambiente do agendador:

```bash
export DOU_SMTP_HOST="smtp.gmail.com"
export DOU_SMTP_PORT="587"
export DOU_SMTP_USER="voce@example.com"
export DOU_SMTP_PASS="sua_senha_de_app"
export DOU_NOTIFY_FROM="voce@example.com"
export DOU_NOTIFY_TO="voce@example.com"
```

Observações:
- Para Gmail, use uma Senha de App (não sua senha de login normal).
- Se as variáveis SMTP estiverem faltando, o script volta para webhook ou notificações desktop.

---

## 3) Tarefa cron semanal (a cada 7 dias)

Edite seu crontab:

```bash
crontab -e
```

Adicione esta linha (executa toda segunda-feira às 08:00):

```cron
0 8 * * 1 cd /home/moonpie/Documents/GitProjects/dou-monitor && /usr/bin/env DOU_SMTP_HOST="smtp.gmail.com" DOU_SMTP_PORT="587" DOU_SMTP_USER="voce@example.com" DOU_SMTP_PASS="sua_senha_de_app" DOU_NOTIFY_FROM="voce@example.com" DOU_NOTIFY_TO="voce@example.com" python src/cli/scheduled_run.py --days 7 --threshold 1 --save-output logs/cron_weekly.log >> logs/cron.log 2>&1
```

Se você usa um virtualenv, substitua `python` pelo interpretador do seu venv (exemplo):

```cron
0 8 * * 1 cd /home/moonpie/Documents/GitProjects/dou-monitor && /home/moonpie/Documents/GitProjects/dou-monitor/.venv/bin/python src/cli/scheduled_run.py --days 7 --threshold 1 --save-output logs/cron_weekly.log >> logs/cron.log 2>&1
```

---

## 4) Timer systemd semanal (recomendado em vez de cron)

Crie o serviço de usuário:

`~/.config/systemd/user/dou-monitor.service`

```ini
[Unit]
Description=Executar monitor DOU semanalmente

[Service]
Type=oneshot
WorkingDirectory=/home/moonpie/Documents/GitProjects/dou-monitor
Environment=DOU_SMTP_HOST=smtp.gmail.com
Environment=DOU_SMTP_PORT=587
Environment=DOU_SMTP_USER=voce@example.com
Environment=DOU_SMTP_PASS=sua_senha_de_app
Environment=DOU_NOTIFY_FROM=voce@example.com
Environment=DOU_NOTIFY_TO=voce@example.com
ExecStart=/home/moonpie/Documents/GitProjects/dou-monitor/.venv/bin/python /home/moonpie/Documents/GitProjects/dou-monitor/src/cli/scheduled_run.py --days 7 --threshold 1 --save-output /home/moonpie/Documents/GitProjects/dou-monitor/logs/systemd_weekly.log
```

Crie o timer:

`~/.config/systemd/user/dou-monitor.timer`

```ini
[Unit]
Description=Executar monitor DOU a cada 7 dias

[Timer]
OnBootSec=10min
OnUnitActiveSec=7d
Persistent=true
Unit=dou-monitor.service

[Install]
WantedBy=timers.target
```

Habilite e inicie:

```bash
systemctl --user daemon-reload
systemctl --user enable --now dou-monitor.timer
systemctl --user list-timers | grep dou-monitor
```

Teste o serviço imediatamente (depuração/teste):

```bash
systemctl --user start dou-monitor.service
systemctl --user status dou-monitor.service
```

Inspecione logs:

```bash
journalctl --user -u dou-monitor.service -n 100 --no-pager
```

---

## 5) Notificações alternativas

- Webhook: defina `DOU_WEBHOOK_URL` (Slack/Discord/endpoint personalizado que aceita texto plano).
- Desktop: instale `notify-send` (pacote `libnotify-bin` no Debian/Ubuntu).
- Serviços existentes (Gotify, ntfy, Pushover, bot do Telegram) podem ser integrados via endpoint webhook.

