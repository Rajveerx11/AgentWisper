from __future__ import annotations

import re
from dataclasses import dataclass

_HESITATION = re.compile(
    r"(?<![\w'-])(?:um+|uh+|erm+|hmm+)(?![\w'-])(?:\s*,\s*|\s+)?",
    re.IGNORECASE,
)
_BOUNDARY_FILLER = re.compile(
    r"(^|[.!?;:,])\s*(?:you know|I mean)\s*,\s*",
    re.IGNORECASE,
)
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:!?])")
_DUPLICATE_SPACES = re.compile(r"[ \t]{2,}")
_EMPTY_PUNCTUATION = re.compile(r"(^|[.!?;:])\s*,\s*")


@dataclass(frozen=True, slots=True)
class CleanupResult:
    text: str
    removed_count: int


def clean_spoken_text(text: str) -> CleanupResult:
    """Remove only high-confidence speech fillers from a transcript."""
    cleaned = text.strip()
    removed = 0

    cleaned, count = _HESITATION.subn("", cleaned)
    removed += count
    cleaned, count = _BOUNDARY_FILLER.subn(
        lambda match: f"{match.group(1)} " if match.group(1) else "",
        cleaned,
    )
    removed += count

    cleaned = _EMPTY_PUNCTUATION.sub(r"\1 ", cleaned)
    cleaned = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", cleaned)
    cleaned = _DUPLICATE_SPACES.sub(" ", cleaned).strip(" ,")
    cleaned = re.sub(
        r"(^|[.!?]\s+)([a-z])",
        lambda match: match.group(1) + match.group(2).upper(),
        cleaned,
    )
    return CleanupResult(cleaned, removed)
