"""Storage backends for litestar-storages."""

from __future__ import annotations

from litestar_storages.backends.azure import AzureConfig, AzureStorage
from litestar_storages.backends.filesystem import (
    FileSystemConfig,
    FileSystemStorage,
)
from litestar_storages.backends.gcs import GCSConfig, GCSStorage
from litestar_storages.backends.memory import MemoryConfig, MemoryStorage
from litestar_storages.backends.s3 import S3Config, S3Storage

__all__ = (
    "AzureConfig",
    "AzureStorage",
    "FileSystemConfig",
    "FileSystemStorage",
    "GCSConfig",
    "GCSStorage",
    "MemoryConfig",
    "MemoryStorage",
    "S3Config",
    "S3Storage",
)
