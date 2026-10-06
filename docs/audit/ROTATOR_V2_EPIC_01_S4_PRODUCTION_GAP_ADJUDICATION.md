# Rotator V2 Epic 01 S4 Production-Gap Adjudication

## Decision

The S4 blocker is confirmed as a production-facing implementation gap. The
frozen authority and S3 semantic fixture exist, but the candidate has not been
expanded from the two-motor S2 fixture into a CAD-realizable candidate, and the
Epic-specific CAD bridge is absent. This is not evidence that the frozen
geometry is physically infeasible. It is evidence that S4 cannot currently be
executed through the production candidate-CAD path without implementing the
prohibited S4 work.

## Scope And Method

This was a read-only adjudication of the accepted Spec, accepted Plan, current
project files, production candidate-CAD contracts, and the Epic unit tests. No
implementation, test, specification, plan, authority, or normalized STEP file
was changed. No fixture-only workaround was attempted, and S5 was not started.

Reviewed authority and requirements:

- `docs/superpowers/specs/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md`
- `docs/superpowers/plans/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md`
- `docs/audit/ROTATOR_V2_EPIC_01_INDEPENDENT_FINAL_CRIT_01_REREVIEW.md`
- `projects/rotator_v2/epic_01/authority_manifest.json`
- `projects/rotator_v2/epic_01/candidate_definition.py`

The focused command was:

```text
python -m pytest tests/unit/test_rotator_v2_epic_01_authority.py tests/unit/test_rotator_v2_epic_01_candidate_source_authority.py tests/unit/test_rotator_v2_epic_01_physical_mechanism.py tests/unit/test_rotator_v2_epic_01_candidate_cad.py -q
```

Result: 7 passed, 1 failed. The failure is the S4 inventory test and reports
that the current candidate contains only `motor_AZ` and `motor_EL`, while the
S3 inventory contains 25 physical instances.

## Claim Adjudication

| Claim | Verdict | Evidence |
| --- | --- | --- |
| S1 frozen authority is available | Confirmed | The authority test passes. The manifest freezes the normalized STEP, external spur architecture, 30T/36T transmission, geometry values, transforms, and holds. |
| S2 binds the two trusted motors | Confirmed | `test_rotator_v2_epic_01_candidate_source_authority.py` passes. `build_s2_candidate_fixture()` creates one component specification with the normalized STEP and exactly `motor_AZ` and `motor_EL`. |
| S3 provides the semantic body/joint/pair baseline | Partially confirmed | `build_s3_physical_mechanism()` and its focused tests pass for the declared bodies, two joints, 300 pair bindings, intervals, topology metadata, and keep-out fidelity. Its generated specification registry is only six untyped dictionaries, not a full CAD candidate. |
| S2 candidate is already the complete S4 candidate | Rejected | `candidate_definition.py:268-287` creates only one motor specification and two physical component instances. The S4 test at `test_rotator_v2_epic_01_candidate_cad.py:15-22` fails against the 25-member S3 inventory. |
| Candidate-specific CAD mapping implementation exists | Rejected | The Plan requires `projects/rotator_v2/epic_01/candidate_cad.py`, but that file is absent. The Epic directory contains only `authority_manifest.json` and `candidate_definition.py` apart from cache output. |
| All required representations are currently expressible through the wired candidate path | Rejected | The production service requires a mapping for every candidate physical instance (`cad_realization.py:508-513`). Its exact-generated path delegates only to `compile_generated_part()` (`cad_realization.py:726-767`), whose typed generated vocabulary is shaft, cylindrical hub, and rectangular frame member (`models/generated_part.py:1048-1172`). Its no-generated fallback is limited to a mounting-plate program and a small component-type allowlist (`cad_realization.py:104-109`, `726-767`). The required gear, compound carrier/pad, fork, bridge, plate topology, and keep-out realization are not wired into this candidate path. |
| Required placement derivations exist | Rejected | S3 stores only a small `placement_derivations` metadata dictionary and the S2 fixture stores two target transforms. No `GeneratedPlacementDerivation` records or S4 mapping manifest are present. Request version 2 requires one derivation for every exact-generated mapping (`cad_realization.py:949-1023`). |
| The complete same-body solid oracle has run | Rejected | No Epic `candidate_cad.py` or S4 test implements the required derived physical-solid pair universe, literal declared-interface oracle, direct zero-volume non-interface checks, motor sub-gates, or topology assertions. The prior rereview only accepted this as a future implementation obligation. |
| The three-body/two-joint candidate bridge can currently be supplied to M10-3 | Rejected for S4 completion | `ProductionApplication.evaluate_candidate_multi_joint_m10()` requires a candidate, successful CAD realization, bridge, and request (`application.py:2143-2153`). There is no Epic CAD realization, bridge construction, M10 configuration file, or candidate M10 request in the project directory. |
| Frozen geometry itself is proven impossible | Indeterminate and not claimed | No complete candidate CAD was realized, so no valid FreeCAD/OCCT result exists for the complete candidate. The prior FINAL-CRIT-01 rereview established planning geometry and motor-transform closure, not implementation completion. |

## Required-CAD Matrix

The matrix below is the complete 25-instance S3 physical inventory. The
required fidelity is taken from the accepted S4 obligation: trusted source
geometry for the motors, exact generated geometry for generated/manufactured
candidate constituents, and declared-bounded collision representations for
antenna envelopes and the AZ keep-out. `Absent` means no candidate instance,
mapping, representation identity, placement derivation, or CAD realization was
found in the current project implementation.

| Body | Physical instance | Required representation | Current evidence | Adjudication |
| --- | --- | --- | --- | --- |
| `base_body` | `az_base` | Exact generated/composite base plate | No candidate instance or mapping | Missing |
| `base_body` | `az_carrier` | Exact generated/composite retained-post and station carrier | S3 names one aggregate member; no CAD mapping or separate solid inventory | Missing and under-specified for S4 |
| `base_body` | `az_keep_out` | Declared-bounded collision representation | S3 fidelity string exists only | No realized representation |
| `base_body` | `az_motor_mount` | Exact generated plate with D20/D4.5 topology | S3 role only | Missing |
| `base_body` | `az_pinion` | Exact generated spur gear with D-shaft interface | S3 role only; no Epic gear mapping | Missing |
| `base_body` | `az_support_A` | Exact generated support housing | S3 dimensions are an untyped dictionary | Missing |
| `base_body` | `az_support_B` | Exact generated support housing | S3 dimensions are an untyped dictionary | Missing |
| `base_body` | `motor_AZ` | Trusted normalized STEP geometry | Present in S2 candidate and target-transform fixture | Partial only; no S4 mapping |
| `az_rotating_body` | `az_deck` | Exact generated deck plate | S3 role only | Missing |
| `az_rotating_body` | `az_driven_gear` | Exact generated spur gear | S3 role only; no Epic gear mapping | Missing |
| `az_rotating_body` | `az_hub` | Exact generated cylindrical hub | S3 role only | Missing |
| `az_rotating_body` | `az_shaft` | Exact generated shaft with clear bore | S3 dimensions are an untyped dictionary | Missing |
| `az_rotating_body` | `el_edge_bridge` | Exact generated bridge rail | S3 role only | Missing |
| `az_rotating_body` | `el_fork` | Exact generated/composite two-arm fork | S3 names one aggregate member; no separate arm CAD inventory | Missing and under-specified for S4 |
| `az_rotating_body` | `el_motor_mount` | Exact generated plate with D20/D4.5 topology | S3 role only | Missing |
| `az_rotating_body` | `el_pinion` | Exact generated spur gear with D-shaft interface | S3 role only; no Epic gear mapping | Missing |
| `az_rotating_body` | `el_support_A` | Exact generated support housing | S3 dimensions are an untyped dictionary | Missing |
| `az_rotating_body` | `el_support_B` | Exact generated support housing | S3 dimensions are an untyped dictionary | Missing |
| `az_rotating_body` | `motor_EL` | Trusted normalized STEP geometry with accepted axis transform | Present in S2 candidate and target-transform fixture | Partial only; no S4 mapping |
| `el_payload_body` | `antenna_envelopes` | Declared-bounded collision representation | S3 role only | Missing |
| `el_payload_body` | `carrier_attachment_boss` | Exact generated/composite boss with D50 bore | S3 role only | Missing |
| `el_payload_body` | `el_driven_gear` | Exact generated spur gear | S3 role only; no Epic gear mapping | Missing |
| `el_payload_body` | `el_hub` | Exact generated cylindrical hub | S3 role only | Missing |
| `el_payload_body` | `el_shaft` | Exact generated shaft | S3 dimensions are an untyped dictionary | Missing |
| `el_payload_body` | `rail_and_pad_carrier` | Exact generated/composite rail and five pads | S3 role only; no composite CAD mapping | Missing |

The S3 aggregate IDs also create a direct integration issue. The accepted Spec
requires the S4 physical-solid inventory to expose the three retained AZ posts,
station A, station-B left rail, and the two separate EL fork arms. Current S3
membership exposes those as aggregate `az_carrier` and `el_fork` members. The
current candidate therefore cannot satisfy both the failed inventory equality
test and the required derived solid-pair oracle without an explicit S4
candidate-CAD inventory/representation implementation.

## Production Contract Findings

The existing generic contracts are sufficient primitives for some of the
obligation, but they do not constitute the missing Epic implementation:

- `CandidateCadRealizationRequest` can require complete mapping coverage and
  placement derivations, and `CandidateCadRealizationService` can replay those
  records. This confirms the correct production seam, not that the Epic has
  supplied its inputs.
- The generic generated-part compiler handles only the accepted typed generated
  part classes and their corresponding stock/bore/plate programs. It does not
  provide an Epic-specific spur-gear, compound-solid, fused-body, or
  declared-bounded multi-solid builder through `CandidateCadRealizationService`.
- The low-level CAD and gear modules elsewhere in `src/mechcad_harness` do not
  remove the missing candidate binding, representation manifest, placement
  derivation set, same-body oracle, or three-body M10 bridge. Using them without
  those records would be a fixture-only or contract-bypassing workaround.
- The application entrypoints are present, but they are downstream entrypoints:
  `realize_candidate_cad()` requires a complete candidate and request, while
  `evaluate_candidate_multi_joint_m10()` requires the resulting CAD and bridge.

## Boundary And Next Stage

The correct response under the accepted Plan is to stop at S4. Implementing the
missing candidate expansion, CAD mappings, generated/composite representations,
placement derivations, same-body OCCT oracle, or M10 bridge would be S4
implementation work and is outside this read-only adjudication. No S5 or
mandatory predecessor regression suite was run because the S4 gate is not
complete.

ROTATOR_V2_EPIC_01_S4_PRODUCTION_GAP_CONFIRMED
