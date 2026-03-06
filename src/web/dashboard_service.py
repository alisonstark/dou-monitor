import json
import shutil
from datetime import datetime, timedelta
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


def _parse_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        try:
            return int(float(raw.replace(".", "").replace(",", ".")))
        except ValueError:
            return None


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
            file_mtime = file_path.stat().st_mtime
            file_date = datetime.fromtimestamp(file_mtime).date().isoformat()
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            metadata = data.get("metadata", {})
            banca_obj = metadata.get("banca") if isinstance(metadata.get("banca"), dict) else {}
            cronograma = data.get("cronograma", {})
            vagas = data.get("vagas", {})
            financeiro = data.get("financeiro", {})
            review_meta = data.get("_review", {})
            source_meta = data.get("_source", {}) if isinstance(data.get("_source"), dict) else {}
            if "pdf_filename" in source_meta:
                pdf_filename = _safe_text(source_meta.get("pdf_filename"))
            else:
                pdf_filename = f"{file_path.stem}.pdf"

            records.append(
                {
                    "id": file_path.stem,
                    "file_name": file_path.name,
                    "pdf_filename": pdf_filename,
                    "orgao": _safe_text(metadata.get("orgao")),
                    "edital_numero": _safe_text(metadata.get("edital_numero")),
                    "cargo": _safe_text(metadata.get("cargo")),
                    "banca": _safe_text(banca_obj.get("nome")),
                    "inscricao_inicio": _safe_text(cronograma.get("inscricao_inicio")),
                    "inscricao_fim": _safe_text(cronograma.get("inscricao_fim")),
                    "isencao_inicio": _safe_text(cronograma.get("isencao_inicio")),
                    "data_prova": _safe_text(cronograma.get("data_prova")),
                    "vagas_total": vagas.get("total"),
                    "taxa_inscricao": _safe_text(financeiro.get("taxa_inscricao")),
                    "is_reviewed": bool(review_meta.get("last_reviewed")),
                    "reviewer": _safe_text(review_meta.get("reviewer")),
                    "summary_date": file_date,
                    "summary_mtime": file_mtime,
                }
            )
        except Exception:
            continue

    return records


def get_last_update_time(summaries_dir: Path) -> Dict[str, Any]:
    """Get timestamp of most recently modified summary file."""
    if not summaries_dir.exists():
        return {"timestamp": None, "formatted": "Nenhum dado encontrado", "file_count": 0}
    
    json_files = list(summaries_dir.glob("*.json"))
    if not json_files:
        return {"timestamp": None, "formatted": "Nenhum dado encontrado", "file_count": 0}
    
    # Get most recent modification time
    latest_mtime = max(f.stat().st_mtime for f in json_files)
    latest_dt = datetime.fromtimestamp(latest_mtime)
    
    # Calculate time ago
    now = datetime.now()
    delta = now - latest_dt
    
    if delta.days > 0:
        time_ago = f"{delta.days} dia(s) atrás"
    elif delta.seconds >= 3600:
        hours = delta.seconds // 3600
        time_ago = f"{hours} hora(s) atrás"
    elif delta.seconds >= 60:
        minutes = delta.seconds // 60
        time_ago = f"{minutes} minuto(s) atrás"
    else:
        time_ago = "agora mesmo"
    
    formatted_date = latest_dt.strftime("%d/%m/%Y %H:%M")
    
    return {
        "timestamp": latest_mtime,
        "formatted": f"{formatted_date} ({time_ago})",
        "file_count": len(json_files),
        "days_old": delta.days
    }


def categorize_notices(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
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


# Backward-compatible alias during naming migration.
def categorize_concursos(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    return categorize_notices(records)


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
    inscricao_to = _safe_text(filters.get("inscricao_to"))

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

        if inscricao_to:
            inscricao_ref = _safe_text(rec.get("inscricao_fim")) or _safe_text(rec.get("inscricao_inicio"))
            if not _in_date_range(inscricao_ref, "", inscricao_to):
                continue

        filtered.append(rec)

    return filtered


def filter_records_by_cache_window(records: List[Dict[str, Any]], window_days: int) -> List[Dict[str, Any]]:
    """Keep records that were updated in cache within the last N days."""
    safe_window = max(1, int(window_days))
    cutoff_date = (datetime.now().date() - timedelta(days=safe_window - 1))

    filtered: List[Dict[str, Any]] = []
    for rec in records:
        raw_date = _safe_text(rec.get("summary_date"))
        try:
            summary_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if summary_date >= cutoff_date:
            filtered.append(rec)
    return filtered


def get_cache_coverage_info(records: List[Dict[str, Any]], requested_days: int) -> Dict[str, int | bool]:
    """Estimate how many days of cached data are available based on summary file dates."""
    safe_requested = max(1, int(requested_days))
    dates = []
    for rec in records:
        raw_date = _safe_text(rec.get("summary_date"))
        try:
            dates.append(datetime.strptime(raw_date, "%Y-%m-%d").date())
        except ValueError:
            continue

    if not dates:
        return {
            "requested_days": safe_requested,
            "available_days": 0,
            "has_gap": True,
        }

    oldest = min(dates)
    available_days = (datetime.now().date() - oldest).days + 1

    return {
        "requested_days": safe_requested,
        "available_days": max(1, available_days),
        "has_gap": safe_requested > available_days,
    }


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
    Execute monitoring workflow: scrape DOU, categorize concursos,
    extract to JSON for ALL concursos found.
    PDF persistence is optional (export_pdf=True).
    
    Returns dict with:
        - success: bool
        - total_concursos: int (all concursos found)
        - abertura_concursos: int (filtered by abertura/inicio/iniciado keywords)
        - outros_concursos: int (other editais/concursos)
        - processed: int (summaries extracted)
        - saved_pdfs: int (PDFs persisted to editais/)
        - errors: int (export/extraction errors)
        - error_message: str (if success=False)
    """
    try:
        import sys
        import os
        import tempfile
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
            "outros_concursos": len(concursos) - len(abertura_concursos),
            "processed": 0,
            "saved_pdfs": 0,
            "errors": 0,
            "error_message": "",
        }
        
        # Process ALL concursos, not just abertura.
        if concursos:
            try:
                from export.pdf_export import save_concurso_pdf
                
                for concurso in concursos:
                    pdf_path = ""
                    try:
                        if export_pdf:
                            pdf_path = os.path.join(
                                str(project_root / "editais"),
                                f"{concurso['url_title']}.pdf",
                            )
                            pdf_result = save_concurso_pdf(concurso)
                        else:
                            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                                pdf_path = tmp_file.name
                            pdf_result = save_concurso_pdf(concurso, output_path=pdf_path)

                        if isinstance(pdf_result, str) and pdf_result.startswith("Error"):
                            result["errors"] += 1
                        else:
                            if export_pdf:
                                result["saved_pdfs"] += 1
                            # Attempt extraction (summary is always persisted)
                            try:
                                save_extraction_json(
                                    pdf_path,
                                    source_url_title=concurso.get("url_title"),
                                    source_pdf_filename=(f"{concurso['url_title']}.pdf" if export_pdf else None),
                                    pdf_persisted=export_pdf,
                                )
                                result["processed"] += 1
                            except Exception:
                                result["errors"] += 1
                    except Exception:
                        result["errors"] += 1
                    finally:
                        if not export_pdf and pdf_path:
                            try:
                                if os.path.exists(pdf_path):
                                    os.remove(pdf_path)
                            except Exception:
                                pass
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


def get_record_by_file_name(records: List[Dict[str, Any]], file_name: str) -> Dict[str, Any] | None:
    target = _safe_text(file_name)
    if not target:
        return None
    for rec in records:
        if rec.get("file_name") == target:
            return rec
    return None


def apply_manual_review(
    summaries_dir: Path,
    backup_dir: Path,
    reviewed_examples_dir: Path,
    file_name: str,
    updates: Dict[str, Any],
    reviewer: str,
) -> Dict[str, Any]:
    summary_path = summaries_dir / _safe_text(file_name)
    if not summary_path.exists():
        return {
            "success": False,
            "message": f"Arquivo nao encontrado: {file_name}",
            "changed_fields": [],
        }

    try:
        with summary_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {
            "success": False,
            "message": f"Falha ao carregar JSON: {e}",
            "changed_fields": [],
        }

    metadata = data.setdefault("metadata", {})
    vagas = data.setdefault("vagas", {})
    financeiro = data.setdefault("financeiro", {})
    cronograma = data.setdefault("cronograma", {})

    raw_banca = metadata.get("banca")
    if isinstance(raw_banca, dict):
        banca_obj = dict(raw_banca)
    elif _safe_text(raw_banca):
        banca_obj = {"nome": _safe_text(raw_banca)}
    else:
        banca_obj = {}

    desired_values: Dict[str, tuple[Any, Any]] = {
        "metadata.orgao": (metadata.get("orgao"), _safe_text(updates.get("orgao"))),
        "metadata.edital_numero": (metadata.get("edital_numero"), _safe_text(updates.get("edital_numero"))),
        "metadata.cargo": (metadata.get("cargo"), _safe_text(updates.get("cargo"))),
        "metadata.banca": (
            metadata.get("banca"),
            {
                **banca_obj,
                "nome": _safe_text(updates.get("banca")),
                "tipo": "manual",
                "confianca_extracao": 1.0,
            },
        ),
        "vagas.total": (vagas.get("total"), _parse_optional_int(updates.get("vagas_total"))),
        "financeiro.taxa_inscricao": (
            financeiro.get("taxa_inscricao"),
            _safe_text(updates.get("taxa_inscricao")),
        ),
        "cronograma.data_prova": (cronograma.get("data_prova"), _safe_text(updates.get("data_prova"))),
    }

    changes: List[Dict[str, Any]] = []
    for field_path, (old_val, new_val) in desired_values.items():
        if old_val != new_val:
            changes.append({"field": field_path, "old": old_val, "new": new_val})

    if not changes:
        return {
            "success": True,
            "message": "Nenhuma alteracao detectada.",
            "changed_fields": [],
        }

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{summary_path.name}.{timestamp}.bak"

    try:
        shutil.copy2(summary_path, backup_path)

        metadata["orgao"] = desired_values["metadata.orgao"][1]
        metadata["edital_numero"] = desired_values["metadata.edital_numero"][1]
        metadata["cargo"] = desired_values["metadata.cargo"][1]
        metadata["banca"] = desired_values["metadata.banca"][1]
        vagas["total"] = desired_values["vagas.total"][1]
        financeiro["taxa_inscricao"] = desired_values["financeiro.taxa_inscricao"][1]
        cronograma["data_prova"] = desired_values["cronograma.data_prova"][1]

        review_meta = data.get("_review", {})
        review_meta["last_reviewed"] = timestamp
        review_meta["reviewer"] = _safe_text(reviewer) or "dashboard-manual-review"
        review_meta["source"] = "dashboard"
        data["_review"] = review_meta

        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return {
            "success": False,
            "message": f"Falha ao salvar revisao: {e}",
            "changed_fields": [],
        }

    try:
        reviewed_examples_dir.mkdir(parents=True, exist_ok=True)
        example_path = reviewed_examples_dir / f"{summary_path.stem}.{timestamp}.json"
        source_meta = data.get("_source", {}) if isinstance(data.get("_source"), dict) else {}
        if "pdf_filename" in source_meta:
            source_pdf = _safe_text(source_meta.get("pdf_filename"))
        else:
            source_pdf = f"{summary_path.stem}.pdf"
        pdf_path = Path("editais") / source_pdf
        reviewed_payload = {
            "summary_file": summary_path.name,
            "pdf_file": str(pdf_path) if source_pdf and pdf_path.exists() else None,
            "timestamp": timestamp,
            "reviewer": data["_review"]["reviewer"],
            "source": "dashboard",
            "changes": changes,
        }
        with example_path.open("w", encoding="utf-8") as f:
            json.dump(reviewed_payload, f, ensure_ascii=False, indent=2)
    except Exception:
        # Fail-open here: review was already applied and backed up.
        pass

    return {
        "success": True,
        "message": f"Revisao aplicada com {len(changes)} alteracao(oes).",
        "changed_fields": [item["field"] for item in changes],
    }
