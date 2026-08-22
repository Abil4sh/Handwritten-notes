"""Font registry.

Reads the manifest, registers every font with ReportLab exactly once, and
exposes them by id. Registration is expensive (it parses the whole TTF), so
we do it lazily and cache the result.
"""

import json
from functools import lru_cache
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONTS_DIR = Path(__file__).resolve().parent.parent / "handwriting" / "fonts"


@lru_cache(maxsize=1)
def load_fonts() -> dict[str, dict]:
    """Register every font in the manifest. Returns {font_id: metadata}."""
    manifest = json.loads((FONTS_DIR / "fonts.json").read_text())
    registry: dict[str, dict] = {}

    for font in manifest["fonts"]:
        path = FONTS_DIR / "files" / font["file"]
        if not path.exists():
            raise FileNotFoundError(
                f"Missing font file {path}. Run: python scripts/fetch_fonts.py"
            )
        pdfmetrics.registerFont(TTFont(font["id"], str(path)))
        registry[font["id"]] = font

    return registry


def font_ids() -> list[str]:
    return list(load_fonts().keys())
