from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from shutil import which as default_which
from typing import Any

import docker  # type: ignore[import-untyped]


@dataclass(frozen=True)
class DockerEnvironmentProbe:
    cli_present: bool
    cli_path: str | None
    daemon_reachable: bool
    daemon_error: str | None
    detail: str
    issue_code: str
    remediation: str

    @property
    def ready(self) -> bool:
        return self.cli_present and self.daemon_reachable


DockerClientFactory = Callable[[], Any]
WhichResolver = Callable[[str], str | None]


def _classify_daemon_error(error: str) -> tuple[str, str]:
    normalized = error.lower()
    if "permission denied" in normalized:
        return (
            "daemon_permission_denied",
            "run on a host/user that can access the Docker daemon "
            "(for example via docker group membership or a rootless Docker context)",
        )
    return (
        "daemon_unreachable",
        "start a reachable Docker daemon or point the client at one",
    )


def probe_docker_environment(
    *,
    client_factory: DockerClientFactory | None = None,
    which: WhichResolver = default_which,
) -> DockerEnvironmentProbe:
    docker_path = which("docker")
    if docker_path is None:
        return DockerEnvironmentProbe(
            cli_present=False,
            cli_path=None,
            daemon_reachable=False,
            daemon_error=None,
            detail="docker CLI is not installed or not on PATH",
            issue_code="cli_missing",
            remediation="install Docker CLI and ensure it is available on PATH",
        )

    factory = client_factory or docker.from_env
    try:
        client = factory()
        client.ping()
    except Exception as exc:
        issue_code, remediation = _classify_daemon_error(str(exc))
        return DockerEnvironmentProbe(
            cli_present=True,
            cli_path=docker_path,
            daemon_reachable=False,
            daemon_error=str(exc),
            detail=f"docker daemon is not reachable: {exc}",
            issue_code=issue_code,
            remediation=remediation,
        )

    return DockerEnvironmentProbe(
        cli_present=True,
        cli_path=docker_path,
        daemon_reachable=True,
        daemon_error=None,
        detail="docker CLI and daemon are available",
        issue_code="ready",
        remediation="none",
    )
