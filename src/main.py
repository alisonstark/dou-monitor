import argparse
from datetime import datetime, timedelta

from pdf_export import save_concurso_pdf
from scraper import get_concurso_preview_lines, scrape_concursos


def parse_args():
    parser = argparse.ArgumentParser(description="Monitor DOU concursos")
    parser.add_argument(
        "--export-pdf",
        action="store_true",
        help="Save results as PDFs using Playwright",
    )
    return parser.parse_args()


def process_abertura_concursos(abertura_concursos, export_pdf):
    preview_header_printed = False
    errors = 0
    processed = 0

    for concurso in abertura_concursos:
        processed += 1
        print(f"Title:   {concurso['title']}")
        print(f"Date:    {concurso['date']} (Edition {concurso['edition']})")
        print(f"Section: {concurso['section']}")
        print(f"URL:     {concurso['url']}")
        if export_pdf:
            try:
                save_concurso_pdf(concurso)
            except Exception as e:
                errors += 1
                print(f"Error accessing URL: {e}")
        else:
            if not preview_header_printed:
                print(80*"-")
                print("[!] \033[31mPREVIEW MODE\033[0m: use --export-pdf to save results as PDFs.")
                print(80*"-" + "\n")
                preview_header_printed = True
            try:
                preview_lines = get_concurso_preview_lines(concurso, max_lines=10)
                if preview_lines:
                    for line in preview_lines:
                        print(line)
                else:
                    print("No preview content found.")
            except Exception as e:
                errors += 1
                print(f"Error accessing URL: {e}")
        print(f"{'-'*80}\n")

    return {
        "processed": processed,
        "errors": errors,
        "preview_mode": not export_pdf,
    }

if __name__ == "__main__":

    args = parse_args()

    # Make it so that the end_date is today's date, and the start_date is 7 days before today's date.
    
    end_date = datetime.today().strftime('%d-%m-%Y')
    start_date = (datetime.today() - timedelta(days=7)).strftime('%d-%m-%Y')

    concursos = scrape_concursos(start_date, end_date)

    # From the list of public tenders and competitions found, obtain the ones that contain keywords like "abertura"
    # that indicate the opening of a public tender or competition, and print their titles, dates, and URLs.
    abertura_concursos = []
    keywords = ["abertura", "início", "iniciado"]
    
    for concurso in concursos:
        title_lower = concurso['title'].lower()
        if any(keyword in title_lower for keyword in keywords):
            abertura_concursos.append(concurso)
    
    print(f"\n{'='*80}")
    print(f"Total concursos found: {len(concursos)}")
    print(f"Total abertura concursos: {len(abertura_concursos)}")
    print(f"{'='*80}\n")
    
    # If the abertura_concursos list is not empty, access the URL of each concurso in the abertura_concursos list 
    # and print the first 500 characters of the page content to verify that the page is accessible and contains relevant information about the concurso.

    if abertura_concursos:
        result = process_abertura_concursos(abertura_concursos, args.export_pdf)
        if result["errors"]:
            print(f"Completed with {result['errors']} error(s).")
    else:
        print("No abertura concursos found in the specified date range.")