# Auslan 2D avatar pipeline

`["STUDENT", "ASSIGNMENT", ...]` -> ordered `.pt` motions -> blended 2D
avatar -> synchronised subtitles -> one continuous `.mp4`.

## Quick start

```bash
# 1. build a word lexicon out of the dataset (writes signs/<WORD>.pt)
.venv-1/bin/python build_lexicon.py --out signs

# 2. render
.venv-1/bin/python -m auslan_avatar \
    --signs HELLO LOOK POSSUM WELL YEP \
    --sentence "Hello, look at possum - well, yep." \
    --out output_signed.mp4
```

From Python — this is the interface to call from the LLM/RAG side:

```python
from auslan_avatar import render_sentence

result = render_sentence(
    ["STUDENT", "ASSIGNMENT", "SUBMIT", "BEFORE", "FRIDAY"],
    lexicon="signs",
    output="out.mp4",
    sentence="Student must submit the assignment before Friday.",
)
print(result.duration, result.timing())
```

Or drive it from a file: `--signs-json signs_example.json`.

## Modules

| Module | Responsibility |
|---|---|
| `poseio.py` | Read/write `.pt`. Works with **or without torch** installed. |
| `skeleton.py` | Keypoint layout (136-point Auslan, COCO-WholeBody-133, COCO-17). |
| `lexicon.py` | `WORD` -> `.pt` path, aliases, missing-sign errors. |
| `motion.py` | Canonicalise, retarget, blend transitions, build the timeline. |
| `render.py` | Draw the 2D avatar. |
| `subtitles.py` | Per-sign word + full-sentence subtitle band. |
| `pipeline.py` | Orchestration (`render_sentence`). |
| `__main__.py` | CLI. |

Adding a sign is dropping `WORD.pt` into `signs/`. Nothing else changes.

## Keypoint layout

The dataset uses 136 keypoints per frame, `(x, y, confidence)`:

| Indices | Count | Part |
|---|---|---|
| 0-16 | 17 | body (COCO-17) |
| 17-25 | 9 | feet/aux (unused, very low confidence) |
| 26-93 | 68 | face |
| 94-114 | 21 | left hand |
| 115-135 | 21 | right hand |

Note this is **not** standard COCO-WholeBody-133 — there is an extra 9-point
block after the body, shifting face and hands by +3. `skeleton.detect_layout`
handles both.

## How the motion is processed

Raw coordinates are absolute pixels from different source videos, so they
cannot be concatenated directly. The pipeline:

1. **Gap-fill** joints below the confidence threshold by interpolating in time.
2. **Repair** joints never seen in a clip (park them on the wrist/nose rather
   than leaving extractor garbage).
3. **Canonicalise**: origin at the shoulder midpoint, unit = shoulder width.
4. **Retarget** onto one skeleton measured across the whole lexicon, keeping
   bone *directions* and resetting bone *lengths*.
5. **Anchor hands** to the body wrist so they cannot float free.
6. **Damp torso roll** to +/- 12 degrees.
7. **Smooth**, retime to a legible minimum duration, then blend.

Transitions are cubic-eased (`smoothstep`) between the outgoing and incoming
poses, with the length scaled by how far the hands actually travel
(4-16 frames). Nothing ever jump-cuts between files.

## Data-quality notes

These matter more than the code, and are why steps 2/4/6 exist. Measured on
the five verified signs:

* **Hips are unusable.** The signers sit behind a table, so hips are occluded
  and the extractor invents them *at ~0.70 confidence* — confidence alone
  cannot reject them. LOOK's hip midpoint sits 0.96 shoulder-widths to one
  side. The torso is therefore built from the shoulder line only, and hips are
  excluded from framing.
* **Rubber limbs.** LOOK's right upper arm varies +/-60% within one clip;
  WELL's forearms come out under half length; YEP is 30% left/right
  asymmetric. Hence the shared-skeleton retarget.
* **Implausible roll.** LOOK's shoulder line swings 51 degrees at ~0.78
  confidence. Hence the roll clamp.
* **Hands are weak.** Mean hand confidence is ~0.10-0.28, far below body
  (~0.68). Handshapes are the least reliable part of the output — which is
  unfortunate, because in a real sign language they carry much of the meaning.

## Lexicon

`build_lexicon.py` finds subtitles that are exactly one word, and keeps only
clips whose frame count matches the annotated span (within `--tol`). The
clip-index offset differs per file (Video_1 is 0, **Video_2 is 93**), so it is
detected rather than assumed.

Only **5** signs currently verify: `HELLO LOOK POSSUM WELL YEP`. The released
data is sentence-level; there is no `STUDENT.pt` to be had from it.

## Useful flags

```
--speed 1.3            overall tempo
--min-sign-seconds     stretch very short signs
--min/--max-transition blend length bounds (frames)
--max-tilt 12          torso roll clamp, 0 disables
--no-retarget          show the raw pose data instead
--no-face / --no-sentence / --no-word
--skip-missing         drop unknown signs instead of failing
--list                 print the lexicon
```
