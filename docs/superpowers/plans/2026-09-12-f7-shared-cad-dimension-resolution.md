# F7 Shared CAD Dimension Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate candidate-versus-canonical legacy mounting-plate CAD dimension divergence through one alias-agreement contract.

**Architecture:** A dependency-leaf resolver owns one unordered alias set for `length_mm`, `width_mm`, and `thickness_mm`, and resolves normalized input records per component instance and semantic dimension. Candidate and canonical CAD remain separate stages: each adapts only its own record representation into the resolver; candidate construction gains an early agreement gate and canonical CAD keeps resolver-level defense in depth.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, existing MechCAD CAD-program models.

## Global Constraints

- Modify only F7-relevant production, test, and authorized audit documentation files.
- Preserve Python 3.11+, Pydantic v2, UTC-aware datetime requirements, and existing unambiguous candidate/canonical wire and hash behavior.
- Do not modify `docs/reconstruction/**`.
- Do not merge `candidates/cad_realization.py` and `candidates/canonical_cad.py`, and do not allow canonical CAD to consume candidate CAD artifacts.
- The alias contract defines an unordered canonical alias set; ordering is diagnostic-only and never semantic precedence.
- Agreement is checked per component instance and semantic dimension; direct normalized millimeter values use exact equality.
- Do not add defaults, unit conversion, tolerance semantics, or generated-part behavior.
- Preserve unrelated dirty work and create exactly one final local commit: `refactor(cad): unify dimension resolution`.

---

### Task 1: Blocking Compatibility Checkpoint and Resolver Contract Tests

**Files:**
- Create: `tests/unit/test_f7_dimension_resolution.py`
- Inspect: `tests/unit/test_m12_candidate_cad_compiler.py`
- Inspect: `tests/unit/test_m12_canonical_cad.py`
- Inspect: `tests/unit/test_m13_2_candidate_cad_integration.py`
- Inspect: accepted fixtures and golden tests under `tests/unit/` and `tests/integration/`

**Interfaces:**
- Produces the blocking compatibility decision required before semantic implementation.
- Defines the expected public core API:
  `DimensionInput(component_instance_id: str, semantic_name: str, alias: str, value: float, unit: str, identity: str)` and
  `resolve_dimensions(inputs: Iterable[DimensionInput], required_dimensions: Iterable[str]) -> dict[tuple[str, str], ResolvedDimension]`.
- `ResolvedDimension` exposes `value: float` and `identities: tuple[str, ...]`.

- [ ] **Step 1: Search accepted, golden, and persisted fixtures for ambiguous legacy plate aliases**

Run these commands and inspect every match that places more than one of the three aliases in one component specification or combines a matching property with a scoped design variable/accepted choice:

```powershell
rg -n -U 'geometry\.(length_mm|width_mm|thickness_mm)[\s\S]{0,120}(plate_(length_mm|width_mm|thickness_mm)|(length_mm|width_mm|thickness_mm))' tests docs/audit
rg -n 'geometry\.(length_mm|width_mm|thickness_mm)|plate_(length_mm|width_mm|thickness_mm)' tests docs/audit
rg -n '(^|[.])?(length_mm|width_mm|thickness_mm)' tests/unit/test_m12* tests/unit/test_m13* tests/integration/test_m12* tests/integration/test_m13*
```

Expected: no accepted/golden/persisted fixture carries contradictory values for one component instance and one semantic plate dimension. If any ambiguous persisted or accepted fixture is found, stop here. Record its exact path, classification, values, and authority status; do not implement semantic changes until the user supplies a compatibility policy.

- [ ] **Step 2: Write failing resolver contract tests**

Create `tests/unit/test_f7_dimension_resolution.py` with exact direct-input tests. The tests must use two component IDs to prove that agreement is scoped rather than global:

```python
import pytest

from mechcad_harness.candidates.dimensions import (
    DimensionConflictError,
    DimensionInput,
    resolve_dimensions,
)


def _input(component_id, semantic_name, alias, value, identity):
    return DimensionInput(
        component_instance_id=component_id,
        semantic_name=semantic_name,
        alias=alias,
        value=value,
        unit="mm",
        identity=identity,
    )


def test_conflicting_aliases_fail_without_alias_precedence():
    with pytest.raises(DimensionConflictError, match="mount.*length_mm"):
        resolve_dimensions(
            (
                _input("mount", "length_mm", "geometry.length_mm", 100.0, "property:geometry"),
                _input("mount", "length_mm", "length_mm", 30.0, "property:bare"),
            ),
            required_dimensions=("length_mm",),
        )


def test_equal_aliases_resolve_one_value_and_all_identities():
    resolved = resolve_dimensions(
        (
            _input("mount", "length_mm", "geometry.length_mm", 100.0, "property:geometry"),
            _input("mount", "length_mm", "length_mm", 100.0, "choice:bare"),
        ),
        required_dimensions=("length_mm",),
    )

    assert resolved[("mount", "length_mm")].value == 100.0
    assert resolved[("mount", "length_mm")].identities == ("choice:bare", "property:geometry")


@pytest.mark.parametrize(
    ("semantic_name", "aliases"),
    (
        ("length_mm", ("geometry.length_mm", "plate_length_mm", "length_mm")),
        ("width_mm", ("geometry.width_mm", "plate_width_mm", "width_mm")),
        ("thickness_mm", ("geometry.thickness_mm", "plate_thickness_mm", "thickness_mm")),
    ),
)
def test_every_legacy_plate_alias_family_requires_agreement(semantic_name, aliases):
    with pytest.raises(DimensionConflictError):
        resolve_dimensions(
            tuple(
                _input("mount", semantic_name, alias, float(index + 1), f"value:{alias}")
                for index, alias in enumerate(aliases)
            ),
            required_dimensions=(semantic_name,),
        )


def test_values_for_different_component_instances_do_not_conflict():
    resolved = resolve_dimensions(
        (
            _input("mount-a", "length_mm", "length_mm", 30.0, "a"),
            _input("mount-b", "length_mm", "length_mm", 100.0, "b"),
        ),
        required_dimensions=("length_mm",),
    )

    assert resolved[("mount-a", "length_mm")].value == 30.0
    assert resolved[("mount-b", "length_mm")].value == 100.0
```

Adjust the last assertion only if the selected API returns results keyed by `(component_instance_id, semantic_name)`; the final API must retain both scopes and the test must assert both values.

- [ ] **Step 3: Run the new tests to verify the missing module fails**

Run: `pytest tests/unit/test_f7_dimension_resolution.py -q`

Expected: collection failure because `mechcad_harness.candidates.dimensions` does not exist.

- [ ] **Step 4: Record the checkpoint result in the implementation notes**

If no ambiguous authority fixture exists, record the exact commands and zero-conflict result for the final audit remediation append. Do not change an accepted fixture or regenerate a golden file.

### Task 2: Implement the Neutral Dimension Resolver

**Files:**
- Create: `src/mechcad_harness/candidates/dimensions.py`
- Modify: `tests/unit/test_f7_dimension_resolution.py`

**Interfaces:**
- Consumes: normalized `DimensionInput` records only.
- Produces: `LEGACY_PLATE_DIMENSION_ALIASES`, `DimensionInput`, `ResolvedDimension`, `DimensionResolutionError`, `DimensionConflictError`, and `resolve_dimensions`.
- `resolve_dimensions` must return results keyed by `(component_instance_id, semantic_name)` so one call can validate multiple components without conflation.

- [ ] **Step 1: Add the minimal resolver types and immutable alias contract**

Implement the dependency-leaf module with standard-library `dataclass` types and no imports from candidate models, canonical models, promotion, CAD compilation, application, or runtime code:

```python
LEGACY_PLATE_DIMENSION_ALIASES = {
    "length_mm": frozenset({"geometry.length_mm", "plate_length_mm", "length_mm"}),
    "width_mm": frozenset({"geometry.width_mm", "plate_width_mm", "width_mm"}),
    "thickness_mm": frozenset({"geometry.thickness_mm", "plate_thickness_mm", "thickness_mm"}),
}


@dataclass(frozen=True)
class DimensionInput:
    component_instance_id: str
    semantic_name: str
    alias: str
    value: float
    unit: str
    identity: str


@dataclass(frozen=True)
class ResolvedDimension:
    value: float
    identities: tuple[str, ...]
```

Validate nonblank IDs/names/aliases/identities, membership in the semantic alias set, `unit == "mm"`, and finite positive non-boolean numeric values. Raise `DimensionResolutionError` for invalid inputs and `DimensionConflictError` for unequal values.

- [ ] **Step 2: Implement scoped, order-independent agreement**

Group inputs by `(component_instance_id, semantic_name)`. For each group, sort only for deterministic diagnostics and identity output. Compare every value to the first sorted value with exact `==`; if any differs, raise `DimensionConflictError` naming the component and semantic dimension. Never use alias or source ordering to select a value. Require each requested semantic dimension for every component represented by the call; raise `DimensionResolutionError` when unavailable.

- [ ] **Step 3: Add invalid-input tests**

Add parameterized invalid cases for an unknown alias, non-`mm` unit, zero, `float("nan")`, and `True`; each must raise `DimensionResolutionError`.

- [ ] **Step 4: Run resolver tests**

Run: `pytest tests/unit/test_f7_dimension_resolution.py -q`

Expected: PASS.

### Task 3: Add the Early Candidate Agreement Gate and Candidate Adapter

**Files:**
- Modify: `src/mechcad_harness/candidates/models.py:1066-1107`
- Modify: `src/mechcad_harness/candidates/cad_realization.py:101-110, 773-813`
- Modify: `tests/unit/test_m12_candidate_cad_compiler.py`
- Modify: `tests/unit/test_f7_dimension_resolution.py`

**Interfaces:**
- Consumes: `resolve_dimensions` and `LEGACY_PLATE_DIMENSION_ALIASES` from `candidates.dimensions`.
- Produces: candidate-model rejection of conflicting legacy plate dimensions and `CandidateCadRealizationService._generated_dimensions` values/identities derived from the shared resolver.

- [ ] **Step 1: Write failing candidate-boundary regressions**

Add a helper that builds a `mount` `ComponentSpecificationSnapshot` from explicit property tuples. Add a parameterized test for each semantic dimension that constructs two otherwise valid aliases with values `100.0` and `30.0` and asserts candidate construction fails:

```python
with pytest.raises(ValidationError, match="mount.*length_mm"):
    _candidate(state, specification=conflicting_specification)
```

Add a separate property-versus-design-variable test using:

```python
CandidateDesignVariable(name="mount.length_mm", value=30.0)
```

with the property `geometry.length_mm = 100.0`; assert candidate construction fails. Include equal duplicate values and assert candidate creation succeeds.

- [ ] **Step 2: Run candidate regressions to verify they fail before implementation**

Run: `pytest tests/unit/test_m12_candidate_cad_compiler.py -q`

Expected: FAIL because `MechanicalDesignCandidate` currently accepts conflicting aliases and source values.

- [ ] **Step 3: Implement candidate-neutral input collection at the candidate boundary**

In `models.py`, add a small private helper near `MechanicalDesignCandidate` that:

- maps each physical component instance to its specification;
- skips a specification with `generated_part` or `geometry_source`, and skips component types outside the legacy plate set (`fixture`, `mount`, `support-mount`, `driven-body`);
- emits one `DimensionInput` for each available property whose key is in the resolver alias set, using its normalized `mm` value and `property_hash` identity;
- emits one `DimensionInput` for each currently supported scoped variable spelling, using the semantic dimension spelling and identity `candidate:design-variable:<name>`;
- calls `resolve_dimensions` with all three required legacy dimensions for that instance.

Call this helper from `MechanicalDesignCandidate.validate_candidate` after specification/component and design-variable uniqueness checks, before candidate hash calculation. Convert resolver exceptions to `ValueError` without changing the persisted model shape.

- [ ] **Step 4: Replace candidate CAD alias precedence with the shared adapter**

Remove `CandidateCadRealizationService._DIMENSION_ALIASES`. In `_generated_dimensions`, construct the same normalized `DimensionInput` records from its candidate property and scoped-variable sources, call `resolve_dimensions` for the one physical instance, and return values plus deterministic resolver identities. Preserve current `None` behavior only for missing/unavailable/invalid non-conflicting dimensions; resolver conflicts must become `CandidateCadIntegrityError` through the existing boundary.

- [ ] **Step 5: Verify candidate tests and unambiguous output**

Run: `pytest tests/unit/test_m12_candidate_cad_compiler.py tests/unit/test_m12_candidate_cad_replay.py -q`

Expected: PASS, including existing assertion that a single `geometry.*` property produces the same plate dimensions.

### Task 4: Use the Resolver in Canonical CAD Without Reusing Candidate Artifacts

**Files:**
- Modify: `src/mechcad_harness/candidates/canonical_cad.py:41-46, 604-673`
- Modify: `tests/unit/test_m12_canonical_cad.py`
- Modify: `tests/unit/test_f7_dimension_resolution.py`

**Interfaces:**
- Consumes: `resolve_dimensions` and resolver input types from `candidates.dimensions`.
- Produces: `CanonicalPhysicalCadCompiler._compile_generated` that resolves legacy plate dimensions using the shared core and raises `CanonicalCadIntegrityError` on disagreement.

- [ ] **Step 1: Write failing canonical tests for single aliases, equal aliases, and conflicts**

Extend the canonical fixture builder to accept property and accepted-choice tuples. Parameterize every semantic dimension and its three aliases. For each family:

- construct one canonical record with one accepted choice and assert the existing expected plate base dimensions;
- construct equal property and choice aliases and assert canonical CAD succeeds;
- construct a `geometry.<dimension>` property at `100.0` and a matching canonical accepted choice at `30.0`, then assert:

```python
with pytest.raises(CanonicalCadIntegrityError, match="mount-1.*length_mm"):
    CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)
```

The tests must directly construct/reconstruct canonical data so they prove defense in depth without candidate CAD invocation.

- [ ] **Step 2: Run canonical regressions to verify current precedence is observable**

Run: `pytest tests/unit/test_m12_canonical_cad.py -q`

Expected: the conflict tests fail because canonical CAD currently chooses accepted choices before properties.

- [ ] **Step 3: Replace canonical alias/source precedence with shared resolution**

Remove module `_DIMENSION_ALIASES`. In `CanonicalPhysicalCadCompiler._compile_generated`, collect all matching accepted design choices and specification properties for each instance and semantic dimension into `DimensionInput` records. Keep the current accepted-choice key forms as collection forms, but do not use their discovery order as precedence. Require all three dimensions via `resolve_dimensions`, use only its resolved values and sorted identities to construct `MountingPlateDesignSpec`, and translate resolution errors to `CanonicalCadIntegrityError`.

- [ ] **Step 4: Confirm canonical independence remains explicit**

Keep and run `test_canonical_compiler_does_not_invoke_candidate_cad`. It must pass unchanged, proving canonical CAD shares semantic code only and never treats candidate CAD artifacts or services as authority.

- [ ] **Step 5: Run canonical tests**

Run: `pytest tests/unit/test_m12_canonical_cad.py tests/unit/test_m12_canonical_m10.py -q`

Expected: PASS.

### Task 5: Promotion Equivalence, Generated-Part Regression, and Audit Record

**Files:**
- Modify: `tests/unit/test_m12_promoted_verification.py` or `tests/unit/test_m12_promotion_compiler.py`
- Modify: `tests/unit/test_m13_2_candidate_cad_integration.py`
- Modify: `docs/audit/MECHCAD_LOGIC_DUPLICATION_AUDIT.md`
- Modify: `docs/audit/MECHCAD_CAPABILITY_OWNERSHIP_MAP.md`

**Interfaces:**
- Consumes: candidate/canonical resolver outputs and existing promotion compiler/reconstruction fixtures.
- Produces: high-level evidence that promotion preserves unambiguous dimensions, generated parts remain unaffected, and audit state records actual F7 remediation.

- [ ] **Step 1: Write the promoted candidate/canonical equivalence test**

Using an existing successful promotion fixture, create an unambiguous legacy plate candidate whose three dimensions come from one supported spelling. Realize candidate CAD, promote/reconstruct it through the existing flow, then realize canonical CAD. Extract the mounting plate base operation from each assembly and assert:

```python
assert (
    candidate_base.length_mm,
    candidate_base.width_mm,
    candidate_base.thickness_mm,
) == (
    canonical_base.length_mm,
    canonical_base.width_mm,
    canonical_base.thickness_mm,
)
```

Do not compare realization, request, or assembly hashes; those remain intentionally stage-specific.

- [ ] **Step 2: Write the generated-part non-regression test**

Use the existing M13-2 fixture with a generated shaft, hub, or frame member. Run candidate and canonical generated-part compilation and assert its established generated program parameters and geometry-definition identities. Do not feed legacy plate aliases into generated-part data and do not change generated-part models.

- [ ] **Step 3: Run promotion and generated-part tests**

Run: `pytest tests/unit/test_m12_promoted_verification.py tests/unit/test_m12_promotion_compiler.py tests/unit/test_m13_2_candidate_cad_integration.py tests/unit/test_m13_2_promotion_canonical_roundtrip.py -q`

Expected: PASS.

- [ ] **Step 4: Append the audit remediation evidence after tests pass**

Append a dated `F7 Remediation Record (post-acceptance)` to `MECHCAD_LOGIC_DUPLICATION_AUDIT.md`; do not rewrite the historical F7 finding. Record the core path/API, the three legacy plate families, exact-alias-agreement policy, candidate gate, canonical defense, fixture-search result, test commands/results, and excluded findings.

Update only the F7/current-owner row in `MECHCAD_CAPABILITY_OWNERSHIP_MAP.md` to name `candidates/dimensions.py` as the shared semantic authority and mark candidate/canonical CAD as stage-specific adapters. Do not claim unrelated findings are resolved.

### Task 6: Regression Sweep, Repository Search, Independent Review, and One Commit

**Files:**
- Modify only files already changed by Tasks 1-5, if verification reveals an F7 defect.

**Interfaces:**
- Consumes: completed implementation and test evidence.
- Produces: a reviewed F7 remediation commit with no unaddressed F7 regression.

- [ ] **Step 1: Search for remaining duplicated semantic alias tables**

Run:

```powershell
rg -n '_DIMENSION_ALIASES|geometry\.length_mm|plate_length_mm|geometry\.width_mm|plate_width_mm|geometry\.thickness_mm|plate_thickness_mm' src tests
```

Expected: the only legacy plate alias authority is `candidates/dimensions.py`; candidate/canonical files contain adapter collection logic only. Document any remaining alias reference as a fixture or a justified non-F7 capability.

- [ ] **Step 2: Run focused F7 and affected candidate/promotion/CAD suites**

Run:

```powershell
pytest tests/unit/test_f7_dimension_resolution.py -q
pytest tests/unit/test_m12_candidate_cad_compiler.py tests/unit/test_m12_candidate_cad_replay.py tests/unit/test_m12_canonical_cad.py tests/unit/test_m12_canonical_m10.py tests/unit/test_m12_promoted_verification.py tests/unit/test_m12_promotion_compiler.py tests/unit/test_m13_2_candidate_cad_integration.py tests/unit/test_m13_2_promotion_canonical_roundtrip.py -q
```

Expected: PASS. Capture exact pass counts from the actual commands.

- [ ] **Step 3: Run the full unit suite and repository suite**

Run:

```powershell
pytest tests/unit -q
pytest -q
git diff --check
```

Expected: unit suite and full suite PASS. If the known FreeCAD integration hang blocks `pytest -q`, record the exact command, timeout/hang evidence, affected test boundary, and comparison with a pre-change baseline invocation; do not call it a baseline issue without that evidence.

- [ ] **Step 4: Perform an independent skeptical review in a fresh context**

Ask a fresh reviewer to disprove all ten required claims: one authority; independent stages; no silent conflicts; equal aliases accepted; unchanged unambiguous behavior; all three families covered; promotion cannot reintroduce ambiguity; generated parts unaffected; no dependency cycle; and no false claim that F1/F3/F4/F5/F6/F8/F11 were resolved. Correct every confirmed defect and rerun the relevant focused tests before proceeding.

- [ ] **Step 5: Inspect the final diff and commit only F7 files**

Run:

```powershell
git status --short
git log --oneline -10
```

Stage only the files actually modified for F7, never use `git add .` or `git add -A`, then create the one authorized local commit:

```powershell
git add -- <exact F7 production, test, audit, spec, and plan paths>
git commit -m "refactor(cad): unify dimension resolution"
```

Expected: one local F7 remediation commit; no push.

## Plan Self-Review

- Spec coverage: Tasks 1-4 establish the blocking fixture policy, neutral unordered alias contract, candidate gate, and canonical defense. Task 5 covers promotion, M13-2 non-regression, and authorized audit updates. Task 6 covers the required searches, suites, independent review, diff check, and one-commit policy.
- Placeholder scan: no deferred implementation placeholders or unspecified test commands remain. The compatibility checkpoint intentionally stops implementation when an accepted ambiguous artifact is found, as required.
- Type consistency: the resolver types and API are introduced in Task 2 and consumed by Tasks 3-4; the key includes component and semantic scopes throughout.
