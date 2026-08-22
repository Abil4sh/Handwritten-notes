"""Page renderer.

Turns a Note into a PDF. Owns page geometry, line breaking, and pagination.

Still no jitter -- that is Step 5. What this step adds is paper: a background
drawn under every page, and, on ruled paper, leading snapped to the ruling
pitch so that every baseline lands on a line.
"""

import math
from dataclasses import dataclass

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from app.notes.schema import Note
from app.render.fonts import load_fonts
from app.render.handwriting import HandwritingRenderer, get_renderer
from app.render.paper import Paper, draw_background, get_paper


@dataclass(frozen=True)
class BlockStyle:
    """How one kind of block is laid out. Becomes template config in Step 6."""

    size_pt: float = 13.0
    leading_mult: float = 1.45
    space_before_mm: float = 0.0
    space_after_mm: float = 2.5
    indent_mm: float = 0.0
    hanging_indent_mm: float = 0.0
    marker: str = ""
    underline: bool = False
    centered: bool = False
    left_bar: bool = False


STYLES: dict[str, BlockStyle] = {
    "heading_1": BlockStyle(size_pt=20, space_before_mm=7, space_after_mm=2.5, underline=True),
    "heading_2": BlockStyle(size_pt=16, space_before_mm=5, space_after_mm=2.0),
    "heading_3": BlockStyle(size_pt=14, space_before_mm=4, space_after_mm=1.5),
    "paragraph": BlockStyle(),
    "bullet": BlockStyle(marker="\u2022", indent_mm=5, hanging_indent_mm=5, space_after_mm=1.5),
    "numbered": BlockStyle(indent_mm=5, hanging_indent_mm=6, space_after_mm=1.5),
    "definition": BlockStyle(indent_mm=3, hanging_indent_mm=3),
    "example": BlockStyle(size_pt=12, indent_mm=5),
    "formula": BlockStyle(size_pt=15, centered=True, space_before_mm=3, space_after_mm=3),
    "callout": BlockStyle(indent_mm=5, space_before_mm=2, space_after_mm=2.5, left_bar=True),
    "quote": BlockStyle(size_pt=12, indent_mm=6, space_before_mm=2, left_bar=True),
    "divider": BlockStyle(space_before_mm=4, space_after_mm=4),
}

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_TOP_MM = 22
MARGIN_BOTTOM_MM = 20
MARGIN_LEFT_MM = 20
MARGIN_RIGHT_MM = 18
TITLE_SIZE_PT = 26


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


def style_for(block) -> BlockStyle:
    if block.type == "heading":
        return STYLES[f"heading_{block.level}"]
    return STYLES[block.type]


def marker_for(block, style: BlockStyle) -> str:
    if block.type == "numbered":
        return f"{block.index}."
    return style.marker


class PageRenderer:
    def __init__(self, out_path: str, hw: HandwritingRenderer, paper: Paper, seed: int = 0):
        load_fonts()
        self.hw = hw
        self.font_id = hw.font_id
        self.seed = seed
        self.line_counter = 0
        self.paper = paper
        self.canvas = canvas.Canvas(out_path, pagesize=A4)

        # On paper with a margin rule, text starts to the right of it.
        self.left = MARGIN_LEFT_MM * mm
        for rule in paper.rules:
            if rule["type"] == "vertical":
                self.left = rule["x_mm"] * mm + 4 * mm

        self.right = PAGE_WIDTH - MARGIN_RIGHT_MM * mm
        self.top = PAGE_HEIGHT - MARGIN_TOP_MM * mm
        self.bottom = MARGIN_BOTTOM_MM * mm
        self.pitch = paper.line_pitch if paper.snap_leading else None

        self.page_number = 1
        self.start_page()
        self.y = self.first_baseline()

    # -- ruling arithmetic -------------------------------------------

    def first_baseline(self) -> float:
        """Baseline of the first line on a page, snapped to a ruling if any."""
        if not self.pitch:
            return self.top - TITLE_SIZE_PT
        limit = self.top - TITLE_SIZE_PT
        k = math.ceil((PAGE_HEIGHT - limit) / self.pitch)
        return PAGE_HEIGHT - k * self.pitch + self.paper.baseline_lift_pt

    def snap_leading(self, leading: float) -> float:
        """Line spacing must be a whole number of rulings, at least one."""
        if not self.pitch:
            return leading
        return max(1, math.ceil(leading / self.pitch)) * self.pitch

    def snap_gap(self, gap: float) -> float:
        """Gaps round to the nearest ruling -- small ones disappear entirely."""
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

    def new_page(self) -> None:
        self.draw_page_number()
        self.canvas.showPage()
        self.page_number += 1
        self.start_page()
        self.y = self.first_baseline()

    def draw_page_number(self) -> None:
        self.canvas.setFont(self.font_id, 10)
        self.canvas.setFillGray(0.45)
        self.canvas.drawCentredString(
            (self.left + self.right) / 2, self.bottom - 10 * mm, str(self.page_number)
        )
        self.canvas.setFillGray(0)

    def space_left(self) -> float:
        return self.y - self.bottom

    # -- drawing -----------------------------------------------------

    def draw_title(self, title: str) -> None:
        self.hw.draw_run(self.canvas, title, self.left, self.y, TITLE_SIZE_PT, self.next_seed())
        self.y -= self.snap_leading(TITLE_SIZE_PT * 1.3) + self.snap_gap(4 * mm)

    def draw_divider(self, style: BlockStyle) -> None:
        self.y -= self.snap_gap(style.space_before_mm * mm)
        if self.space_left() < 6 * mm:
            self.new_page()
        self.canvas.setStrokeGray(0.65)
        self.canvas.setLineWidth(0.7)
        mid = (self.left + self.right) / 2
        self.canvas.line(mid - 20 * mm, self.y, mid + 20 * mm, self.y)
        self.y -= self.snap_gap(style.space_after_mm * mm)

    def draw_left_bar(self, style: BlockStyle, block_top: float) -> None:
        if not style.left_bar:
            return
        x = self.left + style.indent_mm * mm - 3 * mm
        self.canvas.setStrokeGray(0.55)
        self.canvas.setLineWidth(1.2)
        self.canvas.line(x, block_top + 2, x, self.y + 4)

    def draw_block(self, block) -> None:
        style = style_for(block)

        if block.type == "divider":
            self.draw_divider(style)
            return

        text = block_text(block)
        marker = marker_for(block, style)
        leading = self.snap_leading(style.size_pt * style.leading_mult)

        # Hanging indent: the marker sits at `marker_x`, and every line of text
        # -- first and continuation alike -- starts at `text_x`.
        marker_x = self.left + style.indent_mm * mm
        text_x = marker_x + style.hanging_indent_mm * mm
        lines = self.wrap(text, style.size_pt, self.right - text_x)
        if not lines:
            return

        self.y -= self.snap_gap(style.space_before_mm * mm)

        # Widow/orphan control: never strand a heading, or the first line of a
        # multi-line block, at the bottom of a page.
        body = STYLES["paragraph"]
        body_leading = self.snap_leading(body.size_pt * body.leading_mult)
        if block.type == "heading":
            needed = leading * len(lines) + body_leading * 2
        elif len(lines) == 1:
            needed = leading
        else:
            needed = leading * 2
        if self.space_left() < needed:
            self.new_page()

        block_top = self.y

        for i, line in enumerate(lines):
            if self.space_left() < leading:
                self.draw_left_bar(style, block_top)
                self.new_page()
                block_top = self.y

            if i == 0 and marker:
                self.hw.draw_run(self.canvas, marker, marker_x, self.y, style.size_pt, self.next_seed())

            if style.centered:
                width = self.measure(line, style.size_pt)
                line_x = (self.left + self.right) / 2 - width / 2
            else:
                line_x = text_x
            self.hw.draw_run(self.canvas, line, line_x, self.y, style.size_pt, self.next_seed())

            if style.underline and i == len(lines) - 1:
                width = self.measure(line, style.size_pt)
                self.canvas.setStrokeColor(HexColor(self.hw.style.ink))
                self.canvas.setLineWidth(0.6)
                self.canvas.line(text_x, self.y - 3, text_x + width, self.y - 3)

            self.y -= leading

        self.draw_left_bar(style, block_top)
        self.y -= self.snap_gap(style.space_after_mm * mm)

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
    seed: int = 0,
) -> int:
    renderer = PageRenderer(out_path, get_renderer(style_id), get_paper(paper_id), seed)
    renderer.render(note)
    return renderer.page_number
