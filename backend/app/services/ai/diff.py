"""Minimal unified-diff parsing: just enough to attach new-file line numbers to patch lines.

GitHub's ``patch`` field contains only hunks (no ``diff --git``/``---``/``+++`` headers).
Lines after a hunk header we cannot parse get no line number rather than a guessed one.
"""

import re
from dataclasses import dataclass
from typing import Literal

_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

LineKind = Literal["hunk", "added", "removed", "context", "meta"]


@dataclass(frozen=True)
class DiffLine:
    kind: LineKind
    text: str
    new_line: int | None
    """Line number in the new file version; set for added and context lines only."""


def parse_patch(patch: str) -> list[DiffLine]:
    lines: list[DiffLine] = []
    next_new: int | None = None
    for raw in patch.splitlines():
        if raw.startswith("@@"):
            match = _HUNK_HEADER.match(raw)
            next_new = int(match.group(1)) if match else None
            lines.append(DiffLine("hunk", raw, None))
        elif raw.startswith("+"):
            lines.append(DiffLine("added", raw[1:], next_new))
            next_new = next_new + 1 if next_new is not None else None
        elif raw.startswith("-"):
            lines.append(DiffLine("removed", raw[1:], None))
        elif raw.startswith("\\"):  # "\ No newline at end of file"
            lines.append(DiffLine("meta", raw, None))
        else:
            text = raw[1:] if raw.startswith(" ") else raw
            lines.append(DiffLine("context", text, next_new))
            next_new = next_new + 1 if next_new is not None else None
    return lines
