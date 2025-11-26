"""Litestar integration components.

This module provides optional Litestar framework integration. Litestar must be
installed separately to use these components:

    pip install litestar-storages[litestar]

If Litestar is not installed, importing from this module will raise an
ImportError with installation instructions.
"""

from __future__ import annotations

# Check if Litestar is available
try:
    import litestar  # noqa: F401

    LITESTAR_AVAILABLE = True
except ImportError:
    LITESTAR_AVAILABLE = False


def _raise_litestar_not_installed() -> None:
    """Raise ImportError with installation instructions."""
    msg = (
        "Litestar is not installed. To use Litestar integration features, "
        "install litestar-storages with the 'litestar' extra:\n\n"
        "    pip install litestar-storages[litestar]\n\n"
        "Or install Litestar directly:\n\n"
        "    pip install litestar"
    )
    raise ImportError(msg)


def __getattr__(name: str) -> object:
    """Lazy import with helpful error messages when Litestar is not installed."""
    if name == "LITESTAR_AVAILABLE":
        return LITESTAR_AVAILABLE

    if not LITESTAR_AVAILABLE:
        _raise_litestar_not_installed()

    # Litestar is available, do the actual import
    if name == "StoragePlugin":
        from litestar_storages.contrib.plugin import StoragePlugin

        return StoragePlugin
    if name == "StoredFileDTO":
        from litestar_storages.contrib.dto import StoredFileDTO

        return StoredFileDTO
    if name == "StoredFileReadDTO":
        from litestar_storages.contrib.dto import StoredFileReadDTO

        return StoredFileReadDTO
    if name == "StorageDependency":
        from litestar_storages.contrib.dependencies import StorageDependency

        return StorageDependency
    if name == "provide_storage":
        from litestar_storages.contrib.dependencies import provide_storage

        return provide_storage

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


__all__ = [
    "LITESTAR_AVAILABLE",
    "StorageDependency",
    # Plugin
    "StoragePlugin",
    # DTOs
    "StoredFileDTO",
    "StoredFileReadDTO",
    # Dependencies
    "provide_storage",
]
