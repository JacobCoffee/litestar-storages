"""Integration tests for the full-featured example application.

Tests verify the complete file upload/download/list workflow
for both images and documents controllers using Litestar's test client.
"""

from __future__ import annotations

import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.integration


class TestFullFeaturedHealthCheck:
    """Test health check endpoint."""

    async def test_health_check(self) -> None:
        """
        Test health check endpoint.

        Verifies:
        - Returns 200 OK
        - Returns healthy status
        """
        from examples.full_featured.app import app

        async with AsyncTestClient(app=app) as client:
            response = await client.get("/health")

            assert response.status_code == 200
            assert response.json() == {"status": "healthy"}


class TestImageController:
    """Test image file operations."""

    async def test_upload_image(self) -> None:
        """
        Test uploading an image file.

        Verifies:
        - Image upload returns StoredFile response
        - Response contains correct metadata
        """
        from examples.full_featured.app import app

        # Create fake PNG header
        png_data = bytes([0x89, 0x50, 0x4E, 0x47]) + b"fake png content"

        async with AsyncTestClient(app=app) as client:
            response = await client.post(
                "/api/images/",
                files={"data": ("test.png", png_data, "image/png")},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["key"] == "uploads/test.png"
            assert data["content_type"] == "image/png"

    async def test_upload_non_image_rejected(self) -> None:
        """
        Test that non-image files are rejected.

        Verifies:
        - Non-image content type returns 400
        """
        from examples.full_featured.app import app

        async with AsyncTestClient(app=app) as client:
            response = await client.post(
                "/api/images/",
                files={"data": ("test.txt", b"text content", "text/plain")},
            )

            assert response.status_code == 400
            assert "Invalid content type" in response.json()["detail"]

    async def test_list_images(self) -> None:
        """
        Test listing uploaded images.

        Verifies:
        - Returns list of uploaded images
        """
        from examples.full_featured.app import app

        async with AsyncTestClient(app=app) as client:
            # Upload an image first
            await client.post(
                "/api/images/",
                files={"data": ("list-test.png", b"png content", "image/png")},
            )

            # List images
            response = await client.get("/api/images/")
            assert response.status_code == 200
            assert isinstance(response.json(), list)

    async def test_get_image_info(self) -> None:
        """
        Test getting image metadata.

        Verifies:
        - Returns image metadata
        """
        from examples.full_featured.app import app

        async with AsyncTestClient(app=app) as client:
            # Upload image
            await client.post(
                "/api/images/",
                files={"data": ("info-test.jpg", b"jpg content", "image/jpeg")},
            )

            # Get info
            response = await client.get("/api/images/uploads/info-test.jpg")
            assert response.status_code == 200
            data = response.json()
            assert data["key"] == "uploads/info-test.jpg"

    async def test_download_image(self) -> None:
        """
        Test downloading an image.

        Verifies:
        - Image can be downloaded
        - Content matches uploaded data
        """
        from examples.full_featured.app import app

        content = b"downloadable image content"

        async with AsyncTestClient(app=app) as client:
            # Upload
            await client.post(
                "/api/images/",
                files={"data": ("download.gif", content, "image/gif")},
            )

            # Download
            response = await client.get("/api/images/uploads/download.gif/download")
            assert response.status_code == 200
            assert response.content == content

    async def test_delete_image(self) -> None:
        """
        Test deleting an image.

        Verifies:
        - Delete returns 204
        - Image is no longer accessible
        """
        from examples.full_featured.app import app

        async with AsyncTestClient(app=app) as client:
            # Upload
            await client.post(
                "/api/images/",
                files={"data": ("delete-me.png", b"to delete", "image/png")},
            )

            # Delete
            response = await client.delete("/api/images/uploads/delete-me.png")
            assert response.status_code == 204

            # Verify deleted
            response = await client.get("/api/images/uploads/delete-me.png")
            assert response.status_code == 404


class TestDocumentController:
    """Test document file operations."""

    async def test_upload_document(self) -> None:
        """
        Test uploading a document file.

        Verifies:
        - Document upload returns StoredFile response
        """
        from examples.full_featured.app import app

        async with AsyncTestClient(app=app) as client:
            response = await client.post(
                "/api/documents/",
                files={"data": ("test.pdf", b"fake pdf content", "application/pdf")},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["key"] == "docs/test.pdf"

    async def test_list_documents(self) -> None:
        """
        Test listing uploaded documents.

        Verifies:
        - Returns list of uploaded documents
        """
        from examples.full_featured.app import app

        async with AsyncTestClient(app=app) as client:
            # Upload a document first
            await client.post(
                "/api/documents/",
                files={"data": ("doc.docx", b"docx content", "application/msword")},
            )

            # List documents
            response = await client.get("/api/documents/")
            assert response.status_code == 200
            assert isinstance(response.json(), list)

    async def test_get_document_info(self) -> None:
        """
        Test getting document metadata.

        Verifies:
        - Returns document metadata
        """
        from examples.full_featured.app import app

        async with AsyncTestClient(app=app) as client:
            # Upload document
            await client.post(
                "/api/documents/",
                files={"data": ("info.xlsx", b"xlsx content", "application/vnd.ms-excel")},
            )

            # Get info
            response = await client.get("/api/documents/docs/info.xlsx")
            assert response.status_code == 200
            data = response.json()
            assert data["key"] == "docs/info.xlsx"

    async def test_download_document(self) -> None:
        """
        Test downloading a document.

        Verifies:
        - Document can be downloaded
        - Content-Disposition header is set for attachment
        """
        from examples.full_featured.app import app

        content = b"downloadable document content"

        async with AsyncTestClient(app=app) as client:
            # Upload
            await client.post(
                "/api/documents/",
                files={"data": ("report.csv", content, "text/csv")},
            )

            # Download
            response = await client.get("/api/documents/docs/report.csv/download")
            assert response.status_code == 200
            assert response.content == content
            assert "attachment" in response.headers.get("content-disposition", "")

    async def test_get_document_url(self) -> None:
        """
        Test getting presigned URL for document.

        Verifies:
        - Returns URL and expiry info
        """
        from examples.full_featured.app import app

        async with AsyncTestClient(app=app) as client:
            # Upload
            await client.post(
                "/api/documents/",
                files={"data": ("shared.txt", b"shared content", "text/plain")},
            )

            # Get URL
            response = await client.get("/api/documents/docs/shared.txt/url")
            assert response.status_code == 200
            data = response.json()
            assert "url" in data
            assert "expires_in" in data

    async def test_delete_document(self) -> None:
        """
        Test deleting a document.

        Verifies:
        - Delete returns 204
        """
        from examples.full_featured.app import app

        async with AsyncTestClient(app=app) as client:
            # Upload
            await client.post(
                "/api/documents/",
                files={"data": ("to-delete.pdf", b"delete me", "application/pdf")},
            )

            # Delete
            response = await client.delete("/api/documents/docs/to-delete.pdf")
            assert response.status_code == 204


class TestExceptionHandling:
    """Test custom exception handlers."""

    async def test_file_not_found_handler(self) -> None:
        """
        Test that StorageFileNotFoundError returns 404.

        Verifies:
        - Custom exception handler is invoked
        - Returns proper error response
        """
        from examples.full_featured.app import app

        async with AsyncTestClient(app=app) as client:
            response = await client.get("/api/images/nonexistent.png")

            assert response.status_code == 404
            assert "File not found" in response.json()["detail"]


class TestMultiStorageIsolation:
    """Test that images and documents storages are isolated."""

    async def test_storage_isolation(self) -> None:
        """
        Test that uploads to images don't appear in documents.

        Verifies:
        - Files uploaded to images_storage are not in documents_storage
        - Files uploaded to documents_storage are not in images_storage
        """
        from examples.full_featured.app import app

        async with AsyncTestClient(app=app) as client:
            # Upload to images
            await client.post(
                "/api/images/",
                files={"data": ("isolated.png", b"image", "image/png")},
            )

            # Upload to documents
            await client.post(
                "/api/documents/",
                files={"data": ("isolated.pdf", b"doc", "application/pdf")},
            )

            # Check images list only has image
            images_response = await client.get("/api/images/")
            images = images_response.json()
            image_keys = [i["key"] for i in images]
            assert any("isolated.png" in k for k in image_keys)
            assert not any("isolated.pdf" in k for k in image_keys)

            # Check documents list only has document
            docs_response = await client.get("/api/documents/")
            docs = docs_response.json()
            doc_keys = [d["key"] for d in docs]
            assert any("isolated.pdf" in k for k in doc_keys)
            assert not any("isolated.png" in k for k in doc_keys)
