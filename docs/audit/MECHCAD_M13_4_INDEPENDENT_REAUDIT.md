# M13-4 Independent Re-Audit

## Verdict

```text
M13_4_INDEPENDENT_REAUDIT_REJECTED
M13_4_ACCEPTANCE_STATUS = REJECTED
ROTATOR_V2_MAY_RESUME = NO
```

## Audit Independence

This audit did not implement or remediate M13-4, edit production or test code,
commit, tag, push, or start Rotator V2. The only intentional repository write is
this report. The prior rejection remains preserved at
`docs/audit/MECHCAD_M13_4_INDEPENDENT_ACCEPTANCE.md`.

## Historical Rejection

The controlling prior findings were CRIT-01 (fabricated authority), CRIT-02
(no scalar restart boundary/incomplete equivalence), and IMP-01 (incomplete
promotion/Evidence proof). The completion report was treated as a claim only.

## Remediation Scope

The received remediation is confined to:

- `tests/integration/m13_4_acceptance_fixtures.py`
- `tests/integration/test_m13_4_full_stack_acceptance.py`
- `docs/audit/MECHCAD_M13_4_COMPLETION_REPORT.md`

No new M13-4 semantic production change was found in `src/mechcad_harness/`.
The dirty M13-4E/M13-4P source files remain accepted pre-existing work.

## Worktree / Protected Surface

`git status --short`, `git diff --stat`, `git diff`, and `git diff --check` were
run. `git diff --check` exits zero with existing CRLF normalization warnings.
No predecessor golden or hash file was modified by this remediation.

## CRIT-01 Re-Audit

### Supplied Authority

The prior false `vendor:motor` / manufacturer shaft authority is removed from
the active M13-4 fixture. The trusted artifact is byte-verified and is correctly
represented as a 30 x 30 x 5 mm `support-plate`, with source identity
`trusted:supplied-support-plate`.

Its mounting face `Face6` and `support-mount-frame` use geometry-inferred local
measurements accepted through `HUMAN_CONFIRMED_INTERPRETATION`, bound to the
artifact ID/hash. It provides no shaft interface. J1 instead identifies its axis
from generated `shaft-a`; J2 identifies its axis from generated `hub-a` output.
This repair is truthful as to supplier/manufacturer provenance.

### Generated Authority

Revision-1 source state now contains requirement
`REQ-M13-4-GENERATED-GEOMETRY`, constraints
`CON-TRANSMISSION-OUTPUT-INTERFACE` and
`CON-TRANSMISSION-PACKAGING-ENVELOPE`, and supported authoritative parameters
`transmission.output_interface` and `transmission.packaging_envelope`.
Candidate binding covers `/id`, `/requirements`, `/constraints`,
`/authoritative_parameters`, and `/physical_mechanisms`.

| Consumer field | Value | Source / derivation |
| --- | --- | --- |
| shaft diameter; both bore diameters | 10 mm | output-interface shaft diameter |
| shaft length; hub length | 50 mm | packaging max height |
| hub OD; frame width | 30 mm | packaging max width |
| frame length | 60 mm | packaging max length |
| frame height; shaft axial offset | 10 mm | output-interface diameter |
| input bore start/depth | 0 / 25 mm | direct zero / half packaging height |
| output bore start/depth | 25 / 25 mm | half packaging height |
| support frame pose | (0,0,5), identity orientation | accepted geometry-backed mounting frame |
| frame rotation | 0 degrees | persisted design selection |

The repository's generated-part authority contracts accept candidate design
selections replayed from supported source parameters. This portion is materially
improved and no longer depends on manufacturer-labelled fixture data.

### Pair Policy

All 15 unordered pairs are constructed once: three same-body exclusions, two
intended-contact exclusions, and ten all-configuration `CHECK_CLEARANCE` pairs.
It contains both root/articulated and articulated/articulated checks.

However, `motor-r/shaft-a` remains falsely excluded as
`INTENDED_CONTACT_EXCLUDED` with reason `explicit J1 support connection`
(`m13_4_acceptance_fixtures.py:700-703`). The actual plate occupies z=0..5 and
the derived shaft starts at z=15, leaving 10 mm clearance. A support mounting
face does not establish an intended rotating contact with the shaft. This is a
false exclusion, not a truthful J1 contact policy.

### Placement Authority

The support-frame pose is geometry-backed and generated placements replay from
the typed derivation chain. The realized positions make the false J1 exclusion
observable: support at z=0..5, frame at z=5, shaft-a/hub-a at z=15, and the
second shaft/hub at z=65. Thus placement replay confirms, rather than cures,
the pair-policy defect.

## CRIT-02 Re-Audit

### Restart Architecture

The remediation adds Phase A -> JSON bytes -> Phase B. Phase A creates candidate
CAD/M10, selection, promotion revision 2, primitive diagnostic snapshot, receipt
JSON, and locator JSON. Phase B accepts only `locator_path`, reloads JSON bytes,
constructs a fresh root, reloads revision 2, resolves durable artifacts/receipt,

### Restart Payload

The locator payload contains JSON strings and integers only: workspace/project and
configuration paths, receipt/snapshot paths, source revision/hash and source-byte
hash, promotion run/artifact IDs and hashes, ChangeSet ID, promoted revision/hash,
canonical mechanism ID/hash, compilation hash, and projection hash. It contains
no live candidate, CAD, bridge, M10, selection, application, store, model, or
dataclass object. Receipt crossing is through persisted JSON bytes as explicitly
required for fresh-root receipt verification, not a retained Python object.

### Candidate Leakage Audit

No Phase-A runtime object is an argument or closure input to Phase B. The Phase-B
agent raises if invoked and its invocation count is asserted zero. This proves no
agent call, and the fresh construction itself uses persisted state/artifacts.
The project ID is nevertheless ambient in `build_m134_application_at()` rather
than passed from the locator; this is a minor isolation weakness, not the primary
failure.

### Canonical Revision Binding

The locator explicitly stores promoted revision/state hash. Phase B loads exactly
that revision and recomputes `state_hash`; it does not select latest state or
revision 3. The accepted timeline remains revision 1 source, revision 2
promotion, then revision 3 stale mutation only after canonical revision-2 work.

### Semantic Snapshot

The persisted diagnostic snapshot now includes bodies/reference members, joint
endpoints/axis owner/sign/limits/home semantics, all pair classifications and
reasons, ordered configurations, placed transforms, inventory entries, and
representation fidelity.

It still omits required restart-equivalence categories: exact checked-pair scope,
volume and distance tolerances, generated-placement derivation semantics, and
member/body offset semantics. The richer accepted comparator is executed only in

### Canonical Construction Independence

Phase B does not read the semantic snapshot until after it has reconstructed the
canonical mechanism, realized canonical CAD, compiled the bridge, and executed
canonical M10. The snapshot is diagnostic only. Construction independence is
therefore proven in substance, but the required complete cross-boundary semantic
proof is not.

### Semantic Equivalence

Raw candidate/canonical CAD, bridge, request, and result hashes are not compared.
The accepted semantic comparator is used in the main test. The persisted Phase-B
comparison is incomplete for the reasons above, so it cannot close CRIT-02.

## IMP-01 Re-Audit

### Original Compilation

The capstone observes exactly one production `compile_multi_joint()` call. It
does not assert full typed equality `receipt.compilation == observed_compilation`,
The existing M13-4P test proves the generic production contract, but this M13-4
capstone still lacks its required direct assertion.

### Promotion Lifecycle

The remediated test reloads decision/result artifacts, promotion run, and
invalidation; asserts `RUN_CREATED` and `REVISION_ADVANCED`; validates active
revision/state hash; and binds the ChangeSet ID and changed mechanism path. This
is a valid improvement. It does not eliminate the original-compilation omission.

### Fresh-Root Receipt Verification

The receipt round-trips through JSON, its nested records are rehydrated, and a
fresh root verifies it via exact decision-artifact location and persisted run
metadata. The test invokes fresh-root verification once; no second repeatability
assertion is present.

### Canonical Evidence

Canonical M10 Evidence is present and backend/provider/execution mode are checked.

## FreeCAD Runtime

With `MECHCAD_FREECADCMD` explicitly set, the executable exists and reports
FreeCAD 1.1.3. The focused live tests run through the configured subprocess
provider; no MCP-only or fake-provider path was credited.

## Candidate Live Route

Candidate CAD, M10-3, selection replay, production promotion revision 2, and
candidate evidence execute through `ProductionApplication`. Ordinary M10-3 stays

## Canonical Live Route

Phase B reconstructs revision 2, regenerates canonical CAD and bridge, and runs
canonical M10-3 through the fresh production root. This route is live but its
complete semantic and Evidence assertions remain incomplete.

## M10-4

The focused explicit cfg0 -> (J1=1, J2=1) path uses two checked pairs and real
FreeCAD. Candidate/canonical status remains `COLLISION_WITNESS`; no global
collision-free claim was found. The false `motor-r/shaft-a` intended-contact
exclusion does not alter the selected M10-4 pairs, but still invalidates the full
pair policy.

## M11

`M11_STATUS=UNRESOLVED` and `M11_ELIGIBLE=False` remain true. No material, load,

## Stale / Currentness Negatives

Revision 3 is created after canonical revision-2 execution. Candidate CAD and
selection then fail via existing currentness semantics. Trusted source-byte

## Test Quality

No whole-route monkeypatch, fake ChangeEngine, fake StateManager, fabricated
Observation hooks remain narrow. The principal quality failures are the false
physical exclusion and omitted required cross-boundary assertions.

## Focused Remediation Selectors

```text
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k serialized_restart
1 passed, 2 deselected in 82.49s

py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k canonical_restart
1 passed, 2 deselected in 82.45s
```

Both selectors execute the same serialized restart test; the names do not prove

## Focused M13-4 Gate

```text
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -rs
3 passed in 206.82s
exit status: 0
M13_4_REQUIRED_SKIPS = 0
```

## M13-4P Regression

```text
8 passed in 14.05s; exit status 0
```

## M13-4E Regression

```text
116 passed in 134.17s; exit status 0
```

## Predecessor Regression

```text
75 passed in 37.55s; exit status 0
```

## Required M10/M12/CAD Regression

The exact execution-plan group was run with FreeCAD configured:

```text
757 passed in 386.88s; exit status 0
```

## Full Suite

```text
py -3 -m pytest -q -rs
2831 passed, 25 skipped in 3613.79s; exit status 0
```

## Skip Audit

The 25 skips are only optional OpenCode live validation (6), unavailable materials

## Static / Protected Surface

`py -3 -m compileall -q src tests` and `git diff --check` pass. The active M13-4

## New Findings

### CRITICAL

- **M13-4-REAUDIT-CRIT-01: false intended-contact exclusion remains in the complete physical pair policy.**
  - Requirement: every excluded physical pair must be semantically truthful and backed by declared interface/contact authority.
  - Evidence: support plate z=0..5 and shaft-a z=15..65 are derived at `m13_4_acceptance_fixtures.py:915-977`; nevertheless lines 700-703 classify `motor-r/shaft-a` as intended contact.
  - Affected symbol: `_physical_realization`.
  - Impact: M13-4 does not have a truthful complete 15-pair physical universe.
  - Minimal remediation: fixture/test only. Make the geometry/contact authority truthful or classify this cross-body pair for clearance; do not change production semantics.

- **M13-4-REAUDIT-CRIT-02: serialized semantic snapshot omits required construction-equivalence facts.**
  - Requirement: the Phase-A/Phase-B diagnostic equivalence must cover exact scope, tolerances, offsets, and placement-derivation semantics.
  - Evidence: `_semantic_snapshot` at test lines 95-194, used by Phase B at lines 1163-1179, contains none of those fields.
  - Affected symbol: `_semantic_snapshot` and `_phase_b_verify_from_locator`.
  - Impact: hard restart is present but does not prove complete candidate/canonical semantic equivalence across it.
  - Minimal remediation: fixture/test only. Add primitive fields to the persisted diagnostic snapshot and compare them after canonical construction; do not use them as construction input.

### IMPORTANT

- **M13-4-REAUDIT-IMP-01: capstone-specific original-compilation and canonical-Evidence proof remains incomplete.**
  - Requirement: assert receipt equals the single original compilation in full, and verify full canonical Evidence bindings/currentness through accepted production APIs.
  - Evidence: test lines 471-556 do not compare full receipt compilation/projection/mapping; Phase-B lines 1154-1161 assert only evidence presence/provider/execution mode.
  - Impact: M13-4 cannot independently prove all required promotion and canonical Evidence facts.
  - Minimal remediation: M13-4 test only.

### MINOR

- Phase B composes through the fixture's module-level `PROJECT_ID` rather than
  passing locator project ID to the builder.

### NOTES

- The former manufacturer-labelled supplied authority and fixture-local generated
  dimensions were materially repaired.
- Passing live and regression gates do not make a false pair exclusion truthful.

## Prior Finding Adjudication

```text
M13-4-CRIT-01 = REPLACED_BY_NEW_FINDING
M13-4-CRIT-02 = OPEN
M13-4-IMP-01  = OPEN
```

CRIT-01's original fabricated authority is closed, but the required truthful pair

## Acceptance Decision

The runtime and all required test gates pass. Acceptance requires truthful pair

```text
M13_4_INDEPENDENT_REAUDIT_REJECTED
M13_4_ACCEPTANCE_STATUS = REJECTED
```

## Downstream Authorization

```text
ROTATOR_V2_MAY_RESUME = NO
```
