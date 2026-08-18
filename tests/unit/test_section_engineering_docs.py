from pathlib import Path


def test_c3a_boundaries_are_documented():
    text = Path("README.md").read_text(encoding="utf-8")
    for phrase in (
        "M5.5C-3A",
        "result IDs",
        "output hash",
        "UNAVAILABLE",
        "kg/m",
        "N*mm^2",
        "SHEAR_MODULUS_UNAVAILABLE",
        "HOMOGENEOUS_SECTION",
        "ISOTROPIC_LINEAR_ELASTIC_PRELIMINARY",
        "C-3B",
        "Evidence",
    ):
        assert phrase in text
