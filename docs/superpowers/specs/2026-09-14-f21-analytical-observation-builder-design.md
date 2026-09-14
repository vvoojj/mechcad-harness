# F21 Analytical Observation Builder Design

**Status:** DESIGN ONLY - awaiting human review

## 1. Problem Statement

`ProductionApplication` has two adjacent-but-independent structural workflows
that repeat the same final analytical-observation construction sequence:

1. realize already trusted STEP geometry;
2. resolve the definition's semantic regions against that realization; and
3. construct `CantileverGeometryObservation` and
   `CantileverMaterialObservation` through the existing canonical constructors.

The F21 target is limited to removing repetition in step 3. It must not merge
or weaken the different trust, reload, verification, publication, currentness,
or error semantics that precede or follow construction.

## 2. Current Duplicated Paths

### Path A: Evidence publication reconstruction

`ProductionApplication._publish_structural_analytical_validation`
(`src/mechcad_harness/application.py`) is installed as the composed analytical
validation factory used by `StructuralEvidencePublisher.publish`.

Before construction, this path parses byte-verified mesh content, reads the
source STEP artifact in project scope with expected type and hash, confirms the
composed structural dependencies, obtains the artifact path, realizes geometry,
and resolves regions. It wraps all source-observation work in a broad exception
boundary that raises `ValueError("trusted analytical source observations are
unavailable")`. It returns the validation plus both observations so the
publisher can persist them in `StructuralEvidencePayload`, create `Evidence`,
and freshly verify that Evidence.

### Path B: Direct analytical evaluation

`ProductionApplication.evaluate_structural_analytical_validation`
(`src/mechcad_harness/application.py`) first reloads and compares the durable
execution manifest, revalidates the composed dependencies, reconstructs a
trusted result, validates the supplied result hash, loads trusted mesh bytes,
and performs additional source STEP artifact, manifest-reference, input-binding,
and direct FreeCAD-provenance checks. It then realizes the source artifact and
resolves regions. The same broad source-observation exception boundary is used.

This path deliberately ignores caller-supplied `mesh`, `geometry_observation`,
and `material_observation` values. It returns only a
`StructuralAnalyticalValidationResult`; it does not publish Evidence.

## 3. Field-By-Field Equivalence Analysis

Both paths call the same existing pure constructors with the same positional
inputs, in the same order:

```python
geometry_observation = cantilever_geometry_observation(
    request, definition, realization, region_map,
)
material_observation = cantilever_material_observation(request, definition)
```

The resulting types and fields are as follows.

| Produced type and field | Classification | Source and required behavior |
| --- | --- | --- |
| `CantileverGeometryObservation.project_id` | IDENTICAL_AUTHORITY | `request.source_binding.project_id` |
| `source_revision` | IDENTICAL_AUTHORITY | `request.source_binding.source_revision` |
| `source_state_hash` | IDENTICAL_AUTHORITY | `request.source_binding.source_state_hash` |
| `definition_id` | IDENTICAL_AUTHORITY | `definition.id` |
| `definition_hash` | IDENTICAL_AUTHORITY | bound definition hash after `structural_definition_hash(definition)` validation |
| `geometry_artifact_id` | IDENTICAL_AUTHORITY | `request.source_binding.geometry_artifact_id` |
| `geometry_artifact_hash` | IDENTICAL_AUTHORITY | `request.source_binding.geometry_artifact_hash` |
| `length_mm` | IDENTICAL_AUTHORITY | realized bounding-box `xmax - xmin` |
| `width_mm` | IDENTICAL_AUTHORITY | realized bounding-box `ymax - ymin` |
| `height_mm` | IDENTICAL_AUTHORITY | realized bounding-box `zmax - zmin` |
| `free_end_area_mm2` | IDENTICAL_AUTHORITY | `region_map` entry whose ID is exactly `free` |
| `CantileverMaterialObservation.project_id` through `geometry_artifact_hash` | IDENTICAL_AUTHORITY | same source-binding and definition values as geometry observation |
| `material_identity` | IDENTICAL_AUTHORITY | `definition.material_assignment.material_identity` |
| `elastic_modulus_mpa` | IDENTICAL_AUTHORITY | canonical elastic-modulus property snapshot |
| `poisson_ratio` | IDENTICAL_AUTHORITY | canonical Poisson-ratio property snapshot |
| `material_assignment_id` | OPTIONAL_DIFFERENCE | nullable model field, but both current constructors provide the same assignment ID |
| `elastic_modulus_source_identity` | OPTIONAL_DIFFERENCE | nullable model field, but both current constructors provide the same snapshot source identity |
| `poisson_ratio_source_identity` | OPTIONAL_DIFFERENCE | nullable model field, but both current constructors provide the same snapshot source identity |
| construction order | ORDER_SENSITIVE | geometry observation is built before material observation in both paths; preserve it |

There are no caller-specific fields in either observation. The two constructors
already own their input/hash/geometry/material validation. A construction-only
helper must invoke them exactly once and must not replace their validation with
new derivation.

## 4. Authority and Trust Boundaries

The shared construction inputs are trusted only because each caller establishes
its own preconditions. The proposed helper is not an authority boundary and
must treat every input as already authorized by its caller.

Path A preserves its independently required artifact read and composed-service
trust checks before realization. Its return values become immutable fields in a
durable structural Evidence payload only through `StructuralEvidencePublisher`.

Path B preserves its independently required durable-manifest reload and equality
check, fresh result reconstruction and hash comparison, trusted mesh load, source
STEP binding/reference/direct-provenance checks, and final source-currentness
check. Its caller-supplied observation parameters remain non-authoritative and
ignored.

Backend provenance remains intentionally distinct where the surrounding paths
use direct FreeCAD provenance checks or composed-helper adapter checks. F21
does not move, compare, normalize, or centralize those checks. Structural
provenance verification and artifact/read verification are separate
execution-versus-Evidence layers and remain separate.

M11 handoff revalidation remains outside F21 and must not be collapsed into any
upstream validation. The existing centralized mesh-input hash authority remains
outside the helper. F12 canonical multi-joint verification and F10 retirement
boundaries are unrelated protected surfaces.

## 5. Decision

**Decision: CONSOLIDATE THE CONSTRUCTION-ONLY PAIR.**

The two paths are semantically identical only after the respective callers have
obtained `realization` and `region_map`. At that narrow boundary, extraction is
behavior-preserving: identical constructors, argument ordering, outputs, model
defaults, and exception propagation are retained. The helper is not justified
for any operation before or after those two constructor calls.

## 6. Proposed Private API

Add this private `ProductionApplication` method in a future implementation:

```python
def _build_cantilever_analytical_observations(
    self,
    *,
    request: StructuralAnalysisRequest,
    definition,
    realization,
    region_map,
) -> tuple[CantileverGeometryObservation, CantileverMaterialObservation]:
```

The helper owns exactly these calls, in this order:

1. `cantilever_geometry_observation(request, definition, realization, region_map)`;
2. `cantilever_material_observation(request, definition)`; and
3. returning `(geometry_observation, material_observation)`.

It must not derive fields itself. In particular, it must not calculate bounding
box dimensions, select a region, read material snapshots, manufacture nullable
metadata, substitute defaults, compare hashes, or suppress constructor errors.

It must be private, construction-only, free of I/O, free of reloads, free of
Evidence publication, free of currentness decisions, free of verification
decisions, free of new persistence, and introduce no public API.

## 7. Caller Responsibilities Preserved

`_publish_structural_analytical_validation` retains mesh parsing, STEP artifact
read/type/hash verification, composed dependency validation, geometry
realization, region resolution, its existing source-observation exception
translation, analytical validation, and its three-value return contract.

`evaluate_structural_analytical_validation` retains type checks, request
resolution, durable manifest reload, definition reload, composed dependency
validation, fresh result reconstruction/hash comparison, trusted mesh loading,
STEP artifact/read/binding/provenance/reference checks, geometry realization,
region resolution, its existing source-observation exception translation,
analytical validation, source-currentness assertion, and its validation-only
return contract.

The direct evaluation method continues to ignore caller-supplied observation
snapshots. Neither caller delegates its authority decision to the helper.

## 8. Explicit Non-Goals

F21 does not:

- consolidate structural provenance verification;
- consolidate artifact verification;
- collapse M11 handoff revalidation;
- modify F12 canonical replay;
- revive F10 retired M6B-4C surfaces;
- change M10 schemas or hashes;
- change Evidence ownership;
- create new persistence;
- introduce public APIs;
- refactor unrelated `application.py` code;
- modify `docs/reconstruction/**`;
- alter the already-centralized mesh-input hash authority; or
- unify direct FreeCAD provenance construction with intentionally distinct
  helper-based adapter variants.

## 9. Error Semantics

The low-level existing constructors retain their exact validation errors:
definition-hash mismatch, missing realized bounding box, missing `free` region,
and missing required material snapshots. The helper must not catch, translate,
reorder, or partially return around those errors.

Both application callers retain their existing `try`/`except` boundary around
geometry realization, region resolution, and observation construction. Thus
any exception from the helper remains chained as the current
`ValueError("trusted analytical source observations are unavailable")` in both
paths. Errors raised by each caller before that boundary remain unchanged.

## 10. Provenance and Evidence Invariants

Observation source-binding fields must continue to be taken only from the bound
request/definition and realized geometry/region-map inputs established by the
caller. No caller-provided observation snapshot becomes trusted input.

Path A continues to provide both observations to the publisher, which persists
them only alongside analytical validation and verifies the complete payload.
Path B continues not to publish or persist either observation. Historical
Evidence verification continues to reconstruct analytical checks from persisted
typed observations and byte-verified MSH content without runtime geometry
realization.

## 11. Serialization and Hash Compatibility

The helper returns the same frozen Pydantic model types with the same field
values and optional-field population. It introduces no model, schema-version,
default, ordering, serialization, or persistence change.

Where Path A persists observations, `StructuralEvidencePayload.semantic_hash`
and the enclosing Evidence `output_hash` must remain byte-for-byte compatible
for equivalent inputs. `StructuralAnalyticalValidationResult.validation_hash`,
request hashes, definition hashes, geometry artifact hashes, mesh hashes, and
the existing mesh-input hash authority must be untouched.

There is no dedicated committed golden fixture for these exact observation
constructor calls. Compatibility is nevertheless guarded by model/hash tests,
persisted analytical-validation reconstruction/tamper tests, and M11-4/M11-5
live coverage. An implementation must add focused regression assertions before
claiming compatibility.

## 12. Test Strategy

Future implementation must first add focused unit tests in the existing
production-application test module that prove:

- each caller invokes the private helper only after its own preconditions;
- the helper returns the exact two canonical observation types and preserves
  constructor argument order;
- helper construction failures retain the existing wrapped error message and
  exception chaining at both callers;
- direct evaluation still ignores forged caller observation snapshots;
- publication still persists both observations and produces the same structural
  Evidence semantic hash for a fixed fixture; and
- existing replaced-dependency/source-binding rejection tests still fail closed.

Run the focused unit modules for production application, observation
construction, structural evidence models/verifier, and structural results.
Run the accepted M11-4/M11-5 regression and live gates only when separately
authorized; F21 design itself does not authorize external runtime execution.

## 13. Acceptance Criteria

- Only the two duplicated application-level constructor sequences are changed.
- The helper is private and has exactly the construction-only input/output scope
  described above.
- Both callers retain all current reload, verification, provenance, artifact,
  currentness, exception, return-value, and Evidence responsibilities.
- No models, schemas, hashes, persisted payload shapes, public APIs, or M10/F10/F12
  behavior change.
- Focused tests demonstrate unchanged outputs, failure behavior, forged-input
  rejection, and Evidence serialization/hash compatibility.
- `git diff --check` and affected test commands pass.

## 14. Implementation-Plan Prerequisites

Before an implementation plan may be written, a human reviewer must approve
this design decision and confirm that the scope remains construction-only.
The implementation planner must re-read the then-current `application.py`, the
observation constructors, publisher/verifier payload flow, and focused tests to
detect intervening changes. It must not assume this design remains valid if the
two call sites, trusted inputs, or error boundaries have diverged.

## 15. Risks and Stop Conditions

Stop and return to design review rather than implementing if any current code
inspection finds that either path uses a different observation type, different
constructor input, different field default, additional caller-specific field,
different exception boundary, or different ordering requirement.

Also stop if extracting the helper would move artifact access, durable-manifest
reload, provenance checks, currentness checks, validation, Evidence publication,
or hash derivation into the helper; if it requires a public API or persistence
change; or if fixed-fixture payload hashes change. Any such result changes the
F21 decision to `KEEP_SEPARATE` unless a new, explicitly approved design
supersedes this document.
