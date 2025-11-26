"""Pytest configuration for book library tests."""

import sys
from pathlib import Path

# Add book-library directory to Python path
book_library_path = Path(__file__).parent.parent
sys.path.insert(0, str(book_library_path))
