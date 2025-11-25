Dependencies
============

.. module:: litestar_storages.contrib.dependencies

Utilities for manual dependency injection when not using the
:class:`~litestar_storages.contrib.plugin.StoragePlugin`.

Type Alias
----------

.. data:: StorageDependency
   :type: TypeAlias

   Type alias for storage dependency injection in route handlers.

   .. code-block:: python

      from litestar import get
      from litestar_storages.contrib.dependencies import StorageDependency

      @get("/files/{key:str}")
      async def get_file(key: str, storage: StorageDependency) -> bytes:
          return await storage.get_bytes(key)

Provider Function
-----------------

.. autofunction:: provide_storage

Usage Examples
--------------

Manual Dependency Registration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you need more control over dependency registration than the plugin provides:

.. code-block:: python

   from litestar import Litestar
   from litestar.di import Provide
   from litestar_storages import S3Storage, S3Config
   from litestar_storages.contrib.dependencies import provide_storage

   storage = S3Storage(config=S3Config(bucket="uploads"))

   app = Litestar(
       route_handlers=[...],
       dependencies={
           "storage": Provide(provide_storage(storage), sync_to_thread=False),
       },
   )

Multiple Storages
^^^^^^^^^^^^^^^^^

.. code-block:: python

   from litestar import Litestar
   from litestar.di import Provide
   from litestar_storages import S3Storage, AzureStorage
   from litestar_storages.contrib.dependencies import provide_storage

   s3 = S3Storage(config=S3Config(bucket="main"))
   azure = AzureStorage(config=AzureConfig(container="archive"))

   app = Litestar(
       route_handlers=[...],
       dependencies={
           "storage": Provide(provide_storage(s3), sync_to_thread=False),
           "archive_storage": Provide(provide_storage(azure), sync_to_thread=False),
       },
   )

With Manual Cleanup
^^^^^^^^^^^^^^^^^^^

When not using the plugin, you must handle cleanup manually:

.. code-block:: python

   from litestar import Litestar
   from litestar.di import Provide
   from litestar_storages import S3Storage, S3Config
   from litestar_storages.contrib.dependencies import provide_storage

   storage = S3Storage(config=S3Config(bucket="uploads"))

   async def cleanup(app: Litestar) -> None:
       await storage.close()

   app = Litestar(
       route_handlers=[...],
       dependencies={
           "storage": Provide(provide_storage(storage), sync_to_thread=False),
       },
       on_shutdown=[cleanup],
   )

Router-Level Dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^

Register storage for specific routers:

.. code-block:: python

   from litestar import Router, get
   from litestar.di import Provide
   from litestar_storages import S3Storage, Storage
   from litestar_storages.contrib.dependencies import provide_storage

   @get("/")
   async def list_uploads(storage: Storage) -> list[str]:
       return [f.key async for f in storage.list()]

   uploads_router = Router(
       path="/uploads",
       route_handlers=[list_uploads],
       dependencies={
           "storage": Provide(
               provide_storage(S3Storage(config=S3Config(bucket="uploads"))),
               sync_to_thread=False,
           ),
       },
   )

When to Use Manual Dependencies
-------------------------------

Use manual dependency registration instead of the plugin when you need:

1. **Router-specific storages** - Different storages for different routers
2. **Conditional registration** - Logic determining which storage to use
3. **Testing overrides** - Easy swapping of storage in tests
4. **Custom cleanup logic** - Additional cleanup beyond ``close()``

For most applications, :class:`~litestar_storages.contrib.plugin.StoragePlugin`
is simpler and handles lifecycle management automatically.
