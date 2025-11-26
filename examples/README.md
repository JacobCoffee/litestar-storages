# Examples

Example Litestar applications demonstrating litestar-storages integration.

## Minimal Example

A bare-bones example showing the simplest possible integration.

```bash
cd examples/minimal
uv run litestar run
```

Features:
- Single memory storage backend
- Upload, download, and list endpoints
- ~40 lines of code

**Endpoints:**
- `POST /upload` - Upload a file
- `GET /files/{key}` - Download a file
- `GET /files` - List all files

## Full-Featured Example

A production-style example demonstrating advanced patterns.

```bash
cd examples/full_featured
uv run litestar run
```

Features:
- Multiple named storage backends (images, documents)
- Controller-based route organization
- DTO responses for clean API output
- Custom exception handlers (404, 409)
- Streaming file downloads
- Presigned URL generation
- Content-type validation

**Endpoints:**

Images (`/api/images`):
- `POST /api/images/` - Upload an image
- `GET /api/images/` - List all images
- `GET /api/images/{key}` - Get image metadata
- `GET /api/images/{key}/download` - Download image
- `DELETE /api/images/{key}` - Delete image

Documents (`/api/documents`):
- `POST /api/documents/` - Upload a document
- `GET /api/documents/` - List all documents
- `GET /api/documents/{key}` - Get document metadata
- `GET /api/documents/{key}/download` - Download document
- `GET /api/documents/{key}/url` - Get presigned URL
- `DELETE /api/documents/{key}` - Delete document

## Testing the Examples

Upload a file:
```bash
curl -X POST -F "data=@myfile.txt" http://localhost:8000/upload
```

List files:
```bash
curl http://localhost:8000/files
```

Download a file:
```bash
curl http://localhost:8000/files/myfile.txt -o downloaded.txt
```
