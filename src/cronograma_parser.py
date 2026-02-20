"""
Production-grade cronograma parsing pipeline.

Strategy:
1. Normalize text (fix broken lines, remove URLs)
2. Find ALL dates using comprehensive regex
3. Look backwards to capture event context
4. Classify events
5. Map to 4 essential fields
"""

import re
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Comprehensive date pattern: handles single dates, ranges, and "Entre"
# Case-insensitive to match both "a" and "A"
DATE_PATTERN = re.compile(
    r'('
        r'\d{2}/\d{2}/\d{4}\s*a\s*\d{2}/\d{2}/\d{4}'
        r'|Entre\s+\d{2}/\d{2}/\d{4}(?:\s*(?:e|a)\s*\d{2}/\d{2}/\d{4})?'
        r'|\d{2}/\d{2}/\d{4}'
    r')',
    re.IGNORECASE
)


def to_iso(date_str: str) -> Optional[str]:
    """Convert DD/MM/YYYY to ISO YYYY-MM-DD."""
    try:
        dt = datetime.strptime(date_str.strip(), "%d/%m/%Y")
        return dt.date().isoformat()
    except Exception:
        return None


def normalize_text(text: str) -> str:
    """
    Normalize PDF text to handle broken line breaks and noise.
    """
    # STEP 1: Handle table format where label appears BETWEEN dates
    # "DD/MM/YYYY a URL\nLABEL\nDD/MM/YYYY" -> "LABEL DD/MM/YYYY a DD/MM/YYYY"
    text = re.sub(
        r'(\d{2}/\d{2}/\d{4})\s+a\s+[^\n]*\n\s*([^\n]+)\n\s*(\d{2}/\d{2}/\d{4})',
        r'\2 \1 a \3',
        text
    )
    
    # STEP 2: Remove URLs (after restructuring table)
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    
    # STEP 3: Fix broken date ranges split by newline
    text = re.sub(
        r'(\d{2}/\d{2}/\d{4})\s*a\s*\n\s*(\d{2}/\d{2}/\d{4})',
        r'\1 a \2',
        text
    )
    
    # STEP 4: Fix broken "Entre"
    text = re.sub(
        r'Entre\s*\n\s*(\d{2}/\d{2}/\d{4})',
        r'Entre \1',
        text
    )
    
    # STEP 5: Fix "Entre DD/MM/YYYY a [text] DD/MM/YYYY"
    text = re.sub(
        r'(Entre\s+\d{2}/\d{2}/\d{4})\s+a\s*\n?\s*([^\d\n]+)?\s*(\d{2}/\d{2}/\d{4})',
        r'\1 a \3',
        text,
        flags=re.IGNORECASE
    )
    
    # STEP 6: Collapse excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def parse_date_block(date_block: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse a date block into (start_iso, end_iso).
    
    Handles:
    - "DD/MM/YYYY a DD/MM/YYYY"
    - "Entre DD/MM/YYYY a/e DD/MM/YYYY"
    - "DD/MM/YYYY" (single date)
    """
    date_block = date_block.strip()
    
    # Range using "a"
    if " a " in date_block:
        parts = date_block.split(" a ")
        if len(parts) == 2:
            return to_iso(parts[0]), to_iso(parts[1])
    
    # Entre ... e/a ...
    if date_block.lower().startswith("entre"):
        dates = re.findall(r'\d{2}/\d{2}/\d{4}', date_block)
        if len(dates) == 2:
            return to_iso(dates[0]), to_iso(dates[1])
        elif len(dates) == 1:
            return to_iso(dates[0]), None
    
    # Single date
    return to_iso(date_block), None


def classify_event(event_text: str) -> str:
    """
    Classify event type from event text.
    Returns one of: inscricao, isencao, prova, outro
    
    Priority order matters - check more specific terms first.
    """
    e = event_text.lower()
    
    # Check isenção BEFORE inscrição (more specific)
    if "isen" in e or "isençã" in e:
        return "isencao"
    
    # Then check inscrição
    if "inscri" in e:
        return "inscricao"
    
    # Prova/exam related
    if "prova" in e:
        return "prova"
    
    # Other event types
    if "resultado" in e:
        return "resultado"
    if "recurso" in e:
        return "recurso"
    if "homolog" in e:
        return "homologacao"
    if "publica" in e:
        return "publicacao"
    
    return "outro"


def extract_all_dates(text: str) -> List[Dict]:
    """
    Extract all date events from text.
    
    Returns list of dicts with:
    - evento: str (event description)
    - data_inicio: str (ISO date)
    - data_fim: str | None (ISO date for ranges)
    - tipo: str (event classification)
    """
    text = normalize_text(text)
    results = []
    
    for match in DATE_PATTERN.finditer(text):
        date_block = match.group(0)
        start_index = match.start()
        
        # Look back up to 150 chars before the date to find event description
        context_start = max(0, start_index - 150)
        context = text[context_start:start_index]
        
        # Clean trailing fragments like portal notes
        context = re.sub(r'Nota Informativa.*', '', context)
        context = context.strip()
        
        # Heuristic: take last sentence fragment
        event_text = context.split(".")[-1].strip()
        
        # Remove trailing connectors
        event_text = re.sub(r'[:\-–]+$', '', event_text).strip()
        
        # Parse dates
        data_inicio, data_fim = parse_date_block(date_block)
        
        if data_inicio:  # Only add if we successfully parsed at least start date
            results.append({
                "evento": event_text,
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "tipo": classify_event(event_text)
            })
    
    return results


class CronogramaParser:
    """
    Production-grade cronograma parser using semantic date extraction.
    
    Strategy:
    1. Find all dates in text
    2. Look backwards to capture event labels
    3. Classify events
    4. Map to 4 essential fields
    """

    def __init__(self):
        pass


    def extract_from_text(self, text: str) -> Dict[str, Optional[str]]:
        """
        Extract 4 essential cronograma fields from text.
        
        Returns dict with keys:
        - inscricao_inicio, inscricao_fim
        - isencao_inicio
        - data_prova
        
        Strategy:
        1. Try to find CRONOGRAMA section and extract from there (faster, more precise)
        2. If that fails, scan entire PDF (more robust)
        """
        result = {
            "inscricao_inicio": None,
            "inscricao_fim": None,
            "isencao_inicio": None,
            "data_prova": None,
        }
        
        if not text:
            return result
        
        # Try to isolate cronograma section for faster/more accurate extraction
        cronograma_section = None
        cronograma_match = re.search(
            r'(CRONOGRAMA|Cronograma|DATAS?\s+IMPORTANTES?|Datas?\s+Importantes?)[^\n]*\n([\s\S]{100,12000}?)(?=\n\s*(?:ANEXO|Anexo|CAPÍTULO|Capítulo|\d+\.\s+[A-Z])|$)',
            text,
            re.IGNORECASE
        )
        
        if cronograma_match:
            cronograma_section = cronograma_match.group(2)
            logger.debug(f"Found cronograma section ({len(cronograma_section)} chars)")
        
        # Try section-based extraction first
        events = []
        if cronograma_section:
            events = extract_all_dates(cronograma_section)
            logger.debug(f"Extracted {len(events)} date events from cronograma section")
        
        # Fallback: scan entire PDF if section not found or yielded insufficient results
        if not events or len(events) < 3:
            logger.debug("Insufficient events in section, scanning entire PDF")
            events = extract_all_dates(text)
            logger.debug(f"Extracted {len(events)} date events from full text")
        
        # Map events to our 4 essential fields
        # Prefer date ranges over single dates for prova
        prova_range = None
        
        for event in events:
            tipo = event["tipo"]
            
            if tipo == "inscricao" and not result["inscricao_inicio"]:
                result["inscricao_inicio"] = event["data_inicio"]
                result["inscricao_fim"] = event["data_fim"]
                logger.debug(f"Found inscricao: {event['data_inicio']} - {event['data_fim']}")
            
            elif tipo == "isencao" and not result["isencao_inicio"]:
                result["isencao_inicio"] = event["data_inicio"]
                logger.debug(f"Found isencao: {event['data_inicio']}")
            
            elif tipo == "prova":
                # Prefer ranges over single dates
                if event["data_fim"] and not prova_range:
                    prova_range = event
                    logger.debug(f"Found prova range: {event['data_inicio']} - {event['data_fim']}")
                elif not result["data_prova"] and not event["data_fim"]:
                    result["data_prova"] = event["data_inicio"]
                    logger.debug(f"Found prova single: {event['data_inicio']}")
        
        # Use prova range if found, otherwise keep single date
        if prova_range:
            result["data_prova"] = prova_range["data_inicio"]
            logger.debug(f"Using prova range start: {prova_range['data_inicio']}")
        
        return result
