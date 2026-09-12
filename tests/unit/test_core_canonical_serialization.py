"""F2 remediation: neutral canonical serialization core.

These tests characterize the accepted strict canonical byte contract and prove
that the consolidated serializers agree for non-ASCII payloads while preserving
the existing ASCII hash bytes.
"""

import hashlib
import json
from pathlib import Path

import pytest

from mechcad_harness.core.canonical import canonical_json_bytes, canonical_json_text

ASCII_NESTED = {"b": 2, "a": [1, True, None, 3.5]}
NON_ASCII = {"label": "caf\u00e9 \u2013 \u03c9", "n": 1, "flags": [True, False, None], "f": 1.5}


def _expected_text(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_core_matches_explicit_strict_contract_for_ascii_nested_payload():
    assert canonical_json_text(ASCII_NESTED) == _expected_text(ASCII_NESTED)
    assert canonical_json_bytes(ASCII_NESTED) == _expected_text(ASCII_NESTED).encode("utf-8")


def test_core_preserves_non_ascii_utf8_bytes():
    encoded = canonical_json_bytes(NON_ASCII)
    assert "caf\u00e9".encode("utf-8") in encoded
    assert b"\\u00e9" not in encoded
    assert encoded == _expected_text(NON_ASCII).encode("utf-8")


def test_core_is_deterministic_across_key_insertion_order():
    left = {"z": 1, "a": {"y": 2, "b": 3}}
    right = {"a": {"b": 3, "y": 2}, "z": 1}
    assert canonical_json_bytes(left) == canonical_json_bytes(right)


def test_core_uses_compact_separators():
    assert canonical_json_text({"a": 1, "b": 2}) == '{"a":1,"b":2}'


def test_core_serializes_lists_booleans_null_and_numbers():
    assert (
        canonical_json_text({"l": [1, 2.5, -3], "t": True, "f": False, "n": None})
        == '{"f":false,"l":[1,2.5,-3],"n":null,"t":true}'
    )


def test_core_rejects_non_json_serializable_values_under_strict_contract():
    with pytest.raises(TypeError):
        canonical_json_bytes({"bad": object()})


def test_default_ensure_ascii_variant_would_diverge_for_non_ascii():
    default_variant = json.dumps(NON_ASCII, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert default_variant != canonical_json_bytes(NON_ASCII)


def test_cross_site_strict_serializers_agree_on_non_ascii_payload():
    from mechcad_harness.candidates.multi_joint_selection import _digest as selection_digest
    from mechcad_harness.models.multi_joint_verification import _hash_payload as verification_hash
    from mechcad_harness.models.physical_pair_policy import _canonical_json as pair_policy_canonical
    from mechcad_harness.state.hashing import canonical_json
    from mechcad_harness.structural.evidence_models import _stable_hash
    from mechcad_harness.structural.models import _stable_json
    from mechcad_harness.tools.broker import payload_hash

    expected_bytes = canonical_json_bytes(NON_ASCII)
    expected_text = canonical_json_text(NON_ASCII)
    expected_digest = "sha256:" + hashlib.sha256(expected_bytes).hexdigest()

    assert canonical_json(NON_ASCII) == expected_bytes
    assert pair_policy_canonical(NON_ASCII) == expected_bytes
    assert _stable_json(NON_ASCII) == expected_text
    assert payload_hash(NON_ASCII) == expected_digest
    assert verification_hash(NON_ASCII) == expected_digest
    assert selection_digest(NON_ASCII) == expected_digest
    assert _stable_hash(NON_ASCII) == expected_digest


def test_migrated_strict_helpers_preserve_ascii_hash_digest():
    from mechcad_harness.candidates.multi_joint_selection import _digest as selection_digest
    from mechcad_harness.models.multi_joint_verification import _hash_payload as verification_hash
    from mechcad_harness.structural.evidence_models import _stable_hash
    from mechcad_harness.tools.broker import payload_hash

    golden = "sha256:061c4d431b3e8aeabdb002f7c7e9e6babcf52ec551fcddf0fcf44eaccdcb42ca"
    assert payload_hash(ASCII_NESTED) == golden
    assert _stable_hash(ASCII_NESTED) == golden
    assert verification_hash(ASCII_NESTED) == golden
    assert selection_digest(ASCII_NESTED) == golden


def test_state_hash_bytes_are_unchanged():
    from mechcad_harness.state import state_hash

    assert (
        state_hash(ASCII_NESTED)
        == "sha256:061c4d431b3e8aeabdb002f7c7e9e6babcf52ec551fcddf0fcf44eaccdcb42ca"
    )


def test_imported_component_hash_bytes_are_unchanged():
    from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash

    component = ImportedCadComponent(
        component_id="cad_motor",
        artifact_id="ART-1",
        artifact_hash="sha256:" + "1" * 64,
        format="step",
        source_revision=1,
        source_state_hash="sha256:" + "a" * 64,
    )
    assert (
        imported_component_hash(component)
        == "sha256:bc9e5cf864c2097f4ccbb65790b554448e236faa9c0a4fef6388e42e17d8c59b"
    )


def test_cad_program_hash_bytes_are_unchanged():
    from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram, cad_program_hash

    program = CadPartProgram(
        part_id="P1",
        operations=(BasePlateOperation(operation_id="base", length_mm=80, width_mm=60, thickness_mm=8),),
    )
    assert (
        cad_program_hash(program)
        == "sha256:c3427b595ee051f9c2eed55e0820e10d3d95919da747758992f7049425ceb1b0"
    )


def test_neutral_core_is_a_dependency_leaf():
    import mechcad_harness.core.canonical as canonical

    source = Path(canonical.__file__).read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            assert "mechcad_harness" not in stripped, line


def test_import_smoke_has_no_cycle_for_low_level_packages():
    import importlib

    import mechcad_harness.core.canonical  # noqa: F401

    for name in (
        "mechcad_harness.models",
        "mechcad_harness.state",
        "mechcad_harness.structural",
        "mechcad_harness.candidates",
        "mechcad_harness.backends",
        "mechcad_harness.tools",
    ):
        importlib.import_module(name)


def test_low_level_packages_do_not_import_the_state_layer():
    """The neutral core exists so low-level packages need not import state.hashing."""
    root = Path(__file__).parents[2] / "src" / "mechcad_harness"
    for package in ("models", "backends", "tools"):
        for source in (root / package).rglob("*.py"):
            text = source.read_text(encoding="utf-8")
            assert "mechcad_harness.state" not in text, source
            assert "state.hashing" not in text, source
            assert "from mechcad_harness import state" not in text, source
