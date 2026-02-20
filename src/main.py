import argparse
from datetime import datetime, timedelta

from scraper import scrape_concursos
from extractor import save_extraction_json
import os
import unicodedata


def parse_args():
    parser = argparse.ArgumentParser(description="Monitor DOU concursos")
    parser.add_argument(
        "--export-pdf",
        action="store_true",
        help="Save results as PDFs using Playwright",
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)",
    )
    return parser.parse_args()


def process_abertura_concursos(abertura_concursos, export_pdf):
    preview_header_printed = False
    errors = 0
    processed = 0

    for concurso in abertura_concursos:
        processed += 1
        # Always show the title; in preview mode we only display the title
        print(f"Title:   {concurso['title']}")
        if export_pdf:
            try:
                # Import lazily so preview mode doesn't require Playwright to be installed
                from pdf_export import save_concurso_pdf
            except Exception as e:
                errors += 1
                print(f"Error importing Playwright/pdf_export: {e}")
                print("PDF export unavailable; install Playwright or run without --export-pdf.")
                continue

            try:
                result = save_concurso_pdf(concurso)
                # Check if the result is an error message
                if isinstance(result, str) and result.startswith("Error"):
                    errors += 1
                    print(result)
                else:
                    print(result)
                    # after saving the PDF, attempt extraction to JSON
                    try:
                        pdf_path = os.path.join("editais", f"{concurso['url_title']}.pdf")
                        out_json = save_extraction_json(pdf_path)
                        print(f"Extraction saved to {out_json}")
                    except Exception as ex:
                        print(f"Warning: extraction failed: {ex}")
            except Exception as e:
                errors += 1
                print(f"Error accessing URL: {e}")
        else:
            # preview mode: keep output minimal (only title)
            # increment processed count already done; nothing else to fetch here.
            pass
        print(f"{'-'*80}\n")

    return {
        "processed": processed,
        "errors": errors,
        "preview_mode": not export_pdf,
    }

if __name__ == "__main__":

    args = parse_args()

    # Make end_date today's date, and start_date `args.days` before today's date.
    end_date = datetime.today().strftime('%d-%m-%Y')
    start_date = (datetime.today() - timedelta(days=args.days)).strftime('%d-%m-%Y')

    concursos = scrape_concursos(start_date, end_date)

    # From the list of public tenders and competitions found, obtain the ones that contain keywords like "abertura"
    # that indicate the opening of a public tender or competition, and print their titles, dates, and URLs.
    abertura_concursos = []
    # use unaccented keyword matching to be robust to diacritics
    keywords = ["abertura", "inicio", "iniciado"]

    def _normalize(text: str) -> str:
        return "".join(
            c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
        ).lower()

    for concurso in concursos:
        title_norm = _normalize(concurso.get('title', ''))
        if any(keyword in title_norm for keyword in keywords):
            abertura_concursos.append(concurso)
    
    print(f"\n{'='*80}")
    print(f"SCRAPING RESULTS: {start_date} to {end_date}")
    print(f"{'='*80}")
    print(f"Total concursos found: {len(concursos)}")
    
    if concursos:
        print(f"\nAll concursos:")
        for i, c in enumerate(concursos, 1):
            title = c.get('title', 'N/A')[:100]  # Truncate long titles
            print(f"  {i}. {title}")
    
    print(f"\n{'='*80}")
    print(f"Total abertura concursos (keywords: {', '.join(keywords)}): {len(abertura_concursos)}")
    print(f"{'='*80}\n")
    
    # If the abertura_concursos list is not empty, access the URL of each concurso in the abertura_concursos list 
    # and print the first 500 characters of the page content to verify that the page is accessible and contains relevant information about the concurso.

    if abertura_concursos:
        result = process_abertura_concursos(abertura_concursos, args.export_pdf)
        if result["errors"]:
            print(f"Completed with {result['errors']} error(s).")
    else:
        print("No abertura concursos found in the specified date range.")