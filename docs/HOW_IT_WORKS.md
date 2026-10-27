# How it works: a guided tour

Written for someone learning the codebase. Everything described here exists
and was checked on 2026-10-24. Planned features are labelled **planned**.

## The whole system in one picture

```
 ┌─────────────────────────── BUILD TIME (Python, on your Mac) ───────────────────────────┐
 │                                                                                        │
 │  datasets/raw/labels/Test_ITW.json      datasets/videos/rgb/ (6,430 .mp4)              │
 │  {"20062": "FINISH", ...}               20062_kf_rgb.mp4 ...                           │
 │          │                                       │                                     │
 │          ▼                                       │                                     │
 │  scripts/ingest.py ──► datasets/processed/catalog.json  (3,215 signs, ids, keys)       │
 │                                  │               │                                     │
 │                                  ▼               ▼                                     │
 │                     scripts/build_library.py ── backend/extract_motion.py (MediaPipe)   │
 │                                  │                + scripts/validate_signs.py           │
 │                                  ▼                                                      │
 │        assets/signs/motion/<clip>.json   assets/signs/videos/<clip>.mp4                 │
 │        assets/signs/manifest.json  (which signs exist, playable, flags)                 │
 │                                                                                        │
 │  datasets/raw/Dictionary_Mapping.pt ──► scripts/build_keywords.py ──► keywords.json    │
 └────────────────────────────────────────────────────────────────────────────────────────┘
                         │ files on disk, nothing else connects the two halves
                         ▼
 ┌─────────────────────────── RUNTIME (only the browser) ─────────────────────────────────┐
 │  backend/serve.py just hands out files (it computes nothing)                           │
 │                                                                                        │
 │  you type "I can help"                                                                 │
 │        │                                                                               │
 │        ▼                                                                               │
 │  src/planner.js ──► plan:  I (sign)   can -> ABLE (keyword)   help (sign)              │
 │        │                   editable chips + gloss line in the sidebar                  │
 │        ▼                                                                               │
 │  src/library.js ──► fetch I.json, ABLE.json, HELP.json  (cached)                       │
 │        │             normalise each signer to one body size, trim rest poses           │
 │        ▼                                                                               │
 │  src/timeline.js ─► one clock: clip, transition, clip, transition, clip                │
 │        │                                                                               │
 │        ▼                                                                               │
 │  index.html drawFrame() ──► 2D figure on <canvas>   +   source video bottom-right      │
 └────────────────────────────────────────────────────────────────────────────────────────┘

 NOT CONNECTED (archived 2026-10-27, outside the project): 3D avatar (jump_3d, Blender), OpenCV renderer (pt_pose_pipeline),
 early video scripts. llm_plan.py runs only by hand and is never called by the page.
```

## Your 16 questions

**1. What have you built?**
A web page that turns English text into a sequence of real Auslan signs
recorded by real signers, played on a 2D figure. Behind it sits a Python
pipeline that converts 6,430 sign videos into motion data the page can play.

**2. What problem does it solve?**
Deaf people whose first language is Auslan can find written English,
like bills, notices and appointment letters, hard to follow. This
prototype explores turning short English messages into signs. Today it is
a **research prototype**: it shows signs, but not grammatical Auslan.

**3. How does it work?**
In two separate halves. A **build** half (Python, slow, run occasionally)
turns videos into data files. A **runtime** half (the browser, instant)
reads those files. They share only files, and never talk to each other
while the page runs.

**4. What happens when you type a sentence?**
Take "I don't want to pay the bill tomorrow":

1. **Split into words.** "don't" becomes "do not".
2. **Turn each word into a step.** "do" is dropped, because Auslan has no
   do-support. "not want" becomes the sign NOT WANT. "to" and "the" are
   dropped. "pay" becomes PAY, "bill" becomes BILL, and "tomorrow" becomes
   TOMORROW, moved to the front (Auslan puts time first).
3. **Attach a reason to every step**, shown in the sidebar, where you can
   change any step.
4. **Load and play.** Only the signs used are downloaded, and they play
   back to back with short transitions between them.

**5. How does it find the right sign?** In order:
1. The sign's own name: "help" finds HELP.
2. Phrases: "thank you" finds THANK YOU as one sign.
3. Word stems: "paid" finds PAY.
4. Dictionary keywords, when nothing above matched: "can" finds ABLE.
5. Otherwise, fingerspelling.

Two rules make this safe:
- **No meaning flips.** "want" can never play the *don't want* sign.
- **No meaning swaps.** A specific meaning like OPEN (DOOR) is only used
  if the sentence mentions a door.

**6. Where does the JSON vocabulary fit?**
- **`Test_ITW.json`** is the list of signs: video id → sign name.
- **`catalog.json`** is that list, organised.
- **`manifest.json`** is the same list, plus which signs are extracted and
  whether they're reliable. It's the only list the page reads.
- **`keywords.json`** holds the extra English words for each sign.

**7. How are the 2D animations made?**
MediaPipe finds each frame's body, hand and face points in the video.
These are stored as numbers. The page draws lines between the points:
arms, fingers, a face outline, brows and lips. It's like a dot-to-dot
puzzle redrawn 60 times a second.

**8. How are the 3D animations made?**
They aren't, in the app. The archived 3D work (`experiments/3d/`) tried to rotate the
bones of a 3D character to match the same points. It struggled with arm
proportions and wrist rotation, and was parked in favour of 2D.

**9. How does motion capture work?**
It isn't a mocap suit. It's **video pose estimation**, in three passes per
video:
1. MediaPipe Holistic over the whole frame.
2. For any hand still missing, a closer look at a zoomed crop around that
   wrist.
3. Filling gaps of up to 4 frames.

Ownership rules make sure a hand is only ever stored for the arm it's
attached to. Without them, PAY and HELP drew the same hand twice.

**10. What does the GLB avatar do?**
A `.glb` file is a 3D character model with a skeleton (`jump_3d/boy.glb`,
`jakke.glb`). The 3D experiment loads it with Three.js and turns its arm
bones. The app doesn't use it. Also, the root-folder `jakke.glb` is really
an FBX file with the wrong name.

**11. How does the frontend talk to the backend?**
It doesn't. There's no backend while the page runs. The page fetches
plain files: JSON and MP4. `serve.py` is only a file server, so the same
`dist/` folder works on any static host.

**12. What is actually connected?**
The planner, library, timeline and renderer, all through files built by
`ingest`, `build_library`, `validate_signs` and `build_keywords`.

**13. What is an isolated experiment?**
Everything in the archived `experiments/` folder:
- the 3D avatar
- the Blender scripts
- the OpenCV video renderer (`auslan_avatar`)
- the `.pt` sentence-pose work
- 13 early stick-figure scripts

Plus `llm_plan.py`, which runs only by hand.

**14. What works right now?**
- **Planning and playback:** typing, planning, editing and playback with
  speed, pause, scrub and loop, plus fingerspelling.
- **Signs:** 2,012 playable, checked by the validator.
- **Tests:** all pass (36 JS + 15 Python + 9 LLM checks, plus a browser test).

**15. What doesn't work, or isn't there?**
- **Extraction isn't finished**, and only progresses while the Mac is awake.
- **No Auslan grammar or facial grammar.**
- **Missing signs:** many everyday words, including PLEASE.
- **No Deaf user testing.**
- **Licensing questions** are open.
- **3D isn't connected.**
- **The LLM planner has never run live.**

**16. What should you focus on next?**
1. **Finish the data.** Keep the Mac plugged in, then read `final_status.txt`.
2. **Get it checked by Auslan users**, on real signs and real sentences.
3. **Sort out licensing** before showing it publicly.

Code changes come after those three. Right now, what limits quality is the
data, not the code.
