DTOs
====

.. module:: litestar_storages.contrib.dto

Data Transfer Objects for serializing :class:`~litestar_storages.types.StoredFile`
objects in API responses.

DTO Classes
-----------

.. autoclass:: StoredFileDTO
   :members:
   :undoc-members:
   :no-show-inheritance:

   **Bases:** :class:`~litestar.dto.DataclassDTO`\ [:class:`~litestar_storages.types.StoredFile`]

   **Excluded fields:** ``metadata``

   Use this DTO for standard upload responses where internal metadata
   should not be exposed to clients.

.. autoclass:: StoredFileReadDTO
   :members:
   :undoc-members:
   :no-show-inheritance:

   **Bases:** :class:`~litestar.dto.DataclassDTO`\ [:class:`~litestar_storages.types.StoredFile`]

   **Included fields:** All (including ``metadata``)

   Use this DTO when you need to expose all file information, including
   user-defined metadata.

Usage Examples
--------------

Basic Upload Response
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from litestar import post
   from litestar.datastructures import UploadFile
   from litestar_storages import Storage, StoredFile
   from litestar_storages.contrib.dto import StoredFileDTO

   @post("/upload", return_dto=StoredFileDTO)
   async def upload(
       data: UploadFile,
       storage: Storage,
   ) -> StoredFile:
       content = await data.read()
       return await storage.put(
           key=f"uploads/{data.filename}",
           data=content,
           content_type=data.content_type,
       )

Response:

.. code-block:: json

   {
       "key": "uploads/document.pdf",
       "size": 102400,
       "content_type": "application/pdf",
       "etag": "d41d8cd98f00b204e9800998ecf8427e",
       "last_modified": "2024-01-15T10:30:00Z"
   }

File Info with Metadata
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from litestar import get
   from litestar_storages import Storage, StoredFile
   from litestar_storages.contrib.dto import StoredFileReadDTO

   @get("/files/{key:path}/info", return_dto=StoredFileReadDTO)
   async def get_file_info(
       key: str,
       storage: Storage,
   ) -> StoredFile:
       return await storage.info(key)

Response:

.. code-block:: json

   {
       "key": "uploads/document.pdf",
       "size": 102400,
       "content_type": "application/pdf",
       "etag": "d41d8cd98f00b204e9800998ecf8427e",
       "last_modified": "2024-01-15T10:30:00Z",
       "metadata": {
           "uploaded_by": "user123",
           "department": "engineering"
       }
   }

Listing Files
^^^^^^^^^^^^^

.. code-block:: python

   from litestar import get
   from litestar_storages import Storage, StoredFile
   from litestar_storages.contrib.dto import StoredFileDTO

   @get("/files", return_dto=StoredFileDTO)
   async def list_files(
       storage: Storage,
       prefix: str = "",
   ) -> list[StoredFile]:
       return [file async for file in storage.list(prefix)]

Custom DTOs
^^^^^^^^^^^

Create custom DTOs for specific use cases:

.. code-block:: python

   from litestar.dto import DataclassDTO, DTOConfig
   from litestar_storages.types import StoredFile

   class MinimalFileDTO(DataclassDTO[StoredFile]):
       """Only return key and size."""
       config = DTOConfig(
           include={"key", "size"},
       )

   class DetailedFileDTO(DataclassDTO[StoredFile]):
       """Return all fields with renamed output."""
       config = DTOConfig(
           rename_fields={"key": "path", "content_type": "mime_type"},
       )

Using DTOs with Upload Results
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from dataclasses import dataclass
   from litestar import post
   from litestar.dto import DataclassDTO
   from litestar_storages import Storage, StoredFile
   from litestar_storages.contrib.dto import StoredFileDTO

   @dataclass
   class UploadResponse:
       file: StoredFile
       download_url: str

   class UploadResponseDTO(DataclassDTO[UploadResponse]):
       pass

   @post("/upload", return_dto=UploadResponseDTO)
   async def upload(
       data: UploadFile,
       storage: Storage,
   ) -> UploadResponse:
       content = await data.read()
       file = await storage.put(
           key=f"uploads/{data.filename}",
           data=content,
       )
       url = await storage.url(file.key)
       return UploadResponse(file=file, download_url=url)
