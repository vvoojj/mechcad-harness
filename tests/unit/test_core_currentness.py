"""F3: neutral currentness vocabulary and dependency-leaf boundary."""

import ast
from pathlib import Path
import sys


def test_currentness_has_the_neutral_wire_values():
    from mechcad_harness.core.currentness import Currentness

    assert tuple(Currentness) == (
        Currentness.CURRENT,
        Currentness.STALE_RELATIVE_TO_CURRENT_STATE,
        Currentness.CURRENTNESS_UNAVAILABLE,
    )
    assert [member.value for member in Currentness] == [
        "current",
        "stale_relative_to_current_state",
        "currentness_unavailable",
    ]


def test_currentness_core_is_a_standard_library_dependency_leaf():
    source_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "mechcad_harness"
        / "core"
        / "currentness.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    assert len(classes) == 1
    assert any(
        isinstance(base, ast.Name) and base.id == "StrEnum"
        for base in classes[0].bases
    )

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module if node.level == 0 else "")

    assert imports
    assert all(
        name.split(".", 1)[0] in sys.stdlib_module_names for name in imports
    )
