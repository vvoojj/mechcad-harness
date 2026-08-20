import math

import pytest
from pydantic import ValidationError

from mechcad_harness.cad_analysis import (
    CadAssemblyAnalysisPlan,
    CadClearanceAnalyzer,
    CadClearanceResult,
    CadInterferenceCheck,
    CadMinimumClearanceCheck,
    analysis_plan_hash,
    canonical_instance_pair,
)


def test_interference_check_requires_nonnegative_finite_limit():
    with pytest.raises(ValidationError):
        CadInterferenceCheck(check_id="i", instance_a="a", instance_b="b", max_allowed_interference_volume_mm3=-1)
    with pytest.raises(ValidationError):
        CadInterferenceCheck(check_id="i", instance_a="a", instance_b="b", max_allowed_interference_volume_mm3=math.inf)


def test_clearance_check_requires_nonnegative_finite_requirement():
    with pytest.raises(ValidationError):
        CadMinimumClearanceCheck(check_id="c", instance_a="a", instance_b="b", required_clearance_mm=-1)
    with pytest.raises(ValidationError):
        CadMinimumClearanceCheck(check_id="c", instance_a="a", instance_b="b", required_clearance_mm=math.nan)


def test_checks_reject_same_instance_pairs():
    with pytest.raises(ValidationError):
        CadInterferenceCheck(check_id="i", instance_a="a", instance_b="a")


def test_pair_order_is_canonical_and_hash_is_order_independent():
    first = CadAssemblyAnalysisPlan(
        analysis_id="analysis",
        checks=(CadInterferenceCheck(check_id="i", instance_a="b", instance_b="a"),),
    )
    second = CadAssemblyAnalysisPlan(
        analysis_id="analysis",
        checks=(CadInterferenceCheck(check_id="i", instance_a="a", instance_b="b"),),
    )
    assert canonical_instance_pair("b", "a") == ("a", "b")
    assert analysis_plan_hash(first, "sha256:assembly") == analysis_plan_hash(second, "sha256:assembly")


def test_plan_rejects_duplicate_check_ids():
    with pytest.raises(ValidationError):
        CadAssemblyAnalysisPlan(
            analysis_id="analysis",
            checks=(
                CadInterferenceCheck(check_id="same", instance_a="a", instance_b="b"),
                CadMinimumClearanceCheck(check_id="same", instance_a="a", instance_b="b"),
            ),
        )


def test_plan_hash_changes_when_semantic_input_changes():
    first = CadAssemblyAnalysisPlan(
        analysis_id="analysis",
        checks=(CadMinimumClearanceCheck(check_id="c", instance_a="a", instance_b="b", required_clearance_mm=20),),
    )
    second = first.model_copy(update={"checks": (CadMinimumClearanceCheck(check_id="c", instance_a="a", instance_b="b", required_clearance_mm=21),)})
    assert analysis_plan_hash(first, "sha256:assembly") != analysis_plan_hash(second, "sha256:assembly")


def test_clearance_result_preserves_zero_for_interference():
    result = CadClearanceResult(
        check_id="c",
        instance_a="a",
        instance_b="b",
        measured_clearance_mm=0,
        required_clearance_mm=1,
        passed=False,
    )
    assert result.measured_clearance_mm == 0


class FakeCommon:
    def __init__(self, volume):
        self.Volume = volume


class FakeShape:
    def __init__(self, volume, distance, common_volume):
        self.Volume = volume
        self.distance = distance
        self.common_volume = common_volume

    def common(self, other):
        return FakeCommon(self.common_volume)

    def distToShape(self, other):
        return (self.distance, (), ())


def test_analyzer_uses_common_volume_and_exact_shape_distance():
    analyzer = CadClearanceAnalyzer()
    shapes = {"a": FakeShape(1, 20, 0), "b": FakeShape(1, 20, 0)}
    plan = CadAssemblyAnalysisPlan(
        analysis_id="analysis",
        checks=(
            CadInterferenceCheck(check_id="i", instance_a="a", instance_b="b"),
            CadMinimumClearanceCheck(check_id="c", instance_a="a", instance_b="b", required_clearance_mm=20),
        ),
    )
    result = analyzer.analyze_shapes(plan, "sha256:assembly", shapes)
    assert result.interference[0].interference_volume_mm3 == 0
    assert result.clearance[0].measured_clearance_mm == 20
    assert result.passed
    assert result.analyzer_version == "mechcad-freecad-clearance@1.0"


def test_analyzer_reports_zero_clearance_for_interference():
    analyzer = CadClearanceAnalyzer()
    shapes = {"a": FakeShape(1, 0, 2), "b": FakeShape(1, 0, 2)}
    plan = CadAssemblyAnalysisPlan(
        analysis_id="analysis",
        checks=(CadMinimumClearanceCheck(check_id="c", instance_a="a", instance_b="b", required_clearance_mm=0),),
    )
    result = analyzer.analyze_shapes(plan, "sha256:assembly", shapes)
    assert result.clearance[0].measured_clearance_mm == 0
    assert not result.clearance[0].passed
