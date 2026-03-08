import re


def is_invalid_year_number_slug(value: str) -> bool:
    """Retorna True quando o slug está só no formato ano-documento (ex.: 2025-687495896)."""
    return bool(re.match(r"^\d{4}-\d+$", (value or "").strip()))


def is_legacy_truncated_slug(value: str) -> bool:
    """Retorna True quando o slug está no formato legado truncado (ex.: 2025-de-...-688390427)."""
    return bool(re.match(r"^\d{4}-de-.*-\d+$", (value or "").strip()))


def rebuild_legacy_slug(candidate_slug: str, edital_numero: str) -> str | None:
    """Reconstrói slug legado truncado usando o número do edital.

    Exemplo:
    - candidate_slug: 2025-de-23-de-fevereiro-de-2026-concurso-publico-688800849
    - edital_numero: 1/2025
    - resultado: edital-n-1/2025-de-23-de-fevereiro-de-2026-concurso-publico-688800849
    """
    slug = (candidate_slug or "").strip()
    edital = (edital_numero or "").strip().lower()
    if not is_legacy_truncated_slug(slug):
        return None

    match = re.match(r"^(\d+)\s*/\s*(\d{4})$", edital)
    if not match:
        return None

    numero, ano = match.group(1), match.group(2)
    if not slug.startswith(f"{ano}-"):
        return None

    return f"edital-n-{numero}/{slug}"
