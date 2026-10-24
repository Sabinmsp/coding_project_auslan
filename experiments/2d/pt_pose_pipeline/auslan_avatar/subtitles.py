"""
Subtitle track construction and rendering.

Two things are drawn in the bottom band:

  * the gloss of the sign being performed right now, large;
  * optionally the full English sentence, with the active word highlighted.
"""

import os

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
    HAVE_PIL = True
except ImportError:  # pragma: no cover
    HAVE_PIL = False

import cv2


_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _load_font(size, bold=True):
    if not HAVE_PIL:
        return None
    names = _FONT_CANDIDATES if bold else _FONT_CANDIDATES[1:]
    for path in names:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default()
    except Exception:  # pragma: no cover
        return None


def word_at_frame(segments, n_frames):
    """
    Map every timeline frame to the gloss that should be on screen.

    A transition is split down the middle: the first half still belongs to
    the sign that is finishing, the second half to the one starting.
    """
    labels = [None] * n_frames

    for seg in segments:
        if seg.kind == "sign":
            for i in range(seg.start, seg.end):
                labels[i] = seg.word

    for seg in segments:
        if seg.kind == "transition":
            outgoing, _, incoming = seg.word.partition("→")
            mid = (seg.start + seg.end) // 2
            for i in range(seg.start, mid):
                labels[i] = outgoing
            for i in range(mid, seg.end):
                labels[i] = incoming
        elif seg.kind == "hold":
            for i in range(seg.start, seg.end):
                labels[i] = seg.word

    # any residual gaps inherit the previous label
    last = None
    for i in range(n_frames):
        if labels[i] is None:
            labels[i] = last
        else:
            last = labels[i]
    return labels


def display_form(word):
    """STUDENT -> Student, leaving mixed-case input alone."""
    if word is None:
        return ""
    return word.capitalize() if word.isupper() or word.islower() else word


class SubtitleRenderer:
    def __init__(self, width, height, band_height=None, sentence=None,
                 words=None, show_sentence=True, show_word=True, mono=False):
        self.width = width
        self.height = height
        self.band = band_height or max(96, int(height * 0.16))
        self.sentence = sentence
        self.words = [w.lower() for w in (words or [])]
        self.show_sentence = show_sentence and bool(sentence)
        self.show_word = show_word
        self.mono = mono

        # Greyscale theme to match the stick-figure style.
        if mono:
            self.band_bgr = (255, 255, 255)
            self.band_alpha = 1.0
            self.rule_bgr = (170, 170, 170)
            self.word_rgb = (20, 20, 20)
            self.sentence_rgb = (135, 135, 135)
            self.active_rgb = (20, 20, 20)
        else:
            self.band_bgr = (26, 22, 20)
            self.band_alpha = 0.82
            self.rule_bgr = (90, 80, 72)
            self.word_rgb = (255, 248, 235)
            self.sentence_rgb = (205, 198, 190)
            self.active_rgb = (255, 214, 120)

        self.font_word = _load_font(int(self.band * 0.40), bold=True)
        self.font_sentence = _load_font(int(self.band * 0.21), bold=False)

    # -- helpers ----------------------------------------------------------

    def _measure(self, draw, text, font):
        if font is None:
            return (len(text) * 10, 16)
        box = draw.textbbox((0, 0), text, font=font)
        return (box[2] - box[0], box[3] - box[1])

    def _sentence_tokens(self):
        """Split the sentence into tokens, flagging which are signable words."""
        out = []
        for raw in (self.sentence or "").split():
            key = "".join(ch for ch in raw.lower() if ch.isalpha())
            out.append((raw, key))
        return out

    # -- drawing ----------------------------------------------------------

    def draw(self, img, word):
        """Composite the subtitle band onto a BGR frame, in place."""
        h, w = img.shape[:2]
        top = h - self.band

        # translucent band
        overlay = img.copy()
        cv2.rectangle(overlay, (0, top), (w, h), self.band_bgr, -1)
        cv2.addWeighted(overlay, self.band_alpha, img,
                        1.0 - self.band_alpha, 0, img)
        cv2.line(img, (0, top), (w, top), self.rule_bgr, 2, cv2.LINE_AA)

        if not HAVE_PIL:
            return self._draw_cv2(img, word, top)

        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil)

        y = top + int(self.band * 0.12)
        if self.show_word:
            text = display_form(word)
            tw, th = self._measure(draw, text, self.font_word)
            draw.text(((w - tw) / 2, y), text, font=self.font_word,
                      fill=self.word_rgb)
            y += th + int(self.band * 0.16)

        if self.show_sentence:
            self._draw_sentence(draw, w, y, word)

        img[:] = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
        return img

    def _draw_sentence(self, draw, w, y, active):
        tokens = self._sentence_tokens()
        active_key = (active or "").lower()
        font = self.font_sentence
        space = self._measure(draw, " ", font)[0]

        widths = [self._measure(draw, t[0], font)[0] for t in tokens]
        total = sum(widths) + space * max(0, len(tokens) - 1)

        # wrap onto two lines if needed
        lines, line, line_w = [], [], 0
        limit = w * 0.92
        if total <= limit:
            lines = [list(range(len(tokens)))]
        else:
            for i, tw in enumerate(widths):
                add = tw + (space if line else 0)
                if line and line_w + add > limit:
                    lines.append(line)
                    line, line_w = [i], tw
                else:
                    line.append(i)
                    line_w += add
            if line:
                lines.append(line)

        line_h = self._measure(draw, "Ag", font)[1] + int(self.band * 0.06)
        for row, idxs in enumerate(lines):
            row_w = sum(widths[i] for i in idxs) + space * max(0, len(idxs) - 1)
            x = (w - row_w) / 2
            for i in idxs:
                raw, key = tokens[i]
                hot = key and key == active_key
                draw.text(
                    (x, y + row * line_h), raw, font=font,
                    fill=self.active_rgb if hot else self.sentence_rgb,
                )
                x += widths[i] + space

    def _draw_cv2(self, img, word, top):
        """Plain OpenCV fallback when Pillow is unavailable."""
        h, w = img.shape[:2]
        text = display_form(word)
        size = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 1.4, 3)[0]
        cv2.putText(img, text, ((w - size[0]) // 2, top + size[1] + 14),
                    cv2.FONT_HERSHEY_DUPLEX, 1.4, self.word_rgb[::-1], 3,
                    cv2.LINE_AA)
        if self.show_sentence:
            s = self.sentence
            size2 = cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            cv2.putText(img, s, ((w - size2[0]) // 2, h - 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        self.sentence_rgb[::-1], 2, cv2.LINE_AA)
        return img
