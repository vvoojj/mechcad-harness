# M8C-1 Design: Generic DesignSpec → CAD Program Production Ingress

**Date:** 2026-08-21
**Status:** DESIGN

## 1. Selected DesignSpec Type

**Type:** `MountingPlateDesignSpec`

A generic mechanical mounting plate specification. It captures plate dimensions, thickness, through-holes, optional rectangular pockets, and optional through-slots — all as concrete numeric values with no domain semantics.

**Why appropriate:** Exercises all four existing generic CAD operations (BasePlate, ThroughHole, RectangularPocket, ThroughSlot) without requiring Yagi/antenna/AZ/EL semantics. MountingPlateDesignSpec supports rectangular plates with through-holes, rectangular pockets, and through-slots — the geometry profile needed for motor mounting brackets and similar flat fixtures. The spec is domain-owned (could come from Yagi, motor, transmission, or any other domain) but the compiler is generic.

## 2. Authority / Provenance Source

The compiler operates on an **accepted** `MountingPlateDesignSpec` that is **derived from** canonical `DesignState`. The compiler does not read `DesignState` directly — it receives a pre-validated spec. Source binding is validated by `CadCompilationService` against the authoritative state:

```
DesignState (canonical)
  -> authoritative_parameter or domain synthesis (accepted)
  -> MountingPlateDesignSpec (accepted, derived)
  -> CadCompilationService (validates source binding)
  -> CadPartProgram (deterministic)
```

Source binding includes: `project_id`, `source_revision`, `source_state_hash`, `spec_hash`. If any binding is stale or mismatched, compilation fails closed.

## 3. Generic Proof Part

A **motor mounting plate** with:
- Rectangular base plate (e.g., 120×100×10 mm)
- Central shaft clearance through-hole
- Four motor mount through-holes
- Four frame mount through-holes
- One rectangular pocket (cable clearance)

This uses: `BasePlateOperation`, `ThroughHoleOperation`, `RectangularPocketOperation`. No `ThroughSlotOperation` is required for the minimal proof, but the spec supports it and tests verify slot compilation.

## 4. Compiler / Service API

```python
# src/mechcad_harness/cad_compilation.py

class CadCompilationError(Exception): ...
class DesignSpecSourceBindingError(CadCompilationError): ...
class DesignSpecStaleSourceError(DesignSpecSourceBindingError): ...
class DesignSpecHashMismatchError(DesignSpecSourceBindingError): ...
class UnresolvedDesignInputError(CadCompilationError): ...

class CadCompilationResult(Model):
    project_id: str
    source_revision: int
    source_state_hash: str
    spec_hash: str
    compiler_version: str
    program: CadPartProgram
    program_hash: str

class CadCompilationService:
    def __init__(self, state_manager: StateManager): ...
    def compile_mounting_plate(
        self,
        *,
        project_id: str,
        source_revision: int,
        source_state_hash: str,
        spec: MountingPlateDesignSpec,
    ) -> CadCompilationResult: ...

def compile_mounting_plate(spec: MountingPlateDesignSpec) -> CadPartProgram: ...
def mounting_plate_spec_hash(spec: MountingPlateDesignSpec) -> str: ...
```

**Compiler identity:** `generic-mounting-plate-compiler@1.0`

## 5. Deterministic Identity Rules

- `source_revision` and `source_state_hash` are validated against `StateManager` (fail-closed on mismatch)
- `spec_hash` is deterministic SHA-256 of `MountingPlateDesignSpec` JSON (sorted keys)
- `program_hash` is deterministic SHA-256 of `CadPartProgram` JSON (sorted keys)
- Operation ordering: base plate first, then through-holes sorted by operation_id, then pockets sorted by operation_id, then slots sorted by operation_id
- Compiler identity is a fixed string constant
- No timestamps, random UUIDs, or filesystem order

## 6. ProductionApplication Integration

```python
class ProductionApplication:
    @property
    def cad_compiler(self) -> CadCompilationService: ...

    def compile_design_spec(
        self,
        *,
        source_revision: int,
        source_state_hash: str,
        spec: MountingPlateDesignSpec,
    ) -> CadCompilationResult:
        return self.cad_compiler.compile_mounting_plate(
            project_id=self.project_id,
            source_revision=source_revision,
            source_state_hash=source_state_hash,
            spec=spec,
        )
```

The application owns the service as a composition boundary. No compilation logic in `ProductionApplication`.

## 7. Output

`CadPartProgram` with existing generic operations only:
- `BasePlateOperation`
- `ThroughHoleOperation`
- `RectangularPocketOperation`
- `ThroughSlotOperation`

## 8. Failure Behavior

| Condition | Behavior |
|---|---|
| Stale revision | `DesignSpecStaleSourceError` |
| Hash mismatch | `DesignSpecHashMismatchError` |
| Project mismatch | `DesignSpecSourceBindingError` |
| Unresolved parametric value | `UnresolvedDesignInputError` |
| Invalid geometry | `CadCompilationError` (Pydantic validation) |
| Empty required field | Pydantic `ValidationError` |

All failures are typed. No placeholder or fallback compilation.

## 9. Why No Engineering Decision Is Made

The compiler is a **deterministic transform** from accepted mechanical dimensions to CAD operations. It:
- Validates that all values are concrete and finite
- Maps hole positions to `ThroughHoleOperation`
- Maps plate dimensions to `BasePlateOperation`
- Maps pocket dimensions to `RectangularPocketOperation`
- Maps slot dimensions to `ThroughSlotOperation`
- Chooses deterministic ordering

It does NOT:
- Select thickness from a policy
- Choose hole diameters
- Resolve parametric values
- Perform stress/FEA analysis
- Select materials
- Make any engineering decision

All engineering values must be resolved in the accepted spec before compilation.

## 10. M8C-2 Exclusions

The following are NOT implemented in M8C-1:
- Imported STEP component bridge (`ImportedCadComponent → CadAssemblyProgram`)
- Specialized gear → generic assembly integration
- Material selection workflow
- Multi-axis kinematic chains
- FEA/structural analysis
- Manufacturing approval
- Universal assembly generation from arbitrary design specs
- Gear artifact → assembly integration
