# LabOS End-to-End Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this roadmap task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build LabOS from idea to production-ready open-source core: a policy-first research containment platform for risky agent, code, and model experiments, with safe default isolation, governed export, observable runs, and a clean path for high-risk labs.

**Architecture:** LabOS is a new control-plane product with strict policy and lifecycle governance. Phase 1 ships Docker-backed labs and a microVM-ready contract. Later phases harden the system, add Firecracker-class high-risk execution, and then support private workload packs such as local model labs, trading research labs, and agent evolution labs.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy, Alembic, PostgreSQL, Docker Engine/SDK, Typer CLI, pytest, httpx, uv, optional Firecracker integration in later phase.

---

## 1) Final Product Vision

### What LabOS is
- A governed office of labs.
- Every lab is isolated.
- Every lab is created from policy, not from ad hoc shell decisions.
- Every dangerous capability is explicit.
- Every export is traceable.
- Every long experiment can be observed, paused, resumed, snapshotted, archived, or destroyed.

### What makes it worth building
- Prevents host contamination from risky experiments.
- Gives you repeatable research environments instead of one-off hacks.
- Lets agents work inside controlled blast radiuses.
- Separates public core infrastructure from private strategies and datasets.
- Becomes the execution substrate for future labs: local models, trading research, agent self-improvement.

### What LabOS is not
- Not a generic Docker launcher.
- Not a bare VM manager.
- Not a web-dashboard-first toy.
- Not a trading bot product in Phase 1.
- Not a self-evolving meta-agent product in Phase 1.

---

## 2) Hard Product Boundaries

### Public core repo
Public repo: `Dev-31/labos`

Contains:
- control plane
- policy model
- lifecycle model
- runtime adapters
- export gate
- snapshot logic
- audit/event model
- CLI/API
- docs/tests/examples

### Private companion repos later
Contain:
- private lab profiles
- datasets
- credentials brokers
- trading experiments
- local model experiment packs
- agent evolution recipes

### Phase ordering rule
Do not build consumer workloads before the platform can:
- create isolated labs
- enforce policy
- run jobs
- quarantine exports
- log events
- recover from failure

---

## 3) Non-Negotiable Design Rules

- [ ] No host env inheritance by default.
- [ ] No home directory mount by default.
- [ ] No Docker socket passthrough.
- [ ] No direct host writes from labs.
- [ ] No unrestricted network without explicit policy.
- [ ] No export without provenance.
- [ ] No dangerous lab profile without approval rules.
- [ ] No scheduler-created lab that bypasses quota or policy.
- [ ] No agent/operator action outside control-plane APIs.
- [ ] No “temporary shortcut” that becomes permanent attack surface.

---

## 4) Success Criteria From Start to End

LabOS is only “real” when all of this is true:

### Minimum useful state
- [ ] A lab can be created from a named profile.
- [ ] The profile fully determines runtime, network, persistence, resources, exports, and approval behavior.
- [ ] A run can execute code inside the lab.
- [ ] Logs and run status can be retrieved.
- [ ] The lab can be snapshotted or archived.
- [ ] Artifacts cannot leave the lab except through export workflow.

### Minimum safe state
- [ ] Unsafe defaults are impossible from normal APIs.
- [ ] Secret injection is named, scoped, and time-bound.
- [ ] Every policy decision is auditable.
- [ ] Failed labs do not silently linger forever.
- [ ] Destruction reliably removes runtime artifacts and detaches storage.

### Minimum production-ready state
- [ ] CLI and API both work.
- [ ] Test suite covers domain, policy, API, runtime, and export rules.
- [ ] Docs tell a stranger exactly how to run and extend it.
- [ ] Threat model and security policy are explicit.
- [ ] Public repo is structured cleanly enough for outside contributors.

---

## 5) Final Architecture Target

### Core planes
1. **Control Plane**
   - API
   - lifecycle orchestration
   - policy evaluation
   - approvals
   - quotas
   - scheduler entrypoints
   - event recording

2. **Execution Plane**
   - runtime adapters
   - lab provision/teardown
   - job execution
   - health supervision
   - resource enforcement

3. **Storage Plane**
   - metadata DB
   - managed lab volumes
   - snapshots
   - logs
   - artifact quarantine store

4. **Security Plane**
   - network controls
   - secret injection rules
   - mount rules
   - export gate
   - risk-class mapping

5. **Operator Plane**
   - CLI
   - API consumers
   - agent/chat bridge later

### Runtime target
- Default runtime: Docker-backed containers.
- High-risk runtime: Firecracker-class microVM adapter.
- Strict interface so later runtimes do not leak complexity into core domain.

---

## 6) Ordered Build Roadmap

This is the full sequence. Do not skip ahead unless the current gate is complete.

---

## Phase 0 — Product freeze and repo hygiene

### Objective
Lock the product shape before code sprawl starts.

### Exit gate
You have one repo, one product definition, one sequence, and zero ambiguity about Phase 1.

### Steps
- [ ] Confirm repo name is `labos`.
- [ ] Keep repo public.
- [ ] Keep private workloads out of public core.
- [ ] Freeze Phase 1 scope: API, CLI, policy, Docker runtime, snapshots, exports, approvals, audit, scheduler hooks.
- [ ] Freeze Phase 1 non-scope: web UI, full Firecracker production backend, trading engine, agent evolution engine, enterprise RBAC.
- [ ] Save design spec into repo docs.
- [ ] Save implementation plan into repo docs.
- [ ] Save this roadmap into repo root as `ROADMAP.md`.
- [ ] Add top-level README statement explaining what LabOS is and is not.
- [ ] Add explicit “public core + private experiments” rule to README.

---

## Phase 1 — Repo scaffolding and development baseline

### Objective
Create a clean repo skeleton, local dev workflow, and test baseline.

### Exit gate
A fresh contributor can clone, install, run tests, and start the API locally.

### Steps
- [ ] Create Python package layout.
- [ ] Create `pyproject.toml`.
- [ ] Add runtime dependencies.
- [ ] Add dev/test dependencies.
- [ ] Add package entrypoint.
- [ ] Create `Makefile` or task runner commands.
- [ ] Add `.env.example`.
- [ ] Add `docker-compose.yml` for local Postgres.
- [ ] Add package folders: `api`, `core`, `db`, `runtimes`, `security`, `storage`, `workers`, `cli`, `config`.
- [ ] Add tests folders: `api`, `core`, `runtimes`, `security`, `integration`, `cli`.
- [ ] Add import smoke test.
- [ ] Make import smoke test fail first.
- [ ] Add minimum code to satisfy imports.
- [ ] Run tests until green.
- [ ] Add Ruff config.
- [ ] Add mypy config.
- [ ] Add pytest config.
- [ ] Add CI workflow placeholder.
- [ ] Commit scaffold.

---

## Phase 2 — Domain model and lifecycle state machine

### Objective
Define the vocabulary so the rest of the system doesn’t rot.

### Exit gate
Every main entity and state transition is explicit and test-covered.

### Entities to define
- Profile
- Lab
- Run
- ApprovalRequest
- Snapshot
- ExportRequest
- AuditEvent
- SecretLease
- SchedulerJob

### Steps
- [ ] Define lab states.
- [ ] Define run states.
- [ ] Define approval states.
- [ ] Define export states.
- [ ] Define snapshot states.
- [ ] Write tests for valid and invalid lab transitions.
- [ ] Write tests for valid and invalid run transitions.
- [ ] Implement transition maps.
- [ ] Implement helper functions: `can_transition_*`.
- [ ] Define base entity timestamps and IDs.
- [ ] Define Pydantic/ORM-facing entity schemas.
- [ ] Add validation rules for immutable fields after creation.
- [ ] Add tests for invalid state mutation attempts.
- [ ] Commit domain model.

---

## Phase 3 — Policy system first, before runtime power

### Objective
Make policy the center of the product instead of runtime options.

### Exit gate
A profile can be evaluated into an enforceable execution plan.

### Policy areas
- runtime class
- network mode
- filesystem mode
- persistence mode
- CPU/RAM/disk limits
- execution permissions
- secret rules
- export rules
- approval rules
- audit level
- retention policy

### Required profile set
- `safe-dev`
- `model-local`
- `research-persistent`
- `red-zone`

### Steps
- [ ] Define profile schema.
- [ ] Define allowed enum values for policy dimensions.
- [ ] Write tests for profile validation.
- [ ] Write tests for invalid combinations.
- [ ] Encode combination rules.
- [ ] Define risk classes: low, medium, high, critical.
- [ ] Map profiles to risk classes.
- [ ] Define approval triggers from risk class and requested actions.
- [ ] Implement policy evaluation result object.
- [ ] Implement rule: host mounts forbidden unless explicitly allowed.
- [ ] Implement rule: default secret set is empty.
- [ ] Implement rule: network must be explicit.
- [ ] Implement rule: export policy is deny-until-reviewed for high risk.
- [ ] Add tests for each non-negotiable rule.
- [ ] Commit policy engine.

---

## Phase 4 — Database and persistence backbone

### Objective
Make runtime state durable and queryable.

### Exit gate
Labs, runs, approvals, exports, snapshots, and events survive process restarts.

### Steps
- [ ] Choose SQLAlchemy model style and lock it.
- [ ] Create DB connection settings.
- [ ] Add Alembic.
- [ ] Create initial migration.
- [ ] Add labs table.
- [ ] Add profiles table or profile registry storage decision.
- [ ] Add runs table.
- [ ] Add approval requests table.
- [ ] Add snapshots table.
- [ ] Add export requests table.
- [ ] Add audit events table.
- [ ] Add secret leases table.
- [ ] Add scheduler jobs table.
- [ ] Add indexes for lab status lookups.
- [ ] Add indexes for run status lookups.
- [ ] Add indexes for event timelines.
- [ ] Write repository/store layer tests.
- [ ] Write migration smoke test.
- [ ] Commit DB layer.

---

## Phase 5 — API skeleton and health surface

### Objective
Expose a stable control-plane contract early.

### Exit gate
API boots locally and supports basic health and object CRUD.

### First API groups
- `/health`
- `/profiles`
- `/labs`
- `/runs`
- `/approvals`
- `/snapshots`
- `/exports`
- `/events`

### Steps
- [x] Create FastAPI app factory.
- [x] Add settings loader.
- [x] Add health endpoint.
- [x] Add health test.
- [x] Add profiles list endpoint.
- [x] Add profiles get endpoint.
- [x] Add lab create endpoint schema.
- [x] Add lab list endpoint.
- [x] Add lab get endpoint.
- [x] Add run create endpoint schema.
- [x] Add run list endpoint.
- [x] Add approval list endpoint.
- [x] Add snapshot list endpoint.
- [x] Add export list endpoint.
- [x] Add event list endpoint.
- [x] Add request/response models.
- [x] Add 404 handling.
- [x] Add validation error shaping.
- [x] Add API tests.
- [x] Commit API skeleton.

---

## Phase 6 — Docker runtime adapter

### Objective
Make LabOS actually run work inside isolated container labs.

### Exit gate
A lab can be provisioned, executed in, inspected, and destroyed through the adapter.

### Adapter responsibilities
- create lab
- start lab
- stop lab
- destroy lab
- run command/job
- stream logs
- inspect status
- attach managed storage
- enforce resource limits

### Steps
- [x] Define `RuntimeAdapter` interface.
- [x] Define runtime request object.
- [x] Define runtime result object.
- [x] Write adapter contract tests.
- [x] Implement Docker client wrapper.
- [x] Implement container naming convention.
- [x] Implement managed network naming convention.
- [x] Implement managed volume naming convention.
- [x] Implement container create path.
- [x] Apply CPU limits.
- [x] Apply memory limits.
- [x] Apply storage mounts.
- [x] Apply env injection only from approved secret leases.
- [x] Apply network restrictions from policy.
- [x] Add label set for traceability.
- [x] Implement start path.
- [x] Implement stop path.
- [x] Implement destroy path.
- [x] Implement run execution path.
- [x] Implement log retrieval path.
- [x] Implement inspect path.
- [x] Implement runtime cleanup on failure path.
- [ ] Add integration test against local Docker.
- [x] Commit Docker adapter.

---

## Phase 7 — Storage model and managed lab filesystem

### Objective
Ensure lab writes stay inside governed storage.

### Exit gate
Labs write only to managed areas, and persistence behavior follows policy.

### Storage modes
- ephemeral
- persistent
- snapshot-capable ephemeral
- snapshot-capable persistent

### Steps
- [x] Define storage policy schema.
- [x] Define managed path conventions.
- [x] Separate metadata from runtime payload storage.
- [x] Implement lab workspace allocator.
- [x] Implement ephemeral cleanup rules.
- [x] Implement persistent retention rules.
- [x] Write tests for forbidden host path mounts.
- [x] Write tests for cleanup behavior.
- [x] Add storage metadata recording.
- [x] Commit storage layer.

---

## Phase 8 — Snapshot model

### Objective
Make labs recoverable and inspectable over long experiments.

### Exit gate
A lab or its managed state can be snapshotted and restored according to policy.

### Phase 1 snapshot stance
- For containers, start with managed volume + metadata snapshots.
- Do not fake full VM-grade time-travel if it does not exist yet.

### Steps
- [x] Define snapshot request model.
- [x] Define snapshot metadata schema.
- [x] Define snapshot storage location.
- [x] Write tests for snapshot creation flow.
- [x] Implement snapshot capture for supported storage mode.
- [x] Record provenance: lab, run, profile, timestamp, hashes.
- [x] Implement snapshot list API.
- [x] Implement snapshot restore request validation.
- [x] Implement restore path for supported snapshot type.
- [x] Add failure handling for unsupported runtime/snapshot combo.
- [x] Commit snapshot module.

---

## Phase 9 — Export quarantine and decontamination gate

### Objective
Prevent unsafe artifacts from leaking straight to host or users.

### Exit gate
Exports are staged, hashed, reviewed by policy, and only then released.

### Export workflow
1. lab requests export
2. artifact copied to quarantine
3. metadata and hashes recorded
4. policy evaluated
5. approval requested if needed
6. release or deny

### Steps
- [x] Define export request model.
- [x] Define quarantine path structure.
- [x] Define artifact hash model.
- [x] Define provenance record model.
- [x] Write tests for export request creation.
- [x] Write tests for high-risk export requiring approval.
- [x] Implement export staging copy.
- [x] Compute hashes.
- [x] Store file metadata.
- [x] Bind export to lab/run identity.
- [x] Evaluate export policy.
- [x] Block direct release on forbidden profiles.
- [x] Add release endpoint/service.
- [x] Add denial endpoint/service.
- [x] Add event logging for every export stage.
- [x] Commit export gate.

---

## Phase 10 — Approval workflow

### Objective
Make dangerous actions explicit and reviewable.

### Exit gate
High-risk lab creation and export actions can be blocked pending approval.

### Approval-triggered actions
- high-risk profile lab creation
- elevated network access request
- dangerous mount request
- high-risk export release
- long-lived persistent red-zone lab creation

### Steps
- [x] Define approval request schema.
- [x] Define approval decision schema.
- [x] Write tests for actions that should auto-approve.
- [x] Write tests for actions that should require approval.
- [x] Implement approval record creation.
- [x] Implement pending state handling.
- [x] Implement approve action.
- [x] Implement deny action.
- [x] Implement request expiry.
- [x] Implement event generation on decisions.
- [x] Add API endpoints.
- [x] Add CLI commands.
- [x] Commit approvals module.

---

## Phase 11 — Audit and event stream

### Objective
Make the system explain itself.

### Exit gate
Important actions can be reconstructed after the fact.

### Events to capture
- lab requested
- lab approved/denied
- lab provisioned
- lab started/stopped/destroyed
- run queued/started/completed/failed
- snapshot created/restored
- export staged/released/denied
- secret lease issued/revoked
- policy denied

### Steps
- [ ] Define event schema.
- [ ] Define actor model: human, agent, scheduler, system.
- [ ] Define resource reference shape.
- [ ] Implement event writer service.
- [ ] Ensure major workflows emit events.
- [ ] Add event query filters.
- [ ] Add API list endpoint with filters.
- [ ] Add tests for event generation.
- [ ] Commit audit layer.

---

## Phase 12 — Secret brokering and scoped injection

### Objective
Prevent lazy credential sprawl.

### Exit gate
Secrets are explicitly requested, leased, injected, and revoked.

### Phase 1 stance
- Start simple.
- Do not build a whole vault product.
- Build a broker interface and minimal local/provider-backed implementation.

### Steps
- [ ] Define secret request schema.
- [ ] Define secret lease schema.
- [ ] Define lease expiry rules.
- [ ] Write tests for empty-by-default secret injection.
- [ ] Write tests for denied broad env passthrough.
- [ ] Implement broker interface.
- [ ] Implement minimal secret resolver.
- [ ] Implement lease recording.
- [ ] Implement runtime injection from lease only.
- [ ] Implement lease revocation path.
- [ ] Add audit events.
- [ ] Commit secret broker.

---

## Phase 13 — CLI operator surface

### Objective
Make LabOS operable without raw API fiddling.

### Exit gate
An operator can create, inspect, run, snapshot, export, approve, and destroy from the CLI.

### CLI command groups
- `labos profiles`
- `labos labs`
- `labos runs`
- `labos snapshots`
- `labos exports`
- `labos approvals`
- `labos events`

### Steps
- [ ] Create root CLI app.
- [ ] Add API client helper.
- [ ] Add `profiles list`.
- [ ] Add `labs create`.
- [ ] Add `labs list`.
- [ ] Add `labs get`.
- [ ] Add `labs destroy`.
- [ ] Add `runs start`.
- [ ] Add `runs list`.
- [ ] Add `snapshots create`.
- [ ] Add `snapshots list`.
- [ ] Add `exports request`.
- [ ] Add `approvals list`.
- [ ] Add `approvals approve`.
- [ ] Add `approvals deny`.
- [ ] Add `events list`.
- [ ] Add CLI tests.
- [ ] Commit CLI.

---

## Phase 14 — Scheduler hooks and long-running research support

### Objective
Support repeatable automated experiments without giving schedulers raw runtime power.

### Exit gate
Scheduled jobs can request labs and runs through the same control plane.

### Phase 1 stance
- scheduler hooks first
- full distributed orchestration later

### Steps
- [ ] Define scheduler job schema.
- [ ] Define allowed scheduler action set.
- [ ] Write tests for scheduler-created lab policy enforcement.
- [ ] Implement scheduler job storage.
- [ ] Implement enqueue path.
- [ ] Implement worker loop stub.
- [ ] Implement dispatch through same lab creation service.
- [ ] Implement quota checks.
- [ ] Implement retry policy.
- [ ] Implement event logging.
- [ ] Commit scheduler hooks.

---

## Phase 15 — Reliability, cleanup, and failure recovery

### Objective
Make the platform recover from reality instead of only happy paths.

### Exit gate
LabOS can detect and clean broken runtime state.

### Steps
- [ ] Write tests for runtime create failure cleanup.
- [ ] Write tests for half-created lab reconciliation.
- [ ] Write tests for orphaned container detection.
- [ ] Implement reconciliation job.
- [ ] Implement stale pending approval cleanup.
- [ ] Implement stale secret lease cleanup.
- [ ] Implement timed-out run handling.
- [ ] Implement zombie lab detection.
- [ ] Implement destroy retry logic.
- [ ] Add failure events.
- [ ] Commit resilience layer.

---

## Phase 16 — Security hardening and threat-model verification

### Objective
Prove the product acts like a containment platform, not just claims it.

### Exit gate
Threat model has concrete verification coverage.

### Steps
- [ ] Turn threat-model bullets into test cases.
- [ ] Verify blocked home mount paths.
- [ ] Verify denied Docker socket mount.
- [ ] Verify empty default secret injection.
- [ ] Verify network deny behavior.
- [ ] Verify export quarantine cannot be bypassed from public APIs.
- [ ] Verify actor/audit trail for dangerous actions.
- [ ] Add SECURITY.md.
- [ ] Add disclosure/contact policy.
- [ ] Commit security pass.

---

## Phase 17 — Documentation and contributor surface

### Objective
Make the repo understandable to outsiders.

### Exit gate
A serious engineer can understand and extend LabOS without talking to us first.

### Required docs
- README
- architecture
- threat model
- policies
- lab profiles
- API guide
- CLI guide
- repo sources/references
- contributing
- roadmap

### Steps
- [ ] Rewrite README to match actual implementation.
- [ ] Add quickstart.
- [ ] Add local dev setup.
- [ ] Add architecture diagram or text map.
- [ ] Document each profile.
- [ ] Document runtime support matrix.
- [ ] Document export workflow.
- [ ] Document approval workflow.
- [ ] Document storage model.
- [ ] Document public-core/private-workload split.
- [ ] Add CONTRIBUTING.md.
- [ ] Commit docs.

---

## Phase 18 — First public release prep

### Objective
Make the repo releaseable, not just code-complete.

### Exit gate
You can tag `v0.1.0` without embarrassment.

### Steps
- [ ] Clean open issues in code comments.
- [ ] Run full test suite.
- [ ] Run lint.
- [ ] Run type checks.
- [ ] Test install from clean machine/container.
- [ ] Test local Docker integration from scratch.
- [ ] Validate docs commands actually work.
- [ ] Add release checklist.
- [ ] Add changelog or release notes.
- [ ] Tag first release.

---

## Phase 19 — High-risk runtime phase (Firecracker-class)

### Objective
Graduate from microVM-ready architecture to real high-risk isolation.

### Exit gate
A high-risk lab profile runs on a microVM backend through the same control plane contract.

### Important rule
Do not start this until the control plane, policy model, audit model, and export gate are already stable.

### Steps
- [ ] Reconfirm runtime adapter contract is sufficient.
- [ ] Define microVM-specific config schema.
- [ ] Define boot image strategy.
- [ ] Define storage attach strategy.
- [ ] Define network strategy for deny-by-default microVMs.
- [ ] Write adapter contract tests for microVM runtime.
- [ ] Implement backend wrapper.
- [ ] Implement create/start/stop/destroy paths.
- [ ] Implement log/serial capture path.
- [ ] Implement snapshot semantics honestly.
- [ ] Add high-risk profile mapping.
- [ ] Add integration tests.
- [ ] Commit microVM runtime.

---

## Phase 20 — Agent/chat operator bridge

### Objective
Let this agent operate LabOS through the same safe interface humans use.

### Exit gate
Chat control exists as an API/CLI client, not as a backdoor.

### Steps
- [ ] Define operator action mapping.
- [ ] Define allowed chat commands.
- [ ] Define confirmation requirements for dangerous actions.
- [ ] Implement API client wrapper suitable for agent use.
- [ ] Implement structured output formats for status/approvals/exports.
- [ ] Add audit actor type for chat/agent.
- [ ] Add tests for policy parity between CLI/API/chat clients.
- [ ] Commit operator bridge.

---

## Phase 21 — Private workload packs after core is stable

### Objective
Use LabOS as the substrate for your real labs.

### Do not open this phase until LabOS core is stable.

### Pack A: Local model lab
Use cases:
- llama.cpp experiments
- quantization tests
- prompt/runtime benchmarks
- model memory/runtime tuning

Steps:
- [ ] Create private profile pack for model labs.
- [ ] Define GPU/CPU support assumptions.
- [ ] Define persistent model-cache rules.
- [ ] Define allowed local model artifact export paths.
- [ ] Add benchmark templates.

### Pack B: Trading research lab
Use cases:
- 3-month continuous backtesting
- forward testing
- market simulation
- strategy scoring
- recommendation generation later

Steps:
- [ ] Create private research profile.
- [ ] Define long-run persistence and retention.
- [ ] Define dataset ingestion workflow.
- [ ] Define checkpointing cadence.
- [ ] Define run health and recovery policy.
- [ ] Define artifact/report export format.
- [ ] Add simulation-only enforcement until explicitly changed.

### Pack C: Agent evolution / meta-agent lab
Use cases:
- benchmark agents safely
- compare prompts/policies/tools
- evaluate self-improvement hypotheses

Steps:
- [ ] Create private agent-eval profile.
- [ ] Define benchmark datasets.
- [ ] Define scoring schema.
- [ ] Define approval rules for self-modification experiments.
- [ ] Define artifact isolation for generated code and traces.

---

## 7) What we must refuse to do early

- [ ] Do not bolt on a dashboard first.
- [ ] Do not overbuild Kubernetes support.
- [ ] Do not ship fake microVM support.
- [ ] Do not mix private trading code into public core.
- [ ] Do not let agent convenience break policy boundaries.
- [ ] Do not claim snapshot guarantees that container storage cannot really provide.
- [ ] Do not leak host credentials into labs to “make things easier.”

---

## 8) Immediate execution order from here

These are the next concrete moves from today.

### Step block A — Repo content push
- [ ] Copy design spec into `labos/docs/`.
- [ ] Copy implementation plan into `labos/docs/`.
- [ ] Copy this roadmap into `labos/ROADMAP.md`.
- [ ] Add a short bootstrap README.
- [ ] Commit and push.

### Step block B — Start build
- [ ] Scaffold package and tests.
- [ ] Implement domain model.
- [ ] Implement policy engine.
- [ ] Implement DB layer.
- [ ] Implement API skeleton.
- [ ] Implement Docker runtime.
- [ ] Implement export gate.
- [ ] Implement approvals.
- [ ] Implement CLI.
- [ ] Implement scheduler hooks.
- [ ] Harden.
- [ ] Release.

---

## 9) Definition of Done for LabOS v0.1

`v0.1` is done only when:
- [ ] public repo exists and is structured cleanly
- [ ] docs explain product and boundaries
- [ ] profile-driven lab creation works
- [ ] Docker-backed labs run safely
- [ ] logs/status/events work
- [ ] snapshots work for supported storage mode
- [ ] export quarantine works
- [ ] approvals work
- [ ] CLI works
- [ ] tests are green
- [ ] security rules are verified
- [ ] no fake claims remain in docs

---

## 10) Honest judgment

Your instinct is right, but the dangerous failure mode is obvious: if we rush to build “special labs” before the containment substrate is strict, we will just recreate the same contamination problem with nicer branding.

So the roadmap is intentionally brutal:
- core containment first
- risky runtime second
- real workload packs third

That is the only sequence that makes sense.
