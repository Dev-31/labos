from __future__ import annotations

from pathlib import Path

import pytest

from labos.config.profiles.base import DEFAULT_PROFILES
from labos.core.policy_models import PersistenceMode
from labos.storage.allocator import ManagedStorageAllocator
from labos.storage.models import StoragePolicy


def test_storage_policy_derives_managed_defaults_from_profile() -> None:
    profile = DEFAULT_PROFILES["research-persistent"]

    policy = StoragePolicy.from_profile(profile)

    assert policy.persistence_mode is PersistenceMode.PERSISTENT
    assert policy.disk_mb == profile.disk_mb
    assert policy.retention_days == profile.retention_days
    assert policy.snapshot_capable is True
    assert policy.workspace_mount_target == "/workspace"


def test_allocator_creates_managed_paths_and_rejects_unmanaged_sources(tmp_path: Path) -> None:
    allocator = ManagedStorageAllocator(root=tmp_path / "managed")
    policy = StoragePolicy.from_profile(DEFAULT_PROFILES["safe-dev"])

    allocation = allocator.allocate("lab-123", policy)

    assert allocation.root_path == (tmp_path / "managed" / "labs" / "lab-123")
    assert allocation.workspace_path == allocation.root_path / "workspace"
    assert allocation.exports_path == allocation.root_path / "exports"
    assert allocation.quarantine_path == allocation.root_path / "quarantine"
    assert allocation.snapshots_path == allocation.root_path / "snapshots"
    assert allocation.runtime_mount().source == str(allocation.workspace_path)
    assert allocation.runtime_mount().target == "/workspace"

    allocator.assert_managed_path(allocation.workspace_path)
    with pytest.raises(ValueError, match="managed storage root"):
        allocator.assert_managed_path(Path("/etc/passwd"))
