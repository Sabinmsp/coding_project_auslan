"""
End-to-end pipeline: list of glosses -> continuous subtitled MP4.
"""

import os
from dataclasses import dataclass, field

import cv2
import numpy as np

from . import motion as mo
from . import skeleton as sk
from .lexicon import Lexicon
from .poseio import read_clip
from .render import Palette, default_palette, fit_view, make_renderer
from .subtitles import SubtitleRenderer, word_at_frame


@dataclass
class RenderConfig:
    width: int = 720
    height: int = 900
    fps: float = 25.0
    speed: float = 1.0
    min_sign_seconds: float = 0.72
    lead_in: int = 6
    tail: int = 10
    conf_min: float = mo.DEFAULT_CONF
    smooth_window: int = 5
    anchor_hands: bool = True
    retarget: bool = True
    max_tilt_deg: float = 12.0
    hand_min_coverage: float = 0.55
    torso_length: float = 1.45
    style: str = "stick"
    stroke: float = 0.030
    show_face: bool = True
    show_word: bool = True
    show_sentence: bool = True
    subtitle_band: int = None
    palette: Palette = None      # None -> chosen from `style`
    transition: dict = field(default_factory=dict)
    codec: str = "mp4v"


@dataclass
class RenderResult:
    path: str
    frames: int
    fps: float
    duration: float
    segments: list
    words: list
    missing: list = field(default_factory=list)

    def timing(self):
        """Human-readable per-sign timing table."""
        rows = []
        for seg in self.segments:
            if seg.kind != "sign":
                continue
            rows.append(
                (seg.word, seg.start / self.fps, seg.end / self.fps,
                 len(seg) / self.fps)
            )
        return rows


def load_motions(entries, config, layout_hint=None):
    """
    Read and canonicalise each sign against one shared skeleton.

    Two passes: normalise everything first, measure a single skeleton across
    the whole set, then refine each sign onto it. Signs are cut from
    different source videos, so without the shared pass each would animate a
    differently proportioned body and the joins would jump.
    """
    motions, layouts, usables, coverage = [], [], [], []

    for word, entry in entries:
        clip = read_clip(entry.path, clip_key=entry.clip, fps=config.fps,
                         name=word)
        layout = layout_hint or sk.detect_layout(clip.n_joints)
        coverage.append(mo.hand_coverage(clip, layout, config.conf_min))
        xy, usable = mo.canonicalize(
            clip,
            layout=layout,
            conf_min=config.conf_min,
            refine_pose=False,
        )
        motions.append(xy)
        layouts.append(layout)
        usables.append(usable)

    widths = {m.shape[1] for m in motions}
    if len(widths) > 1:
        raise ValueError(
            f"signs have inconsistent keypoint counts: {sorted(widths)}"
        )

    layout = layouts[0]
    # A joint is drawable if any sign ever saw it.
    usable = np.any(np.stack(usables, axis=0), axis=0)

    skeleton = mo.measure_skeleton(motions, layout) if config.retarget else None
    motions = [
        mo.refine(
            m, layout, usable,
            skeleton=skeleton,
            anchor_hands=config.anchor_hands,
            max_tilt_deg=config.max_tilt_deg,
            smooth_window=config.smooth_window,
        )
        for m in motions
    ]
    return motions, layout, usable, coverage


def render_sentence(words, lexicon, output, sentence=None, config=None,
                    on_missing="error", progress=None):
    """
    Animate an ordered list of glosses into one continuous MP4.

    words    : e.g. ["STUDENT", "ASSIGNMENT", "SUBMIT", "BEFORE", "FRIDAY"]
    lexicon  : Lexicon instance or path to a directory of .pt files
    sentence : optional full English subtitle line
    """
    config = config or RenderConfig()
    palette = config.palette or default_palette(config.style)
    if not isinstance(lexicon, Lexicon):
        lexicon = Lexicon(lexicon)

    entries, missing = lexicon.resolve_all(words, on_missing=on_missing)
    if not entries:
        raise ValueError("none of the requested signs are in the lexicon")

    motions, layout, usable, coverage = load_motions(entries, config)
    glosses = [w for w, _ in entries]

    frames, segments, hand_track = mo.build_timeline(
        motions, glosses, layout,
        fps=config.fps,
        speed=config.speed,
        min_sign_seconds=config.min_sign_seconds,
        lead_in=config.lead_in,
        tail=config.tail,
        transition_kwargs=config.transition,
        flags=coverage,
    )

    # A hand is only drawn articulated where enough of its 21 joints were
    # genuinely detected; elsewhere it becomes a fist.
    hands_ok = hand_track >= config.hand_min_coverage

    subs = SubtitleRenderer(
        config.width, config.height,
        band_height=config.subtitle_band,
        sentence=sentence,
        words=glosses,
        show_sentence=config.show_sentence,
        show_word=config.show_word,
        mono=config.style == "stick",
    )

    stage_h = config.height - subs.band
    view = fit_view(frames, usable, layout, config.width, stage_h,
                    torso_length=config.torso_length)
    avatar = make_renderer(
        config.style, layout, usable, view,
        palette=palette,
        show_face=config.show_face,
        torso_length=config.torso_length,
        stroke=config.stroke,
    )

    labels = word_at_frame(segments, frames.shape[0])

    os.makedirs(os.path.dirname(os.path.abspath(output)) or ".", exist_ok=True)
    writer = cv2.VideoWriter(
        output,
        cv2.VideoWriter_fourcc(*config.codec),
        config.fps,
        (config.width, config.height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"could not open video writer for {output}")

    try:
        for i in range(frames.shape[0]):
            canvas = np.full((config.height, config.width, 3),
                             palette.background, np.uint8)
            avatar.render(frames[i], canvas=canvas, hands=hands_ok[i])
            subs.draw(canvas, labels[i])
            writer.write(canvas)
            if progress:
                progress(i + 1, frames.shape[0])
    finally:
        writer.release()

    n = frames.shape[0]
    return RenderResult(
        path=output,
        frames=n,
        fps=config.fps,
        duration=n / config.fps,
        segments=segments,
        words=glosses,
        missing=missing,
    )
