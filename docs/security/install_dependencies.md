# 📦 Como Instalar Dependências de Segurança

As correções de segurança implementadas requerem novos pacotes Python. Siga os passos abaixo:

## 🔧 Instalação

```bash
# Ativar ambiente virtual
.venv\Scripts\activate  # Windows
# ou
source .venv/bin/activate  # Linux/Mac

# Instalar TODAS as dependências (incluindo novas)
pip install -r requirements.txt

# Instalar navegador para Playwright (se ainda não instalou)
playwright install chromium
playwright install-deps  # Linux apenas
```

## 📋 Novos Pacotes Adicionados

1. **flask-login==0.6.3**
   - Gerenciamento de autenticação e sessões
   - Decorador `@login_required`
   - Funções `login_user()`, `logout_user()`

2. **flask-wtf==1.2.1**
   - Proteção CSRF (Cross-Site Request Forgery)
   - Validação de formulários
   - Geração automática de tokens CSRF

## ✅ Verificar Instalação

```bash
# Verificar se pacotes foram instalados
pip list | grep -E "flask-login|flask-wtf"

# Ou no Windows PowerShell:
pip list | Select-String -Pattern "flask-login|flask-wtf"

# Testar imports
python -c "from flask_login import LoginManager; from flask_wtf.csrf import CSRFProtect; print('✅ Imports OK')"
```

## 🚨 Erros Comuns

### Erro: "Import flask_login could not be resolved"

**Causa:** Dependências não instaladas.

**Solução:**
```bash
pip install flask-login==0.6.3 flask-wtf==1.2.1
```

### Erro: "No module named 'flask_wtf'"

**Causa:** requirements.txt antigo.

**Solução:**
```bash
# Forçar reinstalação
pip install --upgrade --force-reinstall -r requirements.txt
```

### Erro: "ImportError: cryptography"

**Causa:** Dependência indireta faltando.

**Solução:**
```bash
pip install cryptography
```

## 🔄 Reinstalar Tudo (Reset Completo)

Se tiver problemas, delete e recrie o ambiente virtual:

```bash
# Windows
deactivate
rmdir /s .venv
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

# Linux/Mac
deactivate
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
playwright install-deps
```

## 📝 Próximos Passos

Após instalar as dependências:

1. Configure o `.env` (veja [SECURITY_SETUP.md](SECURITY_SETUP.md))
2. Gere SECRET_KEY e hash de senha
3. Inicie o dashboard: `python src/web/start_dashboard.py`
4. Acesse http://localhost:5000 e faça login

## 📚 Documentação

- [Flask-Login Docs](https://flask-login.readthedocs.io/)
- [Flask-WTF Docs](https://flask-wtf.readthedocs.io/)
