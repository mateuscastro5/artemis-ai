from __future__ import annotations

from ..models.schemas import DiffMetrics, PreprocessedDiff
from ..utils.diff_parser import parse_unified_diff
from ..utils.text_cleaner import extract_meaningful_content, truncate_diff


class Preprocessor:

    def clean_diff(self, raw_diff: str, max_lines: int = 3000) -> PreprocessedDiff:
        hunks = parse_unified_diff(raw_diff)

        if not hunks:
            return PreprocessedDiff(
                cleaned_diff="",
                metrics=DiffMetrics(
                    files_changed=0,
                    lines_added=0,
                    lines_removed=0,
                    languages_detected=[],
                ),
                file_summaries=[],
            )

        cleaned_parts: list[str] = []
        file_summaries: list[str] = []
        total_added = 0
        total_removed = 0
        languages: set[str] = set()

        for hunk in hunks:
            total_added += len(hunk.added_lines)
            total_removed += len(hunk.removed_lines)
            if hunk.language != "Other":
                languages.add(hunk.language)

            content = extract_meaningful_content(hunk.added_lines, hunk.removed_lines)
            if content.strip():
                header = f"// File: {hunk.filename} ({hunk.language})"
                cleaned_parts.append(f"{header}\n{content}")
                file_summaries.append(
                    f"{hunk.filename}: +{len(hunk.added_lines)}/-{len(hunk.removed_lines)} ({hunk.language})"
                )

        cleaned_diff = "\n\n---\n\n".join(cleaned_parts)
        cleaned_diff = truncate_diff(cleaned_diff, max_lines)

        return PreprocessedDiff(
            cleaned_diff=cleaned_diff,
            metrics=DiffMetrics(
                files_changed=len(hunks),
                lines_added=total_added,
                lines_removed=total_removed,
                languages_detected=sorted(languages),
            ),
            file_summaries=file_summaries,
        )
