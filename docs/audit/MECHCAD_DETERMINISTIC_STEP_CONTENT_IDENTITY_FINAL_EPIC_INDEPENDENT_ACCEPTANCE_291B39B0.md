# Deterministic STEP Content Identity — Final Epic Independent Acceptance

## Disposition

```text
Epic: Deterministic STEP Content Identity
Disposition: ACCEPT WITH FINDINGS
Current controlling Plan: 291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679
Accepted Spec: DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68
Observed HEAD: 05da8edad18488492f02be1dad9d1ec3653ce807
```

This record faithfully records the separate final auditor's verdict on the exact
current controlling Plan and worktree. It does not upgrade the auditor's `ACCEPT WITH
FINDINGS` to a clean acceptance. It is not a release, deployment, or commit
authorization.

The older record
`MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_EPIC_INDEPENDENT_ACCEPTANCE.md` remains
unchanged historical evidence for Plan SHA `E449C60B641DBB5A4A630CC61553F5E586127443DC92B24BD5D983E3A15BB70E` and is not authority for this disposition.

## Evidence maturity

| Evidence level | Disposition | Basis |
|---|---|---|
| **DESIGNED** | Accepted | Current controlling Spec and Plan hashes above. |
| **IMPLEMENTED** | Verified in the worktree | Currentness exact-source supplementation, GearWorks timestamp conformance, homogeneous candidate/CAD/provenance families, canonical CAD/M10 @2 coordinate guard. Relevant current hashes are recorded below. |
| **TESTED** | Verified, bounded | Focused provenance/admission/currentness suites and the post-activation production-composition integrations listed below. |
| **PRODUCTION_COMPOSED** | Verified in scope | The final `ProductionApplication` candidate default and current services are exercised through the recorded composition and final-entry tests. No broader automatic synthesis capability is implied. |
| **RUNTIME_VERIFIED** | Verified, bounded | Post-activation tests cover final-entry request@1 rejection and exact @2 provenance resolution. |
| **LIVE_VERIFIED** | Verified, bounded | T-P8.3 and the five authorized candidate-CAD live tests used the real FreeCAD 1.1.3 command-line subprocess. No Gmsh, CalculiX, solver/mesh, or M11 structural execution is claimed. |
| **INDEPENDENTLY_ACCEPTED** | **ACCEPT WITH FINDINGS** | Separate final independent audit against Plan `291B39B0…`; findings F1–F4 below remain visible. |

## Current bytes and protected pins

Current relevant file hashes checked by the final independent audit:

```text
src/mechcad_harness/application.py
  E9E9E830AA839C2D087D6BC479964C254C4337176D0289A58F284DA6E90993F9
src/mechcad_harness/candidates/services.py
  6D33640FCFFED213FB1F71C1A7B30091AB79AEB76B3D3037C2DA5F8D8C8D02B3
src/mechcad_harness/backends/gearworks_cad.py
  F67ECB7787D9C421A68F0F6465CB88606BFBDC3A75D5F2640434314AE2C75321
src/mechcad_harness/candidates/provenance_artifacts.py
  D06EE2B54E7A175459612F347DF16F2E8B73D77F2F26424F4FA374B1ABD864CE
tests/integration/test_m12_candidate_cad_m10_production.py
  4A3C2D7F9DB10602AE1EE3722BFD4F08C6B7DAF2208178A7F6B48EEE117D3F7B
tests/integration/test_m12_promotion_production.py
  5D51401075EAC542F6E35FB7760178E3D10AF6D43A7036F6E376FDD09C8BBB02
tests/integration/test_entry_boundary_remediation.py
  2B37BC13D4B8738CF40239DA2F985D2736F79C19793B4E28EC405630093D0EE2
tests/integration/test_step_content_identity_live.py
  D880417FC08A2B6EF6E0BA9DACD7F1321B2907168256BF2DE35C6BFB690023E8
tests/unit/test_candidate_provenance_artifacts.py
  EF44C436A5B5E80D434A6F85DCFAA2DD72E78D85DEE42E7486A19F269B67631B
tests/unit/test_currentness_exact_source_supplementation.py
  014AAACF04693C73A802265A57264DDAE6D33913639E9BD9B481576705B6A938
tests/unit/test_gear_cad.py
  45A262C797F0DCCE69285D61E31750F5BD5216BC53828FA8E0F5DEE4CE5E772A
```

Six protected implementation/golden pins match:

```text
src/mechcad_harness/multi_joint_kinematics.py
  514340C2F16B4BB29FF39A47C10D4446DE2E84C27040D117B0099D53EB440C4F
src/mechcad_harness/multi_joint_collision_sweep.py
  56E55B664E980EEDA9FFC9D67A038A6EB726DCCB73F42C2B6D0214A06DF9706F
src/mechcad_harness/multi_joint_pair_scope.py
  B593E0AA41B50A0DBC84C050F2396E0DBA63B621FDD48CF3A7E185120706D344
src/mechcad_harness/multi_joint_continuous_path.py
  C063CA8269392B68B911492F72071BDD5F7DE30ACD4461C98CAD045A5574FA9B
src/mechcad_harness/multi_joint_continuous_clearance.py
  66A62F30A7FE96C40F6CB049BF96906A427931B276CE9847DAD42E6F95AD2BC5
tests/unit/test_m13_3_legacy_goldens.py
  7DC391F10E545FC3291669A894A3C2A10729672EBA9E847C1DCA4DD88C8D5BA4
```

No protected pin was reported changed. The final audit was performed on an uncommitted,
dirty worktree. At audit time no commit, push, tag, release, or deployment had occurred.

## Implementation and verification status

- **Currentness exact-source supplementation:** implemented through the existing semantic-binding owner; only candidate-required raw identities are supplemented after canonical state authority is processed. Currentness/admission matrices are unit-verified.
- **GearWorks G2 correction:** the provider emits the accepted timestamp `2000-01-01T00:00:00` directly; stored STEP bytes are identity-checked. Provider/parser tests were recorded as 26 passed.
- **Canonical CAD/M10 provenance@2:** typed envelopes publish and resolve through fresh service instances. The V2 wrappers reparse serialized dictionaries; V1/V2 mixed parents reject. M10@2 fresh resolution verifies project/revision/state coordinates against the resolved CAD@2 parent; a forged revision-mismatched envelope rejects.
- **M12-5 legacy production path:** candidate-request@1/candidate@1/promotion@1 is homogeneous; supplied components retain published STEP sources, while only the existing bounded mount/body slots remain source-free. This resolves the earlier mixed-family fixture defect without inventing M13 authority.
- **Final entrypoint rejection:** the final `ProductionApplication` entrypoint rejects request@1 before production operations; the exact test passed.
- **Historical boundary:** R-P5.M10 pre/post equality remains **NOT PROVEN**; the original before/after equality clause remains **NOT EXECUTED**. Prospective replacement verification does not rewrite this historical status.

Final current-byte results recorded or independently rerun:

```text
Provenance/promotion/canonical CAD/M10 unit batch:
  204 passed in 180.76s (worktree run)
  204 passed in 211.65s (fresh independent-auditor run)

Post-activation promotion integration:
  25 passed, 23 warnings in 1181.86s
Post-activation candidate CAD/M10 integration:
  21 passed, 21 warnings in 432.20s
Mixed-version/admission/currentness subset:
  57 passed in 87.02s (fresh independent-auditor run)
Final-entry request@1 rejection:
  1 passed, 1 warning in 3.07s
T-P8.3 live verification through the final default:
  6 passed in 42.12s, real FreeCAD 1.1.3 subprocess
Five authorized candidate-CAD live targets:
  5 passed, 5 warnings in 442.59s, real FreeCAD 1.1.3 subprocess
```

The integration warning counts are retained. Earlier promotion-suite timeouts also
remain in the current-byte supplements; later successful full runs do not erase them.

## Non-blocking findings — preserved verbatim in substance

The final independent audit returned **ACCEPT WITH FINDINGS**, not a clean acceptance.
Its four findings are:

1. **Stale evidence SHA citation:** a T-P7.2 evidence citation names SHA
   `F337DFF9DB33A581993DBFBE914114DFBBAD433F94DF147DC49B05BB8B6FC470`, which the
   auditor could not resolve to a repository artifact. The current T-P7.2 supplement
   is `MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP7_2_CANONICAL_PROVENANCE_V2_CURRENT_BYTES_SUPPLEMENT.md`
   at SHA `29E2CAD7EADBF861850D11CCEE2055097465D5A4355823B5F8E5CDF21BA5B364`; its
   recorded 203-test count is stale compared with the verified 204-test result.
2. **P8.2 broad run not repeated on the exact final provenance bytes:** the broad run
   excluding the two exact failures recorded 2439 passed, 1 skipped, and 866 deselected.
   The final provenance resolver change was covered by the focused 204-test batch and
   production integrations, but the broad P8.2 invocation was not repeated afterward.
3. **Older records reference the superseded Plan:** prior gate/acceptance records bound
   to Plan `E449C60B641DBB5A4A630CC61553F5E586127443DC92B24BD5D983E3A15BB70E` remain
   historical; current disposition is bound to Plan `291B39B0…`.
4. **Superseded fixture hashes remain in older evidence:** earlier final-gate evidence
   contains candidate/promotion fixture hashes that no longer match the later accepted
   test bytes. Those historical records are not rewritten; newer supplements identify
   the current hashes.

The two P8.2 failures were:

- `test_rotator_v2_epic_01_candidate_cad.py::test_s4_candidate_inventory_equals_frozen_s3_physical_inventory`
- `test_section_docs.py::test_structural_extra_and_axis_contract_are_documented`

The independent auditor adjudicated them outside the Plan's literal minimum required
test-file groups and non-blocking for the accepted Plan scope. Their causes are not
claimed pre-existing; both remain findings in the source evidence.

## Gate disposition and release boundary

The independent audit judged the controlling Plan's acceptance sequence satisfied with
findings: P8-R0V and P8.1 pass; P8.2 meets the literal minimum scope with the two recorded
findings; T-P8.4a and its final-entry rejection pass; post-activation production
composition passes; T-P8.3 is live-verified in the bounded FreeCAD scenario; final
independent disposition is **ACCEPT WITH FINDINGS**.

This is implementation verification for the exact accepted Plan/Spec bytes above. It
does not authorize or claim a release or deployment. R-P5.M10 equality remains
**NOT PROVEN / NOT EXECUTED**.

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_EPIC_INDEPENDENTLY_ACCEPTED_WITH_FINDINGS_291B39B0
