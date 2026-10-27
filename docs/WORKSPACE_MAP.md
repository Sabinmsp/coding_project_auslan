# Workspace map

Every file and folder you have for this project: what it is, whether
anything uses it, and whether it can be removed.

**Update 2026-10-27:** `auslan-ai-clean/experiments/` (442 MB), the old QA
images and batch logs, and four obsolete status documents were moved to
`~/SignBridge-archive-2026-10-27/` (see its README). References to
`auslan-ai-clean/experiments/` below now mean that archive folder.

**Cleanup done 2026-10-27** (approved: rebuildable files + exact duplicates;
1,251 MB freed, all tests passing afterwards):
- deleted `auslan-ai-clean/dist/` and `auslan_2d_demo/dist/`, which are
  rebuilt by `python3 scripts/build_dist.py`; and Python caches;
- deleted 3 unreferenced duplicates (`boy.glb`, `hello_auslan_poseqqq.gif`,
  `08133_motion_world.json`);
- replaced 3 duplicates that old scripts still open with **links** to their
  identical twins (`Jake.blend` → `Jake.fbx`, `jakke.glb` → `Jake.fbx`,
  `08133_kf_rgb.mp4` → `rgb/08133_kf_rgb.mp4`), so those scripts keep working.

Each duplicate was checksum-verified immediately before removal. Nothing
else was moved or deleted.

## The three places

```
/Users/sabinpradhan/
├── untitled folder 3/                 THE ORIGINAL WORKSPACE (~8 GB, 97 items + 2 below)
│   ├── auslan-ai-clean/               ★ THE PROJECT: work here (2.9 GB, Git: main)
│   ├── backup_before_cleanup_2026-10-22.tar.gz   backup of the original (639 MB)
│   └── ... months of earlier work (below)
└── auslan-backups/
    └── fingerspelling_2026-10-24.tar.gz   backup of the fingerspelling media (82 MB, verified)
```

**Rule of thumb:** work only inside `auslan-ai-clean/`. The original folder
is the source data plus history.

## Legend

| mark | meaning |
|---|---|
| **KEEP** | used by the project. Removing it breaks something |
| **REBUILD** | generated; removable, and one command recreates it |
| **HISTORY** | earlier work, not used; copies exist in `auslan-ai-clean/experiments/` and/or the backup |
| **DUPLICATE** | byte-identical to another file (verified by checksum) |

## 1. Inside `auslan-ai-clean/` (the project)

| path | size | mark | what it is |
|---|---|---|---|
| `frontend/` | 0.1 MB | KEEP | the web app: `index.html`, `src/planner.js`, `library.js`, `timeline.js` |
| `backend/` | 0.05 MB | KEEP | `paths.py`, `extract_motion.py`, `serve.py` (dev server, port 8003), `llm_plan.py` (optional, unused) |
| `scripts/` | 0.1 MB | KEEP | build commands (ingest, build_library, validate, keywords, add_sign, qa, dist, fingerspelling, finish_library.sh) |
| `tests/` | 0.2 MB | KEEP | `sh tests/run_all.sh` runs everything |
| `docs/` | 0.9 MB | KEEP | start with `HOW_IT_WORKS.md`, then this map |
| `assets/signs/manifest.json`, `keywords.json`, `face_topology.json` | 0.7 MB | KEEP | what the page reads (in Git) |
| `assets/signs/motion/`, `videos/` | 1.3 GB | KEEP · REBUILD | the 4,480 extracted clips. Rebuildable, but it takes ~10 hours: keep them |
| `assets/fingerspelling/` | 114 MB | KEEP | A–Z letters + 3 phrases. **Can't be rebuilt by a script yet**; backed up in `~/auslan-backups/` |
| `assets/signs.json` | — | KEEP | quick-pick buttons |
| `datasets/raw/` | 3 MB | KEEP | labels (`Test_*.json`), `Dictionary_Mapping.pt`, the two spreadsheets |
| `datasets/videos/rgb`, `datasets/landmarks/*` | links | KEEP | **symlinks** to the original folder's 5.1 GB of data. Don't move those originals |
| `datasets/processed/catalog.json`, `extract_log.jsonl`, `validation.json` | 5 MB | KEEP | the library's records (in Git; the log is also the resume point) |
| `datasets/processed/fingerspell_letters/` | 49 MB | KEEP | letter source clips, in the fingerspelling backup |
| `datasets/processed/qa/`, `logs/`, `final_status.txt` | ~25 MB | REBUILD | QA images, run logs, status report |
| `dist/` | — | REBUILD | **removed 2026-10-27**; recreate with `python3 scripts/build_dist.py` (~1 GB) |
| `experiments/` | 442 MB | HISTORY | 2D/3D experiments, archived; the code is in Git, the media isn't |
| `.git/` | — | KEEP | version history (4 commits) |

## 2. The original folder `untitled folder 3/`

### Source data: KEEP, and leave exactly where it is (5.1 GB)
The project's symlinks point at these paths. Moving them breaks extraction,
the tests and QA.

| item | what |
|---|---|
| `rgb/` (4.2 GB) | the 6,430 sign videos |
| `pose_cam1.pkl` (689 MB) | dataset poses for every clip (unused so far; reported in DATASET_REPORT.md) |
| `video_1.pt`, `video_2.pt`, `video_55.pt` (238 MB) | sentence-clip poses (experiment only) |
| `Test_ITW/MTV/STU/SYN/TED.json`, `Dictionary_Mapping (1).pt`, `Auslan*Daily_Communication.xlsx` | originals of the files copied into `datasets/raw/` |

### Environment: KEEP
| item | what |
|---|---|
| `.venv-1/` (1.4 GB) | Python 3.10 + MediaPipe/OpenCV/NumPy, used by every extraction script. Don't rename the folder it's in: a venv stores absolute paths |

### Superseded app: HISTORY (429 MB)
| item | what |
|---|---|
| `auslan_2d_demo/` | the app before the cleanup: older code without the later fixes. Its `dist/` (113 MB) is REBUILD; its `library/` (120 MB) holds the old buggy extraction (v2). Everything useful was copied into `auslan-ai-clean/` |

### 3D work: HISTORY (477 MB)
`jump_3d/`, `auslan-3d/`, `Jake.fbx`, `Jake_08133.blend`, `Jake_rig.blend(1)`,
`young+boy+character+riigged.glb`, the Blender scripts (`animate_avatar*.py`,
`retarget.py`, `test_one_frame.py`, `inspect_*rig.py`, `make_comparison.py`,
`extract_landmarks.py`, `extract_motion.py`, `text-to-3d.py`, `hhh.py`) and
their outputs (`08133_3d_avatar.mp4`, `08133_clean_3d.mp4`,
`08133_comparison.mp4`, `08133_motion.json`, `08133_kf_rgb_landmarks.npz`).
Copied to `auslan-ai-clean/experiments/3d/`. `Jake.blend` and `jakke.glb` are
now **links** to `Jake.fbx` (they were byte-identical FBX copies with wrong
names). The duplicate `boy.glb` and `08133_motion_world.json` were removed
(the copies in `jump_3d/` and `auslan-3d/` remain).

### `.pt` pose experiment: HISTORY (33 MB)
`auslan_avatar/`, `signs/`, `extracted_keypoints/`, `build_lexicon.py`,
`README_avatar.md`, `signs_example.json`, `pt-to-video.py`,
`ptheellotovid.py`, `pygame_avatar.py`, `55.py`, `water.py`,
`clip_summary.csv`, `output_signed.mp4`, `output_stick.mp4`,
`video_2_0.gif`. Copied to `auslan-ai-clean/experiments/2d/pt_pose_pipeline/`.

### Early 2D renderers and their media: HISTORY (28 MB)
13 scripts (`08133_kf_rgb_py.py`, `19new.py`, `cc.py`, `video_to_2d.py`,
`demo_to_2d.py`, `make_demo.py`, `type_word_to_2d.py`, `two_words.py`,
`make_combined_avatar.py`, `make_hello_auslan_pose.py`, `rbg_depth.py`,
`alphabet_2d.py`, `fingerspell_2d.py`), their input clips (`19.mp4`,
`1630.mp4`, `2240.mp4`, `2778.mp4`, `3185.mp4`, `44.mp4`, `78.mp4`,
`08133_kf_depth.mp4`) and outputs (`*_2d.mp4`, `output_19*.mp4`,
`final_*.mp4`, `auslan_7_sign_demo*.mp4`, `SABIN_*.mp4`,
`MIKAELA_alphabet_2d.mp4`, `hello_auslan_pose.gif`). Copied to
`auslan-ai-clean/experiments/2d/early_video_renderers/`.
`08133_kf_rgb.mp4` is now a **link** to `rgb/08133_kf_rgb.mp4`; the duplicate
`hello_auslan_poseqqq.gif` was removed.

### Other
| item | mark | what |
|---|---|---|
| `Screen Recording 2026-09-05 at 10.06.44 am.mov` (45 MB) | HISTORY | purpose unknown; copied to `experiments/old_tests/recordings/` |
| `backup_before_cleanup_2026-10-22.tar.gz` (639 MB) | KEEP | the safety net for everything above except the raw data |
| `.DS_Store` | — | macOS folder metadata, harmless |

## If you ever need space

From safest to most involved. **None of this has been done**; each step
needs your go-ahead.

| step | frees | risk |
|---|---|---|
| ~~delete both `dist/` folders~~ | ~~1.1 GB~~ | **done 2026-10-27** |
| ~~remove verified duplicates~~ | ~~180 MB~~ | **done 2026-10-27** |
| move HISTORY items of the original folder into an `_archive/` subfolder | 0 (tidier, not smaller) | low, if the source data and `.venv-1` stay put |
| delete HISTORY items | ~1 GB | they exist in the clean project's `experiments/` and the backup, but deleting is permanent |

**Never move or delete:** `rgb/`, `pose_cam1.pkl`, `video_*.pt`, `.venv-1/`,
`auslan-ai-clean/assets/`, `auslan-ai-clean/datasets/`, or the two backups.
