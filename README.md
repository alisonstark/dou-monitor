# DOU-monitor

## Goal
Monitor DOU (Diario Oficial da Uniao) publications for concurso-related results, with fast preview and optional PDF export.

## Capabilities
- Scrapes DOU search results using the site embedded JSON data
- Handles connection retries and timeouts
- Filters results by keywords (abertura, inicio, iniciado)
- Preview mode prints the first 10 lines per result
- PDF export uses the site print layout for high fidelity output
- PDF export reuses a browser context with realistic locale and timezone

## How to Run
- Install dependencies and Playwright browsers
- Run the main script from the project root
- Use the export flag to save PDFs, or omit it for preview mode

## Output
- Console summary with counts and result metadata
- Optional PDFs saved under the editais folder
