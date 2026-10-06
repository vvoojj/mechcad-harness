# Deterministic STEP Content Identity Spec Revision - Independent Acceptance

## Verdict

```text
Target:
docs/superpowers/specs/2026-09-19-deterministic-step-content-identity.md

Exact accepted Spec SHA-256:
DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68

Disposition:
INDEPENDENTLY_ACCEPTED

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_SPEC_INDEPENDENTLY_ACCEPTED
```

This disposition applies ONLY to the exact Spec bytes whose SHA-256 is stated
above. Any byte change to the Spec, including a status-wording change, produces
a different SHA and is not covered by this acceptance.

## Materialization Boundary

This record materializes the prior independent read-only re-audit result for
the exact Spec revision above. It does not edit the Spec, the Plan, production
code, tests, architecture, reference material, reconstruction/history, or any
pre-existing audit record.

The accepted Spec remains marked PROPOSED / DOCUMENTATION_ONLY / pending
independent acceptance in its own bytes. Those strings are part of the accepted
byte sequence and were not changed. This later record is the durable repository
authority establishing INDEPENDENTLY_ACCEPTED for the exact SHA above.

The Spec acceptance is design/specification acceptance only. It does not accept
or authorize implementation, production composition, default activation, test
execution, or live runtime verification.

## Acceptance Context

Acceptance-record materialization date: 2026-09-26

Branch observed before writing:

```text
master
```

HEAD observed before writing:

```text
05da8edad18488492f02be1dad9d1ec3653ce807
```

The current Plan is:

```text
docs/superpowers/plans/2026-09-21-deterministic-step-content-identity-implementation.md
SHA-256: 4C6D3BDCA27824FF5E57B7FA78DC8C6128E6BDA23C3DE85249071D4654B5E9E4
```

The Plan is now STALE for future T-P7.2 work because it binds the earlier
accepted Spec revision rather than `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.
The Plan must be revised to bind this exact Spec SHA, and that revised Plan
must receive independent Plan acceptance before any implementation
authorization.

Production default remains LEGACY. T-P7.2 remains STOPPED until:

```text
revised Plan bound to DE17C360...
-> independent Plan acceptance
-> explicit implementation authorization
```

T-P7.3 and P8 remain unauthorized and not started as applicable. No runtime,
FreeCAD, Gmsh, CalculiX, MINI, implementation-test, CI, or live-verification
claim is made by this Spec acceptance.

## Acceptance-Critical Closure

The following closure is accepted as normative Spec design. It is not a claim
that the current implementation already provides the wiring.

### Global Raw Completeness

`required_raw_source_artifacts` is verifier-local and represents the complete
authority-derived raw source set. Candidate-CAD provenance requires exact
bidirectional equality between the set and the provenance envelope:

```text
no extra
AND
no missing
```

Every required raw artifact is byte-verified with its existing raw provenance
bindings before semantic acceptance.

### Raw Set and Raw Multiset

`required_raw_source_artifacts` is the logical raw source set keyed by exact
artifact identity, including `(artifact_id, artifact_hash)`.

`verified_source_artifact_hashes` is an order-insensitive,
multiplicity-preserving raw SHA multiset. These are distinct obligations. Raw
set completeness is not replaced by raw-hash membership, and the raw multiset
is not collapsed into the deduplicated semantic-content collection.

Raw and semantic collection lengths are independent. No positional zip or
count linkage between them is permitted.

### Per-Slot Raw Correctness

For each `TRUSTED_SOURCE_GEOMETRY` mapping, the exact slot key is:

```text
(mapping.physical_instance_id, mapping.cad_instance_id)
```

The expected raw pair is selected only from the authoritative component
specification's single `GeometrySourceReference`:

```text
(GeometrySourceReference.artifact_id,
 GeometrySourceReference.artifact_hash)
```

The actual raw pair is reconstructed only through:

```text
mapping.cad_instance_id
-> persisted CadAssemblyProgram instance
-> instance.part_id
-> persisted imported component
-> ImportedCadComponent.artifact_id / artifact_hash
```

The expected pair must equal the actual pair exactly, field-for-field and
byte-for-byte. Missing, ambiguous, conflicting, or unverifiable resolution
fails closed. The pair must also be a member of the already verified complete
raw source set.

The expected pair is not derived from semantic content identity,
`mapping.source_geometry_identity`, `mapping.geometry_definition_identities`,
`verified_source_content_identities`, `semantic_assembly_hash`, or content
equality.

### Equal-Content Artifacts Are Not Interchangeable

The accepted Spec rejects this forged in-set slot swap:

```text
Authority:       P1/S1 -> A
                 P2/S2 -> B

Forged assembly: S1 -> B
                 S2 -> A
```

The rejection remains mandatory even when A and B are both globally required,
both byte-verify, both remain in the raw multiset, and
`step-content-identity@1(A) == step-content-identity@1(B)`.

### Positive N=2/M=1 Case

The correct binding remains valid:

```text
S1 -> A
S2 -> B
```

Two distinct raw artifacts with one shared semantic content identity are
valid when both exact per-slot pairs match, both raw artifacts are required and
byte-verified, raw multiset obligations pass, and semantic recomputation
deduplicates the shared content identity once. Raw and semantic collection
lengths are not required to match.

### Semantic Recomputation

Semantic content identity is recomputed only from the exact byte-verified raw
artifact correctly bound to each slot. Raw artifact IDs and raw SHA values stay
outside new semantic hashes. Raw provenance is validated independently from
semantic identity and semantic deduplication.

### Capability Classification

The accepted audit classification is:

```text
EXISTING_CAPABILITY_NOT_WIRED_TO_THIS_PATH
```

The required data is already representable through the current physical
component, component specification, candidate mapping, assembly, and imported
component structures. The missing work is verifier wiring. This does not
authorize a new generic persistence, store, registry, authority, or service
subsystem, and this record does not claim that the wiring is implemented,
production-wired, unit-verified, or live-verified.

## Preserved Closed Surfaces

This revision preserves the prior accepted design closures, including:

- raw/content separation;
- immutable raw `EngineeringArtifact.sha256` semantics;
- frozen legacy schemas, hashes, serializers, validators, and historical records;
- `canonical-m10-provenance@2` with exactly 5 declared fields;
- `candidate-multi-joint-m10-provenance@1` with exactly 7 declared fields;
- no `candidate-multi-joint-m10-provenance@2`;
- no `promotion-chain-locator@2`;
- provenance envelopes with no self-hash;
- P5 low-level request as PURE_REDERIVED;
- typed P6 result persisted;
- legacy P6 result self-hash recomputed before semantic acceptance;
- Root A as verified entry context only;
- Roots B and C as durable restart roots;
- zero-execution restart contract;
- §17 single-joint and multi-joint promotion request counts of 19 and 18;
- homogeneous new-family dispatch;
- mixed-version failure;
- no new `ArtifactStore`, service, registry, or persistence path.

These are preserved design statements, not implementation or runtime
acceptance claims.

## Historical Chain

Historical evidence is preserved and not retargeted:

- Previously accepted controlling baseline before this revision:
  `1C1284D3B6F281C09FF457D6C708B2D770038C67F7C72306D880A95F149DEFAF`.
- Its existing acceptance record remains unchanged at:
  `docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_SPEC_INDEPENDENT_ACCEPTANCE.md`.
- Rejected/remediated predecessor exposing the per-slot raw-binding defect:
  `3CC91B0C513A88EF34A657F8D08B45020567666D3ABFE2DE44CB9C9F8EBD50A2`.
- Intermediate cleanup predecessor:
  `51FA438DD4A867F3A9B7F49478998D9A1EE6026EE0987B7A2D09925B2571E81C`.
- Accepted revision now:
  `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.

No rejected or intermediate SHA is treated as accepted. The earlier
`1C128...` acceptance remains historical truth for its exact bytes only.

## Verification and File Scope

Before writing this record, independent `Get-FileHash -Algorithm SHA256`
checks produced:

```text
Spec: DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68
Plan: 4C6D3BDCA27824FF5E57B7FA78DC8C6128E6BDA23C3DE85249071D4654B5E9E4
```

The pre-write worktree status count was 99. The requested revision-specific
path did not exist before writing. The only intentional mutation from this
task is this new file:

```text
docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_SPEC_REVISION_DE17C360_INDEPENDENT_ACCEPTANCE.md
```

The old `...SPEC_INDEPENDENT_ACCEPTANCE.md` record was not edited, replaced,
retargeted, or deleted. Pre-existing worktree changes were preserved.

No tests, implementation tests, FreeCAD, Gmsh, CalculiX, MINI, live runtime,
commit, reset, stash, clean, push, install, Spec edit, Plan edit, code edit,
test edit, architecture edit, reference edit, reconstruction/history edit, or
existing-audit edit was performed.

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_SPEC_INDEPENDENTLY_ACCEPTED
