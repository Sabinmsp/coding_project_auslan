"""
Check every extracted sign's landmarks for the faults that make an
animation wrong, and flag unreliable signs instead of playing them silently.

    python3 scripts/validate_signs.py                 # all extracted signs -> report + manifest flags
    python3 scripts/validate_signs.py --ids pay help  # just these
    python3 scripts/validate_signs.py --files a.json b.json   # any compact motion files (compare versions)

Per sign, in frames where a hand is RAISED (signing, not resting):

  wrong_slot     a hand whose wrist is closer to the OTHER arm's wrist (and
                 not within 0.15 of its own, which touching hands can be) --
                 the left/right swap that makes one arm end in nothing
  duplicate      both slots holding the same physical hand
  detached       a hand more than 0.35 shoulder-widths from its own arm's
                 wrist (drawn floating away from the arm)
  coverage       share of raised frames with a usable hand
  dropouts       times a raised hand vanishes and comes back; longest gap
  jumps          a hand or wrist moving > 0.5 shoulder-widths in one frame
                 (1/30 s) -- faster than any sign, so a tracking error
  stretch        an arm segment longer than 1.3x its own 90th-percentile
                 length -- a limb cannot grow, so a landmark is wrong
                 (shorter is normal: foreshortening, arm toward the camera)
  low_conf       MediaPipe visibility < 0.5 for a raised arm's elbow/wrist
  short          under 0.6 s in total

Status: "unreliable" -- data is wrong (slots, duplicates, stretch, or under
half the raised frames usable); "review" -- usable but degraded; "ok".
Results go to datasets/processed/validation.json and into the manifest,
where the player shows the flags and the planner fingerspells unreliable
signs by default (a person can still choose them).
"""
import argparse
import json
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import paths  # noqa: E402

RAISED = 0.8          # wrist above this fraction of shoulder->hip = signing
ATTACHED = 0.15       # a hand this close to its own wrist is attached (touching hands)
DETACHED = 0.35
JUMP = 0.5
STRETCH = 1.3
LOW_CONF = 50
VALIDATION = paths.PROCESSED / "validation.json"


def analyse(m):
    S, A, n = m["scale"], m["width"] / m["height"], m["n"]
    pt = lambda arr, i: (arr[2 * i] / S * A, arr[2 * i + 1] / S)
    d = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])
    poses = m["pose"]
    sws = [d(pt(p, 11), pt(p, 12)) for p in poses if p]
    if not sws:
        return {"status": "unreliable", "flags": ["no pose"], "frames": n}
    sw = st.median(sws)
    segs = {"L_upper": (11, 13), "L_fore": (13, 15), "R_upper": (12, 14), "R_fore": (14, 16)}
    ref = {}
    for k, (a, b) in segs.items():
        lens = sorted(d(pt(p, a), pt(p, b)) for p in poses if p)
        ref[k] = lens[int(0.9 * (len(lens) - 1))]
    c = {"wrong_slot": 0, "duplicate": 0, "detached": 0, "jumps": 0, "stretch": 0, "low_conf": 0}
    side_stats = {}
    vis = m.get("pose_vis")
    for side, key, own, other, el in (("left", "left_hand", 15, 16, 13), ("right", "right_hand", 16, 15, 14)):
        raised = usable = dropouts = longest = gap = 0
        was_present, prev_root, prev_wrist = None, None, None
        for i, p in enumerate(poses):
            h = m[key][i]
            if not p:
                prev_root = prev_wrist = None
                continue
            shy = (pt(p, 11)[1] + pt(p, 12)[1]) / 2
            hipy = (pt(p, 23)[1] + pt(p, 24)[1]) / 2
            is_raised = hipy - shy > 1e-6 and (pt(p, own)[1] - shy) / (hipy - shy) < RAISED
            if h:
                go, gx = d(pt(h, 0), pt(p, own)) / sw, d(pt(h, 0), pt(p, other)) / sw
                if gx < go and go > ATTACHED:
                    c["wrong_slot"] += 1
                elif go > DETACHED:
                    c["detached"] += 1
                if prev_root and d(pt(h, 0), prev_root) / sw > JUMP:
                    c["jumps"] += 1
                prev_root = pt(h, 0)
            else:
                prev_root = None
            if prev_wrist and d(pt(p, own), prev_wrist) / sw > JUMP:
                c["jumps"] += 1
            prev_wrist = pt(p, own)
            if is_raised:
                raised += 1
                usable += bool(h)
                if vis and vis[i] and min(vis[i][own - 11], vis[i][el - 11]) < LOW_CONF:
                    c["low_conf"] += 1
                if h:
                    if was_present is False:
                        dropouts += 1
                    gap = 0
                else:
                    gap += 1
                    longest = max(longest, gap)
                was_present = bool(h)
        side_stats[side] = {"raised": raised, "coverage": round(usable / raised, 3) if raised else None,
                            "dropouts": dropouts, "longest_gap": longest}
    for i, p in enumerate(poses):
        if not p:
            continue
        L, R = m["left_hand"][i], m["right_hand"][i]
        if L and R and sum(d(pt(L, k), pt(R, k)) for k in range(21)) / 21 / sw < 0.15:
            c["duplicate"] += 1
        for k, (a, b) in segs.items():
            if d(pt(p, a), pt(p, b)) > STRETCH * ref[k]:
                c["stretch"] += 1

    used = [s for s in side_stats.values() if s["raised"] >= 0.2 * n]
    raised_total = max(1, sum(s["raised"] for s in used))
    cover = min((s["coverage"] for s in used), default=0.0)
    flags = []
    if c["wrong_slot"]: flags.append(f"hand in wrong slot x{c['wrong_slot']}")
    if c["duplicate"]: flags.append(f"duplicated hand x{c['duplicate']}")
    if c["stretch"] > 0.05 * n: flags.append(f"limb stretch x{c['stretch']}")
    if cover < 0.7: flags.append(f"hand coverage {cover:.0%}")
    if c["detached"] > 0.1 * raised_total: flags.append(f"hand detached from arm x{c['detached']}")
    if c["jumps"] > 2: flags.append(f"jumps x{c['jumps']}")
    if max((s["longest_gap"] for s in used), default=0) > 6: flags.append("tracking gap > 0.2 s")
    if c["low_conf"] > 0.2 * raised_total: flags.append(f"low pose confidence x{c['low_conf']}")
    if n / m["fps"] < 0.6: flags.append(f"short ({n} frames)")
    unreliable = (c["wrong_slot"] + c["duplicate"] > 0.1 * raised_total
                  or c["stretch"] > 0.1 * n or cover < 0.5 or not used)
    status = "unreliable" if unreliable else ("review" if flags else "ok")
    return {"status": status, "flags": flags, "frames": n, "xv": m.get("xv", 2),
            "coverage": round(cover, 3), "hands": side_stats, **c}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--files", nargs="*")
    args = ap.parse_args()

    if args.files:
        for f in args.files:
            r = analyse(json.loads(Path(f).read_text()))
            print(f"{Path(f).name:28} {r['status']:10} {', '.join(r['flags']) or '-'}")
        return

    manifest = json.loads(paths.MANIFEST.read_text())
    ids = args.ids or [i for i, s in manifest["signs"].items() if s["clip"]]
    results = json.loads(VALIDATION.read_text()) if VALIDATION.exists() else {}
    for sid in ids:
        s = manifest["signs"][sid]
        if not s["clip"]:
            print(f"{sid}: not extracted"); continue
        r = analyse(json.loads((paths.SIGN_MOTION / f"{s['clip']}.json").read_text()))
        results[s["clip"]] = {"sign": sid, **r}
        if args.ids:
            print(f"{sid:14} {r['status']:10} {', '.join(r['flags']) or '-'}")
    VALIDATION.write_text(json.dumps(results, indent=1))

    # flags go into the manifest, which the player reads
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_library
    counts = build_library.build_manifest(json.loads(paths.CATALOG.read_text()), build_library.read_log())
    mine = [results[manifest["signs"][i]["clip"]]["status"] for i in ids if manifest["signs"][i]["clip"]]
    print(f"validated {len(mine)}: ok {mine.count('ok')}, review {mine.count('review')}, "
          f"unreliable {mine.count('unreliable')} -> {VALIDATION.relative_to(paths.ROOT)}; manifest {counts}")


if __name__ == "__main__":
    main()
