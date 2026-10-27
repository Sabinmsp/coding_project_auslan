# MVP checklist: demonstrable 2D prototype

State on 2026-10-26. **[x]** done and verified · **[ ]** to do · **[~]** partly done.
Automated tests check engineering, not Auslan. Nothing here claims linguistic accuracy.

## 1. Data
- [x] 3,215 signs catalogued from `Test_ITW.json`; negated/sense glosses handled safely
- [x] Extraction with the fixed extractor (v4): **3,215 / 3,215** signs playable, 0 failures (2026-10-26)
- [x] `scripts/finish_library.sh` completed: 904 signs use their better second recording; 2,543 ok / 602 review / 70 unreliable
- [ ] Human review of the `review` signs most likely to appear in demos (core words first)
- [ ] Decide what to do with signs still `unreliable` after the rescue (re-record, or leave fingerspelled)
- [ ] Swap the 11 unnecessary Signbank letters for the corpus's own letter clips (O and Q stay)
- [ ] A script that rebuilds `letters.json` and the 26 letter tracks (today: one-off, not reproducible)

## 2. Input and planning
- [x] Free-text input; contractions, numbers, phrases, negation, stems
- [x] Dictionary keywords with safety rules (no meaning flips; loose matches spelled)
- [x] Every word becomes sign / fingerspell / omit, with a reason
- [x] One clear on-screen statement in the page header: "It is not a full Auslan translation" (2026-10-27)
- [x] Every fingerspelled step says why (name / no sign / unreliable / loose match / requested)

## 3. Quality signalling
- [x] Plan chips show icon + word for each state
- [x] One consistent 4-state indicator (✓ Sign / ⚠ Check / ✋ Fingerspelled / — Omitted)
- [x] A sentence summary
- [x] Unreliable signs fingerspelled on every route; playable only from a step's menu, with a stage warning

## 4. Playback
- [x] Sequential playback, transitions, loop wrap, interpolation between recorded frames
- [x] Play / pause / replay / scrub / speed; source video in sync
- [x] Wrists joined; no redrawing while paused
- [x] Tracking drop-outs fade instead of blinking; single-frame spikes removed; compact fingerspelling (see CODE_FAIR_REPORT.md)
- [x] A sign's file failing to load mid-sentence is reported; the rest plays (tested)

## 5. Testing
- [x] 55 JS + 16 Python + 9 LLM-validation tests, library integrity check, 3 browser suites pass (2026-10-27)
- [x] Browser tests in `tests/browser/`; `sh tests/run_all.sh` runs everything
- [x] Tests for failed extraction, a missing motion file, fast switching, pause in a transition
- [x] A whole-library check: no typed word ever auto-plays an `unreliable` sign

## 6. Project hygiene
- [x] Git repository (`main`)
- [x] One server: the current app on 8003
- [ ] `requirements.txt` proven with a fresh environment

## 7. Demonstration readiness
- [ ] 10–20 demo sentences chosen, each reviewed by a Deaf or Auslan-qualified person
- [ ] Known limitations written for viewers (grammar, facial expression, missing vocabulary)
- [ ] Licensing: confirm the corpus licence; Signbank permission before any public showing
