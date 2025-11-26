Azure Storage
=============

.. module:: litestar_storages.backends.azure

Azure Blob Storage backend using ``azure-storage-blob`` async API. Supports
connection strings, account keys, and managed identity authentication.

.. note::
   Requires the ``azure-storage-blob`` package. Install with:
   ``pip install litestar-storages[azure]`` or ``pip install azure-storage-blob``

   For managed identity support, also install ``azure-identity``.

Configuration
-------------

.. autoclass:: AzureConfig
   :members:
   :undoc-members:
   :show-inheritance:

Storage Class
-------------

.. autoclass:: AzureStorage
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Usage Examples
--------------

Using Connection String
^^^^^^^^^^^^^^^^^^^^^^^

The simplest authentication method:

.. code-block:: python

   from litestar_storages import AzureStorage, AzureConfig

   storage = AzureStorage(
       config=AzureConfig(
           container="my-container",
           connection_string="DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=...;EndpointSuffix=core.windows.net",
       )
   )

Using Account URL and Key
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   storage = AzureStorage(
       config=AzureConfig(
           container="my-container",
           account_url="https://myaccount.blob.core.windows.net",
           account_key="your-account-key",
       )
   )

Using Managed Identity
^^^^^^^^^^^^^^^^^^^^^^

When running on Azure (App Service, Functions, AKS, etc.):

.. code-block:: python

   # Requires: pip install azure-identity

   storage = AzureStorage(
       config=AzureConfig(
           container="my-container",
           account_url="https://myaccount.blob.core.windows.net",
           # No account_key - uses DefaultAzureCredential
       )
   )

Using Azurite Emulator
^^^^^^^^^^^^^^^^^^^^^^

For local development:

.. code-block:: bash

   # Start Azurite
   docker run -p 10000:10000 -p 10001:10001 -p 10002:10002 \
       mcr.microsoft.com/azure-storage/azurite

.. code-block:: python

   storage = AzureStorage(
       config=AzureConfig(
           container="test-container",
           connection_string="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1",
       )
   )

With Key Prefix
^^^^^^^^^^^^^^^

.. code-block:: python

   storage = AzureStorage(
       config=AzureConfig(
           container="uploads",
           connection_string="...",
           prefix="media/images/",
       )
   )

   # Key "photo.jpg" becomes "media/images/photo.jpg" in Azure
   await storage.put("photo.jpg", data)

SAS URLs
^^^^^^^^

Generate shared access signature URLs for temporary access:

.. code-block:: python

   from datetime import timedelta

   # Default expiry (1 hour)
   url = await storage.url("documents/report.pdf")

   # Custom expiry
   url = await storage.url(
       "documents/report.pdf",
       expires_in=timedelta(hours=24),
   )

.. note::
   Generating SAS URLs requires the account key (either directly via
   ``account_key`` or parsed from ``connection_string``).

File Operations
^^^^^^^^^^^^^^^

.. code-block:: python

   # Upload with metadata
   result = await storage.put(
       "documents/contract.pdf",
       pdf_bytes,
       content_type="application/pdf",
       metadata={"client": "acme", "version": "2"},
   )

   # Download
   data = await storage.get_bytes("documents/contract.pdf")

   # Stream download
   async for chunk in storage.get("documents/contract.pdf"):
       await response.write(chunk)

   # Check existence
   exists = await storage.exists("documents/contract.pdf")

   # Get metadata
   info = await storage.info("documents/contract.pdf")
   print(f"Size: {info.size}, ETag: {info.etag}")
   print(f"Metadata: {info.metadata}")

   # List files
   async for file in storage.list("documents/"):
       print(f"{file.key}: {file.size} bytes")

   # Copy (server-side)
   await storage.copy("source.txt", "destination.txt")

   # Move (copy + delete)
   await storage.move("old-path.txt", "new-path.txt")

   # Delete
   await storage.delete("documents/old.pdf")

.. note::
   Unlike S3 and GCS, Azure delete raises an error for non-existent blobs.
   Use ``exists()`` first if you need idempotent deletes.

Authentication Methods
----------------------

Azure supports multiple authentication methods:

1. **Connection String** - Contains account name and key
2. **Account URL + Key** - Explicit credentials
3. **Account URL + Managed Identity** - Using DefaultAzureCredential
4. **SAS Token** - Embedded in account URL

For production on Azure, managed identity is recommended.

Resource Cleanup
----------------

Always close the storage when done:

.. code-block:: python

   storage = AzureStorage(config=AzureConfig(...))
   try:
       # Use storage...
       pass
   finally:
       await storage.close()

When using :class:`~litestar_storages.contrib.plugin.StoragePlugin`,
cleanup is handled automatically on application shutdown.
