"""Note templates.

A template is a JSON file describing every visual decision: page geometry,
per-block sizing and spacing, rules, and column structure. The renderer reads
these values and never branches on a template id.

Every template is merged over `base.json`, so a template only declares what it
changes. Adding a property to base.json therefore does not require editing the
other template files.
"""

import copy
import json
from functools import lru_cache
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
BASE_ID = "base"


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge `override` onto a copy of `base`."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


@lru_cache(maxsize=1)
def load_templates() -> dict[str, dict]:
    base = json.loads((TEMPLATES_DIR / f"{BASE_ID}.json").read_text())
    templates: dict[str, dict] = {}

    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        if path.stem == BASE_ID:
            continue
        config = json.loads(path.read_text())
        templates[config["id"]] = deep_merge(base, config)

    return templates


def template_ids() -> list[str]:
    return list(load_templates().keys())


def get_template(template_id: str) -> dict:
    templates = load_templates()
    if template_id not in templates:
        raise KeyError(f"unknown template '{template_id}'. Available: {', '.join(templates)}")
    return templates[template_id]


def block_style(template: dict, block) -> dict:
    """The style dict for one block, by type (and level, for headings)."""
    blocks = template["blocks"]
    if block.type == "heading":
        return blocks.get(f"heading_{block.level}", blocks["heading_1"])
    return blocks[block.type]
