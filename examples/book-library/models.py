"""Data models for the book library application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from litestar.datastructures import UploadFile


@dataclass
class Book:
    """Book model with cover image."""

    id: int
    title: str
    author: str
    isbn: str
    cover_path: str | None = None

    _id_counter: ClassVar[int] = 0

    @classmethod
    def create(
        cls,
        title: str,
        author: str,
        isbn: str,
        cover_path: str | None = None,
    ) -> Book:
        """Create a new book with auto-incrementing ID."""
        cls._id_counter += 1
        return cls(
            id=cls._id_counter,
            title=title,
            author=author,
            isbn=isbn,
            cover_path=cover_path,
        )


@dataclass
class BookCreate:
    """Request model for creating a book."""

    title: str
    author: str
    isbn: str
    cover_image: UploadFile


@dataclass
class BookResponse:
    """Response model for book (without binary cover data)."""

    id: int
    title: str
    author: str
    isbn: str
    has_cover: bool
    cover_url: str | None = None

    @classmethod
    def from_book(cls, book: Book, base_url: str = "") -> BookResponse:
        """Convert Book model to response."""
        return cls(
            id=book.id,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            has_cover=book.cover_path is not None,
            cover_url=f"{base_url}/books/{book.id}/cover" if book.cover_path else None,
        )


@dataclass
class Author:
    """Author model with profile photo."""

    id: int
    name: str
    bio: str | None = None
    photo_path: str | None = None

    _id_counter: ClassVar[int] = 0

    @classmethod
    def create(
        cls,
        name: str,
        bio: str | None = None,
        photo_path: str | None = None,
    ) -> Author:
        """Create a new author with auto-incrementing ID."""
        cls._id_counter += 1
        return cls(
            id=cls._id_counter,
            name=name,
            bio=bio,
            photo_path=photo_path,
        )


@dataclass
class AuthorCreate:
    """Request model for creating an author."""

    name: str
    bio: str | None = None
    photo: UploadFile | None = None


@dataclass
class AuthorResponse:
    """Response model for author (without binary photo data)."""

    id: int
    name: str
    bio: str | None = None
    has_photo: bool = False
    photo_url: str | None = None

    @classmethod
    def from_author(cls, author: Author, base_url: str = "") -> AuthorResponse:
        """Convert Author model to response."""
        return cls(
            id=author.id,
            name=author.name,
            bio=author.bio,
            has_photo=author.photo_path is not None,
            photo_url=f"{base_url}/authors/{author.id}/photo" if author.photo_path else None,
        )
