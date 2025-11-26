"""Main Litestar application for the book library example."""

from __future__ import annotations

from litestar import Litestar, get

from litestar_storages.backends import MemoryStorage
from litestar_storages.contrib import StoragePlugin

from controllers import AuthorController, BookController


@get("/")
async def index() -> dict[str, str | dict[str, list[str]]]:
    """Root endpoint with API information."""
    return {
        "message": "Book Library API - Litestar Storage Example",
        "endpoints": {
            "books": [
                "POST /books - Create book with cover",
                "GET /books - List all books",
                "GET /books/{id} - Get book details",
                "GET /books/{id}/cover - Download cover",
                "DELETE /books/{id} - Delete book",
            ],
            "authors": [
                "POST /authors - Create author with photo",
                "GET /authors - List all authors",
                "GET /authors/{id} - Get author details",
                "GET /authors/{id}/photo - Download photo",
                "DELETE /authors/{id} - Delete author",
            ],
        },
    }


@get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


def create_app() -> Litestar:
    """Create and configure the Litestar application.

    Returns:
        Configured Litestar application
    """
    # Configure storage plugin with two named storages
    # Note: Named storages are provided as kwargs and will be injected
    # as {name}_storage dependencies (e.g., covers_storage, photos_storage)
    storage_plugin = StoragePlugin(
        covers=MemoryStorage(),  # For book cover images -> covers_storage
        photos=MemoryStorage(),  # For author profile photos -> photos_storage
    )

    return Litestar(
        route_handlers=[
            index,
            health,
            BookController,
            AuthorController,
        ],
        plugins=[storage_plugin],
        debug=True,
    )


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
