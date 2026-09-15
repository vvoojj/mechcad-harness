# MechCAD Documentation Gaps

Maturity terms follow `MECHCAD_SYSTEM_CONTRACT.md`. This is a current gap
register, not a substitute for historical reconstruction. The disposition says
whether the row remains operationally active, requires audit evidence, or is
retained only as a concise historical reference.

| ID | Status | Disposition | Current focus / retained pointer |
|---|---|---|---|
| GAP-001 | RESOLVED | MOVE_TO_HISTORY_BY_POINTER | Historical source-path correction; use `docs/MechCAD_Harness_Project_Description.md` and reconstruction for history. |
| GAP-002 | RESOLVED | MOVE_TO_HISTORY_BY_POINTER | Superseded M0-only root framing; current root documents use the M13-4 baseline. |
| GAP-003 | RESOLVED | KEEP_RESOLVED_REFERENCE | Generic contracts retain generic axes/frames; Yagi terminology remains reference-domain only. |
| GAP-004 | AUDIT_REQUIRED | KEEP_AUDIT_REQUIRED | M6B-2B code/tests exist, but retained acceptance provenance for the design-only boundary remains unresolved. |
| GAP-005 | OPEN | KEEP_ACTIVE | Unchecked M7C/M7D plans are historical execution plans, not completion evidence; retain a clear pointer rather than creating retrospective acceptance. |
| GAP-006 | AUDIT_REQUIRED | KEEP_AUDIT_REQUIRED | Audit registered role identity against invocation and ownership records. |
| GAP-007 | AUDIT_REQUIRED | KEEP_AUDIT_REQUIRED | The general M5 permission wording permits a compatibility form broader than exact `name@version`, while current `ToolBroker` and M6B mediator enforce exact `name@version` and reject bare names (guarded by `tests/unit/test_tools.py` and `tests/unit/test_production_application.py`). Reconcile whether the broader general compatibility contract is restored or formally retired; do not flatten the two scopes. |
| GAP-008 | OPEN | KEEP_ACTIVE | Current terminal recovery scans `*/final.json` and supports bounded terminal outcomes; its contract/acceptance boundary still needs documentation or audit evidence. |
| GAP-009 | RESOLVED | KEEP_RESOLVED_REFERENCE | Bounded M11 is current; broad structural approval and unrestricted FEA remain future. |
| GAP-010 | AUDIT_REQUIRED | KEEP_AUDIT_REQUIRED | Audit representative artifact/source-revision and promotion bindings; ArtifactStore persistence is not canonical state. |
| GAP-011 | RESOLVED | KEEP_RESOLVED_REFERENCE | M9 live-verified the connected FreeCAD/imported-artifact path; adapter existence alone remains insufficient proof elsewhere. |
| GAP-012 | AUDIT_REQUIRED | KEEP_AUDIT_REQUIRED | M6B-3/M6B-4 acceptance traceability is concentrated in historical project records; retired M6B-4C is not a current capability. |
| GAP-013 | SUPERSEDED | SUPERSEDED | Historic roadmap claims must not demote accepted foundations; reconstruction owns the chronology. |
| GAP-014 | AUDIT_REQUIRED | KEEP_AUDIT_REQUIRED | Partially resolved: artifacts/results now record separate `build123d` runtime provenance (`backends/gearworks_cad.py`, `artifacts/models.py`) and M12-6 live-observed build123d 0.11.1. Remaining audit item: deterministic-replay sufficiency and whether a separate registered provider identity is required. |
| GAP-015 | RESOLVED | KEEP_RESOLVED_REFERENCE | Material lookup/evaluation remains distinct from future canonical material selection. |
| GAP-016 | RESOLVED | KEEP_RESOLVED_REFERENCE | build123d remains specialized gear geometry, not the generic project CAD compiler. |
| GAP-017 | RESOLVED | KEEP_RESOLVED_REFERENCE | Backend identity is required; conditional library metadata remains valid. |
| GAP-018 | RESOLVED | KEEP_RESOLVED_REFERENCE | Gear-pair artifacts do not establish a general `CadAssemblyProgram`. |
| GAP-019 | RESOLVED | KEEP_RESOLVED_REFERENCE | M11-5 durable Evidence/repeatability/convergence is current only within its bounded scope. |
| GAP-020 | RESOLVED | KEEP_RESOLVED_REFERENCE | M11-6 is the accepted structural system closure, not a broader structural capability. |

Current-code confirmation establishes implementation behavior, not historical
execution or acceptance. `AUDIT_REQUIRED` is not a negative implementation
verdict. No M12/M13 reconciliation gap remains: accepted M13-4 architecture is
now owned by `docs/architecture/`, with implementation/wiring status in
`docs/reference/`.
