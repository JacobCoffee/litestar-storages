"""Litestar integration components."""

from __future__ import annotations

from litestar_storages.contrib.dependencies import StorageDependency, provide_storage
from litestar_storages.contrib.dto import StoredFileDTO, StoredFileReadDTO
from litestar_storages.contrib.plugin import StoragePlugin

__all__ = [
    "StorageDependency",
    # Plugin
    "StoragePlugin",
    # DTOs
    "StoredFileDTO",
    "StoredFileReadDTO",
    # Dependencies
    "provide_storage",
]
