# 🔒 Guia de Segurança - DOU Monitor

Este guia fornece instruções passo a passo para configurar segurança antes de fazer deploy em produção.

## 📋 Pré-Requisitos

Antes de iniciar o dashboard, você DEVE configurar as variáveis de ambiente.

## 🔧 Configuração Inicial

### 1. Criar Arquivo .env

Copie o arquivo `.env.example` para `.env`:

```bash
cp .env.example .env
```

### 2. Gerar SECRET_KEY

Execute no terminal Python:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copie o resultado e cole em `.env`:

```env
FLASK_SECRET_KEY=<cole_o_token_aqui>
```

### 3. Gerar Hash de Senha

Execute no terminal Python (substitua `SUA_SENHA_AQUI`):

```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('SUA_SENHA_AQUI'))"
```

Cole o hash em `.env`:

```env
ADMIN_USER=admin
ADMIN_PASS_HASH=pbkdf2:sha256:...<cole_o_hash_aqui>
```

### 4. Configurar Email (Opcional)

Para notificações por email, configure:

```env
DOU_EMAIL_FROM=seu_email@gmail.com
DOU_EMAIL_TO=destinatario@example.com
DOU_EMAIL_PASSWORD=<senha_de_app_do_gmail>
DOU_EMAIL_SMTP_SERVER=smtp.gmail.com
DOU_EMAIL_SMTP_PORT=587
```

**⚠️ Gmail:** Use [senha de app](https://support.google.com/accounts/answer/185833) em vez da senha normal.

### 5. Configurar Webhook (Opcional)

Para notificações via webhook (Discord, Slack, etc):

```env
DOU_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

**🔒 Segurança:** Somente URLs HTTPS são permitidas.

## 🚀 Iniciar Dashboard

### Desenvolvimento (Ambiente Local)

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar para desenvolvimento (opcional: permite login admin/admin sem hash)
export FLASK_ENV=development  # Linux/Mac
set FLASK_ENV=development     # Windows CMD
$env:FLASK_ENV="development"  # Windows PowerShell

# Iniciar dashboard
python src/web/start_dashboard.py
```

Acesse: http://localhost:5000

### Produção (AWS/Cloud)

```bash
# Instalar dependências
pip install -r requirements.txt

# ⚠️ NUNCA USAR debug=True EM PRODUÇÃO

# Configurar variáveis de ambiente no servidor:
export FLASK_ENV=production
export FLASK_SECRET_KEY=<seu_token_gerado>
export ADMIN_USER=admin
export ADMIN_PASS_HASH=<seu_hash_gerado>

# Usar servidor WSGI (ex: Gunicorn)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "src.web.app:create_app()"
```

## 🔐 Credenciais de Login

### Desenvolvimento

Se `FLASK_ENV=development` e `ADMIN_PASS_HASH` não estiver configurado:

- **Usuário:** `admin`
- **Senha:** `admin`

⚠️ **NUNCA use isso em produção!**

### Produção

Use o usuário/senha que você configurou no `.env`:

- **Usuário:** Valor de `ADMIN_USER` (padrão: `admin`)
- **Senha:** A senha que você usou para gerar `ADMIN_PASS_HASH`

## 🧪 Testar Segurança

Execute testes de segurança antes de deploy:

```bash
# Instalar ferramentas de auditoria
pip install bandit pip-audit safety

# Scan de vulnerabilidades no código
bandit -r src/

# Scan de dependências vulneráveis
pip-audit

# Scan de CVEs conhecidos
safety check
```

## ☁️ Deploy AWS - Checklist

Antes de fazer deploy em AWS EC2/ECS:

- [ ] **Variáveis de ambiente configuradas** (SECRET_KEY, senha, etc)
- [ ] **FLASK_ENV=production** definido
- [ ] **Debug mode desabilitado** (nunca usar `debug=True`)
- [ ] **HTTPS habilitado** (use ALB com certificado SSL)
- [ ] **Security Groups configurados** (somente porta 443 pública)
- [ ] **IAM roles configurados** (permissões mínimas necessárias)
- [ ] **Backups automáticos** (configurar snapshots EBS ou S3)
- [ ] **Monitoring configurado** (CloudWatch Logs + Alarms)
- [ ] **Rate limiting** (use AWS WAF ou CloudFlare)
- [ ] **.env não commitado** (verificar histórico Git)

### Exemplo: Configuração AWS EC2

```bash
# 1. Instalar Python + dependências
sudo apt update
sudo apt install python3 python3-pip python3-venv

# 2. Clonar projeto
git clone <seu_repo> /opt/dou-monitor
cd /opt/dou-monitor

# 3. Criar .env (NUNCA commitar .env!)
nano .env
# ... colar configurações...

# 4. Instalar dependências
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 5. Instalar navegador Playwright
playwright install chromium
playwright install-deps

# 6. Configurar systemd service
sudo nano /etc/systemd/system/dou-monitor.service
```

**dou-monitor.service:**
```ini
[Unit]
Description=DOU Monitor Dashboard
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/dou-monitor
Environment="PATH=/opt/dou-monitor/.venv/bin"
EnvironmentFile=/opt/dou-monitor/.env
ExecStart=/opt/dou-monitor/.venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 "src.web.app:create_app()"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 7. Iniciar serviço
sudo systemctl daemon-reload
sudo systemctl enable dou-monitor
sudo systemctl start dou-monitor
sudo systemctl status dou-monitor

# 8. Configurar Nginx reverse proxy (HTTPS)
sudo apt install nginx certbot python3-certbot-nginx
sudo nano /etc/nginx/sites-available/dou-monitor

# ... configurar Nginx com SSL ...
# ... obter certificado Let's Encrypt com certbot ...

sudo systemctl restart nginx
```

## 🛡️ Hardening Adicional

### Firewall (UFW)

```bash
# Permitir somente SSH e HTTPS
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### Fail2Ban (Proteção contra brute force)

```bash
sudo apt install fail2ban
sudo nano /etc/fail2ban/jail.local
```

**jail.local:**
```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
```

## 📊 Monitoring e Logs

### Ver logs de segurança:

```bash
# Logs do dashboard
tail -f logs/security.log

# Logs do sistema
sudo journalctl -u dou-monitor -f

# Logs de autenticação
sudo tail -f /var/log/auth.log
```

### Alertas de Segurança

Configure CloudWatch Alarms para:

- Login failures (mais de 5 em 5 minutos)
- Path traversal attempts
- SSRF attempts
- Unusual download patterns

## 🔄 Manutenção de Segurança

Execute regularmente:

```bash
# Atualizar dependências
pip install --upgrade pip
pip install --upgrade -r requirements.txt

# Verificar vulnerabilidades
pip-audit

# Atualizar sistema operacional
sudo apt update && sudo apt upgrade -y

# Rotacionar logs
sudo logrotate -f /etc/logrotate.conf

# Backup de dados
tar -czf backup-$(date +%Y%m%d).tar.gz data/ .env
```

## 📚 Referências

- [Flask Security Best Practices](https://flask.palletsprojects.com/en/3.0.x/security/)
- [OWASP Top 10](https://owasp.org/Top10/)
- [AWS Security Best Practices](https://aws.amazon.com/security/security-learning/)
- [Let's Encrypt](https://letsencrypt.org/)

## 🆘 Suporte

Para reportar vulnerabilidades de segurança, **NÃO abra uma issue pública**. Entre em contato diretamente com os mantenedores.
