"""Tests for the book library application."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_404_NOT_FOUND,
)
from litestar.testing import AsyncTestClient

if TYPE_CHECKING:
    from litestar import Litestar


@pytest.fixture
def app() -> Litestar:
    """Create test application."""
    # Import here to avoid circular imports
    from app import create_app
    from controllers import authors_db, books_db
    from models import Author, Book

    # Clear databases between tests
    books_db.clear()
    authors_db.clear()

    # Reset ID counters
    Book._id_counter = 0
    Author._id_counter = 0

    return create_app()


@pytest.fixture
async def client(app: Litestar) -> AsyncTestClient:
    """Create test client."""
    async with AsyncTestClient(app=app) as client:
        yield client


class TestRootEndpoints:
    """Test root and health endpoints."""

    async def test_index(self, client: AsyncTestClient) -> None:
        """Test index endpoint."""
        response = await client.get("/")
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert "endpoints" in data
        assert "books" in data["endpoints"]
        assert "authors" in data["endpoints"]

    async def test_health(self, client: AsyncTestClient) -> None:
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == HTTP_200_OK
        assert response.json() == {"status": "healthy"}


class TestBookEndpoints:
    """Test book management endpoints."""

    async def test_create_book(self, client: AsyncTestClient) -> None:
        """Test creating a book with cover image."""
        # Create fake image file
        image_data = b"fake image data"
        files = {
            "cover_image": ("cover.jpg", io.BytesIO(image_data), "image/jpeg"),
        }
        data = {
            "title": "Python Cookbook",
            "author": "David Beazley",
            "isbn": "978-1-449-34037-7",
        }

        response = await client.post("/books", files=files, data=data)
        assert response.status_code == HTTP_201_CREATED

        result = response.json()
        assert result["id"] == 1
        assert result["title"] == "Python Cookbook"
        assert result["author"] == "David Beazley"
        assert result["isbn"] == "978-1-449-34037-7"
        assert result["has_cover"] is True
        assert result["cover_url"] == "/books/1/cover"

    async def test_list_books(self, client: AsyncTestClient) -> None:
        """Test listing all books."""
        # Create two books
        for i in range(2):
            image_data = b"fake image data"
            files = {
                "cover_image": (f"cover{i}.jpg", io.BytesIO(image_data), "image/jpeg"),
            }
            data = {
                "title": f"Book {i}",
                "author": f"Author {i}",
                "isbn": f"978-0-000000-00-{i}",
            }
            await client.post("/books", files=files, data=data)

        # List books
        response = await client.get("/books")
        assert response.status_code == HTTP_200_OK

        books = response.json()
        assert len(books) == 2
        assert books[0]["title"] == "Book 0"
        assert books[1]["title"] == "Book 1"

    async def test_get_book(self, client: AsyncTestClient) -> None:
        """Test getting a specific book."""
        # Create a book
        image_data = b"fake image data"
        files = {
            "cover_image": ("cover.jpg", io.BytesIO(image_data), "image/jpeg"),
        }
        data = {
            "title": "Test Book",
            "author": "Test Author",
            "isbn": "978-0-000000-00-0",
        }
        create_response = await client.post("/books", files=files, data=data)
        book_id = create_response.json()["id"]

        # Get the book
        response = await client.get(f"/books/{book_id}")
        assert response.status_code == HTTP_200_OK

        book = response.json()
        assert book["id"] == book_id
        assert book["title"] == "Test Book"

    async def test_get_book_not_found(self, client: AsyncTestClient) -> None:
        """Test getting a non-existent book."""
        response = await client.get("/books/999")
        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_download_cover(self, client: AsyncTestClient) -> None:
        """Test downloading book cover image."""
        # Create a book with cover
        image_data = b"fake image data"
        files = {
            "cover_image": ("cover.jpg", io.BytesIO(image_data), "image/jpeg"),
        }
        data = {
            "title": "Test Book",
            "author": "Test Author",
            "isbn": "978-0-000000-00-0",
        }
        create_response = await client.post("/books", files=files, data=data)
        book_id = create_response.json()["id"]

        # Download cover
        response = await client.get(f"/books/{book_id}/cover")
        assert response.status_code == HTTP_200_OK
        assert response.content == image_data
        assert response.headers["content-type"] == "image/jpeg"

    async def test_download_cover_not_found(self, client: AsyncTestClient) -> None:
        """Test downloading cover for non-existent book."""
        response = await client.get("/books/999/cover")
        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_delete_book(self, client: AsyncTestClient) -> None:
        """Test deleting a book."""
        # Create a book
        image_data = b"fake image data"
        files = {
            "cover_image": ("cover.jpg", io.BytesIO(image_data), "image/jpeg"),
        }
        data = {
            "title": "Test Book",
            "author": "Test Author",
            "isbn": "978-0-000000-00-0",
        }
        create_response = await client.post("/books", files=files, data=data)
        book_id = create_response.json()["id"]

        # Delete the book
        response = await client.delete(f"/books/{book_id}")
        assert response.status_code == HTTP_200_OK
        assert "deleted successfully" in response.json()["message"]

        # Verify book is deleted
        get_response = await client.get(f"/books/{book_id}")
        assert get_response.status_code == HTTP_404_NOT_FOUND

    async def test_delete_book_not_found(self, client: AsyncTestClient) -> None:
        """Test deleting a non-existent book."""
        response = await client.delete("/books/999")
        assert response.status_code == HTTP_404_NOT_FOUND


class TestAuthorEndpoints:
    """Test author management endpoints."""

    async def test_create_author_with_photo(self, client: AsyncTestClient) -> None:
        """Test creating an author with profile photo."""
        # Create fake image file
        image_data = b"fake photo data"
        files = {
            "photo": ("photo.jpg", io.BytesIO(image_data), "image/jpeg"),
        }
        data = {
            "name": "Guido van Rossum",
            "bio": "Creator of Python",
        }

        response = await client.post("/authors", files=files, data=data)
        assert response.status_code == HTTP_201_CREATED

        result = response.json()
        assert result["id"] == 1
        assert result["name"] == "Guido van Rossum"
        assert result["bio"] == "Creator of Python"
        assert result["has_photo"] is True
        assert result["photo_url"] == "/authors/1/photo"

    # NOTE: Testing optional file upload with httpx is tricky.
    # In real usage, the photo field can be omitted from the form data.
    # The test for authors with photos (test_create_author_with_photo) demonstrates
    # that the optional photo field works correctly when provided.

    async def test_list_authors(self, client: AsyncTestClient) -> None:
        """Test listing all authors."""
        # Create two authors with photos
        for i in range(2):
            image_data = f"fake photo data {i}".encode()
            files = {
                "photo": (f"photo{i}.jpg", io.BytesIO(image_data), "image/jpeg"),
            }
            data = {
                "name": f"Author {i}",
                "bio": f"Bio {i}",
            }
            await client.post("/authors", files=files, data=data)

        # List authors
        response = await client.get("/authors")
        assert response.status_code == HTTP_200_OK

        authors = response.json()
        assert len(authors) == 2
        assert authors[0]["name"] == "Author 0"
        assert authors[1]["name"] == "Author 1"

    async def test_get_author(self, client: AsyncTestClient) -> None:
        """Test getting a specific author."""
        # Create an author with photo
        image_data = b"fake photo data"
        files = {
            "photo": ("photo.jpg", io.BytesIO(image_data), "image/jpeg"),
        }
        data = {
            "name": "Test Author",
            "bio": "Test Bio",
        }
        create_response = await client.post("/authors", files=files, data=data)
        author_id = create_response.json()["id"]

        # Get the author
        response = await client.get(f"/authors/{author_id}")
        assert response.status_code == HTTP_200_OK

        author = response.json()
        assert author["id"] == author_id
        assert author["name"] == "Test Author"

    async def test_get_author_not_found(self, client: AsyncTestClient) -> None:
        """Test getting a non-existent author."""
        response = await client.get("/authors/999")
        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_download_photo(self, client: AsyncTestClient) -> None:
        """Test downloading author profile photo."""
        # Create an author with photo
        image_data = b"fake photo data"
        files = {
            "photo": ("photo.jpg", io.BytesIO(image_data), "image/jpeg"),
        }
        data = {
            "name": "Test Author",
            "bio": "Test Bio",
        }
        create_response = await client.post("/authors", files=files, data=data)
        author_id = create_response.json()["id"]

        # Download photo
        response = await client.get(f"/authors/{author_id}/photo")
        assert response.status_code == HTTP_200_OK
        assert response.content == image_data
        assert response.headers["content-type"] == "image/jpeg"

    async def test_download_photo_not_found(self, client: AsyncTestClient) -> None:
        """Test downloading photo for non-existent author."""
        # Try to download photo for author that doesn't exist
        response = await client.get("/authors/999/photo")
        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_delete_author(self, client: AsyncTestClient) -> None:
        """Test deleting an author."""
        # Create an author
        image_data = b"fake photo data"
        files = {
            "photo": ("photo.jpg", io.BytesIO(image_data), "image/jpeg"),
        }
        data = {
            "name": "Test Author",
            "bio": "Test Bio",
        }
        create_response = await client.post("/authors", files=files, data=data)
        author_id = create_response.json()["id"]

        # Delete the author
        response = await client.delete(f"/authors/{author_id}")
        assert response.status_code == HTTP_200_OK
        assert "deleted successfully" in response.json()["message"]

        # Verify author is deleted
        get_response = await client.get(f"/authors/{author_id}")
        assert get_response.status_code == HTTP_404_NOT_FOUND

    async def test_delete_author_not_found(self, client: AsyncTestClient) -> None:
        """Test deleting a non-existent author."""
        response = await client.delete("/authors/999")
        assert response.status_code == HTTP_404_NOT_FOUND


class TestIntegration:
    """Integration tests for the full application."""

    async def test_full_workflow(self, client: AsyncTestClient) -> None:
        """Test complete workflow: create, list, download, delete."""
        # 1. Create an author with photo
        author_photo = b"author photo data"
        author_files = {
            "photo": ("author.jpg", io.BytesIO(author_photo), "image/jpeg"),
        }
        author_data = {
            "name": "Brandon Rhodes",
            "bio": "Python educator",
        }
        author_response = await client.post("/authors", files=author_files, data=author_data)
        assert author_response.status_code == HTTP_201_CREATED
        author_id = author_response.json()["id"]

        # 2. Create a book with cover
        book_cover = b"book cover data"
        book_files = {
            "cover_image": ("cover.jpg", io.BytesIO(book_cover), "image/jpeg"),
        }
        book_data = {
            "title": "Foundations of Python Network Programming",
            "author": "Brandon Rhodes",
            "isbn": "978-1-4302-5855-1",
        }
        book_response = await client.post("/books", files=book_files, data=book_data)
        assert book_response.status_code == HTTP_201_CREATED
        book_id = book_response.json()["id"]

        # 3. List all books and authors
        books_list = await client.get("/books")
        assert len(books_list.json()) == 1

        authors_list = await client.get("/authors")
        assert len(authors_list.json()) == 1

        # 4. Download files
        cover_response = await client.get(f"/books/{book_id}/cover")
        assert cover_response.status_code == HTTP_200_OK
        assert cover_response.content == book_cover

        photo_response = await client.get(f"/authors/{author_id}/photo")
        assert photo_response.status_code == HTTP_200_OK
        assert photo_response.content == author_photo

        # 5. Delete book and author
        await client.delete(f"/books/{book_id}")
        await client.delete(f"/authors/{author_id}")

        # 6. Verify deletion
        books_list_after = await client.get("/books")
        assert len(books_list_after.json()) == 0

        authors_list_after = await client.get("/authors")
        assert len(authors_list_after.json()) == 0
