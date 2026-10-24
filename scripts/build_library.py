"""
datasets/processed/catalog.json -> extracted, playable sign library (assets/signs/).

    python3 scripts/build_library.py --limit 5            # pilot: first 5 signs
    python3 scripts/build_library.py --only hello finish  # specific sign ids
    python3 scripts/build_library.py                      # every sign, primary take
    python3 scripts/build_library.py --takes all          # also each sign's 2nd take
    python3 scripts/build_library.py --takes rescue       # 2nd take only where the
                                                  #   1st extracted badly
    python3 scripts/build_library.py --manifest-only      # rebuild manifest from log

Resumable: a clip already in datasets/processed/extract_log.jsonl is skipped, so this
can be stopped and re-run at any point. Takes are queued primary-first, so
every sign becomes playable before any second take is spent on.

ORDER. At ~9 clips/min on an M1 the full primary pass is ~6 hours, so the
queue is ordered by usefulness, not alphabet: scripts/core_words.txt (everyday
vocabulary for the bills/notices/health use case) first, then other plain
single-word signs, then multi-word, then specific senses. The manifest is
rebuilt every 200 clips, so the library is usable from the first hour.

Per clip it writes
  assets/signs/motion/<clip>.json   compact landmarks (format below)
  assets/signs/videos/<clip>.mp4    H.264 reference video (the rgb/ originals
                                    are MPEG-4 Part 2, which browsers cannot decode)
and appends one line of quality stats to datasets/processed/extract_log.jsonl. The
manifest is then built from the catalog + log: for each sign, the take
with the best extraction quality, and an "available" flag that is true
only if its motion file really exists.

COMPACT FORMAT (v2). The 2D player reads x/y only, so z and pose_world are
not stored. Pose visibility (MediaPipe's own confidence, 0-100) is kept for
the six arm joints only -- shoulders, elbows, wrists, landmarks 11-16 -- as
"pose_vis", for scripts/validate_signs.py; the player ignores it. Coordinates are integers in 1/10000ths of the
frame (0.05px on a 512px frame). Each track is a per-frame list holding
a flat [x0,y0,x1,y1,...] array, or 0 where that track is absent:

  {"v":2, "fps":30, "width":512, "height":408, "n":65, "scale":10000,
   "pose": [...], "left_hand": [...], "right_hand": [...], "face": [...],
   "face_indices": [...128 mesh ids...], "pose_vis": [[11..16 x6] | 0, ...],
   "src": {"left_hand": "hhhcci--h...", "right_hand": "..."}, "xv": 3}

src records each hand frame's provenance: h holistic, c wrist crop,
i interpolated across a short gap, - absent. A hand that is present but
geometrically impossible is stored as ABSENT (-), not drawn: showing a
hand inside-out is showing wrong data, which is worse than showing none.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import paths  # noqa: E402

CATALOG = paths.CATALOG
LOG = paths.EXTRACT_LOG
MANIFEST = paths.MANIFEST
MOTION, VIDEOS = paths.SIGN_MOTION, paths.SIGN_VIDEOS
find_tool = paths.find_tool
SCALE = 10000

# a hand counts as "in use" in frames where its wrist is raised above this
# fraction of the shoulder->hip distance (0 = shoulder line, 1 = hip line)
RAISED = 0.8
LOW_QUALITY = 0.7


# ---------------------------------------------------------------------
# worker side
# ---------------------------------------------------------------------
_extract = None
_validate = None


def _init_worker():
    global _extract, _validate
    os.environ.setdefault("GLOG_minloglevel", "2")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    sys.path.insert(0, str(paths.ROOT))
    from backend import extract_motion
    _extract = extract_motion
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import validate_signs
    _validate = validate_signs


def flat(points):
    out = []
    for p in points:
        out.append(round(p["x"] * SCALE))
        out.append(round(p["y"] * SCALE))
    return out


def quality(data, possible):
    """How much of the sign the extraction actually captured.

    A one-handed sign legitimately has no second hand, so raw detection
    rates mislead. What matters is: in the frames where a hand is RAISED
    (i.e. signing), was a geometrically possible hand found?"""
    frames = data["frames"]
    n = len(frames)
    pose_cov = sum(1 for f in frames if f["pose"]) / n if n else 0.0
    hands = {}
    for side, wrist in (("left", 15), ("right", 16)):
        raised = got = 0
        for i, f in enumerate(frames):
            p = f["pose"]
            if not p:
                continue
            sh = (p[11]["y"] + p[12]["y"]) / 2
            hip = (p[23]["y"] + p[24]["y"]) / 2
            if hip - sh < 1e-6:
                continue
            if (p[wrist]["y"] - sh) / (hip - sh) < RAISED:
                raised += 1
                got += possible[side][i]
        hands[side] = {"raised": raised, "coverage": round(got / raised, 3) if raised else None}
    # hands in use = raised for at least 20% of the clip
    used = [h["coverage"] for h in hands.values() if h["raised"] >= 0.2 * n]
    hand_cov = min(used) if used else 0.0
    score = round(pose_cov * hand_cov, 3)
    return {"score": score, "pose": round(pose_cov, 3), "hands_used": len(used),
            "left": hands["left"], "right": hands["right"],
            "low": score < LOW_QUALITY}


def process(job):
    clip, src, motion_out, video_out, ffmpeg = job
    t0 = time.time()
    try:
        data, stats = _extract.extract(paths.VIDEO_ROOT / src, face=True, log=lambda *a, **k: None)
        aspect = data["width"] / data["height"]
        possible = {"left": [], "right": []}
        compact = {"v": 2, "fps": data["fps"], "width": data["width"],
                   "height": data["height"], "n": len(data["frames"]), "scale": SCALE,
                   "pose": [], "left_hand": [], "right_hand": [], "face": [],
                   "face_indices": data.get("face_indices", []),
                   "src": {"left_hand": "", "right_hand": ""},
                   "pose_vis": [], "xv": _extract.EXTRACTOR_VERSION}
        rejected = {"left": 0, "right": 0}
        for f in data["frames"]:
            compact["pose"].append(flat(f["pose"]) if f["pose"] else 0)
            compact["pose_vis"].append([round(100 * f["pose"][j].get("visibility", 1.0))
                                        for j in range(11, 17)] if f["pose"] else 0)
            compact["face"].append(flat(f["face"]) if f.get("face") else 0)
            for side in ("left", "right"):
                key = f"{side}_hand"
                ok = bool(f[key]) and _extract.is_possible(f[key], side, aspect)
                possible[side].append(1 if ok else 0)
                if f[key] and not ok:
                    rejected[side] += 1
                compact[key].append(flat(f[key]) if ok else 0)
                compact["src"][key] += ({"holistic": "h", "crop": "c",
                                         "interpolated": "i"}.get(f[f"{key}_source"], "h")
                                        if ok else "-")
        motion_out.parent.mkdir(parents=True, exist_ok=True)
        tmp = motion_out.with_suffix(".tmp")
        tmp.write_text(json.dumps(compact, separators=(",", ":")))
        tmp.replace(motion_out)       # atomic: a killed run never leaves half a file

        video_out.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(paths.VIDEO_ROOT / src),
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
                            str(video_out)], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("ffmpeg: " + r.stderr.strip()[:200])

        q = quality(data, possible)
        q["rejected_hands"] = rejected
        validation = _validate.analyse(compact)
        return {"clip": clip, "ok": True, "xv": _extract.EXTRACTOR_VERSION,
                "validation": {k: validation[k] for k in ("status", "flags")},
                "n": compact["n"], "fps": data["fps"],
                "q": q, "stats": stats, "secs": round(time.time() - t0, 1),
                "bytes": motion_out.stat().st_size}
    except Exception as e:            # one bad clip must not stop 6,000
        return {"clip": clip, "ok": False, "error": f"{type(e).__name__}: {e}",
                "secs": round(time.time() - t0, 1)}


# ---------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------
def read_log():
    done = {}
    if LOG.exists():
        for line in LOG.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["clip"]] = r            # later lines win (re-runs)
    return done


def current(record):
    """Already extracted, successfully, by the current extraction logic?"""
    import importlib
    xv = importlib.import_module("backend.extract_motion").EXTRACTOR_VERSION
    return bool(record) and record["ok"] and record.get("xv", 2) == xv


STATUS_RANK = {"ok": 2, "review": 1, "unreliable": 0}


def validation_of(record, checked):
    """A clip's validation: recorded at extraction time, else from
    datasets/processed/validation.json (validate_signs.py) if it checked the
    same extraction version."""
    if record.get("validation"):
        return record["validation"]
    v = checked.get(record["clip"])
    if v and v.get("xv", 2) == record.get("xv", 2):
        return {"status": v["status"], "flags": v["flags"]}
    return None


def build_manifest(catalog, log):
    signs, keys = {}, {}
    counts = {"signs": 0, "available": 0, "low_quality": 0, "failed": 0,
              "review": 0, "unreliable": 0}
    vfile = paths.PROCESSED / "validation.json"
    checked = json.loads(vfile.read_text()) if vfile.exists() else {}
    for sid, s in catalog["signs"].items():
        counts["signs"] += 1
        good = [log[t["clip"]] for t in s["takes"]
                if t["clip"] in log and log[t["clip"]]["ok"]
                and (MOTION / f"{t['clip']}.json").exists()]
        failed = any(t["clip"] in log and not log[t["clip"]]["ok"] for t in s["takes"])
        entry = {"gloss": s["gloss"], "kind": s["kind"], "keys": s["keys"]}
        if s["sense"]:
            entry["sense"] = s["sense"]
        if good:
            rank = lambda r: STATUS_RANK.get((validation_of(r, checked) or {}).get("status"), 1)
            best = max(good, key=lambda r: (rank(r), r["q"]["score"], r["n"]))
            entry.update({"clip": best["clip"], "fps": best["fps"], "n": best["n"],
                          "q": best["q"]["score"]})
            v = validation_of(best, checked)
            if v and v["status"] != "ok":
                entry["status"], entry["flags"] = v["status"], v["flags"]
                counts[v["status"]] += 1
            if best["q"]["low"]:
                entry["low"] = True
                counts["low_quality"] += 1
            others = [r["clip"] for r in good if r["clip"] != best["clip"]]
            if others:
                entry["alt"] = others
            counts["available"] += 1
        else:
            entry["clip"] = None          # in the corpus, not yet extracted
            if failed:
                entry["failed"] = True
                counts["failed"] += 1
        signs[sid] = entry
        for k in s["keys"]:
            keys.setdefault(k, []).append(sid)
    manifest = {"v": 2, "source": catalog["source"], "counts": counts,
                "built": time.strftime("%Y-%m-%d %H:%M"),
                "signs": signs, "keys": keys}
    # atomic: the page may fetch the manifest while a long run rewrites it
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, separators=(",", ":")))
    tmp.replace(MANIFEST)
    return counts


def priority(catalog):
    """Sign ids, most useful first (see ORDER above)."""
    core = []
    path = paths.CORE_WORDS
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.startswith("#"):
                core += line.upper().split()
    # multi-word core entries ("credit card") arrive as two tokens; also
    # try each adjacent pair
    wanted = {w: i for i, w in enumerate(core)}
    for a, b in zip(core, core[1:]):
        wanted.setdefault(f"{a} {b}", wanted[a])

    def rank(item):
        sid, s = item
        k = s["keys"][0]
        if k in wanted and s["kind"] in ("plain", "phrase"):
            return (0, wanted[k], sid)
        if s["kind"] == "plain":
            return (1 if " " not in k else 2, 0, sid)
        return (3, 0, sid)
    return [sid for sid, _ in sorted(catalog["signs"].items(), key=rank)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--takes", choices=["primary", "all", "rescue"], default="primary")
    ap.add_argument("--rescue-below", type=float, default=0.85,
                    help="--takes rescue: extract the 2nd take where the 1st scored below this")
    # 4 = the M1's performance cores; measured 7 workers no faster than 4
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--manifest-only", action="store_true")
    args = ap.parse_args()

    catalog = json.loads(CATALOG.read_text())
    if args.manifest_only:
        print(build_manifest(catalog, read_log()))
        return

    ids = priority(catalog)
    if args.only:
        missing = [i for i in args.only if i not in catalog["signs"]]
        if missing:
            sys.exit(f"unknown sign ids: {missing}")
        ids = args.only
    if args.limit:
        ids = ids[:args.limit]

    done = read_log()
    queue = [(i, catalog["signs"][i]["takes"][0]) for i in ids]
    if args.takes == "all":
        queue += [(i, t) for i in ids for t in catalog["signs"][i]["takes"][1:]]
    elif args.takes == "rescue":
        def weak(i):
            r = done.get(catalog["signs"][i]["takes"][0]["clip"])
            v = (validation_of(r, {}) or {}) if r else {}
            return r and (not r["ok"] or r["q"]["score"] < args.rescue_below
                          or v.get("status") in ("review", "unreliable"))
        queue = [(i, t) for i in ids if weak(i) for t in catalog["signs"][i]["takes"][1:]]

    ffmpeg = find_tool("ffmpeg")
    jobs = [(t["clip"], t["path"], MOTION / f"{t['clip']}.json",
             VIDEOS / f"{t['clip']}.mp4", ffmpeg)
            for _, t in queue if not current(done.get(t["clip"]))]
    print(f"{len(queue)} clips requested, {len(queue) - len(jobs)} already done, "
          f"{len(jobs)} to extract on {args.workers} workers", flush=True)

    t0, finished, failed = time.time(), 0, 0
    if jobs:
        with ProcessPoolExecutor(args.workers, initializer=_init_worker) as pool, \
                open(LOG, "a") as log:
            futures = [pool.submit(process, j) for j in jobs]
            for fut in as_completed(futures):
                r = fut.result()
                log.write(json.dumps(r) + "\n")
                log.flush()
                finished += 1
                failed += not r["ok"]
                if finished % 25 == 0 or finished == len(jobs) or not r["ok"]:
                    rate = finished / (time.time() - t0)
                    eta = (len(jobs) - finished) / rate if rate else 0
                    status = "" if r["ok"] else f"  FAILED {r['clip']}: {r['error']}"
                    print(f"  {finished}/{len(jobs)}  {rate*60:.0f}/min  "
                          f"eta {eta/60:.0f} min  failed {failed}{status}", flush=True)
                if finished % 200 == 0:          # partial manifest: usable mid-run
                    build_manifest(catalog, read_log())

    counts = build_manifest(catalog, read_log())
    print(f"done in {(time.time() - t0)/60:.1f} min -> {MANIFEST.relative_to(paths.ROOT)}  {counts}")


if __name__ == "__main__":
    main()
