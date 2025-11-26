Exceptions
==========

.. module:: litestar_storages.exceptions

This module defines the exception hierarchy for litestar-storages. All storage
backends raise exceptions from this hierarchy, enabling consistent error handling
across different providers.

.. note::
   Exception names are prefixed with ``Storage`` to avoid shadowing Python built-in
   exceptions like ``FileNotFoundError`` and ``PermissionError``.

Exception Hierarchy
-------------------

.. code-block:: text

   Exception
   +-- StorageError (base for all storage exceptions)
       +-- StorageFileNotFoundError
       +-- StorageFileExistsError
       +-- StoragePermissionError
       +-- StorageConnectionError
       +-- ConfigurationError

Base Exception
--------------

.. autoclass:: StorageError
   :members:
   :undoc-members:
   :show-inheritance:

File Exceptions
---------------

.. autoclass:: StorageFileNotFoundError
   :members:
   :undoc-members:
   :show-inheritance:

   .. rubric:: Example

   .. code-block:: python

      from litestar_storages.exceptions import StorageFileNotFoundError

      try:
          data = await storage.get_bytes("nonexistent.txt")
      except StorageFileNotFoundError as e:
          print(f"File not found: {e.key}")

.. autoclass:: StorageFileExistsError
   :members:
   :undoc-members:
   :show-inheritance:

Permission and Connection Exceptions
------------------------------------

.. autoclass:: StoragePermissionError
   :members:
   :undoc-members:
   :show-inheritance:

   Common causes:

   * Insufficient IAM permissions (cloud backends)
   * File system permissions blocking access
   * Access control policies (bucket policies, ACLs)

.. autoclass:: StorageConnectionError
   :members:
   :undoc-members:
   :show-inheritance:

   Common causes:

   * Network connectivity issues
   * Storage service unavailable
   * Authentication failures
   * Invalid endpoint configuration

Configuration Exception
-----------------------

.. autoclass:: ConfigurationError
   :members:
   :undoc-members:
   :show-inheritance:

   Common causes:

   * Missing required parameters (bucket name, credentials)
   * Invalid configuration values
   * Missing optional dependencies (aioboto3, aiofiles, etc.)

Error Handling Example
----------------------

Comprehensive error handling pattern:

.. code-block:: python

   from litestar_storages import Storage, StorageError
   from litestar_storages.exceptions import (
       ConfigurationError,
       StorageConnectionError,
       StorageFileNotFoundError,
       StoragePermissionError,
   )


   async def safe_get_file(storage: Storage, key: str) -> bytes | None:
       """Safely retrieve a file with comprehensive error handling."""
       try:
           return await storage.get_bytes(key)

       except StorageFileNotFoundError:
           # File doesn't exist - handle gracefully
           return None

       except StoragePermissionError:
           # Log and re-raise or handle based on use case
           logger.error(f"Permission denied for key: {key}")
           raise

       except StorageConnectionError as e:
           # Transient error - could retry
           logger.warning(f"Connection error: {e}, retrying...")
           raise

       except ConfigurationError as e:
           # Configuration issue - fatal
           logger.critical(f"Storage misconfigured: {e}")
           raise

       except StorageError as e:
           # Catch-all for other storage errors
           logger.error(f"Storage error: {e}")
           raise


   async def upload_with_retry(
       storage: Storage,
       key: str,
       data: bytes,
       max_retries: int = 3,
   ) -> StoredFile:
       """Upload with automatic retry on transient errors."""
       for attempt in range(max_retries):
           try:
               return await storage.put(key, data)
           except StorageConnectionError:
               if attempt == max_retries - 1:
                   raise
               await asyncio.sleep(2 ** attempt)  # Exponential backoff
       raise RuntimeError("Unreachable")
