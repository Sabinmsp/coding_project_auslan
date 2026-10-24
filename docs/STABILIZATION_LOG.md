# Stabilization log (approved tasks 1-4)

Every change made during the stabilization phase, why, and how it was
checked. The original workspace was not modified.

## Operations outside the code

| what | detail |
|---|---|
| stopped servers 8001, 8002, 8004 | verified first: 8001/8002 = the original folder's old app (`auslan_2d_demo/serve.py`), 8004 = this project's `dist/`. 8003 (this app) kept running and still serves it |
| fingerspelling backup | `~/auslan-backups/fingerspelling_2026-10-24.tar.gz` (82 MB): `assets/fingerspelling/` + `datasets/processed/fingerspell_letters/`. Verified by restoring to a temp folder: 127/127 files byte-identical |
| Git | repository initialised in `auslan-ai-clean/` (branch `main`); `.gitignore` excludes regenerable media, logs, QA images, `dist/`, experiment binaries; the 5 dataset symlinks are tracked as links |

## Commits

| commit | content |
|---|---|
| `6461138` | initial snapshot of the working application (126 files, 11 MB) |
| `feea04d` | quality indicators, unreliable-sign safeguards, test expansion, rapid-switching fix |
| (next) | review sample, this log, final library state after extraction |

## Code changes

| file | change | why |
|---|---|---|
| `frontend/index.html` | four states with icon + word on every plan chip (✓ Sign / ⚠ Check / ✋ Fingerspelled / — Omitted), a legend stating that ✓ means *automated checks passed* and nothing is verified by Auslan users, a per-sentence summary | viewers could not tell solid signs from doubtful ones; colour alone is not accessible |
| `frontend/index.html` | quick picks: an `unreliable` sign plays fingerspelled (button marked ⚠); choosing it from a step's menu plays it with a red warning on the stage | unreliable signs must not play without a visible warning |
| `frontend/index.html` | captions read the plan of the timeline being drawn (`tl.plan`) | bug found by the new rapid-switching test: TypeError on every frame while a new sentence loaded |
| `frontend/index.html` | stage caption limited to one line | it ran under the warning box |
| `frontend/src/planner.js` | gloss lines fingerspell `unreliable` signs; sign steps carry `status` explicitly | same rule on every route |
| `frontend/src/planner.js` | omitted words described as "omitted by the current planner" (not "no sign in Auslan") | the omission is a choice of these rules, not a fact about Auslan |
| `tests/browser/` | browser tests moved into the project (`cdp.py`, `test_behaviour.py`) + new `test_robustness.py` | they lived outside the project and could not be re-run |
| `tests/test_reliability.mjs` | failed extraction, missing motion file, whole-library unreliable filtering, playback continuity on real clips | gaps identified in NEXT_STEPS |
| `tests/test_pipeline.py` | failed-extraction manifest test (uses a temporary manifest, never the real one) | gap |
| `tests/run_all.sh` | one command for every suite | reproducibility |
| `docs/REVIEW_SAMPLE.md` | 20 review signs, reproducible sample, suggestions only | task 4 |

No thresholds were changed. No sign was reclassified. No 3D, framework, or
LLM work was added. No files were deleted.

## Tests at the time of the second commit

`sh tests/run_all.sh`: 40 node + 16 python + 9 LLM-validation tests, browser
behaviour (23 checks) and robustness (15 checks) -- all passing. These test
the engineering only; they say nothing about whether the signing is correct
Auslan.
