# SignBridge: an Auslan-supported document assistant (prototype)

Drop in a long PDF (a university handbook, a notice, a bill). The app reads
it in the browser, picks out the key points with their page numbers, puts
them in plainer English, and lets you select any point to see it played with
recorded Auslan signs on a 2D figure, with the source video alongside.
Words without a sign are fingerspelled and labelled.

It is an **accessibility prototype, not an Auslan translator**: signs follow
a simplified rule-based order, and nothing has been checked by Deaf signers.

```
PDF ─► text per page (pdf.js, in the browser) ─► key points + pages (offline summariser)
    ─► [optional] plain-English rewrite by Claude, every fact re-checked against the PDF
    ─► select a point ─► sign plan (planner.js) ─► sign library / fingerspelling ─► 2D figure
```

The original workspace (`../`) is unchanged. Old experiments were removed
from this project on 2026-10-27 (their originals remain in `../`); see
[docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md).

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
datasets/      raw/ labels, videos/ + landmarks/ (linked), processed/ (catalog, extract log, validation)
tests/         JS + Python + browser tests, fixtures
docs/          how it works, pipeline, deploy, datasets, reports
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
| summarise a PDF's key excerpts with Claude, from the command line | `python3 backend/summarize_llm.py excerpts.json` (needs `pip install anthropic` + `ANTHROPIC_API_KEY`) |
| regenerate the test PDFs | `python3 tests/fixtures/make_pdfs.py` |
| check every library file is present and well-formed (read-only) | `python3 scripts/check_library.py` |
| build the deployable site (full library, ~1 GB) | `python3 scripts/build_dist.py` -> `dist/` ([docs/DEPLOY.md](docs/DEPLOY.md)) |
| build the full library without any videos (483 MB; playback needs none) | `python3 scripts/build_dist.py --no-videos` |
| ... with assets served from a CDN | `python3 scripts/build_dist.py --no-videos --asset-base https://signs.example.com` ([docs/DEPLOY.md](docs/DEPLOY.md)) |
| extract the 1,950 not-yet-needed second recordings (resumable, ~2.6 h) | `caffeinate -i $V scripts/build_library.py --takes all` |
| build the small web demo (~88 MB, fits Vercel Hobby) | `python3 scripts/build_dist.py --signs-from scripts/web_demo.txt --small-videos` |

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
| `node --test tests/*.mjs` (66) | planner, keywords, library, timeline, reliability, playback, document summary |
| `scripts/check_library.py` | every motion file, video, letter and quick pick present and well-formed |
| `tests/test_pipeline.py` (16) | catalog, keywords, ownership, validator, lossless format |
| `tests/test_llm_plan.py` (9) | LLM plan validation, offline |
| `tests/test_summarize_llm.py` (9) | AI summary endpoint, offline (stubbed model) |
| `tests/browser/` (5 suites, headless Chrome) | behaviour, failure paths, controls + end-to-end, PDF → key points → signing, motion-only playback |

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
