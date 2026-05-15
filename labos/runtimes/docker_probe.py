from __future__ import annotations

import getpass
import grp
import os
import pwd
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from shutil import which as default_which
from stat import S_IMODE
from typing import Any

import docker  # type: ignore[import-untyped]

DEFAULT_DOCKER_TARGET = "unix:///var/run/docker.sock"


@dataclass(frozen=True)
class DockerEnvironmentProbe:
    cli_present: bool
    cli_path: str | None
    daemon_reachable: bool
    daemon_error: str | None
    detail: str
    issue_code: str
    remediation: str
    current_user: str | None = None
    user_groups: tuple[str, ...] = field(default_factory=tuple)
    daemon_target: str | None = None
    socket_path: str | None = None
    socket_exists: bool | None = None
    socket_owner: str | None = None
    socket_group: str | None = None
    socket_mode: str | None = None
    user_in_socket_group: bool | None = None

    @property
    def ready(self) -> bool:
        return self.cli_present and self.daemon_reachable


DockerClientFactory = Callable[[], Any]
WhichResolver = Callable[[str], str | None]


@dataclass(frozen=True)
class DockerAccessContext:
    current_user: str | None
    user_groups: tuple[str, ...]
    daemon_target: str
    socket_path: str | None
    socket_exists: bool | None
    socket_owner: str | None
    socket_group: str | None
    socket_mode: str | None
    user_in_socket_group: bool | None


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


def _docker_target(env: Mapping[str, str]) -> str:
    return env.get("DOCKER_HOST", DEFAULT_DOCKER_TARGET)


def _socket_path_from_target(daemon_target: str) -> str | None:
    if daemon_target.startswith("unix://"):
        return daemon_target.removeprefix("unix://")
    return None


def _group_name(group_id: int) -> str:
    return str(grp.getgrgid(group_id).gr_name)


def _access_context(env: Mapping[str, str]) -> DockerAccessContext:
    daemon_target = _docker_target(env)
    current_user = getpass.getuser()
    user_groups = tuple(sorted({_group_name(group_id) for group_id in os.getgroups()}))
    socket_path = _socket_path_from_target(daemon_target)
    if socket_path is None:
        return DockerAccessContext(
            current_user=current_user,
            user_groups=user_groups,
            daemon_target=daemon_target,
            socket_path=None,
            socket_exists=None,
            socket_owner=None,
            socket_group=None,
            socket_mode=None,
            user_in_socket_group=None,
        )

    socket_exists = os.path.exists(socket_path)
    if not socket_exists:
        return DockerAccessContext(
            current_user=current_user,
            user_groups=user_groups,
            daemon_target=daemon_target,
            socket_path=socket_path,
            socket_exists=False,
            socket_owner=None,
            socket_group=None,
            socket_mode=None,
            user_in_socket_group=None,
        )

    stat_result = os.stat(socket_path)
    socket_owner = str(pwd.getpwuid(stat_result.st_uid).pw_name)
    socket_group = _group_name(stat_result.st_gid)
    return DockerAccessContext(
        current_user=current_user,
        user_groups=user_groups,
        daemon_target=daemon_target,
        socket_path=socket_path,
        socket_exists=True,
        socket_owner=socket_owner,
        socket_group=socket_group,
        socket_mode=f"{S_IMODE(stat_result.st_mode):o}",
        user_in_socket_group=socket_group in user_groups,
    )


def probe_docker_environment(
    *,
    client_factory: DockerClientFactory | None = None,
    which: WhichResolver = default_which,
    env: Mapping[str, str] | None = None,
) -> DockerEnvironmentProbe:
    runtime_env = env or os.environ
    access_context = _access_context(runtime_env)
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
            current_user=access_context.current_user,
            user_groups=access_context.user_groups,
            daemon_target=access_context.daemon_target,
            socket_path=access_context.socket_path,
            socket_exists=access_context.socket_exists,
            socket_owner=access_context.socket_owner,
            socket_group=access_context.socket_group,
            socket_mode=access_context.socket_mode,
            user_in_socket_group=access_context.user_in_socket_group,
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
            current_user=access_context.current_user,
            user_groups=access_context.user_groups,
            daemon_target=access_context.daemon_target,
            socket_path=access_context.socket_path,
            socket_exists=access_context.socket_exists,
            socket_owner=access_context.socket_owner,
            socket_group=access_context.socket_group,
            socket_mode=access_context.socket_mode,
            user_in_socket_group=access_context.user_in_socket_group,
        )

    return DockerEnvironmentProbe(
        cli_present=True,
        cli_path=docker_path,
        daemon_reachable=True,
        daemon_error=None,
        detail="docker CLI and daemon are available",
        issue_code="ready",
        remediation="none",
        current_user=access_context.current_user,
        user_groups=access_context.user_groups,
        daemon_target=access_context.daemon_target,
        socket_path=access_context.socket_path,
        socket_exists=access_context.socket_exists,
        socket_owner=access_context.socket_owner,
        socket_group=access_context.socket_group,
        socket_mode=access_context.socket_mode,
        user_in_socket_group=access_context.user_in_socket_group,
    )
