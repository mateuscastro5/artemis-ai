
from __future__ import annotations

import re

NOISE_PATTERNS = [
    r"^\s*$",
    r"^\s*//.*$",
    r"^\s*#(?!!).*$",
    r"^\s*/\*.*\*/\s*$",
    r'^\s*\*\s',
    r'^\s*\*/$',
    r"^\s*import\s",
    r"^\s*from\s+\S+\s+import\s",
    r"^\s*require\s*\(",
    r"^\s*export\s*\{",
    r'^\s*"use (strict|client|server)"',
    r"^\s*\}\s*$",
    r"^\s*\{\s*$",
    r"^\s*\)\s*$",
    r"^\s*\(\s*$",
]

NOISE_RE = re.compile("|".join(NOISE_PATTERNS))


def is_noise_line(line: str) -> bool:
    return bool(NOISE_RE.match(line))


def clean_lines(lines: list[str], aggressive: bool = False) -> list[str]:

    cleaned = []
    for line in lines:
        if aggressive and is_noise_line(line):
            continue
        if not line.strip():
            continue
        cleaned.append(line)
    return cleaned


def truncate_diff(diff_text: str, max_lines: int) -> str:
    lines = diff_text.splitlines()
    if len(lines) <= max_lines:
        return diff_text
    truncated = lines[:max_lines]
    truncated.append(f"\n... [truncated: {len(lines) - max_lines} more lines]")
    return "\n".join(truncated)


def extract_meaningful_content(added_lines: list[str], removed_lines: list[str]) -> str:

    parts = []
    if added_lines:
        cleaned_added = clean_lines(added_lines, aggressive=True)
        if cleaned_added:
            parts.append("// Added:\n" + "\n".join(cleaned_added))
    if removed_lines:
        cleaned_removed = clean_lines(removed_lines, aggressive=True)
        if cleaned_removed:
            parts.append("// Removed:\n" + "\n".join(cleaned_removed))
    return "\n\n".join(parts)
