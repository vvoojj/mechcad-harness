from mechcad_harness.ids import IdPrefix, generate_id, id_prefix


def test_ids_have_requested_prefixes_and_unique_values():
    first = generate_id(IdPrefix.PROJECT)
    second = generate_id(IdPrefix.PROJECT)

    assert first.startswith("PRJ-")
    assert id_prefix(first) == "PRJ"
    assert first != second


def test_all_required_prefixes_are_supported():
    assert {generate_id(prefix).split("-", 1)[0] for prefix in IdPrefix} == {
        "PRJ",
        "REV",
        "RUN",
        "TASK",
        "CP",
        "CS",
        "ISSUE",
        "EVD",
        "VAL",
        "DEC",
        "REQ",
        "PRT",
        "ASM",
        "MAT",
        "JNT",
        "LC",
    }
