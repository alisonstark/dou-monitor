# Doumon — Passo a Passo para Depuração (educacional)

Propósito: Este documento guia você através de uma execução fictícia da ferramenta e explica, passo a passo, quais componentes são executados, o que esperar em cada etapa e quais funções inspecionar durante a depuração. É intencionalmente pragmático e aponta para as funções principais/secundárias usadas.

Nota: este arquivo é apenas para aprendizado e depuração local. Está adicionado ao `.gitignore` por padrão.

Visão geral (execução única)

- Entrada: um intervalo de datas (padrão últimos 7 dias) passado para `src/main.py` (ou execute sem argumentos)
- Pipeline geral:
  1. `main.py` chama `scrape_concursos(start_date, end_date)` (em `src/scraper.py`) para coletar entradas candidatas do DOU.
 2. `main.py` filtra resultados por avisos de abertura (palavras-chave como `abertura`, `início`).
 3. Para cada entrada relevante, `process_abertura_concursos()` irá visualizar o conteúdo ou exportar um PDF (`src/pdf_export.py`).
 4. Quando um PDF é salvo, `main.py` chama `save_extraction_json(...)` (em `src/extractor.py`) para criar um resumo JSON estruturado em `data/summaries/`.
 5. Você pode gerar um CSV para revisão humana via `src/review_cli.py`, e aplicar correções com `src/apply_review.py` (que também exporta exemplos revisados). Use `src/update_whitelist.py` para propor atualizações de whitelist a partir dos exemplos revisados.


Exemplo passo a passo (entrada fictícia)

Assuma que você execute a ferramenta para processar o DOU de 10-Fev-2026 a 19-Fev-2026.

1) Inicie o pipeline

Comando:
\`\`\`
python src/main.py --export-pdf
\`\`\`

O que acontece e onde procurar
- `src/main.py` (ponto de entrada)
  - `scrape_concursos(start_date, end_date)` (em `src/scraper.py`) — recupera uma lista de dicts como `{ 'url', 'title', 'date', 'edition', 'section', 'url_title' }`.
  - Filtragem: `main.py` mantém entradas cujo `title` contém palavras-chave (`abertura`, `início`, `iniciado`).

2) Para cada `concurso` selecionado (aviso de abertura)

- Se `--export-pdf` estiver definido:
  - `save_concurso_pdf(concurso)` em `src/pdf_export.py` abre a página com Playwright, imprime a página como PDF e salva em `editais/{url_title}.pdf`.
  - Imediatamente após `save_concurso_pdf`, `main.py` chama `save_extraction_json(pdf_path)` do extrator.

- Se não estiver exportando PDF (modo visualização):
  - `get_concurso_preview_lines(concurso, max_lines)` em `src/scraper.py` busca o HTML e retorna as primeiras linhas (usa `requests` + BeautifulSoup).

3) Extração PDF → JSON (área principal para depuração)

- Entrada: `save_extraction_json(path_pdf, out_dir='data/summaries')` em `src/extractor.py`.
  - Chama `extract_from_pdf(path)` que usa `_extract_text_from_pdf(path)`.
  - `_extract_text_from_pdf` tenta `pdfplumber` (fallback: registra aviso e retorna string vazia).

Funções de extração primárias (o que fazem)
- `extract_basic_metadata(text)`
  - Extrai `orgao`, `edital_numero`, `cargo`, `banca` e `data_publicacao_dou`.
  - Usa heurísticas de cabeçalho (por exemplo, linhas ao redor da tag `EDITAL`).
  - Extração de `banca` é em camadas e retorna um dict: `{ nome, tipo, confianca_extracao, snippet }`.

- `extract_cronograma(text)`
  - Heurísticas para detectar datas importantes: inscrição (início/fim), isenção, data da prova, resultado da isenção.
  - Usa padrões regex para `dd/mm/yyyy` e `d de mês de yyyy` e `dateparser` quando disponível.

- `extract_vagas(text)`
  - Tenta capturar `total`, `pcd`, `ppiq`, com regex simples e verificações de consistência (por exemplo, descartar `pcd` se > total).

- `extract_financeiro(text)`
  - Encontra padrões de moeda `R$` para `taxa_inscricao` e tenta capturar `remuneracao_inicial` próximo a palavras-chave como `Remuneração`, `Vencimento`.

Auxiliares secundários (apenas menção)
- `_find_first_currency`, `_parse_date`, `_load_whitelist` (carrega `data/bancas_whitelist.json`), `extract_banca_struct` (o extrator de banca em camadas), `extract_from_pdf`, `save_extraction_json`.

4) Saída e onde inspecionar

- Resumo JSON salvo em: `data/summaries/{pdf_basename}.json`.
- Campos de interesse:
  - `metadata`: `{ orgao, edital_numero, cargo, banca (dict), data_publicacao_dou }`
  - `cronograma`: campos de data (strings ISO quando parseáveis)
  - `vagas`: `{ total, pcd, ppiq }`
  - `financeiro`: `{ taxa_inscricao, remuneracao_inicial }`

Dica: abra o JSON e inspecione `metadata.banca.snippet` — mostra a região de texto usada para decidir a banca. Se a extração parecer errada, o snippet ajuda você a criar um regex melhor ou adicionar o nome à whitelist.

5) Revisão humana no circuito

- Gere um CSV: `python src/review_cli.py --summaries-dir data/summaries` → gera `data/review_<timestamp>.csv`.
  - Função chave: `compute_confidence(item)` (pontua extração, retorna lista de problemas).

- Edite o CSV manualmente para corrigir campos (por exemplo, corrigir nome da `banca`)

- Aplicar correções: dry-run para visualizar mudanças:
  \`\`\`bash
  python src/apply_review.py --csv data/review_YYYYMMDDT...csv
  \`\`\`

- Aplicar correções (grava JSON, cria backups e exporta exemplos revisados para treinamento):
  \`\`\`bash
  python src/apply_review.py --csv data/review_YYYYMMDDT...csv --apply --reviewer "SeuNome"
  \`\`\`
  - `apply_review.apply_row()` é a função principal que aplica uma linha CSV: cria backups (`data/backups/`), atualiza JSON e exporta um exemplo para `data/reviewed_examples/` contendo `changes` e o `snippet` original.

6) De exemplos revisados → atualização da whitelist (pipeline de aprendizado)

- `src/update_whitelist.py` lê `data/reviewed_examples/*.json` e sugere candidatos que aparecem pelo menos `--threshold` vezes.
  - Dry-run: `python src/update_whitelist.py --threshold 3` (lista candidatos)
  - Aplicar: `python src/update_whitelist.py --threshold 3 --apply` → atualiza `data/bancas_whitelist.json`.

- O extrator usa `data/bancas_whitelist.json` automaticamente nas próximas execuções.

Checklist de depuração e testes rápidos

- Se a extração retornar JSON vazio ou campos estiverem faltando:
  - Verifique `data/summaries/{file}.json` para ver `metadata.banca.snippet` e janelas de `cronograma`.
  - Execute pequenos testes interativos:
    \`\`\`python
    from src.extractor import _extract_text_from_pdf, extract_basic_metadata
    txt = _extract_text_from_pdf('editais/example.pdf')
    print(extract_basic_metadata(txt))
    \`\`\`
  - Se o texto estiver vazio, confirme que `pdfplumber` está instalado no virtualenv e que o PDF não é apenas um scan de imagem.

- Se `banca` estiver errada:
  - Inspecione `metadata.banca.snippet` no JSON.
  - Se o nome for um fornecedor conhecido, adicione-o a `data/bancas_whitelist.json` (ou execute `update_whitelist.py` após aplicar correções).

- Se `vagas` mostrar números implausíveis:
  - Abra a página do PDF e procure pela tabela `Quadro de Vagas` ou `ANEXO` — use extração de tabela do `pdfplumber` manualmente para inspecionar caixas delimitadoras.

- Para problemas de parsing de data:
  - Confirme que `dateparser` está instalado; caso contrário, `_parse_date` retorna `None`.

Arquivos e localizações (resumo)

- `src/main.py` — orquestração e flag CLI `--export-pdf` (fluxos de visualização vs exportação)
- `src/scraper.py` — `scrape_concursos`, `get_concurso_preview_lines` (requests + BeautifulSoup)
- `src/pdf_export.py` — `save_concurso_pdf` baseado em Playwright
- `src/extractor.py` — pipeline de extração (extração de texto, metadata/vagas/cronograma/financeiro)
- `src/review_cli.py` — gera CSV de revisão (`compute_confidence`, `generate_csv`)
- `src/apply_review.py` — aplica correções do CSV e exporta exemplos revisados
- `src/update_whitelist.py` — sugere / aplica atualizações de whitelist de exemplos revisados
- `data/summaries/` — resumos JSON (saída do extrator)
- `data/review_*.csv` — CSVs de revisão humana
- `data/reviewed_examples/` — exemplos corrigidos exportados (usados por `update_whitelist.py`)
- `data/bancas_whitelist.json` — whitelist editável para bancas conhecidas

Notas finais

- Aplicar correções via `apply_review.py --apply` é necessário para produzir `data/reviewed_examples/`, que o `update_whitelist.py` consome. O extrator pegará mudanças na whitelist automaticamente na próxima execução (sem mudanças de código necessárias).
- O projeto intencionalmente separa correções de dados (aplicadas ao JSON) de heurísticas do extrator — você deve executar `update_whitelist.py --apply` para atualizar o arquivo de whitelist ou modificar heurísticas em `src/extractor.py` para mudar o comportamento.

Boa depuração! Use os snippets incluídos em `metadata.banca.snippet` para iterar rapidamente em regexes e entradas de whitelist.

---
Gerado: 2026-02-19

