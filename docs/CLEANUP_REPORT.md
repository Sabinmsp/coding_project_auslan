# Cleanup report

**What was done:** the working 2D application and everything around it was
audited and **copied** into this clean structure. The original workspace was
not modified: no file was moved, renamed, edited or deleted there.

| | |
|---|---|
| original workspace | `../` (untitled folder 3) -- unchanged |
| backup taken first | `../backup_before_cleanup_2026-10-22.tar.gz` (639 MB, 1,214 entries: all code, outputs, 3D assets and the extracted library; raw datasets excluded because they were checksummed and only ever read) |
| raw data integrity | 6,442 dataset files checksummed before and after: **all identical** |
| copied | 1,186 files, 761 MB, each md5-verified against its source |
| linked, not duplicated | 5 large datasets, 5.5 GB (`rgb/`, `pose_cam1.pkl`, `video_{1,2,55}.pt`) |
| not copied | 12 items, 1.7 GB: byte-identical duplicates, the regenerable `dist/`, the venv |
| every operation | [`cleanup_operations.json`](cleanup_operations.json) |

Before copying, the background extraction job (started earlier to extract
all 3,215 signs) was stopped so the original library was a consistent
snapshot: 374 signs, log and motion files in agreement. The job is
resumable and continues from this copy (see the end of this report).

## Contents

1. [Audit: every top-level item](#audit-every-top-level-item)
2. [Inside auslan_2d_demo](#inside-auslan_2d_demo)
3. [Duplicates](#duplicates)
4. [What changed in the copied code](#what-changed-in-the-copied-code)
5. [Verification](#verification)
6. [Differences from the original](#differences-from-the-original)
7. [Not used in production](#not-used-in-production)
8. [Open issues found by the audit](#open-issues-found-by-the-audit)

## Audit: every top-level item

Status is one of PRODUCTION, DATASET, EXPERIMENT, GENERATED OUTPUT,
DUPLICATE (proven byte-identical by checksum -- similar names alone were
never treated as duplicates) or UNKNOWN. 97 items: 1 production, 14
datasets, 41 experiments, 25 generated outputs, 6 duplicates, 8 unknown,
plus the venv and macOS metadata.

| Path | Status | Purpose | Dependencies | Size | Location in auslan-ai-clean |
|---|---|---|---|---|---|
| `.DS_Store` | SYSTEM | macOS folder metadata | - | 12 KB | not copied |
| `.venv-1`/ | ENVIRONMENT | Python 3.10 virtualenv (mediapipe, opencv, numpy, torch, ...) | - | 1.3 GB | not copied (recreate from requirements.txt) |
| `08133_2d.mp4` | GENERATED OUTPUT | from 08133_kf_rgb_py.py | - | 424 KB | `experiments/2d/early_video_renderers/outputs/08133_2d.mp4` |
| `08133_3d_avatar.mp4` | GENERATED OUTPUT | from text-to-3d.py | - | 64 KB | `experiments/3d/blender/outputs/08133_3d_avatar.mp4` |
| `08133_clean_3d.mp4` | GENERATED OUTPUT | from hhh.py | - | 143 KB | `experiments/3d/blender/outputs/08133_clean_3d.mp4` |
| `08133_comparison.mp4` | GENERATED OUTPUT | from make_comparison.py | - | 1.1 MB | `experiments/3d/blender/outputs/08133_comparison.mp4` |
| `08133_jump_2d.mp4` | GENERATED OUTPUT | from make_hello_auslan_pose.py | - | 558 KB | `experiments/2d/early_video_renderers/outputs/08133_jump_2d.mp4` |
| `08133_kf_depth.mp4` | DATASET | depth-camera version of ITW clip 08133 (sample) | input to rbg_depth.py | 954 KB | `experiments/2d/early_video_renderers/inputs/08133_kf_depth.mp4` |
| `08133_kf_rgb.mp4` | DUPLICATE | byte-identical copy of rgb/08133_kf_rgb.mp4 | input to several early scripts | 404 KB | not copied -- byte-identical to rgb/08133_kf_rgb.mp4 |
| `08133_kf_rgb_landmarks.npz` | GENERATED OUTPUT | from extract_landmarks.py | - | 329 KB | `experiments/3d/blender/outputs/08133_kf_rgb_landmarks.npz` |
| `08133_kf_rgb_py.py` | EXPERIMENT | early 2D video renderer: clip 08133 -> stick figure 08133_2d.mp4 | cv2, mediapipe; 08133_kf_rgb.mp4 | 5 KB | `experiments/2d/early_video_renderers/08133_kf_rgb_py.py` |
| `08133_motion.json` | GENERATED OUTPUT | 3D experiment motion data (input to an older animate_avatar) | - | 283 KB | `experiments/3d/blender/outputs/08133_motion.json` |
| `08133_motion_world.json` | DUPLICATE | byte-identical to auslan-3d/motion.json | - | 417 KB | not copied -- byte-identical to auslan-3d/motion.json |
| `08133_rgb_depth_2d.mp4` | GENERATED OUTPUT | from rbg_depth.py | - | 520 KB | `experiments/2d/early_video_renderers/outputs/08133_rgb_depth_2d.mp4` |
| `1630.mp4` | UNKNOWN | input clip (make_combined_avatar.py); source not recorded | - | 195 KB | `experiments/2d/early_video_renderers/inputs/1630.mp4` |
| `19.mp4` | UNKNOWN | input clip for the early renderers; source not recorded | - | 768 KB | `experiments/2d/early_video_renderers/inputs/19.mp4` |
| `19new.py` | EXPERIMENT | early 2D video renderer: 19.mp4 -> output_19_nice_2d.mp4 (a later variant of video_to_2d.py, not identical) | cv2, mediapipe; 19.mp4 | 13 KB | `experiments/2d/early_video_renderers/19new.py` |
| `2240.mp4` | UNKNOWN | input clip (make_combined_avatar.py); source not recorded | - | 271 KB | `experiments/2d/early_video_renderers/inputs/2240.mp4` |
| `2778.mp4` | UNKNOWN | input clip (make_combined_avatar.py); source not recorded | - | 472 KB | `experiments/2d/early_video_renderers/inputs/2778.mp4` |
| `3185.mp4` | UNKNOWN | input clip (cc.py, make_combined_avatar.py); dated 2023, source not recorded | - | 690 KB | `experiments/2d/early_video_renderers/inputs/3185.mp4` |
| `3185_2d_avatar.mp4` | GENERATED OUTPUT | from cc.py | - | 627 KB | `experiments/2d/early_video_renderers/outputs/3185_2d_avatar.mp4` |
| `44.mp4` | UNKNOWN | input clip (make_combined_avatar.py); source not recorded | - | 311 KB | `experiments/2d/early_video_renderers/inputs/44.mp4` |
| `55.py` | EXPERIMENT | Auslan-Daily .pt pose experiment: 12-line inspection of video_55.pt | torch | 188 B | `experiments/2d/pt_pose_pipeline/55.py` |
| `78.mp4` | UNKNOWN | input clip (make_combined_avatar.py); source not recorded | - | 341 KB | `experiments/2d/early_video_renderers/inputs/78.mp4` |
| `alphabet_2d.py` | EXPERIMENT | early 2D video renderer: letters -> <NAME>_alphabet_2d.mp4 | cv2, mediapipe; rgb/ | 6 KB | `experiments/2d/early_video_renderers/alphabet_2d.py` |
| `animate_avatar.py` | EXPERIMENT | 3D experiment: bake arm motion onto Jake | Blender (bpy), headless | 8 KB | `experiments/3d/blender/animate_avatar.py` |
| `animate_avatar_broken.py.bak` | EXPERIMENT | 3D experiment: earlier, broken animate_avatar (backup) | Blender (bpy), headless | 742 B | `experiments/3d/blender/animate_avatar_broken.py.bak` |
| `auslan-3d`/ | EXPERIMENT | 3D experiment: Three.js skeleton player (motion.json) | browser; three.js CDN | 428 KB | `experiments/3d/auslan-3d` |
| `Auslan-Daily_Communication.xlsx` | DATASET | 14,042 sentence clips: video, clip name, subtitle, split, signer | video_*.pt | 586 KB | `datasets/raw/auslan_daily/Auslan-Daily_Communication.xlsx` |
| `auslan_2d_demo`/ | PRODUCTION | The working 2D web app + its build pipeline (see breakdown below) | Python 3.10 venv (mediapipe, opencv, numpy), ffmpeg, a browser | 426.2 MB | 11 places (see breakdown) |
| `auslan_7_sign_demo.mp4` | GENERATED OUTPUT | earlier make_combined_avatar.py output | - | 3.4 MB | `experiments/2d/early_video_renderers/outputs/auslan_7_sign_demo.mp4` |
| `auslan_7_sign_demo_stable.mp4` | GENERATED OUTPUT | from make_combined_avatar.py | - | 3.5 MB | `experiments/2d/early_video_renderers/outputs/auslan_7_sign_demo_stable.mp4` |
| `auslan_avatar`/ | EXPERIMENT | Auslan-Daily .pt pose experiment: Python package -- .pt poses -> blended OpenCV avatar -> subtitled MP4 (a second, offline 2D renderer) | numpy, cv2, PIL; signs/*.pt | 147 KB | `experiments/2d/pt_pose_pipeline/auslan_avatar` |
| `Auslan_Daily_Communication.xlsx` | DATASET | same 14,042 clips: subtitle, begin/end frame and time, split -- complementary, NOT a duplicate | video_*.pt | 790 KB | `datasets/raw/auslan_daily/Auslan_Daily_Communication.xlsx` |
| `boy.glb` | DUPLICATE | byte-identical to jump_3d/boy.glb | - | 105.4 MB | not copied -- byte-identical to jump_3d/boy.glb |
| `build_lexicon.py` | EXPERIMENT | Auslan-Daily .pt pose experiment: cuts single-word clips from sentence clips -> signs/<WORD>.pt | auslan_avatar; xlsx, video_*.pt | 7 KB | `experiments/2d/pt_pose_pipeline/build_lexicon.py` |
| `cc.py` | EXPERIMENT | early 2D video renderer: 3185.mp4 -> 3185_2d_avatar.mp4 | cv2, mediapipe; 3185.mp4 | 5 KB | `experiments/2d/early_video_renderers/cc.py` |
| `clip_summary.csv` | GENERATED OUTPUT | clip table written by pt-to-video.py | - | 11 KB | `experiments/2d/pt_pose_pipeline/clip_summary.csv` |
| `demo_to_2d.py` | EXPERIMENT | early 2D video renderer: final_demo.mp4 -> final_demo_2d.mp4 | cv2, mediapipe; final_demo.mp4 | 5 KB | `experiments/2d/early_video_renderers/demo_to_2d.py` |
| `Dictionary_Mapping (1).pt` | DATASET | 3,215 glosses -> id, English keywords, regional variant (torch zip, plain data) | - | 375 KB | `datasets/raw/Dictionary_Mapping.pt` |
| `extract_landmarks.py` | EXPERIMENT | 3D experiment: Holistic -> .npz landmarks for retarget.py | cv2, mediapipe | 6 KB | `experiments/3d/blender/extract_landmarks.py` |
| `extract_motion.py` | EXPERIMENT | 3D experiment: earliest extractor, 08133 -> 08133_motion_world.json (different output from backend/extract_motion.py -- not a duplicate) | cv2, mediapipe | 1 KB | `experiments/3d/blender/extract_motion.py` |
| `extracted_keypoints`/ | GENERATED OUTPUT | 94 .npy keypoint arrays exported by pt-to-video.py | - | 26.0 MB | `experiments/2d/pt_pose_pipeline/extracted_keypoints` |
| `final_2words_2d.mp4` | GENERATED OUTPUT | from two_words.py | - | 615 KB | `experiments/2d/early_video_renderers/outputs/final_2words_2d.mp4` |
| `final_demo.mp4` | GENERATED OUTPUT | from make_demo.py (also the input to demo_to_2d.py) | - | 2.7 MB | `experiments/2d/early_video_renderers/outputs/final_demo.mp4` |
| `final_demo_2d.mp4` | GENERATED OUTPUT | from demo_to_2d.py | - | 1.7 MB | `experiments/2d/early_video_renderers/outputs/final_demo_2d.mp4` |
| `fingerspell_2d.py` | EXPERIMENT | early 2D video renderer: fingerspelling MP4; holds the letter -> clip-id table the web app's corpus letters came from | cv2, mediapipe; rgb/ | 7 KB | `experiments/2d/early_video_renderers/fingerspell_2d.py` |
| `hello_auslan_pose.gif` | GENERATED OUTPUT | early pose GIF; producing script not found | - | 877 KB | `experiments/2d/early_video_renderers/outputs/hello_auslan_pose.gif` |
| `hello_auslan_poseqqq.gif` | DUPLICATE | byte-identical to hello_auslan_pose.gif | - | 877 KB | not copied -- byte-identical to hello_auslan_pose.gif |
| `hhh.py` | EXPERIMENT | 3D experiment: matplotlib 3D figure of 08133 -> 08133_clean_3d.mp4 | cv2, mediapipe, matplotlib | 10 KB | `experiments/3d/blender/hhh.py` |
| `inspect_cc_rig.py` | EXPERIMENT | 3D experiment: rig inspection for the CC rig | Blender (bpy), headless | 4 KB | `experiments/3d/blender/inspect_cc_rig.py` |
| `inspect_rig.py` | EXPERIMENT | 3D experiment: prints armature and bone hierarchy | Blender (bpy), headless | 6 KB | `experiments/3d/blender/inspect_rig.py` |
| `Jake.blend` | DUPLICATE | byte-identical to Jake.fbx -- an FBX file with a .blend name | - | 30.5 MB | not copied -- byte-identical to Jake.fbx (an FBX file with a .blend name) |
| `Jake.fbx` | EXPERIMENT | 3D model (FBX, Character Creator rig) | - | 30.5 MB | `experiments/3d/assets/Jake.fbx` |
| `Jake_08133.blend` | EXPERIMENT | Blender scene: Jake with clip 08133 baked | Blender | 29.3 MB | `experiments/3d/assets/Jake_08133.blend` |
| `Jake_rig.blend` | EXPERIMENT | Blender scene: Jake rig | Blender | 29.3 MB | `experiments/3d/assets/Jake_rig.blend` |
| `Jake_rig.blend1` | EXPERIMENT | Blender's automatic previous-save of Jake_rig.blend (differs from it) | Blender | 29.3 MB | `experiments/3d/assets/Jake_rig.blend1` |
| `jakke.glb` | DUPLICATE | byte-identical to Jake.fbx -- an FBX file with a .glb name (the real GLB is jump_3d/jakke.glb) | - | 30.5 MB | not copied -- byte-identical to Jake.fbx (an FBX file with a .glb name); the real GLB is jump_3d/jakke.glb |
| `jump_3d`/ | EXPERIMENT | 3D experiment: Three.js retargeting of MediaPipe motion onto the Jake / boy rigs | browser; three.js CDN; Blender for conversion | 168.6 MB | `experiments/3d/jump_3d` |
| `make_combined_avatar.py` | EXPERIMENT | early 2D video renderer: 7 input clips -> auslan_7_sign_demo_stable.mp4 | cv2, mediapipe; 19/44/78/1630/2240/2778/3185.mp4 | 11 KB | `experiments/2d/early_video_renderers/make_combined_avatar.py` |
| `make_comparison.py` | EXPERIMENT | 3D experiment: 3-panel debug video (original / skeleton / avatar) | cv2 | 4 KB | `experiments/3d/blender/make_comparison.py` |
| `make_demo.py` | EXPERIMENT | early 2D video renderer: concatenates labelled rgb clips -> final_demo.mp4 | cv2; Test_ITW.json, rgb/ | 7 KB | `experiments/2d/early_video_renderers/make_demo.py` |
| `make_hello_auslan_pose.py` | EXPERIMENT | early 2D video renderer: clip 08133 -> 08133_jump_2d.mp4 | cv2, mediapipe; 08133_kf_rgb.mp4 | 5 KB | `experiments/2d/early_video_renderers/make_hello_auslan_pose.py` |
| `MIKAELA_alphabet_2d.mp4` | GENERATED OUTPUT | from alphabet_2d.py | - | 2.4 MB | `experiments/2d/early_video_renderers/outputs/MIKAELA_alphabet_2d.mp4` |
| `output_19_2d.mp4` | GENERATED OUTPUT | from video_to_2d.py | - | 1.6 MB | `experiments/2d/early_video_renderers/outputs/output_19_2d.mp4` |
| `output_19_nice_2d.mp4` | GENERATED OUTPUT | from 19new.py | - | 857 KB | `experiments/2d/early_video_renderers/outputs/output_19_nice_2d.mp4` |
| `output_signed.mp4` | GENERATED OUTPUT | from auslan_avatar | - | 3.6 MB | `experiments/2d/pt_pose_pipeline/outputs/output_signed.mp4` |
| `output_stick.mp4` | GENERATED OUTPUT | from pygame_avatar.py | - | 2.0 MB | `experiments/2d/pt_pose_pipeline/outputs/output_stick.mp4` |
| `pose_cam1.pkl` | DATASET | 136-keypoint poses for every ITW clip, frame counts matching rgb/ (gzipped pickle) -- unused so far | rgb/ clip ids | 688.8 MB | linked: `datasets/landmarks/pose_cam1.pkl` |
| `pt-to-video.py` | EXPERIMENT | Auslan-Daily .pt pose experiment: video_1.pt + xlsx -> extracted_keypoints/*.npy + clip_summary.csv | torch, pandas | 7 KB | `experiments/2d/pt_pose_pipeline/pt-to-video.py` |
| `ptheellotovid.py` | EXPERIMENT | Auslan-Daily .pt pose experiment: renders extracted_keypoints/video_1_0.npy | matplotlib | 5 KB | `experiments/2d/pt_pose_pipeline/ptheellotovid.py` |
| `pygame_avatar.py` | EXPERIMENT | Auslan-Daily .pt pose experiment: pygame renderer for video_2.pt -> output_stick.mp4, video_2_0.gif | pygame, torch | 10 KB | `experiments/2d/pt_pose_pipeline/pygame_avatar.py` |
| `rbg_depth.py` | EXPERIMENT | early 2D video renderer: RGB + depth of 08133 -> 08133_rgb_depth_2d.mp4 | cv2, mediapipe; 08133 rgb + depth | 8 KB | `experiments/2d/early_video_renderers/rbg_depth.py` |
| `README_avatar.md` | EXPERIMENT | Auslan-Daily .pt pose experiment: documentation for auslan_avatar | - | 5 KB | `experiments/2d/pt_pose_pipeline/README_avatar.md` |
| `retarget.py` | EXPERIMENT | 3D experiment: MediaPipe -> CC4 rig direction-vector retargeting | Blender (bpy), headless | 12 KB | `experiments/3d/blender/retarget.py` |
| `rgb`/ | DATASET | 6,430 ITW isolated-sign clips, 512x408 30 fps MPEG-4 Part 2 | named <clipid>_kf_rgb.mp4; labelled by Test_ITW.json | 4.2 GB | linked: `datasets/videos/rgb` |
| `SABIN_2d_fingerspell.mp4` | GENERATED OUTPUT | from fingerspell_2d.py | - | 1.6 MB | `experiments/2d/early_video_renderers/outputs/SABIN_2d_fingerspell.mp4` |
| `SABIN_alphabet_2d.mp4` | GENERATED OUTPUT | from alphabet_2d.py | - | 1.5 MB | `experiments/2d/early_video_renderers/outputs/SABIN_alphabet_2d.mp4` |
| `Screen Recording 2026-09-05 at 10.06.44 am.mov` | UNKNOWN | screen recording, purpose not recorded | - | 44.9 MB | `experiments/old_tests/recordings/Screen Recording 2026-09-05 at 10.06.44 am.mov` |
| `signs`/ | EXPERIMENT | Auslan-Daily .pt pose experiment: 5-word lexicon (HELLO, LOOK, POSSUM, WELL, YEP) + lexicon.json | made by build_lexicon.py | 717 KB | `experiments/2d/pt_pose_pipeline/signs` |
| `signs_example.json` | EXPERIMENT | Auslan-Daily .pt pose experiment: example input for auslan_avatar | - | 110 B | `experiments/2d/pt_pose_pipeline/signs_example.json` |
| `Test_ITW.json` | DATASET | ITW labels: 6,430 clip ids -> 3,215 glosses (2 takes each); the only label set whose videos are present | rgb/ | 157 KB | `datasets/raw/labels/Test_ITW.json` |
| `Test_MTV.json` | DATASET | MTV labels: 12,860 clip ids -> the same 3,215 glosses; videos NOT present | - | 372 KB | `datasets/raw/labels/Test_MTV.json` |
| `test_one_frame.py` | EXPERIMENT | 3D experiment: one frame drives one bone (unit test of retargeting) | Blender (bpy), headless | 6 KB | `experiments/3d/blender/test_one_frame.py` |
| `Test_STU.json` | DATASET | STU labels: 6,430 clip ids -> same glosses; videos NOT present | - | 157 KB | `datasets/raw/labels/Test_STU.json` |
| `Test_SYN.json` | DATASET | SYN labels: 6,430 clip ids -> same glosses; videos NOT present | - | 157 KB | `datasets/raw/labels/Test_SYN.json` |
| `Test_TED.json` | DATASET | TED labels: 6,430 clip ids -> same glosses; videos NOT present | - | 157 KB | `datasets/raw/labels/Test_TED.json` |
| `text-to-3d.py` | EXPERIMENT | 3D experiment: matplotlib 3D figure of 08133 -> 08133_3d_avatar.mp4 | cv2, mediapipe, matplotlib | 9 KB | `experiments/3d/blender/text-to-3d.py` |
| `two_words.py` | EXPERIMENT | early 2D video renderer: two rgb clips -> final_2words_2d.mp4 | cv2, mediapipe; rgb/ | 5 KB | `experiments/2d/early_video_renderers/two_words.py` |
| `type_word_to_2d.py` | EXPERIMENT | early 2D video renderer: word -> clip via Test_ITW.json -> 2D MP4 (precursor of the web app's lookup) | cv2, mediapipe; Test_ITW.json, rgb/ | 8 KB | `experiments/2d/early_video_renderers/type_word_to_2d.py` |
| `video_1.pt` | DATASET | Auslan-Daily sentence poses: 94 clips x (frames,136,3) + bbox | xlsx subtitles | 60.4 MB | linked: `datasets/landmarks/auslan_daily/video_1.pt` |
| `video_2.pt` | DATASET | Auslan-Daily sentence poses: 128 clips | xlsx subtitles | 85.4 MB | linked: `datasets/landmarks/auslan_daily/video_2.pt` |
| `video_2_0.gif` | GENERATED OUTPUT | from pygame_avatar.py | - | 710 KB | `experiments/2d/pt_pose_pipeline/outputs/video_2_0.gif` |
| `video_55.pt` | DATASET | Auslan-Daily sentence poses: 163 clips | xlsx subtitles | 92.8 MB | linked: `datasets/landmarks/auslan_daily/video_55.pt` |
| `video_to_2d.py` | EXPERIMENT | early 2D video renderer: 19.mp4 -> output_19_2d.mp4 | cv2, mediapipe; 19.mp4 | 6 KB | `experiments/2d/early_video_renderers/video_to_2d.py` |
| `water.py` | EXPERIMENT | Auslan-Daily .pt pose experiment: inspects the WATER segment of one sentence clip | matplotlib; extracted_keypoints/ | 2 KB | `experiments/2d/pt_pose_pipeline/water.py` |
| `young+boy+character+riigged.glb` | EXPERIMENT | 3D model (rigged boy, earlier version) | - | 20.7 MB | `experiments/3d/assets/young+boy+character+riigged.glb` |

## Inside auslan_2d_demo

| path | status | location |
|---|---|---|
| `index.html`, `js/*.js` | PRODUCTION | `frontend/index.html`, `frontend/src/` |
| `signs.json` | PRODUCTION | `assets/signs.json` |
| `letters.json` + 26 letter motion/video files | PRODUCTION | `assets/fingerspelling/` |
| `motion/`+`videos/` for SABIN, PAY YOUR BILL, BILL DUE DATE | PRODUCTION | `assets/fingerspelling/phrases/` |
| `library/manifest.json`, `face_topology.json`, `motion/`, `videos/` | PRODUCTION (generated) | `assets/signs/` |
| `library/catalog.json`, `extract_log.jsonl`, `qa/`, `build_run.log` | GENERATED (build-side) | `datasets/processed/` |
| `fingerspell_letters/` | PRODUCTION (build source) | `datasets/processed/fingerspell_letters/` |
| `extract_motion.py`, `serve.py`, `llm_plan.py` | PRODUCTION | `backend/` |
| `ingest.py`, `build_library.py`, `add_sign.py`, `qa_overlay.py`, `face_topology.py`, `build_dist.py`, `build_fingerspell.py`, `build_sentence.py`, `fetch_signbank_letter.py`, `core_words.txt` | PRODUCTION | `scripts/` |
| `tests/` | PRODUCTION | `tests/` |
| `DEPLOY.md`, `README.md` | docs | `docs/DEPLOY.md`, `docs/history/auslan_2d_demo_README.md` |
| 24 per-sign `motion/*.json` + `videos/*.mp4` (hello, student, ...) | EXPERIMENT (superseded by the library; 5 were mislabelled: finish, good, time, wait, water) | `experiments/2d/legacy_sign_files/` |
| `motion/o_letter.json`, `q_letter.json` + videos | DUPLICATE | not copied |
| `dist/` | GENERATED | not copied; `python3 scripts/build_dist.py` |
| `__pycache__/` | GENERATED | not copied |

A hazard the audit found here: `letters.json` refers to `letter_A.json` but
the files were named `letter_a.json`. macOS ignores case, so it worked; a
Linux host would have returned 404 for every letter if this folder were
served directly (the built `dist/` was not affected). The copy stores each
file under the name `letters.json` uses.

## Duplicates

Proven by md5 across the whole workspace (excluding `rgb/` and the venv):

| kept | not copied | note |
|---|---|---|
| `Jake.fbx` | `Jake.blend`, `jakke.glb` | all three are the same FBX bytes; the `.blend` and `.glb` names are wrong (the real GLB is `jump_3d/jakke.glb`) |
| `jump_3d/boy.glb` | `boy.glb` | |
| `hello_auslan_pose.gif` | `hello_auslan_poseqqq.gif` | |
| `auslan-3d/motion.json` | `08133_motion_world.json` | |
| `rgb/08133_kf_rgb.mp4` | `08133_kf_rgb.mp4` | |
| `letter_o.*`, `letter_q.*` | `o_letter.*`, `q_letter.*` | |

Look-alikes checked and **not** duplicates: the two `Auslan*Daily_Communication.xlsx`
files (same 14,042 rows, different columns), `jump_3d/extract_motion.py` vs
the app's extractor (identical to an older version of it, but the app's
has since gained face capture -- archived with its experiment), root
`extract_motion.py` and `extract_landmarks.py` (different outputs),
`video_to_2d.py` vs `19new.py` (variants), `Jake_rig.blend` vs `.blend1`.

## What changed in the copied code

Paths only. The working animation logic was not modified:

| file | change |
|---|---|
| `frontend/src/planner.js`, `timeline.js` | **none** (byte-identical) |
| `frontend/index.html` | 11 lines: 3 module imports (`./js/` -> `./src/`), 4 asset URLs (-> `./assets/...`), 2 command hints, 2 comments |
| `frontend/src/library.js` | 6 lines: 2 URL templates (-> `assets/signs/`), 4 comments |
| `assets/signs.json`, `assets/fingerspelling/letters.json` | asset paths re-pointed to their new web paths |
| `backend/paths.py` | **new**: every location in one place, plus `find_tool()` and the venv lookup |
| `scripts/*.py`, `backend/llm_plan.py` | paths from `backend/paths.py`; extractor imported as `backend.extract_motion`; five private copies of the ffmpeg/ffprobe finder replaced by `paths.find_tool` (all copies confirmed equivalent: same lookup order and failure, only the error text differed) |
| `backend/extract_motion.py` | command-line paths are taken relative to where you run it, not to the script's folder, and the old `jump.mp4` default was removed (extraction code unchanged) |
| `backend/serve.py` | serves `frontend/` at `/` with `assets/` mounted at `/assets/` -- the same layout `dist/` has |
| `scripts/build_dist.py` | writes `dist/` in that same layout (slimming logic unchanged) |
| `tests/*` | paths |

## Verification

All of this ran against the clean copy.

**Tests**: 43 of 43 pass. That's 27 JS tests (planner, library, timeline),
7 Python tests (catalog rules, manifest integrity, storage lossless against
a fresh MediaPipe run) and 9 LLM-validation tests.

**Every pipeline command re-run in its new location, output compared with the original's:**

| command | result |
|---|---|
| `scripts/ingest.py` (catalog from raw labels) | identical catalog |
| `scripts/build_library.py --manifest-only` | identical manifest (except build time) |
| `scripts/face_topology.py` | byte-identical |
| `backend/extract_motion.py` on clip 20062 | byte-identical to the original extractor's output |
| `scripts/build_fingerspell.py SABIN ...` | `sabin.json` and `sabin.mp4` byte-identical |
| `scripts/build_sentence.py pay_bill_full ...` | `.json` and `.mp4` byte-identical |
| `scripts/build_library.py --only about-turn` | extracted through worker processes (new sign) |
| `scripts/add_sign.py`, `qa_overlay.py`, `backend/llm_plan.py`, `fetch_signbank_letter.py --help` | run correctly (`qa_overlay.py` first failed on an import my path edit had dropped -- fixed, then a static check found no other undefined name in any script) |
| `scripts/build_dist.py` | builds; letter/phrase slimming identical to the original's (94.0 -> 20.2 MB) |

**Side-by-side with the original app** (headless Chrome, original on :8001,
copy on :8003): all **27 buttons** and **36 inputs** -- every quick-pick
sign, the 3 phrases, 9 typed sentences -- produced the same plan, timeline
length, source-video file and position, captions, and **identical canvas
pixels** (SHA-256 of the frame) at 3 moments each. 0 differences.

**Behaviour** (both the dev server and the built `dist/`), all passing:

- **Playback controls:** quick-pick play, play / pause, replay, scrub, 0.5x speed, loop on/off.
- **Reference video:** loads and stays aligned with the figure.
- **Sentences:** the name sentence fingerspells correctly, captions follow the active step, negation, time-first and wh-last rules apply, and a 60-step sentence plays.
- **Fingerspelling:** the SABIN phrase plays with letter progress.
- **Plan editing:** reviewer edits work, and the gloss line is validated.
- **Robustness:** a typed space works, lazy loading and the cache behave, and there are no page errors.

## Differences from the original

All deliberate and listed here:

- **URLs:** the app's own files are under `/src/` and its data under
  `/assets/...`, in development and in `dist/` alike.
- **Letter file names** now match the case `letters.json` uses (fixes the
  Linux-host 404s described above).
- **Extractor command line** takes paths relative to the current directory.
- **Library size:** **375** signs here against 374 in the original, because
  one extra sign was extracted to verify the worker path.
- **Superseded files:** the 24 per-sign files the app no longer used are
  archived in `experiments/2d/legacy_sign_files/` instead of sitting beside
  production files.
- **Extraction job:** now runs from here, so new signs land in this copy
  only.

## Not used in production

Nothing under `experiments/` is loaded by the app or imported by a script:

- `experiments/2d/early_video_renderers/`: 13 scripts that rendered
  stick-figure MP4s offline, their 8 input clips and 15 outputs.
- `experiments/2d/pt_pose_pipeline/`: the `auslan_avatar` package (a second,
  offline OpenCV renderer for the Auslan-Daily `.pt` poses), `build_lexicon.py`,
  the 5-word `.pt` lexicon, `pt-to-video.py`, `ptheellotovid.py`,
  `pygame_avatar.py`, `55.py`, `water.py`, 94 exported keypoint arrays and
  outputs.
- `experiments/2d/legacy_sign_files/`: the pre-library per-sign files.
- `experiments/3d/`: `jump_3d` and `auslan-3d` (Three.js), the Blender
  retargeting scripts and outputs, and the 3D models.
- `experiments/old_tests/recordings/`: one screen recording.

They are archived byte-for-byte with their original relative paths, so
they run from the original workspace, not from here.

## Open issues found by the audit

Reported, not changed, since this cleanup adds no features:

1. **No script regenerates `letters.json` or the 26 letter tracks.** They
   came from one-off commands. Their reproducible source is
   `datasets/processed/fingerspell_letters/`.
2. **`frontend/index.html` still contains the renderer and CSS inline.**
   Splitting them into `src/animation/` and `src/styles/` would change
   working code, so it is left for a separate, tested step.
3. **`scripts/ingest.py` writes one catalog per source.** Importing a new
   folder replaces the ITW catalog rather than adding to it.
4. **8 items have unknown provenance:** 7 input clips (`19.mp4`,
   `3185.mp4`, ...) and a screen recording.
5. **Licensing:** the `rgb/` corpus licence is not recorded. The Signbank
   letters are non-commercial only.
6. **Two large unused data sources:** the dictionary's English keywords and
   `pose_cam1.pkl` (dataset poses for all 6,430 clips). Both are described in
   [DATASET_REPORT.md](DATASET_REPORT.md#two-data-sources-the-app-does-not-use-yet).
7. **4 of the 5 label splits have no videos here** (38,580 clips).

## Continuing

```sh
caffeinate -i ../.venv-1/bin/python scripts/build_library.py   # resumes from extract_log.jsonl
```

Keep the Mac plugged in and awake: macOS sleep pauses it.
