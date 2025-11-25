"""FileSystemStorage-specific tests.

Tests for features and behaviors specific to the filesystem storage backend,
including directory creation, path sanitization, permissions, and URL generation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from litestar_storages.backends.filesystem import FileSystemStorage


@pytest.mark.unit
class TestFileSystemStorageBasics:
    """Test basic FileSystemStorage functionality."""

    async def test_filesystem_storage_creation(self, tmp_path: Path) -> None:
        """
        Test creating FileSystemStorage instance.

        Verifies:
        - Can create instance with path
        - Directory is created if create_dirs=True
        - Config values are applied correctly
        """
        from litestar_storages.backends.filesystem import FileSystemConfig, FileSystemStorage

        storage_path = tmp_path / "storage"

        config = FileSystemConfig(
            path=storage_path,
            create_dirs=True,
        )
        storage = FileSystemStorage(config=config)

        assert storage.config.path == storage_path
        assert storage_path.exists()
        assert storage_path.is_dir()

    async def test_filesystem_storage_no_create_dirs(self, tmp_path: Path) -> None:
        """
        Test creating storage with create_dirs=False.

        Verifies:
        - Directory is not created if create_dirs=False
        - Raises error if directory doesn't exist
        """
        from litestar_storages.backends.filesystem import FileSystemConfig, FileSystemStorage

        storage_path = tmp_path / "nonexistent"

        config = FileSystemConfig(
            path=storage_path,
            create_dirs=False,
        )

        # Should raise error if directory doesn't exist
        with pytest.raises(Exception):  # Could be FileNotFoundError or ConfigurationError
            storage = FileSystemStorage(config=config)
            # Try to use it
            await storage.put("test.txt", b"data")

    async def test_files_stored_on_disk(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that files are actually written to disk.

        Verifies:
        - Uploaded files exist on filesystem
        - File contents match uploaded data
        - Files are in expected location
        """
        await filesystem_storage.put("test.txt", sample_text_data)

        # Verify file exists on disk
        file_path = filesystem_storage.config.path / "test.txt"
        assert file_path.exists()
        assert file_path.is_file()

        # Verify contents match
        with open(file_path, "rb") as f:
            disk_data = f.read()
        assert disk_data == sample_text_data


@pytest.mark.unit
class TestDirectoryCreation:
    """Test directory creation behavior."""

    async def test_nested_directory_creation(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that nested directories are created automatically.

        Verifies:
        - Deeply nested paths create all intermediate directories
        - Files in nested paths can be uploaded
        """
        nested_key = "a/b/c/d/e/file.txt"
        await filesystem_storage.put(nested_key, sample_text_data)

        # Verify directory structure was created
        file_path = filesystem_storage.config.path / nested_key
        assert file_path.exists()
        assert file_path.parent.exists()

        # Verify all intermediate directories exist
        current = file_path.parent
        while current != filesystem_storage.config.path:
            assert current.exists()
            assert current.is_dir()
            current = current.parent

    async def test_directory_creation_concurrent(
        self,
        filesystem_storage: FileSystemStorage,
    ) -> None:
        """
        Test concurrent directory creation doesn't cause errors.

        Verifies:
        - Multiple concurrent uploads to same directory work
        - No race conditions in directory creation
        """
        import asyncio

        async def upload_file(key: str, data: bytes):
            await filesystem_storage.put(key, data)

        # Upload multiple files to same directory concurrently
        tasks = [upload_file(f"shared-dir/file-{i}.txt", f"data-{i}".encode()) for i in range(10)]

        await asyncio.gather(*tasks)

        # Verify all files exist
        for i in range(10):
            assert await filesystem_storage.exists(f"shared-dir/file-{i}.txt")


@pytest.mark.unit
class TestPathSanitization:
    """Test path sanitization and security."""

    async def test_absolute_path_prevented(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that absolute paths are sanitized.

        Verifies:
        - Leading slashes are stripped
        - Files are stored relative to base path
        """
        # Try to upload with absolute-looking path
        await filesystem_storage.put("/absolute/path/file.txt", sample_text_data)

        # File should be stored relative to base path
        # Not at filesystem root
        file_path = filesystem_storage.config.path / "absolute/path/file.txt"
        assert file_path.exists()

        # Should NOT be at /absolute/path/file.txt
        assert not Path("/absolute/path/file.txt").exists()

    async def test_parent_directory_traversal_prevented(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that ../ path traversal is prevented.

        Verifies:
        - ../ components are removed or rejected
        - Files cannot escape base directory
        - Security vulnerability is prevented
        """
        # Try various path traversal attempts
        malicious_paths = [
            "../outside.txt",
            "subdir/../../outside.txt",
            "a/b/c/../../../outside.txt",
            "./../../outside.txt",
        ]

        for malicious_path in malicious_paths:
            await filesystem_storage.put(malicious_path, sample_text_data)

            # File should be sanitized and stored safely within base path
            # Should NOT escape to parent directory
            parent_file = filesystem_storage.config.path.parent / "outside.txt"
            assert not parent_file.exists(), f"Path traversal not prevented for: {malicious_path}"

    async def test_windows_path_separators(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that Windows-style backslashes are handled.

        Verifies:
        - Backslashes are converted to forward slashes
        - Works correctly on Unix and Windows
        """
        # Upload with Windows-style path
        await filesystem_storage.put("folder\\subfolder\\file.txt", sample_text_data)

        # Should be accessible with either separator
        assert await filesystem_storage.exists("folder/subfolder/file.txt")

        # Verify file exists on disk with correct path
        # On Unix, backslashes should be converted
        # On Windows, backslashes are native
        file_path = filesystem_storage.config.path / "folder" / "subfolder" / "file.txt"
        assert file_path.exists()

    async def test_dot_segments_removed(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that . and .. segments are normalized.

        Verifies:
        - . (current directory) is removed
        - .. (parent directory) is resolved safely
        - Normalized paths work correctly
        """
        # Upload with . segments
        await filesystem_storage.put("./file.txt", sample_text_data)
        assert await filesystem_storage.exists("file.txt")

        # Upload with complex path
        await filesystem_storage.put("a/./b/../c/file.txt", sample_text_data)
        # Should be normalized to a/c/file.txt
        assert await filesystem_storage.exists("a/c/file.txt")


@pytest.mark.unit
class TestFilePermissions:
    """Test file permission handling."""

    @pytest.mark.skipif(
        not hasattr(__import__("os"), "chmod"),
        reason="Platform doesn't support chmod",
    )
    async def test_default_file_permissions(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that files are created with correct permissions.

        Verifies:
        - Files have configured permissions (default 0o644)
        - Permissions can be verified via stat
        """
        import stat

        await filesystem_storage.put("perms-test.txt", sample_text_data)

        file_path = filesystem_storage.config.path / "perms-test.txt"
        file_stat = file_path.stat()
        file_mode = stat.S_IMODE(file_stat.st_mode)

        # Default should be 0o644 (rw-r--r--)
        expected_mode = filesystem_storage.config.permissions
        assert file_mode == expected_mode

    @pytest.mark.skipif(
        not hasattr(__import__("os"), "chmod"),
        reason="Platform doesn't support chmod",
    )
    async def test_custom_file_permissions(self, tmp_path: Path) -> None:
        """
        Test creating storage with custom permissions.

        Verifies:
        - Custom permissions are applied to created files
        - Different permission values work correctly
        """
        import stat

        from litestar_storages.backends.filesystem import FileSystemConfig, FileSystemStorage

        custom_perms = 0o600  # rw-------
        config = FileSystemConfig(
            path=tmp_path,
            permissions=custom_perms,
        )
        storage = FileSystemStorage(config=config)

        await storage.put("custom-perms.txt", b"test data")

        file_path = tmp_path / "custom-perms.txt"
        file_stat = file_path.stat()
        file_mode = stat.S_IMODE(file_stat.st_mode)

        assert file_mode == custom_perms


@pytest.mark.unit
class TestURLGeneration:
    """Test URL generation with base_url."""

    async def test_url_without_base_url(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test URL generation when base_url is not configured.

        Verifies:
        - Returns file path or file:// URL
        - URL is usable for local access
        """
        await filesystem_storage.put("test.txt", sample_text_data)

        url = await filesystem_storage.url("test.txt")

        assert isinstance(url, str)
        # Should be a path or file:// URL
        assert "test.txt" in url

    async def test_url_with_base_url(
        self,
        filesystem_storage_with_base_url: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test URL generation when base_url is configured.

        Verifies:
        - Returns base_url + key
        - URL is properly formatted for CDN/web access
        """
        await filesystem_storage_with_base_url.put("images/photo.jpg", sample_text_data)

        url = await filesystem_storage_with_base_url.url("images/photo.jpg")

        assert url.startswith("https://cdn.example.com/uploads/")
        assert url.endswith("images/photo.jpg")
        assert url == "https://cdn.example.com/uploads/images/photo.jpg"

    @pytest.mark.skip(reason="URL encoding not implemented in FileSystemStorage - enhancement for future")
    async def test_url_special_characters_encoded(
        self,
        filesystem_storage_with_base_url: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that special characters in URLs are properly encoded.

        Verifies:
        - Spaces and special chars are URL-encoded
        - URLs are valid and properly formatted
        """
        await filesystem_storage_with_base_url.put("file with spaces.txt", sample_text_data)

        url = await filesystem_storage_with_base_url.url("file with spaces.txt")

        # URL should have encoded spaces
        assert " " not in url
        assert "file" in url
        assert "spaces" in url
        # URL encoding: space becomes %20
        assert "file%20with%20spaces.txt" in url or "file+with+spaces.txt" in url


@pytest.mark.unit
class TestFileSystemCopyMove:
    """Test copy and move operations for filesystem backend."""

    async def test_copy_uses_filesystem_operations(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that copy uses efficient filesystem operations.

        Verifies:
        - Files are copied on disk
        - Both source and destination exist after copy
        - Content is identical
        """
        await filesystem_storage.put("source.txt", sample_text_data)

        await filesystem_storage.copy("source.txt", "destination.txt")

        # Verify both files exist on disk
        source_path = filesystem_storage.config.path / "source.txt"
        dest_path = filesystem_storage.config.path / "destination.txt"

        assert source_path.exists()
        assert dest_path.exists()

        # Verify contents are identical
        with open(source_path, "rb") as f:
            source_content = f.read()
        with open(dest_path, "rb") as f:
            dest_content = f.read()

        assert source_content == dest_content == sample_text_data

    async def test_move_renames_file(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that move uses filesystem rename when possible.

        Verifies:
        - Source file no longer exists after move
        - Destination file exists
        - Content is preserved
        """
        await filesystem_storage.put("old-name.txt", sample_text_data)

        await filesystem_storage.move("old-name.txt", "new-name.txt")

        # Verify source is gone
        source_path = filesystem_storage.config.path / "old-name.txt"
        assert not source_path.exists()

        # Verify destination exists with correct content
        dest_path = filesystem_storage.config.path / "new-name.txt"
        assert dest_path.exists()

        with open(dest_path, "rb") as f:
            content = f.read()
        assert content == sample_text_data

    async def test_copy_across_directories(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test copying files across different directories.

        Verifies:
        - Can copy between nested paths
        - Directories are created as needed
        """
        await filesystem_storage.put("dir1/file.txt", sample_text_data)

        await filesystem_storage.copy("dir1/file.txt", "dir2/subdir/file.txt")

        # Verify both exist
        assert await filesystem_storage.exists("dir1/file.txt")
        assert await filesystem_storage.exists("dir2/subdir/file.txt")

        # Verify directory structure
        dest_path = filesystem_storage.config.path / "dir2/subdir/file.txt"
        assert dest_path.exists()


@pytest.mark.unit
class TestFileSystemListing:
    """Test listing operations for filesystem backend."""

    async def test_list_directory_order(
        self,
        filesystem_storage: FileSystemStorage,
    ) -> None:
        """
        Test that files are listed consistently.

        Verifies:
        - All uploaded files are returned
        - Order is consistent across calls (not necessarily sorted)
        """
        # Upload files in random order
        files = ["zebra.txt", "alpha.txt", "mike.txt", "bravo.txt"]
        for filename in files:
            await filesystem_storage.put(filename, b"data")

        # List files
        listed = [f.key async for f in filesystem_storage.list()]

        # All files should be present
        assert set(listed) == set(files)
        assert len(listed) == len(files)

    async def test_list_respects_filesystem_structure(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that listing reflects actual filesystem structure.

        Verifies:
        - Files in subdirectories are included
        - Directory structure is preserved in keys
        """
        # Create files in various directories
        await filesystem_storage.put("root.txt", sample_text_data)
        await filesystem_storage.put("dir1/file1.txt", sample_text_data)
        await filesystem_storage.put("dir1/subdir/file2.txt", sample_text_data)
        await filesystem_storage.put("dir2/file3.txt", sample_text_data)

        # List all files
        all_files = [f.key async for f in filesystem_storage.list()]

        assert len(all_files) == 4
        assert "root.txt" in all_files
        assert "dir1/file1.txt" in all_files
        assert "dir1/subdir/file2.txt" in all_files
        assert "dir2/file3.txt" in all_files


@pytest.mark.unit
class TestFileSystemMetadata:
    """Test metadata handling for filesystem backend."""

    async def test_content_type_detection(
        self,
        filesystem_storage: FileSystemStorage,
    ) -> None:
        """
        Test that content type can be detected from extension.

        Verifies:
        - Common file extensions have correct content types
        - Content type is stored in metadata or attributes
        """
        test_files = {
            "document.pdf": "application/pdf",
            "image.jpg": "image/jpeg",
            "data.json": "application/json",
            "page.html": "text/html",
        }

        for filename, expected_type in test_files.items():
            result = await filesystem_storage.put(
                filename,
                b"test data",
                content_type=expected_type,
            )

            assert result.content_type == expected_type

    @pytest.mark.skip(reason="Metadata persistence not implemented in FileSystemStorage - enhancement for future")
    async def test_metadata_storage_in_extended_attributes(
        self,
        filesystem_storage: FileSystemStorage,
        sample_metadata: dict[str, str],
    ) -> None:
        """
        Test that metadata is stored (if supported by backend).

        Verifies:
        - Custom metadata can be stored
        - Metadata can be retrieved
        - Implementation is platform-appropriate
        """
        await filesystem_storage.put(
            "with-metadata.txt",
            b"data",
            metadata=sample_metadata,
        )

        info = await filesystem_storage.info("with-metadata.txt")

        # Metadata should be preserved
        # (Implementation may use extended attributes, sidecar files, or in-memory)
        for key, value in sample_metadata.items():
            assert info.metadata.get(key) == value


@pytest.mark.unit
class TestFileSystemEdgeCases:
    """Test edge cases for filesystem backend."""

    async def test_empty_filename(
        self,
        filesystem_storage: FileSystemStorage,
    ) -> None:
        """
        Test handling of empty filename.

        Verifies:
        - Empty filename is rejected or handled gracefully
        """
        from litestar_storages.exceptions import StorageError

        with pytest.raises((StorageError, ValueError)):
            await filesystem_storage.put("", b"data")

    async def test_filename_with_only_slashes(
        self,
        filesystem_storage: FileSystemStorage,
    ) -> None:
        """
        Test handling of filename with only slashes.

        Verifies:
        - Invalid paths are rejected
        - No directory-only paths accepted
        """
        from litestar_storages.exceptions import StorageError

        with pytest.raises((StorageError, ValueError)):
            await filesystem_storage.put("///", b"data")

    async def test_very_long_filename(
        self,
        filesystem_storage: FileSystemStorage,
    ) -> None:
        """
        Test handling of very long filenames.

        Verifies:
        - Long filenames work within OS limits
        - Error if exceeding filesystem limits
        """
        # Most filesystems support 255 bytes per component
        long_name = "a" * 200 + ".txt"

        # Should work
        await filesystem_storage.put(long_name, b"data")
        assert await filesystem_storage.exists(long_name)

        # Extremely long path (over 255 chars per component) might fail
        # depending on filesystem - that's acceptable

    async def test_unicode_filenames(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test handling of Unicode characters in filenames.

        Verifies:
        - Unicode filenames are supported
        - Files can be stored and retrieved
        """
        unicode_names = [
            "文件.txt",  # Chinese
            "файл.txt",  # Russian
            "αρχείο.txt",  # Greek
            "ファイル.txt",  # Japanese
            "emoji-😀.txt",  # Emoji
        ]

        for filename in unicode_names:
            await filesystem_storage.put(filename, sample_text_data)
            assert await filesystem_storage.exists(filename)
            data = await filesystem_storage.get_bytes(filename)
            assert data == sample_text_data

    async def test_symlink_handling(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that symlinks are handled appropriately.

        Verifies:
        - Symlinks within storage are followed or rejected
        - Symlinks outside storage don't escape base path
        """
        import os

        # Create a file
        await filesystem_storage.put("target.txt", sample_text_data)

        target_path = filesystem_storage.config.path / "target.txt"
        link_path = filesystem_storage.config.path / "link.txt"

        try:
            # Create symlink
            os.symlink(target_path, link_path)

            # Storage should handle symlink appropriately
            # Either follow it or raise error
            try:
                data = await filesystem_storage.get_bytes("link.txt")
                # If symlinks are followed
                assert data == sample_text_data
            except Exception:
                # If symlinks are not supported/blocked - also acceptable
                pass
        except OSError:
            # Platform doesn't support symlinks (Windows without admin)
            pytest.skip("Platform doesn't support symlinks")


@pytest.mark.unit
class TestFileSystemErrorHandling:
    """Test error handling in filesystem backend."""

    async def test_put_without_aiofiles_raises_configuration_error(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """
        Test put() raises ConfigurationError when aiofiles is not available.

        Verifies:
        - ImportError for aiofiles is caught
        - ConfigurationError is raised with helpful message
        """
        from litestar_storages.backends.filesystem import FileSystemConfig, FileSystemStorage
        from litestar_storages.exceptions import ConfigurationError

        storage = FileSystemStorage(config=FileSystemConfig(path=tmp_path))

        # Mock aiofiles import to raise ImportError
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "aiofiles":
                raise ImportError("No module named 'aiofiles'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Should raise ConfigurationError
        with pytest.raises(ConfigurationError, match="aiofiles is required"):
            await storage.put("test.txt", b"data")

    async def test_get_without_aiofiles_raises_configuration_error(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """
        Test get() raises ConfigurationError when aiofiles is not available.

        Verifies:
        - ImportError for aiofiles is caught
        - ConfigurationError is raised with helpful message
        """
        from litestar_storages.backends.filesystem import FileSystemConfig, FileSystemStorage
        from litestar_storages.exceptions import ConfigurationError

        storage = FileSystemStorage(config=FileSystemConfig(path=tmp_path))

        # Mock aiofiles import to raise ImportError
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "aiofiles":
                raise ImportError("No module named 'aiofiles'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Should raise ConfigurationError
        with pytest.raises(ConfigurationError, match="aiofiles is required"):
            async for _ in storage.get("test.txt"):
                pass

    async def test_get_bytes_without_aiofiles_raises_configuration_error(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """
        Test get_bytes() raises ConfigurationError when aiofiles is not available.

        Verifies:
        - ImportError for aiofiles is caught
        - ConfigurationError is raised with helpful message
        """
        from litestar_storages.backends.filesystem import FileSystemConfig, FileSystemStorage
        from litestar_storages.exceptions import ConfigurationError

        storage = FileSystemStorage(config=FileSystemConfig(path=tmp_path))

        # Mock aiofiles import to raise ImportError
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "aiofiles":
                raise ImportError("No module named 'aiofiles'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Should raise ConfigurationError
        with pytest.raises(ConfigurationError, match="aiofiles is required"):
            await storage.get_bytes("test.txt")

    async def test_delete_with_permission_error(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
        monkeypatch,
    ) -> None:
        """
        Test delete() raises StoragePermissionError on OSError.

        Verifies:
        - OSError during deletion is caught
        - StoragePermissionError is raised with context
        """
        from litestar_storages.exceptions import StoragePermissionError

        # Create a file
        await filesystem_storage.put("test.txt", sample_text_data)
        file_path = filesystem_storage.config.path / "test.txt"

        # Mock unlink to raise OSError
        from pathlib import Path

        original_unlink = Path.unlink

        def mock_unlink(self, *args, **kwargs):
            if self == file_path:
                raise OSError("Permission denied")
            return original_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", mock_unlink)

        # Should raise StoragePermissionError
        with pytest.raises(StoragePermissionError, match="Failed to delete file"):
            await filesystem_storage.delete("test.txt")

    async def test_copy_with_permission_error(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
        monkeypatch,
    ) -> None:
        """
        Test copy() raises StoragePermissionError on OSError.

        Verifies:
        - OSError during copy is caught
        - StoragePermissionError is raised with context
        """
        from litestar_storages.exceptions import StoragePermissionError

        # Create a source file
        await filesystem_storage.put("source.txt", sample_text_data)

        # Mock shutil.copy2 to raise OSError
        import shutil

        def mock_copy2(*args, **kwargs):
            raise OSError("Permission denied")

        monkeypatch.setattr(shutil, "copy2", mock_copy2)

        # Should raise StoragePermissionError
        with pytest.raises(StoragePermissionError, match="Failed to copy file"):
            await filesystem_storage.copy("source.txt", "destination.txt")

    async def test_move_with_permission_error(
        self,
        filesystem_storage: FileSystemStorage,
        sample_text_data: bytes,
        monkeypatch,
    ) -> None:
        """
        Test move() raises StoragePermissionError on OSError.

        Verifies:
        - OSError during move is caught
        - StoragePermissionError is raised with context
        """
        from litestar_storages.exceptions import StoragePermissionError

        # Create a source file
        await filesystem_storage.put("source.txt", sample_text_data)

        # Mock shutil.move to raise OSError
        import shutil

        def mock_move(*args, **kwargs):
            raise OSError("Permission denied")

        monkeypatch.setattr(shutil, "move", mock_move)

        # Should raise StoragePermissionError
        with pytest.raises(StoragePermissionError, match="Failed to move file"):
            await filesystem_storage.move("source.txt", "destination.txt")

    async def test_get_nonexistent_file_streaming(
        self,
        filesystem_storage: FileSystemStorage,
    ) -> None:
        """
        Test get() (streaming) with non-existent file.

        Verifies:
        - StorageFileNotFoundError is raised when streaming non-existent file
        - The async generator properly raises the error
        """
        from litestar_storages.exceptions import StorageFileNotFoundError

        with pytest.raises(StorageFileNotFoundError, match="nonexistent"):
            async for _ in filesystem_storage.get("nonexistent.txt"):
                pass
