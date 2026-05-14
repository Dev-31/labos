from sqlalchemy import inspect
from sqlalchemy.orm import Session

from labos.db.schema import Base
from labos.db.session import build_engine, build_session_factory


def test_metadata_contains_core_tables() -> None:
    tables = set(Base.metadata.tables.keys())
    assert {
        "labs",
        "lab_storage",
        "runs",
        "approvals",
        "exports",
        "snapshots",
        "events",
    }.issubset(tables)


def test_session_factory_binds_to_sqlite_engine() -> None:
    engine = build_engine("sqlite+pysqlite:///:memory:")
    session_factory = build_session_factory("sqlite+pysqlite:///:memory:")

    assert engine.dialect.name == "sqlite"

    with session_factory() as session:
        assert isinstance(session, Session)
        assert session.bind is not None
        assert session.bind.dialect.name == "sqlite"


def test_approvals_table_contains_workflow_columns() -> None:
    engine = build_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("approvals")}

    assert {
        "resource_type",
        "resource_id",
        "reason",
        "requested_by",
        "state",
        "approved",
        "decision_comment",
        "decided_by",
        "expires_at",
        "decided_at",
    }.issubset(columns)
