from datetime import datetime

from pydantic import BaseModel, Field


class Subscriber(BaseModel):
    email: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
