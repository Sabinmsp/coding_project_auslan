# Auslan 2D sign library

Type English. The page proposes an Auslan sign sequence, lets you check and
correct it, then plays it on a 2D figure built from real signers' recorded
motion, with the source video beside it for comparison.

```sh
python3 serve.py            # http://localhost:8001  (use this, not http.server -- see below)
```

`http://localhost:8001/?text=I go home tomorrow` plans and plays a sentence;
`?gloss=hello fs:SABIN` plays an exact sign sequence. Both make shareable links.

**This is a prototype, not a translator.** The plan is rule-based and has not
been checked by an Auslan user; the figure shows hands, body and the source
clip's face, but cannot add the grammatical facial expressions a sentence
needs. See [Limitations](#limitations).

---

## What the dataset is

`../Test_ITW.json` maps 6,430 clip ids to glosses: **3,215 distinct signs,
2 recorded takes each**, every clip present in `../rgb/` (512x408, 30 fps,
MPEG-4 Part 2). No landmarks ship with it -- every playable sign is
extracted here from video.

A gloss is not an English word. Two kinds of parenthetical mean different
things, and confusing them signs the opposite of what was typed:

| gloss | what it is | found by |
|---|---|---|
| `OPEN (DOOR)` | a specific sense | "open", as an *uncertain* match |
| `WANT (NOT WANT)` | the sign for **don't want** | "not want" / "don't want" only -- **never** "want" |
| `EGYPT (ANCIENT EGYPT)` | a narrowed meaning | "ancient egypt"; "egypt" as uncertain |

The rule (`ingest.py`): if the parenthetical repeats the head word it is the
sign's meaning; if it also negates or shifts time (NOT, NO, LAST, NEXT,
EVERY, ...) the head word must not find it at all. 31 glosses are blocked
this way. **The corpus has no plain GOOD, WANT, KNOW, NAME, SORRY, PLEASE,
EAT or TODAY** -- those are fingerspelled, which is honest; an earlier
version of this library signed GOOD as "no good".

## How it works

```
Test_ITW.json + rgb/*.mp4
   │  ingest.py           labels -> library/catalog.json (ids, keys, senses, takes)
   ▼
   │  build_library.py    per clip: MediaPipe (3 passes) -> compact landmarks,
   │                      H.264 reference video, quality score
   ▼
library/manifest.json     3,215 signs: available?, best take, quality, search keys
   │
   ▼  in the browser
"Pay your bill tomorrow"
   │  js/planner.js       rules -> a plan: sign / fingerspell / omit, each with a reason
   ▼
plan editor               every step a menu: other senses, fingerspell, omit
   │  js/library.js       fetch only the signs used; normalise each signer; trim rest
   ▼
   │  js/timeline.js      one continuous clock; short transitions between signs
   ▼
2D figure + source video + subtitles
```

### Extraction (`extract_motion.py`, `build_library.py`)

Three passes per clip: Holistic over the frame (pose, hands, face); a
dedicated Hands model on an upscaled crop around each wrist where pass 1 got
no geometrically possible hand; interpolation across gaps of up to 4 frames.
Pass 2 is skipped where pass 1 is already good -- byte-identical output,
31s -> 13s per clip.

Stored per sign (`library/motion/<clip>.json`, ~130 KB): x/y in 1/10000ths
of the frame for pose, both hands and 128 face points (outline, brows, eyes,
lips), plus per-frame provenance. **A hand that fails the geometry check is
stored as absent, not drawn** -- showing an inside-out hand is showing wrong
data. Verified lossless against a fresh extraction (`tests/test_pipeline.py`).

Quality score = pose coverage x hand coverage *in the frames where a hand is
raised*, so a one-handed sign isn't penalised for the resting hand. Below 0.7
is flagged "low tracking" in the UI. Each gloss has two takes;
`--takes rescue` extracts the second where the first scored badly, and the
manifest keeps whichever is better.

The queue is ordered by usefulness (`core_words.txt` first: greetings,
pronouns, question words, numbers, bills, health), so the library is usable
long before all 3,215 are done. The run is resumable at any point.

### Planner (`js/planner.js`)

Deterministic rules, each step labelled with the rule that made it:

- **omit** articles, copula, "to"/"of" -- no signs for these roles in Auslan
- **phrases first**: "thank you", "next week", "credit card" are one sign
- **negation**: "don't want" -> NOT WANT; auxiliary "do" dropped
- **stems** only when the word has no sign: "paid" -> PAY, "bills" -> BILL
- **senses need evidence**: OPEN (DOOR) only if the sentence mentions a door.
  `CAN` exists only as CAN (TIN), so "I can help" fingerspells *can* rather
  than sign *tin can*
- **order** (toggle): time adverbs first; a wh-word last in a wh-question
- a multi-word sign that isn't extracted yet falls back word by word
  (NOT + W-A-N-T), never one run-together fingerspelled word
- everything else is fingerspelled, and says whether a sign exists but
  isn't extracted yet, or doesn't exist in the corpus

### Review and correction

Each plan step is a chip with a menu: the chosen sign, every other candidate
for that word (unextracted ones shown, disabled), fingerspelling, or omit.
Changing one marks it **reviewed** and replays. The gloss line under the plan
is the same plan as text (`hello my fs:NAME fs:SABIN`); edit it and press
Enter to play exactly that. Every token is validated -- nothing that isn't a
real, extracted sign is ever played as one.

### Playback (`js/library.js`, `js/timeline.js`)

- **One body frame.** Each clip is a different signer and camera. Each is
  mapped by one uniform scale + translation (from its median shoulder line)
  so all signers share shoulder position and width. One similarity transform
  per clip changes no angle or distance ratio inside the sign.
- **Rest trimmed.** Every corpus clip starts and ends with hands at the hips.
  Only leading/trailing rest is cut -- never anything between the first and
  last raised frame -- and only when the clip demonstrably starts/ends at rest.
- **Signs untouched.** Each sign plays frame for frame at its own fps. The
  only synthesised motion is a 0.22 s transition between signs (0.08 s
  between fingerspelled letters); a hand missing on either side of a
  transition is not interpolated.
- One clock drives figure, captions and video. Speed (0.5-1.25x), pause,
  scrub across the whole sentence, replay, loop.
- Only the signs a sentence uses are fetched; decoded signs are kept in an
  80-entry LRU cache. Startup loads ~100 KB gzipped (mostly the manifest).

### Why `serve.py` and not `python3 -m http.server`

The built-in server ignores HTTP Range requests. Browsers seek inside video
by requesting byte ranges, so with it, scrubbing leaves the source video
stuck at 0 whenever the file isn't already cached. Static hosts handle
ranges; `serve.py` is only for running locally.

## Commands

```sh
python3 serve.py [port] [dir]                  # local server with range support
python3 ingest.py                              # Test_ITW.json -> library/catalog.json
python3 ingest.py --csv f.csv --clip-col id --gloss-col gloss --videos DIR
python3 ingest.py --folder DIR                 # thank_you.mp4 -> THANK YOU
../.venv-1/bin/python build_library.py         # extract everything (resumable)
../.venv-1/bin/python build_library.py --takes rescue   # better takes for weak signs
../.venv-1/bin/python build_library.py --manifest-only
python3 add_sign.py elephant [--button]        # one word, now
python3 add_sign.py --id open-door             # one specific sense
../.venv-1/bin/python qa_overlay.py hello --random 12 --low   # landmarks over video
python3 build_dist.py [--small-videos]         # deployable dist/ (see DEPLOY.md)
python3 llm_plan.py "sentence"                 # optional: Claude-proposed plan
```

On a laptop, keep it plugged in and awake for the full extraction
(`caffeinate -i ../.venv-1/bin/python build_library.py`): ~9 clips/min on an
M1, about 6 hours for all 3,215. macOS sleep pauses it; it resumes on wake.

## Optional: LLM-proposed plans (`llm_plan.py`)

Sends the sentence and the full 3,215-sign lexicon to Claude
(`claude-opus-5-5`, structured JSON output, lexicon prompt-cached, server-side
refusal fallback on). The model may only name lexicon ids; `validate()` then
checks every one -- invented ids and unextracted signs are fingerspelled,
and a negated sign used for a positive word (WANT (NOT WANT) for "want") is
flagged. Prints the gloss line and a link that plays it. It needs
`pip install anthropic` in the venv and credentials, and costs money per
call; the page never calls it. Its output is a proposal like any other plan
-- **not** verified Auslan.

## Tests

```sh
~/.nvm/versions/node/v24.13.1/bin/node --test tests/*.mjs     # planner, library, timeline
../.venv-1/bin/python -m unittest tests/test_pipeline.py     # catalog rules, lossless format
python3 -m unittest tests/test_llm_plan.py                   # LLM validation, offline
```

Browser behaviour (all ten scenarios in the brief, plus typing, video sync,
speed and scrub) was checked by driving headless Chrome against both the dev
folder and `dist/`.

## Fingerspelling

All 26 letters are separate clips (`letters.json`), so any unknown word can
be spelled. 13 of them -- C D F G J K M O Q R U V Z -- are from the Auslan
Signbank dictionary (`fetch_signbank_letter.py`; the corpus has no O or Q at
all), the other 13 from the corpus. **Signbank video is CC BY-NC-ND 4.0, so
this prototype must stay non-commercial and credit Signbank.** Signbank
video is 12-25 fps; motion is resampled by elapsed time to 30 fps, without
which those letters would play up to ~2.5x too fast.

`build_fingerspell.py` / `build_sentence.py` pre-stitch fixed phrases
(SABIN, PAY YOUR BILL) with letter and word boundaries recorded in the file;
they play under "Fingerspelled phrases".

## Limitations

- **Not reviewed by Deaf Auslan users.** Everything verified here is
  geometric or logical -- landmarks match MediaPipe, plans follow the stated
  rules -- not whether a Deaf viewer understands the result. That
  evaluation is the next real step.
- **Grammar.** No spatial reference, verb agreement, classifiers or role
  shift. The order rules are two common patterns applied mechanically.
- **Face.** The figure shows each clip's own face, so it cannot add the
  raised/lowered brows that mark a question, or a negation headshake. The
  plan notes say when a sentence needs them.
- **Vocabulary.** 3,215 signs, missing many everyday words (see above).
  Numbers have signs only for some values; the rest are spelled as words.
- **Tracking.** ~12% of signs extracted so far score below 0.7 -- mostly
  motion-blurred transition frames, shown as wrist dots. `qa_overlay.py`
  shows exactly what was captured.
- **Licensing.** Check the corpus licence before any public deployment;
  Signbank letters are non-commercial only.

## Files

```
index.html               player + plan editor
js/planner.js            English -> plan (rules)
js/library.js            manifest lookup, lazy load, cache, normalise, trim
js/timeline.js           continuous playback, transitions
serve.py                 dev server with HTTP Range support
ingest.py                labels -> library/catalog.json
build_library.py         catalog -> library/motion, library/videos, manifest
extract_motion.py        3-pass MediaPipe extraction (also used by the 3D path)
face_topology.py         -> library/face_topology.json (drawing the face)
core_words.txt           extraction priority
add_sign.py              extract one word's sign now
qa_overlay.py            landmarks drawn over the source video
llm_plan.py              optional Claude-proposed plan, validated
build_dist.py            deployable dist/
signs.json               quick-pick buttons (library ids) + pre-stitched phrases
letters.json             A-Z fingerspelling clips
library/                 catalog, manifest, motion, videos, qa sheets, logs
tests/                   node + python tests
motion/, videos/         letters, phrases, and the older per-sign files
                         (the per-sign ones are no longer used by the page)
```
