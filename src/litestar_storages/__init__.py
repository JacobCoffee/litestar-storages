"""litestar-storages - Async file storage abstraction for Litestar."""

from __future__ import annotations

from litestar_storages.__metadata__ import __project__, __version__
from litestar_storages.backends import (
    FileSystemConfig,
    FileSystemStorage,
    MemoryConfig,
    MemoryStorage,
    S3Config,
    S3Storage,
)
from litestar_storages.base import BaseStorage, Storage
from litestar_storages.exceptions import (
    ConfigurationError,
    StorageConnectionError,
    StorageError,
    StorageFileExistsError,
    StorageFileNotFoundError,
    StoragePermissionError,
)
from litestar_storages.types import StoredFile, UploadResult

__all__ = (
    # Metadata
    "__project__",
    "__version__",
    # Protocol and base class
    "BaseStorage",
    "Storage",
    # Backends
    "FileSystemConfig",
    "FileSystemStorage",
    "MemoryConfig",
    "MemoryStorage",
    "S3Config",
    "S3Storage",
    # Exceptions
    "ConfigurationError",
    "StorageConnectionError",
    "StorageError",
    "StorageFileExistsError",
    "StorageFileNotFoundError",
    "StoragePermissionError",
    # Types
    "StoredFile",
    "UploadResult",
)
