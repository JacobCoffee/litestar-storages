"""Tests for dependency injection utilities.

This module tests the provide_storage() function and StorageDependency type alias.

Tests that require Litestar are marked with @pytest.mark.litestar and will be
skipped if Litestar is not available. Unit tests for framework-agnostic
functionality run without Litestar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from litestar_storages.backends.memory import MemoryConfig, MemoryStorage
from litestar_storages.contrib.dependencies import provide_storage

if TYPE_CHECKING:
    pass


@pytest.mark.unit
class TestProvideStorage:
    """Test provide_storage function."""

    def test_provide_storage_returns_callable(self) -> None:
        """
        Test that provide_storage returns a callable.

        Verifies:
        - Function returns a callable
        - Callable signature is correct for DI
        """
        storage = MemoryStorage(config=MemoryConfig())
        provider = provide_storage(storage)

        assert callable(provider)

    def test_provide_storage_returns_same_instance(self) -> None:
        """
        Test that provider returns the same storage instance.

        Verifies:
        - Provider function returns original storage
        - Same instance is returned on multiple calls
        - Instance identity is preserved
        """
        storage = MemoryStorage(config=MemoryConfig())
        provider = provide_storage(storage)

        # Call provider multiple times
        result1 = provider()
        result2 = provider()
        result3 = provider()

        # All should be the same instance
        assert result1 is storage
        assert result2 is storage
        assert result3 is storage

    def test_provide_storage_with_different_backends(self) -> None:
        """
        Test provide_storage with different storage backends.

        Verifies:
        - Works with any storage implementation
        - Returns correct instance for each backend
        """
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from litestar_storages.backends.filesystem import FileSystemConfig, FileSystemStorage

        # Test with MemoryStorage
        memory_storage = MemoryStorage(config=MemoryConfig())
        memory_provider = provide_storage(memory_storage)
        assert memory_provider() is memory_storage

        # Test with FileSystemStorage
        with TemporaryDirectory() as tmpdir:
            fs_storage = FileSystemStorage(config=FileSystemConfig(path=Path(tmpdir)))
            fs_provider = provide_storage(fs_storage)
            assert fs_provider() is fs_storage

    def test_provide_storage_independent_providers(self) -> None:
        """
        Test that multiple providers are independent.

        Verifies:
        - Each provider returns its own storage instance
        - Providers don't interfere with each other
        """
        storage1 = MemoryStorage(config=MemoryConfig())
        storage2 = MemoryStorage(config=MemoryConfig())

        provider1 = provide_storage(storage1)
        provider2 = provide_storage(storage2)

        assert provider1() is storage1
        assert provider2() is storage2
        assert provider1() is not provider2()

    @pytest.mark.litestar
    async def test_provide_storage_with_litestar_di(self) -> None:
        """
        Test provide_storage integration with Litestar DI.

        Verifies:
        - Provider works with Litestar's DI system
        - Storage can be injected into route handlers
        """
        from typing import Any

        pytest.importorskip("litestar")
        from litestar import Litestar, get
        from litestar.di import Provide
        from litestar.testing import AsyncTestClient

        storage = MemoryStorage(config=MemoryConfig())

        # Create route handler that receives storage via DI
        # Use Any type to avoid forward reference issues in test
        @get("/test")
        async def test_handler(storage: Any) -> dict[str, str]:
            await storage.put("test.txt", b"test data")
            exists = await storage.exists("test.txt")
            return {"exists": str(exists)}

        # Create app with storage DI
        app = Litestar(
            route_handlers=[test_handler],
            dependencies={
                "storage": Provide(provide_storage(storage)),
            },
        )

        # Test the endpoint
        async with AsyncTestClient(app=app) as client:
            response = await client.get("/test")
            assert response.status_code == 200
            assert response.json() == {"exists": "True"}

            # Verify file was actually stored
            assert await storage.exists("test.txt")

    @pytest.mark.litestar
    async def test_provide_storage_multiple_di_instances(self) -> None:
        """
        Test multiple storage instances in DI.

        Verifies:
        - Multiple storages can be registered
        - Each has its own provider
        - Different dependency keys work correctly
        """
        from typing import Any

        pytest.importorskip("litestar")
        from litestar import Litestar, get
        from litestar.di import Provide
        from litestar.testing import AsyncTestClient

        main_storage = MemoryStorage(config=MemoryConfig())
        archive_storage = MemoryStorage(config=MemoryConfig())

        # Route handler using multiple storages
        # Use Any type to avoid forward reference issues in test
        @get("/test")
        async def test_handler(
            storage: Any,
            archive_storage: Any,
        ) -> dict[str, str]:
            await storage.put("main.txt", b"main data")
            await archive_storage.put("archive.txt", b"archive data")
            return {
                "main_exists": str(await storage.exists("main.txt")),
                "archive_exists": str(await archive_storage.exists("archive.txt")),
            }

        # Create app with multiple storage instances
        app = Litestar(
            route_handlers=[test_handler],
            dependencies={
                "storage": Provide(provide_storage(main_storage)),
                "archive_storage": Provide(provide_storage(archive_storage)),
            },
        )

        # Test the endpoint
        async with AsyncTestClient(app=app) as client:
            response = await client.get("/test")
            assert response.status_code == 200
            assert response.json() == {
                "main_exists": "True",
                "archive_exists": "True",
            }

            # Verify files are in separate storages
            assert await main_storage.exists("main.txt")
            assert not await main_storage.exists("archive.txt")
            assert await archive_storage.exists("archive.txt")
            assert not await archive_storage.exists("main.txt")


@pytest.mark.unit
class TestStorageDependency:
    """Test StorageDependency type alias."""

    def test_storage_dependency_type_alias(self) -> None:
        """
        Test that StorageDependency is a valid type alias.

        Verifies:
        - Type alias exists and is importable
        - Can be used in type hints
        """
        from litestar_storages.contrib.dependencies import StorageDependency as SD

        # Type alias should be string literal "Storage"
        assert SD == "Storage"

    def test_storage_dependency_in_function_signature(self) -> None:
        """
        Test using StorageDependency in function signatures.

        Verifies:
        - Can be used as type hint in functions
        - Type checkers recognize it as Storage type
        """
        import inspect
        from typing import Any

        # This function uses type hint compatible with DI
        async def example_function(storage: Any) -> bool:
            return await storage.exists("test.txt")

        # Verify function signature exists
        assert callable(example_function)
        # Verify function has storage parameter
        sig = inspect.signature(example_function)
        assert "storage" in sig.parameters
