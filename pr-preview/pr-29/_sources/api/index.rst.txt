API Reference
=============

This section provides comprehensive API documentation for all public classes,
functions, and modules in litestar-storages. The documentation is automatically
generated from source code docstrings.

.. note::
   All storage backends implement the :class:`~litestar_storages.base.Storage` protocol,
   ensuring consistent behavior across different providers.

Quick Navigation
----------------

**Core Types**

* :class:`~litestar_storages.base.Storage` - Protocol defining the storage interface
* :class:`~litestar_storages.base.BaseStorage` - Abstract base class for backends
* :class:`~litestar_storages.types.StoredFile` - File metadata dataclass
* :class:`~litestar_storages.types.UploadResult` - Upload operation result

**Storage Backends**

* :class:`~litestar_storages.backends.memory.MemoryStorage` - In-memory (testing/development)
* :class:`~litestar_storages.backends.filesystem.FileSystemStorage` - Local filesystem
* :class:`~litestar_storages.backends.s3.S3Storage` - Amazon S3 and S3-compatible services
* :class:`~litestar_storages.backends.gcs.GCSStorage` - Google Cloud Storage
* :class:`~litestar_storages.backends.azure.AzureStorage` - Azure Blob Storage

**Litestar Integration**

* :class:`~litestar_storages.contrib.plugin.StoragePlugin` - Litestar plugin
* :func:`~litestar_storages.contrib.dependencies.provide_storage` - DI utilities
* :class:`~litestar_storages.contrib.dto.StoredFileDTO` - Response DTOs

**Exceptions**

* :class:`~litestar_storages.exceptions.StorageError` - Base exception
* :class:`~litestar_storages.exceptions.StorageFileNotFoundError` - File not found
* :class:`~litestar_storages.exceptions.StoragePermissionError` - Permission denied
* :class:`~litestar_storages.exceptions.ConfigurationError` - Invalid configuration


Module Reference
----------------

.. toctree::
   :maxdepth: 2

   base
   types
   exceptions
   backends/index
   contrib/index
