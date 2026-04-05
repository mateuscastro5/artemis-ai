from __future__ import annotations

import re
from dataclasses import dataclass, field

SKIP_PATTERNS = [
    r"package-lock\.json$",
    r"yarn\.lock$",
    r"pnpm-lock\.yaml$",
    r"Cargo\.lock$",
    r"poetry\.lock$",
    r"Gemfile\.lock$",
    r"\.min\.(js|css)$",
    r"\.map$",
    r"\.svg$",
    r"\.png$",
    r"\.jpg$",
    r"\.jpeg$",
    r"\.gif$",
    r"\.ico$",
    r"\.woff2?$",
    r"\.ttf$",
    r"\.eot$",
    r"\.pdf$",
    r"dist/",
    r"build/",
    r"node_modules/",
    r"__pycache__/",
    r"\.pyc$",
    r"\.generated\.",
    r"\.auto\.",
]

SKIP_RE = re.compile("|".join(SKIP_PATTERNS), re.IGNORECASE)

LANGUAGE_MAP: dict[str, str] = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".swift": "Swift",
    ".dart": "Dart",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".sh": "Shell",
    ".bash": "Shell",
    ".dockerfile": "Docker",
}


@dataclass
class FileHunk:
    filename: str
    language: str
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    context_lines: list[str] = field(default_factory=list)


def detect_language(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith("dockerfile") or lower.startswith("dockerfile"):
        return "Docker"
    for ext, lang in LANGUAGE_MAP.items():
        if lower.endswith(ext):
            return lang
    return "Other"


def should_skip_file(filename: str) -> bool:
    return bool(SKIP_RE.search(filename))


def parse_unified_diff(diff_text: str) -> list[FileHunk]:
    """
        diff --git a/path b/path
        --- a/path
        +++ b/path
        @@ ... @@
        +added
        -removed
         context
    """
    hunks: list[FileHunk] = []
    current_hunk: FileHunk | None = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            match = re.search(r"b/(.+)$", line)
            if match:
                filename = match.group(1)
                if should_skip_file(filename):
                    current_hunk = None
                    continue
                current_hunk = FileHunk(
                    filename=filename,
                    language=detect_language(filename),
                )
                hunks.append(current_hunk)
            continue

        if current_hunk is None:
            continue

        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("index ") or line.startswith("Binary files"):
            continue

        if line.startswith("+"):
            current_hunk.added_lines.append(line[1:])
        elif line.startswith("-"):
            current_hunk.removed_lines.append(line[1:])
        elif line.startswith(" "):
            current_hunk.context_lines.append(line[1:])

    return hunks
