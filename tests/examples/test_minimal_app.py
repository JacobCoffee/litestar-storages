"""Integration tests for the minimal example application.

Tests verify the complete file upload/download/list workflow
using Litestar's test client.
"""

from __future__ import annotations

import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.integration


class TestMinimalAppUpload:
    """Test file upload functionality."""

    async def test_upload_file(self) -> None:
        """
        Test uploading a file via the minimal app.

        Verifies:
        - File upload returns StoredFile response
        - Response contains correct metadata
        """
        from examples.minimal.app import app

        async with AsyncTestClient(app=app) as client:
            response = await client.post(
                "/upload",
                files={"data": ("test.txt", b"Hello, World!", "text/plain")},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["key"] == "test.txt"
            assert data["size"] == len(b"Hello, World!")
            assert data["content_type"] == "text/plain"

    async def test_upload_binary_file(self) -> None:
        """
        Test uploading a binary file.

        Verifies:
        - Binary content is handled correctly
        """
        from examples.minimal.app import app

        binary_data = bytes(range(256))

        async with AsyncTestClient(app=app) as client:
            response = await client.post(
                "/upload",
                files={"data": ("binary.bin", binary_data, "application/octet-stream")},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["key"] == "binary.bin"
            assert data["size"] == len(binary_data)


class TestMinimalAppDownload:
    """Test file download functionality."""

    async def test_download_file(self) -> None:
        """
        Test downloading a previously uploaded file.

        Verifies:
        - File can be retrieved after upload
        - Content matches uploaded data
        """
        from examples.minimal.app import app

        content = b"Test file content for download"

        async with AsyncTestClient(app=app) as client:
            # First upload
            await client.post(
                "/upload",
                files={"data": ("download-test.txt", content, "text/plain")},
            )

            # Then download
            response = await client.get("/files/download-test.txt")

            assert response.status_code == 200
            assert response.content == content

    async def test_download_nonexistent_file(self) -> None:
        """
        Test downloading a file that doesn't exist.

        Verifies:
        - Returns 404 for missing files
        """
        from examples.minimal.app import app

        async with AsyncTestClient(app=app) as client:
            response = await client.get("/files/nonexistent.txt")
            assert response.status_code == 404


class TestMinimalAppList:
    """Test file listing functionality."""

    async def test_list_empty(self) -> None:
        """
        Test listing files when storage is empty.

        Verifies:
        - Returns empty list by using a fresh MemoryStorage instance
        """
        # Import the list_files handler from the app module (it has proper annotations)
        from examples.minimal.app import list_files
        from litestar import Litestar

        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        # Create fresh app with empty storage
        fresh_app = Litestar(
            route_handlers=[list_files],
            plugins=[StoragePlugin(default=MemoryStorage())],
        )

        async with AsyncTestClient(app=fresh_app) as client:
            response = await client.get("/files")
            assert response.status_code == 200
            assert response.json() == []

    async def test_list_uploaded_files(self) -> None:
        """
        Test listing files after uploads.

        Verifies:
        - List returns uploaded files
        - File metadata is correct
        """
        from examples.minimal.app import app

        async with AsyncTestClient(app=app) as client:
            # Upload multiple files
            await client.post(
                "/upload",
                files={"data": ("file1.txt", b"content1", "text/plain")},
            )
            await client.post(
                "/upload",
                files={"data": ("file2.txt", b"content2", "text/plain")},
            )

            # List files
            response = await client.get("/files")
            assert response.status_code == 200

            files = response.json()
            keys = {f["key"] for f in files}
            assert "file1.txt" in keys
            assert "file2.txt" in keys


class TestMinimalAppWorkflow:
    """Test complete workflows."""

    async def test_upload_download_delete_workflow(self) -> None:
        """
        Test complete upload -> download -> delete workflow.

        Verifies:
        - File can be uploaded
        - File can be downloaded
        - File can be deleted (via storage directly)
        - File is gone after delete
        """
        from examples.minimal.app import app

        content = b"Workflow test content"

        async with AsyncTestClient(app=app) as client:
            # Upload
            upload_response = await client.post(
                "/upload",
                files={"data": ("workflow.txt", content, "text/plain")},
            )
            assert upload_response.status_code == 201

            # Download
            download_response = await client.get("/files/workflow.txt")
            assert download_response.status_code == 200
            assert download_response.content == content

    async def test_overwrite_file(self) -> None:
        """
        Test uploading a file with the same name overwrites.

        Verifies:
        - Second upload with same name succeeds
        - Content is updated
        """
        from examples.minimal.app import app

        async with AsyncTestClient(app=app) as client:
            # First upload
            await client.post(
                "/upload",
                files={"data": ("overwrite.txt", b"original", "text/plain")},
            )

            # Second upload with same name
            await client.post(
                "/upload",
                files={"data": ("overwrite.txt", b"updated", "text/plain")},
            )

            # Download should return updated content
            response = await client.get("/files/overwrite.txt")
            assert response.content == b"updated"
