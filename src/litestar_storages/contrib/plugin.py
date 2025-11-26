"""Litestar plugin for storage integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from litestar.di import Provide
from litestar.plugins import InitPluginProtocol

from litestar_storages.base import Storage  # noqa: TC001 - needed at runtime for DI

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.config.app import AppConfig

__all__ = ["StoragePlugin"]


class StoragePlugin(InitPluginProtocol):
    """Litestar plugin for storage integration.

    This plugin provides dependency injection support for storage instances,
    enabling seamless integration with Litestar applications. It supports
    both single and multiple named storage configurations.

    Provides:
        - Dependency injection of storage instances
        - Lifespan management (connection cleanup)
        - Multiple named storage support

    Example:
        Single storage configuration:

        ```python
        from litestar import Litestar
        from litestar_storages import S3Storage, S3Config, StoragePlugin

        storage = S3Storage(config=S3Config(bucket="uploads"))

        app = Litestar(
            route_handlers=[...],
            plugins=[StoragePlugin(storage)],
        )
        ```

        Multiple named storages:

        ```python
        from litestar import Litestar
        from litestar_storages import S3Storage, AzureStorage, StoragePlugin

        app = Litestar(
            route_handlers=[...],
            plugins=[
                StoragePlugin(
                    default=S3Storage(config=S3Config(bucket="main-uploads")),
                    images=S3Storage(config=S3Config(bucket="images")),
                    documents=AzureStorage(config=AzureConfig(container="docs")),
                )
            ],
        )
        ```

        Using in route handlers:

        ```python
        from litestar import post
        from litestar.datastructures import UploadFile
        from litestar_storages import Storage, StoredFile


        @post("/upload")
        async def upload(
            data: UploadFile,
            storage: Storage,  # Injected default storage
        ) -> StoredFile:
            return await storage.put(
                key=f"uploads/{data.filename}",
                data=data.file,
                content_type=data.content_type,
            )


        @post("/upload-image")
        async def upload_image(
            data: UploadFile,
            images_storage: Storage,  # Injected named storage
        ) -> StoredFile:
            return await images_storage.put(
                key=f"images/{data.filename}",
                data=data.file,
                content_type=data.content_type,
            )
        ```
    """

    __slots__ = ("storages",)

    def __init__(
        self,
        default: Storage | None = None,
        **named_storages: Storage,
    ) -> None:
        """Initialize the StoragePlugin.

        Args:
            default: Optional default storage instance. If provided, it will be
                registered as the "storage" dependency.
            **named_storages: Named storage instances. Each will be registered
                as "{name}_storage" dependency.

        Example:
            ```python
            plugin = StoragePlugin(
                default=S3Storage(...),
                images=S3Storage(...),
                documents=AzureStorage(...),
            )
            ```

            This registers three dependencies:
            - `storage` (from default)
            - `images_storage`
            - `documents_storage`
        """
        self.storages: dict[str, Storage] = dict(named_storages)
        if default is not None:
            self.storages["default"] = default

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Register storage instances as dependencies on application initialization.

        This method is called by Litestar during application startup. It registers
        each storage instance as a dependency that can be injected into route handlers.

        Args:
            app_config: The Litestar application configuration

        Returns:
            Modified application configuration with storage dependencies registered

        Note:
            - The "default" storage is registered as "storage"
            - Named storages are registered as "{name}_storage"
            - Existing dependencies are preserved
        """
        dependencies = dict(app_config.dependencies or {})

        for name, storage in self.storages.items():
            dep_name = "storage" if name == "default" else f"{name}_storage"
            # Use a factory function to avoid late binding issues
            # sync_to_thread=False since we're just returning a reference, no blocking I/O
            dependencies[dep_name] = Provide(
                self._make_storage_provider(storage),
                sync_to_thread=False,
            )

        app_config.dependencies = dependencies

        # Register shutdown handler for storage cleanup
        on_shutdown = list(app_config.on_shutdown or [])
        on_shutdown.append(self._shutdown_storages)
        app_config.on_shutdown = on_shutdown

        return app_config

    async def _shutdown_storages(self, _app: Litestar) -> None:
        """Shutdown handler that closes all storage backends.

        This method is called by Litestar during application shutdown.
        It iterates over all registered storages and calls their close()
        method to release resources.

        Args:
            _app: The Litestar application instance (unused but required by signature)

        Note:
            Errors during close() are caught and logged to ensure all storages
            get a chance to clean up, even if one fails.
        """
        import logging

        logger = logging.getLogger(__name__)

        for name, storage in self.storages.items():
            if hasattr(storage, "close"):
                try:
                    await storage.close()
                except Exception as e:
                    logger.warning(
                        "Error closing storage '%s': %s",
                        name,
                        e,
                    )

    @staticmethod
    def _make_storage_provider(storage: Storage) -> Callable[[], Storage]:
        """Create a provider function for dependency injection.

        This factory method ensures proper closure binding for each storage instance.

        Args:
            storage: The storage instance to provide

        Returns:
            A callable that returns the storage instance
        """

        def provider() -> Storage:
            return storage

        return provider
