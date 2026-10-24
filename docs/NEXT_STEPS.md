# Next steps: five engineering tasks, by impact and risk

None of these are started. Each needs your approval first.

## 1. Put the project under Git (high impact, low risk)
**Why:** today the only way back from a mistake is a tar backup. Nothing in
`auslan-ai-clean/` or its parent folder is a Git repository (verified).

**Procedure:**
1. Extend `.gitignore` so these stay out of Git:
   - **Regenerable sign data:** `assets/signs/motion/` (305 MB) and
     `assets/signs/videos/` (386 MB). `build_library.py` recreates them.
   - **Build output and logs:** `dist/`, `datasets/processed/logs/`, `__pycache__/`.
   - **The large experiment model:** `experiments/3d/jump_3d/boy.glb` (105 MB).
2. **Keep in Git:** code, docs, tests, the small data files (labels, dictionary,
   catalog, manifest, keywords, `signs.json`, validation) and the 5 dataset
   symlinks, as links.
3. **Back up separately, outside Git:** `assets/fingerspelling/` (114 MB). It
   can't be regenerated today (see task 5). Use Git LFS, or keep it in the
   tar backup.
4. Run `git init`, check `git status` lists only the intended files, then
   make the first commit.

No secrets were found, and there are no `.env` files. Nothing is deleted.

## 2. One honest quality indicator (high impact for users, low risk)
**Why:** viewers can't tell a solid sign from a doubtful one. Today:
- the meaning sits in chip colour only, which fails accessibility;
- "low tracking" covers two different problems;
- unreliable signs can still play from quick picks (FRIEND), the gloss line
  or the menu, with only small caption text.

**Proposal: four states, each with an icon, a word and a colour:**

| state | when | today |
|---|---|---|
| ✓ **Sign** | a sign that validated `ok` | green chip |
| ⚠ **Check** | a `review` sign, an uncertain sense, or a keyword pick among several | amber or "low tracking" |
| ✋ **Fingerspelled** | no sign, sign not extracted, `unreliable`, or a loose keyword | blue chip |
| — **Not shown** | articles, the copula, punctuation | grey, struck through |

Plus a line under the plan, e.g. "4 signed · 1 to check · 2 fingerspelled ·
2 not shown", and the same label in the stage caption while that step plays.

**Code affected:** `frontend/index.html` only (chip classes, a legend, the
caption). The planner already gives every step these facts.

## 3. Bring the browser tests into the project, and fill the gaps (high impact, low risk)
**Why:** the browser behaviour test (play, pause, scrub, speed, loop, video
sync, typing) lives in a temporary folder outside the project, so you can't
re-run it.

**Gaps found:**

| area | missing test |
|---|---|
| missing words | the UI marks fingerspelled and not-shown words (after task 2) |
| failed extraction | a sign whose takes all failed is never planned as a sign; the manifest's `failed` flag |
| missing file at runtime | a motion file returns 404 mid-sentence: the rest still plays and the failure is reported |
| sequencing | fast switching between two sentences (no mixed frames from the old one) |
| playback | pause and resume during a transition; loop with speed changed |
| whole library | no typed single word auto-plays an `unreliable` sign (check every manifest key) |

**Proposal:**
- add `tests/browser/` with the existing CDP harness (Chrome, no new framework);
- add Node tests for the planner and library items;
- add a one-line `tests/run_all.sh`.

## 4. Finish the library and check the classifier (high impact, medium risk)
**Why:** 1,117 signs still need extracting, and the classification needs a
human look.

**What the numbers show** (2,012 signs available):
- 1,217 `ok`, 620 `review`, 175 `unreliable`.
- **The categories don't overlap.** Each sign has exactly one status.
- The separate "low quality" score (403 signs) falls entirely inside review
  and unreliable.
- **Unreliable** is almost always a hand missing in most signing frames (170
  of 175).
- **286 of the 620 review signs have only one flag: "tracking gap > 0.2 s".**
  That's a single hand missing for more than 6 frames. It may be too strict.
- **120 review signs are flagged "duplicated hand".** One duplicate frame is
  enough to trigger it, so palms pressed together may count.

**Proposal:**
- **Finish extraction:** keep the Mac plugged in with the lid open, and let
  `finish_library.sh` run its rescue pass.
- **Calibrate the review flag:** pick 20 review signs at random, compare each
  figure with its video (`qa_overlay.py`), and decide whether the gap
  threshold and the single-duplicate rule should change. Change thresholds
  only with that evidence.

## 5. Make the letters reproducible and the corpus's own (medium impact, low risk)
**Why:**
- No script rebuilds `letters.json` and the letter tracks.
- 11 of the 13 Signbank letters are unnecessary.
- Signbank's licence (CC BY-NC-ND) restricts public use of figures made from it.

**Proposal:** a `scripts/build_letters.py` that:
- extracts the 24 corpus letters with the current extractor;
- keeps O and Q from Signbank, credited;
- writes `letters.json`.

Then compare old and new letters side by side before switching.

**Not on this list, on purpose:** 3D, an LLM planner, new frameworks,
directory changes. Linguistic accuracy also needs Auslan users, not code.
