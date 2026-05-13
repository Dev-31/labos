import pytest
from pydantic import ValidationError

from labos.core.enums import AuditLevel
from labos.core.policy_engine import PolicyEngine
from labos.core.policy_models import (
    ExportMode,
    FilesystemMode,
    NetworkMode,
    PersistenceMode,
    Profile,
    RiskClass,
    RuntimeClass,
)


def test_red_zone_requires_microvm_and_approval() -> None:
    engine = PolicyEngine()

    decision = engine.validate_request(
        profile_name="red-zone",
        requested_overrides={},
        requester_type="agent",
    )

    assert decision.runtime_class is RuntimeClass.MICROVM
    assert decision.approval_required is True
    assert decision.risk_class is RiskClass.CRITICAL


def test_safe_dev_export_allows_managed_export_path() -> None:
    engine = PolicyEngine()

    decision = engine.validate_export("safe-dev", "/lab/exports/report.json")

    assert decision.allowed is True
    assert decision.approval_required is False
    assert decision.quarantine_required is False


def test_high_risk_exports_are_deny_until_reviewed() -> None:
    engine = PolicyEngine()

    decision = engine.validate_export("red-zone", "/lab/exports/report.json")

    assert decision.allowed is True
    assert decision.approval_required is True
    assert decision.quarantine_required is True


def test_profile_validation_rejects_invalid_microvm_combination() -> None:
    with pytest.raises(ValidationError, match="microVM profiles must deny network egress"):
        Profile(
            name="bad-red-zone",
            runtime_class=RuntimeClass.MICROVM,
            risk_class=RiskClass.CRITICAL,
            network_mode=NetworkMode.RESTRICTED,
            filesystem_mode=FilesystemMode.MANAGED,
            persistence_mode=PersistenceMode.EPHEMERAL,
            export_mode=ExportMode.APPROVAL,
            cpu_limit=2,
            memory_mb=2048,
            disk_mb=4096,
            max_runtime_minutes=60,
            approval_on_start=True,
            approval_on_export=True,
            audit_level=AuditLevel.FORENSIC,
            retention_days=7,
        )


def test_host_mounts_are_forbidden_by_default() -> None:
    engine = PolicyEngine()

    with pytest.raises(
        ValueError,
        match="host mounts are forbidden unless the profile explicitly allows them",
    ):
        engine.validate_request(
            profile_name="safe-dev",
            requested_overrides={"host_mounts": ["/tmp:/host-tmp"]},
            requester_type="human",
        )


def test_request_defaults_to_empty_secret_set() -> None:
    engine = PolicyEngine()

    decision = engine.validate_request(
        profile_name="model-local",
        requested_overrides={},
        requester_type="human",
    )

    assert decision.injected_secrets == []


def test_request_rejects_host_environment_inheritance() -> None:
    engine = PolicyEngine()

    with pytest.raises(ValueError, match="host environment inheritance is forbidden"):
        engine.validate_request(
            profile_name="safe-dev",
            requested_overrides={"inherit_host_env": True},
            requester_type="human",
        )


def test_request_rejects_network_override() -> None:
    engine = PolicyEngine()

    with pytest.raises(ValueError, match="network mode is fixed by profile"):
        engine.validate_request(
            profile_name="safe-dev",
            requested_overrides={"network_mode": "allow-all"},
            requester_type="human",
        )
