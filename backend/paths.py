"""
Every filesystem location the project uses, in one place.

Scripts import these instead of building paths from their own location,
so the layout is defined once. Large datasets are symlinks under
datasets/ (see docs/DATASET_REPORT.md); if the project is moved, re-point
those links and nothing else changes.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- the web app, and everything it loads at runtime (served at /assets/) ---
FRONTEND = ROOT / "frontend"
ASSETS = ROOT / "assets"
QUICK_PICKS = ASSETS / "signs.json"              # quick-pick buttons + pre-stitched phrases
SIGNS = ASSETS / "signs"                         # the sign library
MANIFEST = SIGNS / "manifest.json"
FACE_TOPOLOGY = SIGNS / "face_topology.json"
KEYWORDS = SIGNS / "keywords.json"               # English keyword -> sign ids (scripts/build_keywords.py)
SIGN_MOTION = SIGNS / "motion"                   # <clip>.json, compact v2
SIGN_VIDEOS = SIGNS / "videos"                   # <clip>.mp4, H.264
FINGERSPELLING = ASSETS / "fingerspelling"
LETTERS = FINGERSPELLING / "letters.json"
PHRASES = FINGERSPELLING / "phrases"             # pre-stitched fingerspelled phrases

# --- data -------------------------------------------------------------------
DATASETS = ROOT / "datasets"
LABELS = DATASETS / "raw" / "labels" / "Test_ITW.json"
DICTIONARY = DATASETS / "raw" / "Dictionary_Mapping.pt"   # gloss -> English keywords
VIDEO_ROOT = DATASETS / "videos"                 # catalog take paths are relative to this
RGB = VIDEO_ROOT / "rgb"                         # symlink: the 6,430 ITW clips (4.2 GB)
PROCESSED = DATASETS / "processed"
CATALOG = PROCESSED / "catalog.json"
EXTRACT_LOG = PROCESSED / "extract_log.jsonl"
QA = PROCESSED / "qa"
FINGERSPELL_SOURCE = PROCESSED / "fingerspell_letters"

# --- build --------------------------------------------------------------------
CORE_WORDS = ROOT / "scripts" / "core_words.txt"
DIST = ROOT / "dist"


def find_tool(name):
    """Absolute path to a command-line tool (ffmpeg, ffprobe).

    subprocess does not see an interactive shell's PATH additions
    (Homebrew's shellenv etc.), so a tool that works when typed into a
    terminal can be "not found" from Python. PATH first, then the common
    install locations."""
    found = shutil.which(name)
    if found:
        return found
    for c in (f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}"):
        if Path(c).exists():
            return c
    raise RuntimeError(f"{name} not found on PATH or in common install locations")


def python_with_mediapipe():
    """The interpreter that has MediaPipe: a project-local .venv if one was
    created from requirements.txt, else the workspace's original .venv-1."""
    for c in (ROOT / ".venv" / "bin" / "python", ROOT.parent / ".venv-1" / "bin" / "python"):
        if c.exists():
            return str(c)
    return sys.executable
