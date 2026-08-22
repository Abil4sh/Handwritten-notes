"""Structure a text file into a note, then optionally render it.

    python -m scripts.structure_text notes.txt
    python -m scripts.structure_text notes.txt --render --style caveat --paper ruled
"""

import argparse
import json
from pathlib import Path

from app.notes.structure import structure_note
from app.render.page_renderer import render_note

OUT_DIR = Path(__file__).resolve().parent.parent / "out"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="path to a plain text file")
    parser.add_argument("--render", action="store_true", help="also render a PDF")
    parser.add_argument("--template", default="lecture")
    parser.add_argument("--style", default="patrick_hand")
    parser.add_argument("--paper", default="plain")
    args = parser.parse_args()

    source = Path(args.path)
    note = structure_note(source.read_text())

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"{source.stem}.json"
    json_path.write_text(json.dumps(note.model_dump(), indent=2))
    print(f"{note.title}: {len(note.blocks)} blocks -> {json_path}")

    for block in note.blocks:
        text = getattr(block, "text", "")
        print(f"  {block.type:<11} {text[:60]}")

    if args.render:
        pdf_path = OUT_DIR / f"{source.stem}.pdf"
        pages = render_note(note, str(pdf_path), args.style, args.paper, args.template)
        print(f"\n{pages} page(s) -> {pdf_path}")


if __name__ == "__main__":
    main()
