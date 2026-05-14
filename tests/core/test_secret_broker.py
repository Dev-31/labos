from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from labos.core.policy_engine import PolicyEngine
from labos.core.policy_models import RequesterType
from labos.db.schema import Base, LabRow
from labos.db.session import build_engine, build_session_factory
from labos.security.secret_broker import EnvSecretBroker, SecretLeaseService, SecretNotFoundError


def build_session_factory_for_test(tmp_path) -> tuple[str, object]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'labos-secret-broker.db'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    return database_url, build_session_factory(database_url)


def test_issue_materialize_and_revoke_secret_lease(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LABOS_SECRET_API_TOKEN", "super-secret")
    _database_url, session_factory = build_session_factory_for_test(tmp_path)
    policy = PolicyEngine()
    policy.profiles["safe-dev"] = policy.profiles["safe-dev"].model_copy(
        update={"allowed_secret_names": ["API_TOKEN"]}
    )
    service = SecretLeaseService(policy_engine=policy, broker=EnvSecretBroker())

    with session_factory() as session:
        session.add(
            LabRow(
                id="lab-123",
                profile_name="safe-dev",
                state="approved",
                runtime_class="container",
            )
        )
        session.commit()

        lease = service.issue_lease(
            session,
            lab_id="lab-123",
            secret_name="API_TOKEN",
            requester_type=RequesterType.HUMAN,
            ttl_minutes=30,
        )
        session.commit()

        runtime_leases = service.materialize_runtime_leases(session, lab_id="lab-123")
        assert len(runtime_leases) == 1
        assert runtime_leases[0].name == "API_TOKEN"
        assert runtime_leases[0].value == "super-secret"
        assert runtime_leases[0].approved is True
        assert runtime_leases[0].is_active() is True

        revoked = service.revoke_lease(session, lease_id=lease.id)
        session.commit()

        assert revoked.revoked_at is not None
        assert service.materialize_runtime_leases(session, lab_id="lab-123") == []


def test_issue_lease_rejects_secret_not_allowed_by_profile(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LABOS_SECRET_API_TOKEN", "super-secret")
    _database_url, session_factory = build_session_factory_for_test(tmp_path)
    service = SecretLeaseService(policy_engine=PolicyEngine(), broker=EnvSecretBroker())

    with session_factory() as session:
        session.add(
            LabRow(
                id="lab-123",
                profile_name="safe-dev",
                state="approved",
                runtime_class="container",
            )
        )
        session.commit()

        with pytest.raises(ValueError, match="secret_name is not allowed by profile"):
            service.issue_lease(
                session,
                lab_id="lab-123",
                secret_name="API_TOKEN",
                requester_type=RequesterType.HUMAN,
                ttl_minutes=15,
            )


def test_env_secret_broker_raises_for_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LABOS_SECRET_API_TOKEN", raising=False)

    broker = EnvSecretBroker()

    with pytest.raises(SecretNotFoundError, match="API_TOKEN"):
        broker.resolve("API_TOKEN")


def test_materialize_runtime_leases_ignores_expired_records(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LABOS_SECRET_API_TOKEN", "super-secret")
    _database_url, session_factory = build_session_factory_for_test(tmp_path)
    policy = PolicyEngine()
    policy.profiles["safe-dev"] = policy.profiles["safe-dev"].model_copy(
        update={"allowed_secret_names": ["API_TOKEN"]}
    )
    service = SecretLeaseService(policy_engine=policy, broker=EnvSecretBroker())

    with session_factory() as session:
        session.add(
            LabRow(
                id="lab-123",
                profile_name="safe-dev",
                state="approved",
                runtime_class="container",
            )
        )
        session.commit()

        lease = service.issue_lease(
            session,
            lab_id="lab-123",
            secret_name="API_TOKEN",
            requester_type=RequesterType.HUMAN,
            ttl_minutes=1,
        )
        lease.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()

        assert service.materialize_runtime_leases(session, lab_id="lab-123") == []
