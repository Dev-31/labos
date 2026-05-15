from __future__ import annotations

from types import SimpleNamespace

from labos.runtimes.docker_probe import probe_docker_environment


class FakeDockerClient:
    def __init__(self, *, ping_works: bool = True) -> None:
        self.ping_works = ping_works

    def ping(self) -> bool:
        if not self.ping_works:
            raise RuntimeError("daemon unavailable")
        return True


def test_probe_reports_missing_cli() -> None:
    result = probe_docker_environment(which=lambda _name: None)

    assert result.ready is False
    assert result.cli_present is False
    assert result.cli_path is None
    assert result.daemon_reachable is False
    assert result.daemon_error is None
    assert result.issue_code == "cli_missing"
    assert result.remediation == "install Docker CLI and ensure it is available on PATH"
    assert "docker CLI" in result.detail


def test_probe_reports_unreachable_daemon() -> None:
    result = probe_docker_environment(
        which=lambda _name: "/usr/bin/docker",
        client_factory=lambda: FakeDockerClient(ping_works=False),
    )

    assert result.ready is False
    assert result.cli_present is True
    assert result.cli_path == "/usr/bin/docker"
    assert result.daemon_reachable is False
    assert result.daemon_error == "daemon unavailable"
    assert result.issue_code == "daemon_unreachable"
    assert result.remediation == "start a reachable Docker daemon or point the client at one"
    assert "daemon unavailable" in result.detail


def test_probe_reports_permission_denied_daemon_access() -> None:
    result = probe_docker_environment(
        which=lambda _name: "/usr/bin/docker",
        client_factory=lambda: (_ for _ in ()).throw(
            PermissionError("permission denied while contacting docker daemon")
        ),
    )

    assert result.ready is False
    assert result.cli_present is True
    assert result.cli_path == "/usr/bin/docker"
    assert result.daemon_reachable is False
    assert result.issue_code == "daemon_permission_denied"
    assert result.remediation == (
        "run on a host/user that can access the Docker daemon "
        "(for example via docker group membership or a rootless Docker context)"
    )
    assert "permission denied" in (result.daemon_error or "")


def test_probe_reports_socket_access_context_for_unix_target(monkeypatch, tmp_path) -> None:
    socket_path = tmp_path / "docker.sock"
    socket_path.touch()

    monkeypatch.setattr("labos.runtimes.docker_probe.getpass.getuser", lambda: "ubuntu")
    monkeypatch.setattr("labos.runtimes.docker_probe.os.getgroups", lambda: [1001, 1002])

    def fake_group_from_gid(gid: int) -> SimpleNamespace:
        mapping = {
            1001: SimpleNamespace(gr_name="ubuntu"),
            1002: SimpleNamespace(gr_name="adm"),
            4242: SimpleNamespace(gr_name="docker"),
        }
        return mapping[gid]

    monkeypatch.setattr("labos.runtimes.docker_probe.grp.getgrgid", fake_group_from_gid)
    monkeypatch.setattr(
        "labos.runtimes.docker_probe.pwd.getpwuid",
        lambda uid: SimpleNamespace(pw_name="root"),
    )
    monkeypatch.setattr(
        "labos.runtimes.docker_probe.os.stat",
        lambda path: SimpleNamespace(st_uid=0, st_gid=4242, st_mode=0o140660),
    )

    result = probe_docker_environment(
        which=lambda _name: "/usr/bin/docker",
        client_factory=lambda: (_ for _ in ()).throw(PermissionError("permission denied")),
        env={"DOCKER_HOST": f"unix://{socket_path}"},
    )

    assert result.daemon_target == f"unix://{socket_path}"
    assert result.current_user == "ubuntu"
    assert result.user_groups == ("adm", "ubuntu")
    assert result.socket_path == str(socket_path)
    assert result.socket_exists is True
    assert result.socket_owner == "root"
    assert result.socket_group == "docker"
    assert result.socket_mode == "660"
    assert result.user_in_socket_group is False


def test_probe_reports_ready_environment() -> None:
    result = probe_docker_environment(
        which=lambda _name: "/usr/bin/docker",
        client_factory=lambda: FakeDockerClient(ping_works=True),
    )

    assert result.ready is True
    assert result.cli_present is True
    assert result.cli_path == "/usr/bin/docker"
    assert result.daemon_reachable is True
    assert result.daemon_error is None
    assert result.issue_code == "ready"
    assert result.remediation == "none"
    assert result.detail == "docker CLI and daemon are available"
