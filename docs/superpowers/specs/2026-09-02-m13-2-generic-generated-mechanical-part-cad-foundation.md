# M13-2 Generic Generated Mechanical-Part CAD Foundation

## Status

- Session type: architecture + specification only. No production code, tests,
  plans, M13-3/M13-4 work, or commits were produced in this session.
- Predecessor accepted baseline: `M13_1_SUPPLIED_COMPONENT_NUMERIC_INTERFACE_AUTHORITY_IMPLEMENTED_AND_VERIFIED`
  (commit `f6d8124`, completion report
  `docs/audit/MECHCAD_M13_1_COMPLETION_REPORT.md`).
- Revision: reconciled architecture with final source-binding and
  placement-authority closure. All earlier reconciliation findings are
  resolved, and the remaining trust-boundary issues are closed in this
  revision: layer-independent `DESIGN_SELECTION` bindings (no
  `candidate:design-variable:` strings persisted), removal of the unproven
  cross-layer `specification_hash` assumption, the bounded auxiliary
  `GeneratedAuthorityInput` contract, semantic placement derivation moved out
  of CAD realization, explicit local-to-assembly composition binding the
  specific source physical instance, frame-member attachment-face endpoint
  semantics, exact promotion semantics for the new records, and expanded
  acceptance tests. No architecture decision below is left to the
  implementation-plan author.
- Pre-implementation reconciliation (final revision before implementation):
  four narrow findings closed against repository reality — **P1** rotation
  authority is a scalar angle resolved from an existing scalar
  `DESIGN_SELECTION` record plus an axis from a typed frame reference (free
  quaternion authority explicitly deferred; no record accepts a
  multi-component tuple — see Rotation Authority Resolution); **P2**
  `geometry_definition_identities` is the shared-helper union of every input
  hash and every binding hash (see Geometry Definition Identities); **P3**
  design-variable placement orientation is identity as part of the named
  `accepted-design-variable-placement@1` contract, never a fallback (see
  Source Placement Orientation Contract); **P4** the exact frame-face
  plane-point/outward-normal convention is frozen (see Frame Face
  Semantics). No approved architecture decision was redesigned.
- Gap disposition: **CONFIRMED** (decomposed; see Gap Disposition).
- Dependency decision: **USE EXISTING STACK**. No new third-party dependency;
  build123d is **not** used for M13-2 (see build123d Role).
- Initial exact generated-part scope: solid circular shaft, cylindrical hub /
  sleeve coupling, rectangular frame member. Plate/bracket keeps the existing
  legacy path unchanged (see Plate Scope Decision).
- Bearing decision: **D (deferred)**; trusted purchased bearings remain
  `ImportedCadComponent` (decision A path) when trusted STEP exists (see
  Bearing Decision).
- Source-binding reconciliation model: **Option A** — persisted bindings carry
  only layer-independent semantic locators + value hashes, so the
  `GeneratedPartSpecification` remains byte-identical across promotion (see
  Candidate / Canonical Source Binding).
- Placement authority: semantic `GeneratedPlacementDerivation` records at
  mechanism/physical-instance relation level are the authoritative input;
  candidate CAD realization and `CandidatePlacementOrigin` are downstream
  evidence, never the semantic owner (see Placement Semantic Owner).
- Proposed final marker for the future implementation milestone:
  `M13_2_GENERIC_GENERATED_MECHANICAL_PART_CAD_FOUNDATION_VERIFIED`
  (see Acceptance Criteria).

## Problem

MechCAD can represent candidate physical mechanisms (M12-1), size bounded
revolute-drive realizations (M12-3), evaluate candidate CAD with exact M10
geometry (M12-4), promote selected mechanisms (M12-5), and replay everything
freshly from canonical state (M12-6). M13-1 adds typed, source-bound numeric
shaft/mounting interface authority for supplied STEP components.

What MechCAD still cannot do is turn an authorized physical/mechanical part
specification into deterministic, inspectable **generated** CAD for real
generic mechanical parts — shafts, hubs/couplings, frame members — through the
established generic CAD pipeline:

1. `CadPartProgram` (`src/mechcad_harness/cad_program.py`) has a
   plate-only vocabulary: exactly four operation types — `base_plate`
   (cad_program.py:33), `through_hole` (cad_program.py:46),
   `rectangular_pocket` (cad_program.py:59), `through_slot`
   (cad_program.py:74). There is **no positive cylinder primitive**, no
   transform op, no compound op. A shaft or hub cannot be expressed at all.
2. The candidate generated-CAD path
   (`candidates/cad_realization.py:405-426`) is restricted to component types
   `{fixture, mount, support-mount, driven-body}`
   (cad_realization.py:72) and lowers only mounting plates via
   `compile_mounting_plate`. Any other generated component role
   (`SHAFT`, `HUB_OR_COUPLING`, `ROTATING_MEMBER`, `BEARING`, ...) yields
   `CandidateCadStageReason.UNSUPPORTED_REPRESENTATION`
   (cad_realization.py:406-407).
3. Generated candidate CAD is forced to fidelity
   `DECLARED_BOUNDED_COLLISION_REPRESENTATION`
   (cad_realization.py:170-171). There is no fidelity class that can honestly
   declare *exact deterministic generated geometry*.
4. There is no semantic generated-part model: today a "shaft" is only property
   key/value pairs on a `ComponentSpecificationSnapshot`
   (`shaft.diameter_mm` read at `revolute_drive/calculations.py:654`) plus
   loose design variables, with no typed geometry semantics, no derived
   interfaces, no deterministic interface hashes, and — critically — **no
   per-dimension authority binding** proving that CAD uses the same
   engineering value that was admitted/evaluated elsewhere.
5. Nothing consumes M13-1 supplied interfaces to deterministically place or
   parameterize generated counterpart parts. Grepping `src/` for generated-part
   consumption of `supplied_interface_definitions` returns nothing; M13-1 is an
   authority substrate only (M13-1 completion report, Limitations, line 195).

The result is that M12 candidates must either use trusted imported STEP for
every real part or fall back to plate-like bounded envelopes that cannot
represent a round shaft, a bored hub, or a frame member. M13-2 closes this gap
generically, without creating a second CAD system, and without touching M10,
M11, or M13-3/M13-4 scope.

## Current Repository Capability Audit

Verified against current source (not summaries). For each existing capability:
model / CAD primitive / deterministic compiler / provider-backend / production
caller / candidate path / canonical path / live verification.

### Generic CAD contracts

| Capability | Status | Evidence |
|---|---|---|
| `CadPartProgram` model | exists | `cad_program.py:93`; SAFE_ID validation (line 14); exactly one base op, first (lines 110-112); deterministic `cad_program_hash` (lines 146-148) |
| CAD primitive vocabulary | exists, plate-only | `base_plate`, `through_hole`, `rectangular_pocket`, `through_slot` (cad_program.py:33/46/59/74; mirrored in `cad_manifest.py:14`). Cuts only; no positive cylinder, no transform, no compound; single-solid enforced (`backends/freecad.py:82`, `:251`) |
| FreeCAD part backend | exists, live-verified | `backends/freecad.py:168`; subprocess script execution (`:256-264`); FCStd+STEP published via `ArtifactStore` with `input_hash = cad_program_hash` (`:271-296`); fresh reopen verification (`:298-363`); `mechcad-freecad@2.1`, FreeCAD 1.1.3 detected live (`:126-138`) |
| Mounting-plate compiler | exists, production caller | `cad_compilation.py:179-225` (`compile_mounting_plate`, deterministic feature-ID ordering), service-gated by source binding (`:238-286`); called from `application.py:789-801` |
| Specialized azimuth plate compiler | exists, domain-synthesizer only | `azimuth_mount_plate.py:346-357`; not a generic compiler |
| `CadAssemblyProgram` + `CadRigidTransform` | exists, live-verified | `cad_assembly.py:16-51`; dual registries (parts + imported); hash over canonical constituents (lines 113-132); validation enforces unique definition IDs and unique instance IDs (lines 53-78) but does **not** forbid multiple instances sharing one `part_id`; live mixed assembly verified (M9-3) |
| `ImportedCadComponent` | exists, live-verified | `imported_component.py:29-102`; sha256 + format + revision binding; STEP-only; assembly re-verification (`backends/freecad_assembly.py:146-167`) |
| Imported STEP multi-shape trust | exists | `backends/freecad_assembly.py:217-229` aggregates **all** top-level STEP shapes into one compound; same aggregation in `transient_freecad_measurement.py:260-355` and `structural/geometry.py:53-60`. Generated parts load `source_objects[0].Shape` (`freecad_assembly.py:234-237`) — safe only because part programs are verified single-solid |
| Gear CAD (build123d) | exists, specialized only | `backends/gearworks_cad.py:24-79`; py_gearworks 0.0.18 + build123d 0.11.1 (pinned, `pyproject.toml:17`, `backends/compatibility.py:31-50`); publishes generic STEP `EngineeringArtifact` through `ArtifactStore`; **no** automatic conversion into `ImportedCadComponent`; **no** path into candidate CAD realization |
| Candidate CAD realization (M12-4) | exists | `candidates/cad_realization.py:86-213`; imported path via `geometry_source` -> `resolve_imported_component` (`:371-403`); generated path restricted to plate types (`:405-426`) and bounded fidelity (`:170-171`) |
| Canonical CAD realization (M12-5/6) | exists | `candidates/canonical_cad.py:336-508`; generated plate dims re-derived from accepted design choices then spec properties (`:570-629`), same `_GENERATED_COMPONENT_TYPES` restriction (`:321`) |
| Fidelity classes | exist, two only | `CandidateGeometryFidelity` (`cad_realization.py:499-501`) and `CanonicalGeometryFidelity` (`models/physical_mechanism.py:119-123`): `TRUSTED_SOURCE_GEOMETRY`, `DECLARED_BOUNDED_COLLISION_REPRESENTATION` |
| M10 candidate/canonical evaluation | exists, unchanged by M13-2 | `candidates/m10_evaluation.py:425-444` (full pairwise universe), `candidates/canonical_m10.py:186-205`; fidelity enforcement is **exact enum equality** (`m10_evaluation.py:549-556`: `mapping.fidelity is not fidelity` raises; `canonical_m10.py:884-891`: identical pattern) |

### Physical / authority models

| Capability | Status | Evidence |
|---|---|---|
| `PhysicalComponentInstance` / roles | exists | `candidates/models.py:401-407`; roles include `SHAFT`, `HUB_OR_COUPLING`, `MOUNT_OR_SUPPORT`, `BEARING` (`:389-398`) |
| `ComponentSpecificationSnapshot` | exists | `candidates/models.py:239-386`; properties, `geometry_source`, M13 records (`supplied_reference_frames`/`supplied_interface_definitions`/`geometry_derivation_transforms`, lines 249-251); `interfaces: tuple[str, ...]` with exactly-once listing for M13-1 interfaces (lines 353-354); schema `component-specification@1`/`@2` |
| `CanonicalComponentSpecification` | exists | `models/physical_mechanism.py:255-430`; canonical mirror incl. M13 records; schema `canonical-component-specification@1`/`@2` |
| `CandidateDesignVariable` | exists | `candidates/models.py:564-583`; fields `name`, `value (str\|float\|int\|bool)`, `canonical_path` (optional); **no self-hash** — identity today is the string `candidate:design-variable:{name}` (used at cad_realization.py:467, promotion.py:503) |
| `CanonicalAcceptedDesignChoice` | exists, self-hashed | `models/physical_mechanism.py:443-477`; fields `key`, `value`, `origin`, `provenance`, `source_identities`, `choice_hash`; promotion maps `CandidateDesignVariable` to choice with `choice_key = variable.name`, first dot-segment remapped candidate-to-canonical instance id when it matches (`_canonical_choice`, promotion.py:491-511) |
| `ComponentPropertySnapshot` / `CanonicalComponentProperty` | exist, self-hashed **per layer** | `candidates/models.py:131-161` / `physical_mechanism.py:126-180`; both compute `property_hash` over their own payload with the same canonical-JSON pattern, but the payload projections are separate parallel implementations (differing `schema_version` strings), so cross-layer `property_hash` equality is a derived coincidence, not a guaranteed contract |
| Specification hash parallelism (audit finding) | both sides compute `specification_hash` over `_specification_hash_payload()` (schema-gated full payload minus the hash field) with the same canonical-JSON pattern (`candidates/models.py:254-292,381` / `physical_mechanism.py:277-315,406-411`); promotion copies payload values byte-for-byte, but **no production code or test intentionally guarantees candidate/canonical `specification_hash` equality** — it is a derived parallelism, and M13-2 must not rely on it |
| M13-1 interface/fact/evidence models | **shared classes** | `SuppliedComponentInterfaceDefinition`, `RotationalShaftInterface`, `SuppliedInterfaceFact`, `SuppliedInterfaceEvidence`, `SuppliedComponentReferenceFrame` are single classes in `models/supplied_component_interface.py` used by **both** `ComponentSpecificationSnapshot` and `CanonicalComponentSpecification` (imported at `candidates/models.py:21-27` and by the canonical module); their self-hashes (`interface_hash`, `fact_hash`, `evidence_hash`, `frame_hash`) are computed by one shared function over byte-identical payloads, so they are genuinely layer-stable |
| `MechanicalConnection` | exists | `candidates/models.py:410-445`; kinds incl. `COAXIAL_CONNECTION`, `COUPLING`, `SHAFT_JOURNAL`; meanings incl. `CAD_PLACEMENT_MATING_INTENT` |
| Placement provenance (candidate) | exists | `CandidatePlacementOrigin` (`cad_realization.py:504-528`): `authority` (incl. `"deterministic_derived_relation"`), `input_identities`, `derivation`, `transform`, `origin_hash`; lives only in the candidate CAD realization mapping — **not** a canonical record and **not** a semantic owner |
| Placement records (canonical) | exists | `CanonicalPlacement` (`models/physical_mechanism.py:480-529`): `placement_id`, `instance_id`, `origin` (enum incl. `DETERMINISTIC_RELATION`, physical_mechanism.py:115), `input_identities`, `relation`, x/y/z + quaternion (canonicalized), `placement_hash`. Current promotion projects **only** xyz design-variable placements (`_canonical_placements`, promotion.py:513-545, relation `"accepted-design-variable-placement@1"`); no derived-placement projection exists yet |
| Promotion mapping schema | exists | `_verify_policy` (promotion.py:949-960): `candidate-canonical-mapping@2` iff any spec is `component-specification@2`, else `@1` |
| Promotion classifications | exists | `_expected_classifications` (promotion.py:1112-1184): properties, geometry sources, M13 frames/interfaces/transforms, design variables, physical instances, connections, joint bindings — each with exact identity strings and expected values |
| M12-3 sizing | exists | `revolute_drive/calculations.py:55-73` (`ShaftStaticSizingResult` incl. computed `minimum_diameter_mm`, calculations.py:709); admissibility service `revolute_drive/service.py:683-826`; selected diameter consumed from spec property or design variable `selected-output-shaft-diameter` (`:683-690`); bore compatibility checks only — hub/bearing ODs are **not** sized |
| M12-5 promotion | exists | `candidates/promotion.py:310-444` builds a fresh `CanonicalPhysicalMechanism` from semantics only; specs copied via `_canonical_specification` (`:446-489`); CAD payloads never cross |
| Dependency invalidation | exists | `config/dependencies.yaml:45-49` (`/physical_mechanisms/*` -> continuous-clearance + kinematic-sweep families); `dependency/graph.py:87-168`; promotion invalidation enforcement (`candidates/promotion.py:1540-1559`) |
| M13-1 interface authority | exists | `models/supplied_component_interface.py` (2040 lines): `RotationalShaftInterface` (lines 492-537), `MountingFaceInterface` (578-623), `SuppliedComponentReferenceFrame` (1225-1264), materialization + replay (1619-1996), fail-closed authority gates (683-903) |
| Generated-part semantic model | **missing** | No `GeneratedPart*` model anywhere in `src/` (grep confirmed); M13-1 completion report limitations line 195 |
| M13-1 to generated-part consumption | **missing** | No consumer of `supplied_interface_definitions` for placement/parameterization exists |
| Generated dimension authority binding | **missing** | No mechanism ties a generated numeric field to the admitted/selected value it must equal |
| Instance-level semantic placement derivation | **missing** | No record relates a supplied instance's authoritative placement to a generated counterpart's placement |

## Gap Disposition

**CONFIRMED**, decomposed into seven exact sub-gaps:

- **G1 — CAD primitive gap (model + primitive + compiler + backend).**
  `CadPartProgram` cannot express any positive cylinder. Verified: the
  discriminated union at `cad_program.py:90` contains exactly four op types;
  the FreeCAD backend's `compile_program` (`backends/freecad.py:195-235`) can
  only make a box and cut into it. Disposition: **extend `CadPartProgram`
  minimally** (two new op types, exact coordinate contract below); no parallel
  AST.
- **G2 — candidate generated-CAD routing gap (candidate path).**
  `CandidateCadRealizationService` supports generated CAD only for
  `{fixture, mount, support-mount, driven-body}` plate-like types and only at
  bounded fidelity (`cad_realization.py:72`, `:170-171`, `:405-407`).
  Disposition: extend routing, do not replace (Candidate CAD Integration).
- **G3 — exact-generated fidelity gap (fidelity taxonomy).** No fidelity value
  exists for exact deterministic generated geometry; generated CAD is forced to
  `DECLARED_BOUNDED_COLLISION_REPRESENTATION` (`cad_realization.py:170-171`).
  Disposition: add one fidelity member to the two existing enums; do not
  create a new taxonomy. M10 fidelity checking itself requires no change
  (verified exact-enum-equality; see Fidelity plumbing recheck).
- **G4 — semantic generated-part model gap (semantic owner).** Generated part
  semantics exist only as loose property keys/design variables; there is no
  typed, hashable generated-part specification with deterministic derived
  interfaces. Disposition: add `GeneratedPartSpecification` inside the
  existing specification snapshots (Semantic Physical-Part Model); no parallel
  candidate model.
- **G5 — M13-1 consumption gap.** No production code derives generated-part
  dimensions or placement from authorized M13-1 supplied interfaces.
  Disposition: define an explicit consumption boundary (M13-1 Consumption
  Boundary); reuse M13-1 gates as-is.
- **G6 — generated dimension authority-binding gap (trust boundary).** Even
  with a semantic model, a bare numeric field proves nothing: M12-3 could
  admit a 20 mm shaft while the generated spec silently contains 15 mm — both
  independently hash-valid. Disposition: every generated geometry field
  carries exactly one verifiable authority binding built over
  `GeneratedAuthorityInput` records (Generated Dimension Authority Binding);
  the compiler refuses any field whose binding cannot be verified.
- **G7 — instance-level placement authority gap.** No semantic record relates
  a specific supplied physical instance's authoritative placement (composed
  with its local M13-1 interface frame) to a generated counterpart's
  placement. Disposition: `GeneratedPlacementDerivation` records at
  mechanism/physical-instance relation level (see Placement Semantic Owner).

Not gaps (already supported, must not be rebuilt):

- Plate/bracket semantic compilation: `compile_mounting_plate`
  (`cad_compilation.py:179-225`) is a working generic deterministic compiler.
- Source-bound compilation gating: `CadCompilationService` revision/state-hash
  gating (`cad_compilation.py:238-286`).
- Imported purchased components: full trusted path exists end to end.
- Artifact storage, provenance, fresh reload: `ArtifactStore` +
  `FreeCADBackend._verify_persisted`.
- Placement representation: `CadRigidTransform` +
  `CandidatePlacementOrigin` (candidate) and `CanonicalPlacement`
  (canonical) both exist; only derivation functions and projection are
  missing.
- Canonical reconstruction and promotion: existing flow needs extension, not
  replacement.

## Goals

- G-1. Enable an authorized semantic physical-part specification to be lowered
  deterministically into the **existing** `CadPartProgram` -> FreeCAD ->
  FCStd/STEP -> `ArtifactStore` -> fresh-reload pipeline.
- G-2. Keep the doctrine `semantic physical component != CAD representation !=
  derived artifact`: the semantic part is hashable and understandable without
  executing CAD; `CadPartProgram` and STEP bytes are never canonical authority.
- G-3. Prove, for every generated geometry field, that CAD uses exactly the
  engineering value admitted/evaluated elsewhere (authority binding).
- G-4. Give generated parts typed, deterministic, hash-traceable interfaces
  derived from their own authoritative dimensions — without duplicating the
  M13-1 supplied-evidence taxonomy — and register them in the existing
  interface endpoint contract.
- G-5. Consume M13-1 supplied interfaces as deterministic inputs for generated
  counterpart dimensions and placement, via the existing fail-closed M13-1
  authority gates.
- G-6. Integrate generated parts into M12-4 candidate CAD and M12-5 canonical
  regeneration with preserved physical constituent identity, declared fidelity,
  and existing promotion/invalidation mechanics.
- G-7. Add no new dependency, no second CAD AST, no second backend, no second
  assembly format, no ad-hoc FreeCAD scripts outside the established boundary.
- G-8. Keep the whole capability generic; Rotator V2 is only a validation
  example.

## Non-Goals

- M13-3 (generic multi-joint candidate/canonical bridge) and M13-4 (live
  integration acceptance) — boundaries defined below.
- Rotator V2 implementation, antenna/azimuth/el-specific production names.
- Timing belts, gear strength, bearing life, shaft fatigue, contact mechanics.
- Automatic component selection, automatic mechanism synthesis, optimization.
- Arbitrary CAD sketch solving, general assembly mate solving, tolerance/GD&T,
  fit/interference design, manufacturing process planning, CAM.
- Whole-assembly M11, nonlinear FEA, dynamics.
- Stepped-shaft systems, keyway/D-bore strength, set-screw sizing, spline
  generation (a supplied `d_flat` shaft may *exist* per M13-1, but generated
  D-bores are out of initial scope).
- Sheet-metal systems, structural profile catalogs.
- Any change to M10 algorithms or M11 execution.
- Material selection or material-attached generated geometry (see Material
  Decision).
- Any change to the existing mounting-plate semantic path (see Plate Scope
  Decision).

## Existing CAD Stack

- **FreeCAD 1.1.3** via `discover_freecad()` (`backends/freecad.py:113-123`),
  `MECHCAD_FREECADCMD`/PATH/import; subprocess execution; live version probe
  (`:126-138`); `BackendProvenance` (`backends/models.py:39-47`) recorded on
  every artifact; FCStd/STEP both published and fresh-verified.
- **`CadPartProgram`**: single-solid, single-base, plate-centric subtractive
  program; fixed coordinate system literal
  `lower-left-bottom; +X length, +Y width, +Z thickness`
  (cad_program.py:96); deterministic canonical-JSON SHA-256 hash.
- **`CadAssemblyProgram`**: dual registries + instances with
  `CadRigidTransform` placements; canonical ordering; full-fidelity assembly
  hash.
- **`ArtifactStore`**: immutable artifacts with sha256, revision/state binding,
  project/run scoping; `existing_in_project` / `read_verified_in_project`
  re-verification.
- **build123d 0.11.1 + py_gearworks 0.0.18**: present, pinned, used only by
  `backends/gearworks_cad.py` for gear STEP production.
- **bd_materials 0.2.4**: material property/mass lookup adapter (not CAD).

## Dependency Decision

**USE EXISTING STACK.** No new third-party dependency. Justification:

1. The only missing geometry is a positive cylinder and a subtractive cylinder
   — both are one line each in the existing FreeCAD script compiler
   (`Part.makeCylinder`) inside `backends/freecad.py`, which already has
   provenance, verification, and artifact publication.
2. build123d is already installed but is deliberately **not** used here: it
   would bypass the `CadPartProgram` trust boundary (its `Part` objects are not
   hashable programs) and would create a second geometry path with its own
   determinism risks, for zero capability gain at this scope.
3. No candidate library (CadQuery, SolidPython, trimesh, SpatialMath) offers
   anything the existing stack lacks for shaft/hub/frame geometry.
4. Determinism and provenance are preserved by staying inside the existing
   hashable-program -> FreeCAD-subprocess -> verified-artifact pipeline.

## Semantic Physical-Part Model

New frozen, `extra="forbid"` Pydantic models in a new module
`src/mechcad_harness/models/generated_part.py` (names are new; nothing
parallel to `CadPartProgram` is introduced — the spec *compiles to* it):

- `GeneratedPartSpecification` — tagged union (discriminator
  `part_kind`) over the initial part types below. Semantic owner and hash
  owner of a generated physical part.
- `SolidCircularShaftSpecification` — engineering semantics: `generated_part_id`
  (SAFE_ID, stable definition-local identity), `diameter_mm`, `length_mm`
  (each an authority-bound field, below), `inputs`/`field_bindings` (below),
  and derived `interfaces`.
- `CylindricalHubSpecification` — `generated_part_id`, `outer_diameter_mm`,
  `length_mm`, `bores: tuple[HubBoreSegment, ...]` (min 1) where each
  `HubBoreSegment` is `bore_id` (SAFE_ID, unique within the hub),
  `diameter_mm`, `start_z_mm`, `depth_mm` (explicit axial extent from the
  local origin plane; through-bore = one segment spanning the full length;
  two-bore stepped coupling = two segments from opposite ends), and derived
  `interfaces`. Same convention: origin at the reference end-face center, +Z
  along the hub axis.
- `RectangularFrameMemberSpecification` — `generated_part_id`, `length_mm`,
  `width_mm`, `height_mm`, and derived `interfaces`. Solid rectangular
  member; local frame: origin at a reference corner of the reference end
  face, +X/+Y/+Z along member length/width/height (same base-plate frame
  convention as `BasePlateOperation`).
- `inputs: tuple[GeneratedAuthorityInput, ...]` and
  `field_bindings: tuple[GeneratedPartFieldBinding, ...]` — the authority
  contract for every engineering dimension (next section).
- Plate/bracket parts do **not** get a semantic model variant and do not
  embed generated-part markers: the existing `MountingPlateDesignSpec` /
  `compile_mounting_plate` path is untouched (Plate Scope Decision).

Validation requirements (consistent with house style):

- All dimensions strictly positive, finite, mm-unit semantics by field name;
  reject empty/whitespace IDs (SAFE-ID pattern where IDs name CAD objects);
  `generated_part_id`, `bore_id`, and `input_id` unique within their scope.
- Shaft: no extra features in initial scope (no shoulders, no keyways).
- Hub: every bore segment must lie fully within the stock axial extent
  (`0 <= start_z_mm`, `start_z_mm + depth_mm <= length_mm`), bore diameter
  strictly less than `outer_diameter_mm`; overlapping bore segments rejected
  (deterministic axial-interval check; validation may sort intervals
  internally — ordering semantics are carried by `bore_id`, never by tuple
  position); canonical serialization order is `bore_id` sort order; duplicate
  or duplicate-ID segments rejected.
- Frame member: strictly positive dims; no features in initial scope.
- Every spec, input, binding, relation, and interface carries a self-hash
  (`generated_part_hash`, `input_hash`, `binding_hash`, `interface_hash`)
  computed exactly like `cad_program_hash` / M13-1 self-hashes: canonical
  JSON (`mode="json"`, `sort_keys`, tight separators) -> `sha256:<hex>`,
  excluding only the hash field itself.

The semantic part must remain fully understandable and hashable without
executing CAD: no FreeCAD shape, no build123d part, no STEP bytes, and no
`CadPartProgram` is part of the specification.

## Generated Dimension Authority Binding

A bare valid float is not authority. The authority contract has two levels:
**auxiliary authority inputs** (values that exist for their own sake —
supplied facts, design selections, explicit relation inputs) and **field
bindings** (what ties each generated geometry field to those inputs). This
split is required because deterministic relations consume inputs that are not
themselves generated geometry fields (e.g. a supplied shaft diameter and an
explicit clearance), and placement derivations consume inputs (axial offset,
clocking) that are likewise not geometry fields.

### `GeneratedAuthorityInput` (bounded auxiliary input contract)

```
GeneratedAuthorityInput
    input_id      # SAFE_ID, unique within its owning scope
                  # (spec-level for part inputs; derivation-level for
                  # placement inputs)
    role          # closed per-rule role enum, e.g. "supplied_diameter",
                  # "clearance", "axial_offset", "clocking_angle",
                  # "selected_diameter", "dimension"
    source_kind   # COMPONENT_PROPERTY | DESIGN_SELECTION |
                  # M13_1_INTERFACE_FACT
    locator       # kind-specific, layer-independent semantic locator
                  # (below)
    value         # the bound numeric value (finite float)
    value_hash    # sha256 over the canonical JSON of the value
    input_hash    # self-hash over the above
```

Exact per-kind layer-independent locators (using current repository
semantics; **no `candidate:` identity strings, no instance IDs, no container
hashes are persisted**):

1. **`COMPONENT_PROPERTY`** — `locator = {property_key}`. Resolution scope:
   the properties of the enclosing component specification snapshot
   (candidate: `ComponentSpecificationSnapshot.properties`; canonical:
   `CanonicalComponentSpecification.properties`). Verification: resolve the
   property by key; require `AVAILABLE`, a single normalized value, unit
   `mm`, and value exactly equal to the bound `value` (and `value_hash`
   matches). The property's `property_hash` is checked as **runtime
   provenance** in the resolving stage only — it is not persisted in the
   binding, because candidate and canonical property hashes are computed by
   separate parallel implementations and their cross-layer equality is not a
   guaranteed contract (audit finding above).
2. **`DESIGN_SELECTION`** — `locator = {name_form, selection_key,
   selection_hash}` where `name_form` is a closed enum:
   - `COMPONENT_SCOPED`: `selection_key` is the raw semantic key, e.g.
     `selected-output-shaft-diameter` (no owning-instance prefix).
     Candidate resolution: a `CandidateDesignVariable` with
     `name == selection_key`. Canonical resolution: a
     `CanonicalAcceptedDesignChoice` with `key == selection_key`
     (layer-stable because `_canonical_choice` leaves keys unchanged when the
     first segment is not an owning instance id, promotion.py:497-505).
   - `INSTANCE_SCOPED`: `selection_key` is the selection key *relative to
     the owning physical instance*, restricted to the two
     promotion-remappable alias forms `{instance}.{selection_key}` and
     `{instance}.geometry.{selection_key}` (the `geometry.{instance}.{dim}`
     alias form used by the legacy plate path is excluded from generated-part
     bindings because it does not remap at promotion). Candidate resolution:
     a `CandidateDesignVariable` named `{owning_instance_id}.{selection_key}`
     or `{owning_instance_id}.geometry.{selection_key}`. Canonical
     resolution: a `CanonicalAcceptedDesignChoice` keyed
     `{canonical_instance_id}.{selection_key}` or
     `{canonical_instance_id}.geometry.{selection_key}` (the exact
     `_canonical_choice` remapping). The owning-instance context is supplied
     by the verifier at resolution time; **it is never persisted**.
   `selection_hash` = sha256 over canonical JSON of
   `{name_form, selection_key, value}` — derived only from layer-independent
   data, therefore identical on both sides. Verification: resolve the
   variable/choice; require a numeric value **exactly equal** to the bound
   `value` (and `value_hash` matches). The resolved record's layer-specific
   identity string (`candidate:design-variable:{resolved name}` /
   `CanonicalAcceptedDesignChoice.source_identities[0]`) is checked as
   **runtime/promotion provenance only** — it is never part of the persisted
   binding or of `GeneratedPartSpecification` identity. A definition shared
   by several instances resolves per owning instance; all resolutions must
   agree with the single bound value, else fail closed (this also permits two
   instances resolving the same definition against two *equal* selections,
   while unequal per-instance selections fail closed).
3. **`M13_1_INTERFACE_FACT`** — `locator = {interface_hash, fact_id,
   accepted_evidence_id, value_hash}`. The outer supplying
   `specification_hash` is **not** part of the locator (see M13-1 Cross-Layer
   Locator). Resolution scope: the bounded mechanism/specification set
   available to the verifier (candidate: the candidate's component
   specifications; canonical: the promoted mechanism's component
   specifications). Verification: find active supplied interface definitions
   whose `interface_hash` matches; require at least one match (fail closed if
   none); run the existing `require_authoritatively_consumable_interface` /
   `require_authoritative_fact` gates
   (`models/supplied_component_interface.py:683-903`); require the fact
   `fact_id` with accepted evidence `accepted_evidence_id` whose effective
   value equals the bound `value` (and `value_hash` matches). Because
   `interface_hash` is a self-hash of a **shared model class** (one hash
   function, byte-identical payloads on both sides — audit finding above),
   matching on it is genuinely layer-stable. Multiple matches are
   byte-identical records and therefore carry identical values, so the
   resolved value is unambiguous; zero matches fail closed.
   `source_identity` is never used as a uniqueness substitute.

### `GeneratedPartFieldBinding` (field-level authority)

```
GeneratedPartFieldBinding
    field_slot        # closed slot vocabulary, e.g. "shaft.diameter_mm",
                      # "hub.bore:<bore_id>.diameter_mm"; one binding per
                      # slot, no duplicates
    source            # exactly one of:
                      #   {input_id}                      (direct)
                      #   {rule_id, ordered input_ids}    (relation)
    field_value_hash  # sha256 over the canonical JSON of the field value
    binding_hash      # self-hash over the above
```

- **Direct binding:** the field's value must exactly equal the referenced
  `GeneratedAuthorityInput`'s value (and hashes match).
- **Relation binding:** `rule_id` is from the closed rule registry; the
  ordered `input_ids` reference `GeneratedAuthorityInput` records **by ID,
  never by output field slots**; the rule's required roles and arity are
  validated exactly; input-to-relation references must be acyclic; the pure
  rule function re-evaluated over the resolved input values must equal the
  stored field value (and `field_value_hash` matches).

Closed rule registry (initial scope):

- `hub-bore-from-supplied-shaft@1` — arity 1, role `supplied_diameter`;
  output = the supplied diameter exactly.
- `hub-bore-from-supplied-shaft-with-clearance@1` — arity 2, ordered roles
  `(supplied_diameter, clearance)`; output = supplied diameter + clearance.

Rules:

- Every required generated geometry field has **exactly one** complete
  binding; a field without a binding makes the whole specification
  invalid (construction-time failure — UNRESOLVED AUTHORITY).
- Every binding and input is verified immediately before compilation. **No
  generated CAD compiler may accept a numeric field whose authority binding
  cannot be verified** — verification failure is fail-closed (UNRESOLVED
  AUTHORITY / INTEGRITY FAILURE), never a silent substitution.
- `value_hash` / `field_value_hash` = sha256 over canonical JSON of the
  numeric value (full precision, no rounding). This makes the banned
  scenario impossible: a binding verified against an admitted 20 mm variable
  cannot verify a 15 mm field, because neither the exact-value comparison
  nor the value hash can match.
- No second authority taxonomy is created: inputs reuse
  `ComponentPropertySnapshot` keys, `CandidateDesignVariable` /
  `CanonicalAcceptedDesignChoice` semantic keys, and M13-1
  interface/fact/evidence hashes as they exist today; only the thin
  locator/value envelope is new.

## Candidate / Canonical Source Binding

**Option A is adopted**: persisted bindings carry only layer-independent
semantic locators + value hashes whose representation is identical before and
after promotion.

- No persisted binding field contains a candidate-only identity: no
  `candidate:design-variable:` strings, no candidate or canonical instance
  IDs, no `CandidateDesignVariable` object identity, no outer
  `specification_hash`, no run/temp/run-state references.
  (`INSTANCE_SCOPED` locators store only the instance-relative suffix; the
  resolved full name and the resolved record's identity string exist only in
  verification context and are checked as runtime/promotion provenance.)
- Layer-stability of the persisted locators is by construction:
  - `COMPONENT_PROPERTY` resolves by key inside the enclosing spec (the
    payload is copied byte-for-byte at promotion).
  - `DESIGN_SELECTION` resolves by the `name_form`/`selection_key` rules on
    both sides; `selection_hash` derives only from form + key + value.
  - `M13_1_INTERFACE_FACT` resolves by `interface_hash` of a **shared model
    class** (single hash function, byte-identical payload).
- **What is NOT assumed:** candidate and canonical `specification_hash`
  equality. Both sides compute it over parallel schema-gated payloads with
  the same canonical-JSON pattern (audit finding), but production code does
  not intentionally guarantee cross-layer equality, so no M13-2 contract
  depends on it. (A future regression test may pin the parallel projection as
  an implementation detail; M13-2 correctness never relies on it.)
- Consequences:
  - The complete `GeneratedPartSpecification` — including `inputs` and
    `field_bindings` — remains **byte-identical** across promotion.
  - Fresh canonical reconstruction verifies every generated dimension
    **without** `MechanicalDesignCandidate`, candidate design-variable
    objects, candidate CAD, or old run state: `COMPONENT_PROPERTY` resolves
    inside the canonical spec; `DESIGN_SELECTION` resolves against
    `CanonicalAcceptedDesignChoice` records (by the exact key rules above);
    `M13_1_INTERFACE_FACT` resolves against the promoted mechanism's
    canonical M13-1 records and gates; relations re-evaluate pure rules.
- Promotion adds one completeness check: every input and binding of every
  promoted `GeneratedPartSpecification` must resolve on **both** sides
  (candidate source record -> canonical source record) with identical values,
  and the `M12_3_RESULT` admissibility requirement already enforced by
  `validate_readiness` (promotion.py:778-830) covers the engineering side.
  A binding that fails to resolve on either side fails promotion (UNRESOLVED,
  not silent drop).

## M12-3 Shaft Sizing Binding

Preserved rule: `ShaftStaticSizingResult.minimum_diameter_mm`
(revolute_drive/calculations.py:709) is an admissibility/derived limit. It is
**never** a binding source kind and never automatically becomes the CAD
diameter. Promoting the derived minimum merely because it influenced
admissibility is prohibited.

When a selected shaft diameter was admitted by M12-3 (the admissibility
result requires status `ADMISSIBLE`, promotion.py:778-830), M13-2 proves
`GeneratedPartSpecification.diameter_mm` is exactly the admitted selected
diameter as follows:

- The selected diameter enters the candidate as a `CandidateDesignVariable`
  (today `selected-output-shaft-diameter`, revolute_drive/service.py:683-690)
  or as the shaft spec property `shaft.diameter_mm`.
- The generated shaft's `diameter_mm` field carries a **direct field
  binding** to a `DESIGN_SELECTION` input (`name_form=COMPONENT_SCOPED`,
  `selection_key=selected-output-shaft-diameter`) or a `COMPONENT_PROPERTY`
  input (`property_key=shaft.diameter_mm`) — exactly the value M12-3 read
  for its checks (M12-3 consumes the same property/variable,
  service.py:683-690, calculations.py:654).
- Because the M12-3 admissibility is bound to the same
  candidate/specification hash, and the binding verifies exact value
  equality against that same source, the scenario "M12-3 checks diameter A,
  CAD generates diameter B" cannot construct a verifiable specification.
- Canonical side: the same input resolves against the promoted
  `CanonicalAcceptedDesignChoice` (key `selected-output-shaft-diameter`,
  projected by `_canonical_choice`) — the same admitted value.

## Generated Part Identity

- **Semantic owner:** the `GeneratedPartSpecification`, embedded in the
  enclosing component specification snapshot.
- **Hash owner:** `generated_part_hash(spec)` (covering inputs, bindings,
  interfaces).
- **Definition vs instance (explicit):** `generated_part_id` is a stable
  **definition-local** identity. It is *not* a
  `CandidateCadInstanceMapping.cad_instance_id` and not a
  `CadComponentInstance.instance_id`, and it is **not by itself** the
  assembly-global CAD definition identity (two different component
  specifications may legitimately both contain `generated_part_id = "shaft"`
  with different semantic dimensions). A
  `ComponentSpecificationSnapshot` is a definition snapshot and may be
  referenced by multiple `PhysicalComponentInstance`s; correspondingly one
  compiled `CadPartProgram` may be referenced by multiple
  `CadComponentInstance`s (the `CadAssemblyProgram` validation already
  permits multiple instances sharing one registered `part_id`,
  cad_assembly.py:53-78).
- **CAD definition identity (collision-free, layer-stable):**
  `generated_cad_definition_id(generated_part) = "generated-part-" + <full
  64-hex sha256 of `generated_part_hash`>`. It is a deterministic SAFE_ID
  (`^[A-Za-z][A-Za-z0-9_.-]*$` — satisfied) derived from the **complete**
  semantic hash, never a collision-prone short prefix. Consequences:
  - same `GeneratedPartSpecification` -> same `CadPartProgram.part_id`;
  - same definition reused by two physical instances -> one part
    definition, two instance IDs;
  - **different `GeneratedPartSpecification` -> different
    `CadPartProgram.part_id`, even when both carry the same local
    `generated_part_id`** (distinct definitions can never collide in the
    `CadAssemblyProgram.parts` registry);
  - candidate and canonical compilation derive the exact same CAD
    definition ID from the byte-identical `GeneratedPartSpecification`
    (same `generated_part_hash` -> same `program.part_id`).
  `generated_part_id` remains useful for local semantic IDs (operation IDs,
  interface IDs, frame IDs) but is not assembly-global identity by itself.
- **Embedding point:** a new optional field `generated_part:
  GeneratedPartSpecification | None = None` on both
  `ComponentSpecificationSnapshot` (`candidates/models.py`) and
  `CanonicalComponentSpecification` (`models/physical_mechanism.py`).
  Schema versions bump to `component-specification@3` /
  `canonical-component-specification@3` (exact semantics below). @1/@2
  payloads and their hashes remain byte-identical.
- **Specification hash effect:** `specification_hash` includes the embedded
  spec (it already hashes the whole payload, candidates/models.py:252-292);
  therefore changing a shaft diameter, hub bore, input value, or binding
  changes `specification_hash` -> `PhysicalComponentInstance.specification_hash`
  -> `MechanicalDesignCandidate.candidate_hash`. No separate candidate-identity
  plumbing is needed.
- **No parallel candidate model.** `GeneratedMechanicalPartCandidate` is
  explicitly rejected: the candidate is still a `MechanicalDesignCandidate`;
  the generated part is one component specification within it.
- **CAD request identity:** `CandidateCadRealizationRequest` mappings
  reference physical instance IDs and declare `representation_identity =
  cad_program_hash(compiled_program)` for generated parts (already enforced,
  cad_realization.py:424-425). For a definition shared by two instances,
  both mappings carry the same `representation_identity` and both CAD
  instances reference the same `part_id` with different `instance_id`s and
  (possibly) different placements.
- **Generated artifact identity:** unchanged — `ArtifactStore` artifact IDs +
  sha256 + `input_hash = cad_program_hash(program)`
  (`backends/freecad.py:293`).
- **Must not change identity:** `run_id`, temp paths, FreeCAD object names
  (derived deterministically from operation IDs, `freecad.py:157-161`),
  build123d/FreeCAD runtime objects, artifact creation timestamps,
  `cad_instance_id`.

### Geometry Definition Identities (exact contract)

The `EXACT_GENERATED_GEOMETRY` provenance must truthfully identify the
**geometry-definition dependency set** of the generated specification — not
merely its auxiliary input values. Two generated specifications can consume
the same authority inputs but bind them differently through different field
bindings / deterministic relation rules; their `generated_part_hash` (and
`cad_program_hash`) differ, and the identity set must distinguish the binding
semantics too.

- **Exact definition:** a single shared helper

  ```
  generated_geometry_definition_identities(spec) =
      tuple(sorted(
          {input.input_hash for input in spec.inputs}
          | {binding.binding_hash for binding in spec.field_bindings}
      ))
  ```

  — the canonical ordered (sorted, de-duplicated) union of **every**
  `GeneratedAuthorityInput.input_hash` and **every**
  `GeneratedPartFieldBinding.binding_hash` of the generated specification.
  The **same helper** is used candidate-side (`CandidateCadRealization`
  compilation) and canonical-side (canonical CAD compilation).
- **Where it is enforced:**
  - `CandidateCadRealization` / generated compilation validation: the
    mapping's `geometry_definition_identities` must equal the helper output
    exactly (mirroring the existing trusted/bounded checks,
    cad_realization.py:378, :412-413).
  - canonical CAD validation: identical equality for generated mappings
    (trusted mappings keep `(artifact_id,)` unchanged).
  - evaluation allowed-identity checking (`allowed_geometry_inputs`,
    evaluation.py:346-357): for specifications with
    `generated_part is not None`, the allowed set gains exactly the helper's
    input-hash and binding-hash values.
  - `CandidatePlacementOrigin.provenance`: geometry identities are placed
    **only where actually applicable** — placement-origin provenance carries
    the placement-derivation references (rule, interface hashes, input
    hashes, rotation input hash), never the geometry-definition identity set
    as such.
- **Never** added to fill the tuple: runtime IDs, candidate IDs, artifact
  paths, or outer specification hashes.
- **Mandatory regression:** same `GeneratedAuthorityInput` set + binding
  graph A **must not** verify against the same input set + binding graph B —
  the geometry-definition identity set / validation distinguishes the binding
  semantics (relation vs direct, different clearance rules, different
  targeted fields).

## component-specification@3 Schema Semantics

Exact serialization/validation contract:

- `@1` — unchanged historical payload; validation and hash behavior
  unchanged; must not contain M13 records, coordinate system, or
  `generated_part` (existing @1 rules, candidates/models.py:306-314).
- `@2` — unchanged M13-1 payload; validation and hash behavior unchanged;
  must not contain `generated_part`.
- `@3` — generated-part payload: `generated_part is not None` is **required**
  and all of the following are **required to be empty/None**:
  `geometry_source is None`, `supplied_reference_frames == ()`,
  `supplied_interface_definitions == ()`,
  `geometry_derivation_transforms == ()`.

  Rationale (representation exclusivity): M13-1 supplied authority belongs
  to the **supplied source component**; a generated component refers to that
  authority through `M13_1_INTERFACE_FACT` inputs pointing at the supplying
  component's active interface (resolved by `interface_hash` within the
  bounded mechanism/specification set). One physical component must not
  silently be both imported supplied geometry and generated geometry — the
  routing would be ambiguous (`cad_realization.py:150` checks
  `geometry_source is not None` first). No legitimate combining case exists
  in current architecture, so coexistence is rejected, not merely
  discouraged: a payload violating the exclusivity rule fails validation.
  The canonical `@3` mirror has identical rules
  (`canonical-component-specification@3`).
- Literal `@1`/`@2` JSON/hash compatibility is preserved: the new field is
  additively optional with a default of `None`, and validators for @1/@2
  reject its presence, so existing payload hashes are unchanged (same
  pattern as the M13-1 `@2` bump; golden-hash regression tests required).
- `@3` serialization/hash determinism: `generated_part_hash` and
  `specification_hash` use the established canonical-JSON pattern; @3
  payloads are deterministic and replayable.

## Initial Generated Part Types

Chosen after inspecting existing CAD primitives. Existing capabilities are
reused wherever possible. The exact generated scope is: **shaft, hub / sleeve
coupling, rectangular frame member** (plate/bracket stays on its existing
legacy path — Plate Scope Decision).

### A. Solid circular shaft — included

- **Why needed:** the primary rotating member of any real mechanism; M12-3
  sizes/admits it (`shaft.diameter_mm`, `minimum_diameter_mm`) but no CAD can
  realize it. Cannot be expressed by existing primitives (no positive
  cylinder).
- **Semantic fields (all authority-bound):** `diameter_mm`
  (typically a direct binding to a `DESIGN_SELECTION` input
  `selected-output-shaft-diameter` — see M12-3 binding section — or a
  `COMPONENT_PROPERTY` input `shaft.diameter_mm`), `length_mm`
  (`DESIGN_SELECTION` or `COMPONENT_PROPERTY`).
- **Generated interfaces:** rotational shaft interface (axis = local +Z,
  nominal diameter = `diameter_mm`, usable engagement length = `length_mm`
  measured from the free end — derived rule `generated-shaft-interface@1`),
  local reference frame at the reference end-face center.
- **CAD lowering:** one `cylindrical_stock` op. No features.
- **Existing primitives sufficient:** no — requires the new primitive.

### B. Cylindrical hub / sleeve coupling — included

- **Why needed:** the generic counterpart that connects a supplied motor
  shaft (M13-1 `RotationalShaftInterface`) to a dedicated generated shaft; the
  minimal coupling representation is a bored cylinder.
- **Semantic fields (all authority-bound):** `outer_diameter_mm`
  (`DESIGN_SELECTION` or `COMPONENT_PROPERTY`), `length_mm`
  (`DESIGN_SELECTION` or `COMPONENT_PROPERTY`), one or more bore segments
  (`bore_id`, `diameter_mm`, `start_z_mm`, `depth_mm`). A plain through-bore
  hub is the minimal case; a two-segment stepped bore covers the input/output
  coupling case generically. D-bore, shoulders, set screws, keys: **out of
  scope**.
- **Generated interfaces:** rotational interface per **externally exposed
  bore mouth** (exact mouth semantics below), plus the local reference
  frame. Bore interfaces are deterministically derived
  (`generated-hub-interface@1` rule).
- **CAD lowering:** `cylindrical_stock` + one `axial_bore` op per segment.
- **Existing primitives sufficient:** no — requires the new primitives.

### C. Rectangular frame member — included, minimal

- **Why needed:** supports and moving frames in real mechanisms are often
  rectangular members; the box primitive exists but no semantic spec/compiler
  binds an authorized frame member to it.
- **Semantic fields (all authority-bound):** `length_mm`, `width_mm`,
  `height_mm` (`DESIGN_SELECTION` or `COMPONENT_PROPERTY`). Solid; no
  features.
- **Generated interfaces:** local reference frame (non-endpoint metadata)
  plus six `GeneratedAttachmentFaceInterface` endpoints (exact endpoint
  semantics below; derived rule `generated-frame-faces@1`) so connection
  intent can reference faces without geometry interpretation.
- **CAD lowering:** one `base_plate` op (the existing box primitive; the
  operation is geometrically a rectangular solid and is reused, not
  duplicated).
- **Existing primitives sufficient:** yes — new semantic model + compiler
  only.

## Shaft Contract

- `SolidCircularShaftSpecification`
  - `generated_part_id`: SAFE_ID, stable definition identity.
  - `diameter_mm > 0`, `length_mm > 0` (finite floats), each with exactly one
    field binding over verified inputs.
  - Reference convention (normative): local origin at the center of the
    reference end face; local +Z along the shaft axis pointing into the
    material; the reference end is the engagement-end by default and the
    convention is part of the hash.
  - `interfaces`: exactly one `GeneratedRotationalInterface` (axis point
    `(0,0,0)`, direction `(0,0,1)`, nominal diameter `diameter_mm`, usable
    engagement `length_mm`) and exactly one `GeneratedReferenceFrame`
    (identity orientation, non-endpoint), both hash-sealed and derived by
    rule `generated-shaft-interface@1` over the bound inputs.
- Deterministic hash: any change to an authority-bound dimension changes the
  spec hash; changing run/path/runtime state never does.

## Hub / Coupling Contract

- `CylindricalHubSpecification`
  - `generated_part_id`: SAFE_ID.
  - `outer_diameter_mm > 0`, `length_mm > 0`, each with exactly one field
    binding.
  - `bores`: 1..4 segments; each `bore_id` (SAFE_ID, unique within the hub),
    `diameter_mm > 0`, `diameter_mm < outer_diameter_mm`,
    `start_z_mm >= 0`, `depth_mm > 0`, `start_z_mm + depth_mm <= length_mm`;
    segments must not overlap; canonical order = `bore_id` sort order; every
    bore field carries exactly one field binding addressed by
    `bore:<bore_id>.*` slots.
  - Reference convention: origin at the center of the reference end face
    (z = 0), +Z along the hub axis into the material; bores measured from
    this origin.
  - `interfaces`: one `GeneratedRotationalInterface` per externally exposed
    bore mouth (exact semantics below), plus the reference frame. Derived by
    rule `generated-hub-interface@1`.
- Sleeve coupling usage pattern (generic, not Rotator-specific): two bore
  segments — input bore bound via relation
  `hub-bore-from-supplied-shaft@1` (or the clearance variant) over an
  `M13_1_INTERFACE_FACT` input carrying the authorized supplied shaft
  diameter (plus, for the clearance variant, an explicit authority-bound
  clearance input), and output bore bound to the generated shaft's admitted
  selected diameter — coaxial on the local +Z axis. The coupling relation
  itself is expressed by existing `MechanicalConnection(kind=COUPLING)` /
  `COAXIAL_CONNECTION` records; M13-2 adds no connection semantics.

### Hub bore identity and mouth semantics

- Bore semantics are identified by `bore_id`, never by tuple position.
  Inserting or reordering bores changes only the serialized order (sorted by
  `bore_id`); existing bores' interface identities and derivation slots are
  unchanged.
- Externally exposed mouths (normative; direction sign is engineering
  semantics, not a convention to be assigned blindly):
  - A bore segment touching `z == 0` creates a **NEAR** mouth interface:
    `interface_id = "{generated_part_id}:bore:{bore_id}:near"`, point
    `(0, 0, 0)`, axis direction `+Z` — the direction means **into the bore
    from that mouth**.
  - A bore segment ending at `z == length_mm` creates a **FAR** mouth
    interface: `interface_id = "{generated_part_id}:bore:{bore_id}:far"`,
    point `(0, 0, length_mm)`, axis direction `-Z` — again into the bore from
    that mouth.
  - A through bore (one segment from 0 to `length_mm`) therefore exposes
    **two** mouth interfaces (near/+Z and far/-Z).
  - A completely internal bore segment exposes **no** external mating
    interface.
  - Nominal diameter = segment `diameter_mm`; usable engagement =
    segment `depth_mm`.

### Frame face semantics (exact, frozen)

For `RectangularFrameMemberSpecification` with its local frame (origin at a
reference corner of the reference end face, +X = length direction, +Y = width
direction, +Z = height direction — the same corner-origin convention as
`BasePlateOperation`'s `lower-left-bottom; +X length, +Y width, +Z thickness`
literal) and dimensions `L = length_mm`, `W = width_mm`, `H = height_mm`, the
six `GeneratedAttachmentFaceInterface` records use the **face-center
convention**, frozen exactly (no conflicting already-approved convention
exists in the repository):

| Interface ID | plane_point | outward_normal |
|---|---|---|
| `{generated_part_id}:face:-x` | `(0, W/2, H/2)` | `(-1, 0, 0)` |
| `{generated_part_id}:face:+x` | `(L, W/2, H/2)` | `(+1, 0, 0)` |
| `{generated_part_id}:face:-y` | `(L/2, 0, H/2)` | `(0, -1, 0)` |
| `{generated_part_id}:face:+y` | `(L/2, W, H/2)` | `(0, +1, 0)` |
| `{generated_part_id}:face:-z` | `(L/2, W/2, 0)` | `(0, 0, -1)` |
| `{generated_part_id}:face:+z` | `(L/2, W/2, H)` | `(0, 0, +1)` |

`GeneratedReferenceFrame` remains non-endpoint metadata. Exact hash/replay
tests for these six interfaces are mandatory (interface IDs, plane points,
normals, `interface_hash` determinism, and pure re-derivation equality under
`generated-frame-faces@1`).

## Plate Scope Decision

**The preferred reduction is adopted.** The existing mounting-plate path is
kept unchanged in M13-2:

- `MountingPlateDesignSpec` and `compile_mounting_plate`
  (`cad_compilation.py:46-225`) remain the semantic model and compiler for
  plates/brackets.
- No generated-part plate marker, no plate `GeneratedPartSpecification`
  variant, no `generated-plate-mount@1` interface family, and **no**
  automatic or marker-based `EXACT_GENERATED_GEOMETRY` upgrade for plates are
  introduced. Existing plate/bracket CAD keeps its existing fidelity behavior
  (legacy bounded path; declared per mapping as today).
- The exact generated scope of M13-2 is therefore exactly: shaft, hub / sleeve
  coupling, rectangular frame member. M13-4 can still use an existing bounded
  plate/support if its scenario requires one.
- If a future milestone needs exact generated plates, it must define a real
  typed plate `GeneratedPartSpecification` variant with its own authority
  bindings — not a marker.

## Bearing Decision

**Decision D — deferred — with the existing decision-A path unchanged:**

1. A purchased real bearing with trusted source STEP continues exactly as
   today: `GeometrySourceReference` -> `ImportedCadComponent` with
   `TRUSTED_SOURCE_GEOMETRY` fidelity. No regeneration, ever.
2. M13-2 adds **no** bearing semantic model, no generated bearing geometry,
   and no bearing envelope primitive semantics. A collision-space bearing
   envelope, if a future milestone needs one, must be declared explicitly as
   `DECLARED_BOUNDED_COLLISION_REPRESENTATION` with its own bounded envelope
   specification — and even that is **out of M13-2 scope** (the new
   `cylindrical_stock` primitive could technically serve it later, but no
   bearing-specific semantics are introduced now).
3. M13-2 claims no bearing life, structural support, or stiffness capability.

## Generated Interface Semantics

Generated parts need deterministic interfaces, but they are **derived**, not
supplied. A new minimal model family is introduced (in
`models/generated_part.py`), deliberately mirroring M13-1's *shapes* without
duplicating its evidence taxonomy:

- `GeneratedRotationalInterface` — `interface_id`, `axis_point` (mm vector3),
  `axis_direction` (unit vector3, canonicalized), `nominal_diameter_mm`,
  `usable_engagement_length_mm`, `derivation` (`GeneratedInterfaceDerivation`),
  `interface_hash`.
- `GeneratedAttachmentFaceInterface` — `interface_id`, `plane_point`,
  `outward_normal`, `derivation`, `interface_hash`. Used for the six
  rectangular frame-member faces (interface IDs:
  `{generated_part_id}:face:-x` through `:face:+z`). This is an **active
  interface** (a legal `MechanicalConnection` endpoint), not metadata —
  see the registry rules below.
- `GeneratedReferenceFrame` — `frame_id`, `origin`, `orientation` (unit
  quaternion, canonical sign), `derivation`, `frame_hash`. A frame is
  **non-endpoint metadata**: it is locally resolvable for M13-3 handoff and
  for placement rules, but it is not a `MechanicalConnection` endpoint and is
  not listed in the `interfaces` registry.
- `GeneratedInterfaceDerivation` — `rule: Literal["generated-shaft-interface@1",
  "generated-hub-interface@1", "generated-frame-faces@1"]`, `source_slots`
  (closed slot vocabulary, below), and **no evidence records**: the authority
  of a generated interface *is* the authority of the bound semantic
  dimensions it derives from.

Distinguishing properties versus M13-1:

| Property | M13-1 supplied interface | M13-2 generated interface |
|---|---|---|
| Authority | declared evidence over an external source document | deterministic derivation from authority-bound semantic dimensions |
| Value origin | `SuppliedInterfaceEvidence` (typed availability/authority) | the `GeneratedPartSpecification` fields themselves (each bound) |
| Geometry binding | `GeometryArtifactIdentity` of a trusted STEP | the generated part's spec (no artifact; artifact exists only after lowering) |
| Replay | `MaterializedInterfaceVerifier` over persisted provenance | pure re-derivation from the spec (same rule function) + hash equality |
| Hash | `interface_hash` self-hash | same self-hash pattern |

Rules:

- Interfaces are constructed **only** by the per-variant pure derivation
  functions (no hand-built interfaces); constructors validate that derived
  values equal the rule output (fail closed, same style as M13-1
  self-hash verification).
- Re-derivation is a pure function of the spec — fresh replay is therefore
  trivially covered by spec-hash verification plus a rule re-equality check.

### Active generated interface registry

Generated rotational and attachment-face interfaces are the typed meaning of
the existing `interfaces: tuple[str, ...]` endpoint registry
(`ComponentSpecificationSnapshot.interfaces`,
candidates/models.py:250/353-354, and the canonical mirror) for `@3`
generated components:

- Every active generated `interface_id` (rotational interfaces **and**
  attachment-face interfaces) appears **exactly once** in the enclosing
  specification's `interfaces` tuple.
- All generated interface IDs are unique; interface IDs embed
  `generated_part_id` (+ `bore_id` + mouth side, or face side, where
  applicable), so they are deterministic and collision-free by construction;
  duplicate detection is enforced at validation anyway.
- No collision with any other typed active interface family: by the `@3`
  exclusivity rule the M13-1 families are empty in a generated spec, so the
  generated interfaces are the only active typed family; the exactly-once and
  uniqueness checks are the same checks M13-1 records already undergo
  (candidates/models.py:353-354 pattern).
- `MechanicalConnection` endpoints (`from_interface_id` / `to_interface_id`)
  and `PhysicalComponentInstance.interfaces` resolve **only** through the
  active generated interface collection (rotational + attachment-face) for
  that generated component — connection validation fails closed on an
  unknown interface id.
- `GeneratedReferenceFrame.frame_id` values are deterministic and locally
  resolvable within the spec (single frame per part in initial scope,
  `frame_id = "{generated_part_id}:frame"`), satisfying the future M13-3
  handoff requirement that joint bindings can resolve an
  `axis_frame_reference` without geometry queries. Frames are explicitly
  **not** endpoints and not registry entries.
- Historical/provenance records (none exist for generated parts in M13-2) are
  never active endpoints.

## Derivation Slot Semantics

`GeneratedInterfaceDerivation.source_slots` and
`GeneratedPartFieldBinding.field_slot` use a **closed, variant-specific slot
vocabulary** — not an arbitrary reflection/path language:

- Legal field slots (exhaustive for initial scope):
  - `shaft.diameter_mm`, `shaft.length_mm`
  - `hub.outer_diameter_mm`, `hub.length_mm`,
    `hub.bore:<bore_id>.diameter_mm`, `hub.bore:<bore_id>.start_z_mm`,
    `hub.bore:<bore_id>.depth_mm`
  - `frame.length_mm`, `frame.width_mm`, `frame.height_mm`
- Relations and interface rules reference inputs **by `input_id`**, never by
  output field slots; each rule validates exactly which input roles/arity are
  legal for it; an illegal reference fails validation.
- No arbitrary Python attribute paths, no JSONPath, no list-index paths (the
  `bores[0]` form is banned — see bore identity), no runtime eval, no generic
  object-path interpreter.
- Generated interface replay uses the **same pure derivation function** that
  created the interface; replay equality plus hash verification is the
  integrity check.

## M13-1 Consumption Boundary

M13-2 consumes M13-1; it does not duplicate or modify it.

1. **Reading interfaces.** Generated-part compilation and placement may read
   only interfaces that already pass the existing M13-1 gates:
   `require_authoritatively_consumable_interface` /
   `require_authoritative_fact` (`models/supplied_component_interface.py:683-903`).
   Direct definitions are read as declared facts; materialized definitions are
   read through their persisted provenance. M13-2 adds **no** new evidence
   types, no acceptance logic, no transform math.
2. **Parameterization (dimension input).** An authorized
   `RotationalShaftInterface.nominal_shaft_diameter` may deterministically
   constrain a generated hub's input bore via an `M13_1_INTERFACE_FACT`
   input consumed by a relation rule (`hub-bore-from-supplied-shaft@1`, or
   the `...-with-clearance@1` variant whose second input is an explicit
   authority-bound clearance `DESIGN_SELECTION`). The clearance value is an
   explicit `GeneratedAuthorityInput` record — never a compiler default.
   M13-2 must not infer anything from the STEP; it resolves the
   already-authorized M13-1 interface.
3. **Placement input.** An authorized supplied frame/interface provides the
   target geometry for deterministic placement derivation (next section).
   The derivation binds the supplying interface by `interface_hash` **and**
   the specific source physical instance (see Local-to-Assembly Composition).
4. **Purchased components stay imported.** M13-2 never regenerates a
   purchased motor, gearbox, or bearing to ease assembly. `ImportedCadComponent`
   remains the exact supplied geometry path.
5. **Promotion.** M13-1 records are copied byte-for-byte by
   `_canonical_specification` (`candidates/promotion.py:451-487`); the
   supplying interfaces referenced by `M13_1_INTERFACE_FACT` inputs cross the
   same way, and input-survival verification (Candidate / Canonical Source
   Binding) proves resolution on both sides **without** relying on any outer
   specification-hash equality.

## Design Variable / Derived Value Semantics

Reuses current MechCAD authority doctrine — `CandidateDesignVariable` for
candidate-side selections, `CanonicalAcceptedDesignChoice` after promotion,
M13-1 facts for supplied inputs, `ComponentPropertySnapshot` for declared
component properties. No new status system. Every classification below is
enforced by the corresponding `GeneratedAuthorityInput` source kind.

| Value | Classification | Authority source |
|---|---|---|
| shaft `diameter_mm` | DESIGN SELECTION (or declared property) | `DESIGN_SELECTION` input (e.g. `selected-output-shaft-diameter`, admitted by M12-3 — see M12-3 section) or `COMPONENT_PROPERTY` `shaft.diameter_mm` |
| shaft `length_mm` | DESIGN SELECTION / declared property | `DESIGN_SELECTION` or `COMPONENT_PROPERTY` input |
| hub `outer_diameter_mm` | DESIGN SELECTION / declared property | `DESIGN_SELECTION` or `COMPONENT_PROPERTY` input |
| hub `length_mm` | DESIGN SELECTION / declared property | `DESIGN_SELECTION` or `COMPONENT_PROPERTY` input |
| hub bore `diameter_mm` | DESIGN SELECTION **or** DETERMINISTIC RELATION | direct binding to an input; or relation over an `M13_1_INTERFACE_FACT` input (+ explicit clearance input for the clearance variant) |
| hub bore `start_z_mm` / `depth_mm` | DESIGN SELECTION (coupling segmentation) | explicit inputs |
| frame member dims | DESIGN SELECTION / declared property | explicit inputs |
| bore clearance | DESIGN SELECTION | explicit `GeneratedAuthorityInput` (`role=clearance`) |
| axial placement offset | DESIGN SELECTION | explicit numeric input on the placement derivation (`role=axial_offset`) |
| explicit scalar clocking angle | DESIGN SELECTION | explicit numeric input (`role=clocking_angle`) when a rule states the rotation axis — **no initial M13-2 rule admits this role; reserved for future rules** |
| explicit placement rotation (single-axis clocking) | DESIGN SELECTION | typed `GeneratedPlacementRotationInput`: a scalar angle resolved from an **existing scalar `DESIGN_SELECTION` record** plus an axis taken from a **typed frame reference** — never a caller-supplied tuple. Free quaternion authority is **deferred** (see Rotation Authority Resolution) |
| generated interface values (axis, bore mouth, engagement, faces) | DERIVED | deterministic rule from bound spec dimensions (`GeneratedInterfaceDerivation.source_slots`) |
| placement transforms | DERIVED | deterministic placement derivation from declared inputs (below) |

**Hidden CAD defaults are prevented structurally:** every engineering
dimension requires exactly one complete verified binding over explicit
inputs; the compiler accepts no optional/defaulted geometry parameters;
there are no "reasonable thickness", "support width", or "hole clearance"
defaults anywhere in the lowering path.

**M12-3 relation:** `minimum_diameter_mm` is never a binding source and never
auto-selected; the selected admitted diameter binds per the M12-3 section.

## Deterministic Placement

M13-2 is not a mating solver. Placement is a pure function over explicitly
declared, authority-bound inputs, and the result is always lowered into the
existing `CadRigidTransform` records on both layers.

### Placement Semantic Owner

The semantic owner of a generated placement relation is a new
**instance-specific** record — **not** `CandidateCadRealization` /
`CandidatePlacementOrigin` (which are downstream evidence) and **not**
`GeneratedPartSpecification` (one definition may be used by multiple
instances with different placements):

```
GeneratedPlacementDerivation            (candidate semantic form;
                                         lives at mechanism/physical-instance
                                         relation level, outside the
                                         component specification)
    derivation_id                       # SAFE_ID, unique within the
                                        # derivation set
    rule_id                             # closed registry:
                                        #   coaxial-generated-placement@1
                                        #   frame-generated-placement@1
    source_physical_instance_id         # candidate instance id (candidate form)
    source_interface_ref                # {interface_id, interface_hash}
                                        # of the supplying (supplied)
                                        # interface, resolved within the
                                        # SOURCE instance's specification
    source_frame_ref                    # optional {frame_id, frame_hash}
                                        # for frame-based rules
    source_placement_ref                # exact semantic placement identity
                                        # of the SOURCE instance (below)
    target_physical_instance_id         # candidate instance id of the
                                        # generated part instance
    target_generated_interface_ref      # {interface_id, interface_hash}
                                        # from the target part's spec
    target_generated_frame_ref          # optional {frame_id, frame_hash}
                                        # from the target part's spec
                                        # (frame-based rules)
    inputs                              # ordered NUMERIC
                                        # GeneratedAuthorityInput records
                                        # only (axial offset; no initial
                                        # rule admits a scalar clocking
                                        # angle input)
    rotation                            # typed placement rotation input
                                        # (below); required for
                                        # frame-generated-placement@1,
                                        # forbidden (must be absent) for
                                        # the axisymmetric rule
    derivation_hash                     # self-hash
```

- **Numeric vs reference inputs (strict separation).**
  `GeneratedAuthorityInput` remains bounded to **numeric engineering
  quantities** (finite float value + `value_hash`) — diameters, clearances,
  axial offsets, scalar design selections, scalar clocking angles. It is
  **never** widened into a geometry/`Any` container, and a frame, quaternion,
  or reference direction is **never** represented as a scalar
  `GeneratedAuthorityInput`. Frame/reference inputs are typed structured
  fields of the derivation (`source_interface_ref`, `source_frame_ref`,
  `target_generated_interface_ref`, `target_generated_frame_ref`) plus the
  typed rotation input:
  - `GeneratedPlacementRotationInput` — the exact bounded rotation authority
    contract (Rotation Authority Resolution below): `rotation_id` (SAFE_ID,
    unique within the derivation), `axis_ref` (a typed frame-axis reference,
    **never** a caller-supplied vector), `angle_degrees` (the authoritative
    scalar, resolved from an existing scalar `DESIGN_SELECTION` record),
    `provenance` (the same layer-independent `DESIGN_SELECTION` locator
    semantics as `GeneratedAuthorityInput`: `name_form` + `selection_key` +
    `selection_hash`), `value_hash`, `input_hash`. The rotation is an explicit
    authority-bound design input — never an implicit identity/default, and
    never a free quaternion.
- **Rotation Authority Resolution (exact, closed).** Repository reality is
  that a design selection resolves exactly **one scalar value**:
  `CandidateDesignVariable.value: str | float | int | bool`
  (candidates/models.py:568) and
  `CanonicalAcceptedDesignChoice.value: str | float | int | bool`
  (physical_mechanism.py:445), with promotion copying the scalar verbatim
  (`_canonical_choice`, promotion.py:507). A quaternion or angle-axis tuple
  therefore cannot truthfully resolve from one existing `DESIGN_SELECTION`
  record without an invented encoding (banned) or widening the predecessor
  authority model (banned for M13-2). The adopted resolution is **Option A —
  scalar-angle authority with typed frame axis**:
  - **Persisted representation:** `{rotation_id, axis_ref, angle_degrees,
    provenance(name_form, selection_key, selection_hash), value_hash,
    input_hash}`. No quaternion is persisted as authority. The rotation
    quaternion is **deterministically reconstructed** by the shared pure
    composition function as a rotation about the referenced frame's local
    axis by the resolved angle (normalized via
    `models.quaternion.normalize_quaternion`, canonical sign); the composed
    transform is verified by exact equality at every stage (candidate
    realization, promotion, canonical replay), so the reconstruction is
    provably the same on both layers.
  - **`axis_ref`:** `{frame_role: Literal["source", "target"],
    axis: Literal["+x", "+y", "+z", "-x", "-y", "-z"]}`. It resolves against
    the derivation's already-bound `source_frame_ref` /
    `target_generated_frame_ref` (`frame_role` selects which); the frame's
    `frame_hash` binding is the authority for the axis. A caller-supplied
    axis vector is structurally impossible.
  - **Authority-bearing source record:** candidate — the
    `CandidateDesignVariable` whose resolved name matches the locator rules;
    canonical — the projected `CanonicalAcceptedDesignChoice` (exact
    `_canonical_choice` key remapping rules).
  - **Candidate resolution:** resolve per the shared `DESIGN_SELECTION`
    rules (name form + owning context supplied by the verifier, never
    persisted); require the value to be numeric (not `bool`), finite, and
    **exactly equal** to the persisted `angle_degrees`; recompute
    `value_hash`.
  - **Canonical resolution:** identical rules against
    `CanonicalAcceptedDesignChoice` records; identical exact-equality and
    hash checks.
  - **Hashes:** `selection_hash` = sha256 over canonical JSON of
    `{name_form, selection_key, value}` (identical to the
    `GeneratedAuthorityInput` definition); `value_hash` = sha256 over
    canonical JSON of the numeric angle value (full precision);
    `input_hash` = self-hash over the record excluding only `input_hash`.
  - **Promotion survival rule:** the same dual-side input/binding survival
    verification as every other `DESIGN_SELECTION` input — the locator must
    resolve on both sides to records carrying the identical angle value;
    any failure fails promotion (UNRESOLVED, never a silent drop).
  - **Failure behavior:** unresolvable locator, non-numeric or `bool`
    value, value or hash mismatch, or an `axis_ref` whose frame cannot be
    resolved / whose frame hash mismatches → UNRESOLVED AUTHORITY /
    INVALID PLACEMENT PROVENANCE, fail closed.
  - **Free quaternion authority is explicitly deferred.** No M13-2 record
    accepts a quaternion (or any multi-component tuple) as trusted
    authority. Orientation beyond one authority-bound single-axis rotation
    is expressed only by **chained derivations** (`source_placement_ref`
    kind `derivation`), each contributing exactly one
    `GeneratedPlacementRotationInput`; derivation chaining is acyclic and
    verified.
- **Initial non-axisymmetric rule (exact):** `frame-generated-placement@1`
  consumes the source typed frame reference (`source_frame_ref`), the target
  generated frame reference (`target_generated_frame_ref`), optional explicit
  authority-bound numeric translation offsets (`inputs`, role
  `axial_offset`/`offset`), and exactly one required explicit
  `GeneratedPlacementRotationInput`. There is **no hidden identity
  rotation**: a frame-member placement without an explicit rotation input
  fails validation. No general transform/mating solver is introduced — the
  rule is a closed-form composition of the declared relation only.

- **Carrier and identity (selection-bound):** the candidate placement
  derivation set is a distinct semantic input of the candidate stage,
  persisted **within the candidate CAD realization request** (existing stage
  record; no new store): `CandidateCadRealizationRequest` gains a
  schema-gated `placement_derivations: tuple[GeneratedPlacementDerivation,
  ...]` field at request schema `candidate-cad-realization-request@2`
  (`@1` unchanged byte-for-byte, so legacy request/realization hashes are
  untouched). The realization records
  `placement_derivations_hash` = sha256 over the canonical JSON of the
  derivation-ID-sorted ordered set payload; the request/realization hashes
  cover it, and the existing decision chain binds it transitively:
  `cad_realization_hash` (`CandidateM10EvaluationScope`, m10_evaluation.py:216,
  verified at `:291-294`) -> `CandidateM10Evaluation` ->
  `CandidateSelection.evaluation_hash` / `evaluation_scope_hash`. See
  Selection / Derivation-Set Binding. It is deliberately **not** embedded in
  `MechanicalDesignCandidate`'s existing hashed payload — legacy candidate
  hashes stay intact.
- **Candidate and canonical forms are distinct typed projections** (by
  design — instance IDs legitimately change across the candidate-canonical
  mapping; byte identity is not forced). The candidate form carries candidate
  instance IDs; the canonical form is the
  `CanonicalGeneratedPlacementDerivation` record (below). The rule,
  interface hashes, layer-independent inputs, and rotation inputs are
  identical in both.
- **Data flow (normative):**
  - Candidate CAD: semantic derivation -> pure recomputation of
    `CadRigidTransform` -> stored on `mapping.placement` +
    `CandidatePlacementOrigin(authority="deterministic_derived_relation",
    input_identities=<ordered derivation input/binding references>,
    derivation=<rule id>)`. The origin records the derivation, it does not
    own it.
  - Promotion: verifies the derivation-set binding against the selected
    decision (Selection / Derivation-Set Binding); verifies each candidate
    CAD placement **against** the semantic derivation (recomputed transform
    == stored mapping transform, exactly); then projects the semantic
    relation to canonical IDs -> `CanonicalGeneratedPlacementDerivation`
    (stored on the promoted mechanism) -> result `CanonicalPlacement`.
  - Canonical CAD: `CanonicalGeneratedPlacementDerivation` + canonical
    component/interface/frame records + the source instance's canonical
    placement + canonical-resolved numeric inputs -> recomputes
    `CadRigidTransform` -> verifies the stored `CanonicalPlacement` ->
    assembly placement. Candidate CAD is never consulted.
- Candidate CAD realization is **required evidence** at promotion readiness
  for `@3` candidates, but it is never the source of the semantic rule.

### Clocking rules (no hidden defaults)

- `axisymmetric-zero-clocking@1` — a **deterministic symmetry convention**,
  not an engineering clocking choice: the initial generated shaft and hub
  representations are exactly axisymmetric solids of revolution about their
  local +Z axis, so rotation about the axis is geometrically irrelevant and
  is declared (by the rule) to be zero. Use of this rule is valid **only**
  when the placed generated representation is exactly axisymmetric; the
  derivation function verifies the target part kind (shaft / hub) and refuses
  otherwise.
- If the generated part has any non-axisymmetric semantic feature (frame
  members, or any future D-bore/keyway variant), explicit authoritative
  clocking is **required**, expressed as exactly one typed
  `GeneratedPlacementRotationInput` (Rotation Authority Resolution: scalar
  angle from an existing scalar `DESIGN_SELECTION` record + typed frame
  axis). The numeric `role=clocking_angle` input remains in the closed role
  enum for future rules that state their own rotation axis; **no initial
  M13-2 rule admits it**, so no derivation carries a `clocking_angle` numeric
  input. No implicit identity clocking exists anywhere.

### Local-to-Assembly Composition (exact)

M13-1 shaft/frame coordinates are **component-local**. A supplied interface
alone therefore cannot define assembly geometry. The composition rule is:

```
world_source_pose =
    source_instance_semantic_placement  (authoritative placement record of
                                         the SPECIFIC source physical
                                         instance — see Source Instance
                                         Identity)
    composed with
    local_M13_1_interface_or_frame_pose  (component-local pose from the
                                          shared M13-1 models)

target_instance_world_transform =
    place(rule_id,
          world_source_pose,
          target_local_interface_pose,   (from the target part's spec)
          axial_offset_input,
          clocking)
```

- `place(...)` for `coaxial-generated-placement@1`: align the target local
  rotational axis to the world source axis, apply the explicit axial offset
  along the axis, apply the declared clocking rule. For
  `frame-generated-placement@1`: compose the explicit target-frame relation.
- Both the candidate realization and the canonical replay use **the same
  pure composition function** — identical inputs produce a bit-identical
  canonicalized quaternion.
- No candidate CAD geometry queries; no inference of world coordinates from
  STEP; no FreeCAD/build123d placement decisions.

### Source Instance Identity

Placement provenance binds the **specific source physical instance** and the
**exact semantic placement identity** used for it, because two physical
instances may share one supplied specification (and therefore one
`interface_hash`):

- `source_physical_instance_id` names the instance explicitly.
- `source_placement_ref` names the authoritative semantic placement of that
  instance — one of:
  - `{kind: design_variable_placement}` — the source instance's placement is
    defined by its authority-bound x/y/z design values under the
    translation-only `accepted-design-variable-placement@1` contract, whose
    identity orientation is **part of the named contract** (Source Placement
    Orientation Contract below) (candidate: the `{instance}.placement.{axis}`
    design variables; canonical: the projected `CanonicalPlacement`), or
  - `{kind: derivation, derivation_id}` — the source instance's placement is
    itself the output of another `GeneratedPlacementDerivation` (acyclic
    chaining only).
- The interface hash identifies the *definition*; the instance id + placement
  reference identify the *physical instance*. Both are required. A resolver
  that cannot resolve the exact (instance, placement) pair fails closed.

### Source Placement Orientation Contract (exact; no implicit orientation)

Missing orientation must never silently become an engineering orientation
decision. The exact rule, chosen after inspecting the existing placement
contracts:

- The **existing accepted design-variable placement contract is
  translation-only with identity orientation as part of the named contract** —
  verified, not assumed:
  - candidate: `_placement_error` (cad_realization.py:470-492) expects the
    mapping transform to equal exactly
    `CadRigidTransform(x_mm, y_mm, z_mm)` with no orientation component —
    identity orientation is what the contract *asserts*, unconditionally;
  - canonical: `_canonical_placements` (promotion.py:513-545) constructs
    `CanonicalPlacement(..., relation="accepted-design-variable-placement@1")`
    without an orientation argument, and `CanonicalPlacement` fixes
    `rotation_quaternion = (1, 0, 0, 0)` (physical_mechanism.py:489) — the
    projection itself establishes identity as part of the named relation
    `accepted-design-variable-placement@1`, never as a conditional fallback
    for absent data.
- Therefore, when `source_placement_ref` has kind
  `design_variable_placement`, the identity orientation used in the
  local-to-assembly composition **is the named contract's orientation**, and
  the replay must verify the full contract pose (translation **and**
  orientation) by exact equality.
- A source instance requiring any **non-identity** orientation cannot be
  expressed by `kind=design_variable_placement` (the contract is
  translation-only); it must be placed by a chained
  `GeneratedPlacementDerivation` carrying an explicit
  `GeneratedPlacementRotationInput` (scalar authority + typed frame axis,
  Rotation Authority Resolution). There is no third path and no "unspecified
  orientation" state anywhere in M13-2.
- Regression coverage is mandatory: replay of a design-variable-placement
  source asserts the exact contract pose (identity orientation) and any
  attempt to consume a design-variable placement as an orientation-bearing
  source without a chained derivation fails closed — an orientation not
  established by the accepted placement contract can never silently become
  identity.

### Canonical placement provenance (closed)

The candidate `CandidatePlacementOrigin` is **not** the canonical placement
authority and does not cross the boundary as-is. Fresh canonical replay needs
a durable **structured** semantic locator — not opaque concatenated hashes in
`input_identities` — for the exact source instance, source placement, local
interfaces/frames, rule, and authority inputs. Two records cooperate:

1. **`CanonicalGeneratedPlacementDerivation`** — the canonical semantic
   re-derivation input, projected from the candidate derivation through the
   existing candidate-canonical instance-ID mapping, stored on the promoted
   `CanonicalPhysicalMechanism` (additive, mechanism-schema-gated collection;
   see Promotion Storage):

```
CanonicalGeneratedPlacementDerivation
    derivation_id                       # same id as the candidate derivation
    rule_id                             # same closed registry
    source_canonical_instance_id        # projected canonical instance id
    source_interface_id / source_interface_hash
    source_frame_id / source_frame_hash     (when applicable)
    source_placement_ref                # canonical placement identity of the
                                        # SOURCE instance (below)
    target_canonical_instance_id        # projected canonical instance id
    target_generated_interface_id / hash
    target_generated_frame_id / hash        (when applicable)
    inputs                              # ordered numeric
                                        # GeneratedAuthorityInput records
                                        # (byte-identical, layer-independent)
    rotation                            # typed rotation input
                                        # (byte-identical, layer-independent;
                                        # frame rule only)
    derivation_hash                     # self-hash (payload with canonical IDs)
```

2. **`CanonicalPlacement`** (`models/physical_mechanism.py:480-529`) —
   remains the persisted **result/placement record**. Its projection
   conventions (verified, not assumed):
   - `origin = DETERMINISTIC_RELATION` (existing enum member,
     physical_mechanism.py:115),
   - `relation` = the placement rule id,
   - `input_identities` = the ordered layer-independent references (source
     interface hash, target generated interface hash, derivation input
     binding references) — **provenance summary only**; structured
     resolution always goes through the canonical derivation record,
   - `x_mm/y_mm/z_mm/rotation_quaternion` = the derived transform.

Fresh canonical replay data flow (exact):

```
CanonicalGeneratedPlacementDerivation
  + canonical component/interface/frame records   (promoted specs, resolved
  |                                                by shared-model hashes)
  + canonical source placement                    (CanonicalPlacement of the
  |                                                SOURCE canonical instance —
  |                                                resolved via
  |                                                source_placement_ref)
  + accepted design choices / rotation provenance (numeric resolution)
        |
        v
recomputed CadRigidTransform   (the same pure composition function as the
        |                       candidate side)
        v
verify stored CanonicalPlacement transform   (exact equality; mismatch =
        |                                     INTEGRITY FAILURE)
        v
canonical CAD assembly placement
```

- `source_placement_ref` (canonical form) resolves the exact source
  canonical instance's placement: either its design-variable-projected
  `CanonicalPlacement` (`{kind: design_variable_placement}`) or another
  canonical derivation's placement (`{kind: derivation, derivation_id}`,
  acyclic). The **specific source instance is preserved** through the
  projection: two equal source interface hashes on different source
  instances resolve to the referenced instance only.
- No candidate object, no `CandidatePlacementOrigin`, no candidate CAD
  result, and no candidate derivation object is consulted canonical-side —
  the canonical derivation record plus canonical mechanism records are
  self-sufficient.

## CAD Lowering Architecture

```
authorized GeneratedPartSpecification  (semantic, hashable, CAD-free,
                                       every field bound to verified inputs)
  + GeneratedPlacementDerivation records (semantic, instance-level)
        |
        v
GeneratedPartCompiler (pure, versioned, no defaults;
                       verifies every input/binding first)
        |
        v
CadPartProgram  (existing model + two new op types)
        |
        v
existing FreeCADBackend.generate_program  (subprocess, verified)
        |
        v
ArtifactStore (FCStd + STEP, sha256, revision-bound provenance)
        |
        v
fresh reload verification (existing _verify_persisted)
        |
        v
CandidateCadRealization / CanonicalCadRealization (existing contracts)
```

Compiler responsibilities (exhaustive):

1. verify the semantic spec is complete, self-consistent, and hash-valid,
2. **verify every `GeneratedAuthorityInput` and
   `GeneratedPartFieldBinding`** against the resolution context (refuse any
   unresolvable/mismatched input — fail closed),
3. lower the verified semantic dimensions into deterministic
   `CadPartProgram` operations with stable operation IDs
   (`{generated_part_id}-stock`, `{generated_part_id}-bore-{bore_id}`, ...)
   and the correct coordinate-system literal,
4. derive and seal the typed interfaces,
5. emit provenance inputs (ordered derivation/binding references) for
   placement/geometry provenance.

Compiler must NOT: choose dimensions, select materials, optimize, decide
topology from natural language, or touch FreeCAD.

`CadPartProgram.part_id` = `generated_cad_definition_id(generated_part)` =
`generated-part-{full generated_part_hash hex}` — a collision-free,
layer-stable CAD definition identity derived from the complete semantic hash
(see Generated Part Identity). It is **not** the mapping's
`cad_instance_id` and **not** the local `generated_part_id` alone
(Definition vs Instance). The `CadComponentInstance` carries
`instance_id = mapping.cad_instance_id`, `part_id = program.part_id`.

## CadPartProgram Reuse / Extension

Existing model reused; extended **minimally** with two op types and one exact
coordinate-system contract:

1. `CylindricalStockOperation` — `operation_type: "cylindrical_stock"`,
   `diameter_mm > 0`, `length_mm > 0`. A positive cylinder along +Z with its
   base-face center at the program origin. Valid as a **base** operation.
2. `AxialBoreOperation` — `operation_type: "axial_bore"`, `diameter_mm > 0`,
   `start_z_mm >= 0`, `depth_mm > 0`. A subtractive cylinder along +Z from
   `start_z_mm` to `start_z_mm + depth_mm`, concentric with the program Z
   axis. Valid only on a `cylindrical_stock` base.

Coordinate-system contract (exact, not deferred to implementation):

- The existing plate/base-box coordinate literal remains byte-identical:
  `lower-left-bottom; +X length, +Y width, +Z thickness`.
- The new cylindrical base coordinate literal is:
  `base-center; +Z cylinder-axis`.
- `CadPartProgram.coordinate_system` becomes a bounded `Literal` union of
  exactly these two strings (a version-safe representation change: the plate
  literal and therefore existing plate program hashes/serialization are
  unchanged; the field type widens from a single literal to a two-value
  union).
- Validation couples the coordinate system to the first base operation:
  `BasePlateOperation` -> the plate literal; `CylindricalStockOperation` ->
  the cylinder literal. Mismatch fails validation.
- Existing plate constructors, defaults, serialization, and hashes remain
  byte-identical. `GeneratedPartCompiler` explicitly emits the correct
  coordinate system for its base kind.

Required coordinated changes (all inside the existing files):

- `cad_program.py`: extend `CadOperationValue`; generalize the
  exactly-one-first-base validation to accept `base_plate` **or**
  `cylindrical_stock`; per-base containment validation (bores within stock
  extent and diameter); the coordinate-system coupling above.
- `cad_manifest.py:14`: extend `operation_kind` Literal with the two new
  values.
- `backends/freecad.py` `compile_program`: two new script branches —
  `Part.makeCylinder(diameter/2, length)` for the stock base and
  `shape = shape.cut(Part.makeCylinder(r, depth, FreeCAD.Vector(0, 0, start_z)))`
  for the bore. Verification (`solid_count == 1`, bbox, probes) unchanged and
  now also guards the new bases.
- Program-hash stability: existing plate programs are untouched (new op types
  are additive union members; the plate literal is unchanged); regression
  tests assert old hashes unchanged.

Explicitly **not** added: transforms, boolean-fuse ops, compound ops,
arbitrary sketch ops, multi-solid programs. Multi-body mechanisms remain
assemblies of single-solid components in `CadAssemblyProgram`.

## build123d Role

**Not used for M13-2.** Repository evidence:

- build123d 0.11.1 is installed and pinned solely for the gear path
  (`pyproject.toml:17`, `backends/compatibility.py:31-50`).
- The only build123d geometry code is `backends/gearworks_cad.py:24-79`
  (toothed profiles — genuinely beyond `CadPartProgram`).
- M13-2 geometry (cylinders, bored cylinders, boxes) is fully expressible
  with existing + two new program ops; build123d would add a second geometry
  path whose `Part` objects are not hashable programs, weakening determinism
  and provenance for zero gain.
- Deterministic STEP export via build123d (timestamp `2000-01-01T00:00:00Z`,
  gearworks_cad.py:54) remains a gear-path detail; no M13-2 artifact flows
  through it.
- If a future milestone needs geometry beyond program expressiveness (e.g.
  involute-adjacent profiles), the honest route is the existing gear-path
  pattern (deterministic specialized generator -> trusted STEP artifact), not
  a bypass of `CadPartProgram` for shafts/hubs.

## FreeCAD Backend Role

Unchanged in responsibility; extended in two compile branches only:

- Already supports: box (`Part.makeBox`), cylinder cut, box cut,
  slot cut (box + two cylinder caps fused), quaternion-to-axis-angle
  placement, compounds of imported instances, FCStd save, STEP export,
  manifest embedding, fresh-reopen verification, provenance.
- M13-2 adds: positive `Part.makeCylinder` for `cylindrical_stock`, and the
  `axial_bore` cut branch. Both are covered by the existing verification
  (bbox/solid/`isInside` probes) and published with identical provenance.
- The generated-part assembly path keeps loading `source_objects[0].Shape`
  (`freecad_assembly.py:234-237`) — sound because every generated program is
  verified single-solid. Multi-shape imported behavior (all top-level shapes
  aggregated) is untouched.

## CAD Fidelity

Reuse the M12-4 fidelity model; add exactly one member to each of the two
existing enums:

- `CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY =
  "exact_generated_geometry"` (`candidates/cad_realization.py:499-501`).
- `CanonicalGeometryFidelity.EXACT_GENERATED_GEOMETRY`
  (`models/physical_mechanism.py:119-123`).

**Meaning (bounded):** `EXACT_GENERATED_GEOMETRY` means *exact deterministic
geometry relative to the authoritative bounded semantic
`GeneratedPartSpecification`* — nothing more. It does **not** mean
manufacturing truth, tolerance correctness, as-built geometry, or structural
adequacy. The claim is exactly as strong as the verified authority bindings
behind the dimensions.

Assignment rules (declared per mapping, never inferred):

| Geometry | Fidelity |
|---|---|
| Trusted purchased STEP | `TRUSTED_SOURCE_GEOMETRY` (unchanged) |
| Shaft / hub / frame member compiled from `GeneratedPartSpecification` with verified bindings | `EXACT_GENERATED_GEOMETRY` (required — these specs are exact relative to their bound semantics) |
| Plate/bracket via the legacy mounting-plate path | unchanged existing behavior (bounded; declared per mapping as today) |
| Bearing envelope | out of scope (Bearing Decision) |

Enforcement additions: a mapping with `EXACT_GENERATED_GEOMETRY` must carry
`representation_identity == cad_program_hash(program)`,
`source_geometry_identity is None` (it has no source artifact), and
`geometry_definition_identities` exactly equal to
`generated_geometry_definition_identities(spec)` — the canonical union of
every input hash and every binding hash (Geometry Definition Identities
contract above) — mirroring the existing trusted-source/bounded checks
(`cad_realization.py:554-558`, `:412-413`). No silent upgrade or downgrade
between bounded and exact is permitted.

### Fidelity plumbing recheck (verified)

Current M10 fidelity checking uses **exact enum equality only** — no
hard-coded assumption that only `TRUSTED_SOURCE_GEOMETRY` counts as an exact
usable representation:

- Candidate M10 scope enforcement: `m10_evaluation.py:549-556` —
  `if mapping.fidelity is not fidelity: raise` (generic equality).
- Canonical M10 scope enforcement: `canonical_m10.py:884-891` — identical
  generic-equality pattern.
- Promotion fidelity conversion: `promotion.py:676-681` converts by value
  (`CandidateGeometryFidelity(fidelity.value)` ->
  `CanonicalGeometryFidelity`) — generic; the new member flows through
  unchanged.

The hard-coded two-value branches live only in CAD plumbing, not in M10:

- `cad_realization.py:170-171` — generated components must be bounded
  (requires a member-aware extension for exact generated parts).
- `cad_realization.py:374-375` — trusted requires source geometry
  (unchanged).
- `evaluation.py:330-337` — trusted mappings must carry the source artifact
  identity; non-trusted mappings must not (`elif
  mapping.source_geometry_identity is not None: raise`) — exact-generated
  mappings with `source_geometry_identity is None` already pass this check
  structurally; the branch requires only member-aware review, not logic
  change.
- `canonical_cad.py:250-274` — trusted branch vs generic else-branch that
  already checks `representation_identity == cad_program_hash(part)` for
  generated parts (works for the new member unchanged).

**Classification:** the required enum-handling extensions are
model/plumbing compatibility in `cad_realization.py` (and review of the two
branch sites above) — **not** a new M10 geometric algorithm. M10's models,
evaluation algorithms, pair universes, and enforcement semantics are
unchanged; the accurate statement is "M10 checking logic unchanged; additive
fidelity enum member flows through generic equality checks; candidate-CAD
plumbing branches gain member-aware handling."

## Multi-Solid Semantics

- Every generated part program yields **exactly one solid** (existing
  verification, `backends/freecad.py:251`). Hub with bore = one solid (ring).
  No multi-solid generated programs exist in M13-2.
- A physical component that is conceptually several solids (e.g. a fabricated
  bracket assembly) must be modeled as **several physical components** in the
  mechanism, each with its own specification, CAD instance, and connections.
  Backend iteration order is therefore never load-bearing; the ambiguity
  banned by the post-M10 trust rules cannot arise.
- Imported multi-shape STEP aggregation behavior is unchanged and untouched.

## Candidate CAD Integration

Extends M12-4; does not bypass it:

- `CandidateCadRealizationService._compile_generated`
  (`cad_realization.py:405-426`) gains a routing branch: if the resolved
  `ComponentSpecificationSnapshot` has `generated_part is not None`, compile
  via `GeneratedPartCompiler` (after full input/binding verification);
  require `mapping.fidelity is EXACT_GENERATED_GEOMETRY`; enforce
  `representation_identity == cad_program_hash(program)` as today.
- The `_GENERATED_COMPONENT_TYPES` allowlist (`:72`) continues to gate the
  legacy plate path; specs carrying `generated_part` are routed by the
  presence of the typed spec (the spec kind — shaft/hub/frame — is the
  authority), so `SHAFT`, `HUB_OR_COUPLING`, `MOUNT_OR_SUPPORT`,
  `ROTATING_MEMBER` role instances can now get real generated CAD.
- Mappings, request validation, replay validation
  (`validate_realization`, `:97-122`), pair-universe construction
  (`m10_evaluation.py:425-444`), and identity checks are reused unchanged:
  every generated CAD constituent maps 1:1 back to its physical instance via
  `mapping.physical_instance_id` <-> `mapping.cad_instance_id`.
- **Definition reuse:** two physical instances referencing the same
  specification (same `generated_part_id`) reuse one compiled
  `CadPartProgram` and appear as two `CadComponentInstance`s with distinct
  `instance_id`s and `part_id = program.part_id`. `definition_id !=
  cad_instance_id` is the supported, normal case.
- **Placement:** derived placements for generated parts are computed by the
  realization service **from** the semantic `GeneratedPlacementDerivation`
  records supplied in the request — the service recomputes the transform and
  records it; it never originates the rule.
- Generated exact geometry participates in the complete collision pair
  universe exactly like imported geometry — no pair is special-cased; pair
  dispositions (`CHECK_CLEARANCE`, exclusions) remain the request's declared
  semantics.
- `CandidateCadStageReason` values are reused: a missing/unverifiable
  authority input surfaces as spec-construction or compile-time failure
  (UNRESOLVED AUTHORITY, `GEOMETRY_UNAVAILABLE` at stage level), unsupported
  features as `UNSUPPORTED_REPRESENTATION`.

## M10 Boundary

- **Zero M10 model/algorithm modifications.** Generated parts enter as
  ordinary `CadAssemblyProgram` constituents; M10's exact `common().Volume` /
  `distToShape()` measurements, discrete sweeps, and continuous proofs operate
  on the assembly exactly as for imported/plate constituents today.
- The fidelity-requirement checks (`m10_evaluation.py:549-556`,
  `canonical_m10.py:884-891`) are generic exact-enum-equality checks — the
  new member flows through them unchanged (verified; see Fidelity plumbing
  recheck). The only member-aware code is candidate-CAD plumbing, classified
  as model/plumbing compatibility.
- Continuous-path clearance proofs and discrete sweeps are inherited
  capabilities, not M13-2 deliverables.

## Promotion Impact

### Mapping schema (exact decision)

`_verify_policy` (promotion.py:949-958) currently selects
`candidate-canonical-mapping@2` iff any candidate spec is
`component-specification@2`, else `@1`. The mapping payload itself needs no
structural new fields for `@3` (the mapping already carries
per-specification hashes and id projections; nothing shape-changing is
added). **Exact decision:**

- all `@1` component specs only -> `candidate-canonical-mapping@1`
- ANY `@2` **or** `@3` component specification ->
  `candidate-canonical-mapping@2`

No `candidate-canonical-mapping@3` is introduced: the mapping payload shape
does not change, only the triggering set of specification schema versions.
Implementation extends the existing `has_v2_specification` check to accept
`component-specification@3` as a `@2`-class trigger.

### Promotion classification for the generated semantic records

Two exact classification identities are added to `_expected_classifications`
(promotion.py:1112-1184):

```
candidate:generated-part:{specification_hash}:{generated_part_id}
    -> ACCEPTED_PHYSICAL_FACT, source_value = generated_part_hash

candidate:generated-placement:{derivation_id}
    -> CANONICAL_REDERIVATION_INPUT, source_value = derivation_hash
```

- The generated-part classification is truthful: the complete generated
  semantic record (dimensions, inputs, bindings, interfaces) is an accepted
  physical fact of the design, identified by its self-hash.
  `PROVENANCE_ONLY`/`DO_NOT_PROMOTE` are rejected for it (same policy as
  M13-1 physical facts, promotion.py:1201-1205).
- The placement-derivation classification is the smallest existing truthful
  category: the relation is **re-derivable** from classified inputs plus the
  rule (`CANONICAL_REDERIVATION_INPUT` — the same semantics M13-1 uses for
  accepted transforms, promotion.py:1157-1165). It is projected, not copied
  as a fact, because instance IDs legitimately change.
- The nested `GeneratedAuthorityInput` records do **not** receive
  independent classifications when their actual source records are already
  covered by existing classifications — which the current sweep guarantees:
  `DESIGN_SELECTION` sources are `CandidateDesignVariable`s (classified at
  `candidate:design-variable:{name}`, promotion.py:1166-1168),
  `COMPONENT_PROPERTY` sources are classified properties
  (`candidate:property:{source_identity}:{key}`, `:1127-1138`),
  `M13_1_INTERFACE_FACT` sources are classified supplied interfaces
  (`candidate:supplied-interface:{spec_hash}:{interface_id}`, `:1148-1156`).
  The layer-specific resolved identity strings are checked as provenance
  during promotion (proving candidate record <-> canonical record represent
  the same semantic key/value) but are never part of
  `GeneratedPartSpecification` identity.
- **Promotion completeness MUST verify input/binding survival** (not
  assumed): for every promoted generated part, every input and binding must
  resolve against the candidate source records *and* against the projected
  canonical records with identical values. Any unresolvable or
  value-mismatched input fails promotion with `UNRESOLVED` — never a silent
  drop.

### Promotion storage (exact; no new store)

- **Candidate derivation set:** persisted within the candidate CAD
  realization request (`candidate-cad-realization-request@2`,
  `placement_derivations` field) — an existing stage record; the complete
  ordered payload is identified by `placement_derivations_hash` (sha256 over
  the canonical JSON of the derivation-ID-sorted ordered set payload).
- **`derivation_id` uniqueness:** scoped within the derivation set (unique
  SAFE_IDs inside one set; the set is bound to exactly one candidate CAD
  realization and one promotion).
- **Instance-ID projection:** candidate -> canonical instance IDs use the
  existing `canonical_by_candidate` mapping (`_canonical_choice` /
  `map_instances`, promotion.py:274-308) — the same projection already used
  for placements and connections.
- **Canonical semantic derivation record:** stored on the promoted
  `CanonicalPhysicalMechanism` as a new additive, mechanism-schema-gated
  collection `generated_placement_derivations:
  tuple[CanonicalGeneratedPlacementDerivation, ...]` (empty/default for
  mechanisms without generated placements, so existing promoted mechanism
  hashes are unchanged; non-empty requires the new mechanism schema version,
  same pattern as the specification `@3` bump). `CanonicalPlacement` remains
  the persisted result record; the canonical derivation record is the
  re-derivation input. No new store is created.

### What crosses promotion

The `CanonicalComponentSpecification` (with embedded byte-identical
`GeneratedPartSpecification`), accepted design choices (via the existing
design-variable projection), canonical placements and their semantic
re-derivation inputs (projected `CanonicalGeneratedPlacementDerivation`
records), connections, joint bindings, and M13-1 records — **never** CAD
artifacts, never candidate CAD state, never the candidate derivation
records themselves (only their verified canonical projections cross).

### Selection / Derivation-Set Binding (exact)

The placement derivation set is semantic design authority; promotion must not
substitute derivation set B after a candidate was selected/evaluated with set
A. The binding uses the **existing decision chain** — no legacy
`MechanicalDesignCandidate` hash is modified:

```
GeneratedPlacementDerivationSet (ordered, derivation-ID-sorted)
    -> placement_derivations_hash
    -> bound into CandidateCadRealizationRequest@2 / realization identity
    -> covered by cad_realization_hash (CandidateM10EvaluationScope,
       m10_evaluation.py:216, verified :291-294)
    -> covered by CandidateM10Evaluation
    -> covered by CandidateSelection (evaluation_hash, evaluation_scope_hash,
       selection_hash)
    -> verified at promotion readiness
```

Promotion readiness for a `@3` candidate must prove:

```
supplied placement derivation set hash
    == placement_derivations_hash bound to the CAD realization referenced by
       the selected evaluation's scope
    == the derivation set the evaluation was computed from
```

Changing the derivation set after selection fails promotion closed
(`UNRESOLVED` / INTEGRITY FAILURE), as does supplying a derivation set that
was never evaluated. Legacy candidates (no M13-2 derivations, request
schema `@1`) keep their existing hashes and pass unchanged.

### Placement verification and projection at promotion

Promotion readiness for a `@3` candidate requires (a) the semantic placement
derivation set (bound per the previous subsection) and (b) the candidate CAD
realization as **evidence**:

1. verify the derivation-set binding (Selection / Derivation-Set Binding),
2. verify every derivation's inputs resolve and are classified,
3. recompute each derivation's transform from its semantic inputs and
   require exact equality with the candidate CAD mapping placement
   (inconsistent CAD placement fails promotion),
4. project each derivation to `CanonicalGeneratedPlacementDerivation`
   (canonical instance IDs via the existing `canonical_by_candidate`
   mapping) and to its result `CanonicalPlacement` per the exact
   conventions of the Placement Semantic Owner section.

## Fresh Canonical Reconstruction

Supported by construction:

- New application process + `DesignState` N+1 (promoted mechanism embedded in
  `physical_mechanisms`) + trusted external supplied artifacts (unchanged
  requirement) -> `reconstruct()` loads and revalidates state
  (`canonical_mechanism.py:188-263`), byte-verifies supplied STEP artifacts
  (`:314-346`), replays materialized M13-1 interfaces (`:348-382`).
- The embedded `GeneratedPartSpecification` needs **no** external artifact:
  semantic dimensions are promoted state, every input resolves against
  canonical records only (`CanonicalAcceptedDesignChoice`, canonical
  component properties, canonical M13-1 interfaces resolved by shared-model
  hashes, pure rules), and the compiler is pure. No candidate object, no
  candidate design-variable object, no previous build123d/FreeCAD document,
  no old temp STEP, no Markdown input is consulted.
- Placement derivations replay from canonical records only:
  `CanonicalGeneratedPlacementDerivation` (stored on the promoted mechanism)
  + canonical component/interface/frame records + the source instance's
  canonical `CanonicalPlacement` + accepted choices/rotation provenance —
  recomputed transforms are verified against the stored `CanonicalPlacement`
  records (Placement Semantic Owner section). No candidate CAD or candidate
  derivation object is needed after promotion.
- The FreeCAD execution remains a fresh subprocess
  (`TRANSIENT_MEASUREMENT_EXECUTION_MODE = "freecadcmd-subprocess"`,
  `analysis_provenance.py:14`; part backend `backends/freecad.py:256-264`).

## Dependency / Invalidation

No M13-specific invalidation infrastructure:

- **Candidate side:** semantic changes (shaft diameter, bore, input values,
  bindings) change `specification_hash` -> `candidate_hash` -> a *new*
  candidate; placement derivation changes change the derivation set hash ->
  new CAD request identity; previous candidate CAD/M10 results bind to the
  old identities and are never reused. This is the existing candidate
  identity mechanism — nothing to build.
- **Promotion path:** promotion adds the mechanism at
  `/physical_mechanisms/{id}`; the existing rule
  `/physical_mechanisms/* -> analysis.continuous_clearance_proof,
  analysis.kinematic_sweep` (`config/dependencies.yaml:45-49`) fires exactly
  once per promotion, and promotion enforcement already requires the
  invalidation record (`promotion.py:1540-1559`).
- **Changes that invalidate** generated CAD / candidate CAD / M10 /
  canonical CAD+M10: generated-part dimension changes, input/binding changes
  (part of the spec hash), generated-interface definition changes (functions
  of dimensions, so covered), source supplied-interface hash changes
  (change the supplying spec payload), source supplied-frame hash changes
  (same), geometry materialization changes (same), placement derivation
  changes (derivation set hash -> new CAD request + new promotion
  classification value), physical connection/placement changes (change
  realization hash / placement provenance, caught by
  `_validate_request_input_identities` and `_validate_placement_provenance`).
- **Canonical in-place dimension edits** of a promoted generated part are out
  of M13-2 scope: promoted mechanisms are modified only through new change
  proposals that re-add/re-derive the mechanism, which re-fires the existing
  rule. (Note for implementers: the `/physical_mechanisms/*` pattern matches
  one path segment; deep in-place edits under a mechanism path would require
  a rule extension — recorded here as a documented boundary, not M13-2 work.)

## Artifact / Provenance Semantics

- Generated artifacts: identical to existing generated plate artifacts —
  `ArtifactStore.publish` with `input_hash = cad_program_hash(program)`,
  `BackendProvenance` (freecad, live version), `EngineeringArtifact`
  sha256/size/revision binding (`backends/freecad.py:271-296`).
- Provenance surface (typed, hashed, minimal):
  - `generated_part_hash` embedded in spec -> candidate/canonical state hash,
  - per-input `GeneratedAuthorityInput` (source kind, layer-independent
    locator, value hash, `input_hash`),
  - per-field `GeneratedPartFieldBinding` (`binding_hash`),
  - `GeneratedInterfaceDerivation` (rule + closed source slots) inside each
    interface,
  - `GeneratedPlacementDerivation` records (`derivation_hash`) bound into
    the CAD request and promotion inputs,
  - compiler identity constant `generated-part-compiler@1` recorded in the
    realization payloads (mirroring `COMPILER_VERSION`,
    `cad_compilation.py:23`).
- Artifact != authority: STEP/FCStd remain derived artifacts bound to the
  program hash; the semantic spec (with its verified bindings) and the
  semantic placement derivations remain the authority.

## Failure Semantics

Reuses existing categories; new failures are classified, never swallowed:

| Failure | Category | Mechanism |
|---|---|---|
| Missing binding / non-authoritative dimension | UNRESOLVED AUTHORITY | spec model construction fails (`GeneratedPartSpecification` completeness + exactly-one-binding rule); at CAD stage surfaces as `GEOMETRY_UNAVAILABLE` (`cad_realization.py:727`) |
| Input/binding verification failure (source value != bound value, unresolvable source, ambiguous M13-1 resolution) | UNRESOLVED AUTHORITY / INTEGRITY FAILURE | compile-time verification, fail closed |
| M12-3-admitted value differs from generated value | prevented structurally | exact-value + `value_hash` verification against the same variable/choice M12-3 consumed |
| Unequal per-instance selections against a shared definition | INTEGRITY FAILURE | per-owning-instance resolution must agree with the single bound value |
| Relation cycle / illegal input role or arity | INVALID SEMANTIC MODEL | relation validation, fail closed |
| Unsupported feature (e.g. requested D-bore, spline) | UNSUPPORTED | `UNSUPPORTED_REPRESENTATION` (`cad_realization.py:728`); never silently replaced (e.g. no round-bore substitution) |
| Invalid semantic model (bore outside stock, overlapping bores, non-positive dim, duplicate bore_id) | INVALID SEMANTIC MODEL | Pydantic validation at construction; fail closed |
| `@3` exclusivity violation (geometry_source or M13 records alongside generated_part) | INVALID SEMANTIC MODEL | schema validation; fail closed |
| Deterministic CAD compilation failure | COMPILATION FAILURE | compiler exception wrapped as `CandidateCadIntegrityError` (same as today, `cad_realization.py:422-423`) |
| FreeCAD crash / timeout | OPERATIONAL FAILURE | existing backend error hierarchy (`backends/errors.py:1-22`) |
| Wrong generated artifact hash on reload | INTEGRITY FAILURE | existing `ArtifactStore` verification + `_verify_persisted` |
| Stale candidate/canonical CAD | STALE/INTEGRITY | existing request/realization hash checks (`cad_realization.py:103-118`) and freshness (`dependency/storage.py:88-130`) |
| Candidate CAD placement inconsistent with semantic derivation | INTEGRITY FAILURE | promotion verification (recomputed != stored mapping transform) |
| Placement derivation set substituted after selection (set B vs evaluated set A) | INTEGRITY FAILURE / UNRESOLVED | promotion readiness derivation-set binding check |
| Placement replay mismatch canonical-side | INTEGRITY FAILURE | recomputed transform != stored `CanonicalPlacement` transform |
| Source instance/placement reference unresolvable or aliased | INVALID PLACEMENT PROVENANCE | exact (instance, placement) resolution, fail closed |
| Placement inputs missing/not authoritative | INVALID PLACEMENT PROVENANCE | `INVALID_PLACEMENT_PROVENANCE` (`cad_realization.py:729`) |
| Non-axisymmetric part placed with `axisymmetric-zero-clocking@1` | INVALID PLACEMENT PROVENANCE | clocking-rule applicability check, fail closed |
| Promotion input/binding survival failure | UNRESOLVED | promotion completeness check (UNRESOLVED, never silent drop) |
| M10 collision witness on generated geometry | ENGINEERING RESULT | existing M10/M12 semantics (`COLLISION_WITNESS` -> infeasible candidate / `ENGINEERING_VIOLATION` at promotion, `promotion.py:1983-1992`) |
| M13-1 interface not authorized for consumption | UNRESOLVED AUTHORITY | existing M13-1 gates (`supplied_component_interface.py:683-903`) |

## Backward Compatibility

- Existing `CadPartProgram` plate programs: hashes, validation, manifests,
  and backend output unchanged (additive union members; plate coordinate
  literal unchanged; regression tests required).
- `component-specification@1`/`@2` and canonical `@1`/`@2` payloads: hash
  and validation behavior unchanged; `@3` introduced only for
  generated-part carriers; @1/@2 validators reject `generated_part`
  presence.
- `MechanicalDesignCandidate` payload/hashes: unchanged — the placement
  derivation set is carried in the CAD realization request at schema
  `candidate-cad-realization-request@2` (`@1` byte-unchanged), not on the
  candidate payload.
- Fidelity enums: additive member; existing persisted fidelity values and
  checks unchanged; promotion mapping schema stays `@1`/`@2` (trigger set
  extended).
- `_GENERATED_COMPONENT_TYPES` legacy routing: unchanged for specs without
  `generated_part`.
- M12-3, M10, M11, M13-1: no behavioral change (M10 fidelity plumbing
  qualification per Fidelity plumbing recheck).

## Material Decision

**Material reference is removed from the initial `GeneratedPartSpecification`
variants.** M13-2 geometry requires no material; no `material_reference`
field is added to the shaft/hub/frame specs.

- Existing component-property/material authority remains the correct separate
  place for material facts: a generated component's specification snapshot
  may still carry a `ComponentPropertySnapshot` (e.g. a material property)
  through the existing property authority — that is outside the generated
  geometry model and outside M13-2 scope.
- M13-2 does not silently select a material and does not require one to
  generate geometry.
- No new material-reference contract is invented. If a future milestone has a
  genuine immediate consumer, it must reuse an existing exact generic
  material-reference type and define its hash/authority behavior explicitly.

## Test Strategy

Future implementation tests (not written in this session):

**A. Semantic model tests** (`tests/unit/test_m13_2_generated_part_models.py`)
- valid shaft / hub / frame member round-trips; deterministic
  `generated_part_hash` (same payload -> same hash; field-order
  insensitive); invalid dimensions (non-positive, non-finite); bore
  containment/overlap rejection; duplicate `bore_id` rejection;
  exactly-one-binding-per-field enforcement (missing binding rejected);
  schema @1/@2 golden JSON/hash compatibility preserved, @3
  required-with/without `generated_part`; @3 exclusivity (geometry_source /
  M13 records alongside generated_part rejected); @3 serialization/hash
  determinism.

**B. Hub/coupling tests**
- through-bore minimal hub; two-segment stepped coupling; D-bore rejected as
  unsupported; bore/OD/length hash sensitivity; bore IDs stable under input
  ordering (reordering input tuples does not change identities, only
  canonical order); through bore creates near/+Z and far/-Z interfaces;
  internal bore creates no external mouth interface.

**C. Frame member tests**
- lowering to box program; `generated-frame-faces@1` correctness; six
  attachment-face interfaces registered exactly once; faces usable as
  connection endpoints; frames are non-endpoint metadata (not in
  `interfaces`); **exact face convention tests**: each of the six interfaces
  has exactly the frozen `plane_point` / `outward_normal` from the Frame Face
  Semantics table, deterministic `interface_hash`, and pure replay equality.

**D. Deterministic lowering tests**
- same semantic spec -> identical `CadPartProgram` (and identical
  `cad_program_hash`) across constructions; stable operation IDs; compiler
  version constant recorded; cylindrical program uses the exact
  `base-center; +Z cylinder-axis` coordinate-system literal; existing plate
  program hash unchanged (golden).

**E. Authority binding tests**
- generated shaft CAD dimension equals its bound admitted design value
  (compile after binding verification);
- changing the source design value without changing the generated value
  fails binding verification;
- changing the generated value without changing the source binding fails;
- M12-3-admitted diameter binds exactly (the "20 admitted / 15 generated"
  scenario is impossible);
- M13-1-derived hub bore reproduces the exact accepted fact/rule
  (interface hash + fact/evidence identities + gates);
- relation has auxiliary supplied-diameter + clearance inputs; changing the
  clearance changes the bore result and hash; missing relation input fails
  closed; relation cycle rejected;
- `COMPONENT_SCOPED` vs `INSTANCE_SCOPED` resolution rules, including the
  canonical key remapping; **persisted `INSTANCE_SCOPED` bindings contain no
  candidate instance id** (and no `candidate:`-prefixed string anywhere in
  the persisted binding); **binding bytes are identical candidate-side and
  canonical-side** (golden); two instances may resolve the same definition
  against two equal selections; unequal per-instance selections fail closed;
- M13-1 fact locator survives the candidate-to-canonical crossing **without
  relying on any outer specification_hash equality** (explicit test with
  differing outer container hashes if the parallelism is absent).
- **geometry-definition identity distinguishes binding semantics:** two
  generated specifications with the **same** `GeneratedAuthorityInput` set
  but different binding graphs (e.g. direct binding vs
  `hub-bore-from-supplied-shaft-with-clearance@1` over the same inputs, or
  the same relation targeted at different field slots) produce **different**
  `generated_geometry_definition_identities` sets, and the candidate/canonical
  validation accepts only the exact helper output for the mapped spec.

**F. No-hidden-defaults tests**
- compiler rejects specs with any unbound field; grep-level/architectural
  assertion that no default geometry constants exist in the compiler;
  clearance requires an explicit input record; placement offset/clocking
  require explicit input records; placement requires a declared clocking
  rule; non-axisymmetric placement cannot use implicit zero clocking.

**G. Exact generated artifact tests with real FreeCAD** (live-marked, like
M9/M12-6)
- shaft program -> FreeCAD FCStd/STEP; volume/bbox match analytic values
  (pi r^2 L etc.); hub ring volume = stock - bore; fresh-reopen verification
  passes.

**H. Fresh STEP reload tests**
- generated STEP re-imported in a separate process; solid count = 1;
  bbox/placement equality to 1e-6.

**I. Identity tests**
- physical instance <-> CAD instance mapping 1:1 for generated parts;
  representation identity = program hash; one generated definition reused by
  two physical/CAD instances (two instances, one program, distinct
  instance_ids, shared part_id); definition ID != CAD instance ID supported;
  candidate hash sensitivity to spec/binding field changes; insensitivity to
  run/temp/runtime inputs and to `cad_instance_id`.

**J. Candidate CAD integration tests**
- mixed candidate: imported motor + generated hub + generated shaft ->
  realization succeeds; plate-legacy path unchanged; fidelity enforcement
  (exact required for generated_part specs; bounded plates unchanged);
  `geometry_source + generated_part` dual representation rejected;
  **candidate CAD placement equals the semantic derivation's recomputed
  transform**; the placement derivation exists independently of
  `CandidateCadRealization` (derivable/verifiable without it).

**K. M10 use without modification tests**
- generated-part candidates run the existing candidate M10 evaluation
  unchanged; pair universe complete; no M10 source changes (asserted by
  existing M10 regression suite).

**L. Promotion tests**
- `@3` -> truthful mapping schema (`candidate-canonical-mapping@2`); missing
  `candidate:generated-part:{spec_hash}:{generated_part_id}` or
  `candidate:generated-placement:{derivation_id}` classification fails
  promotion; input/binding survival verified on both sides (unresolvable or
  value-mismatched input fails); spec crosses byte-identical (golden);
  promotion **rejects candidate CAD placement inconsistent with the semantic
  derivation**; CAD artifacts not promoted.

**M. Fresh canonical regeneration tests**
- fresh canonical generated dimensions verify without candidate object /
  candidate design variables / candidate CAD; **canonical placement
  recomputes without candidate CAD** (source instance canonical placement +
  canonical M13-1 frame + accepted choices only); canonical program hash
  equals candidate program hash for identical semantics (definition identity
  preserved); canonical M10 re-verification passes.

**N. Invalidation tests**
- promotion fires the existing invalidation; candidate semantic change
  produces a new candidate identity; placement-derivation change produces a
  new CAD request identity; freshness checks bind correctly.

**O. Legacy regressions**
- full existing suite (M8-M13-1) green; plate program hashes unchanged;
  `@1`/`@2` specification hashes unchanged; `MechanicalDesignCandidate`
  hashes unchanged.

**P. Imported purchased component remains `ImportedCadComponent`**
- a bearing/motor with trusted STEP never routes to the generated compiler;
  geometry-source routing precedence verified.

**Q. Multi-shape imported behavior unchanged**
- all-top-level-shape aggregation regressions stay green
  (`test_m10_multi_shape_*` family).

**R. Interface registry tests**
- generated interface IDs resolve through the existing `interfaces` registry
  (exactly-once, uniqueness); connection endpoints resolve only through the
  active generated interface collection (rotational + attachment-face);
  unknown interface id fails closed; frame IDs locally resolvable and
  explicitly non-endpoint.

**S. Placement composition tests**
- source local M13-1 frame composes with the explicit source instance
  placement into the world source pose (pure-function oracle);
  **two identical supplied motors share the same `interface_hash` but have
  different instance placements -> the generated placement resolves to the
  explicitly referenced motor instance and cannot silently use the other
  one**; unresolvable/aliased (instance, placement) pairs fail closed;
  chained derivations are acyclic.
- **orientation-contract regression:** replay of a
  `design_variable_placement` source asserts the exact
  `accepted-design-variable-placement@1` contract pose (translation +
  contract identity orientation) by full-transform equality; a
  non-identity-oriented source cannot be expressed through
  `design_variable_placement` and requires a chained derivation — no
  orientation outside the named contract ever silently becomes identity.

**T. Identity and canonical placement closure tests**
- **two different specs with the same local `generated_part_id = "shaft"`
  -> different `CadPartProgram.part_id`** (no registry collision);
- same generated definition reused twice -> same part definition + distinct
  instance IDs; same spec -> same `part_id`;
- candidate/canonical same `generated_part_hash` -> same
  `CadPartProgram.part_id`;
- **canonical placement replay retains exact source instance identity**:
  two equal source interface hashes on different source instances ->
  canonical replay uses the selected source instance only;
- **source placement reference survives candidate->canonical projection**
  (canonical derivation record resolves the source canonical placement);
- **selected decision binds the exact placement-derivation-set hash**:
  candidate evaluated/selected with derivation set A + promotion supplied
  set B -> reject; same set A -> pass; the hash participates in the
  decision/promotion semantic identity chain;
- legacy candidates without M13-2 derivations retain existing
  request/realization/candidate hashes (`@1` goldens);
- **`GeneratedAuthorityInput` remains scalar/numeric** (a frame/quaternion
  value is rejected as an input value);
- **rotation authority is scalar-angle only:** the
  `GeneratedPlacementRotationInput` angle resolves through an existing scalar
  `DESIGN_SELECTION` record (candidate variable / canonical choice, exact
  value + hash equality), the axis resolves through the typed frame
  reference, and **no record accepts a free quaternion or multi-component
  tuple** (free quaternion authority explicitly deferred);
- **`geometry_definition_identities` distinguish binding graphs** (same
  inputs + binding graph A != same inputs + binding graph B; see the
  Geometry Definition Identities contract);
- frame/reference clocking is represented by typed placement references and
  the typed rotation input, not fake float values;
- **frame member placement replays canonically with no hidden orientation
  default** (missing rotation input fails validation; explicit rotation
  replays identically candidate/canonical).

## Future M13-3 Handoff

M13-2 does not implement the generic multi-joint M12-to-M10 bridge. Handoff
boundary guaranteed by M13-2:

- Every generated physical part keeps its stable
  `instance_id` / `specification_hash` / role / interfaces on the physical
  realization — the exact records `JointPhysicalRealizationBinding`
  (`candidates/models.py:448-458`) and `CanonicalJointPhysicalBinding`
  reference. M13-3 can bind a joint to a physical shaft instance (and its
  `axis_frame_reference`) without interpreting geometry.
- Generated rotational interfaces expose typed axis point/direction in the
  part's local frame with locally resolvable `frame_id`s — M13-3 can compose
  these with placement transforms to obtain world-frame joint axes purely
  from records, without geometry queries.
- No M10 changes; no kinematic model changes.

## Future M13-4 Acceptance Handoff

M13-2 is designed so M13-4 can later prove (without executing it here):

imported supplied gearmotor + M13-1 authoritative shaft/mount interfaces +
generated coupling + generated shaft + existing bounded plate/support
geometry (legacy path) -> candidate CAD -> exact FreeCAD artifact -> M10
collision evaluation -> promotion -> fresh canonical CAD/M10.

Requirements M13-2 deliberately satisfies for this: complete generated-part
semantics with verified authority bindings, instance-level semantic
placement derivations consuming M13-1 interfaces, candidate/M10 integration,
promotion round trip, fresh reconstruction. M13-4 defines its own scenario,
environment, and live acceptance evidence.

## Rotator V2 Validation Example

Validation example only; **no Rotator-specific names or abstractions enter
production** (no `az_shaft`, `5840_mount`, `rotator_hub`, etc.):

- Supplied gearmotor STEP with M13-1 `RotationalShaftInterface`
  (diameter d_m, axis frame) and `MountingFaceInterface` (hole pattern),
  realized as a specific physical instance with an authoritative placement.
- Generated sleeve coupling: `CylindricalHubSpecification` with input bore
  bound by relation `hub-bore-from-supplied-shaft@1` over the authorized
  supplied shaft diameter, output bore bound to the generated shaft's
  admitted selected diameter, OD/length as authority-bound design
  selections.
- Generated shaft: `SolidCircularShaftSpecification` with diameter bound to
  the admitted selected value (explicit selection admitted against M12-3
  `minimum_diameter_mm`; the derived minimum is never auto-selected).
- Supports: existing plate path (legacy) and/or
  `RectangularFrameMemberSpecification`.
- Placements: `GeneratedPlacementDerivation` records — coaxial alignment of
  coupling bores to the *specific* gearmotor instance's world shaft axis
  (source instance placement composed with the local interface frame) with
  explicit authority-bound axial offsets and `axisymmetric-zero-clocking@1`
  (valid — axisymmetric parts); frame placements with explicit authoritative
  rotations.

The same capability applies unchanged to any other mechanism (conveyor
drive, gimbal, pump mount).

## Remaining Capability Boundaries

After M13-2 it is still impossible to:

- generate arbitrary mechanical parts (only the bounded initial family);
- generate stepped shafts, keyways/D-bores, splines, threads, gears via this
  path (gears remain on the existing specialized path);
- generate plates through the generated-part model (legacy plate path only);
- run tolerance/GD&T, fit design, or manufacturing planning;
- claim manufacturing truth, as-built accuracy, tolerance correctness,
  bearing life, structural adequacy, fatigue, or safety from
  `EXACT_GENERATED_GEOMETRY` (it is exact only relative to the bound
  semantic spec);
- verify multi-joint mechanism motion (M13-3 future) or certify a
  configuration-space region (M10 retains its existing boundaries);
- synthesize or select mechanisms automatically;
- solve mates or accept inferred geometry;
- run whole-assembly FEA or nonlinear analysis.

## Proposed Implementation Surface

Minimal; all inside existing patterns. **No files are edited in this
session.**

New files:

- `src/mechcad_harness/models/generated_part.py` —
  `GeneratedPartSpecification` union, per-variant specs, `HubBoreSegment`
  (with `bore_id`), `GeneratedAuthorityInput` (source kinds +
  layer-independent locators + roles), `GeneratedPartFieldBinding` (direct +
  relation forms, rule registry `hub-bore-from-supplied-shaft@1` /
  `...-with-clearance@1`), `GeneratedRotationalInterface` /
  `GeneratedAttachmentFaceInterface` / `GeneratedReferenceFrame`,
  `GeneratedInterfaceDerivation`, `generated_part_hash` / `input_hash` /
  `binding_hash` / `selection_hash` functions, closed slot vocabulary, pure
  interface derivation rules, pure relation evaluation (acyclic), input and
  binding verification functions.
- `src/mechcad_harness/models/generated_placement.py` (or a section of the
  module above) — `GeneratedPlacementDerivation` (candidate semantic form),
  derivation-set container + `placement_derivations_hash`, typed
  `GeneratedPlacementRotationInput`, pure `place(...)` composition and
  clocking rules, `CanonicalGeneratedPlacementDerivation` projection.
- `src/mechcad_harness/generated_part_cad.py` (or extend
  `cad_compilation.py` — same layer; both options are the existing compiler
  module family) — `GeneratedPartCompiler` with mandatory input/binding
  verification and `generated_cad_definition_id` derivation,
  `GENERATED_PART_COMPILER_VERSION = "generated-part-compiler@1"`.
- `tests/unit/test_m13_2_generated_part_models.py`
- `tests/unit/test_m13_2_generated_part_bindings.py`
- `tests/unit/test_m13_2_generated_part_cad.py`
- `tests/unit/test_m13_2_placement_derivations.py`
- `tests/unit/test_m13_2_candidate_cad_integration.py`
- `tests/unit/test_m13_2_m13_1_consumption.py`
- `tests/unit/test_m13_2_promotion_canonical_roundtrip.py`
- live acceptance test file (M13-2 acceptance, mirroring M9/M12-6 style).

Modified files (bounded):

- `src/mechcad_harness/cad_program.py` — two new op types + base-kind
  generalization + two-literal coordinate-system contract (hash-stable for
  existing plate programs).
- `src/mechcad_harness/cad_manifest.py` — `operation_kind` Literal +2.
- `src/mechcad_harness/backends/freecad.py` — two compile branches.
- `src/mechcad_harness/candidates/models.py` — `generated_part` field +
  schema `@3` + exclusivity validation on `ComponentSpecificationSnapshot`.
- `src/mechcad_harness/models/physical_mechanism.py` — same on
  `CanonicalComponentSpecification`; `CanonicalGeometryFidelity` +1 member;
  `CanonicalGeneratedPlacementDerivation` model + additive schema-gated
  `generated_placement_derivations` collection on
  `CanonicalPhysicalMechanism`.
- `src/mechcad_harness/candidates/cad_realization.py` —
  `CandidateGeometryFidelity` +1 member; `_compile_generated` routing +
  input/binding verification; placement recomputation **from** the semantic
  derivation set; `CandidateCadRealizationRequest` schema `@2` carrying
  `placement_derivations` + `placement_derivations_hash` (`@1`
  byte-unchanged); shared-definition instance handling (program `part_id` =
  `generated_cad_definition_id`); placement-derivation acceptance in the
  request.
- `src/mechcad_harness/candidates/evaluation.py` — member-aware review of
  the trusted/bounded identity branches (model/plumbing compatibility).
- `src/mechcad_harness/candidates/canonical_cad.py` — generated-part
  routing; input/binding verification canonical-side; placement replay
  against `CanonicalGeneratedPlacementDerivation` + `CanonicalPlacement`.
- `src/mechcad_harness/candidates/promotion.py` — mapping-schema trigger
  extension (`@3` -> mapping@2); `candidate:generated-part:{...}` and
  `candidate:generated-placement:{...}` classifications; input/binding
  survival verification; derivation-set binding verification (supplied set
  hash == selected/evaluated set hash); placement verification (CAD vs
  semantic derivation) + projection to canonical instance IDs;
  `_canonical_placements` extension.
- `src/mechcad_harness/candidates/promotion_models.py` — classification
  plumbing for the two new identities; placement derivation set as a
  promotion input record (no payload shape change to the mapping).
- `src/mechcad_harness/candidates/canonical_mechanism.py` — reconstruction
  input/binding verification; canonical placement-derivation replay.
- `src/mechcad_harness/candidates/__init__.py` /
  `src/mechcad_harness/models/__init__.py` — exports.

Existing models/compilers reused unchanged: `CadPartProgram` hashing,
`compile_mounting_plate` + `CadCompilationService` (untouched legacy plate
path), `ImportedCadComponent`, `CadAssemblyProgram`, `CadRigidTransform`,
`CandidatePlacementOrigin` (downstream evidence only), `CanonicalPlacement`
(fields reused with documented conventions), `FreeCADBackend`
verification/publication, `ArtifactStore`, `MechanicalConnection`,
`CandidateDesignVariable` / `CanonicalAcceptedDesignChoice`, dependency
engine, entire M13-1 module (shared model family — consumed, not modified),
M10 module (no changes).

Rejected surfaces (explicitly): `GeneratedPartStore`, `GeometryStore`,
second CAD AST, second FreeCAD backend, second assembly format,
`GeneratedMechanicalPartCandidate`, ad-hoc FreeCAD scripts, new dependency,
`candidate-canonical-mapping@3`, plate generated-part variant/marker,
material-reference contract, generic path interpreter, new authority
taxonomy. If implementation reveals the need for widespread unrelated CAD
refactoring, the design must be reconsidered per the constraint above.

## Acceptance Criteria

Eventual M13-2 implementation acceptance (bounded, live):

1. **Semantic authority:** a `GeneratedPartSpecification` (shaft, hub, frame
   member) constructs only from complete authority-bound dimensions; hashes
   are deterministic; invalid/incomplete/unbound specs fail closed with
   UNRESOLVED-AUTHORITY-class failures.
2. **Binding proof:** for at least one shaft, the compiled CAD diameter is
   proven identical to the M12-3-admitted selected value via binding
   verification (both directions of mismatch fail closed); for at least one
   hub bore, an accepted M13-1 supplied fact determines the value
   deterministically through an explicit relation with an explicit clearance
   input when used.
3. **Deterministic lowering:** identical specs compile to identical
   `CadPartProgram`s (hash-equal) with no hidden defaults; existing plate
   program hashes are unchanged; cylindrical programs carry the exact
   `base-center; +Z cylinder-axis` literal.
4. **Real geometry:** at least one shaft and one bored hub are realized
   through the existing FreeCAD backend into verified FCStd/STEP; fresh
   reload in a separate process verifies solid count, bbox, and analytic
   volume within tolerance.
5. **Candidate integration:** a candidate containing generated parts (plus at
   least one imported component) realizes candidate CAD through the existing
   M12-4 service with correct physical-to-CAD identity mapping — including a
   definition reused by two instances with distinct instance IDs — exact
   fidelity declarations, and a complete M10 pair universe — without any M10
   model/algorithm change.
6. **Registry integration:** generated interface IDs (rotational +
   attachment-face) resolve through the existing `interfaces` endpoint
   registry; connection endpoints validate against the active generated
   interface collection.
7. **Placement authority:** placements come from semantic
   `GeneratedPlacementDerivation` records (instance-specific, source
   instance + local interface composition; typed reference/rotation inputs);
   candidate CAD placement equals the semantic recomputation; the selected
   decision binds the exact derivation-set hash (substitution after
   selection fails); a promotion with inconsistent candidate CAD placement
   fails; canonical placement recomputes from canonical records only via
   `CanonicalGeneratedPlacementDerivation`.
8. **Promotion round trip:** the semantic generated-part data crosses
   promotion byte-identically under `candidate-canonical-mapping@2` with the
   exact `candidate:generated-part:{spec_hash}:{generated_part_id}`
   (ACCEPTED_PHYSICAL_FACT) and
   `candidate:generated-placement:{derivation_id}`
   (CANONICAL_REDERIVATION_INPUT) classifications and verified input/binding
   survival on both sides — without relying on outer specification-hash
   equality; canonical placement derivations are projected onto the promoted
   mechanism (schema-gated collection); CAD artifacts are not promoted.
9. **Fresh canonical regeneration:** a fresh canonical process verifies every
   generated dimension and every placement relation from promoted semantic
   state alone (no candidate objects) and regenerates equivalent canonical
   CAD (definition identity preserved -> program hash equality for identical
   semantics); canonical M10 re-verification completes.
10. **No forbidden behavior:** no geometry recognition, no hidden CAD
    defaults, no mate solving, no purchased-component regeneration, no
    fidelity upgrades, no first-shape-only regression, no new dependency, no
    Rotator-specific production names, no implicit clocking.
11. **Regression safety:** the full existing test suite (M8 -> M13-1) passes;
    `@1`/`@2` payload hashes and `MechanicalDesignCandidate` hashes
    unchanged.

Successful acceptance yields the marker
`M13_2_GENERIC_GENERATED_MECHANICAL_PART_CAD_FOUNDATION_VERIFIED`.

## Answers to Mandatory Architecture Questions (36 summary)

1. **Exact confirmed gap:** no positive-cylinder program primitive; candidate
   generated CAD limited to four plate-like component types at bounded
   fidelity; no semantic generated-part model with authority bindings; no
   M13-1 consumption; no instance-level semantic placement derivation.
   (G1-G7.)
2. **Existing generic CAD primitives:** `base_plate` (box), `through_hole`,
   `rectangular_pocket`, `through_slot` — cuts only, single base, single
   solid, fixed frame (cad_program.py:33-96).
3. **Specialized-only generated capabilities:** gear CAD
   (`backends/gearworks_cad.py`), azimuth mount plate
   (`azimuth_mount_plate.py:346-357`) — neither is on the generic candidate
   path.
4. **New third-party dependency:** none required.
5. **build123d:** not used for M13-2; retained solely for the existing
   specialized gear path.
6. **Semantic owner:** `GeneratedPartSpecification` embedded in
   `ComponentSpecificationSnapshot` / `CanonicalComponentSpecification`
   (`@3`); placement authority: `GeneratedPlacementDerivation` records at
   mechanism/physical-instance level.
7. **Initial part types:** solid circular shaft; cylindrical hub / sleeve
   coupling; rectangular frame member. Plate/bracket: legacy path unchanged.
   Bearing: deferred.
8. **Dimensions/interfaces per type:** specified in the Shaft / Hub / Frame
   contracts above, each field authority-bound.
9. **Generated interfaces:** typed, hash-sealed, rule-derived records with a
   closed slot vocabulary, registered in the existing `interfaces` endpoint
   contract (rotational + attachment-face active; frames non-endpoint); no
   M13-1 evidence-taxonomy duplication.
10. **M13-1-driven placement/dimensions:** only via already-authorized
    interfaces (existing gates), referenced through `M13_1_INTERFACE_FACT`
    inputs carrying interface/fact/evidence hashes (no outer spec hash);
    placement derivations bind the specific source physical instance and its
    semantic placement identity.
11. **Design variables vs derivations:** table in Design Variable / Derived
    Value Semantics; every classification enforced by an input/binding.
12. **Hidden defaults prevention:** exactly-one-verified-binding per field
    over explicit `GeneratedAuthorityInput` records; no compiler defaults;
    explicit clocking rules only; `axisymmetric-zero-clocking@1` is a
    declared symmetry convention for exactly-axisymmetric parts only.
13. **Semantic identity -> candidate identity:** spec hash (incl. inputs and
    bindings) -> `specification_hash` -> `candidate_hash`; the placement
    derivation set participates through request/promotion binding hashes.
14. **Compilation:** `GeneratedPartCompiler` (input/binding-verifying) ->
    `CadPartProgram` (+2 ops, exact coordinate contract) -> existing FreeCAD
    backend -> `ArtifactStore` -> fresh reload.
15. **Artifact-to-physical identity:** `part_id =
    generated_cad_definition_id(generated_part)` =
    `generated-part-{full generated_part_hash hex}` (collision-free,
    layer-stable); instances carry `instance_id = cad_instance_id`,
    `part_id = program.part_id`; `representation_identity =
    cad_program_hash(program)`; artifact `input_hash` = program hash.
16. **Fidelity:** new `EXACT_GENERATED_GEOMETRY` member meaning exact
    relative to the bound semantic spec only; M10 checking verified to use
    generic enum equality; plumbing branches classified as model/plumbing
    compatibility.
17. **Multi-solid results:** not supported; one solid per generated part;
    multi-solid physical components are separate components.
18. **Candidate CAD reuse:** existing M12-4 service routing extended, not
    bypassed; mapping/replay/pair-universe machinery unchanged; placement
    recomputed from semantic derivations.
19. **What crosses promotion:** semantic component specifications
    (including the byte-identical embedded `GeneratedPartSpecification`),
    accepted design choices, canonical placements and their semantic
    re-derivation inputs (projected `CanonicalGeneratedPlacementDerivation`
    records on the promoted mechanism), connections, joint bindings, M13-1
    records — never CAD artifacts, never candidate derivation records (only
    their verified canonical projections cross).
20. **Fresh canonical regeneration:** `reconstruct()` -> input/binding
    verification against canonical records -> canonical CAD compiler with
    generated-part routing -> placement replay from
    `CanonicalGeneratedPlacementDerivation` + canonical records ->
    fresh FreeCAD execution -> canonical M10.
21. **Invalidation:** candidate identity change; derivation-set identity
    change; promotion-path rule `/physical_mechanisms/*`; no new
    infrastructure.
22. **Failure classification:** table in Failure Semantics.
23. **Bearing:** deferred (D); trusted-STEP path (A) unchanged; no fake
    generated bearing.
24. **Still impossible after M13-2:** listed in Remaining Capability
    Boundaries.

## Self-Review

Reviewed against the final source-binding and placement-authority checklist;
each item resolved:

- **`candidate:design-variable` string inside a supposedly layer-independent
  binding:** closed — the persisted `DESIGN_SELECTION` locator is
  `{name_form, selection_key, selection_hash}` only; the resolved record's
  identity string is runtime/promotion provenance, never persisted.
- **Candidate instance id embedded in `GeneratedPartSpecification`:**
  closed — no instance IDs anywhere in the spec; `INSTANCE_SCOPED` locators
  store only the instance-relative suffix; resolution context is supplied by
  the verifier.
- **Assumption that candidate/canonical `specification_hash` are equal
  without proof:** closed — audited (parallel payload projections, no
  intentional guarantee), the outer supplying spec hash is removed from the
  M13-1 locator, and resolution uses shared-model `interface_hash` +
  fact/evidence identities within the bounded spec set.
- **Deterministic relation inputs with nowhere to persist:** closed —
  `GeneratedAuthorityInput` records persist relation inputs (supplied
  diameter, clearance) at spec level; relations reference them by
  `input_id`.
- **Clearance described as authoritative but lacking an input record:**
  closed — clearance is an explicit `GeneratedAuthorityInput`
  (`role=clearance`); no compiler default.
- **Placement offset/clocking described as bound but lacking an input
  record:** closed — both are explicit inputs on the
  `GeneratedPlacementDerivation` (`role=axial_offset`,
  `role=clocking_angle`); the axisymmetric rule declares symmetry
  instead and is applicability-checked.
- **`CandidateCadRealization` acting as canonical placement authority:**
  closed — the semantic derivation set is the authoritative input; candidate
  CAD is downstream evidence and required promotion evidence only; canonical
  placement comes from the projected `CanonicalPlacement` and canonical-side
  recomputation.
- **Source interface local coordinates treated as assembly coordinates:**
  closed — the exact local-to-assembly composition rule (source instance
  semantic placement composed with the local M13-1 interface/frame pose)
  is normative and shared by candidate and canonical replay.
- **Source interface hash identifying definition but not physical instance:**
  closed — placement derivations bind `source_physical_instance_id` +
  `source_placement_ref` explicitly; identical specs on different instances
  cannot alias placement (test S).
- **Frame face descriptor presented as an endpoint without interface_id:**
  closed — `GeneratedAttachmentFaceInterface` with `interface_id` is the
  active endpoint family for the six frame faces (registered exactly once in
  `interfaces`); `GeneratedReferenceFrame` is explicitly non-endpoint
  metadata.
- **Unnecessary new authority taxonomy:** avoided — inputs reuse existing
  property keys, design-variable/choice semantic keys, and shared M13-1
  hashes; only the thin locator/value envelope (`GeneratedAuthorityInput` /
  `GeneratedPartFieldBinding` / `GeneratedPlacementDerivation`) is new, and
  it reuses existing `PromotionValueClassification` categories.
- **M13-3 scope creep:** none — handoff boundaries only.

Reviewed against the final identity/canonical-placement closure checklist;
each item resolved:

- **Definition-local `generated_part_id` used as assembly-global `part_id`:**
  closed — `CadPartProgram.part_id = generated-part-{full
  generated_part_hash hex}` (complete semantic hash, SAFE_ID-conformant);
  `generated_part_id` remains local (operation/interface/frame IDs).
- **Different generated definitions colliding in
  `CadAssemblyProgram.parts`:** impossible — different semantic specs have
  different `generated_part_hash` values and therefore different CAD
  definition IDs, even with identical local `generated_part_id`s (test T).
- **`source_physical_instance_id` lost during canonical projection:**
  closed — `CanonicalGeneratedPlacementDerivation` retains
  `source_canonical_instance_id` (projected via the existing
  `canonical_by_candidate` mapping).
- **`source_placement_ref` lost during canonical projection:** closed —
  the canonical derivation record retains `source_placement_ref` (canonical
  placement identity of the source instance), resolved against stored
  `CanonicalPlacement` records.
- **Canonical replay requiring data available only in the candidate
  derivation:** closed — the canonical derivation record plus canonical
  mechanism records (specs, placements, choices) are self-sufficient; no
  candidate CAD or candidate derivation object is consulted.
- **Semantic placement derivation replaceable after selection:** closed —
  the derivation-set hash is bound into the CAD realization request `@2`
  identity, transitively covered by `cad_realization_hash` ->
  evaluation -> selection; promotion proves the supplied set hash equals the
  evaluated/selected one; substitution fails closed.
- **Placement derivation set not bound to selected decision:** closed —
  exact binding chain specified (Selection / Derivation-Set Binding);
  legacy candidates keep `@1` hashes unchanged.
- **Scalar `GeneratedAuthorityInput` pretending to contain a
  frame/quaternion:** closed — inputs remain finite-float only; frames are
  typed structured references (`*_ref` fields) and the rotation is the
  scalar-angle + typed-frame-axis `GeneratedPlacementRotationInput`
  (Rotation Authority Resolution); no record accepts a free quaternion or
  multi-component tuple, and free quaternion authority is explicitly
  deferred.
- **Free quaternion authority without a resolvable source record:** closed —
  repository reality binds one scalar per `DESIGN_SELECTION` record
  (candidates/models.py:568, physical_mechanism.py:445); the rotation input
  resolves exactly one scalar angle from an existing record and takes its
  axis from a typed frame reference whose `frame_hash` is the authority.
- **Hidden identity rotation for non-axisymmetric frame member:** closed —
  `frame-generated-placement@1` requires exactly one explicit
  `GeneratedPlacementRotationInput`; absence fails validation.
- **Implicit source orientation:** closed — the design-variable placement
  contract is translation-only with identity orientation as part of the
  named `accepted-design-variable-placement@1` contract (verified at
  cad_realization.py:470-492 and promotion.py:513-545); non-identity
  orientation requires a chained derivation (Source Placement Orientation
  Contract).
- **Opaque hashes where structured resolution is required:** closed —
  `input_identities` on `CanonicalPlacement` are a provenance summary only;
  structured resolution goes through `CanonicalGeneratedPlacementDerivation`.
- **M13-3 scope creep:** none — handoff boundaries only.

No Critical/Important findings remain open.

## Worktree Note

This session modifies only this specification file. Pre-existing
untracked/modified worktree files (plans, projects, reports, `err.txt`,
`src/mechcad-harness/`) are unrelated pre-existing state and were not
touched, per instructions.
