"""
Command line entry point.

    python -m auslan_avatar --signs HELLO LOOK POSSUM \
        --sentence "Hello, look at possum." --out out.mp4
"""

import argparse
import json
import sys

from .lexicon import Lexicon, MissingSignError
from .pipeline import RenderConfig, render_sentence


def build_parser():
    p = argparse.ArgumentParser(
        prog="auslan_avatar",
        description="Render an ordered list of Auslan signs as a subtitled MP4.",
    )
    p.add_argument("--signs", nargs="+", metavar="WORD",
                   help="ordered glosses, e.g. STUDENT ASSIGNMENT SUBMIT")
    p.add_argument("--signs-json", metavar="PATH",
                   help='JSON file: ["STUDENT", "ASSIGNMENT", ...] or '
                        '{"signs": [...], "sentence": "..."}')
    p.add_argument("--lexicon", default="signs",
                   help="directory of <WORD>.pt files (default: signs)")
    p.add_argument("--out", default="output_signed.mp4", help="output .mp4")
    p.add_argument("--sentence", default=None,
                   help="full English subtitle line")
    p.add_argument("--fps", type=float, default=25.0)
    p.add_argument("--width", type=int, default=720)
    p.add_argument("--height", type=int, default=900)
    p.add_argument("--speed", type=float, default=1.0,
                   help=">1 faster, <1 slower")
    p.add_argument("--min-sign-seconds", type=float, default=0.72,
                   help="stretch very short signs to at least this long")
    p.add_argument("--min-transition", type=int, default=4,
                   help="minimum blend frames between signs")
    p.add_argument("--max-transition", type=int, default=16,
                   help="maximum blend frames between signs")
    p.add_argument("--max-tilt", type=float, default=12.0,
                   help="clamp torso roll to +/- this many degrees "
                        "(the shoulder keypoints are noisy); 0 disables")
    p.add_argument("--style", choices=["stick", "human"], default="stick",
                   help="stick = plain line art (default); "
                        "human = shaded figure")
    p.add_argument("--stroke", type=float, default=0.030,
                   help="stick-figure line weight, in shoulder-widths")
    p.add_argument("--no-retarget", action="store_true",
                   help="skip bone-length normalisation (show raw pose data)")
    p.add_argument("--no-face", action="store_true",
                   help="hide facial features")
    p.add_argument("--no-sentence", action="store_true",
                   help="hide the full-sentence subtitle line")
    p.add_argument("--no-word", action="store_true",
                   help="hide the per-sign word subtitle")
    p.add_argument("--skip-missing", action="store_true",
                   help="drop unknown signs instead of failing")
    p.add_argument("--list", action="store_true",
                   help="list the lexicon and exit")
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        lex = Lexicon(args.lexicon)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.list:
        for word in sorted(lex.words):
            print(word)
        return 0

    signs, sentence = args.signs, args.sentence
    if args.signs_json:
        with open(args.signs_json) as fh:
            spec = json.load(fh)
        if isinstance(spec, dict):
            signs = spec.get("signs", signs)
            sentence = spec.get("sentence", sentence)
        else:
            signs = list(spec)

    if not signs:
        print("error: give --signs or --signs-json", file=sys.stderr)
        return 2

    config = RenderConfig(
        width=args.width,
        height=args.height,
        fps=args.fps,
        speed=args.speed,
        min_sign_seconds=args.min_sign_seconds,
        max_tilt_deg=None if args.max_tilt <= 0 else args.max_tilt,
        retarget=not args.no_retarget,
        style=args.style,
        stroke=args.stroke,
        show_face=not args.no_face,
        show_sentence=not args.no_sentence,
        show_word=not args.no_word,
        transition={
            "min_frames": args.min_transition,
            "max_frames": args.max_transition,
        },
    )

    # Only animate progress on a real terminal; piped output would otherwise
    # collect one line per frame.
    live = sys.stdout.isatty() and not args.quiet

    def progress(done, total):
        if live:
            print(f"\r  rendering {done}/{total} frames", end="", flush=True)
        elif not args.quiet and done == total:
            print(f"  rendered {total} frames")

    try:
        result = render_sentence(
            signs, lex, args.out,
            sentence=sentence,
            config=config,
            on_missing="skip" if args.skip_missing else "error",
            progress=progress,
        )
    except MissingSignError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print()
        if result.missing:
            print(f"  skipped (not in lexicon): {', '.join(result.missing)}")
        print(f"  {result.frames} frames @ {result.fps:g} fps "
              f"= {result.duration:.2f}s")
        for word, start, end, dur in result.timing():
            print(f"    {word:<14} {start:6.2f}s -> {end:6.2f}s  ({dur:.2f}s)")
        print(f"  saved: {result.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
