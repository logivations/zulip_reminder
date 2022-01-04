import sqlalchemy


metadata = sqlalchemy.MetaData()

reminders = sqlalchemy.Table(
    "reminders",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("zulip_user_email", sqlalchemy.String),
    sqlalchemy.Column("title", sqlalchemy.String),
    sqlalchemy.Column("created", sqlalchemy.TIMESTAMP),
    sqlalchemy.Column("deadline", sqlalchemy.TIMESTAMP, nullable=True),
    sqlalchemy.Column("active", sqlalchemy.Integer, default=1),
)

intervals = sqlalchemy.Table(
    "intervals",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("reminder_id", sqlalchemy.Integer),
    sqlalchemy.Column("interval_time", sqlalchemy.String)
)

timezone = sqlalchemy.Table(
    "timezone",
    metadata,
    sqlalchemy.Column("zone", sqlalchemy.String),
    sqlalchemy.Column("email", sqlalchemy.String)
)


DATABASE_URL = "sqlite:///./test.db"
engine = sqlalchemy.create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
metadata.create_all(engine)


