"""M10-2 tests: Generic multi-joint kinematic model and forward kinematics."""

from __future__ import annotations

import math

import pytest

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.kinematic_sweep import _rotate_vector
from mechcad_harness.multi_joint_kinematics import (
    EvaluatedJointState,
    InstanceWorldTransform,
    JointConfiguration,
    KinematicForwardKinematicsResult,
    KinematicJointKind,
    KinematicModel,
    MultiJointKinematicsService,
    RevoluteJointModel,
    axis_rotation_transform,
    joint_configuration_hash,
    kinematic_model_hash,
    transform_apply,
    transform_compose,
    transform_inverse,
    MULTI_JOINT_FORWARD_KINEMATICS_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DUMMY_PART = CadPartProgram(
    part_id="link",
    operations=(
        BasePlateOperation(
            operation_id="base", length_mm=10, width_mm=10, thickness_mm=2
        ),
    ),
)


def _three_body_assembly(
    assembly_id="m10-2-fixture",
    link1_offset_mm=30.0,
    link2_offset_mm=50.0,
):
    """Generic three-body serial chain: base -> link-1 -> link-2.

    link-1 home is at (link1_offset_mm, 0, 0) relative to base origin.
    link-2 home is at (link1_offset_mm + link2_offset_mm, 0, 0) relative to
    base origin (i.e. link2_offset_mm along X from link-1 end).
    """
    return CadAssemblyProgram(
        assembly_id=assembly_id,
        parts=(_DUMMY_PART,),
        imported_components=(),
        instances=(
            CadComponentInstance(
                instance_id="base",
                part_id="link",
                placement=CadRigidTransform(x_mm=0, y_mm=0, z_mm=0),
            ),
            CadComponentInstance(
                instance_id="link-1",
                part_id="link",
                placement=CadRigidTransform(
                    x_mm=link1_offset_mm, y_mm=0, z_mm=0
                ),
            ),
            CadComponentInstance(
                instance_id="link-2",
                part_id="link",
                placement=CadRigidTransform(
                    x_mm=link1_offset_mm + link2_offset_mm, y_mm=0, z_mm=0
                ),
            ),
        ),
    )


def _two_body_assembly(assembly_id="m10-2-two-body"):
    """Two-body chain: base -> link-1."""
    return CadAssemblyProgram(
        assembly_id=assembly_id,
        parts=(_DUMMY_PART,),
        imported_components=(),
        instances=(
            CadComponentInstance(
                instance_id="base",
                part_id="link",
                placement=CadRigidTransform(x_mm=0, y_mm=0, z_mm=0),
            ),
            CadComponentInstance(
                instance_id="link-1",
                part_id="link",
                placement=CadRigidTransform(x_mm=30, y_mm=0, z_mm=0),
            ),
        ),
    )


def _branching_assembly(assembly_id="m10-2-branch"):
    """Branching tree: base -> link-A and base -> link-B."""
    return CadAssemblyProgram(
        assembly_id=assembly_id,
        parts=(_DUMMY_PART,),
        imported_components=(),
        instances=(
            CadComponentInstance(
                instance_id="base",
                part_id="link",
                placement=CadRigidTransform(x_mm=0, y_mm=0, z_mm=0),
            ),
            CadComponentInstance(
                instance_id="link-A",
                part_id="link",
                placement=CadRigidTransform(x_mm=30, y_mm=0, z_mm=0),
            ),
            CadComponentInstance(
                instance_id="link-B",
                part_id="link",
                placement=CadRigidTransform(x_mm=0, y_mm=40, z_mm=0),
            ),
        ),
    )


def _three_body_model(
    model_id="model-3",
    j1_origin=(0, 0, 0),
    j1_direction=(0, 0, 1),
    j2_origin=(30, 0, 0),
    j2_direction=(0, 0, 1),
):
    """Standard three-body model with two revolute joints about Z."""
    return KinematicModel(
        model_id=model_id,
        joints=(
            RevoluteJointModel(
                joint_id="joint-1",
                parent_instance_id="base",
                child_instance_id="link-1",
                axis_origin_x_mm=j1_origin[0],
                axis_origin_y_mm=j1_origin[1],
                axis_origin_z_mm=j1_origin[2],
                axis_direction_x=j1_direction[0],
                axis_direction_y=j1_direction[1],
                axis_direction_z=j1_direction[2],
            ),
            RevoluteJointModel(
                joint_id="joint-2",
                parent_instance_id="link-1",
                child_instance_id="link-2",
                axis_origin_x_mm=j2_origin[0],
                axis_origin_y_mm=j2_origin[1],
                axis_origin_z_mm=j2_origin[2],
                axis_direction_x=j2_direction[0],
                axis_direction_y=j2_direction[1],
                axis_direction_z=j2_direction[2],
            ),
        ),
    )


def _config(model_id="model-3", **angles):
    """Build a JointConfiguration from keyword angles.

    The caller should pass model_id= to override, not m=.
    """
    return JointConfiguration(model_id=model_id, positions=dict(angles))


def _cfg(m="model-3", **angles):
    """Shortcut: _cfg(m="my-model", joint_1=90)."""
    return JointConfiguration(model_id=m, positions=dict(angles))


_SERVICE = MultiJointKinematicsService()


# ===================================================================
# A. Model validation
# ===================================================================


class TestModelValidation:
    def test_duplicate_joint_ids_rejected(self):
        with pytest.raises(ValueError, match="duplicate joint IDs"):
            KinematicModel(
                model_id="m",
                joints=(
                    RevoluteJointModel(
                        joint_id="j1",
                        parent_instance_id="a",
                        child_instance_id="b",
                    ),
                    RevoluteJointModel(
                        joint_id="j1",
                        parent_instance_id="b",
                        child_instance_id="c",
                    ),
                ),
            )

    def test_missing_parent_rejected(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="nonexistent",
                    child_instance_id="link-1",
                ),
            ),
        )
        with pytest.raises(ValueError, match="parent.*not in assembly"):
            _SERVICE.evaluate(asm, model, _cfg(m="m", j1=0))

    def test_missing_child_rejected(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="nonexistent",
                ),
            ),
        )
        with pytest.raises(ValueError, match="child.*not in assembly"):
            _SERVICE.evaluate(asm, model, _cfg(m="m", j1=0))

    def test_parent_equals_child_rejected(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="base",
                ),
            ),
        )
        with pytest.raises(ValueError, match="parent == child"):
            _SERVICE.evaluate(asm, model, _cfg(m="m", j1=0))

    def test_child_with_two_parents_rejected(self):
        asm = _branching_assembly()
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="jA",
                    parent_instance_id="base",
                    child_instance_id="link-A",
                ),
                RevoluteJointModel(
                    joint_id="jB",
                    parent_instance_id="link-A",
                    child_instance_id="link-A",
                ),
            ),
        )
        with pytest.raises(ValueError, match="parent == child"):
            _SERVICE.evaluate(
                asm,
                model,
                _cfg(m="m", jA=0, jB=0),
            )

    def test_child_with_two_articulated_parents_rejected(self):
        asm = _branching_assembly()
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="jA",
                    parent_instance_id="base",
                    child_instance_id="link-A",
                ),
                RevoluteJointModel(
                    joint_id="jB",
                    parent_instance_id="base",
                    child_instance_id="link-A",
                ),
            ),
        )
        with pytest.raises(ValueError, match="two parent joints"):
            _SERVICE.evaluate(asm, model, _cfg(m="m", jA=0, jB=0))

    def test_simple_cycle_rejected(self):
        asm = CadAssemblyProgram(
            assembly_id="cycle-asm",
            parts=(_DUMMY_PART,),
            imported_components=(),
            instances=(
                CadComponentInstance(
                    instance_id="a",
                    part_id="link",
                    placement=CadRigidTransform(),
                ),
                CadComponentInstance(
                    instance_id="b",
                    part_id="link",
                    placement=CadRigidTransform(x_mm=10),
                ),
            ),
        )
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="a",
                    child_instance_id="b",
                ),
                RevoluteJointModel(
                    joint_id="j2",
                    parent_instance_id="b",
                    child_instance_id="a",
                ),
            ),
        )
        with pytest.raises(ValueError, match="cycle"):
            _SERVICE.evaluate(asm, model, _cfg(m="m", j1=0, j2=0))

    def test_longer_cycle_rejected(self):
        asm = CadAssemblyProgram(
            assembly_id="cycle-asm",
            parts=(_DUMMY_PART,),
            imported_components=(),
            instances=tuple(
                CadComponentInstance(
                    instance_id=f"n{i}",
                    part_id="link",
                    placement=CadRigidTransform(x_mm=i * 10),
                )
                for i in range(3)
            ),
        )
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="j0",
                    parent_instance_id="n0",
                    child_instance_id="n1",
                ),
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="n1",
                    child_instance_id="n2",
                ),
                RevoluteJointModel(
                    joint_id="j2",
                    parent_instance_id="n2",
                    child_instance_id="n0",
                ),
            ),
        )
        with pytest.raises(ValueError, match="cycle"):
            _SERVICE.evaluate(asm, model, _cfg(m="m", j0=0, j1=0, j2=0))

    def test_axis_normalization(self):
        j = RevoluteJointModel(
            joint_id="j",
            parent_instance_id="a",
            child_instance_id="b",
            axis_direction_x=0,
            axis_direction_y=3,
            axis_direction_z=4,
        )
        assert j.axis_direction == pytest.approx((0.0, 0.6, 0.8))

    def test_zero_length_direction_rejected(self):
        with pytest.raises(ValueError, match="non-zero"):
            RevoluteJointModel(
                joint_id="j",
                parent_instance_id="a",
                child_instance_id="b",
                axis_direction_x=0,
                axis_direction_y=0,
                axis_direction_z=0,
            )

    def test_infinite_axis_rejected(self):
        with pytest.raises(ValueError, match="finite"):
            RevoluteJointModel(
                joint_id="j",
                parent_instance_id="a",
                child_instance_id="b",
                axis_direction_x=math.inf,
            )

    def test_min_greater_than_max_rejected(self):
        with pytest.raises(ValueError, match="min_angle_deg must be <= max"):
            RevoluteJointModel(
                joint_id="j",
                parent_instance_id="a",
                child_instance_id="b",
                min_angle_deg=90,
                max_angle_deg=-90,
            )

    def test_unreachable_articulated_instance_rejected(self):
        # In a valid tree topology every child is reachable from some root,
        # so "unreachable" is defense-in-depth.  A disconnected cycle is
        # caught first by cycle detection.
        asm = CadAssemblyProgram(
            assembly_id="cycle-asm",
            parts=(_DUMMY_PART,),
            imported_components=(),
            instances=(
                CadComponentInstance(
                    instance_id="isolated-root",
                    part_id="link",
                    placement=CadRigidTransform(x_mm=0, y_mm=0, z_mm=0),
                ),
                CadComponentInstance(
                    instance_id="a",
                    part_id="link",
                    placement=CadRigidTransform(x_mm=10, y_mm=0, z_mm=0),
                ),
                CadComponentInstance(
                    instance_id="b",
                    part_id="link",
                    placement=CadRigidTransform(x_mm=20, y_mm=0, z_mm=0),
                ),
            ),
        )
        model = KinematicModel(
            model_id="m",
            joints=(
                # cycle: a→b→a, disconnected from isolated-root
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="a",
                    child_instance_id="b",
                ),
                RevoluteJointModel(
                    joint_id="j2",
                    parent_instance_id="b",
                    child_instance_id="a",
                ),
            ),
        )
        with pytest.raises(ValueError, match="cycle"):
            _SERVICE.evaluate(asm, model, _cfg(m="m", j1=0, j2=0))


class TestModelHashDeterminism:
    def test_same_model_same_hash(self):
        model = _three_body_model()
        h1 = kinematic_model_hash(model)
        h2 = kinematic_model_hash(model)
        assert h1 == h2

    def test_different_axis_direction_different_hash(self):
        m1 = _three_body_model(j1_direction=(0, 0, 1))
        m2 = _three_body_model(j1_direction=(1, 0, 0))
        assert kinematic_model_hash(m1) != kinematic_model_hash(m2)

    def test_different_limits_different_hash(self):
        m1 = _three_body_model()
        m2 = KinematicModel(
            model_id="model-3",
            joints=(
                RevoluteJointModel(
                    joint_id="joint-1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                    min_angle_deg=-90,
                    max_angle_deg=90,
                ),
                RevoluteJointModel(
                    joint_id="joint-2",
                    parent_instance_id="link-1",
                    child_instance_id="link-2",
                ),
            ),
        )
        assert kinematic_model_hash(m1) != kinematic_model_hash(m2)

    def test_different_model_id_different_hash(self):
        m1 = _three_body_model(model_id="m1")
        m2 = _three_body_model(model_id="m2")
        assert kinematic_model_hash(m1) != kinematic_model_hash(m2)

    def test_hash_starts_with_sha256(self):
        h = kinematic_model_hash(_three_body_model())
        assert h.startswith("sha256:")


class TestConfigurationHashDeterminism:
    def test_same_config_same_hash(self):
        cfg = _cfg(m="m", j1=10, j2=20)
        assert joint_configuration_hash(cfg) == joint_configuration_hash(cfg)

    def test_different_angle_different_hash(self):
        c1 = _cfg(m="m", j1=10, j2=20)
        c2 = _cfg(m="m", j1=10, j2=30)
        assert joint_configuration_hash(c1) != joint_configuration_hash(c2)

    def test_insertion_order_independent(self):
        c1 = JointConfiguration(model_id="m", positions={"j1": 10, "j2": 20})
        c2 = JointConfiguration(model_id="m", positions={"j2": 20, "j1": 10})
        assert joint_configuration_hash(c1) == joint_configuration_hash(c2)

    def test_different_model_id_different_hash(self):
        c1 = _cfg(m="m1", j1=10)
        c2 = _cfg(m="m2", j1=10)
        assert joint_configuration_hash(c1) != joint_configuration_hash(c2)

    def test_nan_angle_rejected(self):
        with pytest.raises(ValueError, match="finite"):
            _cfg(m="m", j1=float("nan"), j2=0)

    def test_inf_angle_rejected(self):
        with pytest.raises(ValueError, match="finite"):
            _cfg(m="m", j1=float("inf"), j2=0)


class TestZeroConfiguration:
    def test_zero_config_reproduces_home(self):
        asm = _three_body_assembly()
        model = _three_body_model()
        cfg = _cfg(m="model-3", **{"joint-1": 0, "joint-2": 0})
        result = _SERVICE.evaluate(asm, model, cfg)
        home = {inst.instance_id: inst.placement for inst in asm.instances}
        for iwt in result.instance_world_transforms:
            h = home[iwt.instance_id]
            assert iwt.transform.x_mm == pytest.approx(h.x_mm, abs=1e-9)
            assert iwt.transform.y_mm == pytest.approx(h.y_mm, abs=1e-9)
            assert iwt.transform.z_mm == pytest.approx(h.z_mm, abs=1e-9)
            assert iwt.transform.rotation_quaternion == pytest.approx(
                h.rotation_quaternion, abs=1e-9
            )


class TestKnownAnalyticPose:
    """Three-body chain: base at origin, link-1 at (30,0,0), link-2 at (80,0,0).
    Both joints rotate about Z axis at their respective origins.
    """

    def test_q1_90_q2_0(self):
        asm = _three_body_assembly()
        model = _three_body_model()
        cfg = _cfg(m="model-3", **{"joint-1": 90, "joint-2": 0})
        result = _SERVICE.evaluate(asm, model, cfg)
        t = {i.instance_id: i.transform for i in result.instance_world_transforms}
        assert t["link-1"].x_mm == pytest.approx(0.0, abs=1e-9)
        assert t["link-1"].y_mm == pytest.approx(30.0, abs=1e-9)
        assert t["link-2"].x_mm == pytest.approx(0.0, abs=1e-9)
        assert t["link-2"].y_mm == pytest.approx(80.0, abs=1e-9)

    def test_q1_0_q2_90(self):
        asm = _three_body_assembly()
        model = _three_body_model()
        cfg = _cfg(m="model-3", **{"joint-1": 0, "joint-2": 90})
        result = _SERVICE.evaluate(asm, model, cfg)
        t = {i.instance_id: i.transform for i in result.instance_world_transforms}
        # link-1 unchanged at (30, 0, 0)
        assert t["link-1"].x_mm == pytest.approx(30.0, abs=1e-9)
        assert t["link-1"].y_mm == pytest.approx(0.0, abs=1e-9)
        # joint-2 rotates about (30,0,0) in link-1 frame.
        # link-2 home in link-1 frame: offset (50,0,0) from joint origin.
        # After rotZ(90): offset becomes (0,50,0), plus joint origin = (30,50,0).
        # In world (link-1 not rotated): (30+30, 0+50, 0) = wait no...
        # link-1 world is trans(30,0,0) with identity rotation.
        # T_joint(90) in parent frame: rotation rotZ(90), translation p-rot(q,p).
        # compose(T_joint, T_pch): rotation=rotZ(90), translation=(30,-30,0)+rotZ(90)*(50,0,0)=(30,-30,0)+(0,50,0)=(30,20,0).
        # compose(T_parent=trans(30,0,0), above): translation=(30,0,0)+(30,20,0)=(60,20,0).
        assert t["link-2"].x_mm == pytest.approx(60.0, abs=1e-9)
        assert t["link-2"].y_mm == pytest.approx(20.0, abs=1e-9)

    def test_q1_90_q2_90(self):
        asm = _three_body_assembly()
        model = _three_body_model()
        cfg = _cfg(m="model-3", **{"joint-1": 90, "joint-2": 90})
        result = _SERVICE.evaluate(asm, model, cfg)
        t = {i.instance_id: i.transform for i in result.instance_world_transforms}
        # link-1 at (0, 30, 0) with rotZ(90)
        assert t["link-1"].x_mm == pytest.approx(0.0, abs=1e-9)
        assert t["link-1"].y_mm == pytest.approx(30.0, abs=1e-9)
        # compose(T_joint_2, T_pch_2) = rotZ(90), trans=(30,20,0) in parent frame.
        # compose(T_parent=rotZ(90)+trans(0,30,0), above):
        #   rotation = rotZ(90)*rotZ(90) = rotZ(180)
        #   translation = (0,30,0) + rot(rotZ(90),(30,20,0)) = (0,30,0)+(-20,30,0) = (-20,60,0)
        assert t["link-2"].x_mm == pytest.approx(-20.0, abs=1e-9)
        assert t["link-2"].y_mm == pytest.approx(60.0, abs=1e-9)


class TestParentPropagation:
    """Configuration C from spec section 34: verify parent/child propagation."""

    def test_q1_30_q2_0_both_change(self):
        asm = _three_body_assembly()
        model = _three_body_model()
        cfg_zero = _cfg(m="model-3", **{"joint-1": 0, "joint-2": 0})
        cfg_a = _cfg(m="model-3", **{"joint-1": 30, "joint-2": 0})
        r0 = _SERVICE.evaluate(asm, model, cfg_zero)
        ra = _SERVICE.evaluate(asm, model, cfg_a)
        t0 = {i.instance_id: i.transform for i in r0.instance_world_transforms}
        ta = {i.instance_id: i.transform for i in ra.instance_world_transforms}
        # link-1 changes
        assert ta["link-1"].x_mm != pytest.approx(t0["link-1"].x_mm, abs=1e-6)
        assert ta["link-1"].y_mm != pytest.approx(t0["link-1"].y_mm, abs=1e-6)
        # link-2 changes too (parent moved)
        assert ta["link-2"].x_mm != pytest.approx(t0["link-2"].x_mm, abs=1e-6)
        assert ta["link-2"].y_mm != pytest.approx(t0["link-2"].y_mm, abs=1e-6)

    def test_q1_0_q2_30_only_link2_changes(self):
        asm = _three_body_assembly()
        model = _three_body_model()
        cfg_zero = _cfg(m="model-3", **{"joint-1": 0, "joint-2": 0})
        cfg_b = _cfg(m="model-3", **{"joint-1": 0, "joint-2": 30})
        r0 = _SERVICE.evaluate(asm, model, cfg_zero)
        rb = _SERVICE.evaluate(asm, model, cfg_b)
        t0 = {i.instance_id: i.transform for i in r0.instance_world_transforms}
        tb = {i.instance_id: i.transform for i in rb.instance_world_transforms}
        # link-1 unchanged
        assert tb["link-1"].x_mm == pytest.approx(t0["link-1"].x_mm, abs=1e-9)
        assert tb["link-1"].y_mm == pytest.approx(t0["link-1"].y_mm, abs=1e-9)
        # link-2 changes
        assert tb["link-2"].x_mm != pytest.approx(t0["link-2"].x_mm, abs=1e-6)
        assert tb["link-2"].y_mm != pytest.approx(t0["link-2"].y_mm, abs=1e-6)


class TestArbitraryAxis:
    def test_tilted_axis_produces_non_trivial_rotation(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="tilted",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                    axis_direction_x=1,
                    axis_direction_y=0,
                    axis_direction_z=1,
                ),
            ),
        )
        cfg = JointConfiguration(model_id="tilted", positions={"j1": 90})
        result = _SERVICE.evaluate(asm, model, cfg)
        t = {i.instance_id: i.transform for i in result.instance_world_transforms}
        assert t["link-1"].x_mm != pytest.approx(30.0, abs=1e-6)
        d = math.sqrt(
            t["link-1"].x_mm**2 + t["link-1"].y_mm**2 + t["link-1"].z_mm**2
        )
        assert d == pytest.approx(30.0, abs=1e-9)

    def test_translated_axis_origin(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="translated",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                    axis_origin_x_mm=15,
                    axis_origin_y_mm=0,
                    axis_origin_z_mm=0,
                    axis_direction_x=0,
                    axis_direction_y=0,
                    axis_direction_z=1,
                ),
            ),
        )
        cfg = JointConfiguration(model_id="translated", positions={"j1": 90})
        result = _SERVICE.evaluate(asm, model, cfg)
        t = {i.instance_id: i.transform for i in result.instance_world_transforms}
        assert t["link-1"].x_mm == pytest.approx(15.0, abs=1e-9)
        assert t["link-1"].y_mm == pytest.approx(15.0, abs=1e-9)


class TestJointLimits:
    def test_at_min_accepted(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="limited",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                    min_angle_deg=-45,
                    max_angle_deg=45,
                ),
            ),
        )
        cfg = JointConfiguration(model_id="limited", positions={"j1": -45})
        result = _SERVICE.evaluate(asm, model, cfg)
        assert result.ordered_joint_states[0].within_limits is True

    def test_at_max_accepted(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="limited",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                    min_angle_deg=-45,
                    max_angle_deg=45,
                ),
            ),
        )
        cfg = JointConfiguration(model_id="limited", positions={"j1": 45})
        result = _SERVICE.evaluate(asm, model, cfg)
        assert result.ordered_joint_states[0].within_limits is True

    def test_inside_range_accepted(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="limited",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                    min_angle_deg=-45,
                    max_angle_deg=45,
                ),
            ),
        )
        cfg = JointConfiguration(model_id="limited", positions={"j1": 10})
        result = _SERVICE.evaluate(asm, model, cfg)
        assert result.ordered_joint_states[0].within_limits is True

    def test_below_min_rejected(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="limited",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                    min_angle_deg=-45,
                    max_angle_deg=45,
                ),
            ),
        )
        cfg = JointConfiguration(model_id="limited", positions={"j1": -46})
        with pytest.raises(ValueError, match="below min"):
            _SERVICE.evaluate(asm, model, cfg)

    def test_above_max_rejected(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="limited",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                    min_angle_deg=-45,
                    max_angle_deg=45,
                ),
            ),
        )
        cfg = JointConfiguration(model_id="limited", positions={"j1": 46})
        with pytest.raises(ValueError, match="above max"):
            _SERVICE.evaluate(asm, model, cfg)

    def test_unlimited_accepts_large_angle(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="unlimited",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                ),
            ),
        )
        cfg = JointConfiguration(model_id="unlimited", positions={"j1": 9999})
        result = _SERVICE.evaluate(asm, model, cfg)
        assert result.ordered_joint_states[0].within_limits is True


class TestInvalidNumericalInputs:
    def test_nan_angle_rejected(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                ),
            ),
        )
        with pytest.raises(ValueError, match="finite"):
            JointConfiguration(model_id="m", positions={"j1": float("nan")})

    def test_inf_angle_rejected(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                ),
            ),
        )
        with pytest.raises(ValueError, match="finite"):
            JointConfiguration(model_id="m", positions={"j1": float("inf")})

    def test_missing_joint_in_config_rejected(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                ),
            ),
        )
        cfg = JointConfiguration(model_id="m", positions={})
        with pytest.raises(ValueError, match="missing"):
            _SERVICE.evaluate(asm, model, cfg)

    def test_extra_joint_in_config_rejected(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                ),
            ),
        )
        cfg = JointConfiguration(
            model_id="m", positions={"j1": 0, "j_extra": 10}
        )
        with pytest.raises(ValueError, match="extra"):
            _SERVICE.evaluate(asm, model, cfg)


class TestUnarticulatedInstance:
    def test_unarticulated_instance_unchanged(self):
        asm = CadAssemblyProgram(
            assembly_id="unart-asm",
            parts=(_DUMMY_PART,),
            imported_components=(),
            instances=(
                CadComponentInstance(
                    instance_id="base",
                    part_id="link",
                    placement=CadRigidTransform(x_mm=0, y_mm=0, z_mm=0),
                ),
                CadComponentInstance(
                    instance_id="link-1",
                    part_id="link",
                    placement=CadRigidTransform(x_mm=30, y_mm=0, z_mm=0),
                ),
                CadComponentInstance(
                    instance_id="static-part",
                    part_id="link",
                    placement=CadRigidTransform(x_mm=100, y_mm=50, z_mm=25),
                ),
            ),
        )
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                ),
            ),
        )
        cfg = JointConfiguration(model_id="m", positions={"j1": 90})
        result = _SERVICE.evaluate(asm, model, cfg)
        t = {i.instance_id: i.transform for i in result.instance_world_transforms}
        assert t["static-part"].x_mm == pytest.approx(100.0, abs=1e-9)
        assert t["static-part"].y_mm == pytest.approx(50.0, abs=1e-9)
        assert t["static-part"].z_mm == pytest.approx(25.0, abs=1e-9)
        assert t["static-part"].rotation_quaternion == pytest.approx(
            (1.0, 0.0, 0.0, 0.0), abs=1e-9
        )


class TestSourceAssemblyImmutability:
    def test_source_not_mutated(self):
        asm = _three_body_assembly()
        model = _three_body_model()
        original = {
            inst.instance_id: (inst.placement.x_mm, inst.placement.y_mm, inst.placement.z_mm)
            for inst in asm.instances
        }
        cfg = _cfg(m="model-3", **{"joint-1": 90, "joint-2": 45})
        _SERVICE.evaluate(asm, model, cfg)
        for inst in asm.instances:
            assert (inst.placement.x_mm, inst.placement.y_mm, inst.placement.z_mm) == (
                original[inst.instance_id][0],
                original[inst.instance_id][1],
                original[inst.instance_id][2],
            )


class TestDeterministicOrderIndependence:
    def test_different_insertion_order_same_result(self):
        asm = _three_body_assembly()
        model = _three_body_model()
        c1 = JointConfiguration(
            model_id="model-3",
            positions={"joint-1": 30, "joint-2": 60},
        )
        c2 = JointConfiguration(
            model_id="model-3",
            positions={"joint-2": 60, "joint-1": 30},
        )
        r1 = _SERVICE.evaluate(asm, model, c1)
        r2 = _SERVICE.evaluate(asm, model, c2)
        assert r1.result_hash == r2.result_hash
        assert r1.transformed_assembly_hash == r2.transformed_assembly_hash
        assert joint_configuration_hash(c1) == joint_configuration_hash(c2)
        for t1, t2 in zip(
            r1.instance_world_transforms, r2.instance_world_transforms
        ):
            assert t1.transform.x_mm == pytest.approx(t2.transform.x_mm, abs=1e-12)
            assert t1.transform.y_mm == pytest.approx(t2.transform.y_mm, abs=1e-12)
            assert t1.transform.z_mm == pytest.approx(t2.transform.z_mm, abs=1e-12)


class TestTransformedAssemblyIdentity:
    def test_transformed_assembly_hash_differs_from_source(self):
        asm = _three_body_assembly()
        model = _three_body_model()
        cfg = _cfg(m="model-3", **{"joint-1": 90, "joint-2": 0})
        result = _SERVICE.evaluate(asm, model, cfg)
        assert result.source_assembly_hash != result.transformed_assembly_hash

    def test_result_hash_starts_with_sha256(self):
        asm = _three_body_assembly()
        model = _three_body_model()
        cfg = _cfg(m="model-3", **{"joint-1": 45, "joint-2": 30})
        result = _SERVICE.evaluate(asm, model, cfg)
        assert result.result_hash.startswith("sha256:")

    def test_evaluator_version_in_result(self):
        asm = _three_body_assembly()
        model = _three_body_model()
        cfg = _cfg(m="model-3", **{"joint-1": 10, "joint-2": 20})
        result = _SERVICE.evaluate(asm, model, cfg)
        assert result.evaluator_version == MULTI_JOINT_FORWARD_KINEMATICS_VERSION


class TestConfigurationIdentity:
    def test_same_semantic_config_same_hash(self):
        c1 = _cfg(m="m", j1=30, j2=60)
        c2 = _cfg(m="m", j1=30, j2=60)
        assert joint_configuration_hash(c1) == joint_configuration_hash(c2)

    def test_different_angle_different_hash(self):
        c1 = _cfg(m="m", j1=30, j2=60)
        c2 = _cfg(m="m", j1=30, j2=61)
        assert joint_configuration_hash(c1) != joint_configuration_hash(c2)


class TestUnlimitedJoint:
    def test_no_limits_allows_large_angle(self):
        asm = _two_body_assembly()
        model = KinematicModel(
            model_id="m",
            joints=(
                RevoluteJointModel(
                    joint_id="j1",
                    parent_instance_id="base",
                    child_instance_id="link-1",
                ),
            ),
        )
        cfg = JointConfiguration(model_id="m", positions={"j1": 720})
        result = _SERVICE.evaluate(asm, model, cfg)
        assert result.ordered_joint_states[0].within_limits is True
        t = {i.instance_id: i.transform for i in result.instance_world_transforms}
        assert t["link-1"].x_mm == pytest.approx(30.0, abs=1e-9)
        assert t["link-1"].y_mm == pytest.approx(0.0, abs=1e-9)


class TestBranchingTree:
    def test_branching_tree_both_children_moved(self):
        asm = _branching_assembly()
        model = KinematicModel(
            model_id="branch",
            joints=(
                RevoluteJointModel(
                    joint_id="jA",
                    parent_instance_id="base",
                    child_instance_id="link-A",
                    axis_direction_x=0,
                    axis_direction_y=0,
                    axis_direction_z=1,
                ),
                RevoluteJointModel(
                    joint_id="jB",
                    parent_instance_id="base",
                    child_instance_id="link-B",
                    axis_direction_x=0,
                    axis_direction_y=0,
                    axis_direction_z=1,
                ),
            ),
        )
        cfg = JointConfiguration(
            model_id="branch", positions={"jA": 90, "jB": 0}
        )
        result = _SERVICE.evaluate(asm, model, cfg)
        t = {i.instance_id: i.transform for i in result.instance_world_transforms}
        # link-A: (30,0,0) rotated 90 about Z -> (0,30,0)
        assert t["link-A"].x_mm == pytest.approx(0.0, abs=1e-9)
        assert t["link-A"].y_mm == pytest.approx(30.0, abs=1e-9)
        # link-B: unchanged at (0,40,0)
        assert t["link-B"].x_mm == pytest.approx(0.0, abs=1e-9)
        assert t["link-B"].y_mm == pytest.approx(40.0, abs=1e-9)


class TestSingleBodyNoJoints:
    def test_no_joints_returns_home(self):
        asm = _two_body_assembly()
        model = KinematicModel(model_id="empty", joints=())
        cfg = JointConfiguration(model_id="empty", positions={})
        result = _SERVICE.evaluate(asm, model, cfg)
        home = {inst.instance_id: inst.placement for inst in asm.instances}
        for iwt in result.instance_world_transforms:
            h = home[iwt.instance_id]
            assert iwt.transform.x_mm == pytest.approx(h.x_mm, abs=1e-9)
            assert iwt.transform.y_mm == pytest.approx(h.y_mm, abs=1e-9)
            assert iwt.transform.z_mm == pytest.approx(h.z_mm, abs=1e-9)
