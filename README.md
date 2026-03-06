# Doumon - Monitor de Concursos Públicos

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Características](#-características)
- [Requisitos](#-requisitos)
- [Instalação](#-instalação)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Uso](#-uso)
- [Fluxo de Trabalho](#-fluxo-de-trabalho)
- [Arquitetura](#-arquitetura)
- [Agendamento e Automação](#-agendamento-e-automação)
- [Testes](#-testes)
- [Melhorias Futuras](#-melhorias-futuras)
- [Licença](#-licença)

---

## 🎯 Visão Geral

**Doumon** é uma ferramenta Python para monitoramento automatizado de publicações do **DOU (Diário Oficial da União)** relacionadas a concursos públicos. 

O sistema foi desenvolvido para **candidatos a concursos**, **profissionais de RH** e **organizadores de processos seletivos** que precisam acompanhar editais e cronogramas de forma eficiente.

Principais capacidades:
- 🔍 **Scraping Inteligente** - Busca automatizada no DOU com filtros por palavras-chave
- 📄 **Exportação PDF de Alta Qualidade** - Layout de impressão do site oficial
- 🤖 **Extração Automática de Dados** - Parsing estruturado de editais em JSON
- 📅 **Análise de Cronogramas** - Extração semântica de datas e prazos importantes
- 🔄 **Sistema Auto-melhorador** - Aprende com correções humanas
- ⏰ **Execução Agendada** - Monitoramento contínuo com notificações

---

## ✨ Características

### 🔍 Scraping e Monitoramento

- **Busca Automatizada no DOU**  
  Raspa resultados usando dados JSON embutidos com gerenciamento robusto de retentativas e timeouts

- **Filtragem Inteligente**  
  Detecta editais de abertura por palavras-chave configuráveis (abertura, inicio, iniciado) com correspondência case-insensitive

- **Visualização Organizada**  
  Modo visualização lista todos os concursos encontrados com títulos numerados e destaques para correspondências

### 📄 Extração de Dados

- **PDF → JSON Estruturado**  
  Extração automática de campos estruturados dos editais:
  - 📋 **Metadata**: Órgão, edital número, cargo, banca organizadora
  - 👥 **Vagas**: Total, PCD, PPIQ/PPQ
  - 💰 **Financeiro**: Taxa de inscrição, remuneração
  - 📅 **Cronograma**: Inscrição (início/fim), isenção, data da prova

- **Parser de Cronograma Multi-formato**  
  Sistema de extração semântica com suporte a diversos layouts de edital:
  - Estratégia dupla: baseada em palavras-chave + análise de contexto retrospectivo
  - Otimização baseada em seções para maior velocidade
  - Suporta formatos de Banco do Brasil, INSS, Caixa, Petrobras e outros

### 🔄 Sistema de Aprendizado

- **Fluxo de Revisão Humana no Circuito**  
  Geração de CSV para revisão manual e aplicação de correções validadas

- **Whitelists Auto-atualizáveis**  
  Correções manuais atualizam automaticamente listas de cargos e bancas conhecidas

- **Extração Progressivamente Melhor**  
  Extrações futuras se beneficiam de correções passadas, reduzindo intervenção manual

- **Correspondência Case-insensitive**  
  Suporta qualquer variação de capitalização para cargos e bancas

### ⏰ Automação Completa

- **Execução Agendada**  
  Runner dedicado para agendamento via cron (Linux) ou Task Scheduler (Windows)

- **Notificações Configuráveis**  
  Alertas por email (SMTP), webhook (Slack, Discord) ou desktop quando novos concursos são detectados

- **Thresholds Personalizáveis**  
  Configure intervalo de busca e critérios de notificação

---

## ⚙️ Requisitos

- **Python**: 3.8+ (3.11+ recomendado)
- **Playwright**: Para exportação de PDF via navegador headless
- **Dependências**: Listadas em `requirements.txt` (pdfplumber, dateparser, playwright, requests)

> 📁 Os navegadores Playwright devem ser instalados separadamente após a instalação do pacote Python

---

## 🧰 Instalação

### 1. Criar ambiente virtual (recomendado)

```bash
python -m venv .venv
```

**Windows:**
```powershell
.venv\Scripts\activate
```

**Linux/macOS:**
```bash
source .venv/bin/activate
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Instalar navegadores Playwright

```bash
python -m playwright install
```

---

## 📁 Estrutura do Projeto

```
dou-monitor/
├── README.md                           # Este arquivo
├── changes_summary.md                  # Histórico de mudanças
├── MELHORIAS_PARSER.md                 # Documentação técnica do parser
├── requirements.txt                    # Dependências Python
├── LICENSE                             # Licença do projeto
│
├── src/                                # Código-fonte principal
│   ├── main.py                         # Ponto de entrada e orquestração
│   │
│   ├── extraction/                     # Pipeline de extração
│   │   ├── scraper.py                  # Web scraping do DOU
│   │   ├── extractor.py                # Extração de metadata de PDF
│   │   └── cronograma_parser.py        # Parser de datas e cronograma
│   │
│   ├── processing/                     # Processamento de dados
│   │   ├── apply_review.py             # Aplicação de correções do CSV
│   │   └── update_whitelist.py         # Atualização de whitelists
│   │
│   ├── export/                         # Geração de outputs
│   │   └── pdf_export.py               # Exportação PDF via Playwright
│   │
│   ├── cli/                            # Interfaces CLI
│   │   ├── review_cli.py               # CLI de revisão
│   │   └── scheduled_run.py            # Runner agendado
│   │
│   └── web/                            # Dashboard web
│       ├── app.py                      # Aplicação Flask e rotas
│       ├── dashboard_service.py        # Serviço de carregamento/filtros/categorização
│       ├── templates/
│       │   └── dashboard.html          # Template Jinja2
│       └── static/
│           └── dashboard.css           # Estilos CSS
│
├── data/                               # Dados e configurações
│   ├── cargos_whitelist.json           # Lista de cargos conhecidos
│   ├── summaries/                      # Resumos JSON extraídos
│   ├── dashboard_config.json           # Configurações salvas do dashboard (gerado)
│   ├── backups/                        # Backups de alterações
│   └── reviewed_examples/              # Exemplos revisados (treinamento)
│
├── editais/                            # PDFs exportados
│
├── docs/                               # Documentação adicional
│   ├── debugger_walkthrough.md         # Guia de debugging
│   └── scheduling.md                   # Guia de agendamento
│
└── tests/                              # Testes unitários
    ├── test_cronograma_parser.py
    ├── test_extractor.py
    ├── test_scraper.py
    ├── test_dashboard_service.py
    ├── test_web_app.py
    ├── test_scheduled_run.py
    └── test_categorize.py
```

---

## 📂 Uso

### Comando Principal

Execute o script principal da raiz do projeto:

```bash
cd "c:\Users\moonpie\Documents\Git Projects\dou-monitor"
python src/main.py
```

### Exemplos de Uso

**Modo visualização (sem exportar PDFs):**
```bash
python src/main.py            # Últimos 7 dias (padrão)
python src/main.py -d 14      # Últimos 14 dias
```

**Exportar PDFs e extrair dados:**
```bash
python src/main.py -d 30 --export-pdf
```

### Opções de CLI

| Opção | Atalho | Descrição | Padrão |
|-------|--------|-----------|--------|
| `--export-pdf` | - | Salvar PDFs de qualidade de impressão e extrair resumos JSON | Desativado |
| `--days` | `-d` | Janela de retrospectiva em dias | 7 |

### Saída Esperada

O script exibe:
1. ✅ Intervalo de datas pesquisado
2. 📋 **Todos os concursos encontrados** (lista numerada com títulos)
3. 🎯 Concursos de abertura (palavras-chave: abertura, inicio, iniciado)
4. 📊 Resultados de processamento para cada edital (quando `--export-pdf` ativado)

------

## 🔄 Fluxo de Trabalho

### Pipeline de Extração (PDF → JSON)

Após exportar PDFs com `--export-pdf`, o sistema automaticamente:
1. Extrai texto estruturado do PDF
2. Identifica e parseia campos-chave
3. Salva resumo JSON em `data/summaries/`

**Campos extraídos:**
- 📋 Metadata: órgão, número do edital, cargo, banca organizadora
- 👥 Vagas: total, PCD, PPQ/PPIQ
- 💰 Financeiro: taxa de inscrição, remuneração
- 📅 **Cronograma: inscrição (início/fim), isenção (início), data da prova**

**Processo de extração em dois estágios:**
1. **Estágio prioritário**: Localiza e extrai da seção CRONOGRAMA (rápido, preciso)
2. **Fallback**: Varredura completa do PDF se detecção de seção falhar (robusto)

**Extração baseada em confiança:**
- Alta confiança: palavra-chave aparece no contexto da data
- Baixa confiança: correspondência retrospectiva genérica
- Suporta múltiplos formatos de tabela de diferentes agências governamentais

### Revisão Humana (Aprendizado no Circuito)

#### 1️⃣ Gerar CSV de Revisão

```bash
python src/cli/review_cli.py --summaries-dir data/summaries
```

**Resultado:** `data/review_<timestamp>.csv` com:
- Lista de todos os resumos
- Pontuações de confiança
- Problemas sinalizados

#### 2️⃣ Aplicar Correções

Após editar o CSV manualmente:

**Modo dry-run (visualizar mudanças):**
```bash
python src/processing/apply_review.py --csv data/review_YYYYMMDDTHHMMSSZ.csv
```

**Aplicar mudanças (cria backups):**
```bash
python src/processing/apply_review.py --csv data/review_YYYYMMDDTHHMMSSZ.csv --apply --reviewer "SeuNome"
```

**O script cria:**
- ✅ Arquivos JSON atualizados em `data/summaries/`
- 💾 Backups automáticos em `data/backups/`
- 📚 **Exemplos revisados em `data/reviewed_examples/`** (para treinamento)

#### 3️⃣ Atualizar Whitelists (Loop de Aprendizado)

```bash
python src/processing/update_whitelist.py --threshold 1 --apply
```

**O que faz:**
- Analisa todos os exemplos revisados em `data/reviewed_examples/`
- Encontra valores de cargo/banca aparecendo ≥ threshold vezes
- Adiciona a `data/cargos_whitelist.json` e `data/bancas_whitelist.json`

**Como a whitelist melhora a extração:**

**Estágio 1 - Validação/Normalização:**
- Cargo/banca extraído via regex → valida contra whitelist → normaliza para forma canônica

**Estágio 2 - Extração de Fallback:**
- Se NENHUM cargo/banca encontrado por padrões primários → busca PDF por itens da whitelist
- 🎯 **Correções de hoje melhoram automaticamente a extração de amanhã**

**Visualizar mudanças propostas sem aplicar:**
```bash
python src/processing/update_whitelist.py --threshold 1
```

---

## 🏗️ Arquitetura

### Organização de Pacotes

O código-fonte em `src/` é organizado em pacotes focados para melhor manutenibilidade e separação de responsabilidades.

### Responsabilidades dos Pacotes

| Pacote | Responsabilidade |
|--------|------------------|
| **extraction/** | Raspa DOU, extrai dados estruturados de PDFs |
| **processing/** | Aplica correções humanas, aprende via whitelists |
| **export/** | Gera arquivos de saída (PDFs, JSON) |
| **cli/** | Interfaces para fluxo humano no circuito e automação |
| **web/** | Dashboard web para visualização, filtros e configurações |

### Arquivos e Pastas de Dados

| Diretório/Arquivo | Descrição |
|-------------------|-----------|
| `editais/` | PDFs salvos (qualidade de impressão via Playwright) |
| `data/summaries/` | Resumos JSON extraídos de cada PDF |
| `data/review_*.csv` | CSVs gerados para revisão manual |
| `data/backups/` | Backups criados ao aplicar correções |
| `data/reviewed_examples/` | Dados de treinamento (alimenta whitelists) |
| `data/cargos_whitelist.json` | Variações de cargo conhecidas |
| `data/bancas_whitelist.json` | Bancas organizadoras conhecidas |

---

## ⏰ Agendamento e Automação

Execute o Doumon periodicamente para monitoramento contínuo de novos concursos.

### Configuração Rápida

**1. Configurar notificações** (opcional mas recomendado)

Edite as variáveis de ambiente ou configure o arquivo de configuração para receber alertas:
- 📧 **Email**: Configure SMTP (Gmail, Outlook, etc.)
- 🔔 **Webhook**: Slack, Discord ou serviço customizado
- 💻 **Desktop**: Notificações do sistema operacional

**2. Criar tarefa agendada**

**Linux (cron):**
```bash
# Executar todo dia às 8h
0 8 * * * cd /caminho/para/dou-monitor && .venv/bin/python src/cli/scheduled_run.py
```

**Windows (Task Scheduler):**
```powershell
# Criar tarefa agendada via PowerShell
$action = New-ScheduledTaskAction -Execute "C:\Users\moonpie\Documents\Git Projects\dou-monitor\.venv\Scripts\python.exe" -Argument "src\cli\scheduled_run.py" -WorkingDirectory "C:\Users\moonpie\Documents\Git Projects\dou-monitor"
$trigger = New-ScheduledTaskTrigger -Daily -At 8am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "Doumon" -Description "Monitora novos concursos no DOU"
```

### Documentação Completa

Para configuração detalhada de notificações, exemplos e troubleshooting, consulte:
📖 **[docs/scheduling.md](docs/scheduling.md)**

---

## 🌐 Dashboard Web

O projeto agora inclui um dashboard web inicial para:
- Visualizar concursos extraídos de `data/summaries/`
- Aplicar filtros por órgão, cargo, banca, busca livre e faixa de data de prova
- Ordenar e paginar os resultados da tabela
- Gerenciar configurações persistentes de filtros e notificações
- Expor endpoint JSON para integrações (`/api/concursos`)
- **Executar monitoramento manual** com um clique (scraping + opcional exportação de PDFs)

### Executar localmente

```bash
python -m src.web.app
```

Abra no navegador:

`http://127.0.0.1:5000`

### Funcionalidades do dashboard

#### Visualização em Duas Seções
O dashboard organiza os concursos em duas categorias:
- **Concursos Abertos**: Editais identificados com palavras-chave de abertura (abertura, início, iniciado)
- **Outros Editais e Concursos**: Demais editais que podem conter informações relevantes mas não foram identificados como aberturas

Cada concurso exibe link direto para **baixar o PDF do edital** diretamente no navegador.

#### Execução Manual
No painel "Execução Manual", você pode:
- Iniciar uma busca no DOU com número configurável de dias de retrospecção
- Opcionalmente exportar PDFs e extrair dados automaticamente
- Ver resultados imediatamente via flash messages (total de concursos, aberturas encontradas, etc.)

#### Filtros e Ordenação
- Busca livre por texto em qualquer campo
- Filtros específicos por órgão, cargo, banca
- Faixa de datas de prova
- Ordenação por 6 colunas (órgão, cargo, banca, edital, data prova, vagas total)
- Paginação com tamanho configurável (10/20/50 itens)

#### API REST
Endpoint JSON para integrações externas:
```
GET /api/concursos?cargo=Professor&page=1&page_size=10
```

### Arquivos usados pelo dashboard

- `src/web/app.py` - aplicação Flask e rotas
- `src/web/dashboard_service.py` - carregamento, filtros, métricas e execução manual
- `src/web/templates/dashboard.html` - interface web
- `src/web/static/dashboard.css` - estilos da interface
- `data/dashboard_config.json` - configurações salvas da UI

As configurações de notificação salvas no dashboard são usadas como padrão pelo runner `src/cli/scheduled_run.py` quando variáveis de ambiente/flags não forem informadas.

---

## 🧪 Testes

Execute a suite de testes unitários:

```bash
# Da raiz do projeto
python -m unittest discover tests -v
```

**Cobertura de testes:**
- ✅ `test_cronograma_parser.py` - Parser de datas e cronograma
- ✅ `test_extractor.py` - Extração de metadata
- ✅ `test_scraper.py` - Web scraping do DOU
- ✅ `test_dashboard_service.py` - Filtros, métricas, ordenação e paginação do dashboard
- ✅ `test_web_app.py` - Rotas HTML/API do dashboard
- ✅ `test_scheduled_run.py` - Leitura de notificações via `dashboard_config.json`
- ✅ `test_categorize.py` - Categorização de concursos abertos vs outros editais

### Testes Manuais com Dados Reais

Para testar com editais reais já salvos:

```bash
# Processar PDFs específicos
python src/extraction/extractor.py editais/exemplo.pdf
```

---

---

## 🚀 Resumo de Início Rápido

### Pipeline Completo em 5 Passos

**1️⃣ Fazer scraping e extrair dados:**
```bash
python src/main.py -d 30 --export-pdf
```

**2️⃣ Revisar extrações:**
```bash
python src/cli/review_cli.py --summaries-dir data/summaries
# Edite o arquivo CSV gerado manualmente
```

**3️⃣ Aplicar correções:**
```bash
python src/processing/apply_review.py --csv data/review_*.csv --apply --reviewer "SeuNome"
```

**4️⃣ Atualizar whitelists:**
```bash
python src/processing/update_whitelist.py --threshold 1 --apply
```

**5️⃣ Próxima raspagem:**
```bash
# Correções dos passos 3-4 melhoram automaticamente a extração! 🎯
python src/main.py -d 30 --export-pdf
```

---

## 🚧 Melhorias Futuras

### Prioridade Alta

- **🎨 Interface Web**  
  ✅ Dashboard web MVP concluído (visualização, filtros, ordenação, API REST, execução manual)  
  🚧 Próximos passos: Status de monitoramento em tempo real, histórico de execuções

- **🔔 Notificações Avançadas**  
  - Filtros por órgão, cargo, região
  - Telegram bot para notificações mobile
  - Sistema de subscrição para múltiplos usuários

- **📊 Análise de Dados**  
  - Estatísticas de concursos por período
  - Tendências de vagas por área
  - Análise de bancas mais frequentes

### Prioridade Média

- **🤖 Melhorias de IA**  
  - Classificação automática de cargos por área
  - Detecção de inconsistências em editais
  - Sugestões de palavras-chave para filtros

- **📱 App Mobile**  
  - Aplicativo React Native para iOS/Android
  - Notificações push nativas
  - Modo offline com sincronização

- **🔍 Busca Avançada**  
  - Filtros combinados (cargo + região + salário)
  - Busca por similaridade semântica
  - Histórico de buscas salvas

### Backlog

- **🔗 Integração com Outros Diários**  
  - Diários oficiais estaduais
  - Diários municipais de capitais
  - Portal de concursos unificado

- **📈 Exportação Avançada**  
  - Excel com formatação
  - Relatórios PDF personalizados
  - Integração com Google Sheets

- **🧪 Cobertura de Testes**  
  - Testes de integração end-to-end
  - Testes de performance
  - Cobertura > 90%

---

## 📚 Documentação Adicional

- **[changes_summary.md](./changes_summary.md)** - Histórico detalhado de mudanças
- **[MELHORIAS_PARSER.md](./MELHORIAS_PARSER.md)** - Documentação técnica do parser de cronograma
- **[docs/scheduling.md](./docs/scheduling.md)** - Guia completo de agendamento e automação
- **[docs/debugger_walkthrough.md](./docs/debugger_walkthrough.md)** - Guia de debugging para desenvolvedores

---

## 📄 Licença

Consulte o arquivo [LICENSE](./LICENSE) para detalhes.

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Para contribuir:

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

---

**Desenvolvido com ❤️ para facilitar a vida de candidatos a concursos públicos**

