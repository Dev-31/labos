from __future__ import annotations

from uuid import uuid4

import pytest

from labos.core.policy_models import NetworkMode, PersistenceMode
from labos.runtimes.base import ManagedMount, RuntimeSpec
from labos.runtimes.docker_probe import probe_docker_environment
from labos.runtimes.docker_runtime import DockerRuntime


@pytest.mark.integration
def test_docker_runtime_smoke() -> None:
    probe = probe_docker_environment()
    if not probe.ready:
        pytest.skip(f"Docker runtime smoke requires a local Docker daemon: {probe.detail}")

    runtime = DockerRuntime()
    suffix = uuid4().hex[:8]
    lab_id = f"smoke-{suffix}"
    volume_name = f"labos-smoke-work-{suffix}"
    spec = RuntimeSpec(
        image="python:3.12-slim",
        network_mode=NetworkMode.RESTRICTED,
        persistence_mode=PersistenceMode.EPHEMERAL,
        cpu_limit=1,
        memory_mb=512,
        managed_mounts=[ManagedMount(source=volume_name, target="/workspace")],
        labels={"labos.profile": "safe-dev", "labos.test": "docker-smoke"},
        command=["sh", "-c", "while true; do sleep 3600; done"],
    )

    created = runtime.create_lab(lab_id, spec)
    try:
        runtime.start_lab(lab_id)
        command = "sh -lc 'echo docker-smoke > /workspace/hello.txt && cat /workspace/hello.txt'"
        result = runtime.exec_run(lab_id, command)
        inspection = runtime.inspect_lab(lab_id)
        managed_labs = runtime.list_managed_labs()

        assert created.container_name == f"labos-{lab_id}"
        assert result.exit_code == 0
        assert result.stdout.strip() == "docker-smoke"
        assert inspection.lab_id == lab_id
        assert inspection.status == "running"
        assert any(lab.lab_id == lab_id for lab in managed_labs)
    finally:
        runtime.destroy_lab(lab_id, remove_persistent_volume=True)

    assert all(lab.lab_id != lab_id for lab in runtime.list_managed_labs())
