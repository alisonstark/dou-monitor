import argparse
import json
from pathlib import Path
from collections import Counter

REVIEWED_DIR = Path("data/reviewed_examples")
WHITELIST_PATH = Path("data/bancas_whitelist.json")


def find_candidates(threshold: int = 3):
    c = Counter()
    files = sorted(REVIEWED_DIR.glob("*.json"))
    for p in files:
        try:
            with p.open(encoding="utf-8") as f:
                j = json.load(f)
        except Exception:
            continue
        for change in j.get("changes", []):
            field = change.get("field")
            if field == "metadata.banca":
                new = change.get("new")
                # new may be dict with 'nome' or a string
                if isinstance(new, dict):
                    name = new.get("nome")
                else:
                    name = new
                if name:
                    c[str(name).upper()] += 1
    return c


def main():
    parser = argparse.ArgumentParser(description="Suggest and apply whitelist additions from reviewed examples")
    parser.add_argument("--threshold", type=int, default=3, help="Minimum occurrences to suggest addition")
    parser.add_argument("--apply", action="store_true", help="Apply suggested additions to whitelist file")
    args = parser.parse_args()

    counts = find_candidates(args.threshold)
    if not counts:
        print("No reviewed examples found.")
        return

    suggestions = [(name, cnt) for name, cnt in counts.items() if cnt >= args.threshold]
    if not suggestions:
        print("No candidates meet the threshold.")
        return

    print("Candidates for whitelist addition (name, count):")
    for name, cnt in suggestions:
        print(f"- {name}: {cnt}")

    if args.apply:
        # load existing whitelist
        if WHITELIST_PATH.exists():
            try:
                with WHITELIST_PATH.open(encoding="utf-8") as f:
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
                print(f"Added {name.title()} to whitelist")
        if changed:
            WHITELIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            with WHITELIST_PATH.open("w", encoding="utf-8") as f:
                json.dump(wl, f, ensure_ascii=False, indent=2)
            print(f"Whitelist updated at {WHITELIST_PATH}")
        else:
            print("No new names added — whitelist unchanged.")


if __name__ == '__main__':
    main()
