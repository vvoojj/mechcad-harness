# Deterministic STEP Content Identity — Commit EOL Normalization Supplement

## Scope

During the authorized commit preparation, `git diff --cached --check` identified CRLF
line endings in the accepted Epic aggregate test
`tests/unit/test_semantic_family_closure.py`. This file is in the Epic test set, not
unrelated work. Its line endings were normalized to LF and one section-heading
punctuation mark was made consistent. Test logic was not changed. Because this changes
test bytes after the final independent acceptance, the prior exact-byte acceptance is
not treated as automatically covering these bytes; a new read-only independent audit is
required before the commit.

## Exact bytes and verification

- Accepted Spec SHA-256: `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.
- Controlling Plan SHA-256: `291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679`.
- HEAD anchor: `05da8edad18488492f02be1dad9d1ec3653ce807`.
- `tests/unit/test_semantic_family_closure.py` SHA-256:
  `834ED73B0040F6B32720ED32EDA9291167E652A79845FCD4A8D6E0AFAE8CBF02`.
- `git ls-files --eol` reports `i/lf w/lf` for that test file.

Focused test command:

```text
py -3 -m pytest tests/unit/test_semantic_family_closure.py -q --tb=short -p no:randomly
132 passed in 130.26s
```

After normalization, `git diff --cached --check` passed for the complete staged set and
`py -3 -m compileall -q src/mechcad_harness tests/unit/test_semantic_family_closure.py`
passed. No commit, push, tag, release, reset, rebase, or cleanup occurred at the time of
this supplement. This supplement claims no acceptance; a fresh final independent audit
must determine disposition for the exact normalized bytes.
