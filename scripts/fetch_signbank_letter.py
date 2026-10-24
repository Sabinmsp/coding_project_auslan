"""
Fetch one fingerspelling letter from the Auslan Signbank dictionary and
drop it into datasets/processed/fingerspell_letters/, ready for build_fingerspell.py /
build_sentence.py.

    python scripts/fetch_signbank_letter.py U
    python scripts/fetch_signbank_letter.py U --slug U-2      # if -1 isn't the sign you want

This automates the exact steps done by hand for O and Q:

    dictionary page  ->  raw <source src=...mp4> in the HTML
                     ->  download
                     ->  letterbox to this library's 512x408
                         (scale+pad, never a stretch -- distorting the
                         signer's proportions would corrupt every
                         downstream angle measurement)
                     ->  extract_motion.py (the same 3-pass pipeline
                         every other letter goes through)

WHY NOT WebFetch: it converts the page to markdown and summarises it,
which silently drops <video>/<source> tags -- on the O and Q lookups it
reported "no video file URLs found" for pages that had one right in the
HTML. Fetching the raw HTML directly and grepping for <source src=...>
is what actually finds it.

LICENSE: Signbank's own content is CC BY-NC-ND 4.0 (non-commercial,
no-derivatives). Fine for a personal/educational demo with attribution;
re-check before anything public-facing or commercial -- extracting
motion landmarks and redrawing them is arguably a derivative work.

Letters already covered by this project's OWN dataset (rgb/) should stay
that way; this script is only for filling the gaps that dataset doesn't
have (checked: O, Q, and now U, R, M, F, C are not in it either).
"""
import argparse
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import paths  # noqa: E402

LETTERS_DIR = paths.FINGERSPELL_SOURCE
TARGET_W, TARGET_H = 512, 408   # this library's standard, set by the rgb/ clips

# subprocess.run() does not inherit an interactive shell's PATH additions
# (Homebrew's shellenv, etc.), so a plain "ffmpeg" can fail here even
# though it works fine typed directly into a terminal. Resolve a real
# path once, checking common install locations as a fallback.
FFMPEG = paths.find_tool("ffmpeg")

USER_AGENT = "Mozilla/5.0"


def fetch_source_url(letter, slug):
    url = f"https://auslan.org.au/dictionary/words/{slug}.html"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")

    match = re.search(r'<source src="([^"]+\.mp4)"', html)
    if not match:
        raise RuntimeError(
            f"No <source ...mp4> found on {url}. Either this letter has no "
            f"dictionary video, or the slug is wrong -- try --slug {letter}-2 "
            f"or search auslan.org.au/dictionary/search/?query={letter} by hand.")
    return url, match.group(1)


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    data = urllib.request.urlopen(req, timeout=30).read()
    dest.write_bytes(data)
    return len(data)


def letterbox_to_library_standard(src, dest):
    subprocess.run([
        FFMPEG, "-y", "-v", "error", "-i", str(src),
        "-vf", f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
               f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=black",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
        "-movflags", "+faststart", "-an", str(dest),
    ], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("letter", help="Single letter, e.g. U")
    parser.add_argument("--slug", default=None,
                         help="Dictionary page slug if not '{LETTER}-1' "
                              "(e.g. some letters may need -2)")
    args = parser.parse_args()

    letter = args.letter.upper()
    slug = args.slug or f"{letter}-1"

    LETTERS_DIR.mkdir(exist_ok=True)
    raw_path = LETTERS_DIR / f"{letter}_signbank_raw.mp4"
    final_path = LETTERS_DIR / f"{letter}.mp4"
    json_path = LETTERS_DIR / f"{letter}.json"

    print(f"[{letter}] looking up {slug} ...")
    page_url, video_url = fetch_source_url(letter, slug)
    print(f"[{letter}] page:  {page_url}")
    print(f"[{letter}] video: {video_url}")

    size = download(video_url, raw_path)
    print(f"[{letter}] downloaded {size/1e6:.1f} MB -> {raw_path.name}")

    letterbox_to_library_standard(raw_path, final_path)
    print(f"[{letter}] letterboxed to {TARGET_W}x{TARGET_H} -> {final_path.name}")

    print(f"[{letter}] extracting motion (this runs MediaPipe, ~15-30s)...")
    # the project's venv, not sys.executable -- system python has neither
    # mediapipe nor opencv installed
    subprocess.run([
        paths.python_with_mediapipe(), str(paths.ROOT / "backend" / "extract_motion.py"),
        str(final_path), str(json_path),
    ], check=True)

    print(f"[{letter}] DONE -> {json_path.name}")


if __name__ == "__main__":
    main()
