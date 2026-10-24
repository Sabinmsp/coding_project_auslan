# Project audit

*Audited 2026-10-24. Every statement here is marked:*

- **[V]** **verified**, by reading the code or running something today.
- **[H]** from **project history**: done earlier in this project and recorded
  in the docs, but not re-run today.
- **[A]** an **assumption**, which needs checking.

## 1. Overview

An English → Auslan **2D sign-animation prototype** that runs in a web browser.

You type English. The browser turns it into a **plan**: a list of signs,
fingerspelled words and omitted words, each with a reason. It then plays
those signs on a 2D stick figure. The figure's motion was extracted from
real signers' videos with MediaPipe, and the source video plays beside it. [V]

It is **not a translator**. The plan follows English word order plus a few
rules, and no Auslan user has checked it yet. [V]

## 2. The workspace: two copies

| folder | what it is | status |
|---|---|---|
| `untitled folder 3/` (the original) | months of work: experiments, datasets, the first app `auslan_2d_demo/` | unchanged since the cleanup [V] |
| `untitled folder 3/auslan-ai-clean/` | **the project you should work in**: the app, pipeline, data links and docs | everything since the cleanup happened here [V] |
| `backup_before_cleanup_2026-10-22.tar.gz` | backup of the original before the cleanup | 639 MB [V] |

The original's `auslan_2d_demo/` holds an **older version** of the app,
without the later fixes. Don't edit it; it's kept for reference. [V]

## 3. Directory inventory (`auslan-ai-clean/`)

| folder | contents | used by the app? |
|---|---|---|
| `frontend/` | `index.html` (renderer, UI, CSS), `src/planner.js`, `src/library.js`, `src/timeline.js` | **yes**: this *is* the app [V] |
| `assets/` | `signs/` (manifest, keyword index, face topology, `motion/` + `videos/` per sign), `fingerspelling/` (A–Z, 3 pre-stitched phrases), `signs.json` (quick-pick buttons) | **yes**: loaded by the page [V] |
| `backend/` | `paths.py`, `extract_motion.py`, `serve.py` (dev server), `llm_plan.py` (optional) | build-time / dev only; nothing here runs when the page plays [V] |
| `scripts/` | build commands: `ingest`, `build_library`, `validate_signs`, `build_keywords`, `add_sign`, `qa_overlay`, `face_topology`, `build_dist`, `build_fingerspell`, `build_sentence`, `fetch_signbank_letter`, `finish_library.sh` | build-time [V] |
| `datasets/` | `raw/` (labels, dictionary, spreadsheets), `videos/rgb` and `landmarks/` (**symlinks** to 5.5 GB in the original), `processed/` (catalog, extraction log, validation, QA images, logs) | build-time [V] |
| `tests/` | 2 JS test files, 2 Python test files, 1 fixture | testing [V] |
| `experiments/` | 2D renderers, `.pt` pose experiment, 3D/Blender work, archived as-is | **no** [V] |
| `docs/` | reports and guides | — |
| `dist/` | generated deployable copy of the site | regenerated [V] |

## 4. File responsibilities (production)

| file | responsibility |
|---|---|
| `frontend/index.html` | page layout and CSS. **Renderer:** `drawFrame`, `drawFace`. **Playback loop:** `render`, `syncVideo`. **Plan editor:** `renderPlan`, `edit`. **Startup:** loads the JSON files [V] |
| `frontend/src/planner.js` | English text → plan: tokenise, contractions, numbers, longest phrase match, negation, omissions, stems, senses, keywords, word order [V] |
| `frontend/src/library.js` | loads signs on demand, caches 80, decodes the stored format, scales every signer to one body size, trims rest poses [V] |
| `frontend/src/timeline.js` | joins clips into one continuous timeline, with transitions and in-between frames [V] |
| `backend/extract_motion.py` | video → landmarks: 3 MediaPipe passes plus the hand-ownership rules (version 4) [V] |
| `backend/paths.py` | every file location in one place [V] |
| `backend/serve.py` | local web server with video seeking, and `/assets` mounted [V] |
| `scripts/ingest.py` | label file → `catalog.json`; sorts out what the brackets in sign names mean [V] |
| `scripts/build_library.py` | extracts every sign; resumable; writes the manifest [V] |
| `scripts/validate_signs.py` | checks every sign's landmarks → ok / review / unreliable [V] |
| `scripts/build_keywords.py` | dictionary keywords → `keywords.json` [V] |

## 5. Data and schemas

| file | schema | used? |
|---|---|---|
| `raw/labels/Test_ITW.json` | `{clip id: GLOSS}`, 6,430 clips → 3,215 glosses, 2 takes each | **yes**, the source of all signs [V] |
| `raw/labels/Test_{MTV,STU,SYN,TED}.json` | same shape, same 3,215 glosses | **no**: their videos aren't in the workspace [V] |
| `raw/Dictionary_Mapping.pt` | `{gloss2id: {GLOSS: {Group_Index, Keywords, State}}}` | **yes**, through `keywords.json` [V] |
| `landmarks/pose_cam1.pkl` | `{clip id: float array (frames, 136, 3)}` for all 6,430 clips | **no**: a possible shortcut that was never evaluated [V] |
| `landmarks/auslan_daily/video_*.pt` | sentence clips, 136-point poses | experiment only [V] |
| `processed/catalog.json` | `{signs: {id: {gloss, kind, keys, sense, takes}}, keys: {KEY: [ids]}}` | build-time [V] |
| `assets/signs/manifest.json` | `{signs: {id: {gloss, kind, keys, clip, q, status, flags}}, keys, counts}` | **page** [V] |
| `assets/signs/keywords.json` | `{keys: {WORD: [[id, kind, sense, position, list length]]}}` | **page** [V] |
| `assets/signs/motion/<clip>.json` | compact v2: integer x/y per frame for the pose, both hands and 128 face points, plus `src`, `pose_vis`, `xv` | **page** [V] |

## 6. Features

**Working** (verified today unless noted):

- Typing a sentence produces an explained plan, and the plan is editable. [V]
- **Sign lookup:** 3,215 sign names, plus 5,208 dictionary keywords with safety rules. [V]
- **Playable signs:** 2,012 of 3,215 extracted. **620 are flagged "review", 175 "unreliable"** (unreliable ones are fingerspelled by default). [V]
- **Fingerspelling:** A–Z, for any word without a sign. [V]
- **Playback:** sequential playback with transitions, pause, replay, scrub, speed and loop; the source video stays in sync. [V]
- **Links:** `?text=` and `?gloss=` links play a sentence directly. [V]
- **Tests:** 36 JS + 15 Python + 9 LLM-validation tests pass; the browser behaviour test passes. [V]

**Incomplete:**

- **Extraction is still running:** 2,025 of 3,207 clips re-extracted. It stalls whenever the Mac sleeps (the lid was closed for most of 23 Oct). [V]
- **No Auslan grammar** beyond two ordering rules, **no facial grammar** (raised or lowered brows, headshake), and no spatial grammar. [V]
- **Not evaluated by Deaf users.** [V]
- **3D avatar:** experiments only, not connected to the app. [V]
- **LLM planner (`llm_plan.py`):** written and validated offline, **never run live**: no API key or SDK is installed. [V]

## 7. Broken or wrong (known)

1. **The vocabulary has gaps.** PLEASE, GOOD, WANT, NAME, SORRY, TODAY and others have no sign in the corpus, so they're fingerspelled. WATER exists only as "water with a hose", and that sign isn't extracted yet. [V]
2. **11 of the 13 Signbank letters weren't needed.** The corpus has its own clips for all of them except O and Q. [V]
3. **Licensing:**
   - Signbank material is CC BY-NC-ND. The figures made from it can't be shown publicly without Signbank's permission. [V]
   - The licence of the `rgb/` corpus isn't recorded anywhere in the workspace. [V]
4. **No script rebuilds `letters.json` and the 26 letter tracks.** They came from one-off commands. [V]
5. **`ingest.py` replaces the catalog** instead of adding to it when importing a new source. [V]
6. **Archived experiments only run from the original folder.** Their paths are relative to it. [V]
7. **Four servers are running** (8001 original, 8002 original dist, 8003 clean, 8004 clean dist), which is confusing. **8003 is the current one.** [V]

## 8. Technical debt

- **`index.html` is large** (~1,000 lines): renderer, playback, editor and CSS in one file. Splitting it would make it easier to learn. [V]
- **The Python setup isn't reproducible yet.** The scripts use the original's `.venv-1`; `requirements.txt` exists but no fresh environment has been built from it. [V]
- **No version control.** It isn't a Git repository, so there's no history to roll back to except the tar backup. [V]
- **Hosting size:** a full deployment is ~1 GB (`dist/`), which is heavy for free hosting. [V]
- **Loose keyword picks:** 1,045 keywords are shared by several signs. The planner picks one and flags it, but those picks are unreviewed guesses. [V]

## 9. Dependencies

- **To view the app:** only a browser and Python 3 (for `serve.py`). [V]
- **To build signs:** Python 3.10 + MediaPipe 0.10.21, OpenCV 4.11, NumPy 1.26 (in `../.venv-1`), and ffmpeg 8.1. [V]
- **Tests:** Node 24 (no npm packages). [V]
- **Optional:** the `anthropic` SDK for `llm_plan.py`; Blender for the 3D experiments; torch/pandas/pygame for the old experiments. [V]
- **None** of the following are used: React, frameworks, databases, an API server. [V]

## 10. Data flow

**Build time** (Python, on your Mac):

```
Test_ITW.json + rgb videos
  -> ingest.py          -> catalog.json
  -> build_library.py   -> (extract_motion + validate) per clip
  -> motion/*.json + videos/*.mp4 + manifest.json
Dictionary_Mapping.pt -> build_keywords.py -> keywords.json
```

**Runtime** (browser only):

```
typed English -> planner.js -> plan -> library.js fetches the motion files
              -> timeline.js -> index.html draws the frames and syncs the video
```

## 11. Major architectural problems

1. **The data, not the code, is the limiting factor:** vocabulary gaps, ~40% of signs flagged, and no grammar data.
2. **Two copies of the app exist**, so it's easy to edit the wrong one.
3. **Validation is technical only** (landmarks, geometry), not linguistic.
4. **Licensing is unresolved** for any public release.

## 12. Recommended improvements (in order)

1. **Finish and check the library.** Let extraction run (plugged in, lid open), then review `final_status.txt`.
2. **Check with Auslan users.** Have a Deaf or Auslan-qualified person review the 50 most common signs and 20 test sentences.
3. **Resolve licensing:** confirm the corpus licence, ask Signbank, and swap the 11 letters back to the corpus's own clips.
4. **Put the project under Git**, and run one server on one port.
5. **Split `index.html`** into renderer, playback and editor modules, and add a script that rebuilds the letters.
