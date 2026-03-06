# 🔒 IMPORTANTE: Configuração de Segurança Required

## ⚠️ ANTES DE INICIAR O DASHBOARD

O projeto foi auditado segundo **OWASP Top 10** e recebeu correções críticas de segurança. Para iniciar o dashboard, você **DEVE** configurar as variáveis de ambiente.

### 🚀 Quick Start (3 minutos)

```bash
# 1. Instalar novas dependências
pip install -r requirements.txt

# 2. Criar arquivo .env
cp .env.example .env

# 3. Gerar SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Copie o resultado para .env na linha FLASK_SECRET_KEY=

# 4. Gerar hash de senha
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('SUA_SENHA_AQUI'))"
# Copie o resultado para .env na linha ADMIN_PASS_HASH=

# 5. Iniciar dashboard
python src/web/start_dashboard.py

# 6. Acessar http://localhost:5000 e fazer login
```

### 🔑 Credenciais de Login

#### Desenvolvimento (Modo Simplificado)
Se `FLASK_ENV=development` e você **não** configurou `ADMIN_PASS_HASH`:
- **Usuário:** `admin`
- **Senha:** `admin`

⚠️ **NUNCA use isso em produção!**

#### Produção
Use a senha que você configurou ao gerar o `ADMIN_PASS_HASH`:
- **Usuário:** `admin` (ou o valor definido em `ADMIN_USER`)
- **Senha:** A senha que você usou no passo 4 acima

---

## 📚 Documentação Completa

Documentação detalhada disponível em `docs/security/`:

1. **[security_audit.md](docs/security/security_audit.md)** - Relatório completo da auditoria OWASP Top 10
2. **[security_fixes_summary.md](docs/security/security_fixes_summary.md)** - Resumo das 19 vulnerabilidades corrigidas
3. **[security_setup.md](docs/security/security_setup.md)** - Guia passo a passo de configuração
4. **[aws_deployment_checklist.md](docs/security/aws_deployment_checklist.md)** - Checklist para deploy em AWS
5. **[install_dependencies.md](docs/security/install_dependencies.md)** - Solução de problemas de instalação

---

## ✅ Correções Implementadas

### Vulnerabilidades Críticas Corrigidas (7):
1. ✅ **Autenticação Implementada** - Flask-Login em todas as rotas
2. ✅ **SECRET_KEY Segura** - Movida para variável de ambiente
3. ✅ **CSRF Protection** - Flask-WTF configurado
4. ✅ **Path Traversal Corrigido** - Validação de filename em `serve_edital()`
5. ✅ **SSRF Mitigado** - Validação de webhook URLs (bloqueia IPs privados)
6. ✅ **Security Headers** - X-Frame-Options, CSP, XSS-Protection
7. ✅ **Logging de Segurança** - Auditoria de login, downloads, MIT edits

### Total: 19/19 vulnerabilidades corrigidas (100%)

---

## 🔐 Novos Arquivos

### Código:
- `src/web/auth.py` - Sistema de autenticação
- `src/web/security.py` - Funções de validação (SSRF, path traversal)
- `src/web/templates/login.html` - Página de login

### Configuração:
- `.env.example` - Template de variáveis de ambiente

---

## 🧪 Testar Segurança

Antes de deploy em produção:

```bash
# Verificar vulnerabilidades
pip install bandit pip-audit safety
bandit -r src/
pip-audit
safety check

# Verificar .env não está no Git
git ls-files | grep "\.env$"  # Deve retornar vazio
```

---

## 🆘 Problemas Comuns

### "Import flask_login could not be resolved"
```bash
pip install flask-login==0.6.3 flask-wtf==1.2.1
```

### "Cannot access dashboard"
Verifique se configurou `.env` com SECRET_KEY e ADMIN_PASS_HASH.

### "Login não funciona"
Certifique-se de usar a mesma senha que você passou para `generate_password_hash()`.

---

## 📞 Suporte

Para questões de segurança, consulte a documentação em `docs/` ou revise:
- [OWASP Top 10](https://owasp.org/Top10/)
- [Flask Security Docs](https://flask.palletsprojects.com/security/)

---

**Status:** ✅ Seguro para deploy (após configurar `.env`)  
**Última Auditoria:** 06/03/2026  
**Framework:** OWASP Top 10 (2021)
