"""Tests for storage type definitions.

This module tests the dataclasses and protocols defined in types.py:
- StoredFile
- ProgressInfo (especially percentage edge cases)
- MultipartUpload (especially completed_parts)
- UploadResult
- ProgressCallback protocol
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from litestar_storages.types import (
    MultipartUpload,
    ProgressInfo,
    StoredFile,
    UploadResult,
)


@pytest.mark.unit
class TestStoredFile:
    """Test StoredFile dataclass."""

    def test_stored_file_creation(self) -> None:
        """
        Test creating a StoredFile instance.

        Verifies:
        - Required fields can be set
        - Optional fields have defaults
        """
        file = StoredFile(
            key="test.txt",
            size=1024,
        )

        assert file.key == "test.txt"
        assert file.size == 1024
        assert file.content_type is None
        assert file.etag is None
        assert file.last_modified is None
        assert file.metadata == {}

    def test_stored_file_with_all_fields(self) -> None:
        """
        Test StoredFile with all fields populated.

        Verifies:
        - All fields can be set
        - Values are preserved
        """
        now = datetime.now(timezone.utc)
        metadata = {"author": "test", "version": "1.0"}

        file = StoredFile(
            key="documents/report.pdf",
            size=2048,
            content_type="application/pdf",
            etag="abc123",
            last_modified=now,
            metadata=metadata,
        )

        assert file.key == "documents/report.pdf"
        assert file.size == 2048
        assert file.content_type == "application/pdf"
        assert file.etag == "abc123"
        assert file.last_modified == now
        assert file.metadata == metadata

    def test_stored_file_is_frozen(self) -> None:
        """
        Test that StoredFile is immutable (frozen).

        Verifies:
        - Cannot modify fields after creation
        - Raises appropriate error on modification attempt
        """
        file = StoredFile(key="test.txt", size=100)

        with pytest.raises(AttributeError):
            file.key = "new-key.txt"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            file.size = 200  # type: ignore[misc]


@pytest.mark.unit
class TestUploadResult:
    """Test UploadResult dataclass."""

    def test_upload_result_creation(self) -> None:
        """
        Test creating an UploadResult instance.

        Verifies:
        - Can be created with StoredFile
        - URL is optional
        """
        stored_file = StoredFile(key="test.txt", size=100)
        result = UploadResult(file=stored_file)

        assert result.file == stored_file
        assert result.url is None

    def test_upload_result_with_url(self) -> None:
        """
        Test UploadResult with URL.

        Verifies:
        - URL can be set
        - Both file and URL are accessible
        """
        stored_file = StoredFile(key="test.txt", size=100)
        url = "https://cdn.example.com/test.txt"
        result = UploadResult(file=stored_file, url=url)

        assert result.file == stored_file
        assert result.url == url

    def test_upload_result_is_frozen(self) -> None:
        """
        Test that UploadResult is immutable (frozen).

        Verifies:
        - Cannot modify fields after creation
        """
        stored_file = StoredFile(key="test.txt", size=100)
        result = UploadResult(file=stored_file)

        with pytest.raises(AttributeError):
            result.url = "https://example.com"  # type: ignore[misc]


@pytest.mark.unit
class TestProgressInfo:
    """Test ProgressInfo dataclass and percentage calculation."""

    def test_progress_info_creation(self) -> None:
        """
        Test creating a ProgressInfo instance.

        Verifies:
        - All fields can be set
        - Instance is mutable (not frozen)
        """
        progress = ProgressInfo(
            bytes_transferred=512,
            total_bytes=1024,
            operation="upload",
            key="test.txt",
        )

        assert progress.bytes_transferred == 512
        assert progress.total_bytes == 1024
        assert progress.operation == "upload"
        assert progress.key == "test.txt"

    def test_progress_info_percentage_calculation(self) -> None:
        """
        Test percentage calculation with normal values.

        Verifies:
        - Percentage is calculated correctly
        - Returns float value between 0 and 100
        """
        progress = ProgressInfo(
            bytes_transferred=256,
            total_bytes=1024,
            operation="upload",
            key="test.txt",
        )

        assert progress.percentage == 25.0

    def test_progress_info_percentage_zero_total(self) -> None:
        """
        Test percentage calculation when total_bytes is 0.

        Verifies:
        - Returns None when total is 0 (avoid division by zero)
        - Edge case is handled gracefully
        """
        progress = ProgressInfo(
            bytes_transferred=0,
            total_bytes=0,
            operation="upload",
            key="test.txt",
        )

        assert progress.percentage is None

    def test_progress_info_percentage_none_total(self) -> None:
        """
        Test percentage calculation when total_bytes is None.

        Verifies:
        - Returns None when total is unknown
        - Useful for streaming uploads with unknown size
        """
        progress = ProgressInfo(
            bytes_transferred=512,
            total_bytes=None,
            operation="upload",
            key="test.txt",
        )

        assert progress.percentage is None

    def test_progress_info_percentage_complete(self) -> None:
        """
        Test percentage at 100% completion.

        Verifies:
        - Returns 100.0 when bytes_transferred equals total_bytes
        """
        progress = ProgressInfo(
            bytes_transferred=1024,
            total_bytes=1024,
            operation="download",
            key="test.txt",
        )

        assert progress.percentage == 100.0

    def test_progress_info_percentage_partial(self) -> None:
        """
        Test percentage with various partial progress values.

        Verifies:
        - Calculation is accurate for different percentages
        - Floating point precision is maintained
        """
        test_cases = [
            (0, 1000, 0.0),
            (1, 1000, 0.1),
            (250, 1000, 25.0),
            (500, 1000, 50.0),
            (750, 1000, 75.0),
            (999, 1000, 99.9),
        ]

        for transferred, total, expected in test_cases:
            progress = ProgressInfo(
                bytes_transferred=transferred,
                total_bytes=total,
                operation="upload",
                key="test.txt",
            )
            assert progress.percentage == expected

        # Test with floating point precision
        progress = ProgressInfo(
            bytes_transferred=333,
            total_bytes=1000,
            operation="upload",
            key="test.txt",
        )
        # Use approximate comparison for floating point
        assert progress.percentage is not None
        assert abs(progress.percentage - 33.3) < 0.01

    def test_progress_info_is_mutable(self) -> None:
        """
        Test that ProgressInfo is mutable.

        Verifies:
        - Fields can be updated after creation
        - Useful for updating progress in callbacks
        """
        progress = ProgressInfo(
            bytes_transferred=0,
            total_bytes=1024,
            operation="upload",
            key="test.txt",
        )

        # Should be able to update fields
        progress.bytes_transferred = 512
        assert progress.bytes_transferred == 512
        assert progress.percentage == 50.0

        progress.bytes_transferred = 1024
        assert progress.bytes_transferred == 1024
        assert progress.percentage == 100.0


@pytest.mark.unit
class TestMultipartUpload:
    """Test MultipartUpload dataclass and completed_parts property."""

    def test_multipart_upload_creation(self) -> None:
        """
        Test creating a MultipartUpload instance.

        Verifies:
        - Required fields can be set
        - Default values are applied
        """
        upload = MultipartUpload(
            upload_id="test-upload-123",
            key="large-file.bin",
        )

        assert upload.upload_id == "test-upload-123"
        assert upload.key == "large-file.bin"
        assert upload.parts == []
        assert upload.part_size == 5 * 1024 * 1024  # 5MB default
        assert upload.total_parts is None

    def test_multipart_upload_with_custom_part_size(self) -> None:
        """
        Test MultipartUpload with custom part size.

        Verifies:
        - Custom part_size can be set
        - Different from default value
        """
        custom_size = 10 * 1024 * 1024  # 10MB
        upload = MultipartUpload(
            upload_id="test-upload-123",
            key="large-file.bin",
            part_size=custom_size,
        )

        assert upload.part_size == custom_size

    def test_multipart_upload_add_part(self) -> None:
        """
        Test adding parts to multipart upload.

        Verifies:
        - add_part() appends to parts list
        - Part number and etag are stored
        """
        upload = MultipartUpload(
            upload_id="test-upload-123",
            key="large-file.bin",
        )

        upload.add_part(1, "etag-1")
        assert len(upload.parts) == 1
        assert upload.parts[0] == (1, "etag-1")

        upload.add_part(2, "etag-2")
        assert len(upload.parts) == 2
        assert upload.parts[1] == (2, "etag-2")

    def test_multipart_upload_completed_parts_property(self) -> None:
        """
        Test completed_parts property calculation.

        Verifies:
        - Returns number of parts in the list
        - Updates as parts are added
        """
        upload = MultipartUpload(
            upload_id="test-upload-123",
            key="large-file.bin",
        )

        assert upload.completed_parts == 0

        upload.add_part(1, "etag-1")
        assert upload.completed_parts == 1

        upload.add_part(2, "etag-2")
        assert upload.completed_parts == 2

        upload.add_part(3, "etag-3")
        assert upload.completed_parts == 3

    def test_multipart_upload_with_total_parts(self) -> None:
        """
        Test MultipartUpload with total_parts set.

        Verifies:
        - total_parts can be set
        - Useful for progress tracking
        """
        upload = MultipartUpload(
            upload_id="test-upload-123",
            key="large-file.bin",
            total_parts=10,
        )

        assert upload.total_parts == 10
        assert upload.completed_parts == 0

        # Add some parts
        for i in range(1, 6):
            upload.add_part(i, f"etag-{i}")

        assert upload.completed_parts == 5
        assert upload.total_parts == 10

    def test_multipart_upload_parts_out_of_order(self) -> None:
        """
        Test adding parts in non-sequential order.

        Verifies:
        - Parts can be added in any order
        - completed_parts still returns correct count
        """
        upload = MultipartUpload(
            upload_id="test-upload-123",
            key="large-file.bin",
        )

        # Add parts out of order
        upload.add_part(3, "etag-3")
        upload.add_part(1, "etag-1")
        upload.add_part(2, "etag-2")

        assert upload.completed_parts == 3
        assert len(upload.parts) == 3
        # Parts are stored in the order they were added
        assert upload.parts[0] == (3, "etag-3")
        assert upload.parts[1] == (1, "etag-1")
        assert upload.parts[2] == (2, "etag-2")

    def test_multipart_upload_is_mutable(self) -> None:
        """
        Test that MultipartUpload is mutable.

        Verifies:
        - Fields can be updated after creation
        - Useful for tracking upload progress
        """
        upload = MultipartUpload(
            upload_id="test-upload-123",
            key="large-file.bin",
        )

        # Should be able to modify fields
        upload.total_parts = 5
        assert upload.total_parts == 5

        upload.add_part(1, "etag-1")
        assert upload.completed_parts == 1


@pytest.mark.unit
class TestProgressCallback:
    """Test ProgressCallback protocol."""

    def test_progress_callback_callable(self) -> None:
        """
        Test that progress callback can be called.

        Verifies:
        - Callback functions match protocol
        - Can be invoked with ProgressInfo
        """
        called = []

        def callback(info: ProgressInfo) -> None:
            called.append(info)

        progress = ProgressInfo(
            bytes_transferred=512,
            total_bytes=1024,
            operation="upload",
            key="test.txt",
        )

        callback(progress)

        assert len(called) == 1
        assert called[0] == progress

    def test_progress_callback_with_percentage(self) -> None:
        """
        Test callback with percentage calculation.

        Verifies:
        - Callback receives correct percentage
        - Can process percentage information
        """
        percentages = []

        def callback(info: ProgressInfo) -> None:
            if info.percentage is not None:
                percentages.append(info.percentage)

        # Simulate progress updates
        for transferred in [0, 256, 512, 768, 1024]:
            progress = ProgressInfo(
                bytes_transferred=transferred,
                total_bytes=1024,
                operation="upload",
                key="test.txt",
            )
            callback(progress)

        assert percentages == [0.0, 25.0, 50.0, 75.0, 100.0]

    def test_progress_callback_with_unknown_total(self) -> None:
        """
        Test callback when total size is unknown.

        Verifies:
        - Callback handles None percentage gracefully
        - Can still track bytes transferred
        """
        transferred_bytes = []

        def callback(info: ProgressInfo) -> None:
            transferred_bytes.append(info.bytes_transferred)

        # Simulate progress with unknown total
        for transferred in [100, 200, 300]:
            progress = ProgressInfo(
                bytes_transferred=transferred,
                total_bytes=None,
                operation="upload",
                key="test.txt",
            )
            callback(progress)
            assert progress.percentage is None

        assert transferred_bytes == [100, 200, 300]
