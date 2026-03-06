import json
from datetime import datetime
from math import ceil
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _safe_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_dashboard_config(config_path: Path) -> Dict[str, Any]:
    default_config = {
        "filters": {
            "keywords": ["abertura", "inicio", "iniciado"],
            "default_days": 7,
        },
        "notifications": {
            "threshold": 1,
            "email_to": "",
            "webhook_url": "",
            "desktop_enabled": True,
        },
    }

    if not config_path.exists():
        return default_config

    try:
        with config_path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            return default_config

        filters_cfg = loaded.get("filters", {})
        notif_cfg = loaded.get("notifications", {})
        default_config["filters"]["keywords"] = [
            _safe_text(x) for x in filters_cfg.get("keywords", default_config["filters"]["keywords"]) if _safe_text(x)
        ]
        default_config["filters"]["default_days"] = _safe_int(
            filters_cfg.get("default_days", default_config["filters"]["default_days"]), 7
        )

        default_config["notifications"]["threshold"] = _safe_int(
            notif_cfg.get("threshold", default_config["notifications"]["threshold"]), 1
        )
        default_config["notifications"]["email_to"] = _safe_text(
            notif_cfg.get("email_to", default_config["notifications"]["email_to"])
        )
        default_config["notifications"]["webhook_url"] = _safe_text(
            notif_cfg.get("webhook_url", default_config["notifications"]["webhook_url"])
        )
        default_config["notifications"]["desktop_enabled"] = bool(
            notif_cfg.get("desktop_enabled", default_config["notifications"]["desktop_enabled"])
        )
    except Exception:
        return default_config

    return default_config


def save_dashboard_config(config_path: Path, config: Dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_summaries(summaries_dir: Path) -> List[Dict[str, Any]]:
    if not summaries_dir.exists():
        return []

    records: List[Dict[str, Any]] = []
    for file_path in sorted(summaries_dir.glob("*.json")):
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            metadata = data.get("metadata", {})
            banca_obj = metadata.get("banca") if isinstance(metadata.get("banca"), dict) else {}
            cronograma = data.get("cronograma", {})
            vagas = data.get("vagas", {})
            financeiro = data.get("financeiro", {})

            records.append(
                {
                    "id": file_path.stem,
                    "file_name": file_path.name,
                    "pdf_filename": f"{file_path.stem}.pdf",
                    "orgao": _safe_text(metadata.get("orgao")),
                    "edital_numero": _safe_text(metadata.get("edital_numero")),
                    "cargo": _safe_text(metadata.get("cargo")),
                    "banca": _safe_text(banca_obj.get("nome")),
                    "inscricao_inicio": _safe_text(cronograma.get("inscricao_inicio")),
                    "inscricao_fim": _safe_text(cronograma.get("inscricao_fim")),
                    "data_prova": _safe_text(cronograma.get("data_prova")),
                    "vagas_total": vagas.get("total"),
                    "taxa_inscricao": _safe_text(financeiro.get("taxa_inscricao")),
                }
            )
        except Exception:
            continue

    return records


def categorize_concursos(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Categorize concursos into 'abertura' (opening) and 'outros' (others).
    
    Abertura: contains keywords like 'abertura', 'inicio', 'iniciado' in filename or title
    Outros: other concursos/editais that don't match abertura keywords
    """
    import unicodedata
    
    def _normalize(text: str) -> str:
        """Remove accents and convert to lowercase"""
        return "".join(
            c for c in unicodedata.normalize("NFKD", text)
            if not unicodedata.combining(c)
        ).lower()
    
    abertura_keywords = ["abertura", "inicio", "iniciado"]
    
    abertura = []
    outros = []
    
    for rec in records:
        # Check in filename and orgao field (which often contains the title)
        text_to_check = f"{rec.get('file_name', '')} {rec.get('orgao', '')}"
        normalized = _normalize(text_to_check)
        
        if any(keyword in normalized for keyword in abertura_keywords):
            abertura.append(rec)
        else:
            outros.append(rec)
    
    return {
        "abertura": abertura,
        "outros": outros,
    }


def _contains(value: str, expected: str) -> bool:
    return expected.lower() in value.lower()


def _in_date_range(date_text: str, date_from: str, date_to: str) -> bool:
    if not date_text:
        return False
    try:
        current = datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        return False

    if date_from:
        try:
            if current < datetime.strptime(date_from, "%Y-%m-%d").date():
                return False
        except ValueError:
            return False

    if date_to:
        try:
            if current > datetime.strptime(date_to, "%Y-%m-%d").date():
                return False
        except ValueError:
            return False

    return True


def filter_summaries(records: List[Dict[str, Any]], filters: Dict[str, str]) -> List[Dict[str, Any]]:
    q = _safe_text(filters.get("q"))
    orgao = _safe_text(filters.get("orgao"))
    cargo = _safe_text(filters.get("cargo"))
    banca = _safe_text(filters.get("banca"))
    date_from = _safe_text(filters.get("date_from"))
    date_to = _safe_text(filters.get("date_to"))

    filtered: List[Dict[str, Any]] = []
    for rec in records:
        if orgao and not _contains(rec.get("orgao", ""), orgao):
            continue
        if cargo and not _contains(rec.get("cargo", ""), cargo):
            continue
        if banca and not _contains(rec.get("banca", ""), banca):
            continue
        if q:
            hay = " ".join(
                [
                    _safe_text(rec.get("orgao")),
                    _safe_text(rec.get("edital_numero")),
                    _safe_text(rec.get("cargo")),
                    _safe_text(rec.get("banca")),
                ]
            )
            if not _contains(hay, q):
                continue

        if (date_from or date_to) and not _in_date_range(rec.get("data_prova", ""), date_from, date_to):
            continue

        filtered.append(rec)

    return filtered


def summarize_metrics(records: List[Dict[str, Any]]) -> Dict[str, int]:
    total = len(records)
    with_prova = sum(1 for rec in records if rec.get("data_prova"))
    with_banca = sum(1 for rec in records if rec.get("banca"))
    with_vagas = sum(1 for rec in records if isinstance(rec.get("vagas_total"), int))
    return {
        "total": total,
        "with_prova": with_prova,
        "with_banca": with_banca,
        "with_vagas": with_vagas,
    }


def sort_summaries(records: List[Dict[str, Any]], sort_by: str, sort_dir: str) -> List[Dict[str, Any]]:
    allowed = {
        "orgao",
        "cargo",
        "banca",
        "edital_numero",
        "data_prova",
        "vagas_total",
    }
    key_name = sort_by if sort_by in allowed else "data_prova"
    reverse = sort_dir.lower() == "desc"

    present: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []
    for rec in records:
        value = rec.get(key_name)
        if key_name == "vagas_total":
            if isinstance(value, int):
                present.append(rec)
            else:
                missing.append(rec)
            continue

        if _safe_text(value):
            present.append(rec)
        else:
            missing.append(rec)

    def _sort_key(rec: Dict[str, Any]) -> Any:
        value = rec.get(key_name)
        if key_name == "vagas_total":
            return int(value)
        return _safe_text(value).lower()

    ordered = sorted(present, key=_sort_key, reverse=reverse)
    return ordered + missing


def paginate_summaries(records: List[Dict[str, Any]], page: int, page_size: int) -> Tuple[List[Dict[str, Any]], Dict[str, int | bool]]:
    safe_page_size = max(1, page_size)
    total = len(records)
    total_pages = max(1, ceil(total / safe_page_size))
    current_page = min(max(1, page), total_pages)

    start = (current_page - 1) * safe_page_size
    end = start + safe_page_size
    items = records[start:end]

    meta: Dict[str, int | bool] = {
        "total": total,
        "total_pages": total_pages,
        "page": current_page,
        "page_size": safe_page_size,
        "has_prev": current_page > 1,
        "has_next": current_page < total_pages,
    }
    return items, meta


def run_manual_monitoring(project_root: Path, days: int, export_pdf: bool = False) -> Dict[str, Any]:
    """
    Execute monitoring workflow: scrape DOU, filter abertura concursos,
    optionally export PDFs and extract to JSON.
    
    Returns dict with:
        - success: bool
        - total_concursos: int (all concursos found)
        - abertura_concursos: int (filtered by keywords)
        - processed: int (PDFs exported if export_pdf=True)
        - errors: int (export/extraction errors)
        - error_message: str (if success=False)
    """
    try:
        import sys
        import os
        import unicodedata
        from datetime import timedelta
        
        # Add src to path to import extraction modules
        src_path = str(project_root / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        
        from extraction.scraper import scrape_concursos
        from extraction.extractor import save_extraction_json
        
        # Calculate date range
        end_date = datetime.today().strftime('%d-%m-%Y')
        start_date = (datetime.today() - timedelta(days=days)).strftime('%d-%m-%Y')
        
        # Scrape DOU
        concursos = scrape_concursos(start_date, end_date)
        
        # Filter abertura concursos
        keywords = ["abertura", "inicio", "iniciado"]
        
        def _normalize(text: str) -> str:
            return "".join(
                c for c in unicodedata.normalize("NFKD", text)
                if not unicodedata.combining(c)
            ).lower()
        
        abertura_concursos = []
        for concurso in concursos:
            title_norm = _normalize(concurso.get('title', ''))
            if any(keyword in title_norm for keyword in keywords):
                abertura_concursos.append(concurso)
        
        result = {
            "success": True,
            "total_concursos": len(concursos),
            "abertura_concursos": len(abertura_concursos),
            "processed": 0,
            "errors": 0,
            "error_message": "",
        }
        
        # Export PDFs if requested
        if export_pdf and abertura_concursos:
            try:
                from export.pdf_export import save_concurso_pdf
                
                for concurso in abertura_concursos:
                    try:
                        pdf_result = save_concurso_pdf(concurso)
                        if isinstance(pdf_result, str) and pdf_result.startswith("Error"):
                            result["errors"] += 1
                        else:
                            result["processed"] += 1
                            # Attempt extraction
                            try:
                                pdf_path = os.path.join(
                                    str(project_root / "editais"),
                                    f"{concurso['url_title']}.pdf"
                                )
                                save_extraction_json(pdf_path)
                            except Exception:
                                pass  # Extraction errors are not counted as failures
                    except Exception:
                        result["errors"] += 1
            except ImportError:
                result["error_message"] = "PDF export unavailable (Playwright not installed)"
                result["errors"] += 1
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "total_concursos": 0,
            "abertura_concursos": 0,
            "processed": 0,
            "errors": 0,
            "error_message": str(e),
        }
