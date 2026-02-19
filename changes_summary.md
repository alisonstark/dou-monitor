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
