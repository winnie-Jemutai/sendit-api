from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.document import Document


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)

    hashed_password: str

    full_name: str

    role: str = Field(default="staff")

    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    updated_at: datetime = Field(default_factory=datetime.utcnow)

    last_login: datetime | None = None

    documents: list[Document] = Relationship(back_populates="uploader")


class UserCreate(SQLModel):
    username: str
    email: str
    password: str
    full_name: str
    role: str = "staff"


class UserLogin(SQLModel):
    username: str
    password: str


class UserResponse(SQLModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
