import re
import json
import logging
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    import pdfplumber
except Exception:  # pragma: no cover - optional dependency
    pdfplumber = None

try:
    import dateparser
except Exception:  # pragma: no cover - optional dependency
    dateparser = None

# Try relative import first (when used as package), then absolute
CronogramaParser = None
try:
    from .cronograma_parser import CronogramaParser
except ImportError:
    try:
        from cronograma_parser import CronogramaParser
    except ImportError:
        # Fallback se cronograma_parser não estiver disponível
        CronogramaParser = None

logger = logging.getLogger(__name__)


BANCAS_WHITELIST_PATH = Path("data/bancas_whitelist.json")
CARGOS_WHITELIST_PATH = Path("data/cargos_whitelist.json")


def _load_whitelist(whitelist_path: Path) -> List[str]:
    if whitelist_path.exists():
        try:
            with whitelist_path.open(encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [str(x).upper() for x in data]
        except Exception:
            pass
    return []


def _load_bancas_whitelist() -> List[str]:
    whitelist = _load_whitelist(BANCAS_WHITELIST_PATH)
    # fallback default list if no custom whitelist
    if not whitelist:
        return [
            "CEBRASPE",
            "FGV",
            "FUNDAÇÃO GETULIO VARGAS",
            "VUNESP",
            "IBFC",
            "IDECAN",
            "AOCP",
            "QUADRIX",
            "CONSULPLAN",
            "FUNDATEC",
            "IADES",
            "FCC",
            "FUNRIO",
            "CESGRANRIO",
            "CESPE",
        ]
    return whitelist


def _load_cargos_whitelist() -> List[str]:
    return _load_whitelist(CARGOS_WHITELIST_PATH)


def _extract_text_from_pdf(path: str) -> str:
    """Extract text from PDF using pdfplumber (fallback: empty string).

    If pdfplumber is not available or text extraction fails, returns empty string.
    """
    if pdfplumber is None:
        logger.warning("pdfplumber not installed; text extraction unavailable")
        return ""

    try:
        with pdfplumber.open(path) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        return "\n".join(pages)
    except Exception as e:
        logger.exception("Failed to extract text from PDF: %s", e)
        return ""


def _find_first_currency(text: str) -> Optional[str]:
    """Extract first R$ currency amount from text.
    
    Properly handles Brazilian currency format:
    - R$ 100 (whole number)
    - R$ 100,00 (with decimal)
    - R$ 1.000 (with thousands separator)
    - R$ 1.000,00 (thousands + decimal)
    - R$ 1.000.000,50 (multiple thousands)
    
    Returns None if no valid currency found.
    Does NOT capture trailing commas or other punctuation.
    """
    # Pattern: R$ followed by digits with optional thousands separator (dots)
    # and optional decimal part (comma + 2 digits)
    # Note: [0-9]+ allows any number of starting digits to handle cases like "5000"
    match = re.search(r"R\$\s*[0-9]+(?:\.[0-9]{3})*(?:,[0-9]{2})?", text)
    return match.group(0) if match else None


def _parse_date(text: str) -> Optional[str]:
    if not dateparser:
        return None
    dt = dateparser.parse(text, languages=["pt"])  # supports Portuguese
    if dt:
        return dt.date().isoformat()
    return None


def _title_case_pt(text: str) -> str:
    """Convert text to Title Case in Portuguese, respecting prepositions.
    
    Examples:
        "HOMOLOGAÇÃO DO RESULTADO FINAL" → "Homologação do Resultado Final"
        "EXTRAORDINÁRIO" → "Extraordinário"
        "CONCURSO PÚBLICO" → "Concurso Público"
    """
    if not text:
        return ""
    
    # Preposições, conjunções e artigos que ficam em minúsculas (exceto primeira palavra)
    lowercase_words = {'do', 'da', 'dos', 'das', 'de', 'e', 'ou', 'a', 'o', 'um', 'uma', 'por', 'para', 'em', 'no', 'na', 'nos', 'nas'}
    
    words = text.lower().split()
    result = []
    
    for i, word in enumerate(words):
        if i == 0:  # Sempre capitalizar primeira palavra
            result.append(word.capitalize())
        elif word in lowercase_words:
            result.append(word)
        else:
            result.append(word.capitalize())
    
    return ' '.join(result)


def _extract_edital_type(text: str) -> Optional[str]:
    """Extract the type/purpose of edital (e.g., 'Extraordinário', 'Homologação do Resultado Final').
    
    Patterns:
        "EDITAL EXTRAORDINÁRIO Nº 1/2026" → "Extraordinário"
        "RETIFICAÇÃO DO EDITAL Nº 25/2025" → "Retificação"
        "EDITAL DE ABERTURA" → None (generic, not useful)
        "HOMOLOGAÇÃO DO RESULTADO FINAL" → "Homologação do Resultado Final"
    
    Returns the formatted type in Title Case, or None if generic/not found.
    """
    if not text:
        return None
    
    # Strategy 1: Look for specific keywords that identify edital type (highest priority)
    # These pattern keywords that indicate the type
    keyword_patterns = [
        r"RETIFICAÇÃO",
        r"HOMOLOGAÇÃO",
        r"RESULTADO\s+FINAL",
        r"EXTRAORDINÁRIO",
        r"PRORROGAÇÃO",
        r"CONVOCAÇÃO",
        r"CANCELAMENTO",
        r"SUSPENSÃO",
        r"ALTERAÇÃO",
    ]
    
    for keyword_pattern in keyword_patterns:
        match = re.search(keyword_pattern, text, re.IGNORECASE)
        if match:
            found_keyword = match.group(0).strip()
            
            # For HOMOLOGAÇÃO, check if it's followed by "DO RESULTADO FINAL"
            if found_keyword.upper() == "HOMOLOGAÇÃO":
                next_part = text[match.end():match.end() + 100]
                result_match = re.match(r"\s+DO\s+RESULTADO\s+FINAL", next_part, re.IGNORECASE)
                if result_match:
                    return "Homologação do Resultado Final"
                else:
                    return "Homologação"
            else:
                # For other keywords, just return the keyword with Title Case
                return _title_case_pt(found_keyword.lower())
    
    # Strategy 2: Look for pattern "EDITAL [type] Nº"
    # Match: EDITAL EXTRAORDINÁRIO Nº 1/2026
    generic_types = {'de abertura', 'de abertura de', 'de seleção', 'para bolsistas', 'nº', ''}
    
    match = re.search(
        r"EDITAL\s+(?:DE\s+ABERTURA\s+)?([A-ZÀ-Ú][A-ZÀ-Ú\s\-/]*?)\s*(?:N[ºo]\.?|$)",
        text,
        re.IGNORECASE
    )
    if match:
        edital_type = match.group(1).strip()
        if edital_type.lower() not in generic_types:
            return _title_case_pt(edital_type.lower())
    
    return None


def extract_basic_metadata(text: str) -> Dict[str, Any]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    metadata: Dict[str, Any] = {
        "orgao": None,
        "edital_numero": None,
        "cargo": None,
        "banca": None,
        "data_publicacao_dou": None,
    }

    # Try to infer 'orgao' from lines preceding an 'EDITAL' header
    orgao_val = None
    for i, ln in enumerate(lines[:40]):
        if re.search(r"EDITAL", ln, re.I):
            prev_lines = lines[max(0, i - 2) : i]
            orgao_val = " ".join(prev_lines).strip()
            if orgao_val:
                break

    if not orgao_val:
        orgao_match = re.search(
            r"(?:Órgão|Entidade)[:\s\-\n]{1,30}([A-ZÀ-Ú0-9\w\s\-/\.,]+)", text, re.I
        )
        if orgao_match:
            orgao_val = orgao_match.group(1).strip()

    metadata["orgao"] = orgao_val

    # Extract edital type/purpose instead of just number
    # Examples: "Extraordinário", "Homologação do Resultado Final", "Retificação"
    edital_tipo = _extract_edital_type(text)
    metadata["edital_numero"] = edital_tipo  # Store type in edital_numero for backward compatibility

    # cargo: look for explicit 'cargo' label or common wording
    cargo_val = None
    cargo_match = re.search(r"cargo[s]?[:\s\-]{1,80}([\w\s\-\.,/()]+)", text, re.I)
    if cargo_match:
        cargo_val = cargo_match.group(1).strip()
    else:
        m = re.search(
            r"destinado a selecionar candidatos para o cargo de\s*([\w\s\-\.,/()]+)", text, re.I
        )
        if m:
            cargo_val = m.group(1).strip()
        else:
            for i, ln in enumerate(lines[:20]):
                if re.search(r"EDITAL", ln, re.I):
                    nxt = " ".join(lines[i : i + 6])
                    mm = re.search(r"PROVIMENTO DE\s+([A-Z\w\s\-/,()]+)", nxt, re.I)
                    if mm:
                        cargo_val = mm.group(1).strip()
                    break

    # Load cargo whitelist (used for both validation and fallback extraction)
    cargos_whitelist = _load_cargos_whitelist()
    
    # Validate/normalize cargo against whitelist if extracted
    if cargo_val and cargos_whitelist:
        cargo_upper = cargo_val.upper()
        # Check if extracted cargo matches any whitelisted cargo
        for whitelisted_cargo in cargos_whitelist:
            if whitelisted_cargo in cargo_upper or cargo_upper in whitelisted_cargo:
                # Use the whitelisted version (to normalize variations)
                cargo_val = whitelisted_cargo.title()
                break
    
    # Fallback: If no cargo found, search for whitelisted cargos in text
    if not cargo_val and cargos_whitelist:
        text_upper = text.upper()
        # Search for whitelisted cargos in the first 3000 chars
        search_text = text_upper[:3000]
        for whitelisted_cargo in cargos_whitelist:
            if whitelisted_cargo.upper() in search_text:
                # Found a whitelisted cargo in the text
                cargo_val = whitelisted_cargo.title()
                logger.debug(f"Cargo found via whitelist fallback: {cargo_val}")
                break

    metadata["cargo"] = cargo_val

    # Banca: layered strategy (known list, keyword patterns, negative heuristics)
    def extract_banca_struct(txt: str) -> Dict[str, Any]:
        # Load bancas from whitelist (dynamic) and merge with hardcoded list
        bancas_whitelist = _load_bancas_whitelist()
        
        BANCAS_CONHECIDAS = [
            "CEBRASPE",
            "FGV",
            "FUNDAÇÃO GETULIO VARGAS",
            "FUNDAO GETULIO VARGAS",
            "VUNESP",
            "IBFC",
            "IDECAN",
            "AOCP",
            "QUADRIX",
            "CONSULPLAN",
            "FUNDATEC",
            "IADES",
            "FCC",
            "FUNRIO",
            "CESGRANRIO",
            "CESPE",
        ]
        
        # Merge whitelist with hardcoded list (deduplicate)
        all_bancas = list(set(BANCAS_CONHECIDAS + bancas_whitelist))

        up = txt.upper()

        for banca in all_bancas:
            if banca.upper() in up:
                return {"nome": banca, "tipo": "externa", "confianca_extracao": 0.98}

        label_re = re.search(
            r"(organizad[oa]r|executad[oa]r|realizad[oa]r|sob responsabilidade|contratada).{0,60}por\s+([A-ZÀ-Ú][\w\s\-\.,/()]+)",
            txt,
            re.I,
        )
        if label_re:
            candidate = label_re.group(2).strip()
            if re.search(r"UNIVERSIDADE|UNIVERSITÁRIO|COMISSÃO|PRÓ-?REITOR|PRÓ-REITOR|COMISSÃO EXAMINADORA|COMISSAO", candidate, re.I):
                return {"nome": candidate, "tipo": "execucao_propria", "confianca_extracao": 0.8}
            if re.search(r"FUNDAÇÃO|FUNDACAO|INSTITUTO|FUNDAÇÃO|FUNDAO", candidate, re.I):
                return {"nome": candidate, "tipo": "fundacao", "confianca_extracao": 0.9}
            return {"nome": candidate, "tipo": "externa", "confianca_extracao": 0.6}

        m = re.search(r"(FUNDAÇÃO|FUNDACAO|INSTITUTO)\s+[A-ZÀ-Ú0-9\w\s\-]+", up)
        if m:
            candidate = m.group(0).strip().title()
            return {"nome": candidate, "tipo": "fundacao", "confianca_extracao": 0.75}

        if re.search(r"COMISSÃO EXAMINADORA|COMISSAO EXAMINADORA|COMISSÃO DESIGNADA|COMISSAO DESIGNADA|EXECUTADO PELA PRÓ-?REITORIA|EXECUTADO PELA PROGP", txt, re.I):
            inst = None
            for ln in lines[:10]:
                if re.search(r"UNIVERSIDADE|FUNDAÇÃO|INSTITUTO|MINISTÉRIO|MINISTERIO", ln, re.I):
                    inst = ln
                    break
            return {"nome": inst or "Instituição organizadora", "tipo": "execucao_propria", "confianca_extracao": 0.85}

        return {"nome": None, "tipo": None, "confianca_extracao": 0.0}

    metadata["banca"] = extract_banca_struct(text)

    pub_match = re.search(r"Publicado(?: em)?[:\s\-]{0,10}([0-9]{1,2}\s+de\s+\w+\s+de\s+[0-9]{4})", text, re.I)
    if pub_match:
        metadata["data_publicacao_dou"] = _parse_date(pub_match.group(1))

    return metadata





def extract_cronograma(text: str, pdf_path: str = None) -> Dict[str, Optional[str]]:
    """Extract 3 essential cronograma dates:
    - inscricao_inicio, inscricao_fim (registration period)
    - isencao_inicio (exemption request deadline)
    - data_prova (exam date)
    
    Strategy:
    1. ETAPA 1: Enhanced data-driven regex using CronogramaParser
    2. ETAPA 2: Fallback to basic regex patterns
    """
    cronograma = {
        "inscricao_inicio": None,
        "inscricao_fim": None,
        "isencao_inicio": None,
        "data_prova": None,
    }
    
    # ETAPA 1: Use CronogramaParser to extract from text
    if CronogramaParser:
        logger.debug("ETAPA 1: Using CronogramaParser for enhanced date extraction")
        try:
            parser = CronogramaParser()
            result = parser.extract_from_text(text)
            
            logger.debug(f"CronogramaParser returned: {result}")
            
            if result:
                # Copy only the 4 essential fields
                for field in cronograma.keys():
                    if result.get(field):
                        cronograma[field] = result[field]
                
                populated = sum(1 for v in cronograma.values() if v)
                logger.debug(f"ETAPA 1 result: {populated}/{len(cronograma)} fields populated")
                logger.debug(f"Final cronograma: {cronograma}")
                
                if populated > 0:
                    return cronograma
        except Exception as e:
            logger.debug(f"ETAPA 1 failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    # ETAPA 2: Fallback to specific regex patterns
    logger.debug("ETAPA 2: Fallback regex patterns")
    
    # Find cronograma section to reduce noise
    cronograma_section = text
    cronograma_match = re.search(
        r"(CRONOGRAMA|Cronograma|DATAS\s+IMPORTANTES|Datas\s+Importantes)[^a-z]*?([\s\S]{0,8000}?)(?=\n(?:ANEXO|Anexo|$))",
        text, re.I
    )
    if cronograma_match:
        cronograma_section = cronograma_match.group(2)
        logger.debug(f"Found cronograma section ({len(cronograma_section)} chars)")
    
    # Pattern 1: Inscrição (período)
    inscr_patterns = [
        r"Recebimento de Inscrições?\s*[:\-]?\s*(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})\s+(?:a|ate|até)\s+(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})",
        r"Período de Inscrição\s*[:\-]?\s*(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})\s+(?:a|ate|até)\s+(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})",
    ]
    
    for pattern in inscr_patterns:
        inscr_match = re.search(pattern, cronograma_section, re.I)
        if inscr_match:
            try:
                start_iso = _parse_date(f"{inscr_match.group(1)}/{inscr_match.group(2)}/{inscr_match.group(3)}")
                end_iso = _parse_date(f"{inscr_match.group(4)}/{inscr_match.group(5)}/{inscr_match.group(6)}")
                if start_iso:
                    cronograma["inscricao_inicio"] = start_iso
                if end_iso:
                    cronograma["inscricao_fim"] = end_iso
                break
            except Exception:
                pass
    
    # Pattern 2: Isenção (período de solicitação)
    isencao_patterns = [
        r"Período de solicitação de isenção?\s*[:\-]?\s*(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})",
        r"Solicitação de isenção?\s*[:\-]?\s*(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})",
    ]
    
    for pattern in isencao_patterns:
        isencao_match = re.search(pattern, cronograma_section, re.I)
        if isencao_match:
            try:
                iso = _parse_date(f"{isencao_match.group(1)}/{isencao_match.group(2)}/{isencao_match.group(3)}")
                if iso:
                    cronograma["isencao_inicio"] = iso
                break
            except Exception:
                pass
    
    # Pattern 3: Provas
    prova_patterns = [
        r"Data provável (?:das|da) provas?\s*[:\-]?\s*(?:Entre\s+)?(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})",
        r"Data (?:das|da) provas?\s*[:\-]?\s*(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})",
        r"Realização (?:das|da) provas?\s*[:\-]?\s*(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})",
    ]
    
    for pattern in prova_patterns:
        prova_match = re.search(pattern, cronograma_section, re.I)
        if prova_match:
            try:
                iso = _parse_date(f"{prova_match.group(1)}/{prova_match.group(2)}/{prova_match.group(3)}")
                if iso:
                    cronograma["data_prova"] = iso
                break
            except Exception:
                pass
    
    populated = sum(1 for v in cronograma.values() if v)
    logger.debug(f"ETAPA 2 result: {populated}/{len(cronograma)} fields populated")
    return cronograma



def extract_vagas(text: str) -> Dict[str, Optional[int]]:
    vagas = {
        "total": None,
        "ampla_concorrencia": None,
        "pcd": None,
        "ppiq": None,
    }

    # try patterns
    total_match = re.search(r"(?:Total de vagas|Vagas totais|Vagas)[:\s\-]{0,10}([0-9]+)", text, re.I)
    if total_match:
        vagas["total"] = int(total_match.group(1))
    else:
        # fallback: first occurrence of 'Vagas' with number nearby
        m = re.search(r"Vagas?[^\d]{0,10}([0-9]{1,4})", text, re.I)
        if m:
            vagas["total"] = int(m.group(1))

    pcd_match = re.search(r"PCD[:\s\-]{0,10}([0-9]+)", text, re.I)
    if pcd_match:
        pcd_val = int(pcd_match.group(1))
        vagas["pcd"] = pcd_val

    # PPI / PPIQ patterns (various spellings)
    ppiq_match = re.search(r"PPIQ|PPI|Pretos\s+Pardos|Indígenas", text, re.I)
    if ppiq_match:
        # try to get number near the keyword
        nearby = text[ppiq_match.start():ppiq_match.start()+60]
        nm = re.search(r"([0-9]{1,3})", nearby)
        if nm:
            vagas["ppiq"] = int(nm.group(1))

    # Basic consistency checks
    try:
        if vagas["total"] is not None and vagas.get("pcd") is not None:
            if vagas["pcd"] > vagas["total"]:
                # likely mis-extraction; discard pcd value
                vagas["pcd"] = None
    except Exception:
        pass

    return vagas


def extract_financeiro(text: str) -> Dict[str, Optional[Any]]:
    financeiro = {
        "taxa_inscricao": None,
        "remuneracao_inicial": None,
    }

    taxa = _find_first_currency(text)
    if taxa:
        financeiro["taxa_inscricao"] = taxa

    # remuneration: look for 'Remuneração' or 'Vencimento' near currency
    rem_match = re.search(r"(Remunera[cç][aã]o|Remuneraçao|Remuneração inicial|Vencimento)[:\s\-]{0,30}([Rr]\$\s*[0-9\.,]+)", text, re.I)
    if rem_match:
        financeiro["remuneracao_inicial"] = rem_match.group(2)
    else:
        # fallback: any currency that appears after words like 'remunera' in a larger window
        rem_kw = re.search(r"remuner|vencim|sal[aá]rio", text, re.I)
        if rem_kw:
            window = text[rem_kw.start():rem_kw.start()+200]
            m = re.search(r"R\$\s*[0-9\.,]+", window)
            if m:
                financeiro["remuneracao_inicial"] = m.group(0)

    return financeiro


def extract_from_pdf(path: str) -> Dict[str, Any]:
    """Main entry point: given a PDF path, return a normalized JSON-like dict with extracted fields.

    The function is intentionally conservative: it returns None for fields not found.
    """
    text = _extract_text_from_pdf(path)

    if not text:
        logger.warning("No text extracted from PDF %s", path)

    metadata = extract_basic_metadata(text)
    cronograma = extract_cronograma(text, pdf_path=path)
    vagas = extract_vagas(text)
    financeiro = extract_financeiro(text)

    out = {
        "metadata": metadata,
        "vagas": vagas,
        "financeiro": financeiro,
        "cronograma": cronograma,
    }

    return out


def _extract_document_id(value: str) -> str:
    if not value:
        return ""
    match = re.search(r"(\d{6,})$", value)
    return match.group(1) if match else ""


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    no_accents = "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )
    return re.sub(r"\s+", " ", no_accents)


def _identity_key_from_payload(payload: Dict[str, Any]) -> str:
    metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
    key_parts = [
        _normalize_text(metadata.get("orgao")),
        _normalize_text(metadata.get("edital_numero")),
        _normalize_text(metadata.get("cargo")),
    ]
    # Only use identity key if we have minimally meaningful data.
    if sum(1 for part in key_parts if part) < 2:
        return ""
    return "|".join(key_parts)


def _identity_key_from_file(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return _identity_key_from_payload(payload)
    except Exception:
        return ""
    return ""


def save_extraction_json(
    path_pdf: str,
    out_dir: str = "data/summaries",
    source_url_title: str | None = None,
    source_pdf_filename: str | None = None,
    pdf_persisted: bool = True,
) -> str:
    import os

    os.makedirs(out_dir, exist_ok=True)
    data = extract_from_pdf(path_pdf)
    base = os.path.splitext(os.path.basename(path_pdf))[0]
    source_title = (source_url_title or base).strip()
    document_id = _extract_document_id(source_title)

    # Canonical naming:
    # - preferred: dou-<numeric-id>.json (stable regardless of title slug changes)
    # - fallback: keep original base when no numeric suffix is available
    canonical_stem = f"dou-{document_id}" if document_id else base
    out_path = Path(out_dir) / f"{canonical_stem}.json"

    source_block = data.get("_source", {}) if isinstance(data.get("_source"), dict) else {}
    pdf_name = source_pdf_filename if source_pdf_filename is not None else (
        os.path.basename(path_pdf) if pdf_persisted else None
    )

    source_block.update(
        {
            "pdf_filename": pdf_name,
            "pdf_persisted": bool(pdf_persisted),
            "url_title": source_title,
            "document_id": document_id or None,
            "canonical_summary": out_path.name,
            "extracted_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    data["_source"] = source_block

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Smart cleanup: remove older/alternate files for the same document.
    current_identity = _identity_key_from_payload(data)
    for candidate in Path(out_dir).glob("*.json"):
        if candidate.resolve() == out_path.resolve():
            continue

        should_remove = False
        candidate_doc_id = _extract_document_id(candidate.stem)
        if document_id and candidate_doc_id == document_id:
            should_remove = True
        elif current_identity:
            if _identity_key_from_file(candidate) == current_identity:
                should_remove = True

        if should_remove:
            try:
                candidate.unlink()
            except Exception:
                # Fail-open: keep extraction successful even if cleanup fails.
                pass

    return str(out_path)
