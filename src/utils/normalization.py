import unicodedata


def normalize_text(text: str) -> str:
    """Remove acentos e converte o texto para minúsculas."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    ).lower()
