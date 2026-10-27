# Pipeline

One pipeline, in two halves: an **offline build** that turns labelled
videos into a sign library, and a **runtime** in the browser that turns
English into animation using that library.

```
OFFLINE (Python)                                   RUNTIME (browser)

datasets/raw/labels/Test_ITW.json                  English input
datasets/videos/rgb/*.mp4                              │  frontend/src/planner.js     sign planning
        │  scripts/ingest.py                           ▼
        ▼                                          sign plan (sign / fingerspell / omit, with reasons)
datasets/processed/catalog.json                        │  plan editor (index.html)     human review
        │  scripts/build_library.py                    ▼
        │    └ backend/extract_motion.py           sign lookup        manifest.json -> clip id
        ▼                                              │  frontend/src/library.js
assets/signs/motion/<clip>.json  ─────────────►   motion retrieval   fetch + cache + normalise + trim
assets/signs/videos/<clip>.mp4                         │  frontend/src/timeline.js
assets/signs/manifest.json                             ▼
        │  scripts/qa_overlay.py  (check)          animation sequencing   one clock, transitions
        ▼                                              │  index.html drawFrame()
datasets/processed/qa/*.jpg                            ▼
                                                   2D rendering + source video + subtitles
```

## Offline

**1. Ingest** — `python3 scripts/ingest.py`

Reads labels (`Test_ITW.json` by default; `--json`, `--csv` or `--folder`
for others), probes every video, and writes `datasets/processed/catalog.json`:
a stable id per gloss (`open-door`), its search keys, its kind (plain /
sense / phrase / plural) and its takes, longest first. This is where the
parenthesis rules live (`classify()`); see
[DATASET_REPORT.md](DATASET_REPORT.md#parentheses-in-glosses).

**2. Extract** — `../.venv-1/bin/python scripts/build_library.py`

For each sign's take, in usefulness order (`scripts/core_words.txt` first):

- `backend/extract_motion.extract()` runs three passes: MediaPipe Holistic
  over the frame; a Hands model on an upscaled crop around each wrist where
  pass 1 got no geometrically possible hand; interpolation across gaps of
  4 frames or fewer.
- **Hand ownership** (extractor v4): a hand is only stored in the slot of
  the arm it is attached to. Pass 2 asks for two hands per crop and keeps
  only one whose wrist is within 0.35 shoulder-widths of the cropped wrist
  and that isn't a copy of the other slot's hand. Without this, a crop
  that contained both hands put the other hand in the slot -- see
  [ANIMATION_DEBUG_REPORT.md](ANIMATION_DEBUG_REPORT.md).
- Each clip is validated as soon as it's extracted (next step), and the
  status goes into the log and manifest.
- Pose, both hands and 128 face points are stored as integers (1/10,000 of
  the frame). A hand that fails the geometry check is stored as absent
  rather than drawn wrong.
- The video is transcoded to H.264, since the originals are MPEG-4 Part 2
  and browsers can't play them.
- A quality score is computed: pose coverage times the hand coverage in
  frames where a hand is raised.

Every result is appended to `datasets/processed/extract_log.jsonl`, the
resume point, and `assets/signs/manifest.json` is rebuilt every 200 clips
and at the end. Stopping and re-running is always safe. At ~9 clips/min on
an M1 the full corpus takes about 6 hours.

**Keywords** — `python3 scripts/build_keywords.py` (once; depends only on the
dictionary and the catalog)

`datasets/raw/Dictionary_Mapping.pt` lists English keywords for every sign.
They're indexed into `assets/signs/keywords.json` under the same rules as the
gloss names:

- **Negated or time-shifted words.** A keyword that negates or shifts its
  word ("want (not want)", or "day" for DAY (THE NEXT DAY)) never maps from
  the bare word.
- **Sense-specific words.** A keyword with a sense ("learned
  (knowledgeable)") needs evidence elsewhere in the sentence.

**3. Validate** — `python3 scripts/validate_signs.py [--ids ...]`

The validator checks every sign for:

- **Hands:** in the wrong slot, duplicated, or detached from their arm.
- **Tracking:** coverage while signing, gaps, jumps, low pose confidence.
- **Shape and length:** limb stretch, clip length.

Each sign is marked **ok**, **review** or **unreliable**. The planner
fingerspells unreliable signs by default and shows review flags under
the gloss. `build_library.py --takes rescue` then extracts second takes
for flagged signs, and the manifest keeps the better take.

**4. Check by eye** — `../.venv-1/bin/python scripts/qa_overlay.py <ids> | --random N | --low [--frames ...] [--motion file --tag x]`

Draws the stored landmarks back over 5 frames of the source video
(`datasets/processed/qa/<id>.jpg`): the check that tracking followed the
signer, which comparing data with data cannot show.

## Runtime

| stage | where | what it does |
|---|---|---|
| sign planning | `planner.js plan()` | contractions, numbers, longest-phrase match, negation (NOT WANT), omissions (articles, copula), stems only when the word has no sign, senses only with evidence in the sentence, optional time-first / wh-last order; a sign the validator marked unreliable is fingerspelled (still in the menu). Every step records why. |
| review | `index.html renderPlan()/edit()` | each step is a menu (other senses, fingerspell, omit); the gloss line is the same plan as editable text, validated token by token |
| sign lookup | `library.js Library.candidates()/byId()/keywordEntries()` | gloss names first, then their stems, then the dataset's own English keywords (`assets/signs/keywords.json`: "can" -> ABLE, "remember" -> RECOLLECT). A keyword plays only if strong (among the sign's first two, or a form of its name); loose ones are spelled and offered in the menu; ranked by meaning, never by what is extracted |
| motion retrieval | `library.js Library.sign()/letter()/phrase()` | fetch on first use, LRU cache (80); one similarity transform per clip into a shared body frame; leading/trailing rest trimmed |
| sequencing | `timeline.js buildTimeline()/sample()` | each clip keeps its own timing; between two recorded frames the figure is interpolated linearly (a hand in only one of them comes from the nearer frame); 0.22 s transitions between signs (0.08 s between letters) and around a loop; a hand missing on either side of a transition is not invented |
| rendering | `index.html drawFrame()/drawFace()` | canvas figure; the forearm ends at the hand's own wrist when the hand is attached; one camera for the whole sentence; source video and captions driven by the same clock; nothing redrawn while paused |

## How to add a sign

The sign exists in the corpus (most cases):

```sh
python3 scripts/add_sign.py elephant              # finds the sign(s) meaning ELEPHANT, extracts, registers
python3 scripts/add_sign.py open --all-senses     # every OPEN (...) sense
python3 scripts/add_sign.py --id open-door        # one specific sign
python3 scripts/add_sign.py student --button      # also a quick-pick button
```

Reload the page. `add_sign.py` refuses words whose only sign means
something else ("want" has only *don't want*) and tells you so.

## How to process a new video

New recordings, not in the corpus:

```sh
# a folder of clips named by gloss: thank_you.mp4, open (door).mp4, ...
python3 scripts/ingest.py --folder /path/to/clips
../.venv-1/bin/python scripts/build_library.py
```

`ingest.py` writes **one catalog per source**, so it replaces the ITW
catalog. To add to the library rather than switch it, ingest a CSV/JSON that
lists both sets, or keep the ITW catalog and process the new clips with the
single-clip extractor:

```sh
../.venv-1/bin/python backend/extract_motion.py clip.mp4 out.json   # original (v1) format, one clip
```

Videos should show one signer, upper body in frame, 25-30 fps.
`scripts/qa_overlay.py` shows whether tracking worked.

## How to test the animation

```sh
node --test tests/*.mjs                                     # planner, library, timeline
../.venv-1/bin/python -m unittest tests/test_pipeline.py   # catalog rules, lossless storage
python3 -m unittest tests/test_llm_plan.py                  # LLM output validation
python3 backend/serve.py                                    # then by eye: http://localhost:8001
```

By eye: play a quick-pick sign and compare the figure with the source video
(bottom right). Try `?text=Who is your doctor?` to see a typed sentence with
reordering, and `?gloss=hello fs:SABIN` for an exact sequence. Scrub with the
slider: figure and video must stay aligned.

## Which implementation each stage uses, and why

The workspace had several implementations of most stages. The clean copy
keeps one of each in production; the rest were archived (see PROJECT_STRUCTURE.md).

| stage | in production | archived alternatives | why |
|---|---|---|---|
| video -> landmarks | `backend/extract_motion.py` | `jump_3d/extract_motion.py` (identical to it before its last refactor), root `extract_motion.py` and `extract_landmarks.py` (other formats, for 3D) | 3-pass hand recovery; output verified byte-identical through the refactor |
| sign lookup | catalog + manifest (`ingest.py`, `library.js`) | `auslan_avatar/lexicon.py` (5 `.pt` words), `type_word_to_2d.py` (direct Test_ITW lookup) | covers all 3,215 signs and handles senses and negated glosses |
| fingerspelling | `letters.json` + planner spell steps; `build_fingerspell/sentence.py` for fixed phrases | `fingerspell_2d.py`, `alphabet_2d.py` (render MP4s offline) | plays any word live; same letter clips |
| motion processing | `library.js` normalise + trim, `timeline.js` | `auslan_avatar/motion.py` (canonicalise / blend `.pt` poses) | works on the extracted format; never alters a sign's own frames |
| rendering | `index.html` canvas | `auslan_avatar/render.py` (OpenCV MP4), 13 early renderers | interactive, synchronised with the source video |
| sentence processing | `planner.js` | `auslan_avatar/pipeline.py` (glosses must be given) | turns English into a reviewable plan |

## Optional: LLM-proposed plans

`python3 backend/llm_plan.py "sentence"` asks Claude for a plan using only
the 3,215 listed sign ids, then validates every step locally (invented or
unextracted signs are fingerspelled; a negated sign used for a positive
word is flagged). It prints a gloss line and a `?gloss=` link. It needs
`pip install anthropic` and an API key, so it runs locally, never in the
deployed page.
