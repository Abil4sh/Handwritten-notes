"""Download handwriting fonts from the official google/fonts repository.

Run from the backend/ directory:   python scripts/fetch_fonts.py
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

RAW_BASE = "https://raw.githubusercontent.com/google/fonts/main"

FONTS_DIR = Path(__file__).resolve().parent.parent / "app" / "handwriting" / "fonts"
MANIFEST = FONTS_DIR / "fonts.json"
FILES_DIR = FONTS_DIR / "files"
LICENSE_DIR = FONTS_DIR / "licenses"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Only the path needs escaping; "[" and "]" are not legal raw URL characters.
    safe_url = urllib.parse.quote(url, safe=":/")
    with urllib.request.urlopen(safe_url, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} for {url}")
        dest.write_bytes(response.read())


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    notice_lines = [
        "This project bundles the following fonts from the Google Fonts project",
        f"({manifest['source']}). Each is used unmodified under its own license.",
        "",
    ]

    for font in manifest["fonts"]:
        font_path = FILES_DIR / font["file"]
        download(f"{RAW_BASE}/{font['repo_dir']}/{font['file']}", font_path)

        license_path = LICENSE_DIR / f"{font['id']}-OFL.txt"
        download(f"{RAW_BASE}/{font['repo_dir']}/OFL.txt", license_path)

        size_kb = font_path.stat().st_size / 1024
        print(f"  {font['family']:<20} {size_kb:7.1f} KB   {font['license']}")

        notice_lines.append(
            f"{font['family']} — {font['license']} — "
            f"licenses/{license_path.name} — "
            f"https://github.com/google/fonts/tree/main/{font['repo_dir']}"
        )

    (FONTS_DIR / "NOTICE.txt").write_text("\n".join(notice_lines) + "\n")
    print(f"\n{len(manifest['fonts'])} fonts installed. Wrote {FONTS_DIR / 'NOTICE.txt'}")


if __name__ == "__main__":
    main()
