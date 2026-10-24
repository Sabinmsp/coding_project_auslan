"""
Stitch multiple fingerspelled WORDS into one sentence.

    python scripts/build_sentence.py "pay_bill_by_the_10th_of_2026" \
        PAY:P,A,Y  BILL:B,I,L,L  BY:B,Y  THE:T,H,E \
        TEN:T,E,N  TWENTY:T,W,E,N,T,Y  TWENTY:T,W,E,N,T,Y  SIX:S,I,X

Each argument after the name is WORD:letter,letter,... Reuses
build_fingerspell.py's per-letter concatenation, but adds a second,
longer pause between WORDS (not just between letters), and records both
letter_ranges AND word_ranges in the output so the UI can show
"which word, which letter" instead of just letters.

This exists because a sentence is not just fingerspelling run
continuously -- a viewer needs to know where one word ends and the next
begins, which a uniform letter-to-letter hold does not convey.
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

LETTER_HOLD = 6     # ~0.2s: pause after each letter within a word
WORD_HOLD = 18      # ~0.6s: longer pause after each whole word

def load_letter(letter):
    path = paths.FINGERSPELL_SOURCE / f"{letter}.json"
    return json.loads(path.read_text())

def main():
    name = sys.argv[1]
    word_specs = sys.argv[2:]   # ["PAY:P,A,Y", "BILL:B,I,L,L", ...]

    frames = []
    letter_ranges = []
    word_ranges = []
    fps = None
    width = height = None
    video_letter_sequence = []   # flat list of letters, for the video concat

    for spec in word_specs:
        word_label, letters_csv = spec.split(":")
        letters = letters_csv.split(",")
        word_start = len(frames)

        for letter in letters:
            data = load_letter(letter)
            if fps is None:
                fps = TARGET_FPS; width = data["width"]; height = data["height"]
            if data["width"] != width or data["height"] != height:
                print(f"warning: {letter} is {data['width']}x{data['height']}, "
                      f"sentence uses {width}x{height}")

            letter_frames = resample_to_target_fps(data)
            letter_start = len(frames)
            for f in letter_frames:
                f["frame"] = len(frames)
                frames.append(f)
            last = letter_frames[-1]
            for _ in range(LETTER_HOLD):
                held = json.loads(json.dumps(last))
                held["frame"] = len(frames)
                frames.append(held)
            letter_ranges.append({"letter": letter, "word": word_label,
                                   "start": letter_start, "end": len(frames)})
            video_letter_sequence.append(letter)

        # extra hold at the end of the whole word
        last = frames[-1]
        for _ in range(WORD_HOLD - LETTER_HOLD):
            held = json.loads(json.dumps(last))
            held["frame"] = len(frames)
            frames.append(held)
        word_ranges.append({"word": word_label, "start": word_start, "end": len(frames)})

    out = {"fps": fps, "width": width, "height": height,
           "frame_count": len(frames), "frames": frames,
           "letters": letter_ranges, "words": word_ranges}

    motion_path = paths.PHRASES / f"{name}.json"
    motion_path.write_text(json.dumps(out))
    print(f"wrote {motion_path}  ({len(frames)} frames, {len(frames)/fps:.1f}s @ {fps}fps)")
    print(f"  words: {[w['word'] for w in word_ranges]}")

    # ---- reference video: concat every letter's clip in sequence -------
    video_paths = [paths.FINGERSPELL_SOURCE / f"{l}.mp4" for l in video_letter_sequence]
    concat_list = paths.FINGERSPELL_SOURCE / f"_concat_{name}.txt"
    concat_list.write_text("".join(f"file '{p}'\n" for p in video_paths))

    out_video = paths.PHRASES / f"{name}.mp4"
    subprocess.run([
        FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
        "-movflags", "+faststart", "-an", str(out_video)
    ], check=True)
    print(f"wrote {out_video}")

if __name__ == "__main__":
    main()
