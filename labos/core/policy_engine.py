from __future__ import annotations

from dataclasses import dataclass

from labos.config.profiles.base import DEFAULT_PROFILES
from labos.core.enums import AuditLevel
from labos.core.policy_models import (
    ExportMode,
    FilesystemMode,
    NetworkMode,
    PersistenceMode,
    Profile,
    RequesterType,
    RiskClass,
    RuntimeClass,
)

MANAGED_EXPORT_PREFIXES = ("/lab/exports/", "/artifacts/approved/")


@dataclass(frozen=True)
class RequestDecision:
    profile_name: str
    runtime_class: RuntimeClass
    network_mode: NetworkMode
    filesystem_mode: FilesystemMode
    persistence_mode: PersistenceMode
    export_mode: ExportMode
    cpu_limit: int
    memory_mb: int
    disk_mb: int
    max_runtime_minutes: int
    approval_required: bool
    approval_reasons: tuple[str, ...]
    risk_class: RiskClass
    injected_secrets: list[str]
    host_mounts_allowed: bool
    audit_level: AuditLevel
    retention_days: int


@dataclass(frozen=True)
class ExportDecision:
    allowed: bool
    approval_required: bool
    quarantine_required: bool
    reason: str


class PolicyEngine:
    """Phase 1 policy evaluator for turning profiles into enforceable plans."""

    def __init__(self) -> None:
        self.profiles = dict(DEFAULT_PROFILES)

    def get_profile(self, name: str) -> Profile:
        try:
            return self.profiles[name]
        except KeyError as exc:
            raise KeyError(f"unknown profile: {name}") from exc

    def _normalize_expected_value(self, value: object) -> object:
        return getattr(value, "value", value)

    def _enforce_profile_locked_field(
        self,
        field_name: str,
        requested_overrides: dict[str, object],
        expected_value: object,
    ) -> None:
        if field_name not in requested_overrides:
            return

        normalized_expected = self._normalize_expected_value(expected_value)
        if requested_overrides[field_name] != normalized_expected:
            raise ValueError(f"{field_name} is fixed by profile")

    def validate_request(
        self,
        profile_name: str,
        requested_overrides: dict[str, object],
        requester_type: str,
    ) -> RequestDecision:
        profile = self.get_profile(profile_name)
        requester = RequesterType(requester_type)

        if requested_overrides.get("inherit_host_env"):
            raise ValueError("host environment inheritance is forbidden")

        host_mounts = requested_overrides.get("host_mounts", [])
        if host_mounts and not profile.allow_host_mounts:
            raise ValueError(
                "host mounts are forbidden unless the profile explicitly allows them"
            )

        self._enforce_profile_locked_field(
            field_name="network_mode",
            requested_overrides=requested_overrides,
            expected_value=profile.network_mode,
        )
        self._enforce_profile_locked_field(
            field_name="runtime_class",
            requested_overrides=requested_overrides,
            expected_value=profile.runtime_class,
        )
        self._enforce_profile_locked_field(
            field_name="filesystem_mode",
            requested_overrides=requested_overrides,
            expected_value=profile.filesystem_mode,
        )
        self._enforce_profile_locked_field(
            field_name="persistence_mode",
            requested_overrides=requested_overrides,
            expected_value=profile.persistence_mode,
        )
        self._enforce_profile_locked_field(
            field_name="export_mode",
            requested_overrides=requested_overrides,
            expected_value=profile.export_mode,
        )
        self._enforce_profile_locked_field(
            field_name="cpu_limit",
            requested_overrides=requested_overrides,
            expected_value=profile.cpu_limit,
        )
        self._enforce_profile_locked_field(
            field_name="memory_mb",
            requested_overrides=requested_overrides,
            expected_value=profile.memory_mb,
        )
        self._enforce_profile_locked_field(
            field_name="disk_mb",
            requested_overrides=requested_overrides,
            expected_value=profile.disk_mb,
        )
        self._enforce_profile_locked_field(
            field_name="max_runtime_minutes",
            requested_overrides=requested_overrides,
            expected_value=profile.max_runtime_minutes,
        )

        requested_secrets = requested_overrides.get("secrets", [])
        if not isinstance(requested_secrets, list):
            raise ValueError("requested secrets must be a list of names")
        unknown_secrets = sorted(set(requested_secrets) - set(profile.allowed_secret_names))
        if unknown_secrets:
            secret_list = ", ".join(unknown_secrets)
            raise ValueError(f"requested secrets are not allowed by profile: {secret_list}")

        approval_reasons: list[str] = []
        if profile.approval_on_start:
            approval_reasons.append("profile requires start approval")
        if requester is not RequesterType.HUMAN and profile.risk_class in {
            RiskClass.HIGH,
            RiskClass.CRITICAL,
        }:
            approval_reasons.append("non-human requesters need approval for high-risk profiles")

        return RequestDecision(
            profile_name=profile.name,
            runtime_class=profile.runtime_class,
            network_mode=profile.network_mode,
            filesystem_mode=profile.filesystem_mode,
            persistence_mode=profile.persistence_mode,
            export_mode=profile.export_mode,
            cpu_limit=profile.cpu_limit,
            memory_mb=profile.memory_mb,
            disk_mb=profile.disk_mb,
            max_runtime_minutes=profile.max_runtime_minutes,
            approval_required=bool(approval_reasons),
            approval_reasons=tuple(approval_reasons),
            risk_class=profile.risk_class,
            injected_secrets=requested_secrets,
            host_mounts_allowed=profile.allow_host_mounts,
            audit_level=profile.audit_level,
            retention_days=profile.retention_days,
        )

    def validate_export(self, profile_name: str, export_path: str) -> ExportDecision:
        profile = self.get_profile(profile_name)

        if not export_path.startswith(MANAGED_EXPORT_PREFIXES):
            return ExportDecision(
                allowed=False,
                approval_required=True,
                quarantine_required=True,
                reason="exports must originate from managed LabOS paths",
            )

        quarantine_required = profile.risk_class in {RiskClass.HIGH, RiskClass.CRITICAL}
        return ExportDecision(
            allowed=True,
            approval_required=profile.approval_on_export,
            quarantine_required=quarantine_required,
            reason="managed export path accepted",
        )
