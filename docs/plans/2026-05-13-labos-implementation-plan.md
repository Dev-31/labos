# LabOS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 1 of LabOS: a policy-first research containment platform with container labs by default, microVM-ready architecture for high-risk labs, API + CLI control, audit events, snapshots, approvals, scheduler hooks, and export quarantine.

**Architecture:** Build a new control plane repo rather than forking an existing product. Reuse existing runtime foundations under the hood: Docker/containerd for standard labs and a Firecracker-class adapter boundary for high-risk labs. Study mature adjacent repos for patterns, but keep LabOS as its own API, policy, and lifecycle product.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy/SQLModel or SQLAlchemy Core, Alembic, PostgreSQL, Docker Engine/SDK, optional Firecracker adapter interface, Typer CLI, pytest, httpx, uv.

---

## Repo / Runtime Combination Strategy

### Direct dependencies / foundations
- **Docker Engine / containerd** — real runtime for Phase 1 standard labs
- **Firecracker-compatible backend boundary** — adapter interface designed in Phase 1, first serious implementation in Phase 2
- **PostgreSQL** — durable state for labs, runs, approvals, exports, snapshots, events
- **FastAPI** — control plane API
- **Typer** — operator CLI

### Repos to study and selectively borrow patterns from
- **`kubernetes-sigs/agent-sandbox`**
  - use as reference for lifecycle, templating, claims/warm-pool thinking, and persistent sandbox concepts
  - do **not** make Kubernetes the Phase 1 control plane
- **`abshkbh/arrakis`**
  - use as reference for microVM-oriented API shape, snapshot-and-restore semantics, and risky-agent workload handling
  - do **not** inherit its full server architecture blindly
- **`trycua/cua`**
  - use as reference for SDK ergonomics, multi-runtime abstraction, and future benchmark/computer-use lab patterns
  - do **not** pull its product surface into Phase 1
- **`arjan/awesome-agent-sandboxes`**
  - use as a market map/checklist so LabOS doesn't accidentally rebuild a commodity feature set without differentiation

### Explicit product stance
Do **not** combine these repos by merging codebases into one messy fork. Combine them at the **idea/pattern/runtime-boundary** level while keeping LabOS as a clean new repo.

---

## Proposed Initial Repo Structure

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `ROADMAP.md`
- Create: `SECURITY.md`
- Create: `CONTRIBUTING.md`
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `Makefile`
- Create: `docs/architecture.md`
- Create: `docs/threat-model.md`
- Create: `docs/repo-sources.md`
- Create: `labos/__init__.py`
- Create: `labos/api/`
- Create: `labos/core/`
- Create: `labos/runtimes/`
- Create: `labos/storage/`
- Create: `labos/security/`
- Create: `labos/workers/`
- Create: `labos/cli/`
- Create: `labos/db/`
- Create: `labos/config/`
- Create: `tests/`

---

### Task 1: Scaffold the repo and freeze product boundaries

**Files:**
- Create: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/threat-model.md`
- Create: `docs/repo-sources.md`
- Create: `pyproject.toml`
- Create: `labos/__init__.py`
- Test: `tests/test_imports.py`

- [ ] **Step 1: Write the failing import smoke test**

```python
# tests/test_imports.py
from importlib import import_module


def test_core_modules_import():
    modules = [
        "labos",
        "labos.api.app",
        "labos.core.models",
        "labos.core.policy_engine",
        "labos.runtimes.base",
        "labos.cli.main",
    ]
    for module in modules:
        import_module(module)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_imports.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'labos'`

- [ ] **Step 3: Create minimal package + dependency scaffold**

```toml
# pyproject.toml
[project]
name = "labos"
version = "0.1.0"
description = "Policy-first research containment platform for agents and risky experiments"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn>=0.30",
  "pydantic>=2.8",
  "sqlalchemy>=2.0",
  "alembic>=1.13",
  "psycopg[binary]>=3.2",
  "docker>=7.1",
  "typer>=0.12",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.23",
  "ruff>=0.6",
  "mypy>=1.11",
]

[project.scripts]
labos = "labos.cli.main:app"
```

```python
# labos/__init__.py
__all__ = ["__version__"]
__version__ = "0.1.0"
```

```markdown
# docs/repo-sources.md
# External References

## Runtime / platform references
- kubernetes-sigs/agent-sandbox: lifecycle and sandbox-template concepts
- abshkbh/arrakis: microVM sandbox and snapshot semantics
- trycua/cua: sandbox SDK ergonomics and future benchmark patterns
- arjan/awesome-agent-sandboxes: market/category map

## Rule
These references inform architecture. LabOS remains a clean new control plane, not a merged fork.
```

- [ ] **Step 4: Add architecture and threat-model stubs that lock scope**

```markdown
# docs/architecture.md
# LabOS Architecture

LabOS is a policy-first control plane for isolated labs.

Phase 1:
- API + CLI
- Docker-backed standard labs
- microVM adapter boundary
- policy profiles
- approvals
- audit events
- snapshots
- export gate
```

```markdown
# docs/threat-model.md
# Threat Model

## Primary risks
- host contamination from untrusted code
- accidental secret leakage
- unrestricted egress
- unsafe artifact export
- long-lived zombie labs

## Phase 1 stance
- no host env inheritance by default
- no direct host writes
- network explicit by policy
- exports quarantined
```

- [ ] **Step 5: Add minimal importable modules**

```python
# labos/api/app.py
from fastapi import FastAPI

app = FastAPI(title="LabOS")
```

```python
# labos/core/models.py
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
```

```python
# labos/core/policy_engine.py
class PolicyEngine:
    pass
```

```python
# labos/runtimes/base.py
class RuntimeAdapter:
    pass
```

```python
# labos/cli/main.py
import typer

app = typer.Typer(help="LabOS operator CLI")
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `pytest tests/test_imports.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml docs/architecture.md docs/threat-model.md docs/repo-sources.md labos tests/test_imports.py
git commit -m "chore: scaffold labos repo and architecture docs"
```

### Task 2: Define domain models and state machine

**Files:**
- Create: `labos/core/enums.py`
- Create: `labos/core/entities.py`
- Create: `labos/core/state_machine.py`
- Create: `tests/core/test_state_machine.py`

- [ ] **Step 1: Write the failing state transition tests**

```python
# tests/core/test_state_machine.py
import pytest
from labos.core.enums import LabState, RunState
from labos.core.state_machine import can_transition_lab, can_transition_run


def test_lab_valid_transition_requested_to_approved():
    assert can_transition_lab(LabState.REQUESTED, LabState.APPROVED) is True


def test_lab_invalid_transition_destroyed_to_running():
    assert can_transition_lab(LabState.DESTROYED, LabState.RUNNING) is False


def test_run_valid_transition_starting_to_running():
    assert can_transition_run(RunState.STARTING, RunState.RUNNING) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_state_machine.py -v`
Expected: FAIL because enums/state helpers do not exist

- [ ] **Step 3: Define explicit enums and transition maps**

```python
# labos/core/enums.py
from enum import StrEnum


class LabState(StrEnum):
    REQUESTED = "requested"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"
    ARCHIVED = "archived"


class RunState(StrEnum):
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
```

```python
# labos/core/state_machine.py
from labos.core.enums import LabState, RunState

LAB_TRANSITIONS = {
    LabState.REQUESTED: {LabState.PENDING_APPROVAL, LabState.APPROVED, LabState.FAILED},
    LabState.PENDING_APPROVAL: {LabState.APPROVED, LabState.FAILED},
    LabState.APPROVED: {LabState.PROVISIONING, LabState.FAILED},
    LabState.PROVISIONING: {LabState.RUNNING, LabState.FAILED},
    LabState.RUNNING: {LabState.STOPPED, LabState.FAILED, LabState.DESTROYING},
    LabState.STOPPED: {LabState.RUNNING, LabState.DESTROYING, LabState.ARCHIVED},
    LabState.FAILED: {LabState.DESTROYING, LabState.ARCHIVED},
    LabState.DESTROYING: {LabState.DESTROYED},
    LabState.DESTROYED: set(),
    LabState.ARCHIVED: set(),
}

RUN_TRANSITIONS = {
    RunState.QUEUED: {RunState.STARTING, RunState.CANCELLED},
    RunState.STARTING: {RunState.RUNNING, RunState.FAILED, RunState.CANCELLED},
    RunState.RUNNING: {RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED, RunState.TIMED_OUT},
    RunState.COMPLETED: set(),
    RunState.FAILED: set(),
    RunState.CANCELLED: set(),
    RunState.TIMED_OUT: set(),
}


def can_transition_lab(current: LabState, target: LabState) -> bool:
    return target in LAB_TRANSITIONS[current]


def can_transition_run(current: RunState, target: RunState) -> bool:
    return target in RUN_TRANSITIONS[current]
```

- [ ] **Step 4: Add core entities**

```python
# labos/core/entities.py
from dataclasses import dataclass
from datetime import datetime
from labos.core.enums import LabState, RunState


@dataclass
class Lab:
    id: str
    profile_name: str
    state: LabState
    created_at: datetime


@dataclass
class Run:
    id: str
    lab_id: str
    state: RunState
    created_at: datetime
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/core/test_state_machine.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add labos/core/enums.py labos/core/entities.py labos/core/state_machine.py tests/core/test_state_machine.py
git commit -m "feat: define lab and run state machines"
```

### Task 3: Build profile schema and policy engine

**Files:**
- Create: `labos/config/profiles/base.py`
- Create: `labos/core/policy_models.py`
- Create: `labos/core/policy_engine.py`
- Create: `examples/profiles/safe-dev.yaml`
- Create: `examples/profiles/model-local.yaml`
- Create: `examples/profiles/research-persistent.yaml`
- Create: `examples/profiles/red-zone.yaml`
- Create: `tests/core/test_policy_engine.py`

- [ ] **Step 1: Write failing policy tests**

```python
# tests/core/test_policy_engine.py
from labos.core.policy_engine import PolicyEngine


def test_red_zone_requires_microvm():
    engine = PolicyEngine()
    decision = engine.validate_request(
        profile_name="red-zone",
        requested_overrides={},
        requester_type="agent",
    )
    assert decision.runtime_class == "microvm"
    assert decision.approval_required is True


def test_safe_dev_export_needs_request_not_direct_host_write():
    engine = PolicyEngine()
    decision = engine.validate_export("safe-dev", "/lab/exports/report.json")
    assert decision.allowed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_policy_engine.py -v`
Expected: FAIL because engine and models are incomplete

- [ ] **Step 3: Define the policy schema**

```python
# labos/core/policy_models.py
from pydantic import BaseModel


class Profile(BaseModel):
    name: str
    runtime_class: str
    network_mode: str
    persistence_mode: str
    export_mode: str
    approval_on_start: bool = False
    approval_on_export: bool = False
    max_runtime_minutes: int
```

```python
# labos/config/profiles/base.py
DEFAULT_PROFILES = {
    "safe-dev": {
        "name": "safe-dev",
        "runtime_class": "container",
        "network_mode": "restricted",
        "persistence_mode": "ephemeral",
        "export_mode": "request",
        "approval_on_start": False,
        "approval_on_export": False,
        "max_runtime_minutes": 60,
    },
    "model-local": {
        "name": "model-local",
        "runtime_class": "container",
        "network_mode": "restricted",
        "persistence_mode": "persistent",
        "export_mode": "request",
        "approval_on_start": False,
        "approval_on_export": True,
        "max_runtime_minutes": 480,
    },
    "research-persistent": {
        "name": "research-persistent",
        "runtime_class": "container",
        "network_mode": "restricted",
        "persistence_mode": "persistent",
        "export_mode": "request",
        "approval_on_start": False,
        "approval_on_export": True,
        "max_runtime_minutes": 4320,
    },
    "red-zone": {
        "name": "red-zone",
        "runtime_class": "microvm",
        "network_mode": "deny",
        "persistence_mode": "ephemeral",
        "export_mode": "approval",
        "approval_on_start": True,
        "approval_on_export": True,
        "max_runtime_minutes": 120,
    },
}
```

- [ ] **Step 4: Implement policy decisions**

```python
# labos/core/policy_engine.py
from dataclasses import dataclass
from labos.config.profiles.base import DEFAULT_PROFILES
from labos.core.policy_models import Profile


@dataclass
class RequestDecision:
    runtime_class: str
    approval_required: bool


@dataclass
class ExportDecision:
    allowed: bool
    approval_required: bool


class PolicyEngine:
    def __init__(self):
        self.profiles = {k: Profile(**v) for k, v in DEFAULT_PROFILES.items()}

    def get_profile(self, name: str) -> Profile:
        return self.profiles[name]

    def validate_request(self, profile_name: str, requested_overrides: dict, requester_type: str) -> RequestDecision:
        profile = self.get_profile(profile_name)
        return RequestDecision(
            runtime_class=profile.runtime_class,
            approval_required=profile.approval_on_start,
        )

    def validate_export(self, profile_name: str, export_path: str) -> ExportDecision:
        profile = self.get_profile(profile_name)
        allowed = export_path.startswith("/lab/exports/") or export_path.startswith("/artifacts/approved/")
        return ExportDecision(allowed=allowed, approval_required=profile.approval_on_export)
```

- [ ] **Step 5: Add example YAML profiles for operators**

```yaml
# examples/profiles/red-zone.yaml
name: red-zone
runtime_class: microvm
network_mode: deny
persistence_mode: ephemeral
export_mode: approval
approval_on_start: true
approval_on_export: true
max_runtime_minutes: 120
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/core/test_policy_engine.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add labos/config/profiles/base.py labos/core/policy_models.py labos/core/policy_engine.py examples/profiles tests/core/test_policy_engine.py
git commit -m "feat: add profile schema and policy engine"
```

### Task 4: Create persistence layer and database schema

**Files:**
- Create: `labos/db/schema.py`
- Create: `labos/db/session.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_initial.py`
- Create: `tests/db/test_schema.py`

- [ ] **Step 1: Write failing schema test**

```python
# tests/db/test_schema.py
from labos.db.schema import Base


def test_metadata_contains_core_tables():
    tables = set(Base.metadata.tables.keys())
    assert {"labs", "runs", "approvals", "exports", "snapshots", "events"}.issubset(tables)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/db/test_schema.py -v`
Expected: FAIL because schema is missing

- [ ] **Step 3: Add SQLAlchemy schema**

```python
# labos/db/schema.py
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime


class Base(DeclarativeBase):
    pass


class LabRow(Base):
    __tablename__ = "labs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    profile_name: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    runtime_class: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RunRow(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.id"), nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)


class ApprovalRow(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lab_id: Mapped[str | None] = mapped_column(ForeignKey("labs.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)


class ExportRow(Base):
    __tablename__ = "exports"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.id"), nullable=False)
    source_path: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)


class SnapshotRow(Base):
    __tablename__ = "snapshots"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.id"), nullable=False)
    backend_ref: Mapped[str] = mapped_column(String, nullable=False)


class EventRow(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lab_id: Mapped[str | None] = mapped_column(ForeignKey("labs.id"), nullable=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
```

- [ ] **Step 4: Add DB session helper and initial migration**

```python
# labos/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def build_engine(url: str):
    return create_engine(url, future=True)


def build_session_factory(url: str):
    engine = build_engine(url)
    return sessionmaker(bind=engine, future=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/db/test_schema.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add labos/db/schema.py labos/db/session.py alembic.ini alembic tests/db/test_schema.py
git commit -m "feat: add durable schema for labs runs approvals exports snapshots and events"
```

### Task 5: Implement Docker runtime adapter

**Files:**
- Create: `labos/runtimes/docker_runtime.py`
- Modify: `labos/runtimes/base.py`
- Create: `tests/runtimes/test_docker_runtime.py`

- [ ] **Step 1: Write failing runtime contract tests**

```python
# tests/runtimes/test_docker_runtime.py
from labos.runtimes.base import RuntimeSpec
from labos.runtimes.docker_runtime import DockerRuntime


def test_docker_runtime_reports_backend_name():
    runtime = DockerRuntime()
    assert runtime.backend_name() == "docker"


def test_runtime_spec_contains_network_and_persistence():
    spec = RuntimeSpec(
        image="python:3.12-slim",
        network_mode="restricted",
        persistence_mode="ephemeral",
        cpu_limit=1,
        memory_mb=1024,
    )
    assert spec.network_mode == "restricted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtimes/test_docker_runtime.py -v`
Expected: FAIL because contract is missing

- [ ] **Step 3: Define the runtime interface**

```python
# labos/runtimes/base.py
from dataclasses import dataclass
from typing import Protocol


@dataclass
class RuntimeSpec:
    image: str
    network_mode: str
    persistence_mode: str
    cpu_limit: int
    memory_mb: int


class RuntimeAdapter(Protocol):
    def backend_name(self) -> str: ...
    def create_lab(self, lab_id: str, spec: RuntimeSpec) -> dict: ...
    def destroy_lab(self, lab_id: str) -> None: ...
    def exec_run(self, lab_id: str, command: str) -> dict: ...
```

- [ ] **Step 4: Implement Docker adapter skeleton**

```python
# labos/runtimes/docker_runtime.py
from labos.runtimes.base import RuntimeSpec


class DockerRuntime:
    def backend_name(self) -> str:
        return "docker"

    def create_lab(self, lab_id: str, spec: RuntimeSpec) -> dict:
        return {
            "lab_id": lab_id,
            "backend": "docker",
            "container_name": f"labos-{lab_id}",
            "image": spec.image,
        }

    def destroy_lab(self, lab_id: str) -> None:
        return None

    def exec_run(self, lab_id: str, command: str) -> dict:
        return {
            "lab_id": lab_id,
            "command": command,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/runtimes/test_docker_runtime.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add labos/runtimes/base.py labos/runtimes/docker_runtime.py tests/runtimes/test_docker_runtime.py
git commit -m "feat: add docker runtime adapter contract"
```

### Task 6: Implement lab service, event logging, and run execution

**Files:**
- Create: `labos/core/events.py`
- Create: `labos/core/lab_service.py`
- Create: `labos/core/run_service.py`
- Create: `tests/core/test_lab_service.py`

- [ ] **Step 1: Write failing lifecycle service tests**

```python
# tests/core/test_lab_service.py
from labos.core.lab_service import LabService
from labos.core.policy_engine import PolicyEngine
from labos.runtimes.docker_runtime import DockerRuntime


def test_create_lab_returns_runtime_selection():
    service = LabService(policy_engine=PolicyEngine(), runtime_registry={"container": DockerRuntime()})
    result = service.create_lab_request(profile_name="safe-dev", requester_type="human")
    assert result["runtime_class"] == "container"
    assert result["state"] in {"approved", "pending_approval"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_lab_service.py -v`
Expected: FAIL because services are missing

- [ ] **Step 3: Implement simple event emitter and service methods**

```python
# labos/core/events.py
from dataclasses import dataclass


@dataclass
class Event:
    event_type: str
    payload: dict
```

```python
# labos/core/lab_service.py
from labos.core.events import Event


class LabService:
    def __init__(self, policy_engine, runtime_registry):
        self.policy_engine = policy_engine
        self.runtime_registry = runtime_registry
        self.events = []

    def create_lab_request(self, profile_name: str, requester_type: str) -> dict:
        decision = self.policy_engine.validate_request(profile_name, {}, requester_type)
        state = "pending_approval" if decision.approval_required else "approved"
        event = Event("lab.requested", {"profile_name": profile_name, "runtime_class": decision.runtime_class})
        self.events.append(event)
        return {
            "profile_name": profile_name,
            "runtime_class": decision.runtime_class,
            "state": state,
        }
```

- [ ] **Step 4: Add run service contract**

```python
# labos/core/run_service.py
class RunService:
    def __init__(self, runtime_registry):
        self.runtime_registry = runtime_registry

    def start_run(self, runtime_class: str, lab_id: str, command: str) -> dict:
        runtime = self.runtime_registry[runtime_class]
        return runtime.exec_run(lab_id, command)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/core/test_lab_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add labos/core/events.py labos/core/lab_service.py labos/core/run_service.py tests/core/test_lab_service.py
git commit -m "feat: add lab lifecycle service and event emission"
```

### Task 7: Add export gate and snapshot service

**Files:**
- Create: `labos/security/export_gate.py`
- Create: `labos/storage/snapshots.py`
- Create: `tests/security/test_export_gate.py`

- [ ] **Step 1: Write failing export gate tests**

```python
# tests/security/test_export_gate.py
from labos.security.export_gate import ExportGate


def test_export_gate_allows_quarantined_export_path():
    gate = ExportGate()
    result = gate.check_path("/lab/exports/report.json")
    assert result is True


def test_export_gate_rejects_random_host_path():
    gate = ExportGate()
    result = gate.check_path("/etc/passwd")
    assert result is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/security/test_export_gate.py -v`
Expected: FAIL because gate is missing

- [ ] **Step 3: Implement export gate path policy and snapshot stub**

```python
# labos/security/export_gate.py
class ExportGate:
    ALLOWED_PREFIXES = ("/lab/exports/", "/artifacts/approved/")

    def check_path(self, path: str) -> bool:
        return path.startswith(self.ALLOWED_PREFIXES)
```

```python
# labos/storage/snapshots.py
class SnapshotService:
    def create_snapshot(self, lab_id: str, backend_name: str) -> dict:
        return {
            "lab_id": lab_id,
            "backend_name": backend_name,
            "snapshot_ref": f"{backend_name}:{lab_id}:snapshot-001",
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/security/test_export_gate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add labos/security/export_gate.py labos/storage/snapshots.py tests/security/test_export_gate.py
git commit -m "feat: add export gate and snapshot service stubs"
```

### Task 8: Build API routes for labs, runs, approvals, exports, health

**Files:**
- Modify: `labos/api/app.py`
- Create: `labos/api/routes_health.py`
- Create: `labos/api/routes_labs.py`
- Create: `labos/api/routes_runs.py`
- Create: `labos/api/routes_exports.py`
- Create: `labos/api/routes_approvals.py`
- Create: `tests/api/test_health.py`
- Create: `tests/api/test_labs_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
# tests/api/test_health.py
from fastapi.testclient import TestClient
from labos.api.app import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

```python
# tests/api/test_labs_api.py
from fastapi.testclient import TestClient
from labos.api.app import app


def test_create_lab_request():
    client = TestClient(app)
    response = client.post("/labs", json={"profile_name": "safe-dev", "requester_type": "human"})
    assert response.status_code == 201
    assert response.json()["runtime_class"] == "container"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_health.py tests/api/test_labs_api.py -v`
Expected: FAIL because routes do not exist

- [ ] **Step 3: Implement minimal routes**

```python
# labos/api/routes_health.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}
```

```python
# labos/api/routes_labs.py
from fastapi import APIRouter, status
from pydantic import BaseModel
from labos.core.lab_service import LabService
from labos.core.policy_engine import PolicyEngine
from labos.runtimes.docker_runtime import DockerRuntime

router = APIRouter()
service = LabService(policy_engine=PolicyEngine(), runtime_registry={"container": DockerRuntime()})

class CreateLabRequest(BaseModel):
    profile_name: str
    requester_type: str

@router.post("/labs", status_code=status.HTTP_201_CREATED)
def create_lab(request: CreateLabRequest):
    return service.create_lab_request(request.profile_name, request.requester_type)
```

```python
# labos/api/app.py
from fastapi import FastAPI
from labos.api.routes_health import router as health_router
from labos.api.routes_labs import router as labs_router

app = FastAPI(title="LabOS")
app.include_router(health_router)
app.include_router(labs_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/api/test_health.py tests/api/test_labs_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add labos/api/app.py labos/api/routes_health.py labos/api/routes_labs.py tests/api/test_health.py tests/api/test_labs_api.py
git commit -m "feat: expose health and lab creation api routes"
```

### Task 9: Build operator CLI

**Files:**
- Modify: `labos/cli/main.py`
- Create: `labos/cli/labs.py`
- Create: `labos/cli/runs.py`
- Create: `labos/cli/profiles.py`
- Create: `tests/cli/test_cli_help.py`

- [ ] **Step 1: Write the failing CLI help test**

```python
# tests/cli/test_cli_help.py
from typer.testing import CliRunner
from labos.cli.main import app


def test_cli_has_labs_command_group():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "labs" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_cli_help.py -v`
Expected: FAIL because command groups are missing

- [ ] **Step 3: Add CLI command groups**

```python
# labos/cli/labs.py
import typer

app = typer.Typer(help="Manage labs")

@app.command("list")
def list_labs():
    typer.echo("[]")
```

```python
# labos/cli/profiles.py
import typer

app = typer.Typer(help="Manage profiles")

@app.command("list")
def list_profiles():
    typer.echo("safe-dev\nmodel-local\nresearch-persistent\nred-zone")
```

```python
# labos/cli/main.py
import typer
from labos.cli.labs import app as labs_app
from labos.cli.profiles import app as profiles_app

app = typer.Typer(help="LabOS operator CLI")
app.add_typer(labs_app, name="labs")
app.add_typer(profiles_app, name="profiles")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/cli/test_cli_help.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add labos/cli/main.py labos/cli/labs.py labos/cli/profiles.py tests/cli/test_cli_help.py
git commit -m "feat: add operator cli command groups"
```

### Task 10: Add microVM adapter boundary and repo-integration notes

**Files:**
- Create: `labos/runtimes/microvm_runtime.py`
- Modify: `docs/repo-sources.md`
- Create: `docs/runtime-decisions.md`
- Create: `tests/runtimes/test_microvm_runtime.py`

- [ ] **Step 1: Write failing microVM adapter tests**

```python
# tests/runtimes/test_microvm_runtime.py
from labos.runtimes.microvm_runtime import MicroVMRuntime


def test_microvm_runtime_reports_backend_name():
    runtime = MicroVMRuntime()
    assert runtime.backend_name() == "microvm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtimes/test_microvm_runtime.py -v`
Expected: FAIL because adapter does not exist

- [ ] **Step 3: Add adapter stub and decision doc**

```python
# labos/runtimes/microvm_runtime.py
class MicroVMRuntime:
    def backend_name(self) -> str:
        return "microvm"

    def create_lab(self, lab_id: str, spec):
        raise NotImplementedError("Phase 1 defines the contract; backend implementation follows after control plane stabilization")

    def destroy_lab(self, lab_id: str):
        raise NotImplementedError

    def exec_run(self, lab_id: str, command: str):
        raise NotImplementedError
```

```markdown
# docs/runtime-decisions.md
# Runtime Decisions

## Phase 1 direct runtime
- Docker-backed container labs are the first production path.

## Phase 1 microVM stance
- define the runtime interface now
- keep `red-zone` policy bound to `microvm`
- implement real backend after control plane/API/policy model is proven

## Reference repos reviewed
- kubernetes-sigs/agent-sandbox
- abshkbh/arrakis
- trycua/cua

## Decision
No full fork. LabOS remains the control plane and contracts layer.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtimes/test_microvm_runtime.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add labos/runtimes/microvm_runtime.py docs/runtime-decisions.md docs/repo-sources.md tests/runtimes/test_microvm_runtime.py
git commit -m "docs: lock runtime integration strategy and microvm contract"
```

### Task 11: Add scheduler/approval/export workflow endpoints

**Files:**
- Create: `labos/core/approval_service.py`
- Create: `labos/workers/scheduler.py`
- Create: `labos/api/routes_approvals.py`
- Create: `labos/api/routes_exports.py`
- Create: `tests/api/test_approvals_api.py`

- [ ] **Step 1: Write failing approval/export tests**

```python
# tests/api/test_approvals_api.py
from fastapi.testclient import TestClient
from labos.api.app import app


def test_approvals_endpoint_exists():
    client = TestClient(app)
    response = client.get("/approvals")
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_approvals_api.py -v`
Expected: FAIL because routes do not exist

- [ ] **Step 3: Add minimal workflow surfaces**

```python
# labos/core/approval_service.py
class ApprovalService:
    def list_pending(self):
        return []
```

```python
# labos/api/routes_approvals.py
from fastapi import APIRouter
from labos.core.approval_service import ApprovalService

router = APIRouter()
service = ApprovalService()

@router.get("/approvals")
def list_approvals():
    return service.list_pending()
```

```python
# labos/workers/scheduler.py
class Scheduler:
    def enqueue_lab_start(self, lab_id: str, when_iso: str) -> dict:
        return {"lab_id": lab_id, "scheduled_for": when_iso}
```

- [ ] **Step 4: Include routes and run tests**

Run: `pytest tests/api/test_approvals_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add labos/core/approval_service.py labos/workers/scheduler.py labos/api/routes_approvals.py tests/api/test_approvals_api.py
 git commit -m "feat: add approval workflow and scheduler stubs"
```

### Task 12: End-to-end docs, examples, and verification

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/threat-model.md`
- Create: `docs/api.md`
- Create: `docs/cli.md`
- Create: `tests/integration/test_profile_examples.py`

- [ ] **Step 1: Write the failing docs/profile example test**

```python
# tests/integration/test_profile_examples.py
from pathlib import Path


def test_all_expected_profile_examples_exist():
    expected = [
        "safe-dev.yaml",
        "model-local.yaml",
        "research-persistent.yaml",
        "red-zone.yaml",
    ]
    base = Path("examples/profiles")
    for filename in expected:
        assert (base / filename).exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_profile_examples.py -v`
Expected: FAIL if any examples/docs are missing

- [ ] **Step 3: Write final operator-facing docs**

```markdown
# README.md
# LabOS

LabOS is a policy-first research containment platform for risky agent and code experiments.

## Phase 1 capabilities
- create labs from policy profiles
- run container-backed labs
- define microVM-backed red-zone contracts
- keep audit/event history
- control exports through quarantine rules
- operate through API + CLI
```

```markdown
# docs/cli.md
# CLI

## Planned commands
- `labos profiles list`
- `labos labs list`
- `labos labs create --profile safe-dev`
- `labos runs exec <lab-id> -- python main.py`
- `labos exports request <lab-id> /lab/exports/report.json`
```

- [ ] **Step 4: Run focused verification suite**

Run: `pytest tests/test_imports.py tests/core tests/db tests/runtimes tests/api tests/cli tests/integration -v`
Expected: PASS

- [ ] **Step 5: Run static checks**

Run: `ruff check labos tests && python -m compileall labos`
Expected: PASS with no syntax errors

- [ ] **Step 6: Commit**

```bash
git add README.md docs tests examples
 git commit -m "docs: finalize phase one operator docs and examples"
```

## Functionalities to Add in Phase 1
- declarative lab profiles
- container runtime path
- microVM runtime contract path
- request/approval flow
- lab lifecycle state machine
- run lifecycle state machine
- audit events
- snapshot service stub
- export gate
- profile examples
- API + CLI operator interfaces
- scheduler hook
- strong docs/threat model

## Functionalities Explicitly Deferred to Phase 2+
- real Firecracker backend implementation
- web dashboard
- identity-broker / comms-broker
- GPU scheduling beyond simple profile flags
- benchmark suite integration from CUA-style environments
- private experiment repo automation
- chat-native command bridge into the control plane
- policy escalation UX beyond basic approvals

## Recommended Execution Order After Plan Approval
1. Create fresh repo `labos`
2. Implement Tasks 1–4 to stabilize domain + policy + DB
3. Implement Tasks 5–9 to get a usable container-backed control plane
4. Implement Tasks 10–12 to lock the microVM path and operator docs
5. Only then start Phase 2 work on real microVM backend and Telegram/agent bridge

## Plan Self-Review
- **Spec coverage:** covers isolation, network, persistence, creators, API+CLI, policy profiles, lifecycle, export gate, hybrid runtime, public/private repo split
- **Placeholders:** no `TODO`/`TBD` placeholders left in execution tasks
- **Type consistency:** runtime classes are `container` and `microvm` everywhere; core profile names are consistent

## Final Recommendation
Build a **new LabOS repo** and reuse existing foundations rather than forking a full competitor. Use:
- direct implementation: Docker runtime + FastAPI + Postgres + Typer
- reference patterns: `kubernetes-sigs/agent-sandbox`, `abshkbh/arrakis`, `trycua/cua`
- market/comparison map: `arjan/awesome-agent-sandboxes`
