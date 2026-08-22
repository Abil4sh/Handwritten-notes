"""Paper backgrounds.

A paper is a JSON config describing what gets drawn *underneath* the text:
background tint, rulings, margin rule. It also declares whether text should be
snapped to its ruling pitch, which is the one place paper and layout meet.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm

PAPERS_DIR = Path(__file__).resolve().parent / "papers"


@dataclass(frozen=True)
class Paper:
    id: str
    name: str
    background: str
    rules: tuple
    snap_leading: bool
    baseline_lift_pt: float

    @property
    def line_pitch(self) -> float | None:
        """Vertical ruling pitch in points, or None if the paper has no rulings."""
        for rule in self.rules:
            if rule["type"] == "horizontal":
                return rule["pitch_mm"] * mm
        return None


@lru_cache(maxsize=1)
def load_papers() -> dict[str, Paper]:
    papers: dict[str, Paper] = {}
    for path in sorted(PAPERS_DIR.glob("*.json")):
        config = json.loads(path.read_text())
        papers[config["id"]] = Paper(
            id=config["id"],
            name=config["name"],
            background=config["background"],
            rules=tuple(config["rules"]),
            snap_leading=config["snap_leading"],
            baseline_lift_pt=config["baseline_lift_pt"],
        )
    return papers


def paper_ids() -> list[str]:
    return list(load_papers().keys())


def get_paper(paper_id: str) -> Paper:
    return load_papers()[paper_id]


def draw_background(canvas, paper: Paper, page_width: float, page_height: float) -> None:
    """Draw the paper. Must be called before any text on the page."""
    canvas.setFillColor(HexColor(paper.background))
    canvas.rect(0, 0, page_width, page_height, stroke=0, fill=1)

    for rule in paper.rules:
        canvas.setStrokeColor(HexColor(rule["color"]))
        canvas.setLineWidth(rule["width"])

        if rule["type"] == "horizontal":
            pitch = rule["pitch_mm"] * mm
            y = page_height - pitch
            while y > 0:
                canvas.line(0, y, page_width, y)
                y -= pitch

        elif rule["type"] == "vertical":
            x = rule["x_mm"] * mm
            canvas.line(x, 0, x, page_height)

        elif rule["type"] == "grid":
            pitch = rule["pitch_mm"] * mm
            y = page_height - pitch
            while y > 0:
                canvas.line(0, y, page_width, y)
                y -= pitch
            x = pitch
            while x < page_width:
                canvas.line(x, 0, x, page_height)
                x += pitch

    canvas.setFillColor(HexColor("#000000"))
