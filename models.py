from typing import Optional, Any

import sqlalchemy
from pydantic.main import BaseModel
from pydantic.networks import EmailStr

metadata = sqlalchemy.MetaData()

reminders = sqlalchemy.Table(
    "reminders",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("zulip_user_email", sqlalchemy.String),
    sqlalchemy.Column("text", sqlalchemy.String),
    sqlalchemy.Column("created", sqlalchemy.FLOAT),
    sqlalchemy.Column("full_content", sqlalchemy.String),
    sqlalchemy.Column("is_interval", sqlalchemy.BOOLEAN, default=False),
    sqlalchemy.Column("is_stream", sqlalchemy.BOOLEAN, default=False),
    sqlalchemy.Column("stop_date", sqlalchemy.FLOAT, nullable=True),
    sqlalchemy.Column("active", sqlalchemy.Integer, default=1),
    sqlalchemy.Column("topic", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("to", sqlalchemy.Integer),
    sqlalchemy.Column("text_date", sqlalchemy.String)
)

intervals = sqlalchemy.Table(
    "intervals",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("reminder_id", sqlalchemy.Integer),
    sqlalchemy.Column("interval_time", sqlalchemy.JSON)
)

timezone = sqlalchemy.Table(
    "timezones",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("zone", sqlalchemy.String),
    sqlalchemy.Column("email", sqlalchemy.String, unique=True)
)


class Email(BaseModel):
    zulip_user_email: EmailStr


class Remove(BaseModel):
    id: int
    email: EmailStr


class Reminder(BaseModel):
    zulip_user_email: EmailStr
    text: str
    created: float
    full_content: str
    text_date: str
    active: int = 1
    to: Optional[Any] = None
    time: Any = None
    topic: Optional[str] = None
    is_stream: Optional[bool] = False
    is_interval: bool = False
    is_use_timezone: bool = True


DATABASE_URL = "sqlite:///./test1.db"
engine = sqlalchemy.create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
metadata.create_all(engine)
