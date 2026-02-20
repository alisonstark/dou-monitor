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

---

## Date: February 19, 2026 (whitelist expansion: cargo support)

### Additions (2026-02-19, whitelist expansion)

- **Cargo whitelist support**: Extended `src/update_whitelist.py` to track both `metadata.banca` and `metadata.cargo` fields from reviewed corrections.

- **Dual whitelist files**: The utility now maintains two separate whitelists:
  - `data/bancas_whitelist.json` — for external and internal banca organizations
  - `data/cargos_whitelist.json` — for cargo variations and aliases (e.g., "Professor", "PROFESSOR DA CARREIRA DE MAGISTÉRIO SUPERIOR")

- **Cargo validation in extractor**: Updated `src/extractor.py` to validate extracted cargo values against `data/cargos_whitelist.json` using case-insensitive fuzzy matching. When a match is found, the whitelisted version is used for normalization.

- **Refactored whitelist loading**: Unified whitelist loading logic in `src/extractor.py` with `_load_whitelist()`, `_load_bancas_whitelist()`, and `_load_cargos_whitelist()` functions for better maintainability.

### Workflow

Cargo can now be improved through the same feedback loop as banca:

1. Extract PDFs (cargo is extracted via heuristics)
2. Generate review CSV and edit cargo values as needed
3. Apply corrections: `python src/apply_review.py --csv <csv_file> --apply`
4. Update whitelists: `python src/update_whitelist.py --apply`
5. On next extraction run, the extractor automatically validates cargo against whitelists

### Notes

- Threshold for whitelisting: a cargo (or banca) value must appear in **3+ reviewed corrections** to be suggested and added to the whitelist. This threshold can be adjusted with the `--threshold` parameter.
- The whitelist matching is case-insensitive and supports partial matches, so variations like "Professor", "PROFESSOR", "professor da carreira..." all normalize to the same canonical form from the whitelist.

---

## Date: February 20, 2026 (cronograma extraction fixes & whitelist improvements)

### Critical Fixes

**Problem: Cronograma extraction returning all null values**

Despite implementing a production-grade cronograma parser in the previous session, extraction was failing silently in the full pipeline while working perfectly in isolated tests.

**Root Cause:** 
- Import statement in `src/extractor.py` was using relative import (`from .cronograma_parser import CronogramaParser`)
- This failed silently when running as a script, setting `CronogramaParser = None`
- The code fell back to broken regex patterns without any warning

**Solution:**
- Added fallback import logic to try both relative and absolute imports
- Now works in both package mode and standalone script mode
- Added debug logging to track which extraction method is being used

### Cronograma Parser Enhancements

**1. Section-based extraction optimization**
- Parser now tries to isolate the CRONOGRAMA section first (faster, more accurate)
- Falls back to full PDF scan if section not found or yields < 3 events
- Searches for keywords: "CRONOGRAMA", "DATAS IMPORTANTES" (case-insensitive)
- Reduces false positives by narrowing search scope

**2. Improved date range support**
- Enhanced normalization to handle "Entre DD/MM/YYYY a DD/MM/YYYY" patterns
- Added case-insensitive regex flag to match both "a" and "A" in ranges
- Table format normalization restructures dates appearing before labels

**3. Production pipeline validation**
All 4 cronograma fields now extracting correctly:
- `inscricao_inicio` / `inscricao_fim` - registration period
- `isencao_inicio` - fee exemption start
- `data_prova` - exam date (prefers ranges over single dates)

### Whitelist System Improvements

**Problem: Whitelist only normalizing, not helping extraction**

The whitelist files were only used to normalize already-extracted values, not to improve extraction when primary patterns failed.

**Solution: Two-stage whitelist usage**

**Stage 1 - Validation/Normalization:**
- If cargo/banca extracted via regex → check against whitelist → normalize to canonical form

**Stage 2 - Fallback Extraction (NEW):**
- If NO cargo found by primary patterns → search PDF for any whitelisted cargo
- Enables learning: corrections today improve extraction tomorrow
- Same logic applied to banca extraction

**Implementation:**
- Cargo: searches first 3000 chars of PDF for whitelisted items
- Banca: merges whitelist with hardcoded list, all case-insensitive

### Bug Fixes

**1. Case-sensitivity bugs**
- Fixed cargo whitelist matching to use `.upper()` on both sides
- Fixed banca whitelist matching to use `.upper()` on both sides
- Now resilient to any case variation: "PROFESSOR", "Professor", "professor" all match

**2. update_whitelist.py threshold ignored**
- `--threshold` parameter was being passed but ignored
- Line 47 had hardcoded `>= 3` instead of using the threshold variable
- Fixed: threshold now properly applied throughout the function
- Added threshold value to "no candidates" message for clarity

### User Experience Improvements

**Enhanced scraping output**
- Now displays ALL found concursos with numbered list
- Shows date range being searched
- Displays which keywords are being used for filtering ("abertura", "inicio", "iniciado")
- More organized output format with clear separators

### Testing & Validation

**Full pipeline test:**
```
Direct CronogramaParser: 4/4 fields ✅
extract_cronograma function: 4/4 fields ✅
Full pipeline: 4/4 fields ✅
```

**Extracted values from test PDF:**
```json
{
  "inscricao_inicio": "2026-02-20",
  "inscricao_fim": "2026-03-22",
  "isencao_inicio": "2026-02-20",
  "data_prova": "2026-05-04"
}
```

### Impact

The system now has a **self-improving extraction pipeline**:

1. Extract editais (with fallback to whitelists)
2. Review and correct in CSV
3. Apply corrections (`apply_review.py --apply`)
4. Update whitelists (`update_whitelist.py --threshold 1 --apply`)
5. Future extractions automatically benefit from past corrections

This creates a learning loop where manual corrections progressively reduce the need for future manual intervention.

### Files Modified

- `src/extractor.py` - Import fix, whitelist fallback extraction, case-insensitive matching
- `src/cronograma_parser.py` - Section-based optimization, improved normalization
- `src/update_whitelist.py` - Fixed threshold parameter bug
- `src/main.py` - Enhanced output display
- `data/cargos_whitelist.json` - Auto-populated with "Professor"
- `data/bancas_whitelist.json` - Ready for use

---

````

