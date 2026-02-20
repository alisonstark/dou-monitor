import argparse
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List


def compute_confidence(item: Dict[str, Any]) -> (float, List[str]):
    score = 0.0
    issues: List[str] = []
    md = item.get("metadata", {})
    vagas = item.get("vagas", {})
    fin = item.get("financeiro", {})
    cron = item.get("cronograma", {})

    if md.get("orgao"):
        score += 0.2
    else:
        issues.append("missing_orgao")

    if md.get("edital_numero"):
        score += 0.2
    else:
        issues.append("missing_edital_numero")

    if md.get("cargo"):
        score += 0.2
    else:
        issues.append("missing_cargo")

    if vagas.get("total") is not None:
        score += 0.15
    else:
        issues.append("missing_total_vagas")

    if fin.get("taxa_inscricao"):
        score += 0.1
    else:
        issues.append("missing_taxa")

    # Check for any critical cronograma date (more flexible than just data_prova)
    if any(cron.get(k) for k in ["inscricao_inicio", "data_prova", "resultado_isencao"]):
        score += 0.15
    else:
        issues.append("missing_key_dates")

    # content sanity checks
    banca = md.get("banca")
    banca_nome = None
    if isinstance(banca, dict):
        banca_nome = banca.get("nome")
        # if banca dict has low confidence, flag
        if banca.get("confianca_extracao") is not None and banca.get("confianca_extracao") < 0.6:
            issues.append("banca_low_confidence")
        if banca.get("nome") and ("\n" in banca.get("nome") or len(banca.get("nome")) > 120):
            issues.append("banca_messy")
    else:
        banca_nome = banca
        if banca and ("\n" in banca or len(banca) > 120):
            issues.append("banca_messy")

    # vagas consistency
    total = vagas.get("total")
    pcd = vagas.get("pcd")
    if total is not None and pcd is not None and pcd > total:
        issues.append("pcd_gt_total")

    # clamp score
    if score > 1.0:
        score = 1.0

    return round(score, 2), issues


def _format_date_range(start: str, end: str) -> str:
    """Format a date range as 'DD/MM a DD/MM' for readability."""
    if not start and not end:
        return ""
    if start and end and start != end:
        # Extract day/month from ISO dates (YYYY-MM-DD)
        start_dm = start[5:] if start else ""
        end_dm = end[5:] if end else ""
        return f"{start_dm} a {end_dm}"
    elif start:
        return start[5:]  # Just DD/MM
    else:
        return end[5:] if end else ""


def _summarize_cronograma(cron: Dict) -> str:
    """Create a human-readable summary of essential dates."""
    parts = []
    
    # Inscrição (período)
    inscr = _format_date_range(cron.get("inscricao_inicio"), cron.get("inscricao_fim"))
    if inscr:
        parts.append(f"Insc: {inscr}")
    
    # Isenção (data de início/solicitação)
    if cron.get("isencao_inicio"):
        parts.append(f"Isen: {cron['isencao_inicio'][5:]}")
    
    # Prova
    if cron.get("data_prova"):
        parts.append(f"Prova: {cron['data_prova'][5:]}")
    
    return " | ".join(parts) if parts else ""


def generate_csv(out_path: Path, summaries_dir: Path):
    summaries = sorted(summaries_dir.glob("*.json"))
    rows = []
    for p in summaries:
        with p.open(encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                continue

        conf, issues = compute_confidence(data)
        md = data.get("metadata", {})
        vagas = data.get("vagas", {})
        fin = data.get("financeiro", {})
        cron = data.get("cronograma", {})

        # Extract banca_nome from metadata
        banca = md.get("banca")
        banca_nome = None
        if isinstance(banca, dict):
            banca_nome = banca.get("nome")
        else:
            banca_nome = banca

        rows.append({
            "file": p.name,
            "orgao": md.get("orgao", ""),
            "edital_numero": md.get("edital_numero", ""),
            "cargo": md.get("cargo", ""),
            "banca": banca_nome or "",
            "vagas_total": vagas.get("total", ""),
            "vagas_pcd": vagas.get("pcd", ""),
            "vagas_ppiq": vagas.get("ppiq", ""),
            "taxa_inscricao": fin.get("taxa_inscricao", ""),
            "cronograma": _summarize_cronograma(cron),
            "confidence": conf,
            "issues": ";".join(issues),
        })

    # write CSV
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "file",
        "orgao",
        "edital_numero",
        "cargo",
        "banca",
        "vagas_total",
        "vagas_pcd",
        "vagas_ppiq",
        "taxa_inscricao",
        "cronograma",
        "confidence",
        "issues",
    ]

    with out_path.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    return out_path


def main():
    parser = argparse.ArgumentParser(description="Generate CSV to review extractions")
    parser.add_argument("--summaries-dir", default="data/summaries")
    parser.add_argument("--out", default=None, help="Output CSV path")
    parser.add_argument("--threshold", type=float, default=0.6, help="Confidence threshold for low-confidence flag")

    args = parser.parse_args()
    summaries_dir = Path(args.summaries_dir)
    if args.out:
        out_path = Path(args.out)
    else:
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        out_path = Path("data") / f"review_{ts}.csv"

    out = generate_csv(out_path, summaries_dir)
    print(f"CSV written to: {out}")

    # print low-confidence entries
    import csv as _csv
    low = []
    with out.open(encoding="utf-8") as f:
        rdr = _csv.DictReader(f)
        for row in rdr:
            try:
                if float(row.get("confidence", 0)) < args.threshold:
                    low.append((row["file"], row.get("confidence"), row.get("issues")))
            except Exception:
                continue

    if low:
        print("\nLow-confidence extractions:")
        for f, c, issues in low:
            print(f"- {f}: confidence={c}, issues={issues}")


if __name__ == "__main__":
    main()
