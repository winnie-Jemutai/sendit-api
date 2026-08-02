from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class Webhook(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    webhook_url: str
    event_type: str

    created_at: datetime = Field(default_factory=datetime.utcnow)