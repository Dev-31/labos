from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from labos.core.policy_models import NetworkMode, PersistenceMode
from labos.runtimes.base import ManagedMount, RuntimeSpec, SecretLease
from labos.runtimes.docker_runtime import DockerRuntime


@dataclass
class FakeExecResult:
    exit_code: int
    output: bytes


@dataclass
class FakeContainer:
    name: str
    image: str
    status: str = "created"
    labels: dict[str, str] = field(default_factory=dict)
    attrs: dict[str, Any] = field(
        default_factory=lambda: {"State": {"Status": "created"}, "Config": {"Env": []}}
    )
    exec_calls: list[tuple[str, str]] = field(default_factory=list)
    removed: bool = False
    stop_timeout: int | None = None
    started: bool = False
    logs_output: bytes = b"runtime logs"

    def start(self) -> None:
        self.started = True
        self.status = "running"
        self.attrs["State"]["Status"] = "running"

    def stop(self, timeout: int = 10) -> None:
        self.stop_timeout = timeout
        self.status = "exited"
        self.attrs["State"]["Status"] = "exited"

    def remove(self, force: bool = False) -> None:
        del force
        self.removed = True
        self.status = "removed"
        self.attrs["State"]["Status"] = "removed"

    def exec_run(self, command: str) -> FakeExecResult:
        self.exec_calls.append((self.name, command))
        return FakeExecResult(exit_code=0, output=b"hello from lab")

    def logs(self, tail: int | str = "all") -> bytes:
        del tail
        return self.logs_output

    def reload(self) -> None:
        return None


class FakeContainerManager:
    def __init__(self) -> None:
        self.by_name: dict[str, FakeContainer] = {}
        self.create_kwargs: list[dict[str, Any]] = []
        self.fail_create = False

    def create(self, image: str, name: str, **kwargs: Any) -> FakeContainer:
        self.create_kwargs.append({"image": image, "name": name, **kwargs})
        if self.fail_create:
            raise RuntimeError("container create failed")
        container = FakeContainer(name=name, image=image, labels=kwargs.get("labels", {}))
        container.attrs["Config"]["Env"] = [
            f"{key}={value}" for key, value in kwargs.get("environment", {}).items()
        ]
        self.by_name[name] = container
        return container

    def get(self, name: str) -> FakeContainer:
        return self.by_name[name]


@dataclass
class FakeNetwork:
    name: str
    removed: bool = False

    def remove(self) -> None:
        self.removed = True


class FakeNetworkManager:
    def __init__(self) -> None:
        self.by_name: dict[str, FakeNetwork] = {}

    def create(self, name: str, **kwargs: Any) -> FakeNetwork:
        del kwargs
        network = FakeNetwork(name=name)
        self.by_name[name] = network
        return network

    def get(self, name: str) -> FakeNetwork:
        return self.by_name[name]


@dataclass
class FakeVolume:
    name: str
    removed: bool = False

    def remove(self, force: bool = False) -> None:
        del force
        self.removed = True


class FakeVolumeManager:
    def __init__(self) -> None:
        self.by_name: dict[str, FakeVolume] = {}

    def create(self, name: str, **kwargs: Any) -> FakeVolume:
        del kwargs
        volume = FakeVolume(name=name)
        self.by_name[name] = volume
        return volume

    def get(self, name: str) -> FakeVolume:
        return self.by_name[name]


class FakeDockerClient:
    def __init__(self) -> None:
        self.containers = FakeContainerManager()
        self.networks = FakeNetworkManager()
        self.volumes = FakeVolumeManager()


def build_runtime() -> tuple[DockerRuntime, FakeDockerClient]:
    client = FakeDockerClient()
    return DockerRuntime(client=client), client


def build_spec(
    *,
    network_mode: NetworkMode = NetworkMode.RESTRICTED,
    persistence_mode: PersistenceMode = PersistenceMode.EPHEMERAL,
    secret_leases: list[SecretLease] | None = None,
) -> RuntimeSpec:
    return RuntimeSpec(
        image="python:3.12-slim",
        network_mode=network_mode,
        persistence_mode=persistence_mode,
        cpu_limit=2,
        memory_mb=2048,
        managed_mounts=[ManagedMount(source="labos-work-lab-123", target="/workspace")],
        secret_leases=secret_leases or [],
        labels={"labos.profile": "safe-dev"},
    )


def test_docker_runtime_reports_backend_name() -> None:
    runtime, _client = build_runtime()

    assert runtime.backend_name() == "docker"


def test_runtime_spec_contains_network_and_persistence() -> None:
    spec = build_spec()

    assert spec.network_mode is NetworkMode.RESTRICTED
    assert spec.persistence_mode is PersistenceMode.EPHEMERAL


def test_create_lab_applies_names_limits_labels_and_secret_env() -> None:
    runtime, client = build_runtime()
    lease = SecretLease(
        name="API_TOKEN",
        value="secret-value",
        approved=True,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    created = runtime.create_lab("lab-123", build_spec(secret_leases=[lease]))

    assert created.container_name == "labos-lab-123"
    assert created.network_name == "labos-net-lab-123"
    assert created.volume_names == ["labos-work-lab-123"]
    create_kwargs = client.containers.create_kwargs[0]
    assert create_kwargs["nano_cpus"] == 2_000_000_000
    assert create_kwargs["mem_limit"] == "2048m"
    assert create_kwargs["labels"]["labos.lab_id"] == "lab-123"
    assert create_kwargs["labels"]["labos.managed"] == "true"
    assert create_kwargs["environment"] == {"API_TOKEN": "secret-value"}
    assert create_kwargs["network"] == "labos-net-lab-123"
    assert create_kwargs["volumes"] == {"labos-work-lab-123": {"bind": "/workspace", "mode": "rw"}}


def test_create_lab_uses_network_none_for_deny_mode() -> None:
    runtime, client = build_runtime()

    runtime.create_lab("lab-123", build_spec(network_mode=NetworkMode.DENY))

    create_kwargs = client.containers.create_kwargs[0]
    assert create_kwargs["network_disabled"] is True
    assert create_kwargs["network"] is None


def test_create_lab_rejects_unapproved_or_expired_secret_leases() -> None:
    runtime, _client = build_runtime()
    unapproved = SecretLease(
        name="API_TOKEN",
        value="secret-value",
        approved=False,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    expired = SecretLease(
        name="EXPIRED",
        value="nope",
        approved=True,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="secret lease API_TOKEN is not approved"):
        runtime.create_lab("lab-123", build_spec(secret_leases=[unapproved]))

    with pytest.raises(ValueError, match="secret lease EXPIRED has expired"):
        runtime.create_lab("lab-123", build_spec(secret_leases=[expired]))


def test_runtime_cleans_up_network_and_volumes_when_container_create_fails() -> None:
    runtime, client = build_runtime()
    client.containers.fail_create = True

    with pytest.raises(RuntimeError, match="container create failed"):
        runtime.create_lab("lab-123", build_spec())

    assert client.networks.get("labos-net-lab-123").removed is True
    assert client.volumes.get("labos-work-lab-123").removed is True


def test_runtime_can_start_stop_exec_inspect_logs_and_destroy_lab() -> None:
    runtime, client = build_runtime()
    runtime.create_lab("lab-123", build_spec(persistence_mode=PersistenceMode.PERSISTENT))

    runtime.start_lab("lab-123")
    exec_result = runtime.exec_run("lab-123", "python -c 'print(1)'")
    inspection = runtime.inspect_lab("lab-123")
    logs = runtime.get_logs("lab-123")
    runtime.stop_lab("lab-123", timeout=3)
    runtime.destroy_lab("lab-123", remove_persistent_volume=False)

    assert exec_result.exit_code == 0
    assert exec_result.stdout == "hello from lab"
    assert inspection.status == "running"
    assert inspection.container_name == "labos-lab-123"
    assert inspection.backend == "docker"
    assert logs == "runtime logs"
    assert client.containers.get("labos-lab-123").stop_timeout == 3
    assert client.containers.get("labos-lab-123").removed is True
    assert client.networks.get("labos-net-lab-123").removed is True
    assert client.volumes.get("labos-work-lab-123").removed is False
