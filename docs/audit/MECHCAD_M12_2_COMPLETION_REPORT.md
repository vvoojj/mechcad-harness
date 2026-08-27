# M12-2 Typed Candidate & Component Authority Foundation Completion Report

## Final Disposition

`M12_2_TYPED_CANDIDATE_COMPONENT_AUTHORITY_FOUNDATION_VERIFIED`

Verification closure completed with `py -3 -m pytest tests/`: 1425 collected,
1391 passed, 34 skipped, 0 failed, and 0 errors in 1473.60 seconds. A prior
attempt was user-aborted during `tests/integration/test_m11_5_live_structural.py`;
it was not an environment timeout or a reported test failure.

## Implemented Models

The `mechcad_harness.candidates` package provides frozen, strict M12-2 models
for mechanical candidates, source bindings, component specifications/properties,
physical mechanism graphs, connections, joint bindings, unresolved inputs,
synthesis request/policy, lineage, and candidate-local design variables.

## Candidate Identity / Hashing

Every durable semantic model uses the existing canonical JSON SHA-256 function.
Candidate, request, policy, property, specification, and realization hashes are
recomputed during validation. Volatile execution data is not modeled or hashed.

## Source Binding

`CandidateSourceBinding` binds project, immutable revision, state hash, and an
ordered set of unique literal canonical paths with per-value hashes and authority
classifications. Validation rejects project/revision/state substitution, missing
paths, duplicate paths, and changed consumed values.

## Currentness

`CandidateCurrentnessService` returns `CURRENT`,
`STALE_RELATIVE_TO_CURRENT_STATE`, or `CURRENTNESS_UNAVAILABLE`. It first checks
integrity, then compares only explicit consumed paths against current state;
unrelated revisions can therefore remain current.

## Component Property Authority

Property availability is exactly `AVAILABLE`, `MISSING`, or `NOT_APPLICABLE`.
The dedicated generic property authority vocabulary is per property and is not
the material-specific M11 authority enum. Imported geometry is represented only
as a separate `GeometrySourceReference`; it grants no non-geometry claim.

## Component Specifications

`ComponentSpecificationSnapshot` holds immutable property snapshots, identity,
optional manufacturer/part number, declared interfaces, compatibility text, and
optional geometry artifact reference. It supports custom/generated components
without requiring manufacturer, part number, or STEP geometry.

## Physical Mechanism Topology

`PhysicalMechanismRealization` validates unique component/connection/joint IDs,
specification references, component/interface endpoints, and binding references.
Connection meaning flags are explicit and independent; they create neither CAD
placement nor structural/M11 semantics.

## Joint Realization Binding

`JointPhysicalRealizationBinding` is a string-bound reference to an existing
M10 joint identity without importing or modifying M10. Required joints missing
from a candidate graph are integrity-invalid/unresolved, while request scope can
explicitly mark other joints out of scope.

## Synthesis Request / Policy

Request and policy are independently frozen and hashed. Policy entries carry
hard-admissibility, preference, or execution-limit semantics. Candidate design
variables cannot bind a canonical source path, so policy cannot replace a
source-bound requirement.

## Unresolved Inputs

`UnresolvedCandidateItem` represents typed missing authority/property/geometry,
incomplete joint realization, and unsupported-scope conditions. It is not a
feasibility or suitability result.

## Integrity Verification

`CandidateIntegrityVerifier` revalidates nested hashes and exact request/policy/
source bindings. It fails closed on forged hashes, malformed structures,
missing specifications, graph reference defects, and required joint omissions.

## Publication / Fresh Reload

`CandidatePublicationService` explicitly publishes only verified candidates as
`candidate-publication@1` JSON through `ArtifactStore` under the existing
project/run artifact layout. Resolution reads verified bytes through
`ArtifactStore`, strictly parses the manifest, reconstructs models, recomputes
hashes, and checks source/artifact bindings. No CandidateStore or canonical
database was added.

## Canonical State Non-Mutation

Candidate construction, verification, currentness, and publication use only
read APIs on `StateManager`; none invokes ChangeEngine or creates a revision.

## Tamper / Replay Tests

Focused tests cover forged candidate/specification hashes, artifact byte tamper,
source relevance staleness, unavailable/missing property semantics, topology
defects, required-joint omission, canonical-policy override attempts, and
property-to-specification-to-candidate hash propagation.

## Production Composition

`ProductionApplication` owns read-only candidate integrity, currentness, and
publication services. It does not expose or compose a candidate generator,
catalog, sizing engine, CAD compiler, M10/M11 candidate executor, ranking, or
promotion service.

## Capability Claim

MechCAD can represent immutable source-bound noncanonical mechanical design
candidates containing property-authoritative component snapshots, typed physical
mechanism topology, and explicit joint-realization bindings; evaluate candidate
integrity/currentness; and explicitly publish/freshly verify candidate
definitions through `ArtifactStore` without mutating `DesignState`.

## Remaining Limitations

M12-2 implements no generation, component catalog, sizing/suitability,
optimization, candidate CAD, M10/M11 execution, comparison, selection, or
promotion. Publication is not Evidence or engineering verification.

## Verification Record

- `py -3 -m pytest tests/unit/test_m12_candidate_foundation.py -q`: 10 passed.
- `py -3 -m pytest tests/unit/test_m12_candidate_foundation.py tests/unit/test_artifacts.py tests/unit/test_state_foundation.py -q`: 52 passed.
- `py -3 -m pytest tests/`: 1391 passed, 34 skipped, 0 failed, 0 errors in 1473.60 seconds.
- `py -3 -m compileall -q src/mechcad_harness tests`: passed.
- `git diff --check`: passed; existing CRLF normalization warnings are not diff errors.
