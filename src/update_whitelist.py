import argparse
import json
from pathlib import Path
from collections import Counter

REVIEWED_DIR = Path("data/reviewed_examples")

# Map field names to their whitelist files
WHITELISTS = {
    "metadata.banca": Path("data/bancas_whitelist.json"),
    "metadata.cargo": Path("data/cargos_whitelist.json"),
}


def find_candidates(field: str, threshold: int = 3):
    """Find candidates for a given field from reviewed examples."""
    c = Counter()
    files = sorted(REVIEWED_DIR.glob("*.json"))
    for p in files:
        try:
            with p.open(encoding="utf-8") as f:
                j = json.load(f)
        except Exception:
            continue
        for change in j.get("changes", []):
            change_field = change.get("field")
            if change_field == field:
                new = change.get("new")
                # Handle banca (may be dict with 'nome' or a string)
                if field == "metadata.banca":
                    if isinstance(new, dict):
                        name = new.get("nome")
                    else:
                        name = new
                else:
                    # For other fields, just use the value as-is
                    name = new
                if name:
                    c[str(name).upper()] += 1
    return c


def update_whitelist(field: str, counts: Counter, apply_changes: bool, threshold: int = 3):
    """Update whitelist for a given field."""
    whitelist_path = WHITELISTS.get(field)
    if not whitelist_path:
        print(f"Unknown field: {field}")
        return

    suggestions = [(name, cnt) for name, cnt in counts.items() if cnt >= threshold]
    if not suggestions:
        print(f"No candidates for {field} meet the threshold (>={threshold}).")
        return

    print(f"\nCandidates for {field} whitelist (name, count):")
    for name, cnt in suggestions:
        print(f"  - {name}: {cnt}")

    if apply_changes:
        # load existing whitelist
        if whitelist_path.exists():
            try:
                with whitelist_path.open(encoding="utf-8") as f:
                    wl = json.load(f)
            except Exception:
                wl = []
        else:
            wl = []
        
        wl_upper = {str(x).upper(): x for x in wl}
        changed = False
        for name, cnt in suggestions:
            if name not in wl_upper:
                # append the canonical form (title-case)
                wl.append(name.title())
                changed = True
                print(f"  Added {name.title()} to {field} whitelist")
        
        if changed:
            whitelist_path.parent.mkdir(parents=True, exist_ok=True)
            with whitelist_path.open("w", encoding="utf-8") as f:
                json.dump(wl, f, ensure_ascii=False, indent=2)
            print(f"Whitelist updated at {whitelist_path}")
        else:
            print(f"No new items added to {field} whitelist — unchanged.")


def main():
    parser = argparse.ArgumentParser(description="Suggest and apply whitelist additions from reviewed examples")
    parser.add_argument("--threshold", type=int, default=3, help="Minimum occurrences to suggest addition")
    parser.add_argument("--apply", action="store_true", help="Apply suggested additions to whitelist files")
    args = parser.parse_args()

    if not REVIEWED_DIR.exists():
        print(f"No reviewed examples found at {REVIEWED_DIR}")
        return

    # Process both banca and cargo
    for field in WHITELISTS.keys():
        counts = find_candidates(field, args.threshold)
        if counts:
            update_whitelist(field, counts, args.apply, args.threshold)


if __name__ == '__main__':
    main()
