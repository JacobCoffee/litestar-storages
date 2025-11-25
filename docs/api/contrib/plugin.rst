Storage Plugin
==============

.. module:: litestar_storages.contrib.plugin

The ``StoragePlugin`` provides seamless integration with Litestar applications,
handling dependency injection and lifecycle management for storage instances.

Plugin Class
------------

.. autoclass:: StoragePlugin
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Features
--------

Dependency Injection
^^^^^^^^^^^^^^^^^^^^

The plugin registers storage instances as dependencies that can be injected
into route handlers:

.. code-block:: python

   from litestar import Litestar, get, post
   from litestar_storages import Storage, StoredFile
   from litestar_storages.contrib import StoragePlugin

   @post("/upload")
   async def upload(
       data: bytes,
       storage: Storage,  # Injected
   ) -> StoredFile:
       return await storage.put("file.txt", data)

   @get("/files")
   async def list_files(storage: Storage) -> list[StoredFile]:
       return [file async for file in storage.list()]

Named Storages
^^^^^^^^^^^^^^

Register multiple storages with different names:

.. code-block:: python

   plugin = StoragePlugin(
       default=s3_storage,      # Injected as "storage"
       uploads=upload_storage,  # Injected as "uploads_storage"
       cache=cache_storage,     # Injected as "cache_storage"
   )

   @post("/upload")
   async def upload(
       storage: Storage,         # Default storage
       uploads_storage: Storage, # Named storage
   ) -> StoredFile:
       ...

Automatic Cleanup
^^^^^^^^^^^^^^^^^

The plugin registers a shutdown handler that closes all storage instances:

.. code-block:: python

   # On application shutdown, this is called automatically:
   for storage in storages.values():
       await storage.close()

This ensures proper cleanup of:

* HTTP sessions (aioboto3, gcloud-aio-storage, azure-storage-blob)
* Connection pools
* File handles

Usage Examples
--------------

Single Storage
^^^^^^^^^^^^^^

.. code-block:: python

   from litestar import Litestar
   from litestar_storages import S3Storage, S3Config
   from litestar_storages.contrib import StoragePlugin

   storage = S3Storage(
       config=S3Config(
           bucket="my-uploads",
           region="us-east-1",
       )
   )

   app = Litestar(
       route_handlers=[...],
       plugins=[StoragePlugin(default=storage)],
   )

Multiple Storages by Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   import os
   from litestar import Litestar
   from litestar_storages import (
       MemoryStorage,
       S3Storage, S3Config,
       FileSystemStorage, FileSystemConfig,
   )
   from litestar_storages.contrib import StoragePlugin

   def get_storage():
       env = os.getenv("ENV", "development")

       if env == "production":
           return S3Storage(config=S3Config(
               bucket=os.environ["S3_BUCKET"],
               region=os.environ["AWS_REGION"],
           ))
       elif env == "staging":
           return FileSystemStorage(config=FileSystemConfig(
               path=Path("/var/uploads"),
           ))
       else:
           return MemoryStorage()

   app = Litestar(
       route_handlers=[...],
       plugins=[StoragePlugin(default=get_storage())],
   )

With DTOs
^^^^^^^^^

.. code-block:: python

   from litestar import post
   from litestar.datastructures import UploadFile
   from litestar_storages import Storage, StoredFile
   from litestar_storages.contrib import StoragePlugin, StoredFileDTO

   @post("/upload", return_dto=StoredFileDTO)
   async def upload(
       data: UploadFile,
       storage: Storage,
   ) -> StoredFile:
       content = await data.read()
       return await storage.put(
           key=f"uploads/{data.filename}",
           data=content,
           content_type=data.content_type,
       )

Complete Application
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from litestar import Litestar, get, post, delete
   from litestar.datastructures import UploadFile
   from litestar.response import Stream
   from litestar_storages import Storage, StoredFile
   from litestar_storages.contrib import StoragePlugin, StoredFileDTO
   from litestar_storages.exceptions import StorageFileNotFoundError

   @post("/files", return_dto=StoredFileDTO)
   async def upload_file(
       data: UploadFile,
       storage: Storage,
   ) -> StoredFile:
       content = await data.read()
       return await storage.put(
           key=f"files/{data.filename}",
           data=content,
           content_type=data.content_type,
       )

   @get("/files/{key:path}")
   async def download_file(
       key: str,
       storage: Storage,
   ) -> Stream:
       async def stream():
           async for chunk in storage.get(f"files/{key}"):
               yield chunk
       return Stream(stream())

   @get("/files/{key:path}/info", return_dto=StoredFileDTO)
   async def get_file_info(
       key: str,
       storage: Storage,
   ) -> StoredFile:
       return await storage.info(f"files/{key}")

   @delete("/files/{key:path}")
   async def delete_file(
       key: str,
       storage: Storage,
   ) -> None:
       await storage.delete(f"files/{key}")

   app = Litestar(
       route_handlers=[upload_file, download_file, get_file_info, delete_file],
       plugins=[StoragePlugin(default=S3Storage(config=S3Config(bucket="files")))],
   )
