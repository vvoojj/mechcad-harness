# Constraint Resolution Canonical Application Design

## Status and problem

This is an accepted-design candidate for the currently missing generic platform
edge: trusted constraint resolution records to an ordinary canonical revision.
The design status entering this document is
`CONSTRAINT_RESOLUTION_CANONICAL_APPLICATION_DESIGN_READY`; implementation is
not evidence that the capability is already present.

Current architecture requires constraint resolution to apply canonical values
only through `ChangeEngine`, but current production composition has no such
entrypoint. The retained resolution machinery validates and persists a command
and typed resolution records, while `DesignState.authoritative_parameters`
remains unpopulated by that machinery. This is
`REQUIRED_CURRENT_NOT_IMPLEMENTED`, not a reason to restore the retired F10
route.

## Scope

The implementation adds one narrow production entrypoint:

```python
ProductionApplication.admit_constraint_resolution_batch(
    resolution_run_id: str,
    command_id: str,
)
```

It admits one complete persisted `ConstraintResolutionBatchCommand` through
the existing `RunController` and `ChangeEngine` route. A successful first
application creates exactly one N -> N+1 revision. The source resolution run
is reused; no application run, receipt store, or canonical run locator is
created.

The platform supports all seven retained `SupportedConstraintKey` values. A
concrete `ConstraintResolutionAdmissionPolicy` selects the allowed subset; enum
membership alone never authorizes admission.

## Non-goals and protected boundaries

- F10 remains binding. Do not restore, rename, shim, or reconstruct
  `ConstraintResolutionApplicationService`, `ConstraintResolutionWorkflow`,
  `_anchor_for`, `mechcad-resolution`, `promote_existing_revision`, workflow
  preparation/receipt storage, or workflow-specific recovery.
- Do not modify `AuthoritativeParameter`, `DesignState` wire format, historic
  state hashes, `ChangeOperation`, `ChangeSet`, dependency models/graph/store,
  or `config/dependencies.yaml`.
- Do not add resolution-run locator fields such as `source_resolution_run_id`
  to canonical state. `AuthoritativeParameter.source_resolution_id` remains
  the canonical provenance identifier; the source run is durable,
  noncanonical provenance.
- Do not create a one-resolution-per-revision API, direct state mutation path,
  proposal-status authorization rule, automatic recovery route, or semantic
  dependency subsystem.
- M12's domain-neutral scalar `{value, unit}` authority is separate and out of
  scope. Typed authoritative values admitted here do not satisfy that gap.
- This capability closes the generic prerequisite discovered by MINI N2. It
  does not alter MINI's accepted historical completion, make MINI core pass,
  prove N2 -> N3 recomputation, or authorize restarting MINI.

## Retained authority model

The implementation reuses, without copying target mapping:

- `ConstraintRequestMaterializer` and `ConstraintRequestStore`;
- `ConstraintResolutionBatchCommand`, `ConstraintResolutionMaterializer`,
  `ConstraintResolutionStore`, and `ConstraintResolutionRecord`;
- `canonical_value_for_answer(...)`, `parameter_id(...)`, and current
  deterministic CRREQ/CMD/CRRES/PARAM identities;
- current typed `AuthoritativeValue` and `AuthoritativeParameter` validation.

`ConstraintRequestMaterializer.anchor_for(...)` is the sole supported-key to
canonical-anchor mapping. The admission service must call it for every record;
it must not contain a second map or infer targets from filenames, labels,
geometry, or scope names.

Resolver identity is external-authority provenance. The sole mutation actor is
`mechcad-authority-admission`; it is distinct from the resolver and is allowed
only by the ordinary ownership rule:

```yaml
- path: /authoritative_parameters/*
  owner: mechcad-authority-admission
```

## Admission policy and production composition

`ConstraintResolutionAdmissionPolicy` is a domain-neutral immutable policy
with an exact `project_id`, loaded explicitly by
`ProductionApplication.create(...)` from an optional configuration path or an
equivalently narrow explicit configuration object. No policy means deny all. A
supplied policy whose `project_id` differs from `ProductionApplication.project_id`
is rejected at composition. There is no environment variable, runtime default
allow-list, resolver self-authorization, or populated global production policy
created by this capability.

Each immutable policy rule matches exact `resolver_type`, `resolver_id`, and
`engineering_scope_id`, and lists allowed `SupportedConstraintKey` values. A
batch is authorized only when one rule permits its resolver identity, scope,
and every key in the complete batch. Composition rejects malformed policy
configuration before exposing the production API.

`ProductionApplication` composes the policy and an admission service, exposes
only the batch API above, and delegates state change through the existing
source run's `RunController`. `proposal.status` is not an authorization or
approval gate; authorization is the policy plus the validation contract below.

## Batch contract and validation

The persisted command is the atomic admission unit. Before any canonical
mutation, the service must perform this ordered validation:

1. Load the exact command from `resolution_run_id`, confirm the run and its
   immutable manifest belong to the production project, and retain the manifest
   only as original run-creation provenance.
2. For first application, require the source run's current active
   revision/hash, the current canonical pointer, and a reloaded canonical
   snapshot/hash all to equal the command source revision/hash. The command
   need not equal the manifest initial revision/hash: a later command in an
   iterative run may bind to a later active revision.
3. Recompute the deterministic expected resolution ID for every command answer.
4. Load every expected run-scoped resolution record, then scan the source-run
   resolution directory for records whose `source_command_id` equals the
   requested command ID. Require that command-scoped set to equal the expected
   IDs exactly; reject missing, duplicate, malformed, substituted, or extra
   records claiming that command. Unrelated valid records for another command
   in the same run are permitted.
5. Require every record to be `ResolutionStatus.ACCEPTED`, bind it to the
   command/request/source identity, and recompute
   `canonical_value_for_answer(...)` for equality with its persisted value.
6. Load each source request, require `DISCOVERED`, require it to belong to
   `resolution_run_id`, and require its project, scope, key, revision, and
   state hash to match the command and record. Load its task definition/state
   from the same run and require their source bindings to match the command.
7. Authorize the complete resolver/key batch with
   `ConstraintResolutionAdmissionPolicy`.
8. Obtain every anchor exclusively with `ConstraintRequestMaterializer.anchor_for`.
   Before deriving `parameter_id(...)`, require exactly one matching source
   `Requirement.id` for a `requirement` anchor or exactly one matching source
   `Constraint.id` for a `constraint` anchor. Reject zero or duplicate matches;
   do not infer or create an anchor. Then derive IDs and reject duplicate
   targets or parameter IDs.
9. Search project-wide persisted resolution records for each required
   `source_resolution_id`; require exactly one equivalent record and reject
   project mismatch, malformed data, ambiguity, or conflicts.
10. On first application, require all target authoritative parameters absent
    in the current source state. On replay, use the separate replay contract.

The current canonical pointer must still equal the command source revision and
state hash before the first mutation. Any stale, conflicting, incomplete,
unauthorized, occupied, missing-anchor, or malformed condition fails before
`ChangeEngine` is called. A batch is never partially applied.

## Canonical operation and deterministic identities

The service compiles the validated complete batch into one ordinary
`ChangeProposal` with one ADD operation per parameter at
`/authoritative_parameters/<deterministic_parameter_id>`. Each value is a
current valid `AuthoritativeParameter` with its deterministic ID, normalized
anchor, engineering scope, key, typed canonical value, and
`source_resolution_id`.

Proposal and ChangeSet IDs are deterministic UUID-derived identities over the
immutable admission identity: project ID, resolution run ID, command ID,
source revision/hash, and sorted complete resolution-ID/parameter-ID pairs.
The implementation defines those identities in the new admission module and
uses the same canonical serialization rules on first application and replay.

`RunController.apply_approved_proposal(...)` receives an optional
`changeset_id` and forwards it unchanged to
`ChangeEngine.apply_proposal(..., changeset_id=...)`. This is the only generic
RunController extension. No ChangeEngine, operation, or ChangeSet schema change
is required.

## Project-wide resolution lookup

Resolution records remain physically run-scoped. Extend
`ConstraintResolutionStore` with the smallest project-wide, fail-closed lookup
needed for `source_resolution_id` provenance. It searches ordinary persisted
resolution records across project runs and accepts exactly one valid equivalent
record. Zero matches, multiple matches, a malformed matching record, a foreign
project record, or one ID with different payloads is an error. This is a
read-only lookup over existing records, not a second provenance database.

The same lookup detects a conflicting later accepted record for a source
request before first application or replay.

## Durable provenance, replay, and failure boundaries

Before first application, scan existing source-run event files in the existing
durable event format. For this deterministic admission identity, zero matching
`CONSTRAINT_RESOLUTION_BATCH_PREPARED` events causes one ordinary prepared event
to be appended; exactly one semantically equivalent event is reused; conflicting
or multiple events fail closed. The event contains the resolution run ID,
command ID, ordered resolution IDs, parameter IDs, proposal ID, deterministic
ChangeSet ID, and base revision/hash. The new admission module validates
persisted event records while scanning them; no generic event-store extension
or second provenance store is introduced.

An exact prepared event without canonical N+1 is not replay success. If the
canonical source is still exactly N and all first-application validation passes,
ordinary first application may continue using that event without appending a
duplicate. If canonical state has advanced but the completed durable chain is
absent, fail closed under the existing post-apply boundary.

Exact replay does not call `ChangeEngine` and never creates N+2. It succeeds
only when the exact command, complete resolution set, prepared event, proposal
and ChangeSet IDs, parameter IDs/values/source-resolution IDs, resulting
canonical snapshot/hash, advanced run state/history, ordinary
`REVISION_ADVANCED` evidence where available, normal invalidation record and
ChangeSet ID, and exact changed paths all agree. A partially matching parameter
set or missing durable provenance fails closed. No partial batch resume is
allowed.

Replay does not require the mutable active run binding to equal the old command
source; successful first application is expected to have advanced it to the
recorded N+1 state. It verifies the original source through the command,
request/task bindings, reloaded source snapshot, prepared event, resulting
canonical state, run history, ordinary transition evidence, and invalidation.

Validation-before-mutation is atomic at the service boundary. It does not make
the existing post-apply filesystem workflow transactional. If `ChangeEngine`
creates N+1 but an existing later run transition or invalidation write fails,
N+1 remains, the source run follows existing blocked/no-rollback semantics, and
the service adds neither rollback nor N+2 recovery. A later call may report
replay only after the complete durable chain exists; otherwise it reports the
existing post-apply failure condition.

## Dependency and Evidence semantics

All seven retained keys are currently `NO_CURRENT_DERIVED_DEPENDENCY`.
Admission changes ordinary paths
`/authoritative_parameters/<parameter_id>`. Because no configured dependency
rule matches those paths, the existing graph legitimately returns empty direct
and transitive node tuples. A normal zero-impact `InvalidationRecord` is still
persisted with parent/resulting revisions, deterministic ChangeSet ID, and
exact changed paths.

No current Evidence is incorrectly fresh: `EvidenceStore` stales only nodes
listed by later invalidation records. In particular, output-angular-speed
admission must leave `analysis.transmission.torque` Evidence `CURRENT`; torque
depends only on the configured force/arm/safety requirement paths. Do not add
`analysis.transmission` or blanket transmission invalidation.

A future accepted, production-wired Evidence consumer of an authoritative
parameter must add its dependency rule in that capability's own scope. Any
opaque-ID limitation is a future dependency-contract issue, not work for this
milestone.

## Acceptance criteria

- A multi-record, source-bound persisted command authorized by explicit policy
  produces one deterministic ChangeSet and exactly one N+1 revision.
- The new state reloads with all expected typed parameters and exact
  `source_resolution_id` provenance; its invalidation record has the expected
  zero impact where no rule applies.
- Fresh `ProductionApplication` composition reloads the result and exact replay
  creates no N+2 revision.
- Default-deny, unauthorized resolver, stale source, missing request,
  incomplete/extra/conflicting/ambiguous resolution, wrong anchor,
  missing canonical anchor, canonical-value mismatch, occupied target,
  malformed source run, active-binding mismatch, missing replay provenance,
  and partial replay all fail closed.
- Output-speed admission preserves current torque Evidence.
- No F10-retired component, MINI artifact, M12 scalar-authority surface,
  canonical state wire/hash, or dependency subsystem is changed.
