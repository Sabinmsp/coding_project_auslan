# jump_3d — MediaPipe motion on the Jake rig

```
jump.mp4 → MediaPipe Holistic → motion.json → Three.js → jakke.glb
                                                             ↓
                              CC_Base_{L,R}_{Upperarm,Forearm,Hand}
```

## Run

```sh
python extract_motion.py     # jump.mp4  -> motion.json   (already done)
python3 -m http.server 8000
open http://localhost:8000
```

Open it through the server, not by double-clicking — `fetch` of the GLB and
the JSON is blocked on `file://`.

## Files

| file | notes |
| --- | --- |
| `jump.mp4` | the source clip, H.264 |
| `extract_motion.py` | MediaPipe Holistic → `motion.json` |
| `motion.json` | 51 frames @ 30fps, pose + pose_world + both hands |
| `convert_fbx_to_glb.py` | Blender headless, `Jake.fbx` → `jakke.glb` |
| `jakke.glb` | the rig, 110 nodes, one skin |
| `index.html` | the player |

## Three things that are not obvious

**The original `jakke.glb` was not a GLB.** It was a byte-identical copy of
`Jake.fbx` — a Kaydara FBX Binary with a `.glb` extension. `GLTFLoader` cannot
read it. `convert_fbx_to_glb.py` does the real conversion:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background \
    --python convert_fbx_to_glb.py -- /path/Jake.fbx /path/jakke.glb
```

It also downsizes textures to 1024px and re-encodes them as JPEG, which takes
the export from 50MB to 25MB. Morph targets are kept — Auslan carries grammar
on the face, so those will be needed later.

**"Use the first child bone" picks the wrong bone.** A bone's rest direction
comes from the offset to its child, but `CC_Base_L_Forearm`'s children are, in
order, `ElbowShareBone`, `ForearmTwist01`, `Hand`. Aiming the forearm at the
first of those is **53° off** on the left arm and 41° on the right. Likewise
`CC_Base_L_Hand`'s first child is `Index1`, 12° away from `Mid1`, which is the
bone that actually corresponds to MediaPipe's middle-finger MCP. `index.html`
names each child explicitly in the `BONES` table.

**`pose_world`, not `pose`.** Image-space landmarks are normalised separately
by frame width and height, so x is stretched by the aspect ratio, and their z
is not on the same scale as x/y — that bends the arms in the wrong plane.
`pose_world` is already metric with the origin at the hip midpoint. Hand
landmarks only come in image space, so `index.html` undoes the aspect stretch
using the `width`/`height` recorded in `motion.json`.

## Axis conventions

MediaPipe is +x right, +y **down**, +z away from camera. Three.js is +x right,
+y **up**, +z toward the viewer — so y and z flip and x passes through:

```js
new THREE.Vector3(p.x, -p.y, -p.z)
```

Both of these were checked against the data rather than guessed:

- Jake's anatomical left is **+X** (his `L_Upperarm` sits at x = +0.152), and
  MediaPipe's `LEFT_SHOULDER.x` is greater than `RIGHT_SHOULDER.x` by +0.31 on
  average. Same sign → **no mirroring**.
- Blender's Y-up glTF export turns Blender's −Y front into glTF +Z, so Jake
  faces **+Z**, toward the camera → `model.rotation.y = 0`.

The three checkboxes in the panel flip these live, in case a future clip was
shot mirrored or from behind.

## Verified

Replaying the same transform chain offline against the GLB hierarchy over all
51 frames, both arms, both segments (204 bone aims): the achieved world-space
bone direction matches the requested MediaPipe direction to within
**7e-6 degrees**. What the arms do is exactly what the landmarks say.

Remaining differences from the video are *proportional*, not directional — the
signer's arms are not Jake's arms, so a hand at head height on the signer lands
near the ear on Jake.

## Retargeting

Everything is rest-relative. Character Creator bones carry their own local
axes, so no bone is ever handed a world rotation:

```
q_local = q_parent_world⁻¹ · q_target_world · q_restBasis⁻¹
```

### The body frame — the structural fix

Camera space is not body space. This signer is seated and turned, and the
rotation carrying his body frame onto Jake's averages **13.9°** over the clip
and peaks at **23.4°**. Feeding camera-space directions straight to the rig
handed Jake the signer's torso lean as though it were arm motion.

So every direction is expressed in the signer's body frame — hip midpoint as
origin, torso as primary axis, shoulder line orthogonalised against it — and
then re-expressed in Jake's. Shoulder line and torso are **not** perpendicular
on a real body (their dot product averages 0.228 here), so the basis is built
by Gram-Schmidt rather than assumed orthogonal.

Two consequences. The retargeting no longer depends on where the camera was.
And "turn Jake around" now rotates the motion *with* him:

| | before | after |
|---|---|---|
| largest local bone change when turning Jake 180° | pose visibly changed | **0.044°** across 14 bones, every frame |

That was the symptom worth chasing — it was the coordinate bug showing itself.

### Arms — two axes, not one

`setFromUnitVectors` gives the *shortest* arc, which leaves roll about the bone
unconstrained and arbitrary. That is what makes an arm look mechanical even
when its joint positions are right. Both arm bones are now oriented from a full
basis, with the elbow-plane normal as the roll reference.

The elbow reference cannot be read off Jake's rest pose — his rest elbow bends
only **1.02°**, so `cross(upperarm, forearm)` has magnitude 0.018 and its
direction is numerically worthless. Its *sign* is not. So the axis is taken
from the hand's curl axis (derived, below) and only its sign is voted for by
that degenerate cross product. The two agree to |dot| = 0.83, which is the
cross-check that it is the same anatomical axis. The source elbow is well
conditioned everywhere — it bends 35–90° and never drops below 10°.

The elbow follows the **source elbow**, not an inference from the wrist:

| check | result |
|---|---|
| source→bone error, elbow and wrist, all 102 measurements | **0.000 mm** |
| same during live playback | 7–43 mm (smoothing lag, by design) |

### Fingers — 15 segment directions, through each joint's real DOF

All fifteen segment directions are used (MCP→PIP, PIP→DIP, DIP→TIP for five
digits), but each is retargeted **through the joint's actual degrees of
freedom** rather than aimed blindly. That is what rejects the noise. Measured
per-frame directional jitter:

| segment | right hand | left hand | arm baseline |
|---|---|---|---|
| MCP→PIP | 3.1–4.1° | 12–14° | forearm 4.9° |
| PIP→DIP | index/mid 3.6–4.6°, **ring/pinky 21–29°** | 11–19° | — |
| thumb, all three | 4.0–6.9° | 10–14° | — |

The right hand's proximal phalanges are as clean as the arm segments that
already looked right, so they are driven as hard. Ring and pinky middle
phalanges are not. Most of that jitter lives in axes a hinge cannot move along,
so constraining the joint discards it instead of rendering it:

- **MCP** ball joint → `swingAngles`: flexion as elevation out of the palm
  plane, spread as fan within it.
- **PIP / DIP** one-way hinges → whole angle between consecutive segments,
  sign from the curl axis.
- **Thumb1** saddle joint → aimed directly through the palm basis, because a
  single flexion angle cannot describe a joint that swings on two axes at once.

### Per-segment confidence

A phalanx has a fixed length. When the reconstructed length departs from that
finger's median for the clip, the landmark is misplaced and its direction is
not trusted — so that joint is damped rather than driven. This is what keeps
the ring and pinky from thrashing *without* smoothing the whole hand into mush
and losing the finger transitions, which is where the linguistic content lives.

In practice, exactly as the jitter table predicts:

| segment | confidence |
|---|---|
| right index / mid | 0.82–0.97 |
| right ring / pinky PIP | 0.30 / 0.35 |
| left hand, all | 0.20–0.35 |

Confidence damps *smoothing* only. It must not multiply into a snap — doing so
turns the snap into a partial slerp whose residual depends on history, which is
what made an identical frame resolve differently depending on what came before.

### The curl axis is derived, not hardcoded

Character Creator ships hands with a few degrees of bend already in them, and
the axis of that bend IS the flexion axis. Measured across the four fingers
against `Index1→Pinky1` it comes out **+1 on the left hand and −1 on the
right** — mirror images, as anatomy requires. That also fixes the palm normal
via `normal = curl × forward`, confirmed by the thumb sitting on that side of
the plane at rest.

### Palm orientation

The wrist is **not** solved from elbow→wrist: one direction cannot say whether
the palm faces up or down, and palm orientation is phonemic. Landmarks 0, 5, 9
and 17 build a palm basis and the hand bone gets the rotation carrying Jake's
rest palm basis onto it.

### Rejecting impossible detections

Four gates, in order. A frame failing any of them holds the last good
handshape rather than posing a broken one.

**Fingers inside out.** PIP is a one-way hinge, so a hand whose fingers all
read hyperextended is a bad fit, not a pose.

**Palm flipped.** The PIP test alone is blind to the worst failure: when a
detection is fitted inside out, the palm normal flips *and the curl axis flips
with it*, so the finger bends still measure self-consistently positive. It has
to be caught on the palm frame itself, temporally — a palm normal cannot
reverse between two frames 33 ms apart.

**Flat palm.** |sin| between the across-knuckles and towards-fingertips axes.
When they collapse towards each other the normal is the cross product of two
nearly identical vectors, i.e. noise, and the hand orientation is meaningless.

**Hand collapsed.** Knuckle span over palm length. On the left this drops as
low as 0.12, against a right-hand minimum of 0.71.

Measured over the clip:

| | right hand | left hand |
|---|---|---|
| palm-normal sign flips | **0** | 7 (max swing 84°/frame) |
| ill-conditioned axes | **0** | 1 |
| collapsed knuckle span | **0** | 7 |
| palm-normal frame-to-frame swing | median 4.5° | median 14.8° |

Every gate rejects **nothing at all** on the right hand. That is the check that
they target bad data rather than trimming good data.

| hand | posed | inside out | collapsed | flipped | flat | no landmarks |
|---|---|---|---|---|---|---|
| left | **41** | 4 | 2 | 2 | 0 | 2 |
| right | **51** | 0 | 0 | 0 | 0 | 0 |

(after the three-pass extraction below; on the original single-pass data this
was left 27 / right 46)

The debug panel names the reason per frame, e.g. `LEFT HAND (palm flipped — held)`.

### Clavicles

`clavicle → upperarm → forearm → hand`, parent solved and committed before its
child. The body basis orthogonalises the shoulder line against the torso, but
the *raw* shoulder vector keeps the tilt that orthogonalisation removes — and
that tilt is the clavicle signal. Measured here the shoulder line moves 4.2° sd
against the hip line and tilts across an 18° range against torso-up, so it is
real signing content rather than noise. `CLAVICLE_SCALE` damps or disables it.

### The rest position is not the bind pose

Character Creator ships Jake in a wide A-pose: measured on this rig his arms
sit **60.3° from vertical**, hands out at x = ±0.595 at chest height. Blending
to it made him spread into a near-T-pose at the end of a clip while the status
line said "at neutral". Both were true, which is the problem — a bind pose is a
skinning reference, not a pose anyone stands in.

A rest position is now solved once at load, in Jake's own body frame, through
the same `orientBone` path the motion uses so it cannot disagree with the
retargeting: arms **8.2°** off the torso, elbows 10° soft, hands down at
x = ±0.223. In sign linguistics that is where a signer's hands return between
utterances. The first and last 5 frames ease to it with a smoothstep.

| | bind pose | rest position |
|---|---|---|
| arm from vertical | 60.3° | **8.2°** |
| hand x / y | ±0.595 / 1.148 | **±0.223 / 0.898** |

### Lag is not solve error

The debug panel reports how far each smoothed bone still trails its target, and
near the clip's ends how far the rest blend has deliberately pulled it away.
That is lag, and it is labelled as such — reading it as retargeting error makes
a correct transform look like it diverges. The solve itself is exact:

| frame | snapped solve (α=1, pre-blend) | during smoothed playback |
|---|---|---|
| 3 | 0.0 mm | — |
| 23 | 0.0 mm | — |
| 40 | 0.0 mm | — |
| 50 | **0.0 mm** | L 128.5 / 247.9, R 187.6 / 311.2 mm |

Same transform, same frame. Nothing diverges; frame 50 is simply the last frame
of the rest blend, reached through a 0.45 slerp.

## Using a different avatar

Default is `boy.glb` (Auto-Rig Pro). `?model=./jakke.glb` switches back.

### What an Auto-Rig Pro export needs

Two separate problems, both invisible until the mesh tears.

**The deform chain is not a chain.** ARP holds its deform bones in place with
Copy Transforms *constraints*, and glTF carries none, so `forearm.l` exports
parented to `c_traj`. `repair` reattaches 38 bones with `Object3D.attach()`,
which preserves world transforms, so the rest pose is untouched and the chain
becomes drivable.

**The bones with the pivots are not the bones with the weight.** Checked
against the skin weights rather than guessed from names:

| bone | skin weight | position |
|---|---|---|
| `arm.l` | **0** | x = 0.240 — the shoulder joint |
| `arm_stretch.l` | 87.7% of upper-arm verts | x = 0.408 — *mid-humerus* |

Driving the weighted bone rotates the arm about its own middle; driving the
pivot bone moves nothing. The fix is both: drive `arm.l`/`forearm.l`/`hand.l`
for correct pivots, and reparent `arm_stretch`, `forearm_stretch`, `arm_twist`,
`forearm_twist` underneath them so the mesh follows — which is what ARP's
constraints were doing.

Also: GLTFLoader runs names through `sanitizeNodeName`, so `arm.l` arrives as
`arml`. `findBone` matches either spelling.

## Proportions: joint angles vs hand position

The boy's arm is **64% longer relative to torso** than the signer's (1.517 vs
0.922). No solver satisfies both hand position and arm shape at that gap; it is
a choice, and the default is angles.

| | source mean bend | angle mode error | position mode error |
|---|---|---|---|
| left arm | 19.5° | **0.0°** | 67.5° (max 73°) |
| right arm | 64.0° | **0.0°** | 37.3° (max 61°) |

Position mode pins the hand and lets the elbow absorb the mismatch, which at
worst folded a straight arm (source 12.2°) to **85.7°**. Sign location is
phonemic, but so is the arm's gestalt, and a folded arm misreads worse than a
hand sitting slightly wide. `REACH_MODE = 0` (angles) is the default;
`jake.reachMode(1)` switches to position/IK, which is the better choice on an
avatar built closer to human proportions.

## The solver is a pure function of its frame

Validity is classified once at load, not carried frame to frame. It used to be
stateful — the palm-flip gate compared against the last *accepted* frame and a
rejected frame held the previous pose — so frame 42 solved directly and frame
42 reached by playing forward differed by **150°**. Now 0.04°, whichever way
you arrive. `precomputeHandValidity()` records, per frame, which frame's
landmarks to use.

## Isolating the arm solve

`?fingers=0`, or `jake.fingers(false)`. Arms and palm move 0.04° with fingers
off; fingers move ~26°.

## Superseded: hand-position anchoring

Copying joint angles reproduces the signer's geometry exactly but puts the hand
wherever the avatar's own limb length lands it. That is invisible while the
avatar resembles the signer and obvious the moment it does not:

| | Jake | boy |
|---|---|---|
| arm / torso | 1.207 | **1.474** |
| shoulder width | 0.304 | **0.480** |

Sign languages locate signs against the body, so position is the phonemic
quantity. `REACH_MODE = 1` scales the shoulder-to-wrist offset by the ratio of
**torso** lengths — the one span both bodies genuinely share — and solves the
elbow with two-bone IK, using the signer's own elbow plane as the pole so the
arm bends the way theirs did.

Anchoring matters as much as scaling. Measured, in torso lengths of hand
disagreement between the two avatars on the same frame:

| anchor | hand error |
|---|---|
| each arm's own shoulder | 0.43-0.50 |
| **body centre (shoulder midpoint)** | **0.148-0.163** |
| rebuilt from the hip | 0.28-0.42 |

Anchoring per-shoulder drags the avatar's shoulder width into the result;
rebuilding from the hip mislocates the anchor, because Jake's shoulder midpoint
sits 0.17 torso behind the hip-to-chest line. With the body-centre anchor the
sideways component matches *exactly* on every hand and frame.

The elbows still differ by ~0.35 torso and that is correct: with the hand
pinned and the boy's arms 22% longer, geometry forces his elbow to bow wider.
The elbow is not phonemic.

## Known rough edge

The boy's sleeve bunches at the shoulder on a big lift. His deltoid is weighted
to `shoulder.l` (482 against `arm.l`'s 0), which does not rotate with the arm.
Giving the clavicle a fraction of the arm's swing was tried at 0.35 and is
worse — `shoulder.l` is also the arm's parent, so rotating it drags its own
vertices across the torso. This needs corrective weights on the mesh, not a
bone the retargeter can rotate.


Set `MODEL_FILE` at the top of `index.html`, or append `?model=other.glb` to
the URL. The retargeting maths is rig-agnostic — every axis it uses is derived
from the rest pose rather than assumed — so only the bone *names* change, and
those live in `RIG_PROFILES`. The first profile whose probe bone exists wins,
and the choice is logged at load.

A rig is usable here only if its **deform bones form a real parent chain**.
`validateProfile()` checks that at load and names any misparented bone instead
of silently rendering a torn limb.

### Export .glb, not .gltf

A `.gltf` is JSON that *references* its geometry and textures as separate
files. `young+boy+character+riigged.gltf` arrived alone: all 28 of its
companions were missing, including the 49.4 MB `.bin` holding every vertex,
skin weight and inverse-bind matrix. A lone `.gltf` is an empty shell.

### Auto-Rig Pro needs baking before export

That model is Auto-Rig Pro — 537 bones of IK/FK controllers. Its deform bones
are held in place by Copy Transforms **constraints**, and glTF carries no
constraints, so a raw export breaks the chain:

```
forearm.l   should sit under arm.l    ->  actually parented to c_traj
index1.l    should sit under hand.l   ->  actually c_index1.l
```

Rotating the upper arm would leave the forearm and hand behind. Use ARP's own
exporter (which bakes to a clean humanoid skeleton), or bake the constraints
and re-parent the deform bones, then export `.glb`. An `Auto-Rig Pro` profile
is already in `RIG_PROFILES`, written from that file's node table — untested,
because the model has never been loadable.

## Calibration

`CALIBRATION` at the top of the file, per hand: `WRIST_X/Y/Z_OFFSET` (radians,
in the hand's own frame), `FINGER_CURL_SCALE`, `FINGER_SPREAD_SCALE`,
`FINGER_SPREAD_BIAS`, `THUMB_CURL_SCALE`, `THUMB_SPREAD_SCALE`. `FINGER_TRIM`
is a per-finger multiplier; `LIMITS` holds the anatomical stops.

`FINGER_SPREAD_BIAS` is an *offset*, not a scale, because that is the fault it
corrects. Over this clip's open-hand frames the left hand fans correctly —
index +4°, mid −0°, ring −3°, pinky −9°, radial to ulnar as a real hand does —
while the right sits about +15° thumb-ward. No multiplier removes a constant
offset. Both default to 0.0 so nothing is silently tuned to one clip.

Live from the console, no edit-and-reload:

```js
jake.seek(29)                              // pose one frame, unsmoothed
jake.focus("right")                        // camera onto that hand
jake.calibration.right.FINGER_SPREAD_BIAS = 0.22
jake.state                                 // per-frame solve readout
```

## Debug overlay

Checkbox, or press **d**. Shows source → target directly:

| colour | meaning |
|---|---|
| green points/lines | source shoulder→elbow→wrist, walked along **Jake's own bone lengths** |
| yellow points/lines | all 21 source hand landmarks, at Jake's hand scale |
| red / green / blue arrows | palm curl axis / forward / normal |
| white arrows | avatar bone directions |
| L / R sprites | left-right labelling |

Drawing the source at Jake's proportions is the point: raw source positions
would diverge even with perfect retargeting, since he is not the signer's size.
Green sitting on the joint means correct; a gap is real error. The panel also
prints frame number, body-frame correction, neutral-blend weight, elbow bend,
source→bone error in mm, wrist quaternions, and per-finger MCP/PIP/DIP/spread
with confidences.

## Extraction: three passes

Holistic alone is not enough for the non-dominant hand. It sees the hand at
whatever size it occupies in a 512×408 frame, and for a resting, low-contrast
hand that is far too small to fit reliably — it still returns 21 landmarks,
they are just wrong.

**Pass 1 — Holistic** over the whole frame: body pose and both hands.

**Pass 2 — Hands on a wrist crop.** Crop 1.10× the forearm length, centred
0.35× past the wrist, upscaled to 384px, and re-run the dedicated Hands model.
The crop geometry was chosen by sweeping it against *the number of frames that
survive the sanity gates*, not by eye — raw detection count and raw
segment-length cv both point the wrong way, because a larger crop buys more
detections of mixed quality.

Merged by quality, not preference: pass 2 replaces pass 1 only where it
produces a hand that is geometrically possible. Handedness comes from which
wrist was cropped, never from the model's own label.

**Pass 3 — bridge short holes.** A hand that fails both passes leaves a hole,
and a held pose reads as a freeze followed by a jump. Where the hole is short
and bracketed by two good hands, the in-between is far better estimated by
interpolating them. Gaps longer than 4 frames are left alone — past that the
hand really has done something unobserved, and inventing it would be fiction
rather than interpolation. Measured gap lengths were left `[1,5,3,1,2,3,1,1]`,
right `[1,1,1]`.

Cumulative effect on frames the viewer will actually pose:

| | pass 1 only | + crop | + bridging |
|---|---|---|---|
| left | 25 | 34 | **41** |
| right | 46 | 48 | **51** |

Left-hand per-segment confidence rose from 0.20–0.44 to 0.77–0.86 over the same
frames. Each frame records `left_hand_source` / `right_hand_source` as
`holistic`, `crop` or `interpolated`, so nothing about its provenance is hidden.

`extract_motion_holistic_only.py.bak` is the single-pass version.

## Not done yet

- **Shoulders, spine, head** are still fixed at rest. Auslan carries grammar on
  the face and in torso lean.
- **Left-hand tracking**, still. Down to 10 unusable frames from 24, but the
  five-frame gap in the middle is genuinely unobserved and is held, not
  invented. A second camera angle, or a higher-resolution source clip, is what
  would close it — there is nothing left to recover from these pixels.
- **Forearm twist** is carried by the palm basis, but extreme
  pronation/supination will still read short.

Rollback points: `index_arms_only.html.bak` (arms only) and
`index_v2_hands.html.bak` (before the body frame and elbow plane).
