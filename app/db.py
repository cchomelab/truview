import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine, func, select

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
    db_dir = DB_PATH.parent.resolve()
    db_dir.mkdir(parents=True, exist_ok=True)
    # A mounted volume the container user can't write to is the most common
    # storage problem; fail with a clear message instead of SQLite's
    # "unable to open database file".
    for path in (db_dir, DB_PATH):
        if path.exists() and not os.access(path, os.W_OK):
            raise RuntimeError(
                f"{path} is not writable by uid {os.getuid()} (gid {os.getgid()}). "
                "Check the volume's ownership/permissions."
            )
    SQLModel.metadata.create_all(engine)
    # SQLite creates the file as 0644. OpenShift runs pods as an arbitrary UID in
    # group 0, so make it group-writable or a pod with a different UID can't write
    # to it later. SQLite gives its journal files the same mode as the database.
    if DB_PATH.stat().st_uid == os.getuid():
        DB_PATH.chmod(DB_PATH.stat().st_mode | stat.S_IWGRP)


def add_request_log(entry: RequestLog) -> None:
    with Session(engine) as session:
        session.add(entry)
        session.commit()


def recent_request_logs(limit: int) -> list[RequestLog]:
    with Session(engine) as session:
        statement = select(RequestLog).order_by(RequestLog.id.desc()).limit(limit)
        return list(session.exec(statement))


def request_log_stats() -> dict:
    with Session(engine) as session:
        statement = select(func.count(RequestLog.id), func.min(RequestLog.timestamp))
        total, first = session.exec(statement).one()
    # SQLite drops the timezone; stored values are UTC
    if first is not None and first.tzinfo is None:
        first = first.replace(tzinfo=timezone.utc)
    return {"total_calls": total, "first_call": first, "db_path": str(DB_PATH.resolve())}
