from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_engine(url: str) -> Engine:
    return create_engine(url)


def build_session_factory(url: str) -> sessionmaker[Session]:
    engine = build_engine(url)
    return sessionmaker(bind=engine)
