"""Dependency injection utilities for storage."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from litestar_storages.base import Storage  # noqa: TC001 - needed at runtime for DI

__all__ = ["StorageDependency", "provide_storage"]


# Type alias for storage dependency injection
StorageDependency: TypeAlias = "Storage"
"""Type alias for storage dependency injection in route handlers.

This can be used as a type hint when injecting storage into route handlers.

Example:
    ```python
    from litestar import get
    from litestar_storages.contrib.dependencies import StorageDependency

    @get("/files/{key:str}")
    async def get_file(key: str, storage: StorageDependency) -> bytes:
        return await storage.get_bytes(key)
    ```
"""


def provide_storage(storage: Storage) -> Callable[[], Storage]:
    """Create a dependency provider function for a storage instance.

    This function can be used to create custom dependency providers
    for storage instances when not using the StoragePlugin.

    Args:
        storage: The storage instance to provide

    Returns:
        A callable that returns the storage instance for dependency injection

    Example:
        Manual dependency registration:

        ```python
        from litestar import Litestar
        from litestar.di import Provide
        from litestar_storages import S3Storage, S3Config
        from litestar_storages.contrib.dependencies import provide_storage

        storage = S3Storage(config=S3Config(bucket="uploads"))

        app = Litestar(
            route_handlers=[...],
            dependencies={
                "storage": Provide(provide_storage(storage)),
            },
        )
        ```

        With multiple storages:

        ```python
        from litestar import Litestar
        from litestar.di import Provide
        from litestar_storages import S3Storage, AzureStorage
        from litestar_storages.contrib.dependencies import provide_storage

        s3 = S3Storage(config=S3Config(bucket="main"))
        azure = AzureStorage(config=AzureConfig(container="archive"))

        app = Litestar(
            route_handlers=[...],
            dependencies={
                "storage": Provide(provide_storage(s3)),
                "archive_storage": Provide(provide_storage(azure)),
            },
        )
        ```
    """

    def _provider() -> Storage:
        return storage

    return _provider
