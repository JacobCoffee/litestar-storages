"""Minimal litestar-storages example.

Run with:
    uv run litestar --app examples.minimal.app:app run

Or from this directory:
    uv run litestar run
"""

from typing import Annotated

from litestar import Litestar, Response, get, post
from litestar.datastructures import UploadFile
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.response import Stream
from litestar.status_codes import HTTP_404_NOT_FOUND

from litestar_storages import Storage, StoredFile
from litestar_storages.backends.memory import MemoryStorage
from litestar_storages.contrib.plugin import StoragePlugin
from litestar_storages.exceptions import StorageFileNotFoundError


def not_found_handler(_: object, exc: StorageFileNotFoundError) -> Response:
    """Convert StorageFileNotFoundError to 404 response."""
    return Response(
        content={"detail": f"File not found: {exc.key}"},
        status_code=HTTP_404_NOT_FOUND,
    )


@post("/upload")
async def upload(
    data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    storage: Storage,
) -> StoredFile:
    """Upload a file."""
    content = await data.read()
    return await storage.put(
        key=data.filename or "unnamed",
        data=content,
        content_type=data.content_type,
    )


@get("/files/{key:path}")
async def download(key: str, storage: Storage) -> Stream:
    """Download a file."""
    # Strip leading slash from path parameter
    key = key.lstrip("/")
    info = await storage.info(key)
    return Stream(
        content=storage.get(key),
        media_type=info.content_type,
    )


@get("/files")
async def list_files(storage: Storage) -> list[StoredFile]:
    """List all files."""
    return [f async for f in storage.list()]


app = Litestar(
    route_handlers=[upload, download, list_files],
    plugins=[StoragePlugin(default=MemoryStorage())],
    exception_handlers={StorageFileNotFoundError: not_found_handler},
)
