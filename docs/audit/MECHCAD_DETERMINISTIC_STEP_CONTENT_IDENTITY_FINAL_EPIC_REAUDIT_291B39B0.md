# Deterministic STEP Content Identity — Final Epic Re-Audit (Normalized Test Bytes)

## Disposition

```text
Epic: Deterministic STEP Content Identity
Independent verdict: ACCEPT WITH FINDINGS
Accepted Spec SHA-256: DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68
Controlling Plan SHA-256: 291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679
Observed HEAD: 05da8edad18488492f02be1dad9d1ec3653ce807
```

This is an additive, faithful record of the independent re-audit after normalizing
`tests/unit/test_semantic_family_closure.py` line endings for the authorized commit
check. It does not alter the earlier final acceptance record or the E449-bound historical
record. The independent auditor judged the exact current byte state acceptable with the
findings below. No commit, push, tag, release, or deployment had occurred during the
audit.

## Current byte reconciliation

The final auditor recomputed and matched the Spec, Plan, HEAD, production source, test,
protected-pin, and audit-record hashes. In particular:

```text
src/mechcad_harness/application.py
  E9E9E830AA839C2D087D6BC479964C254C4337176D0289A58F284DA6E90993F9
src/mechcad_harness/candidates/services.py
  6D33640FCFFED213FB1F71C1A7B30091AB79AEB76B3D3037C2DA5F8D8C8D02B3
src/mechcad_harness/backends/gearworks_cad.py
  F67ECB7787D9C421A68F0F6465CB88606BFBDC3A75D5F2640434314AE2C75321
src/mechcad_harness/candidates/provenance_artifacts.py
  D06EE2B54E7A175459612F347DF16F2E8B73D77F2F26424F4FA374B1ABD864CE
tests/unit/test_semantic_family_closure.py
  834ED73B0040F6B32720ED32EDA9291167E652A79845FCD4A8D6E0AFAE8CBF02
```

The aggregate test is now LF in both index and worktree (`git ls-files --eol` reports
`i/lf w/lf`). The commit-normalization supplement
`MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_COMMIT_EOL_NORMALIZATION_SUPPLEMENT.md`
is SHA-256 `AF2729A2DD210C6D7491978D1D96BF1EE46F3673958C71293A480F3A06CC32D9`.

## Verification of the normalized test

```text
py -3 -m pytest tests/unit/test_semantic_family_closure.py -q --tb=short -p no:randomly
132 passed in 130.26s

git diff --cached --check
passed

py -3 -m compileall -q src/mechcad_harness tests/unit/test_semantic_family_closure.py
passed
```

The line-ending normalization and one comment punctuation adjustment did not change
test logic. The final auditor judged the focused rerun sufficient for this formatting-only
test-byte change and found no Epic gate blocker.

## Gate status and retained findings

The independent auditor reconfirmed **ACCEPT WITH FINDINGS** for the current Plan bytes.
The currentness supplementation, GearWorks G2 correction, homogeneous M12-5 legacy
fixture family, canonical CAD/M10 provenance@2 paths, M10@2 parent coordinate guard,
post-activation integration suites, final-entry request@1 rejection, T-P8.3 live evidence,
and six protected pins were accepted within their recorded bounded scope.

All four original findings remain unchanged in substance:

1. **Stale evidence SHA citation:** a T-P7.2 citation names
   `F337DFF9DB33A581993DBFBE914114DFBBAD433F94DF147DC49B05BB8B6FC470`, which does not
   resolve to a repository artifact. The current supplement is
   `MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP7_2_CANONICAL_PROVENANCE_V2_CURRENT_BYTES_SUPPLEMENT.md`
   at `29E2CAD7EADBF861850D11CCEE2055097465D5A4355823B5F8E5CDF21BA5B364`; its recorded
   203-test count is stale versus the verified 204-test result.
2. **P8.2 broad suite not rerun on exact final provenance bytes:** the selected broad
   run recorded 2439 passed, 1 skipped, 866 deselected after excluding exactly two
   failures. Neither failure is called pre-existing. The focused final provenance batch
   and post-activation integration suites passed on later bytes; the broad P8.2 command
   was not repeated on those exact final provenance bytes.
3. **Older records reference the superseded Plan:** E449-bound gate/acceptance records
   remain historical. Current acceptance is bound to Plan `291B39B0…`.
4. **Superseded fixture hashes remain in older evidence:** older final-gate evidence
   retains fixture hashes that no longer match later accepted fixture bytes; those
   records were not rewritten.

The two P8.2 failures remain named in the earlier final acceptance record; neither is
claimed pre-existing. The R-P5.M10 historical pre/post equality remains **NOT PROVEN**;
the original equality clause remains **NOT EXECUTED**. Prospective replacement evidence
does not change that historical fact.

No release/deployment status is established. This record does not authorize or claim
release.
