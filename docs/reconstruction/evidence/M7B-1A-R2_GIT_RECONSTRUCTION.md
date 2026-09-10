# M7B-1A-R2 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: CO_DELIVERED_IMPLEMENTATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Attribution

`19f77a30ef42040d5f07688ab4235a25daaba7f0` is the direct child of
`4468a621dfdf0662acf74501e13b5b182920cf13` and direct parent of
`7c7352a57632d6202a25351761f5cfe0e15adc5b`. The complete commit changes 42
files, with 2,629 insertions and 13 deletions. It bundles M7B with M7A CAD,
assembly, artifact, and exact-analysis work.

The curated M7B attribution is 11 files, 567 insertions, and 4 deletions. The
M7B interface and fixture implementation must not be treated as the complete
42-file commit's exclusive scope.

## Delivered Authority And Fixture Path

The source introduces azimuth drive mounting-interface concepts for threaded
holes, through holes, required mating holes, mount-point IDs, coordinates,
frames, central openings/keepouts, and radial clearance. It wires supported
constraint keys, canonical values, typed resolution answers, anchors,
satisfaction, and application.

A deterministic fixture-only motor-mount plate model/compiler provides hashes,
measurements, readiness, and missing-input reporting. It does not persist a
canonical plate state, synthesize plates, import real hardware, validate
structure, or approve manufacturing.

## Tests And Reproduction Accounting

The attributable M7B suite contains 24 functions:

| File/group | Functions |
| --- | ---: |
| `test_azimuth_mount_plate.py` | 6 |
| `test_m7b1a_authority.py` | 5 |
| `test_m7b1ar_semantics.py` | 12 |
| FreeCAD integration | 1 |

Git adds all 24 functions; the curated R2-only semantic subset is 17 functions
(5 authority and 12 semantic). Focused reproduction: `24 passed`. Full candidate reproduction:
`383 passed, 31 skipped, 1 failed`; the failure is the inherited test expecting
py_gearworks to be unavailable while it is installed.

The FreeCAD integration uses synthetic data and explicit
`M7B1_TEST_FIXTURE_ONLY` provenance. It exercises a CAD path, not real hardware
acceptance. No historical stdout, generated artifact, workspace result, CI
record, completion report, audit, acceptance marker, tag, or Git note is
retained.

## Conformance And Deviations

The authority separates hardware interface requirements from plate design
variables and enforces unique IDs, explicit frames, finite coordinates, opening
requirements, deterministic hashes, and fail-closed readiness.

The persisted authority value carries `mount_points` as `tuple[dict, ...]`,
while domain `MountPointSpec` is typed; only uniqueness is validated through
the authority carrier. The integration test guards on package importability,
not `discover_freecad().available`, and hard-codes the executable path.
End-to-end azimuth request materialization/application is not covered.

## Successor

The relevant chain is `4468a62 -> 19f77a3 -> 7c7352a -> 30b99eb -> 3f7bbc7
-> 9ab9e48 -> 8079c57`. `7c7352a` is the deterministic synthesis successor,
adding requirements authority, stock policy, envelope/ligament calculations,
draft proposals, persisted plate records, ownership, and synthesis tests.
Later `8079c57` is a production/acceptance boundary, not R2 evidence.

## Review Conclusion

Skeptical review confirms the co-delivered boundary, curated 11-file M7B slice,
24-test accounting, synthetic-only FreeCAD evidence, typed-carrier deviation,
guard defect, and absence of retained acceptance evidence.
