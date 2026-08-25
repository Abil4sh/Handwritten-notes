"""Page renderer.

Turns a Note into a PDF. Owns page geometry, line breaking, and pagination.

Every visual decision comes from the template config. This module contains no
template names -- if it did, the system would not be config-driven and adding a
template would mean editing the renderer.
"""

import math
import random

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.notes.schema import Note
from app.render.fonts import load_fonts
from app.render.handwriting import HandwritingRenderer, get_renderer
from app.render.paper import Paper, draw_background, get_paper
from app.render.template import block_style, get_template

HIGHLIGHT_COLORS = {
    "yellow": "#f5e06a",
    "green": "#a8dc8c",
    "blue": "#96c9ec",
    "pink": "#f0a8c0",
    "orange": "#f5bb78",
}

PAGE_WIDTH, PAGE_HEIGHT = A4


def block_text(block) -> str:
    """The text a block contributes to the page, flattened for layout."""
    if block.type == "definition":
        return f"{block.term} \u2014 {block.text}"
    if block.type == "quote":
        text = f"\u201c{block.text}\u201d"
        return f"{text} \u2014 {block.attribution}" if block.attribution else text
    if block.type == "example":
        return f"e.g. {block.text}"
    if block.type == "divider":
        return ""
    return block.text


def marker_for(block, style: dict) -> str:
    if block.type == "numbered":
        return f"{block.index}."
    return style.get("marker", "")


class PageRenderer:
    def __init__(
        self,
        out_path: str,
        hw: HandwritingRenderer,
        paper: Paper,
        template: dict,
        seed: int = 0,
        scale: float = 1.0,
    ):
        load_fonts()
        self.hw = hw
        self.paper = paper
        self.template = template
        self.seed = seed
        self.line_counter = 0
        self.canvas = canvas.Canvas(out_path, pagesize=A4)

        page = template["page"]
        margins = page["margins_mm"]
        self.page_left = margins["left"] * mm
        self.right = PAGE_WIDTH - margins["right"] * mm
        self.top = PAGE_HEIGHT - margins["top"] * mm
        self.bottom = margins["bottom"] * mm + page["bottom_reserved_mm"] * mm

        # A cue column pushes the body text right and gives headings a home.
        self.cue = page["cue_column"]
        if self.cue:
            usable = self.right - self.page_left
            self.cue_width = usable * self.cue["width_pct"] / 100.0
            self.left = self.page_left + self.cue_width + self.cue["gap_mm"] * mm
        else:
            self.cue_width = 0.0
            self.left = self.page_left

        # Paper with a margin rule overrides the template's left margin.
        for rule in paper.rules:
            if rule["type"] == "vertical" and not self.cue:
                self.left = max(self.left, rule["x_mm"] * mm + 4 * mm)

        self.scale = scale
        self.pitch = paper.line_pitch if paper.snap_leading else None
        self.cue_floor = PAGE_HEIGHT  # lowest cue entry so far, to avoid overlap
        self.page_number = 1
        self.start_page()
        self.y = self.first_baseline()

    def sized(self, size_pt: float) -> float:
        """Every point size passes through here, so one slider scales the lot."""
        return size_pt * self.scale

    # -- ruling arithmetic -------------------------------------------

    def first_baseline(self) -> float:
        title_size = self.sized(self.template["title"]["size_pt"])
        if not self.pitch:
            return self.top - title_size
        limit = self.top - title_size
        k = math.ceil((PAGE_HEIGHT - limit) / self.pitch)
        return PAGE_HEIGHT - k * self.pitch + self.paper.baseline_lift_pt

    def snap_leading(self, leading: float) -> float:
        if not self.pitch:
            return leading
        return max(1, math.ceil(leading / self.pitch)) * self.pitch

    def snap_gap(self, gap: float) -> float:
        if not self.pitch:
            return gap
        return round(gap / self.pitch) * self.pitch

    # -- measurement -------------------------------------------------

    def measure(self, text: str, size_pt: float) -> float:
        return self.hw.measure(text, size_pt)

    def next_seed(self) -> int:
        """Deterministic per-line seed: same note renders identically forever."""
        self.line_counter += 1
        return self.seed * 100003 + self.line_counter

    def wrap(self, text: str, size_pt: float, width: float) -> list[str]:
        """Greedy line breaking using real font metrics."""
        if not text:
            return []
        lines: list[str] = []
        current: list[str] = []

        for word in text.split():
            if not current:
                current = [word]
                continue
            trial = " ".join(current + [word])
            if self.measure(trial, size_pt) <= width:
                current.append(word)
            else:
                lines.append(" ".join(current))
                current = [word]

        if current:
            lines.append(" ".join(current))
        return lines

    # -- page management ---------------------------------------------

    def start_page(self) -> None:
        draw_background(self.canvas, self.paper, PAGE_WIDTH, PAGE_HEIGHT)
        self.draw_template_rules()
        self.cue_floor = PAGE_HEIGHT

    def draw_template_rules(self) -> None:
        page = self.template["page"]
        for rule in page["rules"]:
            self.canvas.setStrokeColor(HexColor(rule["color"]))
            self.canvas.setLineWidth(rule["width"])

            if rule["type"] == "cue_divider" and self.cue:
                x = self.left - self.cue["gap_mm"] * mm / 2
                self.canvas.line(x, page["margins_mm"]["bottom"] * mm, x, self.top + 6 * mm)

            elif rule["type"] == "summary_divider":
                y = page["margins_mm"]["bottom"] * mm + page["bottom_reserved_mm"] * mm
                self.canvas.line(self.page_left, y, self.right, y)

    def new_page(self) -> None:
        self.draw_page_number()
        self.canvas.showPage()
        self.page_number += 1
        self.start_page()
        self.y = self.first_baseline()

    def draw_page_number(self) -> None:
        if not self.template["page"]["page_numbers"]:
            return
        self.canvas.setFont(self.hw.font_id, 10)
        self.canvas.setFillGray(0.45)
        self.canvas.drawCentredString(
            (self.left + self.right) / 2,
            self.template["page"]["margins_mm"]["bottom"] * mm - 10 * mm,
            str(self.page_number),
        )
        self.canvas.setFillGray(0)

    def space_left(self) -> float:
        return self.y - self.bottom

    # -- drawing -----------------------------------------------------

    def draw_title(self, title: str) -> None:
        style = self.template["title"]
        size = self.sized(style["size_pt"])
        x = self.page_left if self.cue else self.left
        width = self.hw.draw_run(self.canvas, title, x, self.y, size, self.next_seed())
        if style["underline"]:
            self.canvas.setStrokeColor(HexColor(self.hw.style.ink))
            self.canvas.setLineWidth(0.8)
            self.canvas.line(x, self.y - 4, x + width, self.y - 4)
        self.y -= self.snap_leading(size * style["leading_mult"])
        self.y -= self.snap_gap(style["space_after_mm"] * mm)

    def draw_divider(self, style: dict) -> None:
        self.y -= self.snap_gap(style.get("space_before_mm", 0) * mm)
        if self.space_left() < 6 * mm:
            self.new_page()
        self.canvas.setStrokeColor(HexColor(self.template["ink"]["rule"]))
        self.canvas.setLineWidth(0.7)
        mid = (self.left + self.right) / 2
        self.canvas.line(mid - 20 * mm, self.y, mid + 20 * mm, self.y)
        self.y -= self.snap_gap(style.get("space_after_mm", 0) * mm)

    def draw_left_bar(self, style: dict, block_top: float) -> None:
        if not style.get("left_bar"):
            return
        x = self.left + style.get("indent_mm", 0) * mm - 3 * mm
        self.canvas.setStrokeColor(HexColor(self.template["ink"]["accent"]))
        self.canvas.setLineWidth(1.2)
        self.canvas.line(x, block_top + 2, x, self.y + 4)

    def ink_for(self, style: dict) -> str:
        return self.template["ink"]["accent"] if style.get("accent") else self.hw.style.ink

    def draw_cue_heading(self, block, style: dict) -> None:
        """Cornell: headings live in the left cue column, beside the body text."""
        size = self.sized(style["size_pt"])
        leading = self.snap_leading(size * style["leading_mult"])
        lines = self.wrap(block_text(block), size, self.cue_width)

        top = min(self.y, self.cue_floor - leading)
        if top - leading * len(lines) < self.bottom:
            self.new_page()
            top = self.y

        y = top
        for line in lines:
            self.hw.draw_run(self.canvas, line, self.page_left, y, size, self.next_seed())
            y -= leading

        self.cue_floor = y
        # The body does not move down for a cue heading; it only starts at or
        # below the heading's first line, which is what puts them side by side.
        self.y = min(self.y, top)

    def draw_highlights(self, line: str, offset: int, x: float, size: float, marks) -> None:
        """Marker strokes behind a line, drawn before the text so ink sits on top.

        A real highlighter overshoots the words and does not stop cleanly, so
        each band is nudged and extended slightly.
        """
        line_start, line_end = offset, offset + len(line)

        for mark in marks:
            start = max(mark.start, line_start)
            end = min(mark.end, line_end)
            if start >= end:
                continue

            before = line[: start - line_start]
            inside = line[start - line_start : end - line_start]
            x0 = x + self.measure(before, size)
            width = self.measure(inside, size)

            rng = random.Random(self.seed * 7919 + offset + mark.start)
            colour = HIGHLIGHT_COLORS[mark.color]

            if mark.kind == "underline":
                self.canvas.setStrokeColor(HexColor(colour))
                self.canvas.setLineWidth(1.6)
                y = self.y - size * 0.22 + rng.uniform(-0.6, 0.6)
                self.canvas.line(x0, y, x0 + width + rng.uniform(0, 2), y)
                continue

            self.canvas.setFillColor(HexColor(colour), alpha=0.42)
            self.canvas.rect(
                x0 - 1.2 + rng.uniform(-0.8, 0.8),
                self.y - size * 0.26 + rng.uniform(-0.7, 0.7),
                width + 2.6 + rng.uniform(-0.5, 1.6),
                size * 1.02 + rng.uniform(-0.6, 0.9),
                stroke=0,
                fill=1,
            )
            self.canvas.setFillAlpha(1)

    def draw_block(self, block) -> None:
        style = block_style(self.template, block)

        if block.type == "divider":
            self.draw_divider(style)
            return

        if self.cue and block.type == "heading":
            self.draw_cue_heading(block, style)
            return

        text = block_text(block)
        marker = marker_for(block, style)
        size = self.sized(style["size_pt"])
        leading = self.snap_leading(size * style["leading_mult"])

        # Hanging indent: the marker sits at `marker_x`, and every line of text
        # -- first and continuation alike -- starts at `text_x`.
        marker_x = self.left + style.get("indent_mm", 0) * mm
        text_x = marker_x + style.get("hanging_indent_mm", 0) * mm
        lines = self.wrap(text, size, self.right - text_x)
        if not lines:
            return

        self.y -= self.snap_gap(style.get("space_before_mm", 0) * mm)

        # Widow/orphan control: never strand a heading, or the first line of a
        # multi-line block, at the bottom of a page.
        body = self.template["blocks"]["paragraph"]
        body_leading = self.snap_leading(self.sized(body["size_pt"]) * body["leading_mult"])
        if block.type == "heading":
            needed = leading * len(lines) + body_leading * 2
        elif len(lines) == 1:
            needed = leading
        else:
            needed = leading * 2
        if self.space_left() < needed:
            self.new_page()

        block_top = self.y
        ink = self.ink_for(style)
        marks = getattr(block, "marks", [])
        offset = 0

        for i, line in enumerate(lines):
            if self.space_left() < leading:
                self.draw_left_bar(style, block_top)
                self.new_page()
                block_top = self.y

            if i == 0 and marker:
                self.hw.draw_run(self.canvas, marker, marker_x, self.y, size, self.next_seed(), ink)

            if style.get("centered"):
                line_x = (self.left + self.right) / 2 - self.measure(line, size) / 2
            else:
                line_x = text_x

            if marks:
                self.draw_highlights(line, offset, line_x, size, marks)
            width = self.hw.draw_run(self.canvas, line, line_x, self.y, size, self.next_seed(), ink)

            if style.get("underline") and i == len(lines) - 1:
                self.canvas.setStrokeColor(HexColor(ink))
                self.canvas.setLineWidth(0.6)
                self.canvas.line(line_x, self.y - 3, line_x + width, self.y - 3)

            # +1 for the space the wrapper consumed between lines
            offset += len(line) + 1
            self.y -= leading

        self.draw_left_bar(style, block_top)
        self.y -= self.snap_gap(style.get("space_after_mm", 0) * mm)

    def render(self, note: Note) -> None:
        self.draw_title(note.title)
        for block in note.blocks:
            self.draw_block(block)
        self.draw_page_number()
        self.canvas.save()


def render_note(
    note: Note,
    out_path: str,
    style_id: str = "patrick_hand",
    paper_id: str = "plain",
    template_id: str = "lecture",
    seed: int = 0,
    scale: float = 1.0,
) -> int:
    renderer = PageRenderer(
        out_path,
        get_renderer(style_id),
        get_paper(paper_id),
        get_template(template_id),
        seed,
        scale,
    )
    renderer.render(note)
    return renderer.page_number
