"""
Add signs from the Auslan Signbank dictionary to the library, beside the
corpus signs: datasets/raw/labels/signbank_signs.json -> catalog.json.

    python3 scripts/add_signbank_signs.py            # download what is missing, merge into the catalog
    python3 scripts/add_signbank_signs.py --build    # ... then extract them (build_library.py --only)

For words the corpus (Test_ITW.json) has no usable sign for. Each entry in
signbank_signs.json names one dictionary page and its video, the gloss, and
the English keys that should find it -- chosen by hand, because a Signbank
page lists loose keywords as well as real translations (see "chosen" in
that file for the rule).

Per entry:
    video  -> datasets/videos/signbank/sb<video id>.mp4, letterboxed to the
              library's 512x408 (scripts/fetch_signbank_letter.py, same
              scale+pad -- never a stretch)
    gloss already in the catalog (PUMPKIN, STACK ...) -> the video is added
              as one more take; build_library.py keeps the take that
              extracts best, so a poorly tracked corpus recording is replaced
    new gloss -> a new plain sign, marked "source": "signbank" with its page
"aliases" add a key to an existing sign ("HR" -> hour).

ingest.py rewrites the catalog from the corpus labels alone, so run this
again after any re-ingest; it is idempotent (a take or key already there is
not added twice, a video already downloaded is not fetched again).

LICENSE: Signbank content is CC BY-NC-ND 4.0 (non-commercial, attribution).
The page URL of every sign is kept in its catalog entry for attribution.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from backend import paths  # noqa: E402
from ingest import classify, norm_key, slug  # noqa: E402
from fetch_signbank_letter import download, letterbox_to_library_standard  # noqa: E402

SOURCE = paths.DATASETS / "raw" / "labels" / "signbank_signs.json"
VIDEOS = paths.VIDEO_ROOT / "signbank"
CATALOG = paths.CATALOG


def clip_id(video_url):
    # .../mp4video/27/27750_1.mp4 -> sb27750_1 ("sb": corpus clip ids are bare numbers)
    return "sb" + re.sub(r"[^A-Za-z0-9_]", "_", Path(video_url).stem)


def probe(path):
    out = subprocess.run(
        [paths.find_tool("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-count_frames", "-show_entries", "stream=nb_read_frames,r_frame_rate",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60).stdout.strip()
    rate, n = out.split(",")
    a, b = rate.split("/")
    return int(n), round(float(a) / float(b), 3)


def fetch(entry):
    """Download + letterbox once; return the catalog take."""
    clip = clip_id(entry["video"])
    dest = VIDEOS / f"{clip}.mp4"
    if not dest.exists():
        raw = VIDEOS / f"{clip}.raw.mp4"
        download(entry["video"], raw)
        letterbox_to_library_standard(raw, dest)
        raw.unlink()
        time.sleep(0.3)                      # be polite to the dictionary's server
    frames, fps = probe(dest)
    return {"clip": clip, "frames": frames, "fps": fps,
            "path": str(dest.relative_to(paths.VIDEO_ROOT))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true",
                    help="then run build_library.py for the signs this touched")
    args = ap.parse_args()

    source = json.loads(SOURCE.read_text())
    catalog = json.loads(CATALOG.read_text())
    signs = catalog["signs"]
    by_gloss = {s["gloss"]: sid for sid, s in signs.items()}
    VIDEOS.mkdir(parents=True, exist_ok=True)

    touched, added, extended = [], 0, 0
    for i, entry in enumerate(source["signs"], 1):
        take = fetch(entry)
        keys = [norm_key(k) for k in entry["keys"]]
        sid = by_gloss.get(entry["gloss"])
        if sid is None:
            sid = slug(entry["gloss"])
            if sid in signs:
                sys.exit(f"sign id {sid!r} is taken by {signs[sid]['gloss']!r}; "
                         f"rename the gloss {entry['gloss']!r} in {SOURCE.name}")
            kind, ckeys, head, sense = classify(entry["gloss"])
            signs[sid] = {"gloss": entry["gloss"], "kind": kind, "keys": ckeys, "head": head,
                          "sense": sense, "takes": [], "source": "signbank", "page": entry["page"]}
            by_gloss[entry["gloss"]] = sid
            added += 1
        s = signs[sid]
        if all(t["clip"] != take["clip"] for t in s["takes"]):
            if s.get("source") != "signbank":
                extended += 1
                s.setdefault("signbank", entry["page"])
            s["takes"].append(take)
        s["keys"] += [k for k in keys if k not in s["keys"]]
        touched.append(sid)
        print(f"  {i}/{len(source['signs'])}  {entry['gloss']:<14} -> {sid}  ({take['clip']}, {take['frames']} frames)",
              flush=True)

    for key, sid in source.get("aliases", {}).items():
        if key not in signs[sid]["keys"]:
            signs[sid]["keys"].append(key)

    keys = {}
    for sid, s in signs.items():
        for k in s["keys"]:
            keys.setdefault(k, []).append(sid)
    catalog["keys"] = keys
    CATALOG.write_text(json.dumps(catalog, indent=1))
    print(f"{added} new signs, {extended} corpus signs given a Signbank take -> "
          f"{CATALOG.relative_to(paths.ROOT)} ({len(signs)} signs)")

    if args.build:
        subprocess.run([paths.python_with_mediapipe(), str(HERE / "build_library.py"),
                        "--takes", "all", "--only", *dict.fromkeys(touched)], check=True)
    else:
        print("extract them with:  ../.venv-1/bin/python scripts/build_library.py --takes all --only "
              + " ".join(dict.fromkeys(touched)))


if __name__ == "__main__":
    main()
