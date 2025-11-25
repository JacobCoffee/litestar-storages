"""Type definitions for litestar-storages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

__all__ = ("StoredFile", "UploadResult")


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
