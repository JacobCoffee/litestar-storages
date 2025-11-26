# Todo Attachments Example

A complete Litestar application demonstrating file storage capabilities with a Todo app that supports file attachments.

## Features

- Create, list, and delete todos
- Upload file attachments to todos
- Download attachments
- Delete individual attachments
- Cascade deletion (deleting a todo deletes all its attachments)
- In-memory storage for simplicity (easy to swap for S3, GCS, Azure, etc.)

## Installation

From the example directory:

```bash
# Install dependencies using uv
uv pip install -e .

# Or install with dev dependencies
uv pip install -e ".[dev]"
```

## Running the Application

```bash
# Using uvicorn directly
uv run uvicorn app:app --reload

# Or using the Python module
uv run python -m app
```

The API will be available at `http://localhost:8000`.

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/schema`
- OpenAPI JSON: `http://localhost:8000/schema/openapi.json`

## API Endpoints

### Todos

#### List all todos
```bash
GET /todos
```

#### Create a todo
```bash
POST /todos
Content-Type: application/json

{
  "title": "My Todo",
  "description": "Optional description"
}
```

#### Get a specific todo
```bash
GET /todos/{todo_id}
```

#### Delete a todo (and all its attachments)
```bash
DELETE /todos/{todo_id}
```

### Attachments

#### List attachments for a todo
```bash
GET /todos/{todo_id}/attachments
```

#### Upload an attachment
```bash
POST /todos/{todo_id}/attachments
Content-Type: multipart/form-data

file: <file to upload>
```

#### Download an attachment
```bash
GET /todos/{todo_id}/attachments/{attachment_id}
```

#### Delete an attachment
```bash
DELETE /todos/{todo_id}/attachments/{attachment_id}
```

## Example Usage

### Using cURL

```bash
# Create a todo
TODO_ID=$(curl -X POST http://localhost:8000/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Review documents", "description": "Check the uploaded files"}' \
  | jq -r '.id')

# Upload an attachment
curl -X POST "http://localhost:8000/todos/${TODO_ID}/attachments" \
  -F "file=@document.pdf"

# List attachments
curl "http://localhost:8000/todos/${TODO_ID}/attachments"

# Download an attachment (replace ATTACHMENT_ID)
curl "http://localhost:8000/todos/${TODO_ID}/attachments/ATTACHMENT_ID" \
  -o downloaded-file.pdf

# Delete an attachment
curl -X DELETE "http://localhost:8000/todos/${TODO_ID}/attachments/ATTACHMENT_ID"

# Delete the todo (cascades to all attachments)
curl -X DELETE "http://localhost:8000/todos/${TODO_ID}"
```

### Using Python httpx

```python
import httpx

client = httpx.Client(base_url="http://localhost:8000")

# Create a todo
response = client.post("/todos", json={
    "title": "Review documents",
    "description": "Check the uploaded files"
})
todo = response.json()
todo_id = todo["id"]

# Upload an attachment
with open("document.pdf", "rb") as f:
    response = client.post(
        f"/todos/{todo_id}/attachments",
        files={"file": ("document.pdf", f, "application/pdf")}
    )
attachment = response.json()

# List attachments
response = client.get(f"/todos/{todo_id}/attachments")
attachments = response.json()

# Download an attachment
attachment_id = attachment["id"]
response = client.get(f"/todos/{todo_id}/attachments/{attachment_id}")
with open("downloaded.pdf", "wb") as f:
    f.write(response.content)

# Delete the todo and all attachments
client.delete(f"/todos/{todo_id}")
```

## Running Tests

```bash
# Run tests with pytest
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ --cov=. --cov-report=term-missing
```

## Architecture

### Storage Backend

This example uses `MemoryStorage` for simplicity. In production, you can easily swap it out:

```python
# S3
from litestar_storages import S3Storage

def provide_storage() -> Storage:
    return S3Storage(
        bucket_name="my-bucket",
        region_name="us-east-1",
    )

# Google Cloud Storage
from litestar_storages import GCSStorage

def provide_storage() -> Storage:
    return GCSStorage(
        bucket_name="my-bucket",
        project="my-project",
    )

# Azure Blob Storage
from litestar_storages import AzureStorage

def provide_storage() -> Storage:
    return AzureStorage(
        container_name="my-container",
        connection_string="...",
    )

# Filesystem
from litestar_storages import FilesystemStorage

def provide_storage() -> Storage:
    return FilesystemStorage(base_path="/var/uploads")
```

### File Lifecycle

1. **Upload**: File is stored with path `todos/{todo_id}/{filename}`
2. **Metadata**: Attachment record links file to todo with metadata
3. **Download**: Stream file from storage with original filename
4. **Delete**: Remove from both storage and metadata
5. **Cascade**: Deleting a todo deletes all associated attachments

### Error Handling

- `404 Not Found`: Todo or attachment doesn't exist
- `400 Bad Request`: Invalid request data
- `500 Internal Server Error`: Storage or server errors

## Key Concepts Demonstrated

1. **Dependency Injection**: Storage instance provided via DI
2. **File Uploads**: Handling multipart form data with UploadFile
3. **Streaming Downloads**: Efficient file streaming with proper headers
4. **Cascade Deletion**: Cleaning up related resources
5. **Storage Abstraction**: Backend-agnostic file operations
6. **Error Handling**: Proper HTTP error responses

## Next Steps

- Add authentication/authorization
- Implement file size limits
- Add file type validation
- Support multiple files per upload
- Add pagination for large attachment lists
- Implement file versioning
- Add thumbnail generation for images
- Use a real database (PostgreSQL, SQLite, etc.)
