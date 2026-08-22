"""Handwriting rendering.

Answers exactly one question: "what does this run of text look like, written
by hand?" It knows nothing about pages, blocks, or templates.

The page renderer talks to this through two methods -- `measure` and
`draw_run`. That pair is the seam. In MVP 3, PersonalGlyphRenderer will
implement the same two methods using bitmap glyphs from a user's own
handwriting, and the page renderer will not change at all.
"""

import json
import math
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics

STYLES_DIR = Path(__file__).resolve().parent.parent / "handwriting" / "styles"


@dataclass(frozen=True)
class Jitter:
    unit: str = "glyph"           # "glyph" for print hands, "word" for cursive
    baseline_sigma_pt: float = 0.0
    rotation_sigma_deg: float = 0.0
    size_sigma_pct: float = 0.0
    letter_space_sigma_pt: float = 0.0
    word_space_sigma_pt: float = 0.0
    line_start_sigma_pt: float = 0.0
    line_slope_sigma_deg: float = 0.0
    word_space_bias_pt: float = 0.0


@dataclass(frozen=True)
class HandwritingStyle:
    id: str
    name: str
    font_id: str
    size_multiplier: float
    ink: str
    jitter: Jitter


def clamped_gauss(rng: random.Random, sigma: float) -> float:
    """Gaussian noise with the tails cut off at 2 sigma.

    Unclamped, roughly one glyph in twenty gets a visibly wrong offset, which
    reads as a rendering fault rather than as handwriting.
    """
    if sigma <= 0:
        return 0.0
    return max(-2 * sigma, min(2 * sigma, rng.gauss(0, sigma)))


class HandwritingRenderer(Protocol):
    def measure(self, text: str, size_pt: float) -> float:
        """Width of `text` in points, as it will actually be drawn."""

    def draw_run(
        self, canvas, text: str, x: float, y: float, size_pt: float, seed: int, ink: str | None = None
    ) -> float:
        """Draw `text` with its baseline starting at (x, y). Returns width drawn."""


class FontGlyphRenderer:
    """Draws text with a real font, displacing glyphs to break up regularity."""

    def __init__(self, style: HandwritingStyle):
        self.style = style
        self.font_id = style.font_id
        self.j = style.jitter

    def size(self, size_pt: float) -> float:
        return size_pt * self.style.size_multiplier

    def measure(self, text: str, size_pt: float) -> float:
        # Jitter is zero-mean apart from the word-space bias, so expected width
        # is the plain font width plus that bias once per space.
        width = pdfmetrics.stringWidth(text, self.font_id, self.size(size_pt))
        return width + text.count(" ") * self.j.word_space_bias_pt

    def _units(self, text: str) -> list[str]:
        """Split into the pieces that get displaced independently."""
        if self.j.unit == "word":
            # Cursive letterforms connect. Displacing individual glyphs snaps
            # those joins and looks broken, so whole words move together.
            parts: list[str] = []
            for i, word in enumerate(text.split(" ")):
                if i:
                    parts.append(" ")
                if word:
                    parts.append(word)
            return parts
        return list(text)

    def draw_run(
        self, canvas, text: str, x: float, y: float, size_pt: float, seed: int, ink: str | None = None
    ) -> float:
        if not text:
            return 0.0

        rng = random.Random(seed)
        size = self.size(size_pt)
        canvas.setFont(self.font_id, size)
        canvas.setFillColor(HexColor(ink or self.style.ink))

        # One slope for the whole line: real handwriting drifts, it does not
        # wobble randomly around a perfect horizontal.
        slope = math.tan(math.radians(clamped_gauss(rng, self.j.line_slope_sigma_deg)))

        cursor = x + clamped_gauss(rng, self.j.line_start_sigma_pt)
        start = cursor

        for unit in self._units(text):
            advance = pdfmetrics.stringWidth(unit, self.font_id, size)

            if unit == " ":
                cursor += advance + self.j.word_space_bias_pt + clamped_gauss(rng, self.j.word_space_sigma_pt)
                continue

            dy = clamped_gauss(rng, self.j.baseline_sigma_pt)
            rotation = clamped_gauss(rng, self.j.rotation_sigma_deg)
            scale = 1.0 + clamped_gauss(rng, self.j.size_sigma_pct / 100.0)

            canvas.saveState()
            canvas.translate(cursor, y + dy + (cursor - start) * slope)
            canvas.rotate(rotation)
            canvas.scale(scale, scale)
            canvas.drawString(0, 0, unit)
            canvas.restoreState()

            cursor += advance * scale + clamped_gauss(rng, self.j.letter_space_sigma_pt)

        return cursor - x


@lru_cache(maxsize=1)
def load_styles() -> dict[str, HandwritingStyle]:
    styles: dict[str, HandwritingStyle] = {}
    for path in sorted(STYLES_DIR.glob("*.json")):
        config = json.loads(path.read_text())
        styles[config["id"]] = HandwritingStyle(
            id=config["id"],
            name=config["name"],
            font_id=config["font_id"],
            size_multiplier=config["size_multiplier"],
            ink=config["ink"],
            jitter=Jitter(**config["jitter"]),
        )
    return styles


def style_ids() -> list[str]:
    return list(load_styles().keys())


def get_renderer(style_id: str) -> FontGlyphRenderer:
    return FontGlyphRenderer(load_styles()[style_id])
