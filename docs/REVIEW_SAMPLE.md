# Review sample: 20 signs marked "review"

*Drawn 2026-10-24 23:39 from the 679 signs then marked `review`, sorted by id, with `random.Random(20261024).sample(..., 20)` -- rerun with the same seed to get the same 20.*

**This is a developer's visual check of tracking against the source video. It is NOT linguistic validation:
whether each sign is correct, recognisable Auslan needs Deaf or Auslan-qualified reviewers.** No sign was
reclassified; the suggestions below are input for a threshold decision.

**How "missing hand" is measured:** for each hand that signs (raised above 80% of shoulder-to-hip for at
least 20% of the clip), the share of its raised frames with no usable hand, and the same share within the
**core** -- the middle 60% of its raised period, where the sign itself happens (the first and last 20% are
mostly the hand rising and falling).

**Rule used for the suggestion:** core missing < 15% → ok · 15-30% → review · ≥ 30% → unreliable,
then checked by eye against the overlay.

**Result: 9 ok, 2 review, 9 unreliable.** The current "review" bucket mixes
signs that track well (gaps only at the start/end, or hands touching counted as "duplicates") with signs
whose signing hand is lost through the middle -- as bad as those already marked unreliable.

| sign | flags (validator) | missing hand: all raised (core) | clip | suggested | reason | visual note |
|---|---|---|---|---|---|---|
| **SECRET** `secret` | hand in wrong slot x1 | R 14% (0% of core) | `72499` | **ok** | missing frames are only at the start/end of the movement, or under 15% of the core | one-handed sign at the mouth; the dominant hand is tracked through the sign; the other hand rests (correctly absent) |
| **COW** `cow` | tracking gap > 0.2 s | L 23% (39% of core); R 8% (0% of core) | `98199` | **unreliable** | a hand is missing in 30% or more of the core frames | both hands at the head; the left hand drops out while at the head |
| **BIBLE** `bible` | duplicated hand x1 | L 10% (2% of core); R 23% (21% of core) | `96222` | **review** | a hand is missing in 15-30% of the core frames | hands together in front of the face; right hand lost for parts of the contact |
| **GENIUS** `genius` | duplicated hand x1, tracking gap > 0.2 s | R 28% (13% of core) | `69123` | **ok** | missing frames are only at the start/end of the movement, or under 15% of the core | one-handed, raised high; tracked at the top of the movement, lost briefly on the way |
| **STRICTNESS** `strictness` | hand in wrong slot x2, duplicated hand x3 | L 0% (0% of core); R 0% (0% of core) | `59031` | **ok** | missing frames are only at the start/end of the movement, or under 15% of the core | both hands tracked throughout; flags come from the hands crossing |
| **AIRPORT** `airport` | tracking gap > 0.2 s | L 24% (42% of core); R 11% (0% of core) | `89148` | **unreliable** | a hand is missing in 30% or more of the core frames | the left hand is lost while the hands overlap |
| **DELAY** `delay` | hand coverage 70%, tracking gap > 0.2 s | L 30% (35% of core); R 29% (24% of core) | `77341` | **unreliable** | a hand is missing in 30% or more of the core frames | both hands lost repeatedly during the movement |
| **PROMISCUOUS** `promiscuous` | duplicated hand x4 | L 0% (0% of core); R 3% (6% of core) | `76284` | **ok** | missing frames are only at the start/end of the movement, or under 15% of the core | both hands tracked; 'duplicate' frames are the hands touching |
| **BARTENDER** `bartender` | hand coverage 67%, tracking gap > 0.2 s | L 0% (0% of core); R 33% (12% of core) | `14706` | **ok** | missing frames are only at the start/end of the movement, or under 15% of the core | shaking movement above the head; motion blur at the extremes |
| **SUFFICIENCY** `sufficiency` | hand coverage 68%, tracking gap > 0.2 s | L 9% (7% of core); R 32% (42% of core) | `46140` | **unreliable** | a hand is missing in 30% or more of the core frames | right hand at the chest is visible but untracked through much of the sign |
| **REST** `rest` | hand coverage 62%, tracking gap > 0.2 s | L 26% (6% of core); R 38% (55% of core) | `60675` | **unreliable** | a hand is missing in 30% or more of the core frames | right hand visible at the chest but untracked in most core frames |
| **BOAST** `boast` | tracking gap > 0.2 s | L 4% (0% of core); R 24% (0% of core) | `73566` | **ok** | missing frames are only at the start/end of the movement, or under 15% of the core | both hands tracked in the core; gaps only while raising/lowering |
| **HAND** `hand` | duplicated hand x3 | L 2% (0% of core); R 4% (0% of core) | `57581` | **ok** | missing frames are only at the start/end of the movement, or under 15% of the core | both hands tracked; 'duplicate' frames are the hands touching |
| **POETRY** `poetry` | hand coverage 60%, tracking gap > 0.2 s | L 16% (24% of core); R 40% (41% of core) | `63548` | **unreliable** | a hand is missing in 30% or more of the core frames | the raised, moving hand is blurred and untracked for long stretches |
| **STRUCTURE** `structure` | duplicated hand x1 | L 7% (0% of core); R 15% (0% of core) | `35434` | **ok** | missing frames are only at the start/end of the movement, or under 15% of the core | hands at the mouth/chest tracked; one touching frame |
| **PIE** `pie` | tracking gap > 0.2 s | L 0% (0% of core); R 10% (0% of core) | `95907` | **ok** | missing frames are only at the start/end of the movement, or under 15% of the core | both hands tracked in the core; gap only at the start |
| **SKINNINESS** `skinniness` | hand coverage 57%, tracking gap > 0.2 s | R 43% (42% of core) | `83082` | **unreliable** | a hand is missing in 30% or more of the core frames | the signing hand near the face is visible but untracked in the core |
| **HECTIC** `hectic` | tracking gap > 0.2 s | L 22% (37% of core); R 0% (0% of core) | `03621` | **unreliable** | a hand is missing in 30% or more of the core frames | left hand untracked in the core while moving quickly |
| **LAWN** `lawn` | tracking gap > 0.2 s | L 13% (21% of core); R 17% (25% of core) | `26855` | **review** | a hand is missing in 15-30% of the core frames | both hands lost during the wide sweeping part of the sign |
| **PHYSICS** `physics` | hand coverage 59%, tracking gap > 0.2 s | L 16% (26% of core); R 41% (67% of core) | `28470` | **unreliable** | a hand is missing in 30% or more of the core frames | right hand untracked for most of the sign |

**References.** Motion: `assets/signs/motion/<clip>.json`. Video: `assets/signs/videos/<clip>.mp4`.
Overlay sheets (landmarks drawn on 5 video frames):

```sh
../.venv-1/bin/python scripts/qa_overlay.py secret cow bible genius strictness airport delay promiscuous bartender sufficiency rest boast hand poetry structure pie skinniness hectic lawn physics   # -> datasets/processed/qa/<id>.jpg
```

**What this suggests (for a later, separate decision):** the validator's "tracking gap > 0.2 s" and
"duplicated hand" flags fire on gaps at the edges of a sign and on hands touching. A measure based on
missing hands in the core of the sign separated this sample far more cleanly. Thresholds were NOT changed.
