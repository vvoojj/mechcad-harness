# M9-1 — FreeCAD Runtime Preflight & Live Backend Verification

**Date:** 2026-08-22
**Baseline accepted:** M8C_ARCHITECTURALLY_CLOSED_RUNTIME_GATED
**Scope:** Runtime preflight + existing generic FreeCAD backend verification only.
No new CAD primitives, no imported-component / kinematic / FEA / material / manufacturing work.

## 1. Initial Runtime Status

- initial harness discovery status: **UNAVAILABLE** (M8C reported `discover_freecad().available == False`)
- root cause: **FREECAD_INSTALLED_BUT_NOT_CONFIGURED**

The FreeCAD runtime **existed on disk** at `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`.
`MECHCAD_FREECADCMD` was unset and `freecadcmd` was not on `PATH`, so `discover_freecad()`
returned unavailable. Discovery itself was **not broken** — the implementation already
supported `MECHCAD_FREECADCMD`; only environment configuration was missing.

## 2. Resolved Runtime

- executable: `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe` (exists, executes)
- FreeCAD version: `1.1.3`
- discovery source: `MECHCAD_FREECADCMD` harness override; `discover_freecad().execution_boundary` returns the exact string value `"bundled FreeCAD command line"`
- MECHCAD_FREECADCMD usage: set to the real executable; supported contract, no path hardcoded in business logic
- backend identity/version: `name=freecad`, `adapter_version=mechcad-freecad@2.1`, `library_name=FreeCAD`

## 3. Changes Required

No production code change was required. `discover_freecad()` already supported
`MECHCAD_FREECADCMD`; the only gap was environment configuration. Only one new test
file was added (verification evidence). No source modules modified.

## 4. Live Generic Fixture

`CadPartProgram(part_id="M9A1GenericPlate")` with:
- `BasePlateOperation(operation_id="base", 60 x 40 x 6 mm)`
- `ThroughHoleOperation(operation_id="hole1", x=15, y=20, d=8 mm)`

Purely generic; no domain (Yagi/AZ/EL/gear/imported) semantics.

## 5. Actual Live Path

```
CadGenerationService.generate_program
  -> validate_source (rev+state_hash, read-only)
  -> FreeCADBackend.generate_program
       -> discover_freecad().require_available()
       -> compile_program -> freecadcmd subprocess
       -> FCStd + STEP written to temp
       -> ArtifactStore.publish (sha256 + size + metadata)
       -> _verify_persisted:
            reopen FCStd via freecadcmd (fresh subprocess) -> geometry verified
            re-import STEP via freecadcmd (fresh subprocess) -> geometry verified
```

Verified through the **production service boundary**, not a hand-built graph.

## 6. Live Shape Verification

FCStd: status=`verified`, shape_valid=True, solid_count=1, dims≈(60,40,6)mm,
volume≈`60*40*6 - π*4²*6` mm³, through-hole probe `hole_hole1=True`.
STEP: status=`verified`, shape_valid=True, volume matches.

## 7. Artifact Integrity

`ArtifactStore.existing(fcstd_id)` / `existing(step_id)` succeed; `size_bytes` matches
file size; recomputed `sha256` matches stored digest; types `FCSTD`/`STEP`.

## 8. Fresh Reload

- **Fresh reload proof** = separate-process verification (by `_verify_persisted`):
  after generation, the persisted FCStd was **reopened** and the STEP was **re-imported**
  in **separate freecadcmd subprocesses** and re-verified — not inspected only in memory.
- **Deterministic persisted-artifact reuse** = a second `generate_program()` call returned
  the same persisted artifacts from `ArtifactStore` (proving persistence + reload), with
  deterministic semantic identity (NOT binary byte equality).

These are distinct: fresh reload proves the geometry survived a process boundary;
the second call proves deterministic reuse of the persisted artifact.

### Authority / mutation guarantees (proven by existing evidence)

- **No DesignState mutation:** `manager.load_revision(...)` after generation returns the
  same canonical state hash as before (`test_live_generic_part_persists_and_reloads`).
- **No ChangeProposal:** no `proposal` artifact/file was created anywhere in the workspace.
- **No ChangeSet:** no `changeset` artifact/file was created anywhere in the workspace.

No new test was invented; the existing live test already asserts these.

## 9. Runtime / Backend Provenance

`backend.provenance()`: backend_name=`freecad`, adapter_version=`mechcad-freecad@2.1`, library_name=`FreeCAD`, library_version=`1.1.3`, library_source=resolved executable.
Result carries `backend_version=mechcad-freecad@2.1`, `freecad_version=1.1.3`.
Execution mode: **freecadcmd subprocess** (each generation and verification step runs the
real `freecadcmd` executable as a child process).

## 10. Tests

New `tests/integration/test_m9_1_freecad_runtime_live.py`:

- Live FreeCAD (run + passed): `test_live_backend_compiles_generic_program`,
  `test_live_generic_part_persists_and_reloads`,
  `test_live_generic_part_is_deterministic_and_reloadable`,
  `test_live_backend_runtime_identity` — **4 passed**
- Non-runtime discovery/config (passed): `test_discovery_finds_configured_runtime`,
  `test_discovery_reports_unavailable_for_nonexistent_config`,
  `test_invalid_configured_executable_fails_clearly` — **3 passed**

Existing generic live subset (run + passed with `MECHCAD_FREECADCMD` set):
- `test_through_slot_freecad_live.py` — 1 passed
- `test_freecad_backend_live.py` — 6 passed
- `test_cad_program_live.py` — **5 passed**

Existing FreeCAD unit subset — **48 passed** (no regressions).

`python -m compileall src/mechcad_harness -q` → exit 0.
`git diff --check` → exit 0.

## 11. Files Changed

- Added: `tests/integration/test_m9_1_freecad_runtime_live.py`
- Added: `docs/superpowers/specs/2026-08-22-m9-1-freecad-runtime-live-verification.md`
- No source modules modified. No commit / push / stash / reset / clean.

## 12. M8C Runtime-Gated Edge Updated

`CadPartProgram -> FreeCAD realization` (generic base-plate + hole/slot path) moves from
`RUNTIME_GATED` to `LIVE_FREECAD_VERIFIED` for the generic backend.

NOT upgraded (did not run): imported-component live proof, transient exact collision,
kinematic sweep, FEA, materials, manufacturing.

## 13. Remaining M9 Work

- M9-2 real trusted imported artifact production
- M9-3 live mixed assembly + exact kinematic proof
- M9-4 trusted analysis/backend provenance

## 14. Scope Confirmation

- No imported-component live milestone implemented.
- No kinematic sweep added.
- No new CAD primitives created.
- No FEA. No material selection. No manufacturing work.
- No commit / push / stash / reset / clean.

## 15. Final Disposition

M9_1_LIVE_FREECAD_BACKEND_VERIFIED
