# Sistema de URLs Configuráveis do DOU

## 📋 Visão Geral

O DOU Monitor agora possui um sistema robusto de gerenciamento de URLs que permite atualizar os endereços do DOU sem modificar código, preparando a ferramenta para mudanças futuras no formato de URLs do Diário Oficial da União.

## 🎯 Problema Resolvido

**Antes**: URLs do DOU estavam hardcoded em 4 locais diferentes do código. Se o DOU mudasse o formato das URLs, a ferramenta quebraria completamente.

**Agora**: URLs centralizadas em configuração JSON editável via dashboard ou CLI, com:
- Monitoramento de saúde (detecta falhas consecutivas)
- Alertas automáticos quando algo dá errado
- Interface admin para atualização
- Fallback para configuração padrão

## 📁 Arquitetura

### Arquivo de Configuração
**Localização**: `data/dou_config.json`

```json
{
  "base_url": "https://www.in.gov.br",
  "search_url": "https://www.in.gov.br/consulta/-/buscar/dou",
  "document_url_pattern": "https://www.in.gov.br/web/dou/-/{url_title}",
  "health": {
    "last_successful_download": "2026-03-07T10:30:15",
    "last_failed_download": null,
    "consecutive_failures": 0,
    "alert_threshold": 3
  }
}
```

### Módulo Python
**Localização**: `src/config/dou_urls.py`

**Classe principal**: `DOUUrlConfig`
- Singleton pattern (uma instância global)
- Carrega configuração do JSON
- Fornece métodos para construir URLs
- Monitora saúde dos downloads
- Registra sucessos/falhas

## 🔧 Como Usar

### 1. Via Dashboard (Recomendado)

**Acesso**: Dashboard → Configurações Avançadas → "Configuração de URLs do DOU"

**Campos**:
```
URL de Busca: https://www.in.gov.br/consulta/-/buscar/dou
Padrão de URL de Documentos: https://www.in.gov.br/web/dou/-/{url_title}
URL Base (Fallback): https://www.in.gov.br
```

**Importante**: O campo "Padrão de URL de Documentos" **deve conter** o placeholder `{url_title}`.

**Quando atualizar**:
- ⚠️ Alerta vermelho aparece após 3 falhas consecutivas
- Downloads de PDFs começam a falhar sistematicamente
- DOU anuncia mudança no formato de URLs

### 2. Via CLI

**Comando completo**:
```bash
python src/main.py --update-dou-urls \
  --base-url "https://www.in.gov.br" \
  --search-url "https://www.in.gov.br/consulta/-/buscar/dou" \
  --document-url-pattern "https://www.in.gov.br/web/dou/-/{url_title}"
```

**Atualizar apenas uma URL**:
```bash
# Apenas document URL pattern
python src/main.py --update-dou-urls \
  --document-url-pattern "https://novo-formato.in.gov.br/dou/{url_title}"

# Apenas search URL
python src/main.py --update-dou-urls \
  --search-url "https://www.in.gov.br/nova-busca/-/dou"
```

**Flags disponíveis**:
- `--update-dou-urls`: Ativa modo de atualização
- `--base-url URL`: Nova URL base
- `--search-url URL`: Nova URL de busca
- `--document-url-pattern PATTERN`: Novo padrão (com `{url_title}`)

## 🏥 Sistema de Monitoramento de Saúde

### Como Funciona

1. **Registro de Sucessos**: Cada download bem-sucedido de PDF reseta o contador de falhas
2. **Registro de Falhas**: Cada falha incrementa o contador
3. **Alerta Automático**: Após 3 falhas (configurável), exibe alerta no dashboard e nos logs

### Status de Saúde

**Campos monitorados**:
```json
{
  "last_successful_download": "2026-03-07T10:30:15",  // Último sucesso ISO timestamp
  "last_failed_download": "2026-03-07T12:45:00",      // Última falha ISO timestamp
  "consecutive_failures": 2,                          // Contador de falhas seguidas
  "alert_threshold": 3                                // Limite para alerta
}
```

**Indicadores no Dashboard**:
- 🟢 **0 falhas**: Sistema funcionando normalmente
- 🟡 **1-2 falhas**: Atenção, pode ser problema temporário
- 🔴 **3+ falhas**: ALERTA! URL provavelmente mudou

### Reset do Contador

O contador de falhas **reseta automaticamente** quando:
- Um download de PDF é bem-sucedido
- Admin atualiza as URLs manualmente (via dashboard ou CLI)

## 🛠️ Integração no Código

### Uso nos Módulos

**Antes (hardcoded)**:
```python
url = f"https://www.in.gov.br/web/dou/-/{url_title}"
```

**Depois (configurável)**:
```python
from src.config.dou_urls import get_dou_config

dou_config = get_dou_config()
url = dou_config.get_document_url(url_title)
```

### Métodos Disponíveis

```python
from src.config.dou_urls import get_dou_config

config = get_dou_config()

# Obter URLs
base_url = config.get_base_url()                    # "https://www.in.gov.br"
search_url = config.get_search_url()                # URL de busca
doc_url = config.get_document_url("edital-123")     # Constrói URL completa

# Monitoramento
config.record_success()                             # Registra sucesso
alert = config.record_failure()                     # Registra falha (retorna True se atingiu threshold)
health = config.get_health_status()                 # Dict com status

# Atualização (admin)
success, msg = config.update_urls(
    base_url="https://novo.in.gov.br",
    document_url_pattern="https://novo.in.gov.br/dou/{url_title}",
    updated_by="admin"
)
```

### Locais Atualizados

1. **`src/extraction/scraper.py`**: Busca de concursos
2. **`src/web/dashboard_service.py`**: Carregamento de summaries
3. **`src/web/app.py`**: Download on-demand de PDFs

## 📊 Logs

### Eventos Registrados

**Sucesso**:
```
[INFO] DOU config loaded from data/dou_config.json
[INFO] PDF served: dou-123456789 user=admin
```

**Falha**:
```
[ERROR] PDF download failed: Failed to download PDF from DOU
[CRITICAL] ⚠️ ALERT: 3 consecutive DOU download failures! URL pattern may have changed.
```

**Atualização**:
```
[INFO] DOU URLs update requested: user=admin ip=192.168.1.100
[INFO] DOU URLs updated successfully by user=admin
```

## 🔐 Segurança

- ✅ Atualização requer autenticação (apenas usuários logados)
- ✅ Validação de padrão `{url_title}` obrigatório
- ✅ Logs de todas as atualizações (user + IP)
- ✅ Arquivo de configuração em `.gitignore` (não commitado)
- ✅ Fallback para configuração hardcoded se JSON falhar

## 🚨 Cenários de Falha

### Cenário 1: JSON Corrompido
**Sintoma**: Aplicação não inicia ou erro ao carregar config  
**Solução**: Arquivo é recriado automaticamente com valores padrão

### Cenário 2: URL do DOU mudou
**Sintoma**: Alerta vermelho no dashboard após 3 falhas  
**Solução**: Admin atualiza URLs via dashboard ou CLI

### Cenário 3: Placeholder incorreto
**Sintoma**: Erro ao salvar: "document_url_pattern deve conter placeholder {url_title}"  
**Solução**: Corrigir padrão incluindo `{url_title}`

## 📝 Exemplo Completo de Migração

**Situação**: DOU mudou de `https://www.in.gov.br/web/dou/-/{url_title}` para `https://dou.gov.br/documentos/{url_title}`

### Via Dashboard
1. Acesse "Configurações Avançadas"
2. Role até "Configuração de URLs do DOU"
3. Atualize os campos:
   - URL Base: `https://dou.gov.br`
   - Padrão de URL: `https://dou.gov.br/documentos/{url_title}`
   - Search URL: `https://dou.gov.br/busca/concursos`
4. Clique "Atualizar URLs do DOU"
5. ✅ Confirmação: contador de falhas resetado

### Via CLI
```bash
python src/main.py --update-dou-urls \
  --base-url "https://dou.gov.br" \
  --search-url "https://dou.gov.br/busca/concursos" \
  --document-url-pattern "https://dou.gov.br/documentos/{url_title}"
```

## 🎓 Boas Práticas

1. **Teste primeiro**: Baixar um PDF após atualizar URLs
2. **Backup**: Anotar URLs antigas antes de mudar
3. **Monitoramento**: Verificar dashboard após mudanças no DOU
4. **Documentação**: Registrar mudanças em changelog

## 🔮 Roadmap Futuro

Melhorias planejadas:
- [ ] Histórico de mudanças de URLs
- [ ] Validação automática de URLs (health check endpoint)
- [ ] Notificações por email quando threshold atingido
- [ ] Suporte a múltiplos padrões de URL (A/B testing)
- [ ] API endpoint para consultar status de saúde

---

**Última atualização**: 2026-03-07  
**Versão**: 1.0.0
