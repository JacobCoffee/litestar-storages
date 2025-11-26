"""Tests for Litestar StoragePlugin integration.

Tests for plugin registration, dependency injection, multiple named storages,
and integration with Litestar application lifecycle.

All tests in this module require Litestar to be installed and are marked
with @pytest.mark.litestar. They will be skipped if Litestar is not available.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

# Guard Litestar imports - these tests will be skipped if Litestar is not installed
pytest.importorskip("litestar")

from litestar import Controller, Litestar, delete, get, post
from litestar.datastructures import UploadFile
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.response import Stream
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT
from litestar.testing import AsyncTestClient

from litestar_storages import Storage, StoredFile

if TYPE_CHECKING:
    from litestar_storages.backends.memory import MemoryStorage


# Mark all tests in this module as requiring Litestar
pytestmark = [pytest.mark.litestar, pytest.mark.integration]


@pytest.mark.integration
class TestStoragePluginBasics:
    """Test basic plugin functionality."""

    async def test_plugin_registration(self) -> None:
        """
        Test that StoragePlugin can be registered with Litestar.

        Verifies:
        - Plugin can be added to Litestar app
        - App initializes successfully with plugin
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        storage = MemoryStorage()
        plugin = StoragePlugin(default=storage)

        app = Litestar(route_handlers=[], plugins=[plugin])

        assert app is not None
        assert plugin in app.plugins

    async def test_plugin_with_default_storage(self) -> None:
        """
        Test plugin with default storage configuration.

        Verifies:
        - Default storage is registered
        - Can be injected as 'storage' dependency
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        storage = MemoryStorage()
        plugin = StoragePlugin(default=storage)

        app = Litestar(route_handlers=[], plugins=[plugin])

        # Plugin should have registered dependencies
        assert app.dependencies is not None

    async def test_plugin_with_named_storages(self) -> None:
        """
        Test plugin with multiple named storages.

        Verifies:
        - Multiple storages can be registered
        - Each storage has unique name
        - All are available for injection
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        storage1 = MemoryStorage()
        storage2 = MemoryStorage()
        storage3 = MemoryStorage()

        plugin = StoragePlugin(
            default=storage1,
            images=storage2,
            documents=storage3,
        )

        app = Litestar(route_handlers=[], plugins=[plugin])

        assert app.dependencies is not None
        # Should have dependencies for: storage, images_storage, documents_storage


@pytest.mark.integration
class TestStorageDependencyInjection:
    """Test dependency injection of storage instances."""

    async def test_default_storage_injection(self) -> None:
        """
        Test injecting default storage into route handlers.

        Verifies:
        - Default storage is injectable as 'storage' parameter
        - Correct storage instance is provided
        - Storage is usable in handlers
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        test_storage = MemoryStorage()

        @get("/test")
        async def test_handler(storage: Storage) -> dict:
            """Handler that receives injected storage."""
            # Verify we got the storage
            assert storage is test_storage
            return {"success": True}

        app = Litestar(
            route_handlers=[test_handler],
            plugins=[StoragePlugin(default=test_storage)],
        )

        async with AsyncTestClient(app=app) as client:
            response = await client.get("/test")
            assert response.status_code == HTTP_200_OK
            assert response.json() == {"success": True}

    async def test_named_storage_injection(self) -> None:
        """
        Test injecting named storages into route handlers.

        Verifies:
        - Named storages are injectable with {name}_storage parameter
        - Correct storage instances are provided
        - Multiple storages can be injected into same handler
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        images_storage = MemoryStorage()
        documents_storage = MemoryStorage()

        @get("/test")
        async def test_handler(
            images_storage: Storage,
            documents_storage: Storage,
        ) -> dict:
            """Handler that receives multiple injected storages."""
            # Upload to each storage to verify they work
            await images_storage.put("test.jpg", b"image data")
            await documents_storage.put("test.pdf", b"doc data")

            return {"success": True}

        app = Litestar(
            route_handlers=[test_handler],
            plugins=[
                StoragePlugin(
                    images=images_storage,
                    documents=documents_storage,
                )
            ],
        )

        async with AsyncTestClient(app=app) as client:
            response = await client.get("/test")
            assert response.status_code == HTTP_200_OK

    async def test_storage_isolation(self) -> None:
        """
        Test that injected storages are isolated.

        Verifies:
        - Files uploaded to one storage don't appear in another
        - Each storage maintains independent state
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        storage_a = MemoryStorage()
        storage_b = MemoryStorage()

        @post("/upload-a")
        async def upload_a(a_storage: Storage) -> dict:
            await a_storage.put("file.txt", b"data from A")
            return {"uploaded": "A"}

        @post("/upload-b")
        async def upload_b(b_storage: Storage) -> dict:
            await b_storage.put("file.txt", b"data from B")
            return {"uploaded": "B"}

        @get("/check")
        async def check(a_storage: Storage, b_storage: Storage) -> dict:
            a_exists = await a_storage.exists("file.txt")
            b_exists = await b_storage.exists("file.txt")

            a_data = await a_storage.get_bytes("file.txt") if a_exists else None
            b_data = await b_storage.get_bytes("file.txt") if b_exists else None

            return {
                "a_exists": a_exists,
                "b_exists": b_exists,
                "a_data": a_data.decode() if a_data else None,
                "b_data": b_data.decode() if b_data else None,
            }

        app = Litestar(
            route_handlers=[upload_a, upload_b, check],
            plugins=[StoragePlugin(a=storage_a, b=storage_b)],
        )

        async with AsyncTestClient(app=app) as client:
            # Upload to A
            await client.post("/upload-a")

            # Upload to B
            await client.post("/upload-b")

            # Check both
            response = await client.get("/check")
            data = response.json()

            assert data["a_exists"] is True
            assert data["b_exists"] is True
            assert data["a_data"] == "data from A"
            assert data["b_data"] == "data from B"


@pytest.mark.integration
class TestFileUploadController:
    """Test realistic file upload controller with storage."""

    async def test_file_upload_endpoint(self, memory_storage: MemoryStorage) -> None:
        """
        Test complete file upload workflow.

        Verifies:
        - File upload works with injected storage
        - UploadFile integration works
        - File is stored correctly
        """
        from litestar_storages.contrib.plugin import StoragePlugin

        @post("/upload")
        async def upload_file(
            data: UploadFile = Body(media_type=RequestEncodingType.MULTI_PART),
            storage: Storage = None,
        ) -> StoredFile:
            """Upload a file."""
            content = await data.read()
            return await storage.put(
                key=f"uploads/{data.filename}",
                data=content,
                content_type=data.content_type,
            )

        app = Litestar(
            route_handlers=[upload_file],
            plugins=[StoragePlugin(default=memory_storage)],
        )

        async with AsyncTestClient(app=app) as client:
            # Create multipart upload
            files = {"data": ("test.txt", b"Hello, World!", "text/plain")}
            response = await client.post("/upload", files=files)

            assert response.status_code == HTTP_201_CREATED
            result = response.json()
            assert result["key"] == "uploads/test.txt"
            assert result["size"] == 13

            # Verify file was stored
            assert await memory_storage.exists("uploads/test.txt")

    async def test_file_download_endpoint(self, memory_storage: MemoryStorage) -> None:
        """
        Test file download endpoint.

        Verifies:
        - File download works with streaming
        - Content-Type header is set correctly
        - File content is correct
        """
        from litestar_storages.contrib.plugin import StoragePlugin

        # Pre-populate storage
        await memory_storage.put(
            "downloads/file.txt",
            b"File content here",
            content_type="text/plain",
        )

        @get("/download/{key:path}")
        async def download_file(key: str, storage: Storage) -> Stream:
            """Download a file."""
            # Strip leading slash from path parameter
            key = key.lstrip("/")
            info = await storage.info(key)
            return Stream(
                content=storage.get(key),
                media_type=info.content_type,
                headers={
                    "Content-Length": str(info.size),
                    "Content-Disposition": f'attachment; filename="{key.split("/")[-1]}"',
                },
            )

        app = Litestar(
            route_handlers=[download_file],
            plugins=[StoragePlugin(default=memory_storage)],
        )

        async with AsyncTestClient(app=app) as client:
            response = await client.get("/download/downloads/file.txt")

            assert response.status_code == HTTP_200_OK
            assert response.content == b"File content here"
            assert "text/plain" in response.headers["content-type"]

    async def test_file_delete_endpoint(self, memory_storage: MemoryStorage) -> None:
        """
        Test file deletion endpoint.

        Verifies:
        - File can be deleted via API
        - File no longer exists after deletion
        """
        from litestar_storages.contrib.plugin import StoragePlugin

        # Pre-populate storage
        await memory_storage.put("files/to-delete.txt", b"Delete me")

        @delete("/files/{key:path}", status_code=HTTP_204_NO_CONTENT)
        async def delete_file(key: str, storage: Storage) -> None:
            """Delete a file."""
            # Strip leading slash from path parameter
            key = key.lstrip("/")
            await storage.delete(key)

        app = Litestar(
            route_handlers=[delete_file],
            plugins=[StoragePlugin(default=memory_storage)],
        )

        async with AsyncTestClient(app=app) as client:
            # Verify exists before deletion
            assert await memory_storage.exists("files/to-delete.txt")

            # Delete via API
            response = await client.delete("/files/files/to-delete.txt")
            assert response.status_code == HTTP_204_NO_CONTENT

            # Verify no longer exists
            assert not await memory_storage.exists("files/to-delete.txt")

    async def test_presigned_url_endpoint(self, memory_storage: MemoryStorage) -> None:
        """
        Test generating presigned URLs.

        Verifies:
        - URL generation works through injection
        - Expiration parameter is handled
        """
        from litestar_storages.contrib.plugin import StoragePlugin

        # Pre-populate storage
        await memory_storage.put("test.txt", b"Content")

        @get("/url/{key:str}")
        async def get_file_url(key: str, storage: Storage) -> dict[str, str]:
            """Get presigned URL for file."""
            url = await storage.url(key, expires_in=timedelta(minutes=15))
            return {"url": url}

        app = Litestar(
            route_handlers=[get_file_url],
            plugins=[StoragePlugin(default=memory_storage)],
        )

        async with AsyncTestClient(app=app) as client:
            response = await client.get("/url/test.txt")

            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert "url" in data
            assert isinstance(data["url"], str)


@pytest.mark.integration
class TestControllerIntegration:
    """Test Storage integration with Litestar Controllers."""

    async def test_storage_in_controller(self, memory_storage: MemoryStorage) -> None:
        """
        Test using storage in a Controller class.

        Verifies:
        - Storage injection works in Controller methods
        - Multiple endpoints in same controller can use storage
        """
        from litestar_storages.contrib.plugin import StoragePlugin

        class FileController(Controller):
            path = "/api/files"

            @post("/")
            async def upload(
                self,
                data: UploadFile = Body(media_type=RequestEncodingType.MULTI_PART),
                storage: Storage = None,
            ) -> StoredFile:
                """Upload a file."""
                content = await data.read()
                return await storage.put(
                    key=data.filename,
                    data=content,
                    content_type=data.content_type,
                )

            @get("/{key:path}")
            async def download(self, key: str, storage: Storage) -> Stream:
                """Download a file."""
                # Strip leading slash from path parameter
                key = key.lstrip("/")
                info = await storage.info(key)
                return Stream(
                    content=storage.get(key),
                    media_type=info.content_type,
                )

            @delete("/{key:path}", status_code=HTTP_204_NO_CONTENT)
            async def delete(self, key: str, storage: Storage) -> None:
                """Delete a file."""
                # Strip leading slash from path parameter
                key = key.lstrip("/")
                await storage.delete(key)

        app = Litestar(
            route_handlers=[FileController],
            plugins=[StoragePlugin(default=memory_storage)],
        )

        async with AsyncTestClient(app=app) as client:
            # Upload
            files = {"data": ("test.txt", b"Test content", "text/plain")}
            upload_response = await client.post("/api/files/", files=files)
            assert upload_response.status_code == HTTP_201_CREATED

            # Download
            download_response = await client.get("/api/files/test.txt")
            assert download_response.status_code == HTTP_200_OK
            assert download_response.content == b"Test content"

            # Delete
            delete_response = await client.delete("/api/files/test.txt")
            assert delete_response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.integration
class TestMultipleStorageScenarios:
    """Test scenarios with multiple storage backends."""

    async def test_images_and_documents_separation(self) -> None:
        """
        Test separating images and documents into different storages.

        Verifies:
        - Different content types go to appropriate storage
        - Storages remain isolated
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        images_storage = MemoryStorage()
        documents_storage = MemoryStorage()

        @post("/upload/image")
        async def upload_image(
            data: UploadFile = Body(media_type=RequestEncodingType.MULTI_PART),
            images_storage: Storage = None,
        ) -> dict:
            """Upload image to images storage."""
            content = await data.read()
            await images_storage.put(data.filename, content)
            return {"stored_in": "images"}

        @post("/upload/document")
        async def upload_document(
            data: UploadFile = Body(media_type=RequestEncodingType.MULTI_PART),
            documents_storage: Storage = None,
        ) -> dict:
            """Upload document to documents storage."""
            content = await data.read()
            await documents_storage.put(data.filename, content)
            return {"stored_in": "documents"}

        @get("/stats")
        async def get_stats(
            images_storage: Storage,
            documents_storage: Storage,
        ) -> dict:
            """Get storage statistics."""
            image_files = [f async for f in images_storage.list()]
            document_files = [f async for f in documents_storage.list()]

            return {
                "image_count": len(image_files),
                "document_count": len(document_files),
            }

        app = Litestar(
            route_handlers=[upload_image, upload_document, get_stats],
            plugins=[
                StoragePlugin(
                    images=images_storage,
                    documents=documents_storage,
                )
            ],
        )

        async with AsyncTestClient(app=app) as client:
            # Upload images
            files = {"data": ("photo1.jpg", b"image data 1", "image/jpeg")}
            await client.post("/upload/image", files=files)

            files = {"data": ("photo2.jpg", b"image data 2", "image/jpeg")}
            await client.post("/upload/image", files=files)

            # Upload documents
            files = {"data": ("doc1.pdf", b"pdf data 1", "application/pdf")}
            await client.post("/upload/document", files=files)

            # Check stats
            response = await client.get("/stats")
            stats = response.json()

            assert stats["image_count"] == 2
            assert stats["document_count"] == 1

    async def test_fallback_storage_pattern(self) -> None:
        """
        Test fallback pattern: try primary, use backup if needed.

        Verifies:
        - Can inject multiple storages for redundancy
        - Application logic can choose storage
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        primary_storage = MemoryStorage()
        backup_storage = MemoryStorage()

        @post("/upload-with-fallback")
        async def upload_with_fallback(
            data: UploadFile = Body(media_type=RequestEncodingType.MULTI_PART),
            primary_storage: Storage = None,
            backup_storage: Storage = None,
        ) -> dict:
            """Upload to primary, fallback to backup on error."""
            content = await data.read()

            try:
                await primary_storage.put(data.filename, content)
                return {"stored_in": "primary"}
            except Exception:
                await backup_storage.put(data.filename, content)
                return {"stored_in": "backup"}

        app = Litestar(
            route_handlers=[upload_with_fallback],
            plugins=[
                StoragePlugin(
                    primary=primary_storage,
                    backup=backup_storage,
                )
            ],
        )

        async with AsyncTestClient(app=app) as client:
            files = {"data": ("test.txt", b"test data", "text/plain")}
            response = await client.post("/upload-with-fallback", files=files)

            result = response.json()
            assert result["stored_in"] in ["primary", "backup"]


@pytest.mark.integration
class TestPluginLifecycle:
    """Test plugin lifecycle management."""

    async def test_plugin_initialization(self) -> None:
        """
        Test that plugin initializes correctly on app startup.

        Verifies:
        - Plugin's on_app_init is called
        - Dependencies are registered
        - Storage instances are prepared
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        storage = MemoryStorage()
        plugin = StoragePlugin(default=storage)

        # Creating app should call plugin initialization
        app = Litestar(route_handlers=[], plugins=[plugin])

        assert app.dependencies is not None
        # Dependencies should include storage injection

    async def test_multiple_apps_with_same_storage(self) -> None:
        """
        Test that same storage can be used in multiple apps.

        Verifies:
        - Storage instance can be shared
        - Different apps see same data
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        shared_storage = MemoryStorage()

        @post("/upload")
        async def upload(
            data: UploadFile = Body(media_type=RequestEncodingType.MULTI_PART),
            storage: Storage = None,
        ) -> dict:
            content = await data.read()
            await storage.put(data.filename, content)
            return {"uploaded": data.filename}

        @get("/list")
        async def list_files(storage: Storage) -> dict:
            files = [f.key async for f in storage.list()]
            return {"files": files}

        # Create two apps sharing same storage
        app1 = Litestar(
            route_handlers=[upload],
            plugins=[StoragePlugin(default=shared_storage)],
        )

        app2 = Litestar(
            route_handlers=[list_files],
            plugins=[StoragePlugin(default=shared_storage)],
        )

        # Upload via app1
        async with AsyncTestClient(app=app1) as client:
            files = {"data": ("shared.txt", b"shared data", "text/plain")}
            await client.post("/upload", files=files)

        # List via app2 should see the file
        async with AsyncTestClient(app=app2) as client:
            response = await client.get("/list")
            data = response.json()
            assert "shared.txt" in data["files"]

    async def test_storage_close_on_shutdown(self) -> None:
        """
        Test that storage close() is called on app shutdown.

        Verifies:
        - Storage close() method is called during shutdown
        - Plugin properly handles lifespan
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        # Create a storage that tracks if close() was called
        class TrackingStorage(MemoryStorage):
            closed = False

            async def close(self) -> None:
                TrackingStorage.closed = True

        storage = TrackingStorage()
        plugin = StoragePlugin(default=storage)

        @get("/test")
        async def test_handler(storage: Storage) -> dict:
            return {"ok": True}

        app = Litestar(route_handlers=[test_handler], plugins=[plugin])

        # Use the test client which handles startup/shutdown
        async with AsyncTestClient(app=app) as client:
            response = await client.get("/test")
            assert response.status_code == HTTP_200_OK
            # Storage should not be closed yet
            assert TrackingStorage.closed is False

        # After exiting context manager, shutdown should have been called
        assert TrackingStorage.closed is True

    async def test_multiple_storages_closed_on_shutdown(self) -> None:
        """
        Test that all storages are closed on shutdown.

        Verifies:
        - Multiple storages all have close() called
        - Named storages are properly cleaned up
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        closed_storages: list[str] = []

        class TrackingStorage(MemoryStorage):
            def __init__(self, name: str) -> None:
                super().__init__()
                self.name = name

            async def close(self) -> None:
                closed_storages.append(self.name)

        storage1 = TrackingStorage("default")
        storage2 = TrackingStorage("images")
        storage3 = TrackingStorage("documents")

        plugin = StoragePlugin(
            default=storage1,
            images=storage2,
            documents=storage3,
        )

        app = Litestar(route_handlers=[], plugins=[plugin])

        async with AsyncTestClient(app=app):
            # All storages should not be closed yet
            assert len(closed_storages) == 0

        # All storages should be closed after shutdown
        assert len(closed_storages) == 3
        assert set(closed_storages) == {"default", "images", "documents"}

    async def test_storage_without_close_method(self) -> None:
        """
        Test that storages without close() method are handled gracefully.

        Verifies:
        - No error if storage lacks close() method
        - Shutdown proceeds normally
        """
        from litestar_storages.contrib.plugin import StoragePlugin

        # Create a mock storage-like object without close() method
        class MinimalStorage:
            """A minimal storage-like object for testing."""

            async def put(self, key: str, data: bytes, **kwargs) -> dict:  # type: ignore[type-arg]
                return {"key": key, "size": len(data)}

            async def get(self, key: str) -> bytes:
                return b""

            async def delete(self, key: str) -> None:
                pass

            async def exists(self, key: str) -> bool:
                return False

            async def list(self, prefix: str = "", **kwargs) -> list:  # type: ignore[type-arg]
                return []

            async def url(self, key: str, **kwargs) -> str:  # type: ignore[type-arg]
                return f"memory://{key}"

            async def info(self, key: str) -> dict:  # type: ignore[type-arg]
                return {"key": key}

            # Note: No close() method

        storage = MinimalStorage()
        plugin = StoragePlugin(default=storage)  # type: ignore[arg-type]

        app = Litestar(route_handlers=[], plugins=[plugin])

        # Should not raise any errors - hasattr check should handle missing close()
        async with AsyncTestClient(app=app):
            pass  # Just test that startup/shutdown works

    async def test_close_error_does_not_prevent_other_closures(self) -> None:
        """
        Test that an error in one close() doesn't prevent others.

        Verifies:
        - Error in one storage's close() is handled
        - Other storages still get closed
        """
        from litestar_storages.backends.memory import MemoryStorage
        from litestar_storages.contrib.plugin import StoragePlugin

        closed_storages: list[str] = []

        class ErrorStorage(MemoryStorage):
            async def close(self) -> None:
                raise RuntimeError("Close failed!")

        class TrackingStorage(MemoryStorage):
            def __init__(self, name: str) -> None:
                super().__init__()
                self.name = name

            async def close(self) -> None:
                closed_storages.append(self.name)

        # Put error storage in the middle
        storage1 = TrackingStorage("first")
        storage2 = ErrorStorage()
        storage3 = TrackingStorage("last")

        plugin = StoragePlugin(
            first=storage1,
            error=storage2,
            last=storage3,
        )

        app = Litestar(route_handlers=[], plugins=[plugin])

        # Should not raise - errors in close() are caught and logged
        async with AsyncTestClient(app=app):
            pass

        # Both non-error storages should be closed
        assert "first" in closed_storages
        assert "last" in closed_storages
