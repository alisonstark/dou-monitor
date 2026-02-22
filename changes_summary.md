# Resumo de Mudanças

## Data: 21 de fevereiro de 2026

### 1. Sistema de Agendamento Automático e Notificações

**Novidade:** Implementado sistema completo de execução agendada com notificações.

**Componentes adicionados:**
- `src/cli/scheduled_run.py`: Runner dedicado que executa `main.py`, analisa a contagem de concursos de abertura e envia notificações quando o threshold é atingido
- `docs/scheduling.md`: Documentação completa em português sobre configuração de cron e systemd

**Funcionalidades:**
- Execução automática via cron (agendamento baseado em tempo) ou systemd timer (recomendado)
- Suporte a múltiplos canais de notificação com prioridade:
  1. Email SMTP (configurável via variáveis de ambiente)
  2. Webhook (Slack, Discord, endpoints personalizados)
  3. Notificações desktop via `notify-send`
- Threshold configurável (padrão: notificar quando ≥ 1 concurso de abertura é encontrado)
- Janela de busca personalizável via flag `--days`
- Salva logs opcionais para auditoria e debugging

**Casos de uso:**
- Monitoramento semanal automático do DOU
- Alertas por email quando novos editais de abertura são publicados
- Integração com ferramentas de produtividade (Slack, Discord, etc.)

**Arquivos modificados/adicionados:**
- Novo: `src/cli/scheduled_run.py`
- Novo: `docs/scheduling.md` (traduzido para português)
- Atualizado: `README.md` (adicionada seção de agendamento)
- Atualizado: `docs/debugger_walkthrough.md` (traduzido para português)
- Atualizado: `changes_summary.md` (traduzido para português)

---

## Data: 20 de fevereiro de 2026

### 1. Reestruturação do Projeto - Separação Melhorada de Responsabilidades

**Problema:** Todos os módulos no diretório `src/` plano dificultavam entender responsabilidades.

**Solução:** Reorganizado em pacotes focados:
\`\`\`
src/
├── extraction/        # Scraping de PDF, parsing, extração de datas
├── processing/        # Aplicação de revisões, atualização de whitelists
├── export/           # Geração de saídas (PDFs, JSON)
└── cli/              # Interfaces de linha de comando
\`\`\`

**Benefícios:**
- Separação clara de responsabilidades
- Mais fácil encontrar e modificar funcionalidades relacionadas
- Melhor testabilidade (cada pacote independentemente)
- Mais escalável para recursos futuros

**Arquivos Reorganizados:**
- `extraction/`: scraper.py, extractor.py, cronograma_parser.py
- `processing/`: apply_review.py, update_whitelist.py
- `export/`: pdf_export.py
- `cli/`: review_cli.py

**Todos os imports atualizados:** main.py e todas as importações entre módulos verificadas funcionando

### 2. Atualizações de Documentação

- Atualizado README.md com informações sobre capacidades multi-formato
- Adicionado diagrama de arquitetura do projeto mostrando nova estrutura de pacotes
- Documentadas estratégias de extração dupla na seção do parser de cronograma

---

## Data: 19 de fevereiro de 2026 (Resumo da Sessão Anterior)

### Adições Principais

1. **Pipeline de Extração PDF → JSON** (`src/extraction/extractor.py`)
   - Extração de campos estruturados: metadata, cronograma, vagas, financeiro
   - Usa pdfplumber para parsing de PDF
   - Extração baseada em heurísticas com normalização de fallback

2. **Sistema de Revisão Humana no Circuito**
   - `src/cli/review_cli.py`: Gera CSVs de revisão com pontuações de confiança
   - `src/processing/apply_review.py`: Aplica correções de volta aos resumos JSON com backups

3. **Sistema de Whitelist Auto-Melhorador** (`src/processing/update_whitelist.py`)
   - Aprende com correções manuais
   - Uso em dois estágios: validação (normalizar) + extração de fallback (melhorar)
   - Mantém whitelists separadas para bancas e cargos

4. **Parser de Cronograma em Produção** (`src/extraction/cronograma_parser.py`)
   - Otimização de extração baseada em seções
   - Extração semântica de datas com normalização de texto
   - Gerencia vários formatos de PDF e layouts de tabela

---

## Data: 18 de fevereiro de 2026 (Sessão Inicial)

### Problemas Corrigidos

1. **Erro de Conexão:** Adicionados cabeçalhos de navegador realistas para evitar detecção de bots
2. **Parsing de Resultados de Busca:** Mudado de parsing de links HTML para parsing de JSON embutido
3. **Qualidade de PDF:** Substituída geração manual de PDF por impressão baseada em Playwright

### Recursos Iniciais

- Scraping do DOU com lógica de retry e tratamento de timeout
- Filtragem por palavras-chave (abertura, inicio, iniciado)
- Modo visualização e exportação de PDF via Playwright
- Saída organizada com separadores claros

