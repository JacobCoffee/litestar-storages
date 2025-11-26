"""Tests for storage exception hierarchy.

This module tests exception classes and their string representations.
"""

from __future__ import annotations

import pytest

from litestar_storages.exceptions import (
    ConfigurationError,
    StorageConnectionError,
    StorageError,
    StorageFileExistsError,
    StorageFileNotFoundError,
    StoragePermissionError,
)


@pytest.mark.unit
class TestStorageExceptions:
    """Test exception classes and their behavior."""

    def test_storage_error_base_exception(self) -> None:
        """
        Test StorageError base exception.

        Verifies:
        - Can be instantiated with message
        - Message is preserved
        - Is instance of Exception
        """
        error = StorageError("test error")

        assert str(error) == "test error"
        assert isinstance(error, Exception)

    def test_storage_file_not_found_error(self) -> None:
        """
        Test StorageFileNotFoundError exception.

        Verifies:
        - Accepts key in constructor
        - String representation includes key
        - key attribute is accessible
        """
        key = "path/to/missing/file.txt"
        error = StorageFileNotFoundError(key)

        assert error.key == key
        assert "File not found" in str(error)
        assert key in str(error)
        assert isinstance(error, StorageError)

    def test_storage_file_exists_error(self) -> None:
        """
        Test StorageFileExistsError exception.

        Verifies:
        - Accepts key in constructor
        - String representation includes key
        - key attribute is accessible
        """
        key = "path/to/existing/file.txt"
        error = StorageFileExistsError(key)

        assert error.key == key
        assert "File already exists" in str(error)
        assert key in str(error)
        assert isinstance(error, StorageError)

    def test_storage_permission_error(self) -> None:
        """
        Test StoragePermissionError exception.

        Verifies:
        - Can be instantiated with message
        - Is instance of StorageError
        """
        error = StoragePermissionError("Permission denied")

        assert "Permission denied" in str(error)
        assert isinstance(error, StorageError)

    def test_storage_connection_error(self) -> None:
        """
        Test StorageConnectionError exception.

        Verifies:
        - Can be instantiated with message
        - Is instance of StorageError
        """
        error = StorageConnectionError("Connection failed")

        assert "Connection failed" in str(error)
        assert isinstance(error, StorageError)

    def test_configuration_error(self) -> None:
        """
        Test ConfigurationError exception.

        Verifies:
        - Can be instantiated with message
        - Is instance of StorageError
        """
        error = ConfigurationError("Invalid configuration")

        assert "Invalid configuration" in str(error)
        assert isinstance(error, StorageError)

    def test_exception_inheritance_hierarchy(self) -> None:
        """
        Test exception inheritance relationships.

        Verifies:
        - All storage exceptions inherit from StorageError
        - StorageError inherits from Exception
        - Can catch all storage errors with StorageError
        """
        exceptions = [
            StorageFileNotFoundError("key"),
            StorageFileExistsError("key"),
            StoragePermissionError("message"),
            StorageConnectionError("message"),
            ConfigurationError("message"),
        ]

        for exc in exceptions:
            assert isinstance(exc, StorageError)
            assert isinstance(exc, Exception)

    def test_file_not_found_error_with_special_characters(self) -> None:
        """
        Test StorageFileNotFoundError with special characters in key.

        Verifies:
        - Special characters in key are preserved
        - Unicode characters work correctly
        """
        keys = [
            "path/with spaces/file.txt",
            "path/with-dashes/file.txt",
            "path/with_underscores/file.txt",
            "path/文件.txt",  # Chinese characters
            "path/файл.txt",  # Cyrillic characters
        ]

        for key in keys:
            error = StorageFileNotFoundError(key)
            assert error.key == key
            assert key in str(error)

    def test_file_exists_error_with_special_characters(self) -> None:
        """
        Test StorageFileExistsError with special characters in key.

        Verifies:
        - Special characters in key are preserved
        - Unicode characters work correctly
        """
        keys = [
            "path/with spaces/file.txt",
            "path/with-dashes/file.txt",
            "path/with_underscores/file.txt",
            "path/文件.txt",  # Chinese characters
            "path/файл.txt",  # Cyrillic characters
        ]

        for key in keys:
            error = StorageFileExistsError(key)
            assert error.key == key
            assert key in str(error)

    def test_exception_can_be_raised_and_caught(self) -> None:
        """
        Test exceptions can be raised and caught.

        Verifies:
        - Exceptions can be raised in try/except blocks
        - Correct exception type is caught
        """
        # Test raising and catching specific exception
        with pytest.raises(StorageFileNotFoundError) as exc_info:
            raise StorageFileNotFoundError("test.txt")

        assert exc_info.value.key == "test.txt"

        # Test catching with base class
        with pytest.raises(StorageError):
            raise StorageFileNotFoundError("test.txt")

    def test_exception_chaining(self) -> None:
        """
        Test exception chaining with 'from' clause.

        Verifies:
        - Exceptions can be chained
        - Original exception is preserved
        """
        original_error = ValueError("original error")

        with pytest.raises(StorageError, match="storage error") as exc_info:
            raise StorageError("storage error") from original_error

        assert exc_info.value.__cause__ is original_error
        assert str(exc_info.value.__cause__) == "original error"
