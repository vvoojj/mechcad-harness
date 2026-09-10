# MechCAD M3 Git Reconstruction Report

## 1. Verdict

```text
M3_CAPABILITY_EXISTENCE: YES
M3_IMPLEMENTATION_STATUS: IMPLEMENTED_WITH_DEVIATIONS
M3_SPEC_CONFORMANCE: CONFORMANT_WITH_DEVIATIONS
M3_HISTORICAL_VERIFICATION_STATUS: NOT_RETAINED
CONFIDENCE: HIGH
```

The complete committed M3 core is present in one pure M3 commit. The absence
of retained execution output affects historical verification only; it does not
downgrade committed implementation.

## 2. Commit Boundary

```text
M2_PREDECESSOR_COMMIT: 37f3ff3ea143400adb460e4650e1b580a4f1488d
M3_START_COMMIT: df584f00b240ef8086b99d408f76f42a90c4b517
M3_IMPLEMENTATION_RANGE: df584f0 only
M3_COMPLETION_TREE: df584f00b240ef8086b99d408f76f42a90c4b517
M4_START_COMMIT: a958c397d974153d5712ff5bb2e35df7e4966c4f
```

`df584f0` is:

```text
feat: add M3 dependency invalidation
```

It adds the M3 design and plan, dependency configuration and implementation,
the `AppliedChangeResult` boundary change, M3 tests, and the README M3
section. No separate pre-M4 M3 implementation or repair commit was found.

`a958c39` is:

```text
feat: add M4 run control
```

It is classified `PURE_M4`. It adds the M4 run-control package, tests, design,
plan, and README section without modifying M3 implementation or configuration.

## 3. Artifact Inventory

### Design / Spec

| Path | First commit | Role | Temporal status |
| --- | --- | --- | --- |
| `docs/superpowers/specs/2026-08-18-mechcad-m3-dependency-invalidation-design.md` | `df584f0` | M3 design and scope contract | Contemporary |
| M3 section in `README.md` | `df584f0` | Historical milestone narrative | Contemporary |

### Implementation Plan

| Path | First commit | Role | Temporal status |
| --- | --- | --- | --- |
| `docs/superpowers/plans/2026-08-18-mechcad-m3-dependency-invalidation.md` | `df584f0` | M3 implementation and verification plan | Contemporary |

### Committed Implementation

- `config/dependencies.yaml`
- `src/mechcad_harness/dependency/models.py`
- `src/mechcad_harness/dependency/errors.py`
- `src/mechcad_harness/dependency/graph.py`
- `src/mechcad_harness/dependency/storage.py`
- `src/mechcad_harness/dependency/__init__.py`

`dependency/models.py`, `errors.py`, `graph.py`, and `storage.py` first appear
in `df584f0`. `config/dependencies.yaml` and `dependency/__init__.py` were
introduced by M0 (`7185351`) and modified for M3. `changes/engine.py` and
`changes/__init__.py` were introduced at the shared M1/M2 boundary `37f3ff3`
and modified by M3 to expose applied-change data; neither group is
M3-introduced implementation.

### Committed Tests

- `tests/unit/test_dependency.py` first appears in `df584f0`.
- M2 predecessor tests retained at the M3 tree include
  `tests/unit/test_changes.py` and `tests/unit/test_state_foundation.py`.

### Completion / Acceptance

No M3-specific completion report, acceptance record, CI transcript, terminal
transcript, completion marker, or audit closure record was found.

Later retrospective evidence includes:

- `docs/audit/MECHCAD_ARCHITECTURE_SPEC_RECONCILIATION.md`, which states that
  M3 has no separate acceptance record.
- `docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md`, which identifies
  `DependencyGraph` and `EvidenceStore` as the implementation locations.

## 4. M2 -> M3 Boundary

M2 historically returned a `RevisionSnapshot`. M3 changes
`ChangeEngine.apply_proposal()` to return an ephemeral `AppliedChangeResult`:

```python
AppliedChangeResult(
    snapshot: RevisionSnapshot,
    changeset_id: str,
    changed_paths: tuple[str, ...],
)
```

- `snapshot` is the newly persisted canonical revision.
- `changeset_id` comes from the accepted in-memory `ChangeSet`, generated as
  `CS-<uuid4()>`.
- `changed_paths` are the proposal operation paths.
- Duplicate paths are removed with first-occurrence order preserved.
- The result is ephemeral and is not persisted.
- M3 does not create canonical revisions.
- M3 does not directly mutate `DesignState`.

There is no committed `DependencyService` directly consuming the result. A
caller must explicitly map result fields into:

```text
EvidenceStore.build_invalidation(...)
EvidenceStore.record_invalidation(...)
```

This preserves the boundary:

```text
M2 = canonical mutation
M3 = derived invalidation after mutation
```

## 5. Intended M3 Architecture

The contemporary design and plan specify:

```text
accepted M2 ChangeSet
    -> AppliedChangeResult
    -> changed canonical paths
    -> DependencyGraph
    -> direct dependency impact
    -> downstream dependency impact
    -> immutable invalidation history
    -> Evidence freshness evaluation
```

Evidence remains outside canonical `DesignState`. M3 evaluates freshness but
does not execute recalculation, schedule tasks, or orchestrate agents.

## 6. Actual M3 Architecture

The committed architecture consists of:

- `AppliedChangeResult` in `changes/engine.py`;
- `DependencyGraph` and path matching in `dependency/graph.py`;
- typed graph, impact, freshness, and invalidation models in
  `dependency/models.py`;
- dependency and Evidence errors in `dependency/errors.py`;
- persistence and freshness operations in `dependency/storage.py`.

`EvidenceStore` historically owns:

```text
build_invalidation
record_invalidation
load_invalidation
write_evidence
load_evidence
get_evidence_freshness
is_evidence_fresh
fresh_evidence_status
```

The planned separate `DependencyService` was not created. The functional
capability exists with a different service boundary.

```text
ARCHITECTURE_CLASSIFICATION: IMPLEMENTED_DIFFERENTLY
```

## 7. Dependency Graph Models

### DependencyRule

```text
when: list[str]
invalidates: list[str]
```

Both lists require at least one item through Pydantic validation.

### DependencyEdge

```text
source: str
target: str
```

Both node names must be non-empty.

### ChangeImpact

```text
changed_paths: tuple[str, ...]
direct_nodes: tuple[str, ...]
all_nodes: tuple[str, ...]
```

There is no separate `transitive_nodes` field. `all_nodes` contains direct
nodes plus their downstream transitive nodes.

### InvalidationRecord

```text
project_id: str
revision: int
parent_revision: int | None
changeset_id: str | None
changed_paths: tuple[str, ...]
directly_invalidated_nodes: tuple[str, ...]
transitively_invalidated_nodes: tuple[str, ...]
created_at: str
```

`transitively_invalidated_nodes` is populated from `ChangeImpact.all_nodes`,
so it includes direct nodes as well. The Pydantic models are not frozen; the
practical immutability guarantee is provided by exclusive persisted files.

## 8. Dependency Configuration

At the M3 completion tree, `config/dependencies.yaml` contains these rules:

```text
/materials/*
    -> analysis.materials
    -> analysis.structural
    -> analysis.fits
    -> analysis.transmission_strength
    -> validation.geometry

/components/*/transmission/*
    -> analysis.transmission
    -> analysis.packaging
    -> validation.collision

/components/*/placement/*
    -> analysis.packaging
    -> validation.collision
    -> validation.assembly

/requirements/*
    -> analysis.requirements
    -> analysis.loads
```

The directed edges are:

```text
analysis.loads -> analysis.structural
analysis.structural -> validation.structural
```

Parser behavior:

- JSON is attempted first.
- Otherwise a restricted in-repository YAML subset parser is used.
- PyYAML is not used despite being named in the plan's tech stack.
- Pydantic validates rule and edge shapes.
- Malformed syntax and invalid paths fail as `DependencyConfigError`.
- Duplicate rules and edges are accepted.
- Adjacency sets deduplicate duplicate edge targets.
- Unknown node names may become graph nodes.
- Cycles fail graph construction.

```text
PARSER_CLASSIFICATION: IMPLEMENTED_DIFFERENTLY
```

## 9. Path Matching Semantics

M3 uses the independent matcher `dependency.graph.path_matches`.

- Patterns and paths must begin with `/`.
- Root `/` is invalid.
- Empty segments are invalid.
- `~` is rejected.
- `*` matches exactly one segment.
- `*` does not span multiple segments.
- A pattern may be a prefix of a longer changed path.
- A longer pattern cannot match a shorter changed path.
- The matcher is not RFC 6901.

Examples:

```text
/materials/*
    matches /materials/MAT-001/material

/components/*/transmission
    matches /components/PRT-001/transmission/module
```

## 10. M2 Ownership vs M3 Dependency Matching

M2 ownership matching and M3 dependency matching are separate contracts.

M2 ownership matching strips surrounding slashes, uses literal and one-segment
wildcard segments, applies prefix matching, and selects the most specific
owner rule.

M3 dependency matching requires leading slashes, rejects root, empty segments,
and `~`, evaluates every matching dependency rule, and returns affected graph
nodes. M3 did not change M2 ownership behavior.

## 11. Direct Impact

```text
DIRECT_IMPACT_DEDUPLICATED: YES
DIRECT_IMPACT_DETERMINISTIC: YES
```

`DependencyGraph.impact()`:

1. Deduplicates changed paths while preserving first-seen order.
2. Checks every rule against every normalized path.
3. Collects matched direct nodes into a set.
4. Returns direct nodes sorted lexicographically.

This covers one path, multiple paths, multiple rules matching one path, and
multiple paths matching one node. Unrelated paths produce no direct impact.

## 12. Transitive Impact

Edges mean source node to downstream dependent node. Traversal is recursive
DFS with sorted adjacency and a result set. The final `all_nodes` tuple is
sorted and deduplicated. Direct nodes are included in `all_nodes`.

Historical example:

```text
/requirements/R-1/description
    -> analysis.loads
    -> analysis.structural
    -> validation.structural
```

The committed test `test_transitive_nodes_are_sorted_and_deduplicated` verifies
the sorted result:

```text
analysis.loads
analysis.structural
validation.structural
```

## 13. Cycle / Configuration Validation

Cycle detection runs during graph construction. DFS tracks `visiting` and
`visited` sets. A back edge raises `DependencyCycleError`; no partially valid
graph is returned.

```text
CYCLE_HANDLING: FAIL_CLOSED
```

The committed test `test_dependency_graph_rejects_cycles` covers this path.

## 14. InvalidationRecord

Invalidation records are built from graph impact and a UTC-aware ISO timestamp.
The stored `transitively_invalidated_nodes` value includes direct nodes because
it receives `ChangeImpact.all_nodes`.

The record model does not itself prove that its revision, parent revision, or
changeset ID corresponds to a canonical revision history before persistence.

## 15. Invalidation Persistence

Invalidations are stored at:

```text
projects/<project_id>/invalidations/REV-XXXXXX.json
```

`EvidenceStore.record_invalidation()`:

- creates parent directories;
- serializes compact, sorted UTF-8 JSON;
- writes a temporary file;
- flushes and fsyncs the temporary file;
- publishes with `os.replace()`;
- rejects an existing destination with `InvalidationError`.

An existing record is not overwritten through ordinary sequential use. Corrupt
existing records are not repaired by duplicate writes, and corrupt loads raise
`InvalidationError`.

The existence checks plus `os.replace()` are not a concurrency-proof exclusive
filesystem primitive. M3 does not establish serialized concurrent-writer
safety.

## 16. Evidence Persistence

Evidence is stored at:

```text
projects/<project_id>/evidence/<evidence_id>.json
```

Historical behavior:

- duplicate IDs raise `EvidenceConflictError`;
- evidence `kind` must be a known graph node when written;
- Evidence remains outside `DesignState`;
- stale Evidence remains stored;
- no automatic deletion exists.

```text
canonical state != derived Evidence
```

## 17. Evidence Provenance

M3 uses these Evidence fields:

```text
id
kind
summary
revision
state_hash
```

Freshness evaluation verifies:

1. Evidence can be loaded.
2. Its dependency node is known.
3. The exact historical canonical snapshot exists and passes integrity checks.
4. Evidence `state_hash` equals the snapshot `state_hash`.
5. Every later required invalidation record exists and is readable.
6. Later invalidation impact is evaluated.

The retained implementation does not additionally compare embedded snapshot
or invalidation `project_id`/`revision` fields with the file path requested by
the caller. Consequently, the following "exact" and "complete" statements
describe readable path coverage and state-hash matching, not full record
identity binding.

## 18. Freshness State Machine

### CURRENT

`CURRENT` requires readable path-level revision provenance with matching state
hash, a known dependency node, complete later invalidation path coverage, and
no later invalidation affecting the node. It is not a proof of full embedded
record identity binding.

### STALE

`STALE` requires valid provenance and complete history, with at least one later
invalidation containing the Evidence node in
`transitively_invalidated_nodes`. Because that field includes direct nodes,
both direct and downstream impact can make Evidence stale.

Old stale Evidence does not become current again. Replacement Evidence bound to
a later revision can be current.

### UNKNOWN

`UNKNOWN` is returned when safe freshness cannot be proven, including:

- unknown dependency node;
- missing or invalid historical snapshot;
- state-hash mismatch;
- missing later invalidation record;
- corrupt later invalidation record.

The helper semantics are fail-closed:

```text
CURRENT -> is_evidence_fresh() == True
STALE   -> is_evidence_fresh() == False
UNKNOWN -> is_evidence_fresh() == False
```

`fresh_evidence_status()` reports fresh evidence only when at least one matching
record is `CURRENT`; stale and unknown records are not treated optimistically.

## 19. Complete-History Requirement

For Evidence at revision `N` and current revision `M`, the required invalidation
records are exactly:

```text
N+1 ... M
```

A missing or corrupt record immediately yields `UNKNOWN`. The test
`test_freshness_requires_complete_history_and_valid_provenance` covers missing
history. Embedded invalidation identity is not independently checked.

## 20. Same-Revision Invalidation Exclusion

The freshness loop starts at `evidence.revision + 1`. Therefore the invalidation
that produced revision `N` is excluded when evaluating Evidence created at
revision `N`.

`test_evidence_at_revision_is_not_invalidated_by_own_record` verifies this
behavior.

## 21. Replacement Evidence

`test_end_to_end_unrelated_then_material_change_and_replacement` verifies:

1. Revision 1 material and packaging Evidence is written.
2. An unrelated revision 2 leaves both records `CURRENT`.
3. A material revision 3 makes material Evidence `STALE` while packaging
   Evidence remains `CURRENT`.
4. New material Evidence bound to revision 3 is `CURRENT`.

Revision 3's own invalidation is excluded from the replacement Evidence check.

## 22. M2 -> M3 End-to-End Flow

The committed boundary supports this flow:

```text
ChangeProposal
    -> ChangeEngine.apply_proposal()
    -> canonical RevisionSnapshot
    -> AppliedChangeResult
    -> caller extracts result fields
    -> EvidenceStore.build_invalidation()
    -> EvidenceStore.record_invalidation()
    -> future Evidence freshness query
```

Invalidation recording is not automatic inside `ChangeEngine`. The M3 tests
exercise the storage and freshness flow, but do not directly assert the full
caller consumption of `AppliedChangeResult`.

## 23. Failure After Canonical Revision

Canonical revision creation occurs before caller-recorded M3 invalidation.
If canonical persistence succeeds but invalidation persistence fails:

- the canonical revision remains valid;
- `current.json` remains advanced;
- no rollback occurs;
- required invalidation history has a gap;
- later freshness evaluation returns `UNKNOWN` when that gap is required;
- no automatic retry occurs;
- no recalculation is automatically executed.

This is fail-closed freshness behavior, not canonical-state rollback.

## 24. Canonical / Derived Authority Boundary

```text
M2 = canonical DesignState mutation and revision creation
M3 = derived dependency impact, invalidation history, and Evidence freshness
```

The persisted, validated DesignState revision remains canonical. Invalidation
records and Evidence are separate bindable records.

## 25. Historical M3 Tests

The directly verified historical blob
`df584f00b240ef8086b99d408f76f42a90c4b517:tests/unit/test_dependency.py`
contains 10 test function definitions.

```text
M3_TEST_FILE: tests/unit/test_dependency.py
M3_ACTUAL_TEST_FUNCTION_COUNT: 10
FORENSIC_TEST_COUNT_CORRECTION_REQUIRED: YES
TEST_CODE_IMPLEMENTED: YES
HISTORICAL_TEST_EXECUTION_EVIDENCE: NOT_RETAINED
```

Exact historical test names:

### Dependency matching

- `test_dependency_prefix_and_wildcard_match`
- `test_unrelated_path_has_no_impact`

### Direct / transitive impact and deterministic ordering

- `test_transitive_nodes_are_sorted_and_deduplicated`

### Cycle handling

- `test_dependency_graph_rejects_cycles`

### Persistence and immutability

- `test_invalidation_and_evidence_records_are_immutable`

### Provenance and complete-history freshness

- `test_freshness_requires_complete_history_and_valid_provenance`
- `test_wrong_hash_and_unknown_node_are_unknown`

### Same-revision exclusion

- `test_evidence_at_revision_is_not_invalidated_by_own_record`

### Stale Evidence and fresh helper behavior

- `test_matching_later_invalidation_is_stale_and_unknown_is_not_fresh`

### Replacement Evidence and end-to-end behavior

- `test_end_to_end_unrelated_then_material_change_and_replacement`

The earlier forensic prose count of 8 was incorrect. The historical source
file is authoritative, so the corrected count is 10.

No committed M3 test directly demonstrates:

```text
AppliedChangeResult
    -> caller consumes result
    -> build_invalidation
    -> record_invalidation
```

## 26. Design vs Plan vs Committed Implementation

| Requirement | Design | Plan | Committed Git | Tests | Classification |
| --- | --- | --- | --- | --- | --- |
| `AppliedChangeResult` boundary | Required | Required | Present with snapshot, changeset ID, changed paths | No direct assertion | IMPLEMENTED_AS_DESIGNED |
| Separate dependency service | Required conceptually | `DependencyService` planned | Functions embedded in `EvidenceStore` | No direct service test | IMPLEMENTED_DIFFERENTLY |
| Static dependency configuration | Required | Required | Present | Graph fixtures and impact tests | IMPLEMENTED_AS_DESIGNED |
| Literal, wildcard, prefix matching | Required | Required | Present | Yes | IMPLEMENTED_AS_DESIGNED |
| Direct impact | Required | Required | Sorted and deduplicated | Yes | IMPLEMENTED_AS_DESIGNED |
| Transitive impact | Required | Required | Recursive DFS, sorted and deduplicated | Yes | IMPLEMENTED_AS_DESIGNED |
| Cycle rejection | Required | Required | `DependencyCycleError` at construction | Yes | IMPLEMENTED_AS_DESIGNED |
| YAML parser | YAML configuration | PyYAML named in plan | Restricted local YAML/JSON parser | Indirect | IMPLEMENTED_DIFFERENTLY |
| Immutable invalidations | Required | Required | Exclusive external JSON files | Yes | IMPLEMENTED_AS_DESIGNED |
| Immutable Evidence | Required | Required | Exclusive external JSON files | Yes | IMPLEMENTED_AS_DESIGNED |
| Exact provenance | Required | Required | Revision path and state hash checked; embedded record identity unchecked | Partial | IMPLEMENTED_WITH_DEVIATIONS |
| `CURRENT` / `STALE` / `UNKNOWN` | Required | Required | Present | Yes | IMPLEMENTED_AS_DESIGNED |
| Complete later-history coverage | Required | Required | Requires every `N+1 ... M` record | Yes | IMPLEMENTED_AS_DESIGNED |
| Same-revision exclusion | Required | Required | Present | Yes | IMPLEMENTED_AS_DESIGNED |
| Fresh Evidence helper | Required | Required | `is_evidence_fresh` and status helper | Partial direct coverage | IMPLEMENTED_AS_DESIGNED |
| Automatic M2-to-M3 recording | Explicit caller boundary | Explicit caller call | Not automatic in ChangeEngine | No direct integration test | IMPLEMENTED_AS_DESIGNED |
| Duplicate config validation | Stricter validation intended | Stricter validation planned | Duplicates accepted; runtime structures deduplicate some outputs | No | IMPLEMENTED_DIFFERENTLY |
| Scope exclusions | Required | Required | No execution/orchestration/CAD/FEA | README and code | IMPLEMENTED_AS_DESIGNED |

These deviations do not negate the committed M3 capability.

## 27. Historical Verification Evidence

```text
HISTORICAL_PYTEST_EVIDENCE: NOT_RETAINED
HISTORICAL_COMPILEALL_EVIDENCE: NOT_RETAINED
HISTORICAL_DIFF_CHECK_EVIDENCE: NOT_RETAINED
HISTORICAL_ACCEPTANCE_RECORD: NOT_RETAINED
```

Committed tests establish test code implementation. No retained output proves
that the historical pytest, compileall, or diff-check commands were executed.
Unchecked plan boxes do not override committed implementation.

## 28. M3 -> M4 Boundary

```text
M4_START_COMMIT: a958c397d974153d5712ff5bb2e35df7e4966c4f
BOUNDARY_CLASSIFICATION: PURE_M4
```

M4 conceptually consumes M3 freshness semantics, but the boundary commit does
not modify M3 code or configuration. The M3 completion tree is therefore
`df584f00b240ef8086b99d408f76f42a90c4b517`.

## 29. Later Evolution

| M3 foundation | Later state | Evidence |
| --- | --- | --- |
| `DependencyGraph` and parser | EXTENDED | `682300b` fixes parsing of inline empty lists. |
| Path matching | PRESERVED | No later semantic change found. |
| Dependency configuration | EXTENDED | Later commits add torque, structural, physical-mechanism, and convergence rules or edges. |
| Invalidation persistence | PRESERVED | No later invalidation-storage redesign found. |
| EvidenceStore persistence | EXTENDED | Later commits adapt payload handling for execution provenance. |
| Evidence schema | EXTENDED | `6cbade0` adds producer and backend provenance fields. |
| Freshness semantics | PRESERVED | No later change to the complete-history algorithm found. |
| `AppliedChangeResult` | EXTENDED | Later proposal preparation, locking, and optional changeset-ID support retain the result boundary. |

This section records only M3 foundation evolution and does not reconstruct
later milestones.

## 30. Unresolved Questions

- No retained M3-era execution transcript proves whether historical pytest,
  compileall, or diff-check commands were executed.
- No retained explicit M3 completion or acceptance artifact exists.
- No direct M3 test demonstrates full caller consumption of
  `AppliedChangeResult` into an invalidation record.

These are evidence gaps, not implementation failures.

## 31. Final Reconstructed Classification

```text
M3_CAPABILITY_STATUS: IMPLEMENTED_WITH_DEVIATIONS
M3_GIT_HISTORY_STATUS: SINGLE_COMMIT_PURE_MILESTONE
AT_TIME_IMPLEMENTATION_STATUS: IMPLEMENTED_WITH_DEVIATIONS
SPEC_CONFORMANCE_STATUS: CONFORMANT_WITH_DEVIATIONS
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
CURRENT_HISTORICAL_STATUS: PRESERVED_AND_EXTENDED
```

## 32. Reconstruction Publication Provenance

Git proves that the M0-M4 reconstruction records were published in:

```text
RECONSTRUCTION_PUBLICATION_COMMIT: 8fda5aa580993b5256bfbf1267216ce0f066d0cd
```

That checkpoint added the ledger and all M0-M4 canonical/evidence records.
The historical milestone conclusions remain based on their original boundary
commits, not on the reconstruction-publication commit.

The earlier record's self-description of a worktree observation is not
independently verifiable as a separate forensic phase. It is therefore not
used as evidence for the publication process.
