"""Model-ready review input produced by the input builder and rendered by the prompt layer."""

from dataclasses import dataclass

from app.schemas.pull_request import PullRequestMetadata
from app.schemas.review import SkippedFile
from app.services.ai.diff import DiffLine


@dataclass(frozen=True)
class PreparedFile:
    filename: str
    status: str
    additions: int
    deletions: int
    previous_filename: str | None
    lines: tuple[DiffLine, ...]
    omitted_lines: int
    """Patch lines dropped to fit the per-file budget (0 when the whole diff is included)."""

    @property
    def truncated(self) -> bool:
        return self.omitted_lines > 0

    @property
    def new_lines(self) -> frozenset[int]:
        """New-file line numbers visible in the included diff; the only lines findings may cite."""
        return frozenset(line.new_line for line in self.lines if line.new_line is not None)


@dataclass(frozen=True)
class ManifestEntry:
    filename: str
    status: str
    additions: int
    deletions: int
    note: str


@dataclass(frozen=True)
class ReviewChunk:
    files: tuple[PreparedFile, ...]
    estimated_tokens: int


@dataclass(frozen=True)
class ReviewInput:
    metadata: PullRequestMetadata
    context: str
    """Rendered PR context shared by every chunk (metadata, description, file manifest)."""
    chunks: tuple[ReviewChunk, ...]
    skipped_files: tuple[SkippedFile, ...]
    limitations: tuple[str, ...]
    files_considered: int

    @property
    def reviewed_files(self) -> tuple[PreparedFile, ...]:
        return tuple(file for chunk in self.chunks for file in chunk.files)
