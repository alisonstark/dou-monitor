# Changes Summary

## Date: February 20, 2026

### 1. Enhanced Cronograma Parser - Multi-Format Support

**Problem:** The parser struggled with different edital formats from various agencies. Some use "Das etapas do processo seletivo", others "Cronograma", with varying column layouts and date presentations.

**Solution:** Implemented dual-strategy extraction:
- **Strategy 1 (Keyword-based):** Searches for keywords ("inscrição", "isenção", "prova") and looks forward for dates
- **Strategy 2 (Context-based):** Finds dates and looks backward for context (original approach)  
- **Confidence ranking:** Prioritizes events where keyword appears explicitly in context
- **Improved normalization:** Handles tables where activity and date appear on separate lines

**Results:**
- Petrobras 2017: Now returns both inscrição and prova dates (previously nothing)
- Banco do Brasil 2021: Correctly identifies prova dates (previously only generic context)
- Maintains backward compatibility with existing working editais

**Files Modified:**
- `src/extraction/cronograma_parser.py`: Enhanced extraction strategies

### 2. Project Restructuring - Improved Separation of Concerns

**Problem:** All modules in flat `src/` directory made it harder to understand responsibilities.

**Solution:** Reorganized into focused packages:
```
src/
├── extraction/        # PDF scraping, parsing, date extraction
├── processing/        # Applying reviews, updating whitelists
├── export/           # Output generation (PDFs, JSON)
└── cli/              # Command-line user interfaces
```

**Benefits:**
- Clear separation of responsibilities
- Easier to find and modify related functionality
- Better testability (each package independently)
- More scalable for future features

**Files Reorganized:**
- `extraction/`: scraper.py, extractor.py, cronograma_parser.py
- `processing/`: apply_review.py, update_whitelist.py
- `export/`: pdf_export.py
- `cli/`: review_cli.py

**All imports updated:** main.py and all cross-module imports verified working

### 3. Documentation Updates

- Updated README.md with multi-format capabilities info
- Added project architecture diagram showing new package structure
- Documented dual extraction strategies in cronograma parser section

---

## Date: February 19, 2026 (Summary of Previous Session)

### Major Additions

1. **PDF → JSON Extraction Pipeline** (`src/extraction/extractor.py`)
   - Structured field extraction: metadata, cronograma, vagas, financeiro
   - Uses pdfplumber for PDF parsing
   - Heuristics-based extraction with fallback normalization

2. **Human-in-the-Loop Review System**
   - `src/cli/review_cli.py`: Generate review CSVs with confidence scores
   - `src/processing/apply_review.py`: Apply corrections back to JSON summaries with backups

3. **Self-Improving Whitelist System** (`src/processing/update_whitelist.py`)
   - Learns from manual corrections
   - Two-stage usage: validation (normalize) + fallback extraction (improve)
   - Maintains separate whitelists for bancas and cargos

4. **Production Cronograma Parser** (`src/extraction/cronograma_parser.py`)
   - Section-based extraction optimization
   - Semantic date extraction with text normalization
   - Handles various PDF formats and table layouts

---

## Date: February 18, 2026 (Initial Session)

### Problems Fixed

1. **Connection Error:** Added realistic browser headers to bypass bot detection
2. **Search Results Parsing:** Switched from HTML link parsing to embedded JSON parsing
3. **PDF Quality:** Replaced manual PDF generation with Playwright-based printing

### Initial Features

- DOU scraping with retry logic and timeout handling
- Keyword filtering (abertura, inicio, iniciado)
- Preview mode and PDF export via Playwright
- Organized output with clear separators

