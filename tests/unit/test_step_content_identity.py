from hashlib import sha256

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.step_content_identity import (
    StepContentIdentity,
    canonical_identity_bytes_v1,
    step_content_identity_v1,
)


def _step(*, timestamp="2026-09-22T12:34:56", data="#1=PRODUCT('gear');", header_extra=""):
    return (
        "ISO-10303-21;\n"
        "HEADER;\n"
        "FILE_NAME('gear.step','"
        + timestamp
        + "',('author''s name'),('org'),('preprocessor'),('system'),'' )"
        + ";\n"
        + header_extra
        + "FILE_SCHEMA(('AUTOMOTIVE_DESIGN_CC2'));\n"
        "ENDSEC;\n"
        "DATA;\n"
        + data
        + "\nENDSEC;\n"
        "END-ISO-10303-21;\n"
    ).encode("utf-8")


def test_timestamp_only_changes_have_equal_content_identity_but_different_raw_bytes():
    first = _step(timestamp="2026-09-22T12:34:56")
    second = _step(timestamp="2027-01-02T03:04:05")

    assert first != second
    assert canonical_identity_bytes_v1(first) == canonical_identity_bytes_v1(second)
    assert step_content_identity_v1(first) == step_content_identity_v1(second)
    assert step_content_identity_v1(first).algorithm == "step-content-identity@1"


def test_data_change_changes_content_identity():
    assert step_content_identity_v1(_step(data="#1=PRODUCT('gear');")) != step_content_identity_v1(
        _step(data="#1=PRODUCT('shaft');")
    )


def test_unauthorized_header_change_changes_identity():
    first = _step()
    second = _step(header_extra="\nFILE_DESCRIPTION(('changed'), '2;1');")

    assert step_content_identity_v1(first) != step_content_identity_v1(second)


def test_line_endings_and_whitespace_are_not_normalized():
    crlf = _step().replace(b"\n", b"\r\n")
    spaced = _step().replace(b"FILE_SCHEMA", b"FILE_SCHEMA ")

    assert step_content_identity_v1(_step()) != step_content_identity_v1(crlf)
    assert step_content_identity_v1(_step()) != step_content_identity_v1(spaced)


def test_step_string_doubled_apostrophe_is_parsed():
    identity = step_content_identity_v1(_step())

    assert isinstance(identity, StepContentIdentity)


@pytest.mark.parametrize(
    "payload",
    [
        _step().replace(b"FILE_NAME(", b"FILE_DESCRIPTION(", 1),
        _step().replace(b"FILE_NAME(", b"FILE_NAME('other',", 1),
        _step(timestamp="2026-09-22 12:34:56"),
        _step(timestamp="2026-09-22T12:34:56.000"),
        _step(timestamp="2026-09-22T12:34:56Z"),
    ],
)
def test_invalid_file_name_or_timestamp_fails_closed(payload):
    with pytest.raises(ValueError):
        canonical_identity_bytes_v1(payload)


def test_multiple_file_name_entities_are_rejected():
    payload = _step().replace(
        b"FILE_SCHEMA",
        b"FILE_NAME('other.step','2026-09-22T12:34:56',('a'),('o'),('p'),('s'),'');\nFILE_SCHEMA",
        1,
    )

    with pytest.raises(ValueError):
        canonical_identity_bytes_v1(payload)


@pytest.mark.parametrize(
    "payload",
    [
        _step().replace(b"HEADER;", b"HEADER;\nHEADER;", 1),
        _step().replace(b"DATA;", b"DATA;\nDATA;", 1),
        _step().replace(b"ENDSEC;", b"ENDSEC;\nENDSEC;", 1),
        _step().replace(b"HEADER;", b"DATA;", 1),
        _step().replace(b"ENDSEC;", b"BROKEN;", 1),
    ],
)
def test_section_cardinality_and_order_are_rejected(payload):
    with pytest.raises(ValueError):
        canonical_identity_bytes_v1(payload)


def test_unbalanced_parentheses_and_non_utf8_header_are_rejected():
    with pytest.raises(ValueError):
        canonical_identity_bytes_v1(_step().replace(b"FILE_SCHEMA", b"FILE_SCHEMA((", 1))

    with pytest.raises(ValueError):
        canonical_identity_bytes_v1(_step().replace(b"FILE_SCHEMA", b"FILE_SCHEMA\xff", 1))


def test_size_and_nesting_bounds_are_rejected():
    with pytest.raises(ValueError):
        canonical_identity_bytes_v1(_step(data="A" * (128 * 1024 * 1024)))

    nested = "#1=" + ("(" * 33) + "1" + (")" * 33) + ";"
    with pytest.raises(ValueError):
        canonical_identity_bytes_v1(_step(data=nested))


def test_content_identity_does_not_mutate_or_alias_raw_artifact_bytes(tmp_path):
    raw = _step()
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    artifact = store.publish(
        "STEP-1",
        ArtifactType.STEP,
        "gear.step",
        raw,
        "freecad",
        "1.1.3",
        1,
        "sha256:state",
    )
    _, before = store.read_verified(
        "STEP-1", expected_type=ArtifactType.STEP, expected_hash=artifact.sha256
    )

    step_content_identity_v1(before)

    _, after = store.read_verified(
        "STEP-1", expected_type=ArtifactType.STEP, expected_hash=artifact.sha256
    )
    assert after == raw
    assert sha256(after).hexdigest() == artifact.sha256.removeprefix("sha256:")
