from __future__ import annotations

import re


def clean_text(text: str) -> str:
    """Normalize whitespace and remove control characters."""
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def infer_resource_type(file_name: str) -> str:
    """Infer document type from file name prefix."""
    stem = file_name.rsplit(".", 1)[0].lower()
    for prefix in ("lecture", "faq", "assignment", "guide", "lab"):
        if stem.startswith(prefix):
            return prefix
    return "document"


def infer_topic(file_name: str) -> str:
    """Use file stem as a coarse topic label."""
    return file_name.rsplit(".", 1)[0].lower()
