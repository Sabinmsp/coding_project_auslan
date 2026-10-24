"""
Build a word-level sign lexicon from the Auslan_Daily_Communication dataset.

The released .pt files hold *sentence* clips, so there is no STUDENT.pt to
load. This script finds subtitles that are a single word, picks the cleanest
instance of each, and writes it out as signs/<WORD>.pt in the same structure
the dataset uses -- which is exactly what the pipeline expects.

    python build_lexicon.py --out signs
"""

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

from auslan_avatar.poseio import load_pt, save_pt

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_annotations(xlsx):
    """Parse the annotation spreadsheet without needing openpyxl."""
    z = zipfile.ZipFile(xlsx)
    shared = [
        "".join(t.text or "" for t in si.iter(NS + "t"))
        for si in ET.fromstring(z.read("xl/sharedStrings.xml"))
    ]
    sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

    rows = []
    for r in sheet.iter(NS + "row"):
        cells = {}
        for c in r.iter(NS + "c"):
            col = re.match(r"[A-Z]+", c.get("r")).group()
            v = c.find(NS + "v")
            if v is None:
                continue
            cells[col] = shared[int(v.text)] if c.get("t") == "s" else v.text
        rows.append(cells)

    header, body = rows[0], rows[1:]
    out = []
    for cells in body:
        try:
            out.append({
                "index": int(float(cells["A"])),
                "video": cells["B"],
                "subtitle": cells.get("C", ""),
                "begin": int(float(cells["D"])),
                "end": int(float(cells["E"])),
                "split": cells.get("H", ""),
            })
        except (KeyError, ValueError):
            continue
    return out


def words_of(subtitle):
    return re.findall(r"[a-z']+", (subtitle or "").lower())


def clip_quality(kps):
    """Mean confidence over the joints that matter for signing."""
    conf = kps[..., 2]
    body = conf[:, 5:11].mean()      # shoulders, elbows, wrists
    hands = conf[:, 94:136].mean() if kps.shape[1] >= 136 else 0.0
    face = conf[:, 26:94].mean() if kps.shape[1] >= 94 else 0.0
    return float(0.5 * body + 0.35 * hands + 0.15 * face)


def detect_offset(vrows, data, video):
    """
    Work out how spreadsheet row ids map to clip keys inside a .pt file.

    The numbering is not consistent between the released files (Video_1 is
    offset 0, Video_2 is offset 93), so we recover it by correlating each
    clip's frame count against its annotated frame span.
    """
    base = min(r["index"] for r in vrows)
    best = None
    for off in range(base - 3, base + 4):
        frames, spans = [], []
        for r in vrows:
            key = f"{video.lower()}_{r['index'] - off}"
            if key not in data:
                continue
            frames.append(
                np.asarray(data[key]["Annotation"]["Signer"]["KPS"]).shape[0]
            )
            spans.append(r["end"] - r["begin"])
        if len(frames) < 5:
            continue
        frames, spans = np.array(frames), np.array(spans)
        agree = float((np.abs(frames - spans) <= 2).mean())
        if best is None or agree > best[1]:
            best = (off, agree)
    return best if best else (base, 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default="Auslan_Daily_Communication.xlsx")
    ap.add_argument("--pose", nargs="+", default=["video_1.pt", "video_2.pt"])
    ap.add_argument("--out", default="signs")
    ap.add_argument("--min-frames", type=int, default=10)
    ap.add_argument("--tol", type=int, default=3,
                    help="max |clip frames - annotated span| to trust a match")
    args = ap.parse_args()

    rows = read_annotations(args.xlsx)

    archives = {}
    for path in args.pose:
        if not os.path.exists(path):
            print(f"  ! missing {path}, skipping")
            continue
        stem = os.path.splitext(os.path.basename(path))[0]     # video_1
        video = stem.replace("video_", "Video_")               # Video_1
        archives[video] = load_pt(path)
        print(f"  loaded {path}: {len(archives[video])} clips")

    offsets = {}
    for video, data in archives.items():
        vrows = [r for r in rows if r["video"] == video]
        off, agree = detect_offset(vrows, data, video)
        offsets[video] = off
        print(f"  {video}: clip index offset {off} "
              f"({agree * 100:.0f}% of clips match their annotated span)")

    # Collect single-word clips, keeping only ones we can verify.
    candidates = {}
    rejected = []
    for r in rows:
        if r["video"] not in archives:
            continue
        w = words_of(r["subtitle"])
        if len(w) != 1:
            continue
        word = w[0].upper()
        key = f"{r['video'].lower()}_{r['index'] - offsets[r['video']]}"
        data = archives[r["video"]]
        if key not in data:
            continue
        kps = np.asarray(
            data[key]["Annotation"]["Signer"]["KPS"], dtype=np.float64
        )
        span = r["end"] - r["begin"]
        drift = abs(int(kps.shape[0]) - span)
        if drift > args.tol:
            rejected.append((word, key, int(kps.shape[0]), span))
            continue
        if kps.shape[0] < args.min_frames:
            continue
        candidates.setdefault(word, []).append({
            "key": key, "kps": kps, "video": r["video"],
            "score": clip_quality(kps), "frames": int(kps.shape[0]),
            "subtitle": r["subtitle"], "index": r["index"], "drift": drift,
        })

    if rejected:
        print(f"\n  {len(rejected)} single-word clip(s) rejected "
              f"(frame count disagrees with annotation):")
        for word, key, n, span in rejected:
            print(f"    {word:<10} {key:<14} {n}f vs annotated {span}f")

    os.makedirs(args.out, exist_ok=True)
    manifest = {"entries": {}, "source": "Auslan_Daily_Communication"}

    print(f"\n  {len(candidates)} distinct single-word signs verified\n")
    for word, options in sorted(candidates.items()):
        best = max(options, key=lambda o: (o["score"], o["frames"]))
        payload = {
            "Name": word,
            "Annotation": {"Signer": {"KPS": best["kps"]}},
            "Source": {
                "video": best["video"],
                "clip": best["key"],
                "row": best["index"],
                "frames": best["frames"],
            },
        }
        path = os.path.join(args.out, f"{word}.pt")
        save_pt(payload, path)
        manifest["entries"][word] = {
            "file": f"{word}.pt",
            "source_clip": best["key"],
            "frames": best["frames"],
            "quality": round(best["score"], 3),
            "alternatives": len(options),
        }
        print(f"    {word:<10} {best['frames']:>3}f  q={best['score']:.3f}  "
              f"from {best['key']}  (drift {best['drift']}f, "
              f"{len(options)} candidate(s))")

    with open(os.path.join(args.out, "lexicon.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"\n  wrote {len(manifest['entries'])} signs to {args.out}/")


if __name__ == "__main__":
    main()
