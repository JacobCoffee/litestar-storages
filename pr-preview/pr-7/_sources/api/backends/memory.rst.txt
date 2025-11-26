Memory Storage
==============

.. module:: litestar_storages.backends.memory

In-memory storage backend for testing and development. Data is stored in a
Python dictionary and lost when the process exits.

.. warning::
   This backend is not suitable for production use. Data is not persisted
   and memory usage grows with stored files.

Configuration
-------------

.. autoclass:: MemoryConfig
   :members:
   :undoc-members:
   :show-inheritance:

Storage Class
-------------

.. autoclass:: MemoryStorage
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Usage Examples
--------------

Basic Usage
^^^^^^^^^^^

.. code-block:: python

   from litestar_storages import MemoryStorage

   # Create storage with default settings
   storage = MemoryStorage()

   # Store a file
   result = await storage.put(
       "documents/readme.txt",
       b"Hello, World!",
       content_type="text/plain",
   )
   print(f"Stored {result.size} bytes")

   # Retrieve the file
   data = await storage.get_bytes("documents/readme.txt")
   print(data.decode())  # "Hello, World!"

   # Check existence
   exists = await storage.exists("documents/readme.txt")
   print(f"Exists: {exists}")  # True

   # Delete the file
   await storage.delete("documents/readme.txt")

With Size Limit
^^^^^^^^^^^^^^^

.. code-block:: python

   from litestar_storages import MemoryStorage, MemoryConfig
   from litestar_storages.exceptions import StorageError

   # Limit total storage to 1MB
   storage = MemoryStorage(
       config=MemoryConfig(max_size=1024 * 1024)
   )

   try:
       # This will fail if total exceeds 1MB
       await storage.put("large-file.bin", large_data)
   except StorageError as e:
       print(f"Storage full: {e}")

Testing Example
^^^^^^^^^^^^^^^

.. code-block:: python

   import pytest
   from litestar_storages import MemoryStorage


   @pytest.fixture
   def storage():
       """Provide a fresh storage instance for each test."""
       return MemoryStorage()


   async def test_upload_and_download(storage):
       # Upload
       result = await storage.put("test.txt", b"test content")
       assert result.key == "test.txt"
       assert result.size == 12

       # Download
       data = await storage.get_bytes("test.txt")
       assert data == b"test content"


   async def test_file_not_found(storage):
       from litestar_storages.exceptions import StorageFileNotFoundError

       with pytest.raises(StorageFileNotFoundError):
           await storage.get_bytes("nonexistent.txt")

URL Generation
^^^^^^^^^^^^^^

Memory storage generates ``memory://`` URLs that are not externally accessible:

.. code-block:: python

   url = await storage.url("test.txt")
   # Returns: "memory://test.txt"

This is primarily useful for maintaining API consistency in tests.
