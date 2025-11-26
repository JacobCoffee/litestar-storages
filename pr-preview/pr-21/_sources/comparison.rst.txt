Comparison with Other Libraries
================================

When choosing a file storage library for your Python web application, you have several options.
This guide compares litestar-storages with the most popular alternatives: django-storages and
fastapi-storages. Understanding these differences will help you make an informed decision for
your project.

Library Overview
----------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 25 25

   * - Attribute
     - litestar-storages
     - fastapi-storages
     - django-storages
   * - Latest Version
     - 0.1.0
     - 0.3.0 (Feb 2024)
     - 1.14.6 (April 2025)
   * - GitHub Stars
     - New project
     - ~98
     - ~2,900
   * - PyPI Downloads
     - New project
     - ~21k/month
     - Very high (mature)
   * - Framework
     - Framework-agnostic (Litestar plugin available)
     - FastAPI (via ORM types)
     - Django only
   * - Maintenance Status
     - Active development
     - Low activity
     - Active
   * - License
     - MIT
     - MIT
     - BSD

Architecture Comparison
-----------------------

Sync vs Async: Why It Matters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The most significant architectural difference between these libraries is their approach to
asynchronous I/O. Both django-storages and fastapi-storages are **synchronous**, while
litestar-storages is **async-native**.

**Why async matters for file storage:**

1. **Non-blocking I/O**: File operations, especially to cloud storage, involve network I/O.
   Synchronous operations block your entire application thread while waiting for responses.
   Async operations allow other requests to be processed during this wait time.

2. **Concurrency**: A single async application can handle many concurrent file uploads/downloads
   without spawning additional threads or processes. This is particularly important for
   real-time applications and high-throughput scenarios.

3. **Memory efficiency**: Async streaming allows processing large files chunk-by-chunk without
   loading the entire file into memory, which is critical for handling large uploads.

4. **Modern Python**: The Python ecosystem is moving toward async-first designs. Libraries like
   FastAPI, Litestar, and Starlette are async-native, and using sync storage operations with
   them creates bottlenecks.

.. code-block:: python
   :caption: litestar-storages (async-native)

   # Non-blocking file operations
   async def upload_file(storage: Storage, file: UploadFile) -> StoredFile:
       # This doesn't block the event loop
       return await storage.put(
           key=file.filename,
           data=file.file,  # Async streaming
           content_type=file.content_type,
       )

   # Stream large files without memory overhead
   async def download_file(storage: Storage, key: str) -> AsyncIterator[bytes]:
       async for chunk in storage.get(key):
           yield chunk  # Memory-efficient streaming

.. code-block:: python
   :caption: django-storages / fastapi-storages (sync)

   # Blocks the thread while waiting for S3
   def upload_file(storage, file) -> str:
       # Thread blocked during entire network operation
       return storage.save(file.name, file)

   # May load entire file into memory
   def download_file(storage, name) -> bytes:
       with storage.open(name) as f:
           return f.read()  # Entire file in memory

Design Philosophy
^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 25 25 25

   * - Aspect
     - litestar-storages
     - fastapi-storages
     - django-storages
   * - API Design
     - Protocol-based (duck typing)
     - Class inheritance
     - Django File API
   * - Configuration
     - Dataclass configs
     - Constructor args
     - Django settings
   * - Error Handling
     - Typed exception hierarchy
     - SDK exceptions
     - SDK exceptions
   * - Testing Story
     - In-memory backend
     - Mock SDK
     - Mock Django storage

Feature Comparison Matrix
-------------------------

Core Operations
^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 20 20 20 20

   * - Operation
     - Method
     - litestar-storages
     - fastapi-storages
     - django-storages
   * - Store file
     - ``put`` / ``save``
     - |yes| Async
     - |yes| Sync
     - |yes| Sync
   * - Retrieve file
     - ``get`` / ``open``
     - |yes| Async streaming
     - |yes| Sync
     - |yes| Sync
   * - Delete file
     - ``delete``
     - |yes| Async
     - |yes| Sync
     - |yes| Sync
   * - Check existence
     - ``exists``
     - |yes| Async
     - |no|
     - |yes| Sync
   * - List files
     - ``list`` / ``listdir``
     - |yes| Async iterator
     - |no|
     - |yes| Sync (some backends)
   * - Get URL
     - ``url``
     - |yes| Presigned URLs
     - |no|
     - |yes| Sync
   * - Copy file
     - ``copy``
     - |yes| Async
     - |no|
     - |no|
   * - Move file
     - ``move``
     - |yes| Async
     - |no|
     - |no|
   * - File info/metadata
     - ``info``
     - |yes| StoredFile dataclass
     - |no|
     - |partial| Via file object

.. |yes| replace:: Yes
.. |no| replace:: No
.. |partial| replace:: Partial

Advanced Features
^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 20 20 30

   * - Feature
     - litestar-storages
     - fastapi-storages
     - django-storages
   * - **Multipart Upload**
     - |yes| Explicit API (start/upload_part/complete/abort)
     - |no|
     - |partial| Implicit (S3 only, via boto3 TransferConfig)
   * - **Progress Callbacks**
     - |yes| ProgressInfo dataclass with percentage, speed, ETA
     - |no|
     - |no|
   * - **Retry Logic**
     - |yes| RetryConfig with exponential backoff + jitter
     - |no|
     - |partial| SDK defaults only
   * - **Streaming Upload**
     - |yes| AsyncIterator/AsyncGenerator support
     - |no|
     - |partial| ChunkedUpload for some backends
   * - **Streaming Download**
     - |yes| AsyncIterator yielding chunks
     - |no|
     - |partial| Temp files for large downloads
   * - **Custom Metadata**
     - |yes| Dict passed to put()
     - |no|
     - |partial| Backend-dependent

Backend Support
^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 25 25 25

   * - Backend
     - litestar-storages
     - fastapi-storages
     - django-storages
   * - **Local Filesystem**
     - |yes| FileSystemStorage
     - |yes| FileSystemStorage
     - |yes| FileSystemStorage
   * - **In-Memory**
     - |yes| MemoryStorage
     - |no|
     - |no| (Django's InMemoryStorage is for testing)
   * - **Amazon S3**
     - |yes| S3Storage (aioboto3)
     - |yes| S3Storage (boto3)
     - |yes| S3Boto3Storage (boto3)
   * - **S3-Compatible**
     - |yes| R2, Spaces, MinIO, B2
     - |yes| Basic support
     - |yes| Via endpoint_url
   * - **Google Cloud Storage**
     - |yes| GCSStorage (aiohttp)
     - |no|
     - |yes| GoogleCloudStorage
   * - **Azure Blob Storage**
     - |yes| AzureStorage (aiohttp)
     - |no|
     - |yes| AzureStorage
   * - **Dropbox**
     - |no|
     - |no|
     - |yes| DropBoxStorage
   * - **SFTP/FTP**
     - |no|
     - |no|
     - |yes| SFTPStorage, FTPStorage
   * - **Apache Libcloud**
     - |no|
     - |no|
     - |yes| LibCloudStorage

Framework Integration
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 20 20 30

   * - Feature
     - litestar-storages
     - fastapi-storages
     - django-storages
   * - **Dependency Injection**
     - |yes| StoragePlugin with Provide()
     - |partial| Manual FastAPI Depends
     - |yes| Django settings DEFAULT_FILE_STORAGE
   * - **Lifespan Management**
     - |yes| Auto-cleanup on shutdown
     - |no|
     - |yes| Django manages
   * - **Multiple Storages**
     - |yes| Named storages via plugin
     - |partial| Manual setup
     - |yes| STORAGES dict (Django 4.2+)
   * - **ORM Integration**
     - |no| (Use Litestar types)
     - |yes| SQLAlchemy FileType
     - |yes| FileField, ImageField

Exception Handling
^^^^^^^^^^^^^^^^^^

litestar-storages provides a comprehensive exception hierarchy to handle storage errors
consistently across all backends:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Exception
     - Description
   * - ``StorageError``
     - Base exception for all storage errors
   * - ``StorageFileNotFoundError``
     - File does not exist (key not found)
   * - ``StoragePermissionError``
     - Access denied (authentication/authorization failure)
   * - ``StorageConnectionError``
     - Network or connection issues
   * - ``StorageConfigurationError``
     - Invalid configuration (missing credentials, bad bucket name)
   * - ``StorageQuotaExceededError``
     - Storage limit reached

Both fastapi-storages and django-storages expose underlying SDK exceptions (botocore exceptions,
Azure exceptions, etc.), requiring backend-specific error handling.

litestar-storages Advantages
----------------------------

**1. Async-Native Design**

Built from the ground up with ``async/await``. Uses aioboto3 for S3, aiohttp for GCS/Azure,
and aiofiles for filesystem operations. No thread pool executors or sync-to-async wrappers.

**2. Five Production-Ready Backends**

Memory, Filesystem, S3, Azure, and GCS backends all implement the same protocol. fastapi-storages
only offers 2 backends (Filesystem, S3). While django-storages has more backends (7+), they are
all synchronous.

**3. Explicit Multipart Upload API**

For large files, litestar-storages provides a clear multipart upload workflow:

.. code-block:: python

   # Start multipart upload
   upload = await storage.start_multipart_upload("large-file.zip")

   # Upload parts (can be parallelized)
   parts = []
   for i, chunk in enumerate(chunks, 1):
       part = await storage.upload_part(upload, i, chunk)
       parts.append(part)

   # Complete upload
   await storage.complete_multipart_upload(upload, parts)

   # Or abort if something goes wrong
   await storage.abort_multipart_upload(upload)

**4. Progress Callbacks**

Track upload/download progress with detailed information:

.. code-block:: python

   def on_progress(info: ProgressInfo) -> None:
       print(f"{info.percentage:.1f}% - {info.bytes_per_second / 1024:.1f} KB/s")

   await storage.put(
       "video.mp4",
       data,
       progress_callback=on_progress,
   )

**5. Configurable Retry Logic**

Automatic retries with exponential backoff and jitter:

.. code-block:: python

   from litestar_storages import RetryConfig

   storage = S3Storage(
       config=S3Config(bucket="my-bucket"),
       retry_config=RetryConfig(
           max_attempts=5,
           base_delay=1.0,
           max_delay=30.0,
           exponential_base=2.0,
           jitter=True,
       ),
   )

**6. Protocol-Based Design**

The ``Storage`` protocol uses ``@runtime_checkable`` for duck typing. No inheritance required
for custom backends:

.. code-block:: python

   from litestar_storages import Storage

   # Your custom backend just needs to implement the protocol
   class MyCustomStorage:
       async def put(self, key: str, data: bytes, ...) -> StoredFile: ...
       async def get(self, key: str) -> AsyncIterator[bytes]: ...
       # ... other methods

   # Type checking works
   def use_storage(storage: Storage) -> None:
       assert isinstance(storage, Storage)  # Runtime check works too

**7. Framework-Agnostic Core**

The core storage classes work without Litestar. The ``StoragePlugin`` is optional and only
needed for Litestar integration. Use litestar-storages with FastAPI, Starlette, or plain
Python async code.

**8. In-Memory Backend for Testing**

``MemoryStorage`` makes testing trivial without mocking:

.. code-block:: python

   @pytest.fixture
   def storage():
       return MemoryStorage()

   async def test_upload(storage):
       await storage.put("test.txt", b"content")
       assert await storage.exists("test.txt")

**9. Comprehensive Exception Hierarchy**

Handle errors consistently across all backends without catching backend-specific exceptions.

When to Choose Each Library
---------------------------

Choose litestar-storages when:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- You are building an **async-first application** (Litestar, FastAPI, Starlette, aiohttp)
- You need **progress tracking** for file transfers
- You want **explicit control over multipart uploads**
- You need to handle **large files with streaming**
- You value **testability** with in-memory storage
- You want a **consistent API** across S3, Azure, GCS, and local storage
- You prefer **typed exceptions** over SDK-specific error handling
- You want **retry logic built-in** rather than implementing your own

Choose fastapi-storages when:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- You only need **basic S3 or filesystem storage**
- You are using **SQLAlchemy ORM** and want FileType column integration
- Your application is **sync** or you don't mind blocking operations
- You have **simple storage needs** without progress tracking or multipart uploads

Choose django-storages when:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- You are building a **Django application**
- You need **Django ORM integration** (FileField, ImageField)
- You require backends like **Dropbox, SFTP, FTP, or Libcloud**
- Your application is **sync** (Django's traditional model)
- You want a **mature, battle-tested** library with extensive community support
- You need to match **existing Django infrastructure**

Migration Guide
---------------

Migrating from django-storages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you're moving from Django to an async framework like Litestar:

.. code-block:: python

   # django-storages (before)
   from django.core.files.storage import default_storage

   path = default_storage.save("uploads/file.txt", file)
   url = default_storage.url(path)

   # litestar-storages (after)
   from litestar_storages import S3Storage, S3Config

   storage = S3Storage(S3Config(bucket="my-bucket"))
   stored = await storage.put("uploads/file.txt", file.read())
   url = await storage.url(stored.key)

Key differences:

- All operations are ``async`` - add ``await``
- ``save()`` becomes ``put()`` returning ``StoredFile``
- ``open()`` becomes ``get()`` returning ``AsyncIterator[bytes]``
- ``delete()`` stays the same (but async)
- ``exists()`` stays the same (but async)
- ``url()`` becomes async with optional ``expires_in`` parameter

Migrating from fastapi-storages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # fastapi-storages (before)
   from fastapi_storages import FileSystemStorage

   storage = FileSystemStorage(path="/uploads")
   storage.write(file_path, content)

   # litestar-storages (after)
   from litestar_storages import FileSystemStorage, FileSystemConfig

   storage = FileSystemStorage(FileSystemConfig(path="/uploads"))
   await storage.put(file_path, content)

Key differences:

- Add ``await`` to all operations
- Use config dataclasses instead of constructor arguments
- ``write()`` becomes ``put()``
- Access to additional features: progress callbacks, retry logic, streaming

Performance Considerations
--------------------------

Async Performance Benefits
^^^^^^^^^^^^^^^^^^^^^^^^^^

In benchmarks, async storage operations show significant advantages for concurrent workloads:

.. list-table::
   :header-rows: 1
   :widths: 40 30 30

   * - Scenario
     - Sync (blocking)
     - Async (litestar-storages)
   * - 100 concurrent uploads (1MB each)
     - ~100 threads needed
     - Single event loop
   * - Memory per connection
     - Thread stack (~1MB)
     - Coroutine (~2KB)
   * - Context switching
     - OS-level (expensive)
     - User-level (cheap)
   * - I/O wait handling
     - Thread blocked
     - Other tasks execute

Connection Pooling
^^^^^^^^^^^^^^^^^^

litestar-storages maintains efficient connection pools for cloud backends:

- **S3**: aioboto3's AioSession manages connection pooling
- **GCS/Azure**: aiohttp ClientSession with configurable pool size
- **Filesystem**: aiofiles uses thread pool for non-blocking file I/O

Streaming for Large Files
^^^^^^^^^^^^^^^^^^^^^^^^^

Avoid memory issues with large files using streaming:

.. code-block:: python

   # Memory-efficient upload from file
   async def upload_large_file(storage: Storage, filepath: Path) -> StoredFile:
       async def stream_file():
           async with aiofiles.open(filepath, "rb") as f:
               while chunk := await f.read(8192):
                   yield chunk

       return await storage.put(
           key=filepath.name,
           data=stream_file(),
       )

   # Memory-efficient download
   async def download_large_file(storage: Storage, key: str, dest: Path) -> None:
       async with aiofiles.open(dest, "wb") as f:
           async for chunk in storage.get(key):
               await f.write(chunk)

Summary
-------

.. list-table::
   :header-rows: 1
   :widths: 25 25 25 25

   * - If you need...
     - litestar-storages
     - fastapi-storages
     - django-storages
   * - Async operations
     - **Best choice**
     - Not supported
     - Not supported
   * - Django integration
     - Not applicable
     - Not applicable
     - **Best choice**
   * - SQLAlchemy ORM types
     - Not built-in
     - **Best choice**
     - Not applicable
   * - Progress tracking
     - **Best choice**
     - Not supported
     - Not supported
   * - Multipart uploads
     - **Best choice**
     - Not supported
     - Implicit only
   * - Most backends
     - 5 backends
     - 2 backends
     - **7+ backends**
   * - Testing story
     - **Best choice** (MemoryStorage)
     - Mock SDK
     - Mock Django

litestar-storages is the best choice for **modern async Python applications** that need
**production-grade file storage** with explicit control over uploads, progress tracking,
and retry logic. Choose django-storages if you're committed to Django, or fastapi-storages
if you have very simple storage needs with SQLAlchemy integration.
