GCS Storage
===========

.. module:: litestar_storages.backends.gcs

Google Cloud Storage backend using ``gcloud-aio-storage`` for async operations.
Supports Application Default Credentials (ADC) and service account authentication.

.. note::
   Requires the ``gcloud-aio-storage`` package. Install with:
   ``pip install litestar-storages[gcs]`` or ``pip install gcloud-aio-storage``

Configuration
-------------

.. autoclass:: GCSConfig
   :members:
   :undoc-members:
   :show-inheritance:

Storage Class
-------------

.. autoclass:: GCSStorage
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Usage Examples
--------------

Using Application Default Credentials
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When running on GCP (GCE, GKE, Cloud Run, Cloud Functions), credentials are
automatically detected:

.. code-block:: python

   from litestar_storages import GCSStorage, GCSConfig

   storage = GCSStorage(
       config=GCSConfig(
           bucket="my-bucket",
           project="my-project",
       )
   )

Using Service Account
^^^^^^^^^^^^^^^^^^^^^

For local development or non-GCP environments:

.. code-block:: python

   storage = GCSStorage(
       config=GCSConfig(
           bucket="my-bucket",
           service_file="/path/to/service-account.json",
       )
   )

Using Emulator (fake-gcs-server)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For local testing without GCP access:

.. code-block:: python

   # Start emulator: docker run -p 4443:4443 fsouza/fake-gcs-server

   storage = GCSStorage(
       config=GCSConfig(
           bucket="test-bucket",
           api_root="http://localhost:4443",
       )
   )

With Key Prefix
^^^^^^^^^^^^^^^

.. code-block:: python

   storage = GCSStorage(
       config=GCSConfig(
           bucket="my-bucket",
           prefix="uploads/media/",
       )
   )

   # Key "image.jpg" becomes "uploads/media/image.jpg" in GCS
   await storage.put("image.jpg", data)

Signed URLs
^^^^^^^^^^^

.. code-block:: python

   from datetime import timedelta

   # Generate signed URL with default expiry (1 hour)
   url = await storage.url("documents/contract.pdf")

   # Custom expiry
   url = await storage.url(
       "documents/contract.pdf",
       expires_in=timedelta(days=7),
   )

.. note::
   Generating signed URLs requires service account credentials with the
   ``iam.serviceAccounts.signBlob`` permission.

File Operations
^^^^^^^^^^^^^^^

.. code-block:: python

   # Upload
   result = await storage.put(
       "reports/monthly.pdf",
       pdf_bytes,
       content_type="application/pdf",
       metadata={"department": "finance"},
   )

   # Download
   data = await storage.get_bytes("reports/monthly.pdf")

   # Stream download
   async for chunk in storage.get("reports/monthly.pdf"):
       process(chunk)

   # Check existence
   if await storage.exists("reports/monthly.pdf"):
       print("File exists")

   # Get metadata
   info = await storage.info("reports/monthly.pdf")
   print(f"Size: {info.size}, Type: {info.content_type}")

   # List files
   async for file in storage.list("reports/"):
       print(f"{file.key}: {file.size} bytes")

   # Copy and move
   await storage.copy("reports/v1.pdf", "reports/v2.pdf")
   await storage.move("reports/draft.pdf", "reports/final.pdf")

   # Delete
   await storage.delete("reports/old.pdf")

Authentication Methods
----------------------

GCS supports multiple authentication methods:

1. **Application Default Credentials (ADC)** - Automatic on GCP
2. **Service Account JSON** - Via ``service_file`` config
3. **Environment Variable** - Set ``GOOGLE_APPLICATION_CREDENTIALS``

For production on GCP, ADC with Workload Identity is recommended.

Resource Cleanup
----------------

Always close the storage when done to release HTTP sessions:

.. code-block:: python

   storage = GCSStorage(config=GCSConfig(bucket="my-bucket"))
   try:
       # Use storage...
       pass
   finally:
       await storage.close()

When using :class:`~litestar_storages.contrib.plugin.StoragePlugin`,
cleanup is handled automatically on application shutdown.
