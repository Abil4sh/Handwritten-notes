"""Content addressing.

A render is fully determined by (note content, render spec). Hashing both
gives a cache key: an identical request finds the existing PDF instead of
re-rendering. This only works because jitter is deterministically seeded --
see app/render/handwriting.py.
"""

import hashlib
import json


def stable_json(value) -> str:
    """Canonical JSON: sorted keys, no incidental whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_of(value) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def content_hash(note_content: dict) -> str:
    return sha256_of(note_content)


def spec_hash(note_content_hash: str, spec: dict) -> str:
    return sha256_of({"content": note_content_hash, "spec": spec})
