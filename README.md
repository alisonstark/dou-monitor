# DOU-monitor

## Objetivo
Monitorar publicações do DOU (Diário Oficial da União) para resultados relacionados a concursos, com visualização rápida e exportação opcional de PDF.

## Capacidades
- Raspa resultados de busca do DOU usando dados JSON embutidos
- Gerencia retentativas de conexão e timeouts
- Filtra resultados por palavras-chave (abertura, inicio, iniciado) com correspondência case-insensitive
- Modo visualização imprime títulos de concursos com saída organizada
- Exportação de PDF usa layout de impressão do site para saída de alta fidelidade
- **Extração automática PDF → JSON** com parsing de campos estruturados:
  - Metadata (órgão, edital número, cargo, banca)
  - Vagas (total, PCD, PPIQ)
  - Financeiro (taxa, remuneração)
  - **Cronograma (inscrição, isenção, data prova)** - extração semântica de nível de produção
    - **Suporte multi-formato:** gerencia vários layouts de tabela (etapas do processo, cronograma, eventos básicos)
    - **Estratégia dupla de extração:** baseada em palavras-chave + análise de contexto retrospectivo
    - **Suporta múltiplos formatos de edital:** Banco do Brasil, INSS, Caixa, Petrobras, entre outros
- **Fluxo de trabalho de revisão humana no circuito** com geração de CSV e aplicação de correções
- **Sistema de extração auto-melhorador:**
  - Correções manuais atualizam automaticamente whitelists
  - Extrações futuras se beneficiam de correções passadas
  - Reduz progressivamente a necessidade de intervenção manual
- Correspondência de whitelist completamente case-insensitive
- Otimização baseada em seções para extração de cronograma mais rápida
- **Execução automática agendada:**
  - Runner dedicado para agendamento via cron ou systemd
  - Notificações por email (SMTP), webhook ou desktop quando novos concursos são detectados
  - Configuração personalizável de threshold e intervalo de busca
  - Veja [docs/scheduling.md](docs/scheduling.md) para guia completo de configuração

## Como Executar

**Pré-requisitos:** Instale dependências e navegadores Playwright (veja seção Instalação abaixo)

Execute o script principal da raiz do projeto:

\`\`\`bash
python src/main.py            # modo visualização (mostra todos os concursos encontrados + correspondências de abertura)
python src/main.py -d 14      # visualizar últimos 14 dias
python src/main.py -d 30 --export-pdf  # exportar PDFs e extrair JSON dos últimos 30 dias
\`\`\`

### Opções de CLI
- `--export-pdf`: Salvar PDFs de qualidade de impressão e extrair resumos JSON (requer Playwright)
- `--days` / `-d`: Janela de retrospectiva em dias (padrão: 7)

### Saída
O scraper exibe:
- Intervalo de datas sendo pesquisado
- **Todos os concursos encontrados** (lista numerada com títulos)
- Concursos de abertura correspondendo às palavras-chave (abertura, inicio, iniciado)
- Resultados de processamento para cada edital

Ferramentas adicionais e fluxo de trabalho

### Pipeline de Extração (PDF → JSON)

Após exportar PDFs, o projeto extrai automaticamente resumos estruturados. O extrator salva resumos em `data/summaries/`.

**A extração inclui:**
- Metadata: órgão, edital número, cargo, banca
- Vagas: total, PCD, PPQ/PPIQ
- Financeiro: taxa de inscrição, remuneração
- **Cronograma: inscrição início/fim, isenção início, data da prova**

O parser de cronograma usa extração semântica de datas com normalização de texto para lidar com vários formatos de PDF e layouts de tabela. Funciona em dois estágios:
1. Tenta encontrar e extrair da seção CRONOGRAMA (mais rápido, mais preciso)
2. Volta para varredura completa do PDF se a detecção de seção falhar (mais robusto)

**Suporte multi-formato com extração baseada em confiança:**
- Usa detecção baseada em palavras-chave (procura "inscrição", "isenção", "prova") com varredura para frente de datas
- Volta para análise de contexto retrospectivo para robustez
- Classifica eventos extraídos por alta confiança (palavra-chave aparece no contexto) vs baixa confiança (correspondência retrospectiva genérica)
- Gerencia múltiplos formatos de tabela comuns em diferentes agências governamentais

### Fluxo de Trabalho de Revisão (Aprendizado Humano no Circuito)

**1. Gerar CSV de revisão:**

\`\`\`bash
python src/review_cli.py --summaries-dir data/summaries
\`\`\`

Isso grava `data/review_<timestamp>.csv` listando cada resumo com pontuações de confiança e problemas sinalizados.

**2. Aplicar correções revisadas:**

Após editar o CSV, aplique correções de volta aos resumos JSON (dry-run por padrão):

\`\`\`bash
python src/apply_review.py --csv data/review_YYYYMMDDTHHMMSSZ.csv
\`\`\`

Para realmente gravar mudanças e criar backups, use `--apply` e defina o nome do revisor:

\`\`\`bash
python src/apply_review.py --csv data/review_YYYYMMDDTHHMMSSZ.csv --apply --reviewer "SeuNome"
\`\`\`

Isso cria:
- Arquivos JSON atualizados em `data/summaries/`
- Backups em `data/backups/`
- **Exemplos revisados em `data/reviewed_examples/`** (para treinamento da whitelist)

**3. Atualizar whitelists (Loop de Aprendizado):**

Após aplicar correções, atualize as whitelists de extração para melhorar execuções futuras:

\`\`\`bash
python src/update_whitelist.py --threshold 1 --apply
\`\`\`

Isso:
- Analisa todos os exemplos revisados em `data/reviewed_examples/`
- Encontra valores de cargo/banca aparecendo ≥ threshold vezes
- Adiciona-os a `data/cargos_whitelist.json` e `data/bancas_whitelist.json`

**Como a whitelist melhora a extração:**

**Estágio 1 - Validação/Normalização:**
- Se cargo/banca extraído via regex → valida contra whitelist → normaliza para forma canônica

**Estágio 2 - Extração de Fallback:**
- Se NENHUM cargo/banca encontrado por padrões primários → busca PDF por itens da whitelist
- **Isso significa que correções hoje melhoram a extração amanhã automaticamente**

O sistema é **auto-melhorador**: correções manuais reduzem progressivamente a necessidade de intervenção manual futura. A correspondência de whitelist é totalmente case-insensitive e funciona com qualquer variação ("PROFESSOR", "Professor", "professor").

**Visualizar adições propostas sem aplicar:**

\`\`\`bash
python src/update_whitelist.py --threshold 1
\`\`\`

### Arquitetura do Projeto

O código é organizado em pacotes focados para melhor manutenibilidade e separação de responsabilidades:

\`\`\`
src/
├── main.py                     # Ponto de entrada da aplicação e orquestração
├── extraction/                 # Pipeline de extração de PDF
│   ├── scraper.py             # Scraping web do DOU
│   ├── extractor.py           # Extração de metadata de PDF
│   └── cronograma_parser.py   # Extração de datas/cronograma
├── processing/                # Processamento e refinamento de dados
│   ├── apply_review.py        # Aplicar correções manuais do CSV
│   └── update_whitelist.py    # Aprender de correções para atualizar whitelists
├── export/                    # Geração de saídas
│   └── pdf_export.py          # Exportação de PDF com Playwright
└── cli/                       # Interfaces voltadas ao usuário
    ├── review_cli.py          # CLI de fluxo de trabalho de revisão
    └── scheduled_run.py       # Runner para execução agendada com notificações
\`\`\`

**Responsabilidades dos pacotes:**
- **extraction**: Raspa DOU, extrai dados estruturados de PDFs
- **processing**: Aplica correções humanas, aprende delas via whitelists
- **export**: Gera arquivos de saída (PDFs, JSON)
- **cli**: Interfaces de linha de comando para fluxo de trabalho humano no circuito e automação

Arquivos e pastas
- `editais/` — PDFs salvos gerados pelo scraper (qualidade de impressão via Playwright)
- `data/summaries/` — resumos JSON extraídos de cada PDF
- `data/review_*.csv` — CSVs gerados para revisão manual
- `data/backups/` — backups criados ao aplicar correções do CSV
- `data/reviewed_examples/` — dados de treinamento de correções aplicadas (alimenta aprendizado de whitelist)
- `data/cargos_whitelist.json` — variações de cargo para extração de fallback (auto-atualizado)
- `data/bancas_whitelist.json` — organizações bancas para extração de fallback (auto-atualizado)

Dependências (recomendadas)
- `pdfplumber` — extração de texto e tabela de PDF
- `dateparser` — normalizar datas em português
- `playwright` — exportação de PDF (pacote Python) e motores de navegador

Instalação
\`\`\`bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# instalar motores de navegador Playwright
python -m playwright install
\`\`\`

Guia de depuração para desenvolvedores
- Um passo a passo está disponível em `docs/debugger_walkthrough.md` (ignorado pelo Git por padrão). Explica o fluxo do pipeline, funções principais para inspecionar e verificações interativas rápidas para problemas comuns.

Guia de agendamento e automação
- **Execução automática periódica com notificações** está totalmente documentada em [docs/scheduling.md](docs/scheduling.md)
- Suporta cron jobs e systemd timers
- Configuração de notificações por email (Gmail/SMTP), webhook (Slack, Discord) ou desktop
- Exemplos prontos para uso com instruções passo a passo

---

## Resumo de Início Rápido

1. **Raspar e extrair:**
   \`\`\`bash
   python src/main.py -d 30 --export-pdf
   \`\`\`

2. **Revisar extrações:**
   \`\`\`bash
   python src/review_cli.py --summaries-dir data/summaries
   # Edite o arquivo CSV gerado
   \`\`\`

3. **Aplicar correções:**
   \`\`\`bash
   python src/apply_review.py --csv data/review_*.csv --apply --reviewer "SeuNome"
   \`\`\`

4. **Atualizar whitelists:**
   \`\`\`bash
   python src/update_whitelist.py --threshold 1 --apply
   \`\`\`

5. **Próxima raspagem:** Correções dos passos 3-4 melhoram automaticamente a extração!

---

