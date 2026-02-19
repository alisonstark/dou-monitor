# DOU-monitor — Debugger-style Walkthrough (educational)

Purpose: This document walks you through a fictional run of the tool and explains, step-by-step, which components are executed, what to expect at each stage, and which functions to inspect when debugging. It is intentionally pragmatic and points to the main/secondary functions used.

Note: this file is for learning and local debugging only. It is added to `.gitignore` by default.

Overview (single run)

- Input: a date range (default last 7 days) passed to `src/main.py` (or run without args)
- Overall pipeline:
  1. `main.py` calls `scrape_concursos(start_date, end_date)` (in `src/scraper.py`) to collect candidate DOU entries.
 2. `main.py` filters results for opening notices (keywords like `abertura`, `início`).
 3. For each relevant entry `process_abertura_concursos()` will either preview content or export a PDF (`src/pdf_export.py`).
 4. When a PDF is saved, `main.py` calls `save_extraction_json(...)` (in `src/extractor.py`) to create a structured JSON summary in `data/summaries/`.
 5. You can generate a human-review CSV via `src/review_cli.py`, and apply corrections with `src/apply_review.py` (which also exports reviewed examples). Use `src/update_whitelist.py` to propose whitelist updates from reviewed examples.


Step-by-step example (fictional input)

Assume you run the tool to process DOU for 10-Feb-2026 to 19-Feb-2026.

1) Start the pipeline

Command:
```
python src/main.py --export-pdf
```

What happens and where to look
- `src/main.py` (entrypoint)
  - `scrape_concursos(start_date, end_date)` (in `src/scraper.py`) — retrieves a list of dicts like `{ 'url', 'title', 'date', 'edition', 'section', 'url_title' }`.
  - Filtering: `main.py` keeps entries whose `title` contains keywords (`abertura`, `início`, `iniciado`).

2) For each selected `concurso` (opening notice)

- If `--export-pdf` is set:
  - `save_concurso_pdf(concurso)` in `src/pdf_export.py` opens the page with Playwright, prints the page as PDF, and saves it to `editais/{url_title}.pdf`.
  - Immediately after `save_concurso_pdf`, `main.py` calls `save_extraction_json(pdf_path)` from the extractor.

- If not exporting PDF (preview mode):
  - `get_concurso_preview_lines(concurso, max_lines)` in `src/scraper.py` fetches the HTML and returns the first lines (uses `requests` + BeautifulSoup).

3) PDF → JSON extraction (core area for debugging)

- Entry: `save_extraction_json(path_pdf, out_dir='data/summaries')` in `src/extractor.py`.
  - Calls `extract_from_pdf(path)` which uses `_extract_text_from_pdf(path)`.
  - `_extract_text_from_pdf` tries `pdfplumber` (fallback: log warning and return empty string).

Primary extraction functions (what they do)
- `extract_basic_metadata(text)`
  - Extracts `orgao`, `edital_numero`, `cargo`, `banca` and `data_publicacao_dou`.
  - Uses header heuristics (e.g., lines around the `EDITAL` tag).
  - `banca` extraction is layered and returns a dict: `{ nome, tipo, confianca_extracao, snippet }`.

- `extract_cronograma(text)`
  - Heuristics to detect important dates: inscrição (start/end), isenção, data da prova, resultado da isenção.
  - Uses regex patterns for `dd/mm/yyyy` and `d de mês de yyyy` and `dateparser` when available.

- `extract_vagas(text)`
  - Tries to capture `total`, `pcd`, `ppiq`, with simple regex and consistency checks (e.g., discard `pcd` if > total).

- `extract_financeiro(text)`
  - Finds currency patterns `R$` for `taxa_inscricao` and tries to capture `remuneracao_inicial` near keywords like `Remuneração`, `Vencimento`.

Secondary helpers (mention only)
- `_find_first_currency`, `_parse_date`, `_load_whitelist` (loads `data/bancas_whitelist.json`), `extract_banca_struct` (the layered banca extractor), `extract_from_pdf`, `save_extraction_json`.

4) Output and where to inspect

- JSON summary saved to: `data/summaries/{pdf_basename}.json`.
- Fields of interest:
  - `metadata`: `{ orgao, edital_numero, cargo, banca (dict), data_publicacao_dou }`
  - `cronograma`: date fields (ISO strings when parseable)
  - `vagas`: `{ total, pcd, ppiq }`
  - `financeiro`: `{ taxa_inscricao, remuneracao_inicial }`

Tip: open the JSON and inspect `metadata.banca.snippet` — it shows the text region used to decide the banca. If extraction looks wrong, the snippet helps you craft a better regex or add the name to the whitelist.

5) Human-in-the-loop review

- Generate a CSV: `python src/review_cli.py --summaries-dir data/summaries` → writes `data/review_<timestamp>.csv`.
  - Key function: `compute_confidence(item)` (scores extraction, returns issues list).

- Edit the CSV manually to correct fields (e.g., fix `banca` name)

- Apply corrections: dry-run to preview changes:
  ```bash
  python src/apply_review.py --csv data/review_YYYYMMDDT...csv
  ```

- Apply corrections (writes JSON, makes backups, and exports reviewed examples for training):
  ```bash
  python src/apply_review.py --csv data/review_YYYYMMDDT...csv --apply --reviewer "SeuNome"
  ```
  - `apply_review.apply_row()` is the main function that applies one CSV row: it creates backups (`data/backups/`), updates JSON, and exports an example to `data/reviewed_examples/` containing `changes` and the original `snippet`.

6) From reviewed examples → whitelist update (learning pipeline)

- `src/update_whitelist.py` reads `data/reviewed_examples/*.json` and suggests candidates that appear at least `--threshold` times.
  - Dry-run: `python src/update_whitelist.py --threshold 3` (lists candidates)
  - Apply: `python src/update_whitelist.py --threshold 3 --apply` → updates `data/bancas_whitelist.json`.

- The extractor uses `data/bancas_whitelist.json` automatically on next runs.

Debugging checklist and quick tests

- If extraction returns empty JSON or fields are missing:
  - Check `data/summaries/{file}.json` to see `metadata.banca.snippet` and `cronograma` windows.
  - Run small interactive tests:
    ```python
    from src.extractor import _extract_text_from_pdf, extract_basic_metadata
    txt = _extract_text_from_pdf('editais/example.pdf')
    print(extract_basic_metadata(txt))
    ```
  - If text is empty, confirm `pdfplumber` is installed in the virtualenv and that PDF is not an image-only scan.

- If `banca` is wrong:
  - Inspect `metadata.banca.snippet` in the JSON.
  - If the name is a known vendor, add it to `data/bancas_whitelist.json` (or run `update_whitelist.py` after applying corrections).

- If `vagas` shows implausible numbers:
  - Open the PDF page and search for the `Quadro de Vagas` or `ANEXO` table — use `pdfplumber` table extraction manually to inspect bounding boxes.

- For date parsing issues:
  - Confirm `dateparser` is installed; otherwise `_parse_date` returns `None`.

Files & locations (summary)

- `src/main.py` — orchestration and CLI flag `--export-pdf` (preview vs export flows)
- `src/scraper.py` — `scrape_concursos`, `get_concurso_preview_lines` (requests + BeautifulSoup)
- `src/pdf_export.py` — Playwright-based `save_concurso_pdf`
- `src/extractor.py` — extraction pipeline (text extraction, metadata/vagas/cronograma/financeiro)
- `src/review_cli.py` — generate review CSV (`compute_confidence`, `generate_csv`)
- `src/apply_review.py` — apply CSV corrections and export reviewed examples
- `src/update_whitelist.py` — suggest / apply whitelist updates from reviewed examples
- `data/summaries/` — JSON summaries (output of extractor)
- `data/review_*.csv` — human review CSVs
- `data/reviewed_examples/` — exported corrected examples (used by `update_whitelist.py`)
- `data/bancas_whitelist.json` — editable whitelist for known bancas

Final notes

- Applying corrections via `apply_review.py --apply` is required to produce `data/reviewed_examples/`, which `update_whitelist.py` consumes. The extractor will pick up whitelist changes automatically on the next run (no code changes required).
- The project intentionally separates data corrections (applied to JSON) from extractor heuristics — you must run `update_whitelist.py --apply` to update the whitelist file or modify `src/extractor.py` heuristics to change behavior.

Happy debugging! Use the snippets included in `metadata.banca.snippet` to rapidly iterate on regexes and whitelist entries.

---
Generated: 2026-02-19
