"""Type definitions for litestar-storages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

__all__ = (
    "ProgressCallback",
    "ProgressInfo",
    "StoredFile",
    "UploadResult",
    "MultipartUpload",
)


@dataclass(frozen=True)
class StoredFile:
    """Metadata for a stored file.

    Attributes:
        key: Storage path/key for the file
        size: File size in bytes
        content_type: MIME type of the content
        etag: Entity tag for the file (useful for caching/versioning)
        last_modified: Timestamp of last modification
        metadata: Additional metadata stored with the file
    """

    key: str
    size: int
    content_type: str | None = None
    etag: str | None = None
    last_modified: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class UploadResult:
    """Result of an upload operation.

    Attributes:
        file: Metadata about the uploaded file
        url: Optional URL for accessing the file
    """

    file: StoredFile
    url: str | None = None


@dataclass
class ProgressInfo:
    """Information about transfer progress.

    Attributes:
        bytes_transferred: Number of bytes transferred so far
        total_bytes: Total number of bytes to transfer (None if unknown)
        percentage: Percentage complete (0-100, None if total unknown)
        operation: Type of operation ("upload" or "download")
        key: Storage key being transferred
    """

    bytes_transferred: int
    total_bytes: int | None
    operation: str
    key: str

    @property
    def percentage(self) -> float | None:
        """Calculate percentage complete."""
        if self.total_bytes is None or self.total_bytes == 0:
            return None
        return (self.bytes_transferred / self.total_bytes) * 100


class ProgressCallback(Protocol):
    """Protocol for progress callback functions.

    Progress callbacks are called periodically during upload/download
    operations to report progress. They can be sync or async.

    Example::

        def my_progress(info: ProgressInfo) -> None:
            if info.percentage:
                print(f"{info.operation}: {info.percentage:.1f}%")
            else:
                print(f"{info.operation}: {info.bytes_transferred} bytes")
    """

    def __call__(self, info: ProgressInfo) -> None:
        """Called with progress information.

        Args:
            info: Current progress information
        """
        ...


@dataclass
class MultipartUpload:
    """State for a multipart upload operation.

    Used to track and manage multipart uploads for large files.
    This allows uploads to be paused, resumed, or completed in parts.

    Attributes:
        upload_id: Unique identifier for the multipart upload
        key: Storage key for the file being uploaded
        parts: List of completed part information (part_number, etag)
        part_size: Size of each part in bytes
        total_parts: Expected total number of parts (None if unknown)
    """

    upload_id: str
    key: str
    parts: list[tuple[int, str]] = field(default_factory=list)
    part_size: int = 5 * 1024 * 1024  # 5MB default
    total_parts: int | None = None

    def add_part(self, part_number: int, etag: str) -> None:
        """Record a completed part.

        Args:
            part_number: The part number (1-indexed)
            etag: The ETag returned by the storage service
        """
        self.parts.append((part_number, etag))

    @property
    def completed_parts(self) -> int:
        """Number of parts completed."""
        return len(self.parts)
