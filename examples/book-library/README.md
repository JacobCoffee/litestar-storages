# Book Library - Litestar Storage Example

A complete example demonstrating file storage in Litestar using `litestar-storages`.

## Features

- **Book Management**: Create books with cover images
- **Author Management**: Create authors with profile photos
- **Multiple Named Storages**: Separate storage backends for covers vs photos
- **File Upload/Download**: Upload images and serve them back
- **Error Handling**: Proper 404s and validation

## Architecture

- **MemoryStorage**: In-memory storage for easy testing (no external dependencies)
- **StoragePlugin**: Litestar plugin with dependency injection
- **Named Storages**:
  - `covers` - Book cover images
  - `photos` - Author profile photos

## Installation

```bash
# From the root of litestar-storages repository
uv sync --all-extras

# Or install just the example dependencies
cd examples/book-library
uv pip install -e .
```

## Running the Application

```bash
# From examples/book-library directory
uv run litestar run --app app:app --reload

# Or from repository root
uv run python examples/book-library/app.py
```

The application will be available at: http://localhost:8000

## API Endpoints

### Books

- `POST /books` - Create a book with cover image
- `GET /books` - List all books
- `GET /books/{book_id}` - Get book details
- `GET /books/{book_id}/cover` - Download book cover image
- `DELETE /books/{book_id}` - Delete book and its cover

### Authors

- `POST /authors` - Create an author with profile photo
- `GET /authors` - List all authors
- `GET /authors/{author_id}` - Get author details
- `GET /authors/{author_id}/photo` - Download author photo
- `DELETE /authors/{author_id}` - Delete author and their photo

## Example Usage

### Upload a Book with Cover

```bash
curl -X POST http://localhost:8000/books \
  -F "title=The Python Guide" \
  -F "author=Guido van Rossum" \
  -F "isbn=978-0-123456-78-9" \
  -F "cover_image=@/path/to/cover.jpg"
```

### List Books

```bash
curl http://localhost:8000/books
```

### Download Cover Image

```bash
curl http://localhost:8000/books/1/cover --output cover.jpg
```

### Upload an Author with Photo

```bash
curl -X POST http://localhost:8000/authors \
  -F "name=Guido van Rossum" \
  -F "bio=Creator of Python" \
  -F "photo=@/path/to/photo.jpg"
```

### Download Author Photo

```bash
curl http://localhost:8000/authors/1/photo --output photo.jpg
```

## Running Tests

```bash
# From examples/book-library directory
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=. --cov-report=term-missing
```

## Key Concepts Demonstrated

### 1. Multiple Named Storages

```python
StoragePlugin(
    storages={
        "covers": MemoryStorage(),
        "photos": MemoryStorage(),
    }
)
```

### 2. Dependency Injection

```python
async def create_book(
    storage: Annotated[Storage, Dependency(skip_validation=True)],
    data: BookCreate,
) -> Book:
    ...
```

### 3. File Upload

```python
class BookCreate:
    title: str
    author: str
    isbn: str
    cover_image: UploadFile
```

### 4. File Streaming

```python
@get("/books/{book_id:int}/cover")
async def download_cover(
    book_id: int,
    storage: Annotated[Storage, Dependency(skip_validation=True)],
) -> Stream:
    stored_file = await storage.retrieve(book.cover_path)
    return Stream(stored_file.file)
```

### 5. Error Handling

```python
try:
    await storage.retrieve(path)
except StorageFileNotFoundError:
    raise NotFoundException(detail="Cover image not found")
```

## Architecture Notes

- **In-Memory Storage**: Data is lost on restart (use FileSystemStorage for persistence)
- **No Database**: Using in-memory lists (add SQLAlchemy for real apps)
- **Simple IDs**: Integer counters (use UUIDs in production)
- **No Authentication**: Add auth guards for production use

## Next Steps

To make this production-ready:

1. Replace MemoryStorage with FileSystemStorage or S3Storage
2. Add a proper database (SQLAlchemy + PostgreSQL)
3. Implement authentication and authorization
4. Add image validation (file type, size limits)
5. Implement pagination for list endpoints
6. Add image thumbnails/resizing
7. Implement proper logging and monitoring
