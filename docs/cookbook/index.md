# Cookbook

Practical, end-to-end recipes for common file storage patterns with litestar-storages.

Each recipe is self-contained and includes both framework-agnostic examples (plain asyncio) and Litestar integration examples. Copy, adapt, and build upon these patterns for your own applications.

## Recipes

### [File Upload with Validation](file-upload-validation.md)

Validate file uploads by type and size before storing. Covers MIME type detection, file extension verification, and configurable size limits.

**You'll learn:**
- MIME type validation with magic bytes
- File extension allowlisting
- Configurable size limits
- Custom validation error handling

### [Image Processing Pipeline](image-processing-pipeline.md)

Resize and compress images on upload. Covers integration with Pillow for image manipulation, generating thumbnails, and storing multiple variants.

**You'll learn:**
- Integrating Pillow with async storage
- Generating thumbnails at multiple sizes
- Storing original and processed variants
- Handling image format conversion

### [Multi-Backend Configuration](multi-backend-config.md)

Configure different storage backends for development (filesystem) and production (S3/cloud). Covers environment-based configuration and testing strategies.

**You'll learn:**
- Environment-aware storage factory
- Development vs production configuration
- Testing with MemoryStorage
- Graceful backend switching

### [Streaming Large Files](streaming-large-files.md)

Handle large file uploads and downloads efficiently using chunked streaming. Covers multipart uploads, progress tracking, and memory-efficient downloads.

**You'll learn:**
- Chunked file uploads with progress
- S3 multipart upload for large files
- Streaming downloads without memory pressure
- Progress callbacks for UI feedback

## Prerequisites

All recipes assume you have litestar-storages installed:

```bash
# Basic installation
pip install litestar-storages

# With specific backend support
pip install litestar-storages[s3]      # S3/R2/MinIO
pip install litestar-storages[gcs]     # Google Cloud Storage
pip install litestar-storages[azure]   # Azure Blob Storage
pip install litestar-storages[litestar]  # Litestar plugin

# All extras
pip install litestar-storages[all]
```

## Running the Examples

Most examples can be run directly with Python's asyncio:

```python
import asyncio

async def main():
    # Example code here
    pass

if __name__ == "__main__":
    asyncio.run(main())
```

For Litestar examples, run with uvicorn:

```bash
uvicorn app:app --reload
```

## Error Handling Patterns

All recipes follow consistent error handling using the litestar-storages exception hierarchy:

```python
from litestar_storages import (
    StorageError,              # Base exception
    StorageFileNotFoundError,  # File doesn't exist
    StorageFileExistsError,    # File already exists
    StoragePermissionError,    # Permission denied
    StorageConnectionError,    # Backend unavailable
    ConfigurationError,        # Invalid configuration
)

try:
    await storage.put(key, data)
except StoragePermissionError:
    # Handle permission issues
    pass
except StorageConnectionError:
    # Handle connectivity issues
    pass
except StorageError:
    # Catch-all for other storage errors
    pass
```

## Contributing

Have a useful pattern that isn't covered? Contributions are welcome! See the [contribution guide](../contributing.md) for details.
