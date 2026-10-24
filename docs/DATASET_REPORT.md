# Dataset report

Every number here was measured from the files, not taken from file names
or documentation. Raw files were read with checksums recorded before and
after the cleanup; all 6,442 were unchanged.

## The chain that matters

```
clip id        label (gloss)         source video                     landmarks                         playable
"20062"  ->   Test_ITW.json:   ->   datasets/videos/rgb/       ->   assets/signs/motion/       ->   assets/signs/manifest.json
              "FINISH"              20062_kf_rgb.mp4                 20062.json (extracted here)       signs["finish"].clip = "20062"
```

`scripts/ingest.py` builds the first two links (labels + videos ->
`datasets/processed/catalog.json`); `scripts/build_library.py` builds the
last two. A sign is **playable only if its manifest entry names a clip whose
motion file exists** -- the tests check exactly that.

## Answers

| | |
|---|---|
| **1. Unique sign labels** | **3,215.** All five label files and `Dictionary_Mapping.pt` use exactly the same 3,215 glosses. |
| **2. Available video clips** | **6,430** (`rgb/`, all ITW, 30 fps, 4-182 frames, median 67). MTV, STU, SYN and TED reference **38,580 clips that are not in this workspace**. |
| **3. Extracted motion files** | **375** library signs (v2) + **26** letters + **3** pre-stitched phrases in production. Archived: 24 superseded per-sign files, 94 `.npy` + 5 `.pt` from the sentence experiment, 4 motion JSONs in the 3D experiments. |
| **4. Playable signs** | **375 of 3,215 (11.7%)**, plus fingerspelling of any word (A-Z). 58 of the 375 are flagged low tracking quality (score < 0.7; median 0.89). 0 extraction failures. |
| **5. Missing video references** | ITW: **0** of 6,430. MTV 12,860, STU 6,430, SYN 6,430, TED 6,430: **all** missing. In the app: 0 referenced files missing. |
| **6. Duplicate / ambiguous labels** | Every gloss has exactly 2 takes (expected: two recordings, not duplicates). 299 glosses carry a parenthetical -- see below. 80 search keys match several signs (up to 7: CLOSE). 2 takes are under 20 frames (SCRUM 4, STRUCTURE 8); both signs have a normal second take, which extraction prefers. |

## The label files

| file | entries | glosses | videos here | what it is |
|---|---|---|---|---|
| `labels/Test_ITW.json` | 6,430 | 3,215 | **all** | clip id -> gloss. The only split this project can use. |
| `labels/Test_MTV.json` | 12,860 | 3,215 | none | ids like `27_365`, `web1_832` (a different recording set) |
| `labels/Test_STU.json` | 6,430 | 3,215 | none | |
| `labels/Test_SYN.json` | 6,430 | 3,215 | none | |
| `labels/Test_TED.json` | 6,430 | 3,215 | none | |

No clip id appears in more than one file. The other four splits become
usable only if their videos are obtained; `scripts/ingest.py --json` reads
any of them unchanged.

## Parentheses in glosses

A gloss is a label for a sign, not an English word, and its parenthetical
means one of two different things:

| kind | count | example | found by typing |
|---|---|---|---|
| sense | 253 | `OPEN (DOOR)` | "open" -- marked *uncertain* unless the sentence mentions a door |
| phrase, meaning-changing | 31 | `WANT (NOT WANT)` = *don't want* | "not want" / "don't want" -- **never** "want" |
| phrase, narrowing | 12 | `EGYPT (ANCIENT EGYPT)` | "ancient egypt"; "egypt" as uncertain |
| plural | 3 | `YOU (PLURAL)` | "you", ranked below plain YOU |

Treating the meaning-changing ones as senses would sign the opposite of
what was typed (an earlier version of this project played NO GOOD for
"good"). The corpus has **no plain GOOD, WANT, KNOW, NAME, SORRY, PLEASE,
EAT, TODAY, MONEY or months** -- those words are fingerspelled.

612 glosses are multi-word (THANK YOU, CREDIT CARD) and are matched as one
sign; 79 contain hyphens, which search treats as spaces.

## Two data sources the app does not use yet

These are reported, not integrated: this cleanup adds no features.

**`raw/Dictionary_Mapping.pt`** (now USED -- see below): for each of the
3,215 glosses, a list of English keywords and a regional variant, e.g.

```
FORGET      forget, forgot, forgotten
RECOLLECT   memory, remember, recall, memorise, recollect, ...
TURN ON (START)   light, illuminate, turn on (start)
```

Since 2026-10-24 the planner uses these after the gloss names and their
stems (`scripts/build_keywords.py` -> `assets/signs/keywords.json`, 5,208
keys). The lists are loose -- NO WAY (REJECT) lists "hi" and "hello",
STUPID lists "sorry" -- so a keyword plays only when strong (among the
sign's first two keywords, or a form of its own name), negated or
time-shifted signs are never reached by their bare word, and anything
ambiguous is marked for review.

**`landmarks/pose_cam1.pkl`** (689 MB): a 136-keypoint pose (body,
feet, 68-point face, both hands; x, y, confidence) for **every one of the
6,430 ITW clips**, with frame counts matching the videos exactly. This
library extracts its own MediaPipe landmarks at ~25 s of CPU per clip; this
file already covers all of them. Using it would need a different skeleton
mapping in the renderer and a quality comparison against the MediaPipe
extraction first -- it could make all 3,215 signs available without the
~6-hour batch.

The file is a pickle; it was inspected without being loaded (opcode
disassembly), and the `.pt` files were read with a restricted unpickler
that permits only plain data and NumPy arrays.

## The sentence dataset (archived experiment)

`raw/auslan_daily/*.xlsx` annotate **14,041 sentence clips from 90 source
videos** (train 12,441 / dev 800 / test 800; 1,448 single-word subtitles).
The two files are complementary, not duplicates: one has clip names,
signers and splits, the other frame and time ranges. Poses are present for
only **3 of the 90 videos** -- `video_1.pt` (94 clips), `video_2.pt` (128),
`video_55.pt` (163): 385 clips, 2.7% of the set. The archived
`experiments/2d/pt_pose_pipeline` built a 5-word lexicon from them; the
production app does not use this data.

## Licensing

13 fingerspelling letters (C D F G J K M O Q R U V Z) are from Auslan
Signbank, CC BY-NC-ND 4.0: non-commercial use, with attribution. The
licence of the corpus behind `rgb/` and the label files is not recorded in
this workspace and should be confirmed before any public deployment.
