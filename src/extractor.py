import re
import json
import logging
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

logger = logging.getLogger(__name__)


WHITELIST_PATH = Path("data/bancas_whitelist.json")


def _load_whitelist() -> List[str]:
    if WHITELIST_PATH.exists():
        try:
            with WHITELIST_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [str(x).upper() for x in data]
        except Exception:
            pass
    # fallback default list
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
    match = re.search(r"R\$\s*[0-9\.,]+", text)
    return match.group(0) if match else None


def _parse_date(text: str) -> Optional[str]:
    if not dateparser:
        return None
    dt = dateparser.parse(text, languages=["pt"])  # supports Portuguese
    if dt:
        return dt.date().isoformat()
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

    # Try to capture edital number or date-based identifier
    edital_num = None
    edital_match = re.search(
        r"Edital(?: de Abertura)?(?: n(?:º|o|r)\.?\s*)?[:\-\s]*([0-9A-Za-z\-/\.]+)",
        text,
        re.I,
    )
    if edital_match:
        candidate = edital_match.group(1).strip()
        if len(candidate) > 2 and not re.fullmatch(r"DE|DE\b", candidate, re.I):
            edital_num = candidate

    if not edital_num:
        em = re.search(
            r"Edital de Abertura de\s*([0-9]{1,2}\s+de\s+\w+\s+de\s+[0-9]{4})",
            text,
            re.I,
        )
        if em:
            edital_num = em.group(1).strip()

    metadata["edital_numero"] = edital_num

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

    metadata["cargo"] = cargo_val

    # Banca: layered strategy (known list, keyword patterns, negative heuristics)
    def extract_banca_struct(txt: str) -> Dict[str, Any]:
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

        up = txt.upper()

        for banca in BANCAS_CONHECIDAS:
            if banca in up:
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


def extract_cronograma(text: str) -> Dict[str, Optional[str]]:
    """Extract critical dates (inscrição, isenção, data da prova, homologação, recursos).

    Returns a dict with ISO dates where found.
    """
    cronograma = {
        "inscricao_inicio": None,
        "inscricao_fim": None,
        "isencao_inicio": None,
        "isencao_fim": None,
        "data_prova": None,
        "resultado_isencao": None,
    }

    # find date phrases near keywords
    keywords = {
        "inscricao": [r"inscrições?", r"inscricao"],
        "isencao": [r"isen[cç][aã]o", r"isento"],
        "prova": [r"data da prova", r"realiza.*prova|realizaç[aã]o da prova"],
        "homologacao": [r"homologad", r"homologação"],
    }

    # generic date regex (several formats)
    date_patterns = [r"[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}", r"[0-9]{1,2}\s+de\s+[A-Za-zçÇãÃ]+\s+de\s+[0-9]{4}"]

    for key, kws in keywords.items():
        for kw in kws:
            # search a window of characters around the keyword
            for match in re.finditer(kw, text, re.I):
                start = max(0, match.start() - 200)
                end = min(len(text), match.end() + 200)
                window = text[start:end]
                # try to find any date in the window
                for patt in date_patterns:
                    dmatch = re.search(patt, window)
                    if dmatch:
                        iso = _parse_date(dmatch.group(0))
                        if iso:
                            if key == "inscricao":
                                # decide if it's start or end by presence of '-' or 'a' or 'até'
                                if re.search(r"(até|a|\-|até o|a partir de)", window, re.I):
                                    # heuristics: if 'a' or 'até' before date, treat as end
                                    # crude assignment: fill start then end
                                    if cronograma["inscricao_inicio"] is None:
                                        cronograma["inscricao_inicio"] = iso
                                    elif cronograma["inscricao_fim"] is None:
                                        cronograma["inscricao_fim"] = iso
                                    else:
                                        # no space
                                        pass
                                else:
                                    if cronograma["inscricao_inicio"] is None:
                                        cronograma["inscricao_inicio"] = iso
                            elif key == "isencao":
                                if cronograma["isencao_inicio"] is None:
                                    cronograma["isencao_inicio"] = iso
                                elif cronograma["isencao_fim"] is None:
                                    cronograma["isencao_fim"] = iso
                            elif key == "prova":
                                cronograma["data_prova"] = iso
                            else:
                                cronograma.setdefault(key, iso)
                        break
                # stop after first useful match for this keyword occurrence
                if any(cronograma.get(k) for k in cronograma):
                    break
            # if we've found some dates, stop looking for other synonyms
            if any(cronograma.get(k) for k in cronograma):
                break

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
    cronograma = extract_cronograma(text)
    vagas = extract_vagas(text)
    financeiro = extract_financeiro(text)

    out = {
        "metadata": metadata,
        "vagas": vagas,
        "financeiro": financeiro,
        "cronograma": cronograma,
    }

    return out


def save_extraction_json(path_pdf: str, out_dir: str = "data/summaries") -> str:
    import os

    os.makedirs(out_dir, exist_ok=True)
    data = extract_from_pdf(path_pdf)
    base = os.path.splitext(os.path.basename(path_pdf))[0]
    out_path = os.path.join(out_dir, f"{base}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return out_path
