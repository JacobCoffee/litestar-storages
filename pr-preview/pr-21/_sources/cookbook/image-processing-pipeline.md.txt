# Image Processing Pipeline

Resize and compress images on upload, generating thumbnails and optimized variants. This recipe shows how to integrate Pillow with litestar-storages for a complete image processing workflow.

## Prerequisites

- Python 3.9+
- litestar-storages installed (`pip install litestar-storages`)
- Pillow for image processing (`pip install Pillow`)
- For Litestar examples: `pip install litestar-storages[litestar]`

## The Problem

Raw image uploads from users are often:

- Too large for efficient delivery (multi-megabyte photos)
- Wrong dimensions for your UI (need thumbnails)
- Unoptimized format (BMP when WebP would be smaller)
- Missing responsive variants (mobile vs desktop)

Processing images on upload creates optimized variants once, reducing bandwidth and improving user experience.

## Solution

### Image Processor Class

Create a reusable image processor that generates multiple variants:

```python
"""Image processing utilities for upload pipelines."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple

from PIL import Image


class ImageFormat(str, Enum):
    """Supported output image formats."""

    JPEG = "JPEG"
    PNG = "PNG"
    WEBP = "WEBP"
    GIF = "GIF"


class ImageVariant(NamedTuple):
    """Represents a processed image variant."""

    name: str           # e.g., "thumbnail", "medium", "original"
    data: bytes         # Processed image bytes
    width: int          # Actual width after processing
    height: int         # Actual height after processing
    format: ImageFormat # Output format
    content_type: str   # MIME type


@dataclass
class VariantConfig:
    """Configuration for an image variant.

    Attributes:
        name: Variant identifier (used in storage key)
        max_width: Maximum width in pixels (None for no limit)
        max_height: Maximum height in pixels (None for no limit)
        quality: JPEG/WebP quality (1-100)
        format: Output format (None to preserve original)
    """

    name: str
    max_width: int | None = None
    max_height: int | None = None
    quality: int = 85
    format: ImageFormat | None = None


@dataclass
class ImageProcessor:
    """Process images into multiple variants.

    Attributes:
        variants: List of variant configurations to generate
        preserve_original: Whether to keep the unmodified original
        strip_metadata: Remove EXIF and other metadata for privacy
        background_color: Color for transparency replacement (JPEG)
    """

    variants: list[VariantConfig] = field(default_factory=lambda: [
        VariantConfig(name="thumbnail", max_width=150, max_height=150, quality=80),
        VariantConfig(name="medium", max_width=800, max_height=800, quality=85),
        VariantConfig(name="large", max_width=1920, max_height=1920, quality=90),
    ])
    preserve_original: bool = True
    strip_metadata: bool = True
    background_color: tuple[int, int, int] = (255, 255, 255)  # White

    def _get_content_type(self, fmt: ImageFormat) -> str:
        """Get MIME type for format."""
        return {
            ImageFormat.JPEG: "image/jpeg",
            ImageFormat.PNG: "image/png",
            ImageFormat.WEBP: "image/webp",
            ImageFormat.GIF: "image/gif",
        }[fmt]

    def _detect_format(self, img: Image.Image) -> ImageFormat:
        """Detect the original image format."""
        fmt = img.format or "JPEG"
        try:
            return ImageFormat(fmt.upper())
        except ValueError:
            return ImageFormat.JPEG

    def _prepare_for_save(
        self,
        img: Image.Image,
        target_format: ImageFormat,
    ) -> Image.Image:
        """Prepare image for saving in target format.

        Handles mode conversion (e.g., RGBA to RGB for JPEG).
        """
        if target_format == ImageFormat.JPEG:
            # JPEG doesn't support transparency
            if img.mode in ("RGBA", "LA", "P"):
                # Create white background
                background = Image.new("RGB", img.size, self.background_color)
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1])  # Use alpha as mask
                return background
            elif img.mode != "RGB":
                return img.convert("RGB")

        elif target_format == ImageFormat.PNG:
            if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                return img.convert("RGBA")

        elif target_format == ImageFormat.WEBP:
            if img.mode not in ("RGB", "RGBA"):
                return img.convert("RGBA")

        return img

    def _resize_image(
        self,
        img: Image.Image,
        max_width: int | None,
        max_height: int | None,
    ) -> Image.Image:
        """Resize image maintaining aspect ratio.

        Uses high-quality Lanczos resampling.
        """
        if max_width is None and max_height is None:
            return img

        original_width, original_height = img.size

        # Calculate new dimensions maintaining aspect ratio
        if max_width and max_height:
            # Fit within both constraints
            ratio = min(
                max_width / original_width,
                max_height / original_height,
            )
        elif max_width:
            ratio = max_width / original_width
        else:
            ratio = max_height / original_height  # type: ignore

        # Don't upscale
        if ratio >= 1:
            return img

        new_width = int(original_width * ratio)
        new_height = int(original_height * ratio)

        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def _save_image(
        self,
        img: Image.Image,
        fmt: ImageFormat,
        quality: int,
    ) -> bytes:
        """Save image to bytes with specified format and quality."""
        buffer = io.BytesIO()

        # Prepare image for target format
        img = self._prepare_for_save(img, fmt)

        # Build save kwargs
        save_kwargs: dict = {"format": fmt.value}

        if fmt in (ImageFormat.JPEG, ImageFormat.WEBP):
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True

        if fmt == ImageFormat.JPEG:
            save_kwargs["progressive"] = True

        if fmt == ImageFormat.PNG:
            save_kwargs["optimize"] = True

        if fmt == ImageFormat.WEBP:
            save_kwargs["method"] = 6  # Best compression

        img.save(buffer, **save_kwargs)
        return buffer.getvalue()

    def process(self, data: bytes) -> list[ImageVariant]:
        """Process image into configured variants.

        Args:
            data: Raw image bytes

        Returns:
            List of processed image variants

        Raises:
            ValueError: If image cannot be processed
        """
        try:
            img = Image.open(io.BytesIO(data))
        except Exception as e:
            raise ValueError(f"Invalid image data: {e}") from e

        # Detect original format
        original_format = self._detect_format(img)

        # Strip metadata if requested
        if self.strip_metadata:
            # Create a clean copy without metadata
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(list(img.getdata()))
            img = clean_img

        variants: list[ImageVariant] = []

        # Optionally preserve original
        if self.preserve_original:
            variants.append(ImageVariant(
                name="original",
                data=data,  # Keep original bytes
                width=img.size[0],
                height=img.size[1],
                format=original_format,
                content_type=self._get_content_type(original_format),
            ))

        # Generate configured variants
        for config in self.variants:
            # Resize
            resized = self._resize_image(img, config.max_width, config.max_height)

            # Determine output format
            output_format = config.format or original_format

            # Save to bytes
            processed_data = self._save_image(resized, output_format, config.quality)

            variants.append(ImageVariant(
                name=config.name,
                data=processed_data,
                width=resized.size[0],
                height=resized.size[1],
                format=output_format,
                content_type=self._get_content_type(output_format),
            ))

        return variants
```

### Framework-Agnostic Usage

Process and store image variants with any storage backend:

```python
"""Framework-agnostic image processing pipeline."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
import uuid

from litestar_storages import (
    FileSystemStorage,
    FileSystemConfig,
    StoredFile,
)

# Assume ImageProcessor and ImageVariant are imported from above


@dataclass
class ProcessedImage:
    """Result of processing and storing an image."""

    id: str  # Unique identifier for all variants
    variants: dict[str, StoredFile]  # variant_name -> StoredFile


async def process_and_store(
    storage: FileSystemStorage,
    processor: ImageProcessor,
    data: bytes,
    base_key: str | None = None,
) -> ProcessedImage:
    """Process an image and store all variants.

    Args:
        storage: Storage backend
        processor: Image processor with variant configs
        data: Raw image bytes
        base_key: Optional base key (defaults to UUID)

    Returns:
        ProcessedImage with all stored variants
    """
    # Generate unique ID
    image_id = base_key or str(uuid.uuid4())

    # Process image
    variants = processor.process(data)

    # Store each variant
    stored: dict[str, StoredFile] = {}

    for variant in variants:
        # Generate key: images/{id}/{variant_name}.{ext}
        ext = {
            "JPEG": "jpg",
            "PNG": "png",
            "WEBP": "webp",
            "GIF": "gif",
        }[variant.format.value]

        key = f"images/{image_id}/{variant.name}.{ext}"

        stored[variant.name] = await storage.put(
            key=key,
            data=variant.data,
            content_type=variant.content_type,
            metadata={
                "width": str(variant.width),
                "height": str(variant.height),
                "variant": variant.name,
            },
        )

    return ProcessedImage(id=image_id, variants=stored)


async def get_variant_url(
    storage: FileSystemStorage,
    image_id: str,
    variant: str = "medium",
) -> str | None:
    """Get URL for a specific image variant.

    Args:
        storage: Storage backend
        image_id: Image identifier
        variant: Variant name (thumbnail, medium, large, original)

    Returns:
        URL if variant exists, None otherwise
    """
    # Try common extensions
    for ext in ["jpg", "png", "webp", "gif"]:
        key = f"images/{image_id}/{variant}.{ext}"
        if await storage.exists(key):
            return await storage.url(key)

    return None


async def main() -> None:
    """Example usage."""
    # Configure storage
    storage = FileSystemStorage(
        config=FileSystemConfig(
            path=Path("./uploads"),
            base_url="https://cdn.example.com",
            create_dirs=True,
        )
    )

    # Configure processor with WebP output for smaller files
    processor = ImageProcessor(
        variants=[
            VariantConfig(
                name="thumbnail",
                max_width=150,
                max_height=150,
                quality=80,
                format=ImageFormat.WEBP,
            ),
            VariantConfig(
                name="preview",
                max_width=400,
                max_height=400,
                quality=85,
                format=ImageFormat.WEBP,
            ),
            VariantConfig(
                name="full",
                max_width=1920,
                max_height=1080,
                quality=90,
            ),  # Preserve original format
        ],
        preserve_original=True,
        strip_metadata=True,
    )

    # Load a test image (in real usage, from upload)
    test_image_path = Path("test_image.jpg")
    if test_image_path.exists():
        image_data = test_image_path.read_bytes()
    else:
        # Create a simple test image with Pillow
        from PIL import Image
        import io

        img = Image.new("RGB", (800, 600), color="blue")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        image_data = buffer.getvalue()

    # Process and store
    result = await process_and_store(storage, processor, image_data)

    print(f"Image ID: {result.id}")
    print("Variants:")
    for name, stored in result.variants.items():
        url = await storage.url(stored.key)
        print(f"  {name}: {stored.size} bytes - {url}")


if __name__ == "__main__":
    asyncio.run(main())
```

### With Litestar

Build a complete image upload API with Litestar:

```python
"""Litestar application with image processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
import uuid

from litestar import Litestar, post, get, Response
from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.exceptions import ClientException, NotFoundException
from litestar.status_codes import HTTP_400_BAD_REQUEST

from litestar_storages import (
    S3Storage,
    S3Config,
    Storage,
    StorageFileNotFoundError,
)
from litestar_storages.contrib.plugin import StoragePlugin

# Assume ImageProcessor, VariantConfig, ImageFormat are imported


# Response DTOs
@dataclass
class ImageVariantResponse:
    """Single variant info."""

    name: str
    url: str
    width: int
    height: int
    size: int


@dataclass
class UploadImageResponse:
    """Response for image upload."""

    id: str
    variants: list[ImageVariantResponse]


@dataclass
class ImageInfoResponse:
    """Response for image info lookup."""

    id: str
    variants: list[ImageVariantResponse]


# Dependency providers
def provide_processor() -> ImageProcessor:
    """Provide configured image processor."""
    return ImageProcessor(
        variants=[
            VariantConfig(
                name="thumb",
                max_width=150,
                max_height=150,
                quality=80,
                format=ImageFormat.WEBP,
            ),
            VariantConfig(
                name="medium",
                max_width=600,
                max_height=600,
                quality=85,
                format=ImageFormat.WEBP,
            ),
            VariantConfig(
                name="large",
                max_width=1200,
                max_height=1200,
                quality=90,
            ),
        ],
        preserve_original=True,
        strip_metadata=True,
    )


# Validation
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_SIZE = 20 * 1024 * 1024  # 20MB


def validate_image_upload(content_type: str | None, size: int) -> None:
    """Validate image upload before processing."""
    if content_type and content_type not in ALLOWED_TYPES:
        raise ClientException(
            detail=f"Invalid image type. Allowed: {', '.join(ALLOWED_TYPES)}",
            status_code=HTTP_400_BAD_REQUEST,
        )

    if size > MAX_SIZE:
        raise ClientException(
            detail=f"Image too large. Maximum: {MAX_SIZE // (1024 * 1024)}MB",
            status_code=HTTP_400_BAD_REQUEST,
        )


# Route handlers
@post("/images")
async def upload_image(
    data: UploadFile,
    storage: Storage,
    processor: Annotated[ImageProcessor, Provide(provide_processor)],
) -> UploadImageResponse:
    """Upload and process an image.

    Creates multiple optimized variants:
    - thumb: 150x150 WebP thumbnail
    - medium: 600x600 WebP preview
    - large: 1200x1200 original format
    - original: Unmodified upload
    """
    content = await data.read()

    # Validate
    validate_image_upload(data.content_type, len(content))

    # Process
    try:
        variants = processor.process(content)
    except ValueError as e:
        raise ClientException(
            detail=str(e),
            status_code=HTTP_400_BAD_REQUEST,
        ) from e

    # Generate unique ID
    image_id = str(uuid.uuid4())

    # Store variants and collect responses
    variant_responses: list[ImageVariantResponse] = []

    for variant in variants:
        ext = variant.format.value.lower()
        if ext == "jpeg":
            ext = "jpg"

        key = f"images/{image_id}/{variant.name}.{ext}"

        stored = await storage.put(
            key=key,
            data=variant.data,
            content_type=variant.content_type,
            metadata={
                "width": str(variant.width),
                "height": str(variant.height),
            },
        )

        url = await storage.url(key)

        variant_responses.append(ImageVariantResponse(
            name=variant.name,
            url=url,
            width=variant.width,
            height=variant.height,
            size=stored.size,
        ))

    return UploadImageResponse(id=image_id, variants=variant_responses)


@get("/images/{image_id:str}")
async def get_image_info(
    image_id: str,
    storage: Storage,
) -> ImageInfoResponse:
    """Get info about an uploaded image and its variants."""
    variants: list[ImageVariantResponse] = []

    # Check for known variant names
    variant_names = ["thumb", "medium", "large", "original"]
    extensions = ["webp", "jpg", "png", "gif"]

    found_any = False

    for name in variant_names:
        for ext in extensions:
            key = f"images/{image_id}/{name}.{ext}"
            try:
                info = await storage.info(key)
                url = await storage.url(key)

                # Parse dimensions from metadata
                width = int(info.metadata.get("width", 0))
                height = int(info.metadata.get("height", 0))

                variants.append(ImageVariantResponse(
                    name=name,
                    url=url,
                    width=width,
                    height=height,
                    size=info.size,
                ))
                found_any = True
                break  # Found this variant, move to next
            except StorageFileNotFoundError:
                continue

    if not found_any:
        raise NotFoundException(detail=f"Image not found: {image_id}")

    return ImageInfoResponse(id=image_id, variants=variants)


@get("/images/{image_id:str}/{variant:str}")
async def get_image_variant(
    image_id: str,
    variant: str,
    storage: Storage,
) -> Response:
    """Redirect to a specific image variant.

    Args:
        image_id: Image identifier
        variant: Variant name (thumb, medium, large, original)
    """
    extensions = ["webp", "jpg", "png", "gif"]

    for ext in extensions:
        key = f"images/{image_id}/{variant}.{ext}"
        if await storage.exists(key):
            url = await storage.url(key)
            return Response(
                content=None,
                status_code=302,
                headers={"Location": url},
            )

    raise NotFoundException(detail=f"Variant not found: {variant}")


# Application setup
def create_app() -> Litestar:
    """Create Litestar application with storage plugin."""
    # Configure storage (use environment variables in production)
    import os

    if os.getenv("USE_S3"):
        storage: Storage = S3Storage(
            config=S3Config(
                bucket=os.getenv("S3_BUCKET", "images"),
                region=os.getenv("AWS_REGION", "us-east-1"),
            )
        )
    else:
        from litestar_storages import FileSystemStorage, FileSystemConfig
        storage = FileSystemStorage(
            config=FileSystemConfig(
                path=Path("./uploads"),
                base_url="/files",
                create_dirs=True,
            )
        )

    return Litestar(
        route_handlers=[upload_image, get_image_info, get_image_variant],
        plugins=[StoragePlugin(default=storage)],
    )


app = create_app()
```

### Async Processing with Background Tasks

For high-volume applications, process images in the background:

```python
"""Background image processing with task queue."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import uuid

from litestar import Litestar, post
from litestar.datastructures import UploadFile
from litestar.response import Response

from litestar_storages import (
    MemoryStorage,
    MemoryConfig,
    Storage,
    StoredFile,
)
from litestar_storages.contrib.plugin import StoragePlugin

# Assume ImageProcessor is imported


@dataclass
class ProcessingJob:
    """Represents an image processing job."""

    id: str
    raw_key: str
    status: str  # pending, processing, complete, failed
    error: str | None = None


# Simple in-memory job queue (use Redis/RabbitMQ in production)
_jobs: dict[str, ProcessingJob] = {}
_queue: asyncio.Queue[str] = asyncio.Queue()


async def process_image_job(
    storage: Storage,
    processor: ImageProcessor,
    job_id: str,
) -> None:
    """Process a single image job."""
    job = _jobs.get(job_id)
    if not job:
        return

    job.status = "processing"

    try:
        # Get raw image
        data = await storage.get_bytes(job.raw_key)

        # Process variants
        variants = processor.process(data)

        # Store variants
        for variant in variants:
            ext = variant.format.value.lower()
            if ext == "jpeg":
                ext = "jpg"

            key = f"processed/{job_id}/{variant.name}.{ext}"
            await storage.put(
                key=key,
                data=variant.data,
                content_type=variant.content_type,
            )

        # Clean up raw upload
        await storage.delete(job.raw_key)

        job.status = "complete"

    except Exception as e:
        job.status = "failed"
        job.error = str(e)


async def worker(storage: Storage, processor: ImageProcessor) -> None:
    """Background worker that processes image jobs."""
    while True:
        job_id = await _queue.get()
        try:
            await process_image_job(storage, processor, job_id)
        except Exception:
            pass  # Error already recorded in job
        finally:
            _queue.task_done()


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    """Manage background worker lifecycle."""
    storage = app.state["storage"]
    processor = ImageProcessor()

    # Start worker
    task = asyncio.create_task(worker(storage, processor))

    yield

    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@post("/images/async")
async def upload_image_async(
    data: UploadFile,
    storage: Storage,
) -> dict[str, Any]:
    """Upload image for background processing.

    Returns immediately with job ID for status polling.
    """
    content = await data.read()
    job_id = str(uuid.uuid4())

    # Store raw upload
    raw_key = f"raw/{job_id}"
    await storage.put(key=raw_key, data=content, content_type=data.content_type)

    # Create job
    job = ProcessingJob(id=job_id, raw_key=raw_key, status="pending")
    _jobs[job_id] = job

    # Queue for processing
    await _queue.put(job_id)

    return {
        "job_id": job_id,
        "status": "pending",
        "poll_url": f"/images/jobs/{job_id}",
    }
```

## Key Points

- **Process once, serve forever**: Generate all needed variants at upload time
- **Use appropriate formats**: WebP for web delivery, JPEG for photos, PNG for graphics
- **Strip metadata**: Remove EXIF data for privacy (unless explicitly needed)
- **Set quality levels**: Balance file size vs visual quality (80-90 is usually fine)
- **Handle failures gracefully**: Keep originals until processing succeeds
- **Consider background processing**: For high-volume applications, use task queues

## Performance Tips

1. **Use WebP**: 25-35% smaller than JPEG at equivalent quality
2. **Progressive JPEG**: Better perceived loading for larger images
3. **Lazy loading**: Process variants on-demand for rarely accessed images
4. **CDN integration**: Cache processed images at the edge
5. **Memory limits**: Process large images in chunks or use separate workers

## Related

- [File Upload with Validation](file-upload-validation.md) - Validate before processing
- [Streaming Large Files](streaming-large-files.md) - Handle very large images
- [Multi-Backend Configuration](multi-backend-config.md) - Store processed images in cloud storage
