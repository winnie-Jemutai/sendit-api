from datetime import datetime

from sqlmodel import Field, SQLModel


class Webhook(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    webhook_url: str
    event_type: str

    created_at: datetime = Field(default_factory=datetime.utcnow)
