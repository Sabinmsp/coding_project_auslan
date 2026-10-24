"""
Make a word's sign playable now, without waiting for the full library run.

    python3 scripts/add_sign.py elephant              # the sign(s) meaning ELEPHANT
    python3 scripts/add_sign.py open --all-senses     # OPEN plus OPEN (DOOR), (WINDOW), ...
    python3 scripts/add_sign.py --id open-door        # one specific sign id
    python3 scripts/add_sign.py student --button      # also add a quick-pick button

Looks the word up in datasets/processed/catalog.json with the same rules the player
uses -- in particular a negated gloss like WANT (NOT WANT) is found by
"not want", never by "want" -- then runs build_library.py for just those
signs (extract, transcode, quality-score, manifest). Reload the page and
they play.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import paths  # noqa: E402
from ingest import norm_key  # noqa: E402  (same key rules as the catalog)

CATALOG = paths.CATALOG
SIGNS = paths.QUICK_PICKS
python_with_mediapipe = paths.python_with_mediapipe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("word", nargs="?")
    ap.add_argument("--id", dest="ids", action="append", default=[])
    ap.add_argument("--all-senses", action="store_true")
    ap.add_argument("--button", action="store_true", help="add a quick-pick button")
    args = ap.parse_args()
    if not args.word and not args.ids:
        ap.error("give a word or --id")

    catalog = json.loads(CATALOG.read_text())
    signs = catalog["signs"]
    ids = list(args.ids)
    bad = [i for i in ids if i not in signs]
    if bad:
        sys.exit(f"unknown sign id(s): {', '.join(bad)}")

    if args.word:
        key = norm_key(args.word)
        found = catalog["keys"].get(key, [])
        primary = [i for i in found if signs[i]["kind"] == "plain"
                   or (signs[i]["kind"] == "phrase" and signs[i]["keys"][0] == key)]
        senses = [i for i in found if i not in primary]
        if not found:
            near = sorted(k for k in catalog["keys"] if k.startswith(key))[:8]
            sys.exit(f"no sign for {key!r} in the corpus."
                     + (f" Keys starting with it: {', '.join(near)}" if near else ""))
        if args.all_senses:
            ids += found
        elif primary:
            ids += primary
            if senses:
                print(f"also in the corpus (not added; --all-senses to include): "
                      + ", ".join(f"{i} [{signs[i]['gloss']}]" for i in senses))
        else:
            sys.exit(f"{key!r} only exists as specific senses: "
                     + ", ".join(f"{i} [{signs[i]['gloss']}]" for i in senses)
                     + "\npick one with --id, or take all with --all-senses")

    ids = list(dict.fromkeys(ids))
    print("extracting:", ", ".join(f"{i} [{signs[i]['gloss']}]" for i in ids))
    r = subprocess.run([python_with_mediapipe(), str(HERE / "build_library.py"),
                        "--only", *ids, "--workers", str(min(4, len(ids)))])
    if r.returncode:
        sys.exit(r.returncode)

    if args.button:
        quick = json.loads(SIGNS.read_text())
        for i in ids:
            s = signs[i]
            label = s["keys"][0] if s["kind"] == "phrase" else s["gloss"]
            quick[label] = {"library": i}
        SIGNS.write_text(json.dumps(quick, indent=2) + "\n")
        print("quick-pick buttons added to signs.json")
    print("done -- reload the page")


if __name__ == "__main__":
    main()
