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
    assert decision.approval_reasons == ()


def test_request_decision_exposes_enforceable_execution_plan() -> None:
    engine = PolicyEngine()

    decision = engine.validate_request(
        profile_name="research-persistent",
        requested_overrides={},
        requester_type="scheduler",
    )

    assert decision.profile_name == "research-persistent"
    assert decision.persistence_mode is PersistenceMode.PERSISTENT
    assert decision.export_mode is ExportMode.APPROVAL
    assert decision.retention_days == 30
    assert decision.approval_required is True
    assert decision.approval_reasons == (
        "non-human requesters need approval for high-risk profiles",
    )


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

    with pytest.raises(ValueError, match="network_mode is fixed by profile"):
        engine.validate_request(
            profile_name="safe-dev",
            requested_overrides={"network_mode": "allow-all"},
            requester_type="human",
        )


def test_request_rejects_persistence_override() -> None:
    engine = PolicyEngine()

    with pytest.raises(ValueError, match="persistence_mode is fixed by profile"):
        engine.validate_request(
            profile_name="safe-dev",
            requested_overrides={"persistence_mode": "persistent"},
            requester_type="human",
        )


def test_request_rejects_resource_override() -> None:
    engine = PolicyEngine()

    with pytest.raises(ValueError, match="cpu_limit is fixed by profile"):
        engine.validate_request(
            profile_name="safe-dev",
            requested_overrides={"cpu_limit": 99},
            requester_type="human",
        )


def test_request_rejects_secret_not_allowed_by_profile() -> None:
    engine = PolicyEngine()

    with pytest.raises(ValueError, match="requested secrets are not allowed by profile"):
        engine.validate_request(
            profile_name="safe-dev",
            requested_overrides={"secrets": ["OPENAI_API_KEY"]},
            requester_type="human",
        )


def test_profile_validation_rejects_high_risk_without_export_approval() -> None:
    with pytest.raises(ValidationError, match="high-risk profiles must require export approval"):
        Profile(
            name="unsafe-research",
            runtime_class=RuntimeClass.CONTAINER,
            risk_class=RiskClass.HIGH,
            network_mode=NetworkMode.RESTRICTED,
            filesystem_mode=FilesystemMode.MANAGED,
            persistence_mode=PersistenceMode.PERSISTENT,
            export_mode=ExportMode.REQUEST,
            cpu_limit=4,
            memory_mb=4096,
            disk_mb=8192,
            max_runtime_minutes=90,
            approval_on_start=False,
            approval_on_export=False,
            audit_level=AuditLevel.DETAILED,
            retention_days=14,
        )
