"""Example: GCS Multipart Upload with Progress Tracking.

This example demonstrates:
- Uploading large files using multipart upload
- Progress tracking during upload
- Graceful error handling and cleanup
"""

import asyncio

from litestar_storages.backends.gcs import GCSConfig, GCSStorage
from litestar_storages.types import ProgressInfo


async def upload_with_progress() -> None:
    """Upload a large file with progress tracking."""
    # Initialize storage
    storage = GCSStorage(
        config=GCSConfig(
            bucket="my-bucket",
            # For local testing with fake-gcs-server emulator
            api_root="http://localhost:4443",
        )
    )

    # Create large data (30MB)
    large_data = b"X" * (30 * 1024 * 1024)

    # Progress callback to track upload
    def show_progress(info: ProgressInfo) -> None:
        """Display upload progress."""
        if info.percentage:
            print(f"Upload progress: {info.percentage:.1f}% ({info.bytes_transferred}/{info.total_bytes} bytes)")  # noqa: T201
        else:
            print(f"Uploaded: {info.bytes_transferred} bytes")  # noqa: T201

    try:
        print("Starting large file upload...")  # noqa: T201

        # Upload with 5MB parts
        result = await storage.put_large(
            key="large-file.bin",
            data=large_data,
            content_type="application/octet-stream",
            metadata={"uploaded-by": "example-script"},
            part_size=5 * 1024 * 1024,  # 5MB parts
            progress_callback=show_progress,
        )

        print("\nUpload complete!")  # noqa: T201
        print(f"Key: {result.key}")  # noqa: T201
        print(f"Size: {result.size:,} bytes")  # noqa: T201
        print(f"ETag: {result.etag}")  # noqa: T201

    finally:
        await storage.close()


async def manual_multipart_upload() -> None:
    """Manually control multipart upload for fine-grained control."""
    storage = GCSStorage(
        config=GCSConfig(
            bucket="my-bucket",
            api_root="http://localhost:4443",
        )
    )

    try:
        # Prepare parts
        part1 = b"A" * (5 * 1024 * 1024)  # 5MB
        part2 = b"B" * (5 * 1024 * 1024)  # 5MB
        part3 = b"C" * (5 * 1024 * 1024)  # 5MB

        print("Starting multipart upload...")  # noqa: T201

        # Start upload
        upload = await storage.start_multipart_upload(
            key="manual-large-file.bin",
            content_type="application/octet-stream",
            metadata={"upload-type": "manual"},
            part_size=5 * 1024 * 1024,
        )

        print(f"Upload ID: {upload.upload_id}")  # noqa: T201

        try:
            # Upload parts
            print("Uploading part 1...")  # noqa: T201
            etag1 = await storage.upload_part(upload, 1, part1)
            print(f"Part 1 uploaded: {etag1}")  # noqa: T201

            print("Uploading part 2...")  # noqa: T201
            etag2 = await storage.upload_part(upload, 2, part2)
            print(f"Part 2 uploaded: {etag2}")  # noqa: T201

            print("Uploading part 3...")  # noqa: T201
            etag3 = await storage.upload_part(upload, 3, part3)
            print(f"Part 3 uploaded: {etag3}")  # noqa: T201

            # Complete upload
            print("\nCompleting multipart upload...")  # noqa: T201
            result = await storage.complete_multipart_upload(upload)

            print("Upload complete!")  # noqa: T201
            print(f"Key: {result.key}")  # noqa: T201
            print(f"Size: {result.size:,} bytes")  # noqa: T201

        except Exception as e:
            # If anything fails, abort the upload
            print(f"\nError occurred: {e}")  # noqa: T201
            print("Aborting upload...")  # noqa: T201
            await storage.abort_multipart_upload(upload)
            print("Upload aborted and cleaned up")  # noqa: T201
            raise

    finally:
        await storage.close()


if __name__ == "__main__":
    print("=== GCS Multipart Upload with Progress ===\n")  # noqa: T201
    asyncio.run(upload_with_progress())

    print("\n\n=== Manual Multipart Upload ===\n")  # noqa: T201
    asyncio.run(manual_multipart_upload())
