# Changes Summary

**Date:** February 18, 2026

## Problems Encountered

### Problem 1: Connection Error
The application was encountering a `requests.exceptions.ConnectionError` with the error message:
```
Remote end closed connection without response
```

**Root Cause:** The remote server was closing the connection unexpectedly due to bot detection (default `requests` library User-Agent identifies automated requests).

### Problem 2: No Search Results Found
After fixing the connection issue, the scraper was finding 0 results because it was looking for HTML `<a>` tags with the pattern `/web/dou/-/`, but the search results are not rendered as HTML links.

**Root Cause:** The DOU search page loads results dynamically using JavaScript. The search results are embedded as JSON data in a `<script>` tag, not as traditional HTML links in the initial page load.

### Problem 3: PDF Output Quality
Text-based PDFs looked poor because they did not capture the page's print styling.

**Root Cause:** Manual PDF generation ignored the page's print layout and dynamic styling.
# Changes Summary

**Date:** February 18, 2026

## Problems Encountered

### Problem 1: Connection Error
The application was encountering a `requests.exceptions.ConnectionError` with the error message:

```
Remote end closed connection without response
```

**Root Cause:** The remote server was closing the connection unexpectedly due to bot detection (default `requests` library User-Agent identifies automated requests).

### Problem 2: No Search Results Found
After fixing the connection issue, the scraper was finding 0 results because it was looking for HTML `<a>` tags with the pattern `/web/dou/-/`, but the search results are not rendered as HTML links.

**Root Cause:** The DOU search page loads results dynamically using JavaScript. The search results are embedded as JSON data in a `<script>` tag, not as traditional HTML links in the initial page load.

### Problem 3: PDF Output Quality
Text-based PDFs looked poor because they did not capture the page's print styling.

**Root Cause:** Manual PDF generation ignored the page's print layout and dynamic styling.

## Changes Made

### 1. HTTP Reliability and Parsing Fixes
- Added realistic browser headers to bypass bot detection.
- Added retry logic with progressive backoff and request timeouts.
- Switched scraping from HTML link parsing to embedded JSON parsing.
- Extracted structured fields (title, date, edition, section, URL) from results.

### 2. Print-Quality PDFs
- Replaced manual PDF generation with Playwright-based printing to match the site's print output.
- Ensured the PDF output uses print media styling and page sizing.
- Reused a single browser context with realistic user agent, locale, and timezone to avoid 403 responses.
````markdown
# Changes Summary

**Date:** February 18, 2026

## Problems Encountered

### Problem 1: Connection Error
The application was encountering a `requests.exceptions.ConnectionError` with the error message:
```
Remote end closed connection without response
```

**Root Cause:** The remote server was closing the connection unexpectedly due to bot detection (default `requests` library User-Agent identifies automated requests).

### Problem 2: No Search Results Found
After fixing the connection issue, the scraper was finding 0 results because it was looking for HTML `<a>` tags with the pattern `/web/dou/-/`, but the search results are not rendered as HTML links.

**Root Cause:** The DOU search page loads results dynamically using JavaScript. The search results are embedded as JSON data in a `<script>` tag, not as traditional HTML links in the initial page load.

### Problem 3: PDF Output Quality
Text-based PDFs looked poor because they did not capture the page's print styling.

**Root Cause:** Manual PDF generation ignored the page's print layout and dynamic styling.

# Changes Summary

**Date:** February 18, 2026

## Problems Encountered

### Problem 1: Connection Error
The application was encountering a `requests.exceptions.ConnectionError` with the error message:

```
Remote end closed connection without response
```

**Root Cause:** The remote server was closing the connection unexpectedly due to bot detection (default `requests` library User-Agent identifies automated requests).

### Problem 2: No Search Results Found
After fixing the connection issue, the scraper was finding 0 results because it was looking for HTML `<a>` tags with the pattern `/web/dou/-/`, but the search results are not rendered as HTML links.

**Root Cause:** The DOU search page loads results dynamically using JavaScript. The search results are embedded as JSON data in a `<script>` tag, not as traditional HTML links in the initial page load.

### Problem 3: PDF Output Quality
Text-based PDFs looked poor because they did not capture the page's print styling.

**Root Cause:** Manual PDF generation ignored the page's print layout and dynamic styling.

## Changes Made

### 1. HTTP Reliability and Parsing Fixes
- Added realistic browser headers to bypass bot detection.
- Added retry logic with progressive backoff and request timeouts.
- Switched scraping from HTML link parsing to embedded JSON parsing.
- Extracted structured fields (title, date, edition, section, URL) from results.

### 2. Print-Quality PDFs
- Replaced manual PDF generation with Playwright-based printing to match the site's print output.
- Ensured the PDF output uses print media styling and page sizing.
- Reused a single browser context with realistic user agent, locale, and timezone to avoid 403 responses.

### 3. Separation of Responsibilities
- Moved scraping logic into `src/scraper.py`.
- Moved PDF export into `src/pdf_export.py`.
- Kept `src/main.py` as the execution pipeline only.

### 4. Preview Mode and CLI Flag
- Added `--export-pdf` flag to toggle PDF generation.
- Added preview mode that prints the first 10 lines when PDF export is disabled.

## Result
The tool now:
- ✅ Reliably fetches search results across editions
- ✅ Parses JSON-embedded results correctly
- ✅ Produces print-accurate PDFs via Playwright
- ✅ Supports preview-only runs with a CLI flag
- ✅ Keeps scraping, export, and orchestration cleanly separated


---

## Date: February 19, 2026

### Additions (2026-02-19)

- **PDF → JSON extractor**: Added `src/extractor.py` which extracts structured fields from PDFs (metadata, cronograma, vagas, financeiro) using `pdfplumber` when available and heuristics (regex + dateparser). Output stored by default in `data/summaries/`.

- **Integration in pipeline**: `src/main.py` now calls the extractor after saving PDFs so a JSON summary is produced automatically for each saved edital.

- **Improved heuristics**: Enhanced extraction heuristics for `orgao`, `edital_numero`, `cargo`, `banca` and added basic consistency checks for vagas (e.g., discard PCD if it appears greater than total).

- **Review CSV CLI**: Added `src/review_cli.py` to generate a human-review CSV (`data/review_<timestamp>.csv`) with a confidence score and flagged issues (e.g., `banca_messy`, `pcd_gt_total`).

- **Apply review tool**: Added `src/apply_review.py` that applies corrections from the reviewed CSV back to JSON summaries. It supports dry-run and `--apply` modes and creates backups under `data/backups/` before writing.

- **Default summaries directory**: JSON summaries are now written to `data/summaries/` and review CSV files to `data/` as `review_<timestamp>.csv`.

### Tests performed

- Performed extraction on `editais/edital-de-abertura-de-10-de-fevereiro-de-2026-...686793927.pdf` and produced `data/summaries/...686793927.json`.
- Generated review CSV `data/review_20260219T135434Z.csv` and confirmed low-confidence detection (flagged `banca_messy`).

### Notes and next steps

- The extractor is intentionally conservative: fields not found are left as `null` in JSON. For difficult structures (tabular vagas, mixed-format banca blocks) we should add table parsing using `pdfplumber`'s table detection, or a human-in-the-loop training loop to produce labeled examples for an NER model.
- The current pipeline does not automatically learn from CSV corrections — `apply_review.py` applies changes deterministically. We can add an opt-in training exporter that accumulates reviewed corrections for a future ML model.

---

## Date: February 19, 2026 (documentation + learning pipeline additions)

### Additions (2026-02-19, continued)

- **Debugger walkthrough**: Added `docs/debugger_walkthrough.md` — a step-by-step debugging and learning guide that walks through a fictional run, lists the main functions involved and suggests interactive checks.

- **Reviewed examples export**: `src/apply_review.py` now exports reviewed examples to `data/reviewed_examples/` (one JSON per applied summary) to seed an incremental learning dataset.

- **Whitelist utility**: Added `src/update_whitelist.py` (proposes whitelist additions based on reviewed examples; `--apply` updates `data/bancas_whitelist.json`).

- **.gitignore**: `docs/debugger_walkthrough.md` added to `.gitignore` per request (document is developer-local by intention).

### Next recommended actions

- Run `apply_review.py --apply` after completing CSV edits to produce reviewed examples; then run `update_whitelist.py --threshold N --apply` to add frequent corrections to the extractor's whitelist. This process is not automatic and requires running both steps deliberately to avoid introducing noise.

---

## Date: February 19, 2026 (hotfixes & UX improvements)

### Quick fixes and CLI improvements

- **Added `requirements.txt`** with `playwright`, `pdfplumber`, and `dateparser` to simplify environment setup.
- **Fixed IndentationError** in `src/extractor.py` that caused the script to fail during import.
- **Added `--days` / `-d` CLI flag** to `src/main.py` to control the lookback window (default 7 days).
- **Lazy-import Playwright export**: `pdf_export` is now imported only when `--export-pdf` is used so preview mode runs without Playwright installed.

### Detection & preview improvements

- **Accent-insensitive keyword matching**: title matching now normalizes diacritics before searching for keywords like `abertura`/`inicio`/`iniciado`.
- **Preview boilerplate filter**: common site navigation strings are removed from preview output to avoid noisy lines.
- **Preview mode minimal output**: preview now prints only the title for matched notices (keeps console output concise).

### Notes

- These changes are incremental and focused on developer UX and robustness. If you want the scanner to be more aggressive, we can add a `--scan-body` option to search page content for keywords (slower but more reliable).

````

