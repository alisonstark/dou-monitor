import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from extraction.scraper import scrape_concursos, resolve_url_title_by_document_id
from extraction.extractor import save_extraction_json
from utils.dou_url_utils import (
    is_invalid_year_number_slug,
    is_legacy_truncated_slug,
    rebuild_legacy_slug,
)
from utils.normalization import normalize_text
import os


def parse_args():
    parser = argparse.ArgumentParser(description="Doumon - Monitor de concursos DOU")
    parser.add_argument(
        "--export-pdf",
        action="store_true",
        help="Salva os resultados em PDF usando Playwright",
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=7,
        help="Quantidade de dias para busca retroativa (padrão: 7)",
    )
    parser.add_argument(
        "--update-dou-urls",
        action="store_true",
        help="Atualiza configuração de URLs do DOU (base_url, search_url, document_url_pattern)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        help="Nova URL base do DOU (uso com --update-dou-urls)",
    )
    parser.add_argument(
        "--search-url",
        type=str,
        help="Nova URL de busca do DOU (uso com --update-dou-urls)",
    )
    parser.add_argument(
        "--document-url-pattern",
        type=str,
        help="Novo padrão de URL do documento com placeholder {url_title} (uso com --update-dou-urls)",
    )
    parser.add_argument(
        "--search-threshold",
        type=int,
        help="Limiar de alerta para falhas de busca (uso com --update-dou-urls)",
    )
    parser.add_argument(
        "--processing-threshold",
        type=int,
        help="Limiar de alerta para falhas de processamento (uso com --update-dou-urls)",
    )
    parser.add_argument(
        "--pdf-download-threshold",
        type=int,
        help="Limiar de alerta para falhas de download de PDF (uso com --update-dou-urls)",
    )
    parser.add_argument(
        "--backfill-url-titles",
        action="store_true",
        help="Preenche/corrige _source.url_title em data/summaries usando busca por document_id",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra alterações sem gravar arquivos (uso com --backfill-url-titles)",
    )
    parser.add_argument(
        "--backfill-limit",
        type=int,
        default=0,
        help="Número máximo de summaries no backfill (0 = sem limite)",
    )
    return parser.parse_args()


def backfill_url_titles_in_summaries(summaries_dir: Path, dry_run: bool = False, limit: int = 0) -> dict:
    """Resolve and persist missing/legacy _source.url_title for summaries."""

    def _resolve_by_document_id_any_section(document_id: str) -> str | None:
        for do_type in ("do1", "do2", "do3"):
            resolved = resolve_url_title_by_document_id(document_id, do_type=do_type)
            if resolved:
                return resolved
        return None

    stats = {
        "scanned": 0,
        "missing": 0,
        "legacy_truncated": 0,
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

            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

            url_title = (source_meta.get("url_title") or "").strip()
            needs_repair = False
            if not url_title:
                stats["missing"] += 1
                needs_repair = True
            elif is_legacy_truncated_slug(url_title) or is_invalid_year_number_slug(url_title):
                stats["legacy_truncated"] += 1
                needs_repair = True

            if not needs_repair:
                continue
            
            # Strategy 0: Rebuild prefix for known legacy-truncated current url_title.
            resolved_title = None
            resolution_method = None
            edital_numero = str(metadata.get("edital_numero") or "").strip()

            if url_title and is_legacy_truncated_slug(url_title):
                rebuilt = rebuild_legacy_slug(url_title, edital_numero)
                if rebuilt:
                    resolved_title = rebuilt
                    resolution_method = "cli_backfill_legacy_prefix"
                    print(f"HIT  {file_path.name}: reconstruído de url_title legado -> {resolved_title}")

            # Strategy 1: Extract url_title from legacy pdf_filename (remove .pdf extension).
            pdf_filename = (source_meta.get("pdf_filename") or "").strip()
            if not resolved_title and pdf_filename and pdf_filename.endswith(".pdf"):
                candidate_title = pdf_filename[:-4]  # Remove .pdf
                rebuilt_candidate = rebuild_legacy_slug(candidate_title, edital_numero)
                if rebuilt_candidate:
                    resolved_title = rebuilt_candidate
                    resolution_method = "cli_backfill_legacy_prefix_pdf_filename"
                    print(f"HIT  {file_path.name}: reconstruído de pdf_filename legado -> {resolved_title}")
                elif is_invalid_year_number_slug(candidate_title) or is_legacy_truncated_slug(candidate_title):
                    print(f"SKIP {file_path.name}: pdf_filename inválido para uso direto -> {candidate_title}")
                else:
                    resolved_title = candidate_title
                    resolution_method = "cli_backfill_pdf_filename"
                    print(f"HIT  {file_path.name}: extraído de pdf_filename -> {resolved_title}")
            
            # Strategy 2: Query DOU search API by document_id (if Strategy 1 failed or was invalid)
            if not resolved_title:
                document_id = str(source_meta.get("document_id") or "").strip()
                if not document_id:
                    stats["skipped_no_document_id"] += 1
                    print(f"SKIP {file_path.name}: sem document_id válido")
                    continue

                resolved_title = _resolve_by_document_id_any_section(document_id)
                resolution_method = "cli_backfill_document_id"
                
                if not resolved_title:
                    print(f"MISS {file_path.name}: document_id={document_id} sem correspondência no DOU")
                    # Mark as invalid to avoid future download attempts
                    if not dry_run:
                        source_meta["url_title"] = f"__INVALID__{document_id}"
                        source_meta["url_title_error"] = "Document not found in DOU search API"
                        source_meta["url_title_resolved_at"] = datetime.now().isoformat()
                        with file_path.open("w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
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
    errors = 0
    processed = 0

    for concurso in abertura_concursos:
        processed += 1
        # Sempre mostra o título; no modo preview não persiste artefatos.
        print(f"Titulo:  {concurso['title']}")
        if export_pdf:
            try:
                # Import tardio para não exigir Playwright no modo preview.
                from export.pdf_export import save_concurso_pdf
            except Exception as e:
                errors += 1
                print(f"Erro ao importar Playwright/pdf_export: {e}")
                print("Exportacao de PDF indisponivel; instale o Playwright ou execute sem --export-pdf.")
                continue

            try:
                result = save_concurso_pdf(concurso)
                # Verifica se o resultado retornou mensagem de erro.
                if isinstance(result, str) and result.startswith("Error"):
                    errors += 1
                    print(result)
                else:
                    print(result)
                    # Após salvar o PDF, tenta a extração para JSON.
                    try:
                        pdf_path = os.path.join("editais", f"{concurso['url_title']}.pdf")
                        out_json = save_extraction_json(
                            pdf_path,
                            source_url_title=concurso.get("url_title"),
                            source_pdf_filename=f"{concurso['url_title']}.pdf",
                            pdf_persisted=True,
                        )
                        print(f"Extracao salva em {out_json}")
                    except Exception as ex:
                        print(f"Aviso: extracao falhou: {ex}")
            except Exception as e:
                errors += 1
                print(f"Erro ao acessar URL: {e}")
        else:
            # No modo preview, mantém saída mínima (somente título).
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
        print(f"Legacy truncated detected: {stats['legacy_truncated']}")
        print(f"Resolved (all strategies): {stats['resolved']}")
        print(f"Updated files: {stats['updated']}")
        print(f"Skipped (no document_id): {stats['skipped_no_document_id']}")
        print(f"Errors: {stats['errors']}")
        print("-" * 80 + "\n")
        exit(0)
    
    # Atualiza configuração de URLs do DOU quando solicitado.
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

    # Define intervalo: data final hoje e início com base em --days.
    end_date = datetime.today().strftime('%d-%m-%Y')
    start_date = (datetime.today() - timedelta(days=args.days)).strftime('%d-%m-%Y')

    concursos = scrape_concursos(start_date, end_date)

    # Filtra concursos de abertura por palavras-chave.
    abertura_concursos = []
    # Usa normalização sem acentos para robustez com diacríticos.
    keywords = ["abertura", "inicio", "iniciado"]

    for concurso in concursos:
        title_norm = normalize_text(concurso.get('title', ''))
        if any(keyword in title_norm for keyword in keywords):
            abertura_concursos.append(concurso)
    
    print(f"\n{'='*80}")
    print(f"RESULTADO DA COLETA: {start_date} ate {end_date}")
    print(f"{'='*80}")
    print(f"Total de concursos encontrados: {len(concursos)}")
    
    if concursos:
        print(f"\nTodos os concursos:")
        for i, c in enumerate(concursos, 1):
            title = c.get('title', 'N/A')[:100]  # Truncate long titles
            print(f"  {i}. {title}")
    
    print(f"\n{'='*80}")
    print(f"Total de concursos de abertura (palavras-chave: {', '.join(keywords)}): {len(abertura_concursos)}")
    print(f"{'='*80}\n")
    
    if abertura_concursos:
        result = process_abertura_concursos(abertura_concursos, args.export_pdf)
        if result["errors"]:
            print(f"Execucao concluida com {result['errors']} erro(s).")
    else:
        print("Nenhum concurso de abertura encontrado no intervalo informado.")