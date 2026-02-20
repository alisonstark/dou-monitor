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
    Handles multiple table formats commonly found in editais.
    """
    # STEP 1: Handle table format where label appears BETWEEN dates
    # "DD/MM/YYYY a URL\nLABEL\nDD/MM/YYYY" -> "LABEL DD/MM/YYYY a DD/MM/YYYY"
    text = re.sub(
        r'(\d{2}/\d{2}/\d{4})\s+a\s+[^\n]*\n\s*([^\n]+)\n\s*(\d{2}/\d{2}/\d{4})',
        r'\2 \1 a \3',
        text
    )
    
    # STEP 1.5: Handle common table formats with activity on one line and date on next
    # "Activity name\nDD/MM/YYYY" or "Activity name\nDD/MM/YYYY a DD/MM/YYYY"
    # Handles both singular (inscrição) and plural (inscrições)
    text = re.sub(
        r'(inscri[çc][ãõ][^\n]{0,100})\n\s*(\d{2}/\d{2}/\d{4}(?:\s+a\s+\d{2}/\d{2}/\d{4})?)',
        r'\1 \2',
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r'(isen[çc][ãa]o[^\n]{0,100})\n\s*(\d{2}/\d{2}/\d{4}(?:\s+a\s+\d{2}/\d{2}/\d{4})?)',
        r'\1 \2',
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r'((?:aplica[çc][ãa]o\s+da\s+)?provas?[^\n]{0,100})\n\s*(\d{2}/\d{2}/\d{4}(?:\s+a\s+\d{2}/\d{2}/\d{4})?)',
        r'\1 \2',
        text,
        flags=re.IGNORECASE
    )
    
    # STEP 2: Remove URLs (after restructuring table)
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    
    # STEP 3: Fix broken date ranges split by newline
    text = re.sub(
        r'(\d{2}/\d{2}/\d{4})\s*a\s*\n\s*(\d{2}/\d{2}/\d{4})',
        r'\1 a \2',
        text
    )
    
    # STEP 4: Fix broken "Entre" (handles both "Entre" and "entre")
    text = re.sub(
        r'Entre\s*\n\s*(\d{2}/\d{2}/\d{4})',
        r'Entre \1',
        text,
        flags=re.IGNORECASE
    )
    
    # STEP 5: Fix "Entre DD/MM/YYYY a [text] DD/MM/YYYY"
    text = re.sub(
        r'(Entre\s+\d{2}/\d{2}/\d{4})\s+a\s*\n?\s*([^\d\n]+)?\s*(\d{2}/\d{2}/\d{4})',
        r'\1 a \3',
        text,
        flags=re.IGNORECASE
    )
    
    # STEP 6: Collapse excessive whitespace (but preserve single line breaks for structure)
    text = re.sub(r'[ \t]+', ' ', text)  # Collapse spaces/tabs
    text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 consecutive newlines
    
    return text.strip()


def parse_date_block(date_block: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse a date block into (start_iso, end_iso).
    
    Handles:
    - "DD/MM/YYYY a DD/MM/YYYY"
    - "Entre DD/MM/YYYY a/e DD/MM/YYYY" (handles both 'a' and 'e')
    - "DD/MM/YYYY" (single date)
    """
    date_block = date_block.strip()
    
    # Entre ... e/a ... (check first before splitting on "a")
    if date_block.lower().startswith("entre"):
        dates = re.findall(r'\d{2}/\d{2}/\d{4}', date_block)
        if len(dates) == 2:
            return to_iso(dates[0]), to_iso(dates[1])
        elif len(dates) == 1:
            return to_iso(dates[0]), None
    
    # Range using "a" (only if not an Entre phrase)
    if " a " in date_block:
        parts = date_block.split(" a ")
        if len(parts) == 2:
            return to_iso(parts[0]), to_iso(parts[1])
    
    # Single date
    return to_iso(date_block), None


def classify_event(event_text: str) -> str:
    """
    Classify event type from event text.
    Returns one of: inscricao, isencao, prova, resultado, recurso, publicacao, outro
    
    Strategy: Identify the primary event. Isenção and Inscrição are treated equally for extraction.
    Homologação is dropped - we care about inscricao/isencao as the primary events.
    """
    e = event_text.lower()
    
    # Check isenção BEFORE inscrição (both are important, but check isenção first if both present)
    # Variations: isenção, isencao, isenç, isen
    if "isen" in e or "isençã" in e or "isenc" in e:
        return "isencao"
    
    # Then check inscrição
    # Variations: inscrição, inscricao, inscriçõ, inscri
    if "inscri" in e or "inscric" in e:
        return "inscricao"
    
    # Prova/exam related
    # Include variations: prova, aplicação, realização
    if any(word in e for word in ["prova", "aplicac", "aplicaç", "realizac", "realizaç"]):
        return "prova"
    
    # Other specific event types
    if "resultado" in e:
        return "resultado"
    if "recurso" in e:
        return "recurso"
    if "publica" in e:
        return "publicacao"
    # Note: Homologação is intentionally NOT classified as a separate type
    # It's used to find dates but we focus on inscricao/isencao
    
    return "outro"


def extract_all_dates(text: str) -> List[Dict]:
    """
    Extract all date events from text.
    
    Returns list of dicts with:
    - evento: str (event description)
    - data_inicio: str (ISO date)
    - data_fim: str | None (ISO date for ranges)
    - tipo: str (event classification)
    
    Uses two strategies:
    1. Standard approach: find dates and look backward for context
    2. Keyword approach: find keywords (inscrição, isenção, prova) and look forward for dates
    """
    text = normalize_text(text)
    results = []
    seen_dates = set()  # Track to avoid duplicates
    
    # Strategy 1: Find dates and look backward for context
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
            date_key = f"{data_inicio}|{data_fim}|{event_text[:50]}"
            if date_key not in seen_dates:
                seen_dates.add(date_key)
                results.append({
                    "evento": event_text,
                    "data_inicio": data_inicio,
                    "data_fim": data_fim,
                    "tipo": classify_event(event_text)
                })
    
    # Strategy 2: Keyword-based search for critical events
    # Look for keywords and find dates immediately after them
    keywords = [
        (r'inscri[çc][õo]es?', 'inscricao'),
        (r'isen[çc][ãa]o', 'isencao'),
        (r'(?:aplica[çc][ãa]o\s+da\s+)?provas?(?:\s+objetivas?)?', 'prova'),
        (r'realiza[çc][ãa]o\s+da\s+provas?', 'prova'),
    ]
    
    for keyword_pattern, tipo in keywords:
        # Find keyword occurrences
        for kw_match in re.finditer(keyword_pattern, text, re.IGNORECASE):
            kw_start = kw_match.start()
            kw_text = kw_match.group(0)
            
            # Look forward up to 200 chars for dates
            context_end = min(len(text), kw_start + 200)
            forward_context = text[kw_start:context_end]
            
            # Find dates in forward context
            for date_match in DATE_PATTERN.finditer(forward_context):
                date_block = date_match.group(0)
                data_inicio, data_fim = parse_date_block(date_block)
                
                if data_inicio:
                    # Extract fuller event description (backward + keyword + some forward)
                    back_start = max(0, kw_start - 50)
                    event_text = text[back_start:kw_start + 100].strip()
                    event_text = re.sub(r'[:\-–]+$', '', event_text).strip()
                    
                    date_key = f"{data_inicio}|{data_fim}|{tipo}"
                    if date_key not in seen_dates:
                        seen_dates.add(date_key)
                        results.append({
                            "evento": event_text,
                            "data_inicio": data_inicio,
                            "data_fim": data_fim,
                            "tipo": tipo
                        })
                        break  # Take first date found after this keyword
    
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
        # Strategy: prefer keyword-based matches over generic ones
        # First pass: process keyword-based matches (more reliable)
        prova_range = None
        
        # Separate events by confidence (keyword-based vs backward-looking)
        high_confidence = []
        low_confidence = []
        
        for event in events:
            # High confidence: event text contains the actual keyword
            event_lower = event["evento"].lower()
            if event["tipo"] == "inscricao" and "inscri" in event_lower:
                high_confidence.append(event)
            elif event["tipo"] == "isencao" and "isen" in event_lower:
                high_confidence.append(event)
            elif event["tipo"] == "prova" and ("prova" in event_lower or "aplica" in event_lower or "realiza" in event_lower):
                high_confidence.append(event)
            else:
                low_confidence.append(event)
        
        # Process high confidence events first
        for event in high_confidence:
            tipo = event["tipo"]
            
            if tipo == "inscricao" and not result["inscricao_inicio"]:
                result["inscricao_inicio"] = event["data_inicio"]
                result["inscricao_fim"] = event["data_fim"]
                logger.debug(f"Found inscricao (HC): {event['data_inicio']} - {event['data_fim']}")
            
            elif tipo == "isencao" and not result["isencao_inicio"]:
                result["isencao_inicio"] = event["data_inicio"]
                logger.debug(f"Found isencao (HC): {event['data_inicio']}")
            
            elif tipo == "prova":
                # Prefer ranges over single dates
                if event["data_fim"] and not prova_range:
                    prova_range = event
                    logger.debug(f"Found prova range (HC): {event['data_inicio']} - {event['data_fim']}")
                elif not result["data_prova"] and not event["data_fim"]:
                    result["data_prova"] = event["data_inicio"]
                    logger.debug(f"Found prova single (HC): {event['data_inicio']}")
        
        # Then process low confidence events (only fill gaps)
        for event in low_confidence:
            tipo = event["tipo"]
            
            if tipo == "inscricao" and not result["inscricao_inicio"]:
                result["inscricao_inicio"] = event["data_inicio"]
                result["inscricao_fim"] = event["data_fim"]
                logger.debug(f"Found inscricao (LC): {event['data_inicio']} - {event['data_fim']}")
            
            elif tipo == "isencao" and not result["isencao_inicio"]:
                result["isencao_inicio"] = event["data_inicio"]
                logger.debug(f"Found isencao (LC): {event['data_inicio']}")
            
            elif tipo == "prova":
                # Prefer ranges over single dates
                if event["data_fim"] and not prova_range:
                    prova_range = event
                    logger.debug(f"Found prova range (LC): {event['data_inicio']} - {event['data_fim']}")
                elif not result["data_prova"] and not event["data_fim"]:
                    result["data_prova"] = event["data_inicio"]
                    logger.debug(f"Found prova single (LC): {event['data_inicio']}")
        
        # Use prova range if found, otherwise keep single date
        if prova_range:
            result["data_prova"] = prova_range["data_inicio"]
            logger.debug(f"Using prova range start: {prova_range['data_inicio']}")
        
        return result
