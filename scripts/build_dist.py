"""
Produce dist/ -- a deployable copy of the 2D demo, with the motion JSON
slimmed to what the browser actually reads.

    python3 build_dist.py

The raw motion/*.json files are built for BOTH pipelines, so they carry a
lot the 2D player never touches:

  pose_world          33 landmarks x 4 floats per frame -- used only by
                      the 3D retargeter, never by the 2D canvas
  visibility          MediaPipe's per-landmark confidence; the 2D player
                      draws every point regardless
  *_hand_source       provenance (holistic / crop / interpolated), useful
                      when debugging extraction, not at playback
  float precision     ~16 significant digits, e.g. 0.5118429660797119,
                      on a 512px-wide canvas. 4 decimal places is 0.05px
                      -- already finer than a pixel.

Stripping those is lossless AS FAR AS THE 2D PLAYER IS CONCERNED. The
originals in motion/ are left untouched, since the 3D pipeline and any
re-extraction still need them.

fingerspell_letters/ is excluded entirely: it is build-time source for
build_fingerspell.py / build_sentence.py, never fetched by the page.

dist/ mirrors the URL space the page uses -- frontend/ at the root, assets/
under /assets/ -- which is also how backend/serve.py serves the project in
development, so nothing is rewritten on the way.

Only files the page can actually request are copied: frontend/, the
motion/video of each pre-stitched phrase in assets/signs.json and each
letter in assets/fingerspelling/letters.json, and from assets/signs/ the
manifest, face topology, and the motion + video of every sign the manifest
marks available. Build-side files (catalog, extraction log, QA sheets) live
in datasets/processed/ and never ship. Library motion is already in the
compact v2 format, so it is copied as-is.

    python3 scripts/build_dist.py
    python3 scripts/build_dist.py --small-videos   # re-encode library reference
                                                   # videos at 240px for hosting
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import paths  # noqa: E402

DIST = paths.DIST
PRECISION = 4


def round_landmark(lm):
    """Keep x/y/z at canvas-relevant precision; drop visibility."""
    out = {"x": round(lm["x"], PRECISION), "y": round(lm["y"], PRECISION)}
    if "z" in lm:
        out["z"] = round(lm["z"], PRECISION)
    return out


def slim_motion(data):
    frames = []
    for f in data["frames"]:
        slim = {}
        if f.get("pose"):
            slim["pose"] = [round_landmark(p) for p in f["pose"]]
        for hand in ("left_hand", "right_hand"):
            if f.get(hand):
                slim[hand] = [round_landmark(p) for p in f[hand]]
        frames.append(slim)

    out = {
        "fps": data["fps"],
        "width": data["width"],
        "height": data["height"],
        "frames": frames,
    }
    # fingerspelling boundary metadata, if present -- the UI needs these
    for key in ("letters", "words"):
        if key in data:
            out[key] = data[key]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--small-videos", action="store_true",
                    help="re-encode reference videos at 240px (library, letters and phrases)")
    ap.add_argument("--signs-from", metavar="FILE",
                    help="partial build: only the signs the planner needs for the text in FILE "
                         "(e.g. scripts/web_demo.txt); the rest are marked 'not included in this web demo'")
    ap.add_argument("--no-videos", action="store_true",
                    help="motion-only build: no reference videos at all (playback never needs them)")
    ap.add_argument("--asset-base", default="", metavar="URL",
                    help="serve assets/ from this origin (a CDN / R2 bucket) instead of the site itself")
    args = ap.parse_args()
    ffmpeg = paths.find_tool("ffmpeg") if args.small_videos and not args.no_videos else None

    def copy_video(src, dst):
        if args.no_videos:
            return
        if ffmpeg:
            subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(src), "-vf", "scale=-2:240",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(dst)],
                           check=True)
        else:
            shutil.copy2(src, dst)

    subset = None
    if args.signs_from:
        node = shutil.which("node") or next(iter(sorted(Path.home().glob(".nvm/versions/node/*/bin/node"))), None)
        if not node:
            raise SystemExit("--signs-from needs Node.js (it runs the app's planner)")
        out = subprocess.run([str(node), str(paths.ROOT / "scripts" / "collect_sign_ids.mjs"), args.signs_from],
                             check=True, capture_output=True, text=True).stdout
        subset = set(json.loads(out))
        print(f"partial build: {len(subset)} signs needed by {args.signs_from}")

    if DIST.exists():
        shutil.rmtree(DIST)

    # the app itself. Omitting a fetched file breaks the page silently: no
    # manifest = no signs, no letters.json = nothing can be fingerspelled,
    # no src/ = nothing runs at all.
    shutil.copytree(paths.FRONTEND, DIST)
    for src in (paths.QUICK_PICKS, paths.LETTERS):
        dst = DIST / src.relative_to(paths.ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # letters + pre-stitched phrases: their JSON entries hold web paths
    # (assets/...), which are also their paths inside the project
    signs = json.loads(paths.QUICK_PICKS.read_text())
    letters = json.loads(paths.LETTERS.read_text())
    entries = [e for e in signs.values() if e.get("motion")] + list(letters.values())
    wanted_motion = sorted({e["motion"] for e in entries})
    wanted_video = sorted({e["video"] for e in entries})
    missing = [w for w in wanted_motion + wanted_video if not (paths.ROOT / w).is_file()]
    if missing:
        raise SystemExit(f"referenced but missing: {missing}")

    before = after = 0
    for rel in wanted_motion:
        src, dest = paths.ROOT / rel, DIST / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        slim = slim_motion(json.loads(src.read_text()))
        # separators= removes JSON's default spaces after : and ,
        dest.write_text(json.dumps(slim, separators=(",", ":")))
        before += src.stat().st_size
        after += dest.stat().st_size
        print(f"  {src.name:24} {src.stat().st_size/1e6:7.1f} MB -> "
              f"{dest.stat().st_size/1e6:6.1f} MB")

    video_bytes = 0
    for rel in wanted_video:
        dest = DIST / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        copy_video(paths.ROOT / rel, dest)
        video_bytes += dest.stat().st_size if dest.exists() else 0

    # ---- the sign library ----
    dlib = DIST / paths.SIGNS.relative_to(paths.ROOT)
    (dlib / "motion").mkdir(parents=True)
    (dlib / "videos").mkdir(parents=True)
    for src in (paths.MANIFEST, paths.FACE_TOPOLOGY, paths.KEYWORDS):
        shutil.copy2(src, dlib / src.name)
    manifest = json.loads(paths.MANIFEST.read_text())
    if subset is not None:
        # signs left out stay in the manifest (the planner still knows they
        # exist and offers them, disabled) but have no clip, and the page
        # says why in words: "not included in this web demo"
        for sid, s in manifest["signs"].items():
            if sid not in subset and s.get("clip"):
                s["clip"] = None
                s["web_excluded"] = True
        manifest["unavailable_text"] = "not included in this web demo"
        shipped = [s for s in manifest["signs"].values() if s.get("clip")]
        manifest["counts"]["available"] = len(shipped)
        for k in ("review", "unreliable"):
            manifest["counts"][k] = sum(1 for s in shipped if s.get("status") == k)
    if args.no_videos:
        manifest["videos"] = False          # the page hides its video panel
    if subset is not None or args.no_videos:
        (dlib / paths.MANIFEST.name).write_text(json.dumps(manifest, separators=(",", ":")))
    if args.asset_base:
        # assets/ is uploaded to the CDN separately; the site deploy leaves it out
        (DIST / ".vercelignore").write_text("assets/\n")
        page = DIST / "index.html"
        page.write_text(page.read_text().replace('<meta name="asset-base" content="">',
                                                 f'<meta name="asset-base" content="{args.asset_base}">', 1))
    clips = sorted({s["clip"] for s in manifest["signs"].values() if s["clip"]})
    lib_motion = lib_video = 0
    for clip in clips:
        m_src, v_src = paths.SIGN_MOTION / f"{clip}.json", paths.SIGN_VIDEOS / f"{clip}.mp4"
        shutil.copy2(m_src, dlib / "motion" / m_src.name)
        lib_motion += m_src.stat().st_size
        v_dst = dlib / "videos" / v_src.name
        copy_video(v_src, v_dst)
        lib_video += v_dst.stat().st_size if v_dst.exists() else 0

    # caching: motion and video files change only when a sign is re-extracted,
    # so browsers and the CDN keep them a day and revalidate in the background
    # for a week; the small index files are revalidated on every load, so a
    # redeploy is picked up at once. CORS on assets/ so the files also work
    # when served from a separate CDN origin (--asset-base).
    MEDIA = "public, max-age=86400, stale-while-revalidate=604800"
    INDEX = ["/assets/signs/manifest.json", "/assets/signs/keywords.json",
             "/assets/fingerspelling/letters.json", "/assets/signs.json"]
    rules = ([("/assets/*", [("Access-Control-Allow-Origin", "*")]),
              ("/assets/*.json", [("Content-Type", "application/json"), ("Cache-Control", MEDIA)]),
              ("/assets/*.mp4", [("Content-Type", "video/mp4"), ("Cache-Control", MEDIA)])]
             + [(u, [("Cache-Control", "no-cache")]) for u in INDEX])
    (DIST / "_headers").write_text("".join(f"{u}\n" + "".join(f"  {k}: {v}\n" for k, v in h) for u, h in rules))
    (DIST / "netlify.toml").write_text('[build]\n  publish = "."\n' + "".join(
        f'\n[[headers]]\n  for = "{u}"\n  [headers.values]\n' + "".join(f'    {k} = "{v}"\n' for k, v in h)
        for u, h in rules))

    # the optional AI summary as a Vercel Python function (other static hosts
    # simply don't run it, and the page falls back to its offline summary)
    (DIST / "api").mkdir(exist_ok=True)
    shutil.copy2(paths.ROOT / "backend" / "api_summarize.py", DIST / "api" / "summarize.py")
    shutil.copy2(paths.ROOT / "backend" / "summarize_llm.py", DIST / "api" / "_summarize_llm.py")
    (DIST / "requirements.txt").write_text("anthropic\n")

    # Vercel: same headers; cleanUrls off so /index.html and ?text= links work as-is
    # (Vercel applies matching rules in order, later ones winning)
    vsrc = lambda u: u.replace("*.json", "(.*)\\.json").replace("*.mp4", "(.*)\\.mp4").replace("/*", "/(.*)")
    (DIST / "vercel.json").write_text(json.dumps({"headers": [
        {"source": vsrc(u), "headers": [{"key": k, "value": v} for k, v in h]} for u, h in rules]}, indent=1) + "\n")

    files = [p for p in DIST.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    per_sign = (lib_motion + lib_video) / max(1, len(clips))
    print()
    print(f"letters + phrases: motion {before/1e6:.1f} MB -> {after/1e6:.1f} MB, "
          f"videos {video_bytes/1e6:.1f} MB")
    print(f"library: {len(clips)} signs, motion {lib_motion/1e6:.1f} MB, "
          f"videos {lib_video/1e6:.1f} MB"
          + (" (re-encoded 240px)" if ffmpeg else ""))
    print(f"DIST TOTAL:  {total/1e6:.1f} MB in {len(files)} files")
    n_all = manifest["counts"]["signs"]
    if len(clips) < n_all:
        print(f"  at {per_sign/1e3:.0f} KB/sign, all {n_all} signs would be "
              f"~{(total + per_sign * (n_all - len(clips)))/1e9:.2f} GB")


if __name__ == "__main__":
    main()
