"""Validate every sample note against the schema.

Run from the backend/ directory:   python scripts/validate_notes.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from app.notes.schema import Note

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def main() -> None:
    paths = sorted(SAMPLES_DIR.glob("*.json"))
    if not paths:
        print(f"No sample notes found in {SAMPLES_DIR}")
        sys.exit(1)

    failures = 0
    for path in paths:
        try:
            note = Note.model_validate(json.loads(path.read_text()))
        except ValidationError as exc:
            failures += 1
            print(f"FAIL  {path.name}")
            for error in exc.errors():
                location = ".".join(str(part) for part in error["loc"])
                print(f"        {location}: {error['msg']}")
            continue
        except json.JSONDecodeError as exc:
            failures += 1
            print(f"FAIL  {path.name}  (not valid JSON: {exc})")
            continue

        counts = Counter(block.type for block in note.blocks)
        breakdown = ", ".join(f"{name} x{n}" for name, n in sorted(counts.items()))
        print(f"OK    {path.name:<24} {len(note.blocks):>3} blocks  ({breakdown})")

    print()
    if failures:
        print(f"{failures} of {len(paths)} sample(s) failed validation.")
        sys.exit(1)
    print(f"All {len(paths)} sample(s) valid.")


if __name__ == "__main__":
    main()
