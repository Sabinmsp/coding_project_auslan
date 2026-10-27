# Auslan AI — 2D sign animation

Type English; the app proposes an Auslan sign sequence, lets you review and
correct it, and plays it on a 2D figure driven by recorded signers' motion,
with the source video alongside.

This is the cleaned-up project. The original workspace (`../`) is unchanged;
what moved where, and why, is in [docs/CLEANUP_REPORT.md](docs/CLEANUP_REPORT.md).

## Start

```sh
python3 backend/serve.py 8003     # http://localhost:8003
```

Code Fair notes (what changed, test results, limits, deploying):
[docs/CODE_FAIR_REPORT.md](docs/CODE_FAIR_REPORT.md).

Needs nothing but Python 3 to view. `?text=I go home tomorrow` in the URL
plans and plays a sentence; `?gloss=hello fs:SABIN` plays an exact sign
sequence.

Building signs needs the venv in [requirements.txt](requirements.txt)
(MediaPipe 0.10.21, OpenCV, NumPy) plus ffmpeg. The original workspace's
`../.venv-1` already has them; the commands below use it.

## Layout

```
frontend/      the web app: index.html + src/ (planner, library, timeline)
assets/        what the app loads: signs/ (library), fingerspelling/, signs.json
backend/       Python modules: extract_motion, paths, serve (dev server), llm_plan
scripts/       commands: ingest, build_library, add_sign, qa_overlay, build_dist, ...
datasets/      raw/ labels, videos/ + landmarks/ (linked), processed/ (catalog, logs, QA)
tests/         JS + Python tests
experiments/   2d/ and 3d/ prior work, archived as-is -- not used by the app
docs/          structure, pipeline, datasets, deploy, cleanup report
```

Full map: [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md). Every file in the whole workspace, and what is safe to remove: [docs/WORKSPACE_MAP.md](docs/WORKSPACE_MAP.md).

## Common tasks

Run from this folder. `V=../.venv-1/bin/python` below.

| task | command |
|---|---|
| make one word's sign playable | `python3 scripts/add_sign.py elephant` |
| continue extracting the whole corpus (resumable, ~6 h) | `caffeinate -i $V scripts/build_library.py` |
| rebuild the English keyword index (after re-ingesting) | `python3 scripts/build_keywords.py` |
| check every sign's landmarks for faults | `python3 scripts/validate_signs.py` |
| re-extract flagged signs from their second take | `$V scripts/build_library.py --takes rescue` |
| finish a full run: validate, rescue, re-validate, rebuild `dist/`, write `datasets/processed/final_status.txt` | `caffeinate -i sh scripts/finish_library.sh` |
| check extraction against the video | `$V scripts/qa_overlay.py hello --random 12 --low` |
| add videos from a folder (`thank_you.mp4` -> THANK YOU) | `python3 scripts/ingest.py --folder DIR` then `$V scripts/build_library.py` |
| extract one video to the original motion format | `$V backend/extract_motion.py clip.mp4 out.json` |
| run the tests | see below |
| check every library file is present and well-formed (read-only) | `python3 scripts/check_library.py` |
| build the deployable site (full library, ~1 GB) | `python3 scripts/build_dist.py` -> `dist/` ([docs/DEPLOY.md](docs/DEPLOY.md)) |
| build the small web demo (~75 MB, fits Vercel Hobby) | `python3 scripts/build_dist.py --signs-from scripts/web_demo.txt --small-videos` |

How the parts connect, and how to add a sign or process a new video in
detail: [docs/PIPELINE.md](docs/PIPELINE.md). Why some animations looked
wrong and what fixed them: [docs/ANIMATION_DEBUG_REPORT.md](docs/ANIMATION_DEBUG_REPORT.md).

## Tests

```sh
python3 backend/serve.py 8003 &      # the browser suites need the app running
sh tests/run_all.sh 8003             # everything below, in one go
```

| suite | what |
|---|---|
| `node --test tests/*.mjs` (55) | planner, keywords, library, timeline, reliability, playback |
| `scripts/check_library.py` | every motion file, video, letter and quick pick present and well-formed |
| `tests/test_pipeline.py` (16) | catalog, keywords, ownership, validator, lossless format |
| `tests/test_llm_plan.py` (9) | LLM plan validation, offline |
| `tests/browser/` (3 suites, headless Chrome) | behaviour, failure paths, controls + end-to-end checklist |

These test the engineering. None of them says whether the signing is
correct Auslan.

## Data, in one paragraph

3,215 Auslan signs, two recorded takes each: 6,430 clips in
`datasets/videos/rgb`, labelled by `datasets/raw/labels/Test_ITW.json`.
**All 3,215 are extracted and playable (2026-10-26)**: 2,543 pass the
automated checks, 602 are flagged for review and 70 are unreliable (typed
text fingerspells those). Every other word is fingerspelled from 26 letter clips.
Details, including two large unused data sources:
[docs/DATASET_REPORT.md](docs/DATASET_REPORT.md).

## Limitations

The sign plan is rule-based and has not been reviewed by an Auslan user.
The figure cannot add grammatical facial expressions. Many everyday words
(GOOD, WANT, NAME, PLEASE, SORRY, TODAY...) have no sign in this corpus and
are fingerspelled. Nothing here has yet been evaluated with Deaf viewers.
13 fingerspelling letters come from Auslan Signbank (CC BY-NC-ND 4.0:
non-commercial, attribution); the licence of the `rgb/` corpus should be
confirmed before public deployment.
