# M11-3 Gmsh / CalculiX Technical Proof

This document completes the disposable-runtime technical proof for the initial
M11-3 single-body linear-static contract. It does not implement the production
service and does not start M11-4.

Accepted baseline:

- `M11_1_STRUCTURAL_FEA_ARCHITECTURE_READY`
- `M11_2_STRUCTURAL_AUTHORITY_MODEL_VERIFIED`
- `M11_3_RESULTANT_FORCE_LOWERING_PROVEN`

## Runtime Versions

Verified installations:

- FreeCAD 1.1.3: `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`
- Gmsh 4.15.0: `C:\Program Files\FreeCAD 1.1\bin\gmsh.exe`
- CalculiX 2.22: `C:\Program Files\FreeCAD 1.1\bin\ccx.exe`

The proof used a real FreeCAD-generated STEP artifact, actual Gmsh CLI
meshing, and actual CalculiX CLI solves. No packages were installed.

## FreeCAD Region Resolution

For the initial admitted source contract, realization and semantic resolution
are separate:

1. The public FreeCAD CAD boundary realizes the source-bound CAD program and
   produces verified FCStd and STEP artifacts.
2. A structural region resolver consumes the exact realized BREP, preferably
   from the verified FCStd/STEP artifact, and applies deterministic geometric
   predicates.
3. The resolver emits a semantic region map containing canonical geometric
   descriptors and a hash. It never emits raw `FaceN` authority.

The real fixture was a `100 x 20 x 10 mm` box:

- one admitted solid: `solid_count=1`, `shape_valid=True`;
- six realized planar faces;
- `fixed_end`: exactly one face selected by minimum centroid X, centroid
  `(0,10,5)`, area `200 mm^2`;
- `free_end`: exactly one face selected by maximum centroid X, centroid
  `(100,10,5)`, area `200 mm^2`;
- all other faces were rejected for these semantic regions;
- exact total face area recovery was `200 mm^2` for each selected region.

The source STEP hash was
`sha256:3143f47d4870dc4ea2b923e556d0443bd13a1d0d5428a0c76ed8b17c4a14c6da`.
A source-side canonical semantic-region payload containing solid count,
geometry hash, region names, planar kind, centroids, areas, and plane
predicates produced:

`sha256:4a4df9c13c31104f3edce50f47d19c54a04abe52a908f551749ed76c2003f85a`

The exact STEP BREP was then re-imported into FreeCAD 1.1.3 and resolved again:
one valid solid, six faces, unique min/max-centroid predicates, and both
semantic areas `200.000000000000 mm^2`. The realized-BREP region payload hash
was `sha256:0e7b975b2389527bf0dfea727b261a9f41d29318c6e4c88218401877c2a61c5b`.

## Source Feature / STEP Identity Finding

Source feature identities are meaningful in the source-side FCStd/program
context and may be retained in the CAD manifest. They do not survive STEP
realization as a reliable semantic authority. STEP is therefore treated as
geometry plus artifact provenance; region identity is recovered from exact
realized BREP predicates and not from STEP entity names or raw face indices.

## FreeCAD Reuse Boundary

Production structural code must not call `FreeCADBackend._run` or
`FreeCADBackend._parse_verification` directly. The selected boundary is the
existing public `FreeCADBackend.generate_program` operation, which already:

- uses deterministic local FreeCAD command-line execution;
- verifies FCStd and STEP output;
- binds artifacts to revision/state hash;
- persists `EngineeringArtifact` records with backend provenance.

A narrow `StructuralFreeCADGeometryAdapter` may wrap this public method to
resolve structural regions. It must not duplicate the private subprocess or
verification implementation and must not redesign the existing backend.

## Gmsh Geometry Transfer

The selected actual format is a Gmsh `.geo` script referencing the verified
STEP artifact, executed through the Gmsh command line:

`gmsh.exe box.geo -3 -format inp -o box.inp -nopopup`

The `.geo` contains:

```text
Merge "box.step";
Physical Surface("fixed_end") = {1};
Physical Surface("free_end") = {2};
Physical Volume("volume") = {1};
Mesh.ElementOrder = 2;
Mesh 3;
```

The real Gmsh run reported one connected 3D volume, 854 nodes, and 771 total
elements in the Abaqus/CalculiX `.inp` export. The export contained quadratic
surface `CPS6` blocks, a quadratic volume `C3D10` block, and named ELSETs
`fixed_end`, `free_end`, and `volume`.

The mesh remains source-bound through the STEP artifact hash, `.geo`/region
map hashes, Gmsh identity, and the resulting mesh hash. It is not an
independent engineering authority.

## Physical Group Mapping

The physical groups have the required dimensions and cardinalities:

- `fixed_end`: dimension 2, nonempty;
- `free_end`: dimension 2, nonempty;
- `volume`: dimension 3, exactly one volume entity, nonempty.

Gmsh's exported element block labels may be generic (`Surface1`, `Surface2`,
`Volume1`), so production must use the named physical ELSET definitions and
their entity dimensions, not block names or incidental ordering.

## Actual Quadratic Element Family

The actual volume family is Gmsh element type 11, exported as CalculiX
`C3D10`. Boundary triangles are Gmsh second-order type 9, exported as `CPS6`.
The `CPS6` elements must not remain in the 3D CalculiX structural model; they
are source boundary evidence used to map semantic surfaces to volume-element
faces.

## Gmsh -> C3D10 Conversion

The selected conversion is identity for this Gmsh Abaqus export. It is still
validated geometrically and not assumed from the shared element node count.

## Node Ordering

Gmsh type 11 and CalculiX `C3D10` use:

1. corner 1
2. corner 2
3. corner 3
4. corner 4
5. edge 1-2 midpoint
6. edge 2-3 midpoint
7. edge 1-3 midpoint
8. edge 1-4 midpoint
9. edge 2-4 midpoint
10. edge 3-4 midpoint

The explicit permutation from the Gmsh-exported connectivity to CalculiX is

`[1,2,3,4,5,6,7,8,9,10]`.

This was independently checked on real elements by comparing every midside
coordinate with the corresponding corner-edge midpoint. Maximum discrepancy
was below `5e-13 mm`.

CalculiX's local face table is:

- `S1 = [1,3,2,7,6,5]`
- `S2 = [1,2,4,5,9,8]`
- `S3 = [2,3,4,6,10,9]`
- `S4 = [1,4,3,8,10,7]`

The first three entries are face corners and the last three are the
corresponding midside nodes. This table was confirmed from the CalculiX
`ifacet` source and by isolated four-face solver probes.

## CalculiX Surface Mapping

The deterministic production algorithm is:

1. resolve one semantic BREP face and retain its region-map hash;
2. read the named Gmsh physical surface boundary triangles;
3. for each boundary triangle, identify its three corner node IDs;
4. inspect C3D10 volume elements and the four local corner triples;
5. require exactly one adjacent volume element and local face;
6. emit `(volume_element_id, S1|S2|S3|S4)`;
7. reject duplicate, missing, ambiguous, or unsupported mappings.

The algorithm uses connectivity and geometric identity, not coincidental node
numbering. It supports:

- `FixedSupport`: derived fixed-region node set and `*BOUNDARY` DOFs 1-3;
- `SurfacePressure`: named element-face surface and `*DLOAD` pressure;
- `ResultantForce`: the same mapped face triangles for consistent `*CLOAD`;
- future assessment-region interpretation.

On the real free-end surface, 14 CPS6 boundary triangles mapped to 14 unique
C3D10 element faces and 39 fixed-end nodes were derived deterministically.

## Fixed Support Encoding

The initial encoding is:

```text
*NSET, NSET=fixed_end_nodes
...
*BOUNDARY
fixed_end_nodes, 1, 3, 0
```

The set is derived from the resolved semantic fixed face, not from `Face1` or
any other raw topology index.

## Pressure Encoding

The native normal-pressure encoding is:

```text
*SURFACE, NAME=free_end, TYPE=ELEMENT
element_id, S1
...
*DLOAD
free_end, P, pressure
```

Positive pressure is compression opposite the outward face normal. Native
pressure equivalence with the accepted resultant-force lowering was proven in
`MECHCAD_M11_3_RESULTANT_FORCE_LOWERING_PROOF.md`.

## Resultant Force Encoding

Accepted and closed by `M11_3_RESULTANT_FORCE_LOWERING_PROVEN`:

`StructuralResultantForce -> t = F/A -> exact consistent C3D10 surface integration -> *CLOAD`.

For each straight-sided planar face triangle, corner contribution is zero and
each midside contribution is `A_e/3 * t`. Force and moment are conserved;
normal pressure, tangential, and oblique cases were solver-verified. The
required provenance includes canonical load ID, semantic region ID, region-map
hash, exact area, source force, solver traction, lowering identity/version,
C3D10 rule/version, nodal-load hash, and mesh hash. Mesh node IDs remain
derived identities.

## Body Acceleration Encoding

The accepted unit conversion is:

`density_kg_per_m3 * 1e-12 = density_t_per_mm3`.

For `2700 kg/m^3`, the solver density was `2.7e-9 t/mm^3`. CalculiX encoding:

```text
*DENSITY
2.7e-9
...
*DLOAD
volume, GRAV, 9810., 0., -1., 0.
```

The vector convention is magnitude in `mm/s^2` plus a normalized global
direction. A real constrained solve returned reaction
`(-1.93e-13, +0.5251372, -2.00e-13)` for downward `-Y` gravity. Doubling the
density returned `(-3.86e-13, +1.050274, -4.00e-13)`, a ratio of
`1.9999992`. This proves direction, density dependency, conversion, and
equilibrium behavior. The reaction is the discretized mesh body-load result;
it is not an engineering acceptance calculation.

## CalculiX Execution

The direct solver boundary is a subprocess invocation of `ccx.exe` with the
job basename, in an isolated run directory. The adapter must capture exit
code, stdout, stderr, input/deck hash, and all produced raw files.

Valid constrained solve:

- exit code `0`;
- stdout contains `Job finished`;
- `.frd`, `.dat`, `.sta`, `.cvg`, and `.12d` were produced.

`*NOT_A_REAL_CARD` was also observed to be silently tolerated by CalculiX and
still returned `0`; therefore strict deck/card validation is required before
solver invocation. A bad numeric `*DLOAD` value produced the reliable fatal
signature below.

## Underconstrained Diagnostics

A deliberately unconstrained model (no `*BOUNDARY`) returned:

- exit code `0`;
- stdout `Job finished`;
- `.frd` and `.dat` present;
- no reliable `singular`, `rigid body`, or `nonconverged` diagnostic.

Therefore CalculiX 2.22 cannot be trusted to classify underconstraint from
solver status alone. Production must perform a deterministic constraint
preflight/rank check before invocation. If it cannot prove adequate constraint
coverage, it must emit `SOLVER_UNDERCONSTRAINED` and not accept solver output.
The solver's `0`/`Job finished` signature is insufficient.

Malformed numeric input (`NOT_A_NUMBER`) produced:

- exit code `201`;
- `*ERROR reading *DLOAD. Card image:`;
- `*ERROR in calinput: at least one fatal error message...`;
- `.dat` present as diagnostics;
- `.frd` absent.

This is `SOLVER_FAILED`/invalid deck, not nonconvergence. For the initial
linear-static contract, unresolved increment or missing required result output
must conservatively collapse to `SOLVER_FAILED`; no finer
`SOLVER_NONCONVERGED` classification is claimed without a distinct reliable
signature.

`SOLVER_UNAVAILABLE` is a pre-execution status: executable discovery or
process launch fails, no solver artifacts are accepted, and the captured
launch error is retained. It is not inferred from CalculiX output.

## Required Artifact Types

The minimum durable set is:

| Type | Direct producer | Required on success | May exist on failure | M11-4 use |
|---|---|---:|---:|---|
| `MSH` | Gmsh | yes | yes | mesh/result-node mapping |
| `INP` | structural deck builder | yes | yes | reproducibility and solver input |
| `FRD` | CalculiX | yes for field results | partial/optional | displacement/stress fields |
| `DAT` | CalculiX | yes for text result/summary | yes for diagnostics | reactions and diagnostics |
| `LOG` | solver adapter capture | yes | yes | execution diagnostics |
| `JSON` manifest | structural execution orchestrator | yes | yes | pipeline binding/provenance |

Existing `.sta`, `.cvg`, and `.12d` files are useful raw diagnostics but are
not required as separate minimum durable artifact types for the initial
contract. `ArtifactType` needs narrow additions for `MSH`, `INP`, `FRD`, `DAT`,
and `LOG`; `JSON` already exists. No separate provenance database is needed.

## Multi-Provider Provenance Shape

Each artifact remains an existing `EngineeringArtifact` published by
`ArtifactStore`, with direct producer name/version, SHA-256, input hash,
revision/state binding, and optional `BackendProvenance`.

Direct producer identities:

- FreeCAD geometry: existing `BackendIdentity`/`BackendProvenance`, including
  FreeCAD version and adapter version;
- structural region resolver: versioned structural resolver identity, input
  STEP/FCStd hash, region-map hash;
- Gmsh mesher: Gmsh identity/version/source and `.geo`/STEP input hashes;
- deck builder: versioned deterministic builder identity, mesh/region/load
  hashes;
- CalculiX solver: CalculiX identity/version/source and deck hash.

One `StructuralExecutionManifest` JSON artifact binds all direct artifact IDs,
hashes, identities, source revision/state hash, request identity, resolved
region identity, and final execution status. This fits the existing
`EngineeringArtifact`, `BackendIdentity`, `BackendProvenance`, and
`ArtifactStore` model without another provenance store.

## Failure Artifact Semantics

Success:

- mesh, deck, raw solver output, diagnostics, and manifest may persist;
- manifest records `SUCCEEDED` and all artifact hashes;
- only after successful execution and result validation may a structural result
  be created.

Failure:

- generated mesh/deck/log/dat/partial raw files may persist;
- manifest records `FAILED` with failure status and diagnostics;
- no `StructuralAnalysisResult`;
- no structural verification PASS/FAIL;
- no accepted structural Evidence.

M11-3 is execution and provenance only, not engineering acceptance.

## Run / Source Binding Sequence

The production sequence is:

1. acquire `StateManager.project_lock(project_id)`;
2. load the current pointer and current immutable revision/state hash;
3. require request `source_revision/state_hash` to equal that pointer;
4. validate the structural definition against that immutable snapshot;
5. call `RunController.create_run(expected_source=SourceBinding(...))` while
   still under the project lock;
6. create the execution manifest bound to the same source;
7. execute only with `load_revision(project_id, run.active_revision)` and the
   frozen artifact bindings;
8. never re-read current state for engineering inputs during execution.

`create_run(expected_source=...)` revalidates the immutable snapshot hash and
the current pointer under the same lock, raising `RunIntegrityError` on a
mismatch. `StateManager.load_revision` verifies the snapshot hash. Later
current-pointer advancement cannot rebind an already-created run. This closes
the TOCTOU path while allowing an accepted source-bound run to continue against
its immutable snapshot.

## Technical Risks

- CalculiX accepts some unknown keyword prefixes/cards; strict deck validation
  is mandatory.
- CalculiX may return success for underconstrained systems; constraint
  preflight must be authoritative.
- Curved or non-planar high-order boundary faces are not admitted by the
  closed-form resultant-force rule.
- Gmsh block labels are not semantic group names; named physical ELSETs and
  dimensions must be validated.
- C3D10 ordering and local face mapping must be validated, not assumed.
- Artifact enum extensions are required before production persistence of raw
  structural files.
- STEP carries geometry provenance, not reliable source feature semantics.

## Required Production Components

- public-boundary `StructuralFreeCADGeometryAdapter`;
- deterministic BREP semantic-region resolver and region-map hash;
- Gmsh CLI adapter and source-bound `.geo` builder;
- C3D10 mesh parser/order validator;
- deterministic semantic-face-to-volume-face mapper;
- fixed-support, pressure, body-acceleration, and accepted ResultantForce
  deck lowerings;
- strict deck validator and constraint preflight;
- CalculiX subprocess adapter and conservative status classifier;
- raw artifact publisher using `ArtifactStore`;
- `StructuralExecutionManifest` builder;
- source-bound run integration using `SourceBinding` and `project_lock`.

## Production Implementation Recommendation

The technical proof is ready for implementation, subject to these narrow
constraints:

- do not change M11-2 structural schemas or canonical load semantics;
- implement the proven initial contract only: one source-bound single solid,
  planar semantic face regions, C3D10/CPS6 mapping, and straight-sided planar
  C3D10 consistent ResultantForce lowering;
- fail closed for unsupported geometry, topology ambiguity, missing groups,
  failed constraint preflight, invalid deck, missing required raw artifacts,
  or untrusted source binding;
- preserve direct-producer provenance and one complete execution manifest;
- do not begin M11-4 acceptance or engineering evaluation.

## Disposition

`M11_3_TECHNICAL_PROOF_READY_FOR_IMPLEMENTATION`
