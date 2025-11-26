Storage Backends
================

.. module:: litestar_storages.backends

This section documents all available storage backend implementations. Each backend
implements the :class:`~litestar_storages.base.Storage` protocol and provides a
corresponding configuration dataclass.

Available Backends
------------------

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Backend
     - Use Case
     - Dependencies
   * - :class:`~litestar_storages.backends.memory.MemoryStorage`
     - Testing, development
     - None (built-in)
   * - :class:`~litestar_storages.backends.filesystem.FileSystemStorage`
     - Local file storage
     - ``aiofiles``
   * - :class:`~litestar_storages.backends.s3.S3Storage`
     - AWS S3, R2, Spaces, MinIO
     - ``aioboto3``
   * - :class:`~litestar_storages.backends.gcs.GCSStorage`
     - Google Cloud Storage
     - ``gcloud-aio-storage``
   * - :class:`~litestar_storages.backends.azure.AzureStorage`
     - Azure Blob Storage
     - ``azure-storage-blob``

Backend Modules
---------------

.. toctree::
   :maxdepth: 2

   memory
   filesystem
   s3
   gcs
   azure

Choosing a Backend
------------------

**For Testing and Development**

Use :class:`~litestar_storages.backends.memory.MemoryStorage` for unit tests
and local development. Data is stored in memory and lost on restart.

.. code-block:: python

   from litestar_storages import MemoryStorage

   storage = MemoryStorage()

**For Local/Self-Hosted**

Use :class:`~litestar_storages.backends.filesystem.FileSystemStorage` when
storing files on the local filesystem or network-attached storage.

.. code-block:: python

   from pathlib import Path
   from litestar_storages import FileSystemStorage, FileSystemConfig

   storage = FileSystemStorage(
       config=FileSystemConfig(
           path=Path("/var/uploads"),
           base_url="https://cdn.example.com/uploads",
       )
   )

**For AWS or S3-Compatible**

Use :class:`~litestar_storages.backends.s3.S3Storage` for Amazon S3 and
S3-compatible services like Cloudflare R2, DigitalOcean Spaces, MinIO, etc.

.. code-block:: python

   from litestar_storages import S3Storage, S3Config

   # AWS S3
   storage = S3Storage(
       config=S3Config(
           bucket="my-bucket",
           region="us-east-1",
       )
   )

   # Cloudflare R2
   storage = S3Storage(
       config=S3Config(
           bucket="my-bucket",
           endpoint_url="https://account.r2.cloudflarestorage.com",
           access_key_id="...",
           secret_access_key="...",
       )
   )

**For Google Cloud**

Use :class:`~litestar_storages.backends.gcs.GCSStorage` for Google Cloud Storage.

.. code-block:: python

   from litestar_storages import GCSStorage, GCSConfig

   storage = GCSStorage(
       config=GCSConfig(
           bucket="my-bucket",
           project="my-project",
       )
   )

**For Azure**

Use :class:`~litestar_storages.backends.azure.AzureStorage` for Azure Blob Storage.

.. code-block:: python

   from litestar_storages import AzureStorage, AzureConfig

   storage = AzureStorage(
       config=AzureConfig(
           container="my-container",
           connection_string="DefaultEndpointsProtocol=https;...",
       )
   )
