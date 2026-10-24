# MVP checklist: demonstrable 2D prototype

State on 2026-10-24. **[x]** done and verified · **[ ]** to do · **[~]** partly done.
Automated tests check engineering, not Auslan. Nothing here claims linguistic accuracy.

## 1. Data
- [x] 3,215 signs catalogued from `Test_ITW.json`; negated/sense glosses handled safely
- [~] Extraction with the fixed extractor (v4): **2,098 / 3,215** signs, 0 failures, running
- [ ] `scripts/finish_library.sh` completes: rescue second takes, re-validate, write `final_status.txt`
- [ ] Human review of the `review` signs most likely to appear in demos (core words first)
- [ ] Decide what to do with signs still `unreliable` after the rescue (re-record, or leave fingerspelled)
- [ ] Swap the 11 unnecessary Signbank letters for the corpus's own letter clips (O and Q stay)
- [ ] A script that rebuilds `letters.json` and the 26 letter tracks (today: one-off, not reproducible)

## 2. Input and planning
- [x] Free-text input; contractions, numbers, phrases, negation, stems
- [x] Dictionary keywords with safety rules (no meaning flips; loose matches spelled)
- [x] Every word becomes sign / fingerspell / omit, with a reason
- [ ] One clear on-screen statement: "This shows Auslan signs in a simplified order. It is not a full Auslan translation."

## 3. Quality signalling (see NEXT_STEPS #2)
- [~] Plan chips are coloured by kind, but colour carries the meaning, and "low tracking" means two different things
- [ ] One consistent 4-state indicator with an icon and text on every chip and caption
- [ ] A sentence summary: "4 signed · 1 to check · 2 fingerspelled · 2 not shown"
- [ ] Unreliable signs reachable from quick picks (FRIEND today) visibly labelled before they play

## 4. Playback
- [x] Sequential playback, transitions, loop wrap, interpolation between recorded frames
- [x] Play / pause / replay / scrub / speed; source video in sync
- [x] Wrists joined; no redrawing while paused
- [ ] A clear message when a sign's file fails to load mid-sentence (the code path exists but is untested)

## 5. Testing (see NEXT_STEPS #3)
- [x] 36 JS + 15 Python + 9 LLM-validation tests pass
- [ ] Browser behaviour test moved into `tests/` (it lives outside the project today)
- [ ] Tests for failed extraction, a missing motion file, and fast switching between sentences
- [ ] A whole-library check: no typed word ever auto-plays an `unreliable` sign

## 6. Project hygiene
- [ ] Git repository (NEXT_STEPS #1)
- [ ] One server: the current app on 8003. Stop 8001, 8002 and 8004 (needs your approval)
- [ ] `requirements.txt` proven with a fresh environment

## 7. Demonstration readiness
- [ ] 10–20 demo sentences chosen, each reviewed by a Deaf or Auslan-qualified person
- [ ] Known limitations written for viewers (grammar, facial expression, missing vocabulary)
- [ ] Licensing: confirm the corpus licence; Signbank permission before any public showing
