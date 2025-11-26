"""Tests for the Todo attachments example application."""

from __future__ import annotations

import io
from uuid import UUID

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_404_NOT_FOUND,
)
from litestar.testing import AsyncTestClient

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from models import Attachment, Todo


@pytest.fixture
def app():
    """Create a test application instance."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create an async test client."""
    # Reset global storage instance before each test
    import app as app_module
    app_module._storage_instance = None

    async with AsyncTestClient(app=app) as client:
        yield client
    # Cleanup after each test
    Todo.clear_all()
    Attachment.clear_all()
    app_module._storage_instance = None


@pytest.fixture
async def sample_todo(client):
    """Create a sample todo for testing."""
    response = await client.post(
        "/todos",
        json={
            "title": "Test Todo",
            "description": "A test todo item",
        },
    )
    assert response.status_code == HTTP_201_CREATED
    return response.json()


class TestTodoEndpoints:
    """Tests for todo CRUD endpoints."""

    async def test_create_todo(self, client):
        """Test creating a new todo."""
        response = await client.post(
            "/todos",
            json={
                "title": "Buy groceries",
                "description": "Milk, eggs, bread",
            },
        )

        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        assert data["title"] == "Buy groceries"
        assert data["description"] == "Milk, eggs, bread"
        assert data["completed"] is False
        assert "id" in data
        assert "created_at" in data

        # Verify UUID format
        UUID(data["id"])

    async def test_create_todo_minimal(self, client):
        """Test creating a todo with only required fields."""
        response = await client.post(
            "/todos",
            json={"title": "Simple task"},
        )

        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        assert data["title"] == "Simple task"
        assert data["description"] is None

    async def test_list_todos_empty(self, client):
        """Test listing todos when none exist."""
        response = await client.get("/todos")

        assert response.status_code == HTTP_200_OK
        assert response.json() == []

    async def test_list_todos(self, client):
        """Test listing multiple todos."""
        # Create a few todos
        await client.post("/todos", json={"title": "Todo 1"})
        await client.post("/todos", json={"title": "Todo 2"})
        await client.post("/todos", json={"title": "Todo 3"})

        response = await client.get("/todos")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        assert all("id" in todo for todo in data)

    async def test_get_todo(self, client, sample_todo):
        """Test getting a specific todo."""
        todo_id = sample_todo["id"]
        response = await client.get(f"/todos/{todo_id}")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["id"] == todo_id
        assert data["title"] == sample_todo["title"]

    async def test_get_todo_not_found(self, client):
        """Test getting a non-existent todo."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/todos/{fake_id}")

        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_delete_todo(self, client, sample_todo):
        """Test deleting a todo."""
        todo_id = sample_todo["id"]
        response = await client.delete(f"/todos/{todo_id}")

        assert response.status_code == HTTP_204_NO_CONTENT

        # Verify todo is gone
        response = await client.get(f"/todos/{todo_id}")
        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_delete_todo_not_found(self, client):
        """Test deleting a non-existent todo."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(f"/todos/{fake_id}")

        assert response.status_code == HTTP_404_NOT_FOUND


class TestAttachmentEndpoints:
    """Tests for attachment upload/download/delete endpoints."""

    async def test_upload_attachment(self, client, sample_todo):
        """Test uploading a file attachment to a todo."""
        todo_id = sample_todo["id"]
        file_content = b"This is a test file content"
        file_name = "test.txt"

        response = await client.post(
            f"/todos/{todo_id}/attachments",
            files={"file": (file_name, io.BytesIO(file_content), "text/plain")},
        )

        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        assert data["filename"] == file_name
        assert data["content_type"] == "text/plain"
        assert data["size"] == len(file_content)
        assert data["todo_id"] == todo_id
        assert "id" in data
        assert "created_at" in data

    async def test_upload_attachment_to_nonexistent_todo(self, client):
        """Test uploading an attachment to a non-existent todo."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        file_content = b"test"

        response = await client.post(
            f"/todos/{fake_id}/attachments",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )

        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_list_attachments_empty(self, client, sample_todo):
        """Test listing attachments when none exist."""
        todo_id = sample_todo["id"]
        response = await client.get(f"/todos/{todo_id}/attachments")

        assert response.status_code == HTTP_200_OK
        assert response.json() == []

    async def test_list_attachments(self, client, sample_todo):
        """Test listing multiple attachments for a todo."""
        todo_id = sample_todo["id"]

        # Upload a few attachments
        for i in range(3):
            await client.post(
                f"/todos/{todo_id}/attachments",
                files={"file": (f"file{i}.txt", io.BytesIO(b"content"), "text/plain")},
            )

        response = await client.get(f"/todos/{todo_id}/attachments")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        assert all("id" in att for att in data)
        assert all(att["todo_id"] == todo_id for att in data)

    async def test_download_attachment(self, client, sample_todo):
        """Test downloading an attachment."""
        todo_id = sample_todo["id"]
        file_content = b"Download me!"
        file_name = "download.txt"

        # Upload file
        upload_response = await client.post(
            f"/todos/{todo_id}/attachments",
            files={"file": (file_name, io.BytesIO(file_content), "text/plain")},
        )
        attachment = upload_response.json()
        attachment_id = attachment["id"]

        # Download file
        download_response = await client.get(f"/todos/{todo_id}/attachments/{attachment_id}")

        assert download_response.status_code == HTTP_200_OK
        assert download_response.content == file_content
        assert download_response.headers["content-type"] == "text/plain; charset=utf-8"
        assert f'filename="{file_name}"' in download_response.headers.get("content-disposition", "")

    async def test_download_attachment_not_found(self, client, sample_todo):
        """Test downloading a non-existent attachment."""
        todo_id = sample_todo["id"]
        fake_id = "00000000-0000-0000-0000-000000000000"

        response = await client.get(f"/todos/{todo_id}/attachments/{fake_id}")

        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_download_attachment_wrong_todo(self, client, sample_todo):
        """Test downloading an attachment from the wrong todo."""
        # Create first todo with attachment
        todo_id_1 = sample_todo["id"]
        upload_response = await client.post(
            f"/todos/{todo_id_1}/attachments",
            files={"file": ("test.txt", io.BytesIO(b"content"), "text/plain")},
        )
        attachment_id = upload_response.json()["id"]

        # Create second todo
        response = await client.post("/todos", json={"title": "Another todo"})
        todo_id_2 = response.json()["id"]

        # Try to download attachment from wrong todo
        response = await client.get(f"/todos/{todo_id_2}/attachments/{attachment_id}")

        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_delete_attachment(self, client, sample_todo):
        """Test deleting an attachment."""
        todo_id = sample_todo["id"]

        # Upload file
        upload_response = await client.post(
            f"/todos/{todo_id}/attachments",
            files={"file": ("delete-me.txt", io.BytesIO(b"content"), "text/plain")},
        )
        attachment_id = upload_response.json()["id"]

        # Delete attachment
        delete_response = await client.delete(f"/todos/{todo_id}/attachments/{attachment_id}")

        assert delete_response.status_code == HTTP_204_NO_CONTENT

        # Verify attachment is gone
        download_response = await client.get(f"/todos/{todo_id}/attachments/{attachment_id}")
        assert download_response.status_code == HTTP_404_NOT_FOUND

    async def test_delete_attachment_not_found(self, client, sample_todo):
        """Test deleting a non-existent attachment."""
        todo_id = sample_todo["id"]
        fake_id = "00000000-0000-0000-0000-000000000000"

        response = await client.delete(f"/todos/{todo_id}/attachments/{fake_id}")

        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_cascade_delete_todo_with_attachments(self, client, sample_todo):
        """Test that deleting a todo also deletes all its attachments."""
        todo_id = sample_todo["id"]

        # Upload multiple attachments
        attachment_ids = []
        for i in range(3):
            response = await client.post(
                f"/todos/{todo_id}/attachments",
                files={"file": (f"file{i}.txt", io.BytesIO(b"content"), "text/plain")},
            )
            attachment_ids.append(response.json()["id"])

        # Verify attachments exist
        response = await client.get(f"/todos/{todo_id}/attachments")
        assert len(response.json()) == 3

        # Delete todo
        response = await client.delete(f"/todos/{todo_id}")
        assert response.status_code == HTTP_204_NO_CONTENT

        # Verify todo is gone
        response = await client.get(f"/todos/{todo_id}")
        assert response.status_code == HTTP_404_NOT_FOUND

        # Verify all attachments are gone from records
        assert len(Attachment.get_by_todo(UUID(todo_id))) == 0


class TestFileLifecycle:
    """Tests for complete file lifecycle management."""

    async def test_full_lifecycle(self, client):
        """Test the complete lifecycle: create todo, upload, download, delete."""
        # 1. Create todo
        todo_response = await client.post(
            "/todos",
            json={"title": "Lifecycle test", "description": "Testing file lifecycle"},
        )
        assert todo_response.status_code == HTTP_201_CREATED
        todo_id = todo_response.json()["id"]

        # 2. Upload attachment
        file_content = b"Lifecycle test content"
        upload_response = await client.post(
            f"/todos/{todo_id}/attachments",
            files={"file": ("lifecycle.txt", io.BytesIO(file_content), "text/plain")},
        )
        assert upload_response.status_code == HTTP_201_CREATED
        attachment_id = upload_response.json()["id"]

        # 3. Verify in list
        list_response = await client.get(f"/todos/{todo_id}/attachments")
        assert len(list_response.json()) == 1

        # 4. Download and verify content
        download_response = await client.get(f"/todos/{todo_id}/attachments/{attachment_id}")
        assert download_response.content == file_content

        # 5. Delete attachment
        delete_response = await client.delete(f"/todos/{todo_id}/attachments/{attachment_id}")
        assert delete_response.status_code == HTTP_204_NO_CONTENT

        # 6. Verify gone from list
        list_response = await client.get(f"/todos/{todo_id}/attachments")
        assert len(list_response.json()) == 0

        # 7. Delete todo
        delete_todo_response = await client.delete(f"/todos/{todo_id}")
        assert delete_todo_response.status_code == HTTP_204_NO_CONTENT

    async def test_multiple_attachments_same_todo(self, client, sample_todo):
        """Test uploading multiple different files to the same todo."""
        todo_id = sample_todo["id"]

        files = [
            ("doc.txt", b"Text document", "text/plain"),
            ("data.json", b'{"key": "value"}', "application/json"),
            ("image.png", b"\x89PNG\r\n\x1a\n", "image/png"),
        ]

        attachment_ids = []
        for filename, content, content_type in files:
            response = await client.post(
                f"/todos/{todo_id}/attachments",
                files={"file": (filename, io.BytesIO(content), content_type)},
            )
            assert response.status_code == HTTP_201_CREATED
            attachment_ids.append(response.json()["id"])

        # Verify all attachments are listed
        list_response = await client.get(f"/todos/{todo_id}/attachments")
        attachments = list_response.json()
        assert len(attachments) == 3

        # Verify each can be downloaded
        for attachment_id, (filename, content, _) in zip(attachment_ids, files):
            download_response = await client.get(f"/todos/{todo_id}/attachments/{attachment_id}")
            assert download_response.status_code == HTTP_200_OK
            assert download_response.content == content
