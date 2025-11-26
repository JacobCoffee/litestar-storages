"""Data Transfer Objects for storage responses."""

from __future__ import annotations

from litestar.dto import DataclassDTO, DTOConfig

from litestar_storages.types import StoredFile

__all__ = ["StoredFileDTO", "StoredFileReadDTO"]


class StoredFileDTO(DataclassDTO[StoredFile]):
    """DTO for StoredFile responses.

    This DTO provides a standard way to serialize StoredFile objects
    in API responses. By default, it excludes the metadata field to
    keep responses clean.

    Example:
        Basic usage::

            from litestar import post
            from litestar.datastructures import UploadFile
            from litestar_storages import Storage, StoredFile
            from litestar_storages.contrib.dto import StoredFileDTO


            @post("/upload", return_dto=StoredFileDTO)
            async def upload(
                data: UploadFile,
                storage: Storage,
            ) -> StoredFile:
                return await storage.put(
                    key=f"uploads/{data.filename}",
                    data=data.file,
                    content_type=data.content_type,
                )

        Response will be::

            {
                "key": "uploads/example.jpg",
                "size": 12345,
                "content_type": "image/jpeg",
                "etag": "abc123",
                "last_modified": "2024-01-15T10:30:00Z",
            }
    """

    config = DTOConfig(
        exclude={"metadata"},  # Hide internal metadata by default
    )


class StoredFileReadDTO(DataclassDTO[StoredFile]):
    """DTO for read-only StoredFile responses.

    This DTO is useful when you want to include all fields from StoredFile,
    including metadata, in read operations.

    Example:
        Include metadata in response::

            from litestar import get
            from litestar_storages import Storage, StoredFile
            from litestar_storages.contrib.dto import StoredFileReadDTO


            @get("/files/{key:path}/info", return_dto=StoredFileReadDTO)
            async def get_file_info(
                key: str,
                storage: Storage,
            ) -> StoredFile:
                return await storage.info(key)

        Response will be::

            {
                "key": "uploads/example.jpg",
                "size": 12345,
                "content_type": "image/jpeg",
                "etag": "abc123",
                "last_modified": "2024-01-15T10:30:00Z",
                "metadata": {"uploaded_by": "user123", "original_filename": "my_photo.jpg"},
            }
    """

    config = DTOConfig()  # Include all fields
