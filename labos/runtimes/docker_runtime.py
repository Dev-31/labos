from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import docker  # type: ignore[import-untyped]

from labos.core.policy_models import NetworkMode, PersistenceMode
from labos.runtimes.base import (
    LabInspection,
    ManagedMount,
    ProvisionedLab,
    RunExecutionResult,
    RuntimeSpec,
)


class DockerRuntime:
    """Docker-backed LabOS runtime with managed naming and conservative defaults."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client or docker.from_env()

    def backend_name(self) -> str:
        return "docker"

    def container_name(self, lab_id: str) -> str:
        return f"labos-{lab_id}"

    def network_name(self, lab_id: str) -> str:
        return f"labos-net-{lab_id}"

    def labels(self, lab_id: str, extra_labels: Mapping[str, str] | None = None) -> dict[str, str]:
        labels = {
            "labos.managed": "true",
            "labos.lab_id": lab_id,
            "labos.runtime": self.backend_name(),
        }
        if extra_labels:
            labels.update(dict(extra_labels))
        return labels

    def list_managed_labs(self) -> list[LabInspection]:
        containers = self._client.containers.list(all=True, filters={"label": "labos.managed=true"})
        inspections: list[LabInspection] = []
        for container in containers:
            labels = dict(cast(dict[str, str], getattr(container, "labels", {})))
            lab_id = labels.get("labos.lab_id")
            if lab_id is None:
                continue
            inspections.append(
                LabInspection(
                    lab_id=lab_id,
                    backend=self.backend_name(),
                    container_name=str(getattr(container, "name", self.container_name(lab_id))),
                    status=str(getattr(container, "status", "unknown")),
                    labels=labels,
                )
            )
        inspections.sort(key=lambda inspection: inspection.lab_id)
        return inspections

    def create_lab(self, lab_id: str, spec: RuntimeSpec) -> ProvisionedLab:
        container_name = self.container_name(lab_id)
        network_name = None if spec.network_mode is NetworkMode.DENY else self.network_name(lab_id)
        volume_names = [mount.source for mount in spec.managed_mounts]
        labels = self.labels(lab_id, spec.labels)
        created_network = None
        created_volumes: list[Any] = []

        try:
            if network_name is not None:
                created_network = self._client.networks.create(
                    network_name,
                    internal=spec.network_mode is NetworkMode.RESTRICTED,
                    check_duplicate=True,
                    labels=labels,
                )

            for mount in spec.managed_mounts:
                created_volumes.append(self._ensure_volume(mount.source, labels))

            self._client.containers.create(
                spec.image,
                name=container_name,
                command=spec.command,
                detach=True,
                labels=labels,
                environment=self._build_environment(spec),
                volumes=self._build_volumes(spec.managed_mounts),
                network=network_name,
                network_disabled=spec.network_mode is NetworkMode.DENY,
                nano_cpus=spec.cpu_limit * 1_000_000_000,
                mem_limit=f"{spec.memory_mb}m",
                read_only=spec.persistence_mode is PersistenceMode.EPHEMERAL,
            )
        except Exception:
            if created_network is not None:
                created_network.remove()
            for volume in created_volumes:
                volume.remove(force=True)
            raise

        return ProvisionedLab(
            lab_id=lab_id,
            backend=self.backend_name(),
            container_name=container_name,
            network_name=network_name,
            volume_names=volume_names,
        )

    def start_lab(self, lab_id: str) -> None:
        self._get_container(lab_id).start()

    def stop_lab(self, lab_id: str, timeout: int = 10) -> None:
        self._get_container(lab_id).stop(timeout=timeout)

    def destroy_lab(self, lab_id: str, remove_persistent_volume: bool = False) -> None:
        container = self._get_container(lab_id)
        mounts = self._extract_volume_names(container)
        container.remove(force=True)

        network_name = self.network_name(lab_id)
        try:
            self._client.networks.get(network_name).remove()
        except Exception:
            pass

        if remove_persistent_volume:
            for volume_name in mounts:
                try:
                    self._client.volumes.get(volume_name).remove(force=True)
                except Exception:
                    pass

    def exec_run(self, lab_id: str, command: str) -> RunExecutionResult:
        result = self._get_container(lab_id).exec_run(command)
        return RunExecutionResult(
            exit_code=int(result.exit_code),
            stdout=result.output.decode("utf-8"),
            stderr="",
        )

    def get_logs(self, lab_id: str, tail: int | str = "all") -> str:
        output = self._get_container(lab_id).logs(tail=tail)
        return cast(bytes, output).decode("utf-8")

    def inspect_lab(self, lab_id: str) -> LabInspection:
        container = self._get_container(lab_id)
        container.reload()
        attrs = cast(dict[str, Any], container.attrs)
        state = cast(dict[str, Any], attrs.get("State", {}))
        return LabInspection(
            lab_id=lab_id,
            backend=self.backend_name(),
            container_name=self.container_name(lab_id),
            status=str(state.get("Status", "unknown")),
            labels=self.labels(lab_id),
        )

    def _get_container(self, lab_id: str) -> Any:
        return self._client.containers.get(self.container_name(lab_id))

    def _ensure_volume(self, volume_name: str, labels: Mapping[str, str]) -> Any:
        return self._client.volumes.create(name=volume_name, labels=dict(labels))

    def _build_environment(self, spec: RuntimeSpec) -> dict[str, str]:
        environment: dict[str, str] = {}
        for lease in spec.secret_leases:
            if not lease.approved:
                raise ValueError(f"secret lease {lease.name} is not approved")
            if not lease.is_active():
                raise ValueError(f"secret lease {lease.name} has expired")
            environment[lease.name] = lease.value
        return environment

    def _build_volumes(self, mounts: list[ManagedMount]) -> dict[str, dict[str, str]]:
        return {
            mount.source: {
                "bind": mount.target,
                "mode": "ro" if mount.read_only else "rw",
            }
            for mount in mounts
        }

    def _extract_volume_names(self, container: Any) -> list[str]:
        attrs = cast(dict[str, Any], container.attrs)
        mounts = cast(list[dict[str, Any]], attrs.get("Mounts", []))
        volume_names: list[str] = []
        for mount in mounts:
            mount_name = mount.get("Name")
            if mount_name:
                volume_names.append(str(mount_name))
        return volume_names
