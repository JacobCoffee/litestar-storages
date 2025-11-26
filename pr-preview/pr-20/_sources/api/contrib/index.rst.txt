Litestar Integration
====================

.. module:: litestar_storages.contrib

This module provides integration components for using litestar-storages with
`Litestar <https://litestar.dev/>`_ applications, including:

* **StoragePlugin** - Plugin for automatic dependency injection
* **Dependencies** - Manual DI utilities
* **DTOs** - Data transfer objects for API responses

.. toctree::
   :maxdepth: 2

   plugin
   dependencies
   dto

Quick Start
-----------

The simplest way to integrate storage into a Litestar application:

.. code-block:: python

   from litestar import Litestar, post
   from litestar.datastructures import UploadFile
   from litestar_storages import S3Storage, S3Config, Storage, StoredFile
   from litestar_storages.contrib import StoragePlugin

   # Configure storage
   storage = S3Storage(
       config=S3Config(bucket="uploads", region="us-east-1")
   )

   # Route handler with injected storage
   @post("/upload")
   async def upload_file(
       data: UploadFile,
       storage: Storage,  # Injected by plugin
   ) -> StoredFile:
       content = await data.read()
       return await storage.put(
           key=f"uploads/{data.filename}",
           data=content,
           content_type=data.content_type,
       )

   # Create application with plugin
   app = Litestar(
       route_handlers=[upload_file],
       plugins=[StoragePlugin(default=storage)],
   )

Multiple Storages
-----------------

Use named storages for different purposes:

.. code-block:: python

   from litestar import Litestar, post
   from litestar_storages import S3Storage, AzureStorage, Storage
   from litestar_storages.contrib import StoragePlugin

   app = Litestar(
       route_handlers=[...],
       plugins=[
           StoragePlugin(
               default=S3Storage(config=S3Config(bucket="main")),
               images=S3Storage(config=S3Config(bucket="images")),
               documents=AzureStorage(config=AzureConfig(container="docs")),
           )
       ],
   )


   @post("/upload-image")
   async def upload_image(
       data: UploadFile,
       images_storage: Storage,  # Named storage: "{name}_storage"
   ) -> StoredFile:
       ...


   @post("/upload-doc")
   async def upload_doc(
       data: UploadFile,
       documents_storage: Storage,  # Named storage
   ) -> StoredFile:
       ...

Lifespan Management
-------------------

The plugin automatically manages storage lifecycle:

1. **Startup**: Storages are ready when the application starts
2. **Shutdown**: All storages are closed via ``close()`` method

This ensures proper cleanup of HTTP sessions, connection pools, and other resources.
