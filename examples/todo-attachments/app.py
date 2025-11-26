"""Litestar Todo application with file attachments.

This example demonstrates:
- Creating todos with file attachments
- Uploading files to storage
- Downloading attachments
- Deleting todos with cascade deletion of attachments
- File lifecycle management
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from litestar import Controller, Litestar, delete, get, post
from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.exceptions import NotFoundException
from litestar.params import Body
from litestar.response import Stream
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT

from litestar_storages import MemoryStorage, Storage
from litestar_storages.contrib import StoragePlugin

try:
    from .models import Attachment, Todo
except ImportError:
    # Support running as a standalone script
    from models import Attachment, Todo

logger = logging.getLogger(__name__)

# Global storage instance (singleton for the example)
_storage_instance: Storage | None = None


def provide_storage() -> Storage:
    """Provide storage instance for dependency injection."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = MemoryStorage()
    return _storage_instance


class TodoController(Controller):
    """Controller for todo CRUD operations."""

    path = "/todos"

    @get()
    async def list_todos(self) -> list[dict]:
        """List all todos."""
        return [todo.to_dict() for todo in Todo.get_all()]

    @post(status_code=HTTP_201_CREATED)
    async def create_todo(
        self,
        data: Annotated[dict, Body(media_type=RequestEncodingType.JSON)],
    ) -> dict:
        """Create a new todo."""
        todo = Todo.create(
            title=data["title"],
            description=data.get("description"),
        )
        return todo.to_dict()

    @get("/{todo_id:uuid}")
    async def get_todo(self, todo_id: UUID) -> dict:
        """Get a specific todo by ID."""
        todo = Todo.get(todo_id)
        if not todo:
            raise NotFoundException(detail=f"Todo {todo_id} not found")
        return todo.to_dict()

    @delete("/{todo_id:uuid}", status_code=HTTP_204_NO_CONTENT)
    async def delete_todo(self, todo_id: UUID, storage: Storage) -> None:
        """Delete a todo and all its attachments."""
        todo = Todo.get(todo_id)
        if not todo:
            raise NotFoundException(detail=f"Todo {todo_id} not found")

        # Delete all attachments from storage
        attachments = Attachment.get_by_todo(todo_id)
        for attachment in attachments:
            try:
                await storage.delete(attachment.storage_path)
            except Exception as e:
                logger.warning(f"Failed to delete file {attachment.storage_path}: {e}")

        # Delete attachment records
        Attachment.delete_by_todo(todo_id)

        # Delete todo
        Todo.delete(todo_id)


class AttachmentController(Controller):
    """Controller for attachment operations."""

    path = "/todos/{todo_id:uuid}/attachments"

    @get()
    async def list_attachments(self, todo_id: UUID) -> list[dict]:
        """List all attachments for a todo."""
        todo = Todo.get(todo_id)
        if not todo:
            raise NotFoundException(detail=f"Todo {todo_id} not found")

        attachments = Attachment.get_by_todo(todo_id)
        return [att.to_dict() for att in attachments]

    @post(status_code=HTTP_201_CREATED)
    async def upload_attachment(
        self,
        todo_id: UUID,
        storage: Storage,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> dict:
        """Upload a file attachment to a todo."""
        todo = Todo.get(todo_id)
        if not todo:
            raise NotFoundException(detail=f"Todo {todo_id} not found")

        # Generate storage path: todos/{todo_id}/{filename}
        storage_path = f"todos/{todo_id}/{data.filename}"

        # Read file content
        content = await data.read()

        # Upload file to storage
        stored_file = await storage.put(
            key=storage_path,
            data=content,
            content_type=data.content_type,
        )

        # Create attachment record
        attachment = Attachment.create(
            todo_id=todo_id,
            filename=data.filename,
            content_type=data.content_type or "application/octet-stream",
            size=stored_file.size,
            storage_path=storage_path,
        )

        return attachment.to_dict()

    @get("/{attachment_id:uuid}")
    async def download_attachment(
        self,
        todo_id: UUID,
        attachment_id: UUID,
        storage: Storage,
    ) -> Stream:
        """Download a file attachment."""
        attachment = Attachment.get(attachment_id)
        if not attachment or attachment.todo_id != todo_id:
            raise NotFoundException(detail=f"Attachment {attachment_id} not found")

        # Check if file exists in storage
        if not await storage.exists(attachment.storage_path):
            raise NotFoundException(detail=f"File {attachment.filename} not found in storage")

        # Stream file from storage
        file_stream = storage.get(attachment.storage_path)

        return Stream(
            content=file_stream,
            media_type=attachment.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{attachment.filename}"',
            },
        )

    @delete("/{attachment_id:uuid}", status_code=HTTP_204_NO_CONTENT)
    async def delete_attachment(
        self,
        todo_id: UUID,
        attachment_id: UUID,
        storage: Storage,
    ) -> None:
        """Delete a file attachment."""
        attachment = Attachment.get(attachment_id)
        if not attachment or attachment.todo_id != todo_id:
            raise NotFoundException(detail=f"Attachment {attachment_id} not found")

        # Delete from storage
        try:
            await storage.delete(attachment.storage_path)
        except Exception as e:
            logger.warning(f"Failed to delete file {attachment.storage_path}: {e}")

        # Delete attachment record
        Attachment.delete(attachment_id)


def create_app() -> Litestar:
    """Create and configure the Litestar application."""
    return Litestar(
        route_handlers=[TodoController, AttachmentController],
        plugins=[StoragePlugin()],
        dependencies={
            "storage": Provide(provide_storage, sync_to_thread=False),
        },
        debug=True,
    )


# Application instance for running with uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
