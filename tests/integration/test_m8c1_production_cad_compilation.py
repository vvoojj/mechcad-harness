import inspect
import json

import pytest

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.application import ProductionApplication
from mechcad_harness.cad_compilation import (
    CadCompilationResult,
    CadCompilationService,
    COMPILER_VERSION,
    MountingPlateDesignSpec,
    mounting_plate_spec_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, ThroughHoleOperation, cad_program_hash
from mechcad_harness.models import Component, DesignState
from mechcad_harness.state import StateManager, state_hash


def make_mounting_plate_spec():
    return MountingPlateDesignSpec(
        part_id="production_motor_mount_plate",
        plate_length_mm=120.0,
        plate_width_mm=100.0,
        plate_thickness_mm=10.0,
        mounting_holes=(
            MountingPlateDesignSpec.HoleSpec(hole_id="motor_1", x_mm=30.0, y_mm=25.0, diameter_mm=8.0),
            MountingPlateDesignSpec.HoleSpec(hole_id="motor_2", x_mm=90.0, y_mm=25.0, diameter_mm=8.0),
            MountingPlateDesignSpec.HoleSpec(hole_id="motor_3", x_mm=90.0, y_mm=75.0, diameter_mm=8.0),
            MountingPlateDesignSpec.HoleSpec(hole_id="motor_4", x_mm=30.0, y_mm=75.0, diameter_mm=8.0),
            MountingPlateDesignSpec.HoleSpec(hole_id="central", x_mm=60.0, y_mm=50.0, diameter_mm=30.0),
        ),
        pockets=(
            MountingPlateDesignSpec.PocketSpec(
                pocket_id="cable_clearance", x_mm=45.0, y_mm=35.0,
                length_mm=30.0, width_mm=20.0, depth_mm=3.0,
            ),
        ),
    )


def build_production_application(tmp_path):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")
    state = DesignState(
        id="DES-production-cad",
        revision=1,
        components=[Component(id="PRT-bracket", name="Bracket")],
    )
    StateManager(workspace).create_project("PRJ-production-cad", state)

    identity = AgentIdentity(
        agent_name="mechcad-transmission",
        agent_version="1.0",
        role="transmission_engineer",
        protocol_version="1.0",
    )
    adapter = FakeAgentAdapter(identity, scripted_responses=())

    return ProductionApplication.create(
        workspace,
        "PRJ-production-cad",
        adapter,
        ownership_path=ownership,
        dependency_path=dependencies,
    )


def test_production_application_exposes_cad_compiler(tmp_path):
    application = build_production_application(tmp_path)
    assert isinstance(application.cad_compiler, CadCompilationService)


def test_production_application_compile_design_spec(tmp_path):
    application = build_production_application(tmp_path)
    source = application.load_state()
    spec = make_mounting_plate_spec()

    result = application.compile_design_spec(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        spec=spec,
    )

    assert isinstance(result, CadCompilationResult)
    assert result.project_id == "PRJ-production-cad"
    assert result.source_revision == source.revision
    assert result.source_state_hash == source.state_hash
    assert result.compiler_version == COMPILER_VERSION
    assert result.spec_hash == mounting_plate_spec_hash(spec)
    assert result.program_hash == cad_program_hash(result.program)
    assert result.program.part_id == "production_motor_mount_plate"
    assert isinstance(result.program.operations[0], BasePlateOperation)
    assert any(isinstance(op, ThroughHoleOperation) for op in result.program.operations)


def test_production_application_compile_determinism(tmp_path):
    application = build_production_application(tmp_path)
    source = application.load_state()
    spec = make_mounting_plate_spec()

    r1 = application.compile_design_spec(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        spec=spec,
    )
    r2 = application.compile_design_spec(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        spec=spec,
    )

    assert r1.program_hash == r2.program_hash
    assert r1.spec_hash == r2.spec_hash
    assert cad_program_hash(r1.program) == cad_program_hash(r2.program)


def test_production_application_compile_stale_source_fails_closed(tmp_path):
    application = build_production_application(tmp_path)
    source = application.load_state()
    spec = make_mounting_plate_spec()

    from mechcad_harness.cad_compilation import DesignSpecStaleSourceError
    with pytest.raises(DesignSpecStaleSourceError):
        application.compile_design_spec(
            source_revision=99,
            source_state_hash=source.state_hash,
            spec=spec,
        )


def test_production_application_compile_hash_mismatch_fails_closed(tmp_path):
    application = build_production_application(tmp_path)
    source = application.load_state()
    spec = make_mounting_plate_spec()

    from mechcad_harness.cad_compilation import DesignSpecHashMismatchError
    with pytest.raises(DesignSpecHashMismatchError):
        application.compile_design_spec(
            source_revision=source.revision,
            source_state_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            spec=spec,
        )


def test_production_module_does_not_import_test_helpers():
    import mechcad_harness.cad_compilation
    source = inspect.getsource(mechcad_harness.cad_compilation)
    assert "tests." not in source
    assert "conftest" not in source
