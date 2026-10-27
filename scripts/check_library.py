"""
Library integrity check: is everything the page can ask for actually there
and well-formed?  Read-only -- it never changes or regenerates a file.

    python3 scripts/check_library.py            # report; exit 1 on ERRORS
    python3 scripts/check_library.py --json out.json

ERRORS (the page would break or play garbage):
  - a sign's motion file or video is missing, unreadable or not v2
  - frame arrays disagree with n; a landmark array has the wrong length
  - coordinates outside a sane range or not finite
  - duplicate sign ids / a search key pointing at an unknown id
  - a quick pick or letter pointing at a missing sign or file
WARNINGS (plays, but worth a look):
  - signs marked review / unreliable / low quality by validate_signs.py
  - clips with no pose in most frames, or very short clips
  - letters A-Z missing from the fingerspelling set

This is AUTOMATED checking of files and numbers. It says nothing about
whether a sign is correct Auslan.
"""
import argparse
import json
import math
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from backend import paths  # noqa: E402

LIMIT = 3.0            # image-normalised coordinates live in [0,1]; allow off-frame reach


def load(p):
    with open(p) as f:
        return json.load(f)


def check_motion(path, errors, tag):
    """Returns basic stats, or None when the file is unusable."""
    try:
        raw = load(path)
    except FileNotFoundError:
        errors.append(f"{tag}: motion file missing ({os.path.relpath(path, paths.ROOT)})")
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        errors.append(f"{tag}: motion file unreadable ({e.__class__.__name__})")
        return None
    if raw.get("v") == 2:
        n, scale = raw.get("n"), raw.get("scale", 10000)
        sizes = {"pose": 33 * 2, "left_hand": 21 * 2, "right_hand": 21 * 2}
        if raw.get("face"):
            sizes["face"] = len(raw.get("face_indices", [])) * 2
        bad = 0
        for key, size in sizes.items():
            arr = raw.get(key)
            if not isinstance(arr, list) or len(arr) != n:
                errors.append(f"{tag}: '{key}' has {len(arr) if isinstance(arr, list) else 'no'} frames, n={n}")
                return None
            for fr in arr:
                if fr == 0 or fr is None:
                    continue
                if len(fr) != size:
                    errors.append(f"{tag}: a '{key}' frame has {len(fr)} values, expected {size}")
                    return None
                if any(not isinstance(v, int) or abs(v) > LIMIT * scale for v in fr):
                    bad += 1
        if bad:
            errors.append(f"{tag}: {bad} frames with coordinates out of range")
        pose_frames = sum(1 for fr in raw["pose"] if fr)
        return {"n": n, "fps": raw.get("fps"), "pose_frac": pose_frames / max(1, n)}
    # v1 (letters): frames of {x,y,z}
    frames = raw.get("frames")
    if not isinstance(frames, list) or not frames:
        errors.append(f"{tag}: no frames")
        return None
    bad = 0
    for f in frames:
        for key in ("pose", "left_hand", "right_hand"):
            for p in f.get(key) or []:
                if not all(isinstance(p.get(a), (int, float)) and math.isfinite(p[a]) and abs(p[a]) <= LIMIT
                           for a in ("x", "y")):
                    bad += 1
    if bad:
        errors.append(f"{tag}: {bad} landmarks with invalid coordinates")
    return {"n": len(frames), "fps": raw.get("fps"),
            "pose_frac": sum(1 for f in frames if f.get("pose")) / len(frames)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", help="also write the full result here")
    args = ap.parse_args()
    errors, warnings = [], []
    manifest = load(paths.MANIFEST)
    signs = manifest["signs"]

    # ids and keys
    for key, ids in manifest["keys"].items():
        for i, n in Counter(ids).items():
            if n > 1:
                errors.append(f"key {key!r} lists {i} {n} times")
        for i in ids:
            if i not in signs:
                errors.append(f"key {key!r} points at unknown id {i}")
    clips = Counter(s["clip"] for s in signs.values() if s.get("clip"))
    shared = {c: n for c, n in clips.items() if n > 1}

    status = Counter()
    short, sparse = [], []
    for sid, s in signs.items():
        status[s.get("status") or "ok"] += 1
        if not s.get("clip"):
            (errors if not s.get("failed") else warnings).append(f"sign {sid}: no clip")
            continue
        st = check_motion(os.path.join(paths.SIGN_MOTION, s["clip"] + ".json"), errors, f"sign {sid}")
        if not os.path.exists(os.path.join(paths.SIGN_VIDEOS, s["clip"] + ".mp4")):
            errors.append(f"sign {sid}: video {s['clip']}.mp4 missing")
        if st:
            if st["n"] / (st["fps"] or 30) < 0.6:
                short.append(sid)
            if st["pose_frac"] < 0.5:
                sparse.append(sid)

    # fingerspelling
    letters = load(paths.LETTERS)
    missing_letters = [ch for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if ch not in letters]
    if missing_letters:
        warnings.append(f"letters missing from the fingerspelling set: {''.join(missing_letters)}")
    for ch, e in letters.items():
        check_motion(os.path.join(paths.ROOT, e["motion"]), errors, f"letter {ch}")
        if not os.path.exists(os.path.join(paths.ROOT, e["video"])):
            errors.append(f"letter {ch}: video missing")

    # quick picks and phrases
    for name, e in load(paths.QUICK_PICKS).items():
        if e.get("library") and e["library"] not in signs:
            errors.append(f"quick pick {name}: unknown sign {e['library']}")
        for k in ("motion", "video"):
            if e.get(k) and not os.path.exists(os.path.join(paths.ROOT, e[k])):
                errors.append(f"quick pick {name}: {k} file missing")

    if status["review"]:
        warnings.append(f"{status['review']} signs flagged 'review' by automated tracking checks")
    if status["unreliable"]:
        warnings.append(f"{status['unreliable']} signs 'unreliable' (typed text fingerspells them)")
    if short:
        warnings.append(f"{len(short)} clips shorter than 0.6 s")
    if sparse:
        warnings.append(f"{len(sparse)} clips with a pose in under half their frames: {', '.join(sparse[:10])}")

    print(f"signs {len(signs)} · ok {status['ok']} · review {status['review']} · unreliable {status['unreliable']}"
          f" · letters {len(letters)}/26 · clips shared by several ids {len(shared)}")
    for w in warnings:
        print("WARNING", w)
    for e in errors[:200]:
        print("ERROR  ", e)
    if len(errors) > 200:
        print(f"ERROR   ... and {len(errors) - 200} more")
    print("OK: no integrity errors" if not errors else f"{len(errors)} integrity errors")
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"errors": errors, "warnings": warnings, "status": status,
                       "short": short, "sparse": sparse, "shared_clips": shared}, f, indent=1)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
