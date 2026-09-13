# F4 Structural Mesh Hash Authority Design

## Scope

Remediate F4 only. This design consolidates ownership of structural
mesh-specification and mesh-input identity without changing current hash bytes,
the independent verifier recomputation boundary, or unrelated duplication
findings.

## Current Issue

Structural mesh-specification hashing is independently implemented in the
structural service, validation, result interpreter, and Evidence code. The
Evidence implementation additionally applies a generic volatile-key filter.
Mesh-input hashing is implemented in `structural/models.py` and independently
rebuilt in the Evidence verifier. The values are cross-compared today, but a
future field could make those projections diverge.

## Identity Contract

`structural/models.py` owns two canonical semantic projections:

- `mesh_specification_hash(specification: MeshSpecification) -> str`
- `mesh_input_hash(...) -> str`

`mesh_specification_hash` hashes exactly the JSON-mode dump of the closed
`MeshSpecification` model. Every declared field participates in identity:
`element_family`, `global_target_size_mm`, `refinements`,
`quality_policy_id`, and `mesher_settings_version`. The model remains
`extra="forbid"`; generic volatile-key filtering is prohibited for this
contract.

If a future mesh field must be non-identity, it must be introduced through an
explicit versioned identity-contract change. It must not be silently excluded
by a generic key-name policy.

`mesh_input_hash` retains its existing semantic payload and byte representation:
`source_geometry_hash`, `mesh_specification_hash`, `region_map_hash`,
`gmsh_identity`, and `gmsh_version`.

## Integration

The structural service produces both hashes through the model-owned helpers.
Validation, result interpretation, Evidence convergence checks, and Evidence
artifact verification independently recompute the relevant identity through the
same helpers before comparing it with persisted metadata. Local helper methods
and the Evidence inline payload rebuild are removed rather than retained as
delegating wrappers.

## Verification

Focused tests will prove:

- existing mesh-specification and mesh-input hashes retain their current bytes;
- service production and result/Evidence verification cross-comparisons pass;
- every declared mesh-specification field changes identity when changed;
- a generic volatile-looking key cannot be silently accepted or filtered from
  `MeshSpecification` identity;
- the model helpers are the only production semantic projections for these
  identities.

Run focused structural tests, the full unit suite if feasible, `git diff
--check`, and a fresh skeptical review. The remediation will use one local F4
commit and no push.
