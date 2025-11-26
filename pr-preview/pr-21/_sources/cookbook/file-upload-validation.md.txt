# File Upload with Validation

Validate file uploads by type and size before storing them. This recipe demonstrates how to build a robust file validation layer that prevents invalid or malicious uploads.

## Prerequisites

- Python 3.9+
- litestar-storages installed (`pip install litestar-storages`)
- python-magic for MIME type detection (`pip install python-magic`)
- For Litestar examples: `pip install litestar-storages[litestar]`

## The Problem

Accepting arbitrary file uploads without validation is a security risk and can lead to:

- Storage of malicious files (executables disguised as images)
- Denial of service through large file uploads
- Application errors from unexpected file types
- Wasted storage space on invalid content

## Solution

### File Validator Class

First, create a reusable validator that checks both file type and size:

```python
"""File upload validation utilities."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from typing import BinaryIO

# Optional: Use python-magic for accurate MIME detection
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False


class ValidationError(Exception):
    """Raised when file validation fails."""

    def __init__(self, message: str, field: str = "file") -> None:
        self.message = message
        self.field = field
        super().__init__(message)


@dataclass
class FileValidator:
    """Validates file uploads by type and size.

    Attributes:
        allowed_types: Set of allowed MIME types (e.g., {"image/jpeg", "image/png"})
        allowed_extensions: Set of allowed file extensions (e.g., {".jpg", ".png"})
        max_size: Maximum file size in bytes (default: 10MB)
        min_size: Minimum file size in bytes (default: 1 byte)
        require_magic: If True, use magic bytes for MIME detection (more secure)
    """

    allowed_types: set[str] = field(default_factory=lambda: {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    })
    allowed_extensions: set[str] = field(default_factory=lambda: {
        ".jpg", ".jpeg", ".png", ".gif", ".webp"
    })
    max_size: int = 10 * 1024 * 1024  # 10MB
    min_size: int = 1
    require_magic: bool = True

    def validate_size(self, data: bytes) -> None:
        """Validate file size.

        Args:
            data: File content as bytes

        Raises:
            ValidationError: If size is outside allowed range
        """
        size = len(data)

        if size < self.min_size:
            raise ValidationError(
                f"File too small. Minimum size: {self.min_size} bytes",
                field="file"
            )

        if size > self.max_size:
            raise ValidationError(
                f"File too large. Maximum size: {self.max_size // (1024 * 1024)}MB",
                field="file"
            )

    def validate_extension(self, filename: str) -> None:
        """Validate file extension.

        Args:
            filename: Original filename

        Raises:
            ValidationError: If extension is not allowed
        """
        if not filename:
            raise ValidationError("Filename is required", field="filename")

        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext not in self.allowed_extensions:
            allowed = ", ".join(sorted(self.allowed_extensions))
            raise ValidationError(
                f"File extension '{ext}' not allowed. Allowed: {allowed}",
                field="filename"
            )

    def detect_mime_type(self, data: bytes, filename: str | None = None) -> str:
        """Detect MIME type from file content.

        Args:
            data: File content as bytes
            filename: Optional filename for fallback detection

        Returns:
            Detected MIME type
        """
        if self.require_magic and HAS_MAGIC:
            # Use magic bytes for accurate detection
            mime = magic.Magic(mime=True)
            return mime.from_buffer(data)

        if filename:
            # Fallback to extension-based detection
            guessed, _ = mimetypes.guess_type(filename)
            if guessed:
                return guessed

        return "application/octet-stream"

    def validate_mime_type(self, data: bytes, filename: str | None = None) -> str:
        """Validate MIME type matches allowed types.

        Args:
            data: File content as bytes
            filename: Optional filename for detection fallback

        Returns:
            Detected MIME type if valid

        Raises:
            ValidationError: If MIME type is not allowed
        """
        mime_type = self.detect_mime_type(data, filename)

        if mime_type not in self.allowed_types:
            allowed = ", ".join(sorted(self.allowed_types))
            raise ValidationError(
                f"File type '{mime_type}' not allowed. Allowed: {allowed}",
                field="content_type"
            )

        return mime_type

    def validate(self, data: bytes, filename: str) -> str:
        """Run all validations.

        Args:
            data: File content as bytes
            filename: Original filename

        Returns:
            Detected MIME type if all validations pass

        Raises:
            ValidationError: If any validation fails
        """
        self.validate_size(data)
        self.validate_extension(filename)
        return self.validate_mime_type(data, filename)
```

### Framework-Agnostic Usage

Use the validator with any storage backend in plain asyncio:

```python
"""Framework-agnostic file upload with validation."""

import asyncio
from pathlib import Path

from litestar_storages import (
    FileSystemStorage,
    FileSystemConfig,
    StorageError,
    StoredFile,
)

# Assume FileValidator class is imported from above


async def upload_file(
    storage: FileSystemStorage,
    validator: FileValidator,
    filename: str,
    data: bytes,
) -> StoredFile:
    """Upload a file with validation.

    Args:
        storage: Storage backend
        validator: File validator instance
        filename: Original filename
        data: File content

    Returns:
        StoredFile with metadata about stored file

    Raises:
        ValidationError: If file fails validation
        StorageError: If storage operation fails
    """
    # Validate the file
    content_type = validator.validate(data, filename)

    # Generate a safe storage key
    # In production, use UUID or hash to prevent conflicts
    import uuid
    ext = Path(filename).suffix.lower()
    key = f"uploads/{uuid.uuid4()}{ext}"

    # Store the file
    return await storage.put(
        key=key,
        data=data,
        content_type=content_type,
        metadata={"original_filename": filename},
    )


async def main() -> None:
    """Example usage."""
    # Configure storage
    storage = FileSystemStorage(
        config=FileSystemConfig(
            path=Path("./uploads"),
            create_dirs=True,
        )
    )

    # Configure validator for images only
    validator = FileValidator(
        allowed_types={"image/jpeg", "image/png"},
        allowed_extensions={".jpg", ".jpeg", ".png"},
        max_size=5 * 1024 * 1024,  # 5MB
    )

    # Simulate file upload
    # In real usage, this would come from a request
    test_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # PNG header
    test_filename = "photo.png"

    try:
        result = await upload_file(storage, validator, test_filename, test_data)
        print(f"Uploaded: {result.key} ({result.size} bytes)")
        print(f"Content-Type: {result.content_type}")
    except ValidationError as e:
        print(f"Validation failed: {e.message}")
    except StorageError as e:
        print(f"Storage error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

### With Litestar

Integrate validation into a Litestar application with dependency injection:

```python
"""Litestar application with file upload validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
import uuid

from litestar import Litestar, post, Response
from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.exceptions import ClientException
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_413_REQUEST_ENTITY_TOO_LARGE

from litestar_storages import (
    FileSystemStorage,
    FileSystemConfig,
    Storage,
    StoredFile,
    StorageError,
)
from litestar_storages.contrib.plugin import StoragePlugin

# Assume FileValidator and ValidationError classes are imported


# Response DTO
@dataclass
class UploadResponse:
    """Response for successful upload."""

    key: str
    size: int
    content_type: str
    url: str


# Dependency providers
def provide_validator() -> FileValidator:
    """Provide configured file validator."""
    return FileValidator(
        allowed_types={"image/jpeg", "image/png", "image/gif", "image/webp"},
        allowed_extensions={".jpg", ".jpeg", ".png", ".gif", ".webp"},
        max_size=10 * 1024 * 1024,  # 10MB
    )


# Route handlers
@post("/upload")
async def upload_image(
    data: UploadFile,
    storage: Storage,
    validator: Annotated[FileValidator, Provide(provide_validator)],
) -> UploadResponse:
    """Upload an image with validation.

    Args:
        data: Uploaded file
        storage: Injected storage backend
        validator: Injected file validator

    Returns:
        Upload response with file metadata

    Raises:
        ClientException: If validation fails
    """
    # Read file content
    content = await data.read()
    filename = data.filename or "unknown"

    try:
        # Validate
        content_type = validator.validate(content, filename)
    except ValidationError as e:
        if "too large" in e.message.lower():
            raise ClientException(
                detail=e.message,
                status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            ) from e
        raise ClientException(
            detail=e.message,
            status_code=HTTP_400_BAD_REQUEST,
        ) from e

    # Generate storage key
    ext = Path(filename).suffix.lower()
    key = f"images/{uuid.uuid4()}{ext}"

    try:
        # Store file
        stored = await storage.put(
            key=key,
            data=content,
            content_type=content_type,
            metadata={"original_filename": filename},
        )

        # Generate URL
        url = await storage.url(key)

        return UploadResponse(
            key=stored.key,
            size=stored.size,
            content_type=stored.content_type or content_type,
            url=url,
        )

    except StorageError as e:
        raise ClientException(
            detail="Failed to store file",
            status_code=HTTP_400_BAD_REQUEST,
        ) from e


@post("/upload/documents")
async def upload_document(
    data: UploadFile,
    storage: Storage,
) -> UploadResponse:
    """Upload a document with different validation rules.

    Demonstrates using different validators for different endpoints.
    """
    # Document-specific validator
    validator = FileValidator(
        allowed_types={
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
        },
        allowed_extensions={".pdf", ".doc", ".docx", ".txt"},
        max_size=50 * 1024 * 1024,  # 50MB for documents
    )

    content = await data.read()
    filename = data.filename or "document"

    try:
        content_type = validator.validate(content, filename)
    except ValidationError as e:
        raise ClientException(detail=e.message, status_code=HTTP_400_BAD_REQUEST) from e

    ext = Path(filename).suffix.lower()
    key = f"documents/{uuid.uuid4()}{ext}"

    stored = await storage.put(key=key, data=content, content_type=content_type)
    url = await storage.url(key)

    return UploadResponse(
        key=stored.key,
        size=stored.size,
        content_type=stored.content_type or content_type,
        url=url,
    )


# Application setup
storage = FileSystemStorage(
    config=FileSystemConfig(
        path=Path("./uploads"),
        base_url="/files",
        create_dirs=True,
    )
)

app = Litestar(
    route_handlers=[upload_image, upload_document],
    plugins=[StoragePlugin(default=storage)],
)
```

### Testing the Validation

```python
"""Test file upload validation."""

import pytest
from pathlib import Path

# Assume FileValidator and ValidationError are imported


class TestFileValidator:
    """Tests for FileValidator."""

    def test_validate_size_too_large(self) -> None:
        """Test rejection of oversized files."""
        validator = FileValidator(max_size=100)

        with pytest.raises(ValidationError) as exc_info:
            validator.validate_size(b"x" * 101)

        assert "too large" in exc_info.value.message.lower()

    def test_validate_size_too_small(self) -> None:
        """Test rejection of empty files."""
        validator = FileValidator(min_size=1)

        with pytest.raises(ValidationError) as exc_info:
            validator.validate_size(b"")

        assert "too small" in exc_info.value.message.lower()

    def test_validate_extension_not_allowed(self) -> None:
        """Test rejection of disallowed extensions."""
        validator = FileValidator(allowed_extensions={".jpg", ".png"})

        with pytest.raises(ValidationError) as exc_info:
            validator.validate_extension("malware.exe")

        assert "not allowed" in exc_info.value.message.lower()

    def test_validate_extension_allowed(self) -> None:
        """Test acceptance of allowed extensions."""
        validator = FileValidator(allowed_extensions={".jpg", ".png"})

        # Should not raise
        validator.validate_extension("photo.jpg")
        validator.validate_extension("image.PNG")  # Case insensitive

    def test_validate_mime_type_mismatch(self) -> None:
        """Test detection of disguised files."""
        validator = FileValidator(
            allowed_types={"image/jpeg"},
            require_magic=False,  # Use extension-based for test
        )

        # Executable content with .jpg extension
        # In production with magic=True, this would detect the real type
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_mime_type(b"MZ\x90\x00", "malware.exe")

        assert "not allowed" in exc_info.value.message.lower()

    def test_full_validation_success(self) -> None:
        """Test successful validation."""
        validator = FileValidator(
            allowed_types={"image/png"},
            allowed_extensions={".png"},
            max_size=1000,
            require_magic=False,
        )

        # PNG magic bytes
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50

        result = validator.validate(png_data, "test.png")
        assert result == "image/png"
```

## Key Points

- **Validate early**: Check files before storing to avoid wasting storage and bandwidth
- **Use magic bytes**: Don't trust file extensions alone; use python-magic for accurate MIME detection
- **Set reasonable limits**: Configure size limits appropriate for your use case
- **Provide clear errors**: Return specific validation error messages to help users
- **Generate safe keys**: Never use user-provided filenames directly as storage keys
- **Separate concerns**: Keep validation logic reusable and independent of storage backend

## Security Considerations

1. **Never trust client-provided content types** - Always detect MIME type server-side
2. **Use allowlists, not blocklists** - Specify what's allowed, not what's forbidden
3. **Limit file sizes** - Prevent denial of service through resource exhaustion
4. **Sanitize filenames** - Generate unique keys instead of using original filenames
5. **Consider virus scanning** - For high-risk applications, integrate malware scanning

## Related

- [Streaming Large Files](streaming-large-files.md) - For handling files too large to load into memory
- [Image Processing Pipeline](image-processing-pipeline.md) - Validate and process images together
- [Multi-Backend Configuration](multi-backend-config.md) - Different validation rules per environment
