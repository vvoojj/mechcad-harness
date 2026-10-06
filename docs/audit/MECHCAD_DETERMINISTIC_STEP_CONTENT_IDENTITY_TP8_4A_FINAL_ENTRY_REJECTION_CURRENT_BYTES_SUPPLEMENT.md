# Deterministic STEP Content Identity — T-P8.4a Final-Entry Rejection Supplement

## Authority and current bytes

- Accepted Spec SHA-256: `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.
- Controlling Plan SHA-256: `291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679`.
- HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807` (worktree changes uncommitted).
- Current application implementation SHA-256: `E9E9E830AA839C2D087D6BC479964C254C4337176D0289A58F284DA6E90993F9`.
- Current test SHA-256: `2B37BC13D4B8738CF40239DA2F985D2736F79C19793B4E28EC405630093D0EE2`.

This additive supplement records the exact missing post-activation negative-path
execution identified by the first separate final audit. No implementation or accepted
Plan/Spec bytes changed for this gate.

## T-P8.4a final construction entrypoint rejection

Command:

```text
py -3 -m pytest tests/integration/test_entry_boundary_remediation.py::test_final_entry_rejects_at1_before_any_production_operation -v --tb=short -p no:randomly
```

Result:

```text
1 passed, 1 warning in 3.07s
```

The test exercises `ProductionApplication`'s final construction entrypoint with a
request@1 and verifies it rejects before invoking production operations. The warning is
the existing fixture serializer warning for `GeometrySourceReference` values in
`yagi_payload_carrier_requirements`; it was not suppressed.

The earlier audit's missing-execution-evidence finding is now covered by this fresh run.
This supplement itself makes no independent acceptance claim; the separate final Epic
audit remains required.
