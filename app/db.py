import os
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine, select

# Defaults to a file in the working directory; the container sets /data/truview.db
DB_PATH = Path(os.environ.get("DB_PATH", "truview.db"))

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    # Requests are logged from a threadpool, so the connection crosses threads
    connect_args={"check_same_thread": False},
)


class RequestLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    method: str
    path: str
    status_code: int
    client_host: str | None = None
    user_agent: str | None = None
    duration_ms: float


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def add_request_log(entry: RequestLog) -> None:
    with Session(engine) as session:
        session.add(entry)
        session.commit()


def recent_request_logs(limit: int) -> list[RequestLog]:
    with Session(engine) as session:
        statement = select(RequestLog).order_by(RequestLog.id.desc()).limit(limit)
        return list(session.exec(statement))
