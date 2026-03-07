import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from extraction.scraper import scrape_concursos, resolve_url_title_by_document_id
from extraction.extractor import save_extraction_json
import os
import unicodedata


def parse_args():
    parser = argparse.ArgumentParser(description="Doumon - Monitor de concursos DOU")
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
    parser.add_argument(
        "--update-dou-urls",
        action="store_true",
        help="Update DOU URL configuration (base_url, search_url, document_url_pattern)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        help="New DOU base URL (used with --update-dou-urls)",
    )
    parser.add_argument(
        "--search-url",
        type=str,
        help="New DOU search URL (used with --update-dou-urls)",
    )
    parser.add_argument(
        "--document-url-pattern",
        type=str,
        help="New DOU document URL pattern with {url_title} placeholder (used with --update-dou-urls)",
    )
    parser.add_argument(
        "--search-threshold",
        type=int,
        help="Alert threshold for search failures (used with --update-dou-urls)",
    )
    parser.add_argument(
        "--processing-threshold",
        type=int,
        help="Alert threshold for processing failures (used with --update-dou-urls)",
    )
    parser.add_argument(
        "--pdf-download-threshold",
        type=int,
        help="Alert threshold for PDF download failures (used with --update-dou-urls)",
    )
    parser.add_argument(
        "--backfill-url-titles",
        action="store_true",
        help="Backfill missing _source.url_title in data/summaries using document_id lookup",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files (works with --backfill-url-titles)",
    )
    parser.add_argument(
        "--backfill-limit",
        type=int,
        default=0,
        help="Maximum number of summaries to process in backfill mode (0 = no limit)",
    )
    return parser.parse_args()


def backfill_url_titles_in_summaries(summaries_dir: Path, dry_run: bool = False, limit: int = 0) -> dict:
    """Resolve and persist missing _source.url_title for legacy summaries."""
    stats = {
        "scanned": 0,
        "missing": 0,
        "resolved": 0,
        "updated": 0,
        "skipped_no_document_id": 0,
        "errors": 0,
    }

    if not summaries_dir.exists():
        print(f"Erro: diretório não encontrado: {summaries_dir}")
        return stats

    files = sorted(summaries_dir.glob("*.json"))
    for file_path in files:
        if limit > 0 and stats["scanned"] >= limit:
            break

        stats["scanned"] += 1
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            source_meta = data.get("_source")
            if not isinstance(source_meta, dict):
                continue

            url_title = (source_meta.get("url_title") or "").strip()
            if url_title:
                continue

            stats["missing"] += 1
            
            # Strategy 1: Extract url_title from legacy pdf_filename (remove .pdf extension)
            pdf_filename = (source_meta.get("pdf_filename") or "").strip()
            if pdf_filename and pdf_filename.endswith(".pdf"):
                resolved_title = pdf_filename[:-4]  # Remove .pdf
                resolution_method = "cli_backfill_pdf_filename"
                print(f"HIT  {file_path.name}: extraído de pdf_filename -> {resolved_title}")
            else:
                # Strategy 2: Query DOU search API by document_id
                document_id = str(source_meta.get("document_id") or "").strip()
                if not document_id:
                    stats["skipped_no_document_id"] += 1
                    print(f"SKIP {file_path.name}: sem document_id ou pdf_filename")
                    continue

                resolved_title = resolve_url_title_by_document_id(document_id)
                resolution_method = "cli_backfill_document_id"
                
                if not resolved_title:
                    print(f"MISS {file_path.name}: document_id={document_id} sem correspondência")
                    continue
                    
                print(f"HIT  {file_path.name}: document_id={document_id} -> {resolved_title}")

            stats["resolved"] += 1

            if dry_run:
                continue

            source_meta["url_title"] = resolved_title
            source_meta["url_title_resolved_at"] = datetime.now().isoformat()
            source_meta["url_title_resolved_by"] = resolution_method

            with file_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            stats["updated"] += 1

        except Exception as e:
            stats["errors"] += 1
            print(f"ERR  {file_path.name}: {e}")

    return stats


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
                from export.pdf_export import save_concurso_pdf
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
                        out_json = save_extraction_json(
                            pdf_path,
                            source_url_title=concurso.get("url_title"),
                            source_pdf_filename=f"{concurso['url_title']}.pdf",
                            pdf_persisted=True,
                        )
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

    if args.backfill_url_titles:
        project_root = Path(__file__).resolve().parents[1]
        summaries_dir = project_root / "data" / "summaries"

        print("\n" + "=" * 80)
        print("BACKFILL DE _source.url_title EM SUMMARIES")
        print("=" * 80)
        print(f"Diretório: {summaries_dir}")
        print(f"Modo dry-run: {'SIM' if args.dry_run else 'NAO'}")
        print(f"Limite: {args.backfill_limit if args.backfill_limit > 0 else 'sem limite'}\n")

        stats = backfill_url_titles_in_summaries(
            summaries_dir=summaries_dir,
            dry_run=args.dry_run,
            limit=max(args.backfill_limit, 0),
        )

        print("\n" + "-" * 80)
        print("Resumo")
        print("-" * 80)
        print(f"Scanned: {stats['scanned']}")
        print(f"Missing url_title: {stats['missing']}")
        print(f"Resolved by document_id: {stats['resolved']}")
        print(f"Updated files: {stats['updated']}")
        print(f"Skipped (no document_id): {stats['skipped_no_document_id']}")
        print(f"Errors: {stats['errors']}")
        print("-" * 80 + "\n")
        exit(0)
    
    # Handle DOU URL configuration update if requested
    if args.update_dou_urls:
        from config.dou_urls import get_dou_config
        
        print("\n" + "="*80)
        print("ATUALIZANDO CONFIGURAÇÃO DE URLs DO DOU")
        print("="*80 + "\n")
        
        if not any([
            args.base_url,
            args.search_url,
            args.document_url_pattern,
            args.search_threshold is not None,
            args.processing_threshold is not None,
            args.pdf_download_threshold is not None,
        ]):
            print("Erro: Você deve fornecer pelo menos uma URL ou limiar para atualizar.")
            print("\nUso:")
            print("  --base-url URL               Nova URL base do DOU")
            print("  --search-url URL             Nova URL de busca")
            print("  --document-url-pattern URL   Novo padrão de URL de documentos (use {url_title} como placeholder)")
            print("  --search-threshold N         Limiar de falhas para busca")
            print("  --processing-threshold N     Limiar de falhas para processamento")
            print("  --pdf-download-threshold N   Limiar de falhas para download PDF")
            print("\nExemplo:")
            print('  python src/main.py --update-dou-urls --document-url-pattern "https://www.in.gov.br/web/dou/-/{url_title}"')
            exit(1)

        for value, label in [
            (args.search_threshold, "search-threshold"),
            (args.processing_threshold, "processing-threshold"),
            (args.pdf_download_threshold, "pdf-download-threshold"),
        ]:
            if value is not None and value < 1:
                print(f"Erro: --{label} deve ser >= 1")
                exit(1)
        
        dou_config = get_dou_config()
        success, message = dou_config.update_urls(
            base_url=args.base_url,
            search_url=args.search_url,
            document_url_pattern=args.document_url_pattern,
            updated_by="cli"
        )

        if success:
            success, threshold_message = dou_config.update_alert_thresholds(
                search_threshold=args.search_threshold,
                processing_threshold=args.processing_threshold,
                pdf_download_threshold=args.pdf_download_threshold,
                updated_by="cli",
            )
            if not success:
                message = f"URLs atualizadas, mas houve erro nos limiares: {threshold_message}"
        
        if success:
            print(f"✓ {message}\n")
            print("URLs atualizadas:")
            if args.base_url:
                print(f"  Base URL: {args.base_url}")
            if args.search_url:
                print(f"  Search URL: {args.search_url}")
            if args.document_url_pattern:
                print(f"  Document URL Pattern: {args.document_url_pattern}")
            if args.search_threshold is not None:
                print(f"  Search threshold: {args.search_threshold}")
            if args.processing_threshold is not None:
                print(f"  Processing threshold: {args.processing_threshold}")
            if args.pdf_download_threshold is not None:
                print(f"  PDF download threshold: {args.pdf_download_threshold}")
            print()
        else:
            print(f"✗ Erro: {message}\n")
            exit(1)
        
        exit(0)

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