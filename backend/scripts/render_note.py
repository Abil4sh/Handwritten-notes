"""Render a note JSON file to PDF.

Run from the backend/ directory:
    python -m scripts.render_note samples/binary_search.json
    python -m scripts.render_note samples/binary_search.json --font caveat
"""

import argparse
import json
from pathlib import Path

from app.notes.schema import Note
from app.render.handwriting import style_ids
from app.render.paper import paper_ids
from app.render.page_renderer import render_note

OUT_DIR = Path(__file__).resolve().parent.parent / "out"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("note", help="path to a note JSON file")
    parser.add_argument("--style", default="patrick_hand", help="handwriting style id")
    parser.add_argument("--paper", default="plain", help="paper id")
    parser.add_argument("--out", default=None, help="output PDF path")
    args = parser.parse_args()

    available = style_ids()
    if args.style not in available:
        parser.error(f"unknown style '{args.style}'. Available: {', '.join(available)}")

    papers = paper_ids()
    if args.paper not in papers:
        parser.error(f"unknown paper '{args.paper}'. Available: {', '.join(papers)}")

    note_path = Path(args.note)
    note = Note.model_validate(json.loads(note_path.read_text()))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else OUT_DIR / f"{note_path.stem}_{args.style}_{args.paper}.pdf"

    pages = render_note(note, str(out_path), args.style, args.paper)
    size_kb = out_path.stat().st_size / 1024
    print(f"{note.title}: {len(note.blocks)} blocks -> {pages} page(s), {size_kb:.0f} KB")
    print(out_path)


if __name__ == "__main__":
    main()
