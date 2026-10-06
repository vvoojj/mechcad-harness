# M13-1 Task 1 Implementation Report

Date: 2026-09-01
Status: implemented and left uncommitted

## Scope

Implemented the lower-level shared component-property enum owner and geometry
artifact identity helpers required by M13-1 Task 1. Existing candidate and
canonical import paths remain available through bindings to the shared enum
classes. No M10/M11 behavior, `projects/rotator_v2`, or unrelated generated
files were modified.

## TDD Evidence

1. Added the two focused test modules before production changes:
   - `tests/unit/test_m13_geometry_identity.py`
   - `tests/unit/test_m13_authority_enum_compatibility.py`
2. Ran the required RED command:
   - Command: `py -3 -m pytest tests/unit/test_m13_geometry_identity.py tests/unit/test_m13_authority_enum_compatibility.py -q`
   - Result: failed during collection with the intended missing-module errors for `mechcad_harness.models.geometry_identity` and `mechcad_harness.models.component_property`.
3. Added the minimal implementation and enum bindings.
4. Ran the focused GREEN command:
   - Command: `py -3 -m pytest tests/unit/test_m13_geometry_identity.py tests/unit/test_m13_authority_enum_compatibility.py -q`
   - Result: `5 passed in 1.98s`.
5. Ran the relevant M12 regression tests:
   - Command: `py -3 -m pytest` with all 28 `tests/unit/test_m12_*.py` files listed explicitly.
   - Result: `477 passed in 88.40s`.
6. Ran compilation verification:
   - Command: `py -3 -m compileall -q src/mechcad_harness`
   - Result: clean, no output, exit code 0.
7. Ran tracked-file whitespace verification:
   - Command: `git diff --check -- src/mechcad_harness/candidates/models.py src/mechcad_harness/models/physical_mechanism.py`
   - Result: no whitespace errors. Git emitted only its existing LF-to-CRLF normalization warnings.

## Changed Files

- `src/mechcad_harness/models/component_property.py`: added the single shared owner for `ComponentPropertyAvailability` and `ComponentPropertyAuthority`.
- `src/mechcad_harness/models/geometry_identity.py`: added `GeometryArtifactIdentity`, canonical identity hashing, legacy reference hash projection, and candidate/canonical geometry reference projections.
- `src/mechcad_harness/candidates/models.py`: replaced local component-property enum declarations with imports from the shared owner.
- `src/mechcad_harness/models/physical_mechanism.py`: replaced canonical enum declarations with aliases to the shared enum owner.
- `tests/unit/test_m13_geometry_identity.py`: added identity, hashing, projection-source, validation, and serialization tests.
- `tests/unit/test_m13_authority_enum_compatibility.py`: added class-identity and serialized-value compatibility tests.
- `.superpowers/sdd/task-1-report.md`: this implementation report.

## Self-Review

- `GeometryArtifactIdentity` is frozen and forbids extra fields.
- Artifact hashes require the `sha256:` prefix and 64 lowercase hexadecimal characters.
- Artifact and source identities reject blank strings; coordinate-system IDs reject non-`None` blank strings.
- The semantic identity hash covers exactly the five specified geometry identity fields and excludes the self-hash field.
- `reference_hash_payload` removes `reference_hash` and omits a `None` coordinate-system ID, preserving the legacy hash rule.
- Candidate and canonical enum imports resolve to the same class objects and retain the original serialized values.
- Existing model schemas and existing M10/M11 behavior were not changed.
- No commit, tag, or push was created.

## Concerns

- The `m13=True` candidate projection branch intentionally expects the
  coordinate-system and reference-hash fields that later M13 tasks add to the
  candidate reference model; the current focused tests exercise the legacy
  reference shape and identity helpers only.
- The full repository test suite was not run; the requested focused M13 tests,
  all M12 unit regressions, and source compilation were run successfully.
- The first attempted M12 wildcard command was not expanded by PowerShell and
  ran no tests; it was immediately rerun with all 28 test paths explicitly
  listed and passed.

## M13-3P Task 1: Rigid Transform Agreement

Date: 2026-09-04
Status: implemented and left uncommitted

### Scope

Implemented the frozen pure-Python `rigid-transform-agreement@1.0` policy and
predicate in `multi_joint_kinematics.py`. The implementation adds the required
constant-backed frozen dataclass, uses the shared `normalize_quaternion`
helper, rejects unsupported policy versions, checks all raw translation and
quaternion values for finiteness before normalization, and applies the fixed
inclusive translation and sign-invariant quaternion-angle bounds. Existing
`CadRigidTransform`, transform helpers, serialization, and v1 hashes were not
changed.

### TDD Evidence

1. Added the focused agreement tests before production edits:
   - `tests/unit/test_m13_3p_rigid_body_groups.py`
2. Ran the required RED command before adding the implementation:
   - Command: `py -3 -m pytest tests/unit/test_m13_3p_rigid_body_groups.py -k transform_agreement -v`
   - Result: collection failed because `RIGID_TRANSFORM_AGREEMENT_POLICY` was
     not exported by `multi_joint_kinematics.py`.
3. Added the minimal production implementation.
4. The first GREEN run found a test-only expected-metric-name typo: 9 tests
   passed and the policy assertion failed. The test expectation was corrected
   to the exact specification strings.
5. Ran the focused GREEN command:
   - Command: `py -3 -m pytest tests/unit/test_m13_3p_rigid_body_groups.py -k transform_agreement -v`
   - Result: `10 passed in 0.60s`.
6. Ran the immutable Task 0 golden suite:
   - Command: `py -3 -m pytest tests/unit/test_m13_3p_legacy_goldens.py -v`
   - Result: `5 passed in 0.63s`.
7. Ran focused diff whitespace validation:
   - Command: `git diff --check -- src/mechcad_harness/multi_joint_kinematics.py tests/unit/test_m13_3p_rigid_body_groups.py`
   - Result: clean; Git emitted only its existing LF-to-CRLF normalization
     warning.

### Coverage

- Literal identity and materially incorrect placement.
- Arbitrary normalized-quaternion inverse/composition round trip.
- Observed floating reconstruction from inverse/composition.
- Quaternion sign equivalence (`q` versus `-q`).
- Non-finite model-constructed input returns `False`.
- Inclusive translation boundary at exactly `1e-9` mm and failure at the next
  representable value.
- Inclusive orientation boundary selected by bounded `math.nextafter` search
  using the production metric and failure at the next verified value.
- Frozen constant-backed policy values and unsupported policy-version rejection.

### Changed Files

- `src/mechcad_harness/multi_joint_kinematics.py`: added the Task 1 agreement
  policy, constants, and predicate.
- `tests/unit/test_m13_3p_rigid_body_groups.py`: added focused direct tests.
- `.superpowers/sdd/task-1-report.md`: appended this M13-3P Task 1 evidence;
  prior report content was retained.

### Concerns

- No implementation concerns remain for Task 1.
- The requested focused tests were run under Python 3.14.6 on Windows; the
  project declares Python 3.11 or newer.
- The full repository suite was not requested and was not run.
- Existing unrelated worktree changes remain untouched.
- No commit, tag, push, release, reset, stash, clean, checkout, revert, or
  discard was performed.

### Commit

none (user forbids commits)
