from __future__ import annotations

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
    assert "daemon unavailable" in result.detail


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
    assert result.detail == "docker CLI and daemon are available"
