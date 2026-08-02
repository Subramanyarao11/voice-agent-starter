"""Identifier minting.

IDs are always generated here and never by a language model, because they end
up in database keys and URLs where a hallucinated or colliding value would be
difficult to trace back.
"""

import re
import uuid

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def new_id(prefix: str = "") -> str:
    raw = uuid.uuid4().hex
    return f"{prefix}_{raw}" if prefix else raw


def session_id() -> str:
    return new_id("ses")


def turn_id() -> str:
    return new_id("trn")


def ticket_id() -> str:
    return new_id("esc")


def slugify(value: str, max_length: int = 80) -> str:
    """Stable, filesystem- and URL-safe slug used for benefit IDs."""
    slug = _SLUG_STRIP.sub("-", value.strip().lower()).strip("-")
    return slug[:max_length].rstrip("-") or new_id()
