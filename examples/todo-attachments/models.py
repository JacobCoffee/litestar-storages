"""Todo and Attachment models for the example application."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar
from uuid import UUID, uuid4


@dataclass
class Todo:
    """A todo item that can have file attachments."""

    title: str
    description: str | None = None
    completed: bool = False
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Class-level storage for demo purposes (in production, use a database)
    _todos: ClassVar[dict[UUID, Todo]] = {}

    @classmethod
    def create(cls, title: str, description: str | None = None) -> Todo:
        """Create a new todo and store it."""
        todo = cls(title=title, description=description)
        cls._todos[todo.id] = todo
        return todo

    @classmethod
    def get(cls, todo_id: UUID) -> Todo | None:
        """Get a todo by ID."""
        return cls._todos.get(todo_id)

    @classmethod
    def get_all(cls) -> list[Todo]:
        """Get all todos."""
        return list(cls._todos.values())

    @classmethod
    def delete(cls, todo_id: UUID) -> bool:
        """Delete a todo by ID."""
        if todo_id in cls._todos:
            del cls._todos[todo_id]
            return True
        return False

    @classmethod
    def clear_all(cls) -> None:
        """Clear all todos (for testing)."""
        cls._todos.clear()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "completed": self.completed,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Attachment:
    """A file attachment associated with a todo."""

    todo_id: UUID
    filename: str
    content_type: str
    size: int
    storage_path: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Class-level storage for demo purposes
    _attachments: ClassVar[dict[UUID, Attachment]] = {}

    @classmethod
    def create(
        cls,
        todo_id: UUID,
        filename: str,
        content_type: str,
        size: int,
        storage_path: str,
    ) -> Attachment:
        """Create a new attachment and store it."""
        attachment = cls(
            todo_id=todo_id,
            filename=filename,
            content_type=content_type,
            size=size,
            storage_path=storage_path,
        )
        cls._attachments[attachment.id] = attachment
        return attachment

    @classmethod
    def get(cls, attachment_id: UUID) -> Attachment | None:
        """Get an attachment by ID."""
        return cls._attachments.get(attachment_id)

    @classmethod
    def get_by_todo(cls, todo_id: UUID) -> list[Attachment]:
        """Get all attachments for a todo."""
        return [att for att in cls._attachments.values() if att.todo_id == todo_id]

    @classmethod
    def delete(cls, attachment_id: UUID) -> bool:
        """Delete an attachment by ID."""
        if attachment_id in cls._attachments:
            del cls._attachments[attachment_id]
            return True
        return False

    @classmethod
    def delete_by_todo(cls, todo_id: UUID) -> int:
        """Delete all attachments for a todo. Returns count deleted."""
        to_delete = [att_id for att_id, att in cls._attachments.items() if att.todo_id == todo_id]
        for att_id in to_delete:
            del cls._attachments[att_id]
        return len(to_delete)

    @classmethod
    def clear_all(cls) -> None:
        """Clear all attachments (for testing)."""
        cls._attachments.clear()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "todo_id": str(self.todo_id),
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "created_at": self.created_at.isoformat(),
        }
