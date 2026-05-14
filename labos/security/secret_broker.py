from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from os import getenv
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from labos.core.policy_engine import PolicyEngine
from labos.core.policy_models import RequesterType
from labos.db.schema import LabRow, SecretLeaseRow
from labos.runtimes.base import SecretLease


class SecretNotFoundError(KeyError):
    def __init__(self, secret_name: str) -> None:
        self.secret_name = secret_name
        super().__init__(secret_name)


class SecretLeaseStateError(ValueError):
    pass


class SecretBroker(Protocol):
    def resolve(self, secret_name: str) -> str: ...


@dataclass(frozen=True)
class EnvSecretBroker:
    prefix: str = "LABOS_SECRET_"

    def resolve(self, secret_name: str) -> str:
        env_name = f"{self.prefix}{secret_name}"
        value = getenv(env_name)
        if value is None:
            raise SecretNotFoundError(secret_name)
        return value


class SecretLeaseService:
    def __init__(self, *, policy_engine: PolicyEngine, broker: SecretBroker) -> None:
        self._policy_engine = policy_engine
        self._broker = broker

    def issue_lease(
        self,
        session: Session,
        *,
        lab_id: str,
        secret_name: str,
        requester_type: RequesterType,
        ttl_minutes: int,
    ) -> SecretLeaseRow:
        if ttl_minutes < 1:
            raise ValueError("ttl_minutes must be at least 1")

        lab = session.get(LabRow, lab_id)
        if lab is None:
            raise LookupError("lab")

        profile = self._policy_engine.get_profile(lab.profile_name)
        if secret_name not in profile.allowed_secret_names:
            raise ValueError("secret_name is not allowed by profile")

        self._broker.resolve(secret_name)
        now = datetime.now(UTC)
        lease = SecretLeaseRow(
            id=str(uuid4()),
            lab_id=lab_id,
            secret_name=secret_name,
            approved=True,
            expires_at=now + timedelta(minutes=ttl_minutes),
            revoked_at=None,
        )
        session.add(lease)
        return lease

    def revoke_lease(self, session: Session, *, lease_id: str) -> SecretLeaseRow:
        lease = session.get(SecretLeaseRow, lease_id)
        if lease is None:
            raise LookupError("secret_lease")
        if lease.revoked_at is not None:
            raise SecretLeaseStateError("secret lease already revoked")
        lease.revoked_at = datetime.now(UTC)
        return lease

    def list_leases(self, session: Session, *, lab_id: str) -> list[SecretLeaseRow]:
        return list(
            session.scalars(
            select(SecretLeaseRow)
            .where(SecretLeaseRow.lab_id == lab_id)
            .order_by(SecretLeaseRow.created_at, SecretLeaseRow.id)
            ).all()
        )

    def materialize_runtime_leases(self, session: Session, *, lab_id: str) -> list[SecretLease]:
        now = datetime.now(UTC)
        rows = session.scalars(
            select(SecretLeaseRow)
            .where(SecretLeaseRow.lab_id == lab_id)
            .where(SecretLeaseRow.approved.is_(True))
            .where(SecretLeaseRow.revoked_at.is_(None))
            .where(SecretLeaseRow.expires_at > now)
            .order_by(SecretLeaseRow.created_at, SecretLeaseRow.id)
        ).all()
        return [
            SecretLease(
                name=row.secret_name,
                value=self._broker.resolve(row.secret_name),
                approved=row.approved,
                expires_at=self._normalize_datetime(row.expires_at),
            )
            for row in rows
        ]

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
