"""Route controllers for the book library application."""

from __future__ import annotations

from typing import Annotated

from litestar import Controller, delete, get, post
from litestar.enums import RequestEncodingType
from litestar.exceptions import NotFoundException
from litestar.params import Body
from litestar.response import Stream
from litestar.status_codes import HTTP_200_OK

from litestar_storages import Storage

from models import (
    Author,
    AuthorCreate,
    AuthorResponse,
    Book,
    BookCreate,
    BookResponse,
)

# In-memory "database" for the example
books_db: dict[int, Book] = {}
authors_db: dict[int, Author] = {}


class BookController(Controller):
    """Controller for book management endpoints."""

    path = "/books"

    @post("/")
    async def create_book(
        self,
        covers_storage: Storage,  # Injected by StoragePlugin
        data: Annotated[BookCreate, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> BookResponse:
        """Create a new book with cover image.

        Args:
            covers_storage: Injected covers storage
            data: Book data with cover image upload

        Returns:
            Created book response
        """
        # Store the cover image
        cover_filename = f"covers/{data.isbn}_{data.cover_image.filename}"
        cover_data = await data.cover_image.read()
        stored_file = await covers_storage.put(
            key=cover_filename,
            data=cover_data,
        )

        # Create book record
        book = Book.create(
            title=data.title,
            author=data.author,
            isbn=data.isbn,
            cover_path=stored_file.key,
        )
        books_db[book.id] = book

        return BookResponse.from_book(book)

    @get("/")
    async def list_books(self) -> list[BookResponse]:
        """List all books.

        Returns:
            List of all books
        """
        return [BookResponse.from_book(book) for book in books_db.values()]

    @get("/{book_id:int}")
    async def get_book(self, book_id: int) -> BookResponse:
        """Get a specific book by ID.

        Args:
            book_id: Book ID

        Returns:
            Book response

        Raises:
            NotFoundException: If book not found
        """
        book = books_db.get(book_id)
        if not book:
            raise NotFoundException(detail=f"Book {book_id} not found")

        return BookResponse.from_book(book)

    @get("/{book_id:int}/cover")
    async def download_cover(
        self,
        book_id: int,
        covers_storage: Storage,  # Injected by StoragePlugin
    ) -> Stream:
        """Download book cover image.

        Args:
            book_id: Book ID
            covers_storage: Injected covers storage

        Returns:
            Streaming response with image data

        Raises:
            NotFoundException: If book or cover not found
        """
        book = books_db.get(book_id)
        if not book or not book.cover_path:
            raise NotFoundException(detail=f"Book {book_id} or cover not found")

        # Check if file exists
        if not await covers_storage.exists(book.cover_path):
            raise NotFoundException(detail="Cover image not found")

        # Determine content type from filename
        content_type = "application/octet-stream"
        if book.cover_path.lower().endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif book.cover_path.lower().endswith(".png"):
            content_type = "image/png"
        elif book.cover_path.lower().endswith(".gif"):
            content_type = "image/gif"

        return Stream(
            content=covers_storage.get(book.cover_path),
            media_type=content_type,
        )

    @delete("/{book_id:int}", status_code=HTTP_200_OK)
    async def delete_book(
        self,
        book_id: int,
        covers_storage: Storage,  # Injected by StoragePlugin
    ) -> dict[str, str]:
        """Delete a book and its cover image.

        Args:
            book_id: Book ID
            covers_storage: Injected covers storage

        Returns:
            Success message

        Raises:
            NotFoundException: If book not found
        """
        book = books_db.get(book_id)
        if not book:
            raise NotFoundException(detail=f"Book {book_id} not found")

        # Delete cover image if exists
        if book.cover_path and await covers_storage.exists(book.cover_path):
            await covers_storage.delete(book.cover_path)

        # Delete book record
        del books_db[book_id]

        return {"message": f"Book {book_id} deleted successfully"}


class AuthorController(Controller):
    """Controller for author management endpoints."""

    path = "/authors"

    @post("/")
    async def create_author(
        self,
        photos_storage: Storage,  # Injected by StoragePlugin
        data: Annotated[AuthorCreate, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> AuthorResponse:
        """Create a new author with optional profile photo.

        Args:
            photos_storage: Injected photos storage
            data: Author data with optional photo upload

        Returns:
            Created author response
        """
        photo_path: str | None = None

        # Store the photo if provided
        if data.photo:
            photo_filename = f"photos/{data.name.replace(' ', '_')}_{data.photo.filename}"
            photo_data = await data.photo.read()
            stored_file = await photos_storage.put(
                key=photo_filename,
                data=photo_data,
            )
            photo_path = stored_file.key

        # Create author record
        author = Author.create(
            name=data.name,
            bio=data.bio,
            photo_path=photo_path,
        )
        authors_db[author.id] = author

        return AuthorResponse.from_author(author)

    @get("/")
    async def list_authors(self) -> list[AuthorResponse]:
        """List all authors.

        Returns:
            List of all authors
        """
        return [AuthorResponse.from_author(author) for author in authors_db.values()]

    @get("/{author_id:int}")
    async def get_author(self, author_id: int) -> AuthorResponse:
        """Get a specific author by ID.

        Args:
            author_id: Author ID

        Returns:
            Author response

        Raises:
            NotFoundException: If author not found
        """
        author = authors_db.get(author_id)
        if not author:
            raise NotFoundException(detail=f"Author {author_id} not found")

        return AuthorResponse.from_author(author)

    @get("/{author_id:int}/photo")
    async def download_photo(
        self,
        author_id: int,
        photos_storage: Storage,  # Injected by StoragePlugin
    ) -> Stream:
        """Download author profile photo.

        Args:
            author_id: Author ID
            photos_storage: Injected photos storage

        Returns:
            Streaming response with image data

        Raises:
            NotFoundException: If author or photo not found
        """
        author = authors_db.get(author_id)
        if not author or not author.photo_path:
            raise NotFoundException(detail=f"Author {author_id} or photo not found")

        # Check if file exists
        if not await photos_storage.exists(author.photo_path):
            raise NotFoundException(detail="Author photo not found")

        # Determine content type from filename
        content_type = "application/octet-stream"
        if author.photo_path.lower().endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif author.photo_path.lower().endswith(".png"):
            content_type = "image/png"
        elif author.photo_path.lower().endswith(".gif"):
            content_type = "image/gif"

        return Stream(
            content=photos_storage.get(author.photo_path),
            media_type=content_type,
        )

    @delete("/{author_id:int}", status_code=HTTP_200_OK)
    async def delete_author(
        self,
        author_id: int,
        photos_storage: Storage,  # Injected by StoragePlugin
    ) -> dict[str, str]:
        """Delete an author and their profile photo.

        Args:
            author_id: Author ID
            photos_storage: Injected photos storage

        Returns:
            Success message

        Raises:
            NotFoundException: If author not found
        """
        author = authors_db.get(author_id)
        if not author:
            raise NotFoundException(detail=f"Author {author_id} not found")

        # Delete photo if exists
        if author.photo_path and await photos_storage.exists(author.photo_path):
            await photos_storage.delete(author.photo_path)

        # Delete author record
        del authors_db[author_id]

        return {"message": f"Author {author_id} deleted successfully"}
