# M7B-2A - Yagi Payload-Carrier Authority

## Status

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
```

## Git Boundary

M7B-2A is `30b99eb02cf2fbb627fb59378e34372dbd7adfc9`, the direct child of
M7B-1B `7c7352a57632d6202a25351761f5cfe0e15adc5b` and direct parent of
`3f7bbc7`. It changes 8 files with 306 insertions and 3 deletions.

## Historical Role And Result

The commit establishes authority for `YAGI_PAYLOAD_CARRIER_REQUIREMENTS`,
requirement `REQ-YAGI-PAYLOAD-CARRIER-REQUIREMENTS`, ownership, discriminated
resolution answers, and canonical values. It captures antenna count, rotating
payload limit, frequency/envelope records, spacing and travel, COM targets,
collision strategies, elevation sweep, axis height, extrusion guidance, and
explicit unresolved/not-frozen/not-structurally-accepted states.

Existing resolution application persists the authoritative parameter and
supports reload. This commit does not synthesize a carrier, generate CAD,
perform collision/kinematic analysis, make structural claims, or approve
manufacturing.

## Tests And Execution Evidence

The candidate adds 10 unparameterized unit tests, increasing top-level test
functions from 412 to 422 and collected cases from 431 to 441. Tests cover key
and anchor binding, hard limits, envelope/spacing/balance semantics, unresolved
status, canonicalization, wrong-type rejection, strategy preservation, and
reload persistence.

No candidate-era test transcript, live FreeCAD test, generated artifact,
workspace result, completion report, audit, acceptance marker, tag, or Git note
is retained. The persistence test uses `tmp_path` and is not durable acceptance
evidence.

## Material Deviations

- No formal M7B-2A specification or plan exists at the candidate boundary.
- `DesignState.yagi_payload_carrier_requirements` remains `list[dict]` rather
  than a fully typed carrier-domain collection.
- Cross-field validation is incomplete, including envelope cardinality/identity,
  frequency alignment, and sweep-bound relationships.
- Product selection, wind data, polarization, cabling, exact boom sections,
  structural acceptance, and final geometry remain unresolved by design.

## Successor Relationship

`3f7bbc7` adds bundled M7B-2B/R2/R3/R4 carrier synthesis, clamp-slider and
sliding-interface work, through-slot operation, and preliminary packaging CAD.
`9ab9e48` adds collision-layout and transient kinematics. Later `8079c57` adds
production composition and durable artifacts. These are successor capabilities,
not M7B-2A acceptance evidence.

## Reconstruction Conclusion

M7B-2A is a proven authority/resolution implementation with unit-test presence,
partial cross-field validation, no live or generated artifact, and no retained
formal acceptance evidence.

See [detailed Git evidence](../evidence/M7B-2A_GIT_RECONSTRUCTION.md).
