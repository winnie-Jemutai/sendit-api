from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.user import User


class Document(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    filename: str
    original_filename: str
    version: int = Field(default=1)

    file_size: int
    file_type: str
    status: str = Field(default="uploaded")

    city: str = Field(index=True)
    country: str = Field(default="Kenya")

    weather_data: str | None = Field(default=None)
    weather_fetched_at: datetime | None = None

    description: str | None = None

    uploader_id: int = Field(foreign_key="user.id")
    uploader: User = Relationship(back_populates="documents")

    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    file_path: str


class DocumentCreate(SQLModel):
    city: str
    country: str = "Kenya"
    description: str | None = None


class DocumentUpdate(SQLModel):
    city: str | None = None
    country: str | None = None
    description: str | None = None
