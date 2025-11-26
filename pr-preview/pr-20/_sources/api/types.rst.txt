Types
=====

.. module:: litestar_storages.types

This module contains the data structures used throughout litestar-storages for
representing file metadata and operation results.

StoredFile
----------

The primary data structure for file metadata, returned by most storage operations.

.. autoclass:: StoredFile
   :members:
   :undoc-members:
   :show-inheritance:

   .. rubric:: Example

   .. code-block:: python

      from litestar_storages import StoredFile

      # StoredFile is a frozen dataclass
      file = StoredFile(
          key="uploads/document.pdf",
          size=1024000,
          content_type="application/pdf",
          etag="d41d8cd98f00b204e9800998ecf8427e",
          last_modified=datetime.now(tz=timezone.utc),
          metadata={"uploaded_by": "user123"},
      )

      # Access attributes
      print(f"File: {file.key}, Size: {file.size} bytes")

UploadResult
------------

Result container for upload operations that includes both file metadata and
an optional access URL.

.. autoclass:: UploadResult
   :members:
   :undoc-members:
   :show-inheritance:

   .. rubric:: Example

   .. code-block:: python

      from litestar_storages import UploadResult, StoredFile

      result = UploadResult(
          file=StoredFile(
              key="uploads/image.jpg",
              size=50000,
              content_type="image/jpeg",
          ),
          url="https://bucket.s3.amazonaws.com/uploads/image.jpg?signature=...",
      )

      # Use in responses
      return {
          "uploaded": result.file.key,
          "download_url": result.url,
      }

Type Aliases
------------

The library also uses these standard Python types:

.. code-block:: python

   from collections.abc import AsyncGenerator, AsyncIterator

   # Data input types (accepted by put())
   DataInput = bytes | AsyncGenerator[bytes, None]

   # Stream output type (returned by get())
   DataStream = AsyncIterator[bytes]
