FileSystem Storage
==================

.. module:: litestar_storages.backends.filesystem

Local filesystem storage backend using ``aiofiles`` for async I/O operations.
Stores files in a configurable directory with support for URL generation via
a base URL.

.. note::
   Requires the ``aiofiles`` package. Install with:
   ``pip install litestar-storages[filesystem]`` or ``pip install aiofiles``

Configuration
-------------

.. autoclass:: FileSystemConfig
   :members:
   :undoc-members:
   :show-inheritance:

Storage Class
-------------

.. autoclass:: FileSystemStorage
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Security

   Path traversal attacks are prevented via the ``_sanitize_key()`` method,
   which normalizes paths and prevents access outside the configured base directory.

Usage Examples
--------------

Basic Usage
^^^^^^^^^^^

.. code-block:: python

   from pathlib import Path
   from litestar_storages import FileSystemStorage, FileSystemConfig

   storage = FileSystemStorage(
       config=FileSystemConfig(
           path=Path("/var/uploads"),
       )
   )

   # Store a file
   result = await storage.put(
       "images/photo.jpg",
       image_bytes,
       content_type="image/jpeg",
   )
   # File saved to: /var/uploads/images/photo.jpg

   # Get file info
   info = await storage.info("images/photo.jpg")
   print(f"Size: {info.size}, Modified: {info.last_modified}")

With CDN Base URL
^^^^^^^^^^^^^^^^^

When serving files through a CDN or web server:

.. code-block:: python

   from pathlib import Path
   from litestar_storages import FileSystemStorage, FileSystemConfig

   storage = FileSystemStorage(
       config=FileSystemConfig(
           path=Path("/var/www/uploads"),
           base_url="https://cdn.example.com/uploads",
       )
   )

   await storage.put("images/photo.jpg", image_bytes)

   # Generate public URL
   url = await storage.url("images/photo.jpg")
   # Returns: "https://cdn.example.com/uploads/images/photo.jpg"

Custom Permissions
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   storage = FileSystemStorage(
       config=FileSystemConfig(
           path=Path("/var/uploads"),
           permissions=0o600,  # Owner read/write only
       )
   )

Listing Files
^^^^^^^^^^^^^

.. code-block:: python

   # List all files
   async for file in storage.list():
       print(f"{file.key}: {file.size} bytes")

   # List files with prefix
   async for file in storage.list("images/2024/"):
       print(file.key)

   # List with limit
   async for file in storage.list(limit=10):
       print(file.key)

Streaming Large Files
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Stream download
   async for chunk in storage.get("large-video.mp4"):
       await response.write(chunk)

   # Stream upload from async generator
   async def read_chunks():
       async with aiofiles.open("/path/to/source", "rb") as f:
           while chunk := await f.read(64 * 1024):
               yield chunk

   await storage.put("large-file.bin", read_chunks())

Path Traversal Protection
-------------------------

The storage backend sanitizes all keys to prevent directory traversal attacks:

.. code-block:: python

   # These dangerous inputs are sanitized:
   storage._sanitize_key("../../../etc/passwd")  # Returns: "etc/passwd"
   storage._sanitize_key("/absolute/path")       # Returns: "absolute/path"
   storage._sanitize_key("..\\..\\windows")      # Returns: "windows"

All operations are restricted to files within the configured base path.
