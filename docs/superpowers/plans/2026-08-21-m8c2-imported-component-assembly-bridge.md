# M8C-2 Implementation Plan — Imported Component Assembly Bridge

**Date:** 2026-08-21  
**Spec:** `2026-08-21-m8c2-imported-component-assembly-bridge-design.md`

## Task 1: Typed Imported Component Model

**Files:**
- Create `src/mechcad_harness/imported_component.py`

**Tasks:**
1. Create `ImportedCadComponent` model with fields:
   - `component_id: str` (min_length=1)
   - `artifact_id: str` (min_length=1)
   - `artifact_hash: str` (min_length=1, format "sha256:...")
   - `format: Literal["step"]`
   - `source_revision: int` (gt=0)
   - `source_state_hash: str` (min_length=1)

2. Create `ImportedComponentResolver` class:
   - `resolve_from_artifact_store(artifact_id, artifact_hash, store: ArtifactStore) -> ImportedCadComponent`
   - Validates artifact exists, type is STEP, sha256 matches
   - Raises typed exceptions on failure

3. Create error types:
   - `ImportedArtifactNotFoundError`
   - `ImportedArtifactIntegrityError`
   - `UnsupportedImportedFormatError`

**Tests:**
- `tests/unit/test_imported_component.py`
  - Test successful resolution from ArtifactStore
  - Test missing artifact fails closed
  - Test hash mismatch fails closed
  - Test wrong format fails closed
  - Test deterministic identity

## Task 2: CadAssemblyProgram Extension

**Files:**
- Modify `src/mechcad_harness/cad_assembly.py`

**Tasks:**
1. Add `imported_components` field to `CadAssemblyProgram`:
   ```python
   imported_components: tuple[ImportedCadComponent, ...] = Field(default_factory=tuple)
   ```

2. Update `validate_registry` to:
   - Accept both `parts` and `imported_components` as component sources
   - Ensure at least one is non-empty
   - Validate all instance references resolve to either parts or imported_components
   - Validate no duplicate component IDs across parts and imported_components

3. Update `assembly_hash` to include:
   - Generated part hashes (existing)
   - Imported component identity (component_id, artifact_id, artifact_hash)
   - Component type discrimination in payload

4. Add helper properties:
   - `all_component_ids` → combined parts + imported_components IDs
   - `has_imported_components` → bool

**Tests:**
- `tests/unit/test_cad_assembly.py` (extend existing)
  - Test assembly with only generated parts (backward compat)
  - Test assembly with only imported components
  - Test assembly with mixed components
  - Test deterministic hash computation
  - Test validation rules

## Task 3: FreeCAD Assembly Backend Extension

**Files:**
- Modify `src/mechcad_harness/backends/freecad_assembly.py`

**Tasks:**
1. Add `_import_step_component` method:
   - Takes `ImportedCadComponent` and `ArtifactStore`
   - Resolves artifact path
   - Imports STEP into FreeCAD
   - Returns shape/solid for placement

2. Extend `generate_assembly` to handle mixed components:
   - For `CadPartProgram`: existing path
   - For `ImportedCadComponent`: new import path

3. Update `_compile` to generate FreeCAD script that:
   - Generates parts from programs (existing)
   - Imports STEP files for imported components
   - Places all instances with transforms

4. Update verification to validate imported component shapes

**Tests:**
- `tests/integration/test_freecad_assembly.py` (extend existing)
  - Test assembly with imported STEP component
  - Test shape/solid verification
  - Test placement verification
  - Test fresh reload verification

## Task 4: Production Service Connectivity

**Files:**
- Modify `src/mechcad_harness/assembly_service.py`
- Modify `src/mechcad_harness/application.py`

**Tasks:**
1. Add `generate_assembly_with_imported` to `CadAssemblyGenerationService`:
   - Accepts `CadAssemblyProgram` with imported components
   - Resolves all imported components via ArtifactStore
   - Delegates to backend

2. Add `build_assembly_with_imported_components` to `ProductionApplication`:
   - Composes generated and imported components
   - Validates source binding
   - Returns assembly result with provenance

**Tests:**
- `tests/integration/test_production_assembly.py`
  - Test production path with imported components
  - Test provenance preservation
  - Test deterministic identity

## Task 5: Comprehensive Test Suite

**Files:**
- `tests/unit/test_imported_component.py`
- `tests/unit/test_cad_assembly_mixed.py`
- `tests/integration/test_imported_assembly_bridge.py`

**Tests:**
1. **Model tests:** ImportedCadComponent creation, validation, trust checks
2. **Assembly model tests:** CadAssemblyProgram with mixed components
3. **Deterministic identity:** Hash computation with imported components
4. **Artifact trust:** Missing artifact, hash mismatch, wrong format fail closed
5. **Backend integration:** STEP import, shape verification, placement
6. **Production path:** ProductionApplication with imported components
7. **Provenance:** Artifact identity survives into assembly result
8. **Genericity:** No gear/Yagi/antenna semantics in bridge code

## Task 6: Regression Verification

**Tasks:**
1. Run existing unit tests:
   ```bash
   python -m pytest tests/unit/ -x
   ```

2. Run existing integration tests:
   ```bash
   python -m pytest tests/integration/ -x
   ```

3. Run full test suite:
   ```bash
   python -m pytest tests/ -x
   ```

4. Verify no boundary violations:
   - No gear/motor/antenna semantics in generic bridge
   - No arbitrary file path acceptance
   - No state mutation
   - No commit/push/stash/reset/clean

## Execution Order

1. Task 1 (typed model) — foundation
2. Task 2 (assembly extension) — integration
3. Task 3 (backend extension) — realization
4. Task 4 (service connectivity) — production path
5. Task 5 (comprehensive tests) — verification
6. Task 6 (regression) — safety

## Verification Commands

```bash
# Unit tests
python -m pytest tests/unit/test_imported_component.py -v
python -m pytest tests/unit/test_cad_assembly.py -v

# Integration tests
python -m pytest tests/integration/test_imported_assembly_bridge.py -v

# Regression
python -m pytest tests/ -x

# Compile check
python -m compileall src/mechcad_harness/ -q
```
