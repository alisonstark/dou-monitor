"""Apply corrections from a review CSV back into JSON summary files.

Usage:
  .venv/bin/python src/apply_review.py --csv data/review_YYYYMMDDTHHMMSSZ.csv [--summaries-dir data/summaries] [--backup-dir data/backups] [--reviewer NAME] [--apply]

If --apply is not passed the script performs a dry-run and prints planned changes.
"""
from pathlib import Path
import argparse
import csv
import json
from datetime import datetime
import shutil
from typing import Any


FIELD_MAP = {
    "orgao": ("metadata", "orgao"),
    "edital_numero": ("metadata", "edital_numero"),
    "cargo": ("metadata", "cargo"),
    # banca is special: CSV 'banca' maps to metadata.banca.nome (keeps tipo if present)
    "banca": ("metadata", "banca"),
    "vagas_total": ("vagas", "total"),
    "vagas_pcd": ("vagas", "pcd"),
    "vagas_ppiq": ("vagas", "ppiq"),
    "taxa_inscricao": ("financeiro", "taxa_inscricao"),
    "data_prova": ("cronograma", "data_prova"),
}


def parse_value(target_field: str, raw: str) -> Any:
    if raw is None:
        return None
    raw = raw.strip()
    if raw == "":
        return None
    if target_field in ("total", "pcd", "ppiq"):
        # try int
        try:
            return int(raw)
        except Exception:
            # sometimes numbers come as floats or with commas
            try:
                return int(float(raw.replace(".", "").replace(",", ".")))
            except Exception:
                return None
    # otherwise return raw string
    return raw


def apply_row(row: dict, summaries_dir: Path, backup_dir: Path, apply_changes: bool, reviewer: str):
    filename = row.get("file")
    if not filename:
        print("Skipping row with no file field")
        return

    summary_path = summaries_dir / filename
    if not summary_path.exists():
        print(f"Summary not found: {summary_path}")
        return

    with summary_path.open(encoding="utf-8") as f:
        data = json.load(f)

    changes = {}

    for csv_field, mapping in FIELD_MAP.items():
        csv_val = row.get(csv_field, "")
        if csv_val is None or csv_val.strip() == "":
            continue
        section, key = mapping
        current = data.get(section, {}).get(key)
        new_val = parse_value(key, csv_val)
        # special-case banca: set metadata.banca.nome
        if csv_field == "banca":
            # ensure dict
            if section not in data or not isinstance(data.get(section), dict):
                data[section] = {}
            banca_obj = data[section].get(key) or {}
            if not isinstance(banca_obj, dict):
                banca_obj = {"nome": str(banca_obj)}
            # set nome and preserve tipo if present
            if isinstance(new_val, str):
                banca_obj["nome"] = new_val
            else:
                banca_obj["nome"] = str(new_val)
            # mark that this was manually set
            banca_obj.setdefault("tipo", banca_obj.get("tipo") or "manual")
            banca_obj["confianca_extracao"] = 1.0
            new_val = banca_obj
        if new_val is None:
            continue
        if isinstance(new_val, str) and isinstance(current, str) and new_val.strip() == current.strip():
            continue
        if new_val != current:
            changes[f"{section}.{key}"] = (current, new_val)

    if not changes:
        print(f"No changes for {filename}")
        return

    print(f"Planned changes for {filename}:")
    for k, (old, new) in changes.items():
        print(f" - {k}: {old!r} -> {new!r}")

    if not apply_changes:
        return

    # backup original
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"{filename}.{timestamp}.bak"
    shutil.copy2(summary_path, backup_path)

    # apply changes
    for k, (_, new) in changes.items():
        section, key = k.split(".")
        if section not in data:
            data[section] = {}
        data[section][key] = new

    # add review metadata
    review_meta = data.get("_review", {})
    review_meta["last_reviewed"] = timestamp
    review_meta["reviewer"] = reviewer
    data["_review"] = review_meta

    # write back
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Applied changes and backed up to {backup_path}")

    # Export reviewed example for future training
    try:
        examples_dir = Path("data/reviewed_examples")
        examples_dir.mkdir(parents=True, exist_ok=True)
        base = Path(filename).stem
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        ex_path = examples_dir / f"{base}.{ts}.json"

        # attempt to derive pdf path
        pdf_path = Path("editais") / f"{base}.pdf"

        reviewed = {
            "summary_file": filename,
            "pdf_file": str(pdf_path) if pdf_path.exists() else None,
            "timestamp": timestamp,
            "reviewer": reviewer,
            "changes": [],
        }

        for k, (old, new) in changes.items():
            section, key = k.split('.')
            snippet = None
            # try to get snippet from existing data before change
            old_data = data.get(section, {})
            if isinstance(old_data.get(key), dict):
                snippet = old_data.get(key).get("snippet")
            elif section == "metadata" and key == "banca":
                # fallback: if banca existed as dict before change
                b = old_data.get(key)
                if isinstance(b, dict):
                    snippet = b.get("snippet")

            reviewed["changes"].append({
                "field": k,
                "old": old,
                "new": new,
                "snippet": snippet,
            })

        with ex_path.open("w", encoding="utf-8") as ef:
            json.dump(reviewed, ef, ensure_ascii=False, indent=2)

        print(f"Exported reviewed example to {ex_path}")
    except Exception as e:
        print(f"Warning: failed to export reviewed example: {e}")


def main():
    parser = argparse.ArgumentParser(description="Apply review CSV corrections to summary JSON files")
    parser.add_argument("--csv", required=True, help="CSV file from review_cli to apply")
    parser.add_argument("--summaries-dir", default="data/summaries")
    parser.add_argument("--backup-dir", default="data/backups")
    parser.add_argument("--reviewer", default="manual-review")
    parser.add_argument("--apply", action="store_true", help="Actually write changes (omit for dry-run)")

    args = parser.parse_args()
    csv_path = Path(args.csv)
    summaries_dir = Path(args.summaries_dir)
    backup_dir = Path(args.backup_dir)

    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        return

    with csv_path.open(encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            apply_row(row, summaries_dir, backup_dir, args.apply, args.reviewer)


if __name__ == "__main__":
    main()
