Base Classes
============

.. module:: litestar_storages.base

This module defines the core storage protocol and abstract base class that all
storage backends implement. The protocol-based design ensures consistent behavior
across different storage providers while allowing for backend-specific optimizations.

Storage Protocol
----------------

The ``Storage`` protocol defines the interface that all storage backends must implement.
It is marked with ``@runtime_checkable``, allowing runtime type checking with ``isinstance()``.

.. autoclass:: Storage
   :members:
   :undoc-members:
   :show-inheritance:

   .. rubric:: Core Operations

   The protocol defines these core async operations:

   * :meth:`put` - Store data at a key
   * :meth:`get` - Retrieve data as an async stream
   * :meth:`get_bytes` - Retrieve data as bytes
   * :meth:`delete` - Remove a file
   * :meth:`exists` - Check if a file exists
   * :meth:`list` - List files with optional prefix filter
   * :meth:`url` - Generate access URL (presigned for cloud backends)
   * :meth:`copy` - Copy a file within the storage
   * :meth:`move` - Move/rename a file
   * :meth:`info` - Get file metadata without downloading
   * :meth:`close` - Release resources

Base Storage Class
------------------

The ``BaseStorage`` abstract base class provides default implementations for
convenience methods while requiring subclasses to implement core operations.

.. autoclass:: BaseStorage
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Abstract Methods (must implement)

   Subclasses must implement these methods:

   * :meth:`put`
   * :meth:`get`
   * :meth:`delete`
   * :meth:`exists`
   * :meth:`list`
   * :meth:`url`
   * :meth:`info`

   .. rubric:: Default Implementations

   These methods have default implementations that can be overridden for optimization:

   * :meth:`get_bytes` - Collects stream into bytes
   * :meth:`copy` - Downloads and re-uploads (override for server-side copy)
   * :meth:`move` - Copies then deletes (override for atomic rename)
   * :meth:`close` - No-op (override to release resources)

Usage Example
-------------

Implementing a custom storage backend:

.. code-block:: python

   from collections.abc import AsyncGenerator, AsyncIterator
   from datetime import timedelta

   from litestar_storages import BaseStorage, StoredFile


   class MyCustomStorage(BaseStorage):
       """Custom storage backend example."""

       def __init__(self, connection_url: str) -> None:
           self.connection_url = connection_url
           self._client = None

       async def put(
           self,
           key: str,
           data: bytes | AsyncGenerator[bytes, None],
           *,
           content_type: str | None = None,
           metadata: dict[str, str] | None = None,
       ) -> StoredFile:
           # Implementation here
           ...

       async def get(self, key: str) -> AsyncIterator[bytes]:
           # Implementation here
           ...

       async def delete(self, key: str) -> None:
           # Implementation here
           ...

       async def exists(self, key: str) -> bool:
           # Implementation here
           ...

       async def list(
           self,
           prefix: str = "",
           *,
           limit: int | None = None,
       ) -> AsyncGenerator[StoredFile, None]:
           # Implementation here
           ...

       async def url(
           self,
           key: str,
           *,
           expires_in: timedelta | None = None,
       ) -> str:
           # Implementation here
           ...

       async def info(self, key: str) -> StoredFile:
           # Implementation here
           ...

       async def close(self) -> None:
           # Clean up resources
           if self._client:
               await self._client.close()
