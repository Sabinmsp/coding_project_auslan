"""
Dataset -> datasets/processed/catalog.json: every sign record, normalised, with a
stable ID, its search keys, and its video takes.

    python3 scripts/ingest.py                                   # datasets/raw/labels/Test_ITW.json + datasets/videos/rgb/
    python3 scripts/ingest.py --json other_labels.json --videos /path/to/clips
    python3 scripts/ingest.py --csv signs.csv --clip-col id --gloss-col gloss \
                      --videos /path/to/clips
    python3 scripts/ingest.py --folder /path/to/videos     # hello.mp4, thank_you.mp4 ...

Accepted label files:
  JSON  {"<clip id>": "<GLOSS>", ...}            (Test_ITW.json's shape)
  JSON  [{"clip"|"video": ..., "gloss": ...}, ...]
  CSV   any two columns, named with --clip-col / --gloss-col
  a folder of .mp4 files, the gloss taken from each file name
        (thank_you.mp4 -> THANK YOU, "open (door).mp4" -> OPEN (DOOR))
A clip id resolves to <videos>/<id>_kf_rgb.mp4, then <videos>/<id>.mp4; a
value that is already a path to an existing file is used as-is.

WHAT THE PARENTHESES MEAN -- the one rule that matters most here.

A gloss like "WATER (HOSE)" is a word plus a disambiguating sense: the key
is WATER, the sense is HOSE. But in this corpus a parenthetical that
repeats the head word is the sign's actual MEANING, not a sense of it:

    WANT (NOT WANT)      is the sign for "don't want"
    GOOD (NO GOOD)       is the sign for "no good"
    WEEK (LAST WEEK)     is the sign for "last week"

Keying those under the head word makes typing "want" sign DON'T WANT --
the opposite meaning, and a mistake no viewer could see from the
animation. So when the parenthetical contains the head word, the
parenthetical phrase is the primary key (43 glosses). Whether the bare
head word may ALSO find it depends on what the extra words do:

    negate or shift time -- NOT, NO, LOSE, LAST, NEXT, THIS, AFTER, EVERY,
    ALL -- the head word must NOT find it (31 glosses). GOOD and WANT are
    among these; the corpus has no plain sign for either, so they
    correctly fall through to fingerspelling.

    only narrow it -- ANCIENT EGYPT, DORSAL FIN, ONE HUNDRED -- the head
    word finds it as an uncertain sense match, flagged for review (12).

keys[0] is always the key that states the sign's meaning; a match on any
later key is a sense match, never an exact one.
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import paths  # noqa: E402

OUT = paths.CATALOG
find_tool = paths.find_tool


def norm_key(text):
    """Search-key form: upper case, hyphens as spaces, punctuation dropped
    (apostrophes kept, so DON'T stays one token)."""
    text = text.upper().replace("-", " ")
    text = re.sub(r"[^A-Z0-9' ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "sign"


MEANING_CHANGERS = {"NOT", "NO", "LOSE", "LAST", "NEXT", "THIS", "AFTER",
                    "EVERY", "ALL",
                    # needed by the dictionary keywords ("have (have none)");
                    # no gloss name uses them, so gloss classification is unchanged
                    "NONE", "NEVER", "NOTHING", "WITHOUT"}


def classify(gloss):
    """-> (kind, keys, head, sense). kind is plain | sense | plural | phrase.
    keys[0] is the key that states the meaning."""
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", gloss)
    if not m:
        return "plain", [norm_key(gloss)], norm_key(gloss), None
    head, inner = norm_key(m.group(1)), norm_key(m.group(2))
    if re.search(rf"\b{re.escape(head)}\b", inner):
        # WANT (NOT WANT): the parenthetical IS the meaning
        extra = set(inner.split()) - set(head.split())
        if extra & MEANING_CHANGERS:
            return "phrase", [inner], head, inner
        return "phrase", [inner, head], head, inner
    if inner == "PLURAL":
        return "plural", [head], head, "PLURAL"
    return "sense", [head], head, inner


def load_labels(args):
    if args.folder:
        rows = []
        for f in sorted(Path(args.folder).glob("*.mp4")):
            gloss = re.sub(r"[_\s]+", " ", f.stem).strip().upper()
            rows.append((str(f.resolve()), gloss))
        return rows
    if args.csv:
        with open(args.csv, newline="") as f:
            return [(str(r[args.clip_col]).strip(), r[args.gloss_col].strip())
                    for r in csv.DictReader(f)]
    data = json.loads(Path(args.json).read_text())
    if isinstance(data, dict):
        return [(str(k), v) for k, v in data.items()]
    return [(str(r.get("clip") or r.get("video")), r["gloss"]) for r in data]


def resolve_video(clip, videos):
    p = Path(clip)
    if p.suffix and p.exists():
        return p
    for cand in (videos / f"{clip}_kf_rgb.mp4", videos / f"{clip}.mp4"):
        if cand.exists():
            return cand
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(paths.LABELS))
    ap.add_argument("--csv")
    ap.add_argument("--folder", help="a folder of <gloss>.mp4 files")
    ap.add_argument("--clip-col", default="clip")
    ap.add_argument("--gloss-col", default="gloss")
    ap.add_argument("--videos", default=str(paths.RGB))
    args = ap.parse_args()
    videos = Path(args.videos)
    ffprobe = find_tool("ffprobe")

    labels = load_labels(args)
    print(f"{len(labels)} label rows from {args.folder or args.csv or args.json}")

    def probe(clip):
        path = resolve_video(clip, videos)
        if path is None:
            return clip, None, 0, 0.0
        out = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=nb_frames,r_frame_rate", "-of", "csv=p=0",
             str(path)], capture_output=True, text=True, timeout=20).stdout.strip()
        try:
            rate, n = out.split(",")
            a, b = rate.split("/")
            return clip, path, int(n), float(a) / float(b)
        except ValueError:
            return clip, path, 0, 0.0

    with ThreadPoolExecutor(16) as pool:
        probed = {c: (p, n, fps) for c, p, n, fps in pool.map(probe, [c for c, _ in labels])}

    by_gloss = defaultdict(list)
    missing, dup_rows = [], 0
    seen = set()
    for clip, gloss in labels:
        gloss = re.sub(r"\s+", " ", gloss.strip())
        if (clip, gloss) in seen:
            dup_rows += 1
            continue
        seen.add((clip, gloss))
        path, n, fps = probed[clip]
        if path is None:
            missing.append(clip)
            continue
        clip_id = clip if not Path(clip).suffix else slug(Path(clip).stem)
        by_gloss[gloss].append({"clip": clip_id, "frames": n, "fps": round(fps, 3),
                                "path": str(path.relative_to(paths.VIDEO_ROOT))
                                if path.is_relative_to(paths.VIDEO_ROOT) else str(path)})

    signs, used_ids = {}, Counter()
    for gloss in sorted(by_gloss):
        kind, keys, head, sense = classify(gloss)
        sid = slug(gloss)
        used_ids[sid] += 1
        if used_ids[sid] > 1:
            sid = f"{sid}-{used_ids[sid]}"
        # longest take first: a clipped take is the commoner failure
        takes = sorted(by_gloss[gloss], key=lambda t: (-t["frames"], t["clip"]))
        signs[sid] = {"gloss": gloss, "kind": kind, "keys": keys,
                      "head": head, "sense": sense, "takes": takes}

    keys = defaultdict(list)
    for sid, s in signs.items():
        for k in s["keys"]:
            keys[k].append(sid)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": Path(args.folder or args.csv or args.json).name,
                               "signs": signs, "keys": keys}, indent=1))

    kinds = Counter(s["kind"] for s in signs.values())
    print(f"{len(signs)} signs, {len(keys)} search keys -> {OUT.relative_to(paths.ROOT)}")
    print(f"  kinds: {dict(kinds)}")
    print(f"  takes per sign: {dict(Counter(len(s['takes']) for s in signs.values()))}")
    print(f"  label rows with no video file: {len(missing)}   duplicate rows: {dup_rows}")
    multi = {k: v for k, v in keys.items() if len(v) > 1}
    print(f"  keys with several candidate signs (need context / review): {len(multi)}")


if __name__ == "__main__":
    main()
