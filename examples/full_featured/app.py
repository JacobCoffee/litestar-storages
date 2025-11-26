"""Full-featured litestar-storages example.

Demonstrates:
- Multiple named storage backends (images, documents)
- Controller-based route organization
- DTO responses for clean API output
- Proper exception handling
- Streaming file downloads
- File metadata and listing

Run with:
    uv run litestar --app examples.full_featured.app:app run

Or from this directory:
    uv run litestar run
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Annotated

from litestar import Controller, Litestar, Response, delete, get, post
from litestar.datastructures import UploadFile
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException, NotFoundException
from litestar.params import Body
from litestar.response import Stream
from litestar.status_codes import HTTP_204_NO_CONTENT, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from litestar_storages import Storage, StoredFile
from litestar_storages.backends.memory import MemoryStorage
from litestar_storages.contrib.dto import StoredFileDTO, StoredFileReadDTO
from litestar_storages.contrib.plugin import StoragePlugin
from litestar_storages.exceptions import StorageFileExistsError, StorageFileNotFoundError

if TYPE_CHECKING:
    from litestar.connection import Request


# =============================================================================
# Exception Handlers
# =============================================================================


def storage_not_found_handler(request: Request, exc: StorageFileNotFoundError) -> Response:
    """Convert StorageFileNotFoundError to 404 response."""
    return Response(
        content={"detail": f"File not found: {exc.key}"},
        status_code=HTTP_404_NOT_FOUND,
    )


def storage_exists_handler(request: Request, exc: StorageFileExistsError) -> Response:
    """Convert StorageFileExistsError to 409 response."""
    return Response(
        content={"detail": f"File already exists: {exc.key}"},
        status_code=HTTP_409_CONFLICT,
    )


# =============================================================================
# Controllers
# =============================================================================


class ImageController(Controller):
    """Controller for image file operations.

    Uses the 'images_storage' dependency for all operations.
    """

    path = "/api/images"
    tags = ["Images"]

    @post("/", return_dto=StoredFileDTO)
    async def upload_image(
        self,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
        images_storage: Storage,
    ) -> StoredFile:
        """Upload an image file.

        Stores the image in the images storage backend with content-type validation.
        """
        content = await data.read()
        content_type = data.content_type or "application/octet-stream"

        # Basic content-type validation
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content type: {content_type}. Expected image/*",
            )

        return await images_storage.put(
            key=f"uploads/{data.filename}",
            data=content,
            content_type=content_type,
        )

    @get("/", return_dto=StoredFileDTO)
    async def list_images(self, images_storage: Storage) -> list[StoredFile]:
        """List all uploaded images."""
        return [f async for f in images_storage.list()]

    @get("/{key:path}", return_dto=StoredFileReadDTO)
    async def get_image_info(self, key: str, images_storage: Storage) -> StoredFile:
        """Get metadata for an image."""
        return await images_storage.info(key)

    @get("/{key:path}/download")
    async def download_image(self, key: str, images_storage: Storage) -> Stream:
        """Download an image file."""
        info = await images_storage.info(key)
        return Stream(
            iterator=images_storage.get(key),
            media_type=info.content_type,
            headers={
                "Content-Length": str(info.size),
                "Content-Disposition": f'inline; filename="{key.split("/")[-1]}"',
            },
        )

    @delete("/{key:path}", status_code=HTTP_204_NO_CONTENT)
    async def delete_image(self, key: str, images_storage: Storage) -> None:
        """Delete an image."""
        await images_storage.delete(key)


class DocumentController(Controller):
    """Controller for document file operations.

    Uses the 'documents_storage' dependency for all operations.
    """

    path = "/api/documents"
    tags = ["Documents"]

    @post("/", return_dto=StoredFileDTO)
    async def upload_document(
        self,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
        documents_storage: Storage,
    ) -> StoredFile:
        """Upload a document file."""
        content = await data.read()
        return await documents_storage.put(
            key=f"docs/{data.filename}",
            data=content,
            content_type=data.content_type or "application/octet-stream",
        )

    @get("/", return_dto=StoredFileDTO)
    async def list_documents(self, documents_storage: Storage) -> list[StoredFile]:
        """List all uploaded documents."""
        return [f async for f in documents_storage.list()]

    @get("/{key:path}", return_dto=StoredFileReadDTO)
    async def get_document_info(self, key: str, documents_storage: Storage) -> StoredFile:
        """Get metadata for a document."""
        return await documents_storage.info(key)

    @get("/{key:path}/download")
    async def download_document(self, key: str, documents_storage: Storage) -> Stream:
        """Download a document file."""
        info = await documents_storage.info(key)
        return Stream(
            iterator=documents_storage.get(key),
            media_type=info.content_type,
            headers={
                "Content-Length": str(info.size),
                "Content-Disposition": f'attachment; filename="{key.split("/")[-1]}"',
            },
        )

    @get("/{key:path}/url")
    async def get_document_url(self, key: str, documents_storage: Storage) -> dict[str, str]:
        """Get a presigned URL for document download.

        Returns a URL valid for 15 minutes.
        """
        url = await documents_storage.url(key, expires_in=timedelta(minutes=15))
        return {"url": url, "expires_in": "15 minutes"}

    @delete("/{key:path}", status_code=HTTP_204_NO_CONTENT)
    async def delete_document(self, key: str, documents_storage: Storage) -> None:
        """Delete a document."""
        await documents_storage.delete(key)


# =============================================================================
# Health Check
# =============================================================================


@get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


# =============================================================================
# Application Setup
# =============================================================================

# Create storage backends
# In production, you'd use S3Storage, AzureStorage, etc.
images_storage = MemoryStorage()
documents_storage = MemoryStorage()

app = Litestar(
    route_handlers=[
        health_check,
        ImageController,
        DocumentController,
    ],
    plugins=[
        StoragePlugin(
            images=images_storage,
            documents=documents_storage,
        )
    ],
    exception_handlers={
        StorageFileNotFoundError: storage_not_found_handler,
        StorageFileExistsError: storage_exists_handler,
    },
)
