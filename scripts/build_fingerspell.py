"""
Stitch per-letter motion tracks + videos into one fingerspelled word.

    python scripts/build_fingerspell.py SABIN S A B I N

Concatenates fingerspell_letters/{S,A,B,I,N}.json -> motion/sabin.json
and the matching .mp4s -> videos/sabin.mp4 (video concat is just for the
reference panel; the 2D avatar plays from the stitched JSON only).

A short HOLD_FRAMES is repeated at the end of each letter before moving to
the next. Real fingerspelling has a brief settle on each handshape before
transitioning, and without it letters blur together with no visual
separator -- this is not something MediaPipe recorded, it is inserted
deliberately so the word reads as five letters instead of one blur.
"""
import json
import subprocess
import sys
from pathlib import Path

import shutil


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import paths  # noqa: E402
FFMPEG = paths.find_tool("ffmpeg")

TARGET_FPS = 30.0

def resample_to_target_fps(data):
    """Retime a letter's frames onto TARGET_FPS, by real elapsed duration.

    Source clips are not all the same frame rate: the alphabet clips from
    rgb/ are 30fps, but the O and Q clips (pulled from the Auslan Signbank
    dictionary, since no clip for either exists in this project's own
    dataset) are ~12fps. Concatenating frame lists directly and assuming
    one fps for the whole stitched track would play the ~12fps letters
    back at 2.5x their real speed -- wrong duration, wrong speed, and it
    would not be obvious from the numbers alone (frame counts still look
    reasonable). Resampling by elapsed time keeps every letter at its
    real signing speed regardless of what its source clip's frame rate
    was. A no-op on clips already at TARGET_FPS.
    """
    src_fps = data["fps"]
    src_frames = data["frames"]
    if abs(src_fps - TARGET_FPS) < 0.05:
        return src_frames

    duration = len(src_frames) / src_fps
    n_target = max(1, round(duration * TARGET_FPS))
    out = []
    for i in range(n_target):
        t = i / TARGET_FPS
        src_i = min(len(src_frames) - 1, round(t * src_fps))
        out.append(src_frames[src_i])
    return out

HOLD_FRAMES = 6   # ~0.2s at 30fps, held on each letter's last pose

def main():
    word = sys.argv[1]
    letters = sys.argv[2:]

    tracks = []
    fps = None
    for letter in letters:
        path = paths.FINGERSPELL_SOURCE / f"{letter}.json"
        data = json.loads(path.read_text())
        if fps is None:
            fps = TARGET_FPS
        tracks.append(data)

    width = tracks[0]["width"]
    height = tracks[0]["height"]

    frames = []
    letter_ranges = []   # [{letter, start, end}] -- end is exclusive, hold included
    for data, letter in zip(tracks, letters):
        letter_frames = resample_to_target_fps(data)
        # Frames are in this clip's own coordinate space (normalised 0..1,
        # but stretched by ITS OWN width/height for the hand landmarks).
        # Since every alphabet clip here is the same 512x408 capture rig,
        # re-tagging width/height to the stitched track's values is exact;
        # a clip shot at a different resolution would need re-normalising
        # first.
        if data["width"] != width or data["height"] != height:
            print(f"warning: {letter} is {data['width']}x{data['height']}, "
                  f"stitched track uses {width}x{height} -- hand landmarks "
                  f"will be mis-scaled for this letter")
        start = len(frames)
        for f in letter_frames:
            f["frame"] = len(frames)
            frames.append(f)
        # hold the final pose so the letter is legible before the next begins
        last = letter_frames[-1]
        for _ in range(HOLD_FRAMES):
            held = json.loads(json.dumps(last))
            held["frame"] = len(frames)
            frames.append(held)
        letter_ranges.append({"letter": letter, "start": start, "end": len(frames)})

    out = {"fps": fps, "width": width, "height": height,
           "frame_count": len(frames), "frames": frames,
           "letters": letter_ranges}

    motion_path = paths.PHRASES / f"{word.lower()}.json"
    motion_path.write_text(json.dumps(out))
    print(f"wrote {motion_path}  ({len(frames)} frames, "
          f"{len(frames)/fps:.1f}s @ {fps}fps)")

    # ---- concatenate the source videos for the reference panel --------
    video_paths = [paths.FINGERSPELL_SOURCE / f"{l}.mp4" for l in letters]
    concat_list = paths.FINGERSPELL_SOURCE / "_concat.txt"
    concat_list.write_text("".join(f"file '{p}'\n" for p in video_paths))

    out_video = paths.PHRASES / f"{word.lower()}.mp4"
    # re-encode (not stream-copy) since the hold frames in the JSON have
    # no video equivalent -- concat just runs the letters back to back,
    # which is close enough for the reference panel's purpose
    subprocess.run([
        FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
        "-movflags", "+faststart", "-an", str(out_video)
    ], check=True)
    print(f"wrote {out_video}")

if __name__ == "__main__":
    main()
