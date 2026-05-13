# LabOS Design Spec

## Goal
Build a policy-first research containment platform for risky agent and code experiments. The system should let humans, approved agents, and schedulers create isolated labs on demand, run experiments inside them, observe what happened, snapshot state, export artifacts through a controlled gate, and destroy or archive labs without contaminating the host.

## Product Thesis
This is not a generic sandbox launcher. The product is a **governed lab office**:
- the **office** is the host platform
- each **lab** is an isolated execution environment
- artifacts leave only through a **decontamination / export gate**
- risky actions are controlled by **policy and approval**, not ad hoc shell access

## Scope
### Phase 1 in scope
- API + CLI control plane
- policy profiles as the main user abstraction
- container labs by default
- microVM labs for high-risk profiles
- tiered network policy
- tiered persistence policy
- audit/event model
- snapshots
- export gate
- scheduler support
- agent/chat operability via controller interfaces

### Phase 1 out of scope
- full web dashboard
- Kubernetes deployment complexity as the main path
- built-in trading logic
- built-in meta-agent training system
- multi-region clustering
- enterprise RBAC complexity
- plugin marketplace

## Architecture Decisions
### 1. Isolation model
**Decision:** Hybrid.
- containers by default
- microVMs for high-risk labs

Rationale:
- container-only is too weak for the intended high-risk use cases
- microVM-only would slow down normal operator workflows
- hybrid gives practical speed with serious containment when needed

### 2. Network model
**Decision:** Tiered and modifiable by policy.
- container labs: restricted egress by default
- microVM labs: deny by default
- per-lab/profile overrides allowed only through policy controls

### 3. Persistence model
**Decision:** Tiered.
- short-lived labs: ephemeral by default
- research/training labs: persistent by policy
- snapshots supported for both

### 4. Creators / operators
**Decision:** Humans, approved agents, and scheduler jobs can create labs.
- all requests go through a controller API
- risky profiles/actions require approval
- agents do not get raw infrastructure power

### 5. Interface model
**Decision:** API + CLI first.
- API is the control plane contract
- CLI is the serious operator interface
- chat/agent control should go through the API/CLI bridge
- dashboard can come later

## Core System Model
### Control Plane
Owns:
- API server
- policy engine
- approval engine
- scheduler
- quotas
- lab/run state transitions
- audit/event stream

### Execution Plane
Owns:
- runtime adapters
- lab provisioning and teardown
- run execution supervision
- resource limit application

### Storage Plane
Owns:
- persistent lab volumes
- snapshots
- artifact store
- logs
- metadata

### Security Plane
Owns:
- network policy
- mount policy
- secrets policy
- export quarantine / release flow

### Operator Plane
Owns:
- CLI
- API consumers (agents/chat/scheduler)
- later dashboard

## Repo Strategy
### Public repo
A clean open-source core platform.
Working name:
- `labos` (preferred if available)
- fallback: `agent-lab-core`

### Private repo
Contains:
- private experiments
- private profiles
- strategies
- datasets
- sensitive runbooks
- future trading / agent-evolution workloads

## Phase 1 Code Structure
```text
labos/
  README.md
  LICENSE
  ROADMAP.md
  SECURITY.md
  CONTRIBUTING.md

  docs/
    architecture.md
    threat-model.md
    policies.md
    lab-profiles.md
    api.md
    cli.md

  labos/
    api/
    core/
    runtimes/
    storage/
    security/
    workers/
    cli/
    db/
    config/

  tests/
    api/
    core/
    runtimes/
    security/
    cli/
    integration/

  deploy/
  examples/
```

## Policy Model
Every lab is created from a declarative **profile**.

A profile defines:
- runtime class
- network mode
- filesystem mode
- host access rules
- resource limits
- execution permissions
- secrets policy
- export policy
- approval policy
- audit level

### Example profile set
- `safe-dev`
- `model-local`
- `research-persistent`
- `red-zone`

## Non-Negotiable Safety Rules
1. **No host inheritance by default**
   - no automatic env inheritance
   - no SSH keys
   - no broad credentials
   - no Docker socket
   - no home directory mounts

2. **No direct host writes**
   - lab writes stay inside managed lab storage
   - export is a separate action

3. **Network must be explicit**
   - denied or allowlisted by policy
   - logged when used

4. **Secrets must be scoped and time-bound**
   - inject only named secrets
   - no full host env pass-through

5. **Exports go through quarantine**
   - hash
   - provenance
   - approval if required
   - release only after policy checks

6. **Risk escalation is policy-based**
   - no silent mutation from low-risk to high-risk behavior

## Lifecycle Model
A lab moves through:
**Profile -> Request -> Approval -> Provision -> Run -> Observe -> Snapshot/Export -> Destroy/Archive**

### Lab states
- requested
- pending_approval
- approved
- provisioning
- running
- stopped
- failed
- destroying
- destroyed
- archived

### Run states
- queued
- starting
- running
- completed
- failed
- cancelled
- timed_out

## Chat / Agent Control Model
The user should be able to control labs from chat, but chat is an **operator surface**, not a raw shell bypass.

Chat/agents may:
- request labs
- start/stop labs
- inspect status/logs
- request exports
- approve or escalate defined actions

Chat/agents may not:
- bypass controller policy
- directly mutate runtime internals outside allowed APIs

## Identity Model (Future Extension)
Future labs may use compartmentalized operational identities:
- dedicated email aliases
- dedicated secondary phone numbers
- brokered assignment to labs
- revocation and audit trail

This should be handled by an `identity-broker` / `comms-broker`, not by giving labs raw personal credentials.

## External Landscape Conclusion
The category is not unique. Existing overlap includes:
- secure agent sandboxes
- code execution sandboxes
- microVM runtimes
- persistent sandbox management
- benchmark/evaluation environments

Therefore the differentiation must come from:
- policy-first design
- governed lifecycle
- export quarantine
- persistent + ephemeral lab model
- agent/chat control plane
- hybrid runtime strategy

## Build-vs-Buy Decision
**Approved direction:** build the control plane yourself, but reuse existing runtime foundations.

Meaning:
- do not build the full sandbox stack from zero
- do not blindly fork one competitor and live inside its worldview
- do build your own product around governance, policy, lifecycle, and operator UX

## Repository / Runtime Shortlist
### Direct foundations
- Docker / containerd for standard labs
- Firecracker-class microVM backend for high-risk labs
- FastAPI for API
- Postgres for durable state

### Reference repos to study / potentially borrow patterns from
- `kubernetes-sigs/agent-sandbox`
- `abshkbh/arrakis`
- `trycua/cua`
- `arjan/awesome-agent-sandboxes` (market/reference map, not code base)

## Success Criteria for Phase 1
The platform is successful when it can:
- create labs safely from profiles
- enforce network / persistence / export policy
- run commands and long-lived jobs
- preserve logs and audit events
- snapshot state
- quarantine and release exports
- let agents/chat control labs without bypassing policy
- switch between container and microVM backends through a stable runtime interface
