from math import inf, nan, sqrt
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.structural.models import (
    FRD_RESULT_PARSER_IDENTITY,
    DAT_RESULT_PARSER_IDENTITY,
    INTERPRETER_IDENTITY,
    StressFieldRepresentation,
    StructuralCaseExecutionManifest,
    StructuralAnalysisResult,
    StructuralCriterionResult,
    StructuralCriterionStatus,
    StructuralDisplacementSample,
    StructuralExecutionManifest,
    StructuralLoadCaseResult,
    StructuralResultMaturity,
    StructuralResultParserProvenance,
    StructuralResultUnits,
    StructuralReactionSample,
    StructuralRequestExecutionManifest,
    StructuralStressSample,
    StructuralStressSampleIdentity,
    StructuralStressTensor,
    StructuralResultField,
    StructuralVerificationResult,
    structural_case_manifest_hash,
    execution_manifest_hash,
    structural_request_manifest_hash,
    structural_result_hash,
    structural_verification_hash,
    StructuralExecutionStatus,
    StructuralArtifactRef,
    StructuralSolverManifest,
    LoweredLoadProvenance,
    StructuralMeshManifest,
    PhysicalGroupBinding,
    mesh_manifest_hash,
    CALCULIX_PROVIDER_IDENTITY,
    DECK_BUILDER_IDENTITY,
    GMSH_PROVIDER_IDENTITY,
    REGION_RESOLVER_IDENTITY,
    REGION_RESOLVER_VERSION,
    execution_manifest_hash,
    mesh_input_hash,
)
from mechcad_harness.structural_request import (
    MeshSpecification,
    StructuralAnalysisRequest,
    StructuralExecutionSettings,
    StructuralSourceBinding,
)
from mechcad_harness.models.structural import StructuralResultantForce, structural_definition_hash
from mechcad_harness.models.structural import MaximumDisplacementCriterion, YieldSafetyFactorCriterion
from mechcad_harness.artifacts.storage import ArtifactStore, ArtifactType
from mechcad_harness.structural.results import StructuralResultInterpreter, StructuralVerificationService
from mechcad_harness.structural.deck import cload_semantic_hash
from mechcad_harness.structural.mesh import ParsedMesh, freeze_parsed_mesh
from mechcad_harness.structural.results import (
    CalculiXDatResultParser,
    CalculiXFrdResultParser,
    StructuralResultIntegrityError,
    von_mises_mpa,
    _mesh_hash,
    _parse_verified_mesh,
)
from mechcad_harness.structural.validation import (
    CantileverGeometryObservation,
    CantileverMaterialObservation,
    AnalyticalValidationCheck,
    RectangularCantileverValidationPolicy,
    StructuralAnalyticalValidationResult,
    StructuralAnalyticalValidator,
    cantilever_validation_policy_hash,
)


MESH_HASH = "sha256:" + "m" * 64
FRD_HASH = "sha256:" + "a" * 64
DAT_HASH = "sha256:" + "d" * 64


def _fixture_bytes(name: str) -> bytes:
    return (Path(__file__).parents[1] / "fixtures" / "calculix_2_22" / name).read_bytes()


@pytest.fixture
def parser_mesh():
    nodes = {
        node_id: (float(node_id), 0.0, 0.0)
        for node_id in range(1, 11)
    }
    return ParsedMesh(
        nodes=nodes,
        c3d10={7: tuple(range(1, 11))},
        surface_elements={"fixed": [(1, (1, 2, 3, 4, 5, 6))]},
        volume_elset_name="volume",
        physical_groups=(),
        mesh_bytes=b"parser-mesh",
    )


def test_frd_parser_reads_current_displacement_and_extrapolated_nodal_stress_contract(parser_mesh):
    parsed = CalculiXFrdResultParser().parse(_fixture_bytes("displacement_stress.frd"), parser_mesh)

    displacement = next(sample for sample in parsed.displacements if sample.node_id == 2)
    assert displacement.vector_mm == (0.001, -0.002, 0.003)
    assert parsed.stress_samples[0].representation is StressFieldRepresentation.CALCULIX_EXTRAPOLATED_NODAL_STRESS
    assert parsed.stress_samples[0].tensor_mpa.szx == pytest.approx(-6.0)
    assert parsed.stress_samples[0].identity.element_id is None


def test_frd_parser_rejects_incomplete_required_displacement_domain(parser_mesh):
    with pytest.raises(StructuralResultIntegrityError, match="incomplete DISP domain"):
        CalculiXFrdResultParser().parse(
            _fixture_bytes("displacement_stress.frd"), parser_mesh,
            requested_result_fields=(StructuralResultField.DISPLACEMENT,),
            required_node_ids=frozenset(parser_mesh.nodes),
        )


@pytest.mark.parametrize(
    "tamper",
    [
        lambda payload: b" -1         2 NaN 0.0 0.0\n",
        lambda payload: payload.replace(b" -4  DISP        4    1", b" -4  DISP        5    1"),
        lambda payload: payload[:-2],
        lambda payload: payload.replace(
            b" -1         1 1.00000E-03-2.00000E-03 3.00000E-03",
            b" -1        99 1.00000E-03-2.00000E-03 3.00000E-03",
            1,
        ),
        lambda payload: payload.replace(
            b" -1         2 1.00000E-03-2.00000E-03 3.00000E-03",
            b" -1         1 1.00000E-03-2.00000E-03 3.00000E-03",
            1,
        ),
    ],
)
def test_frd_parser_rejects_invalid_or_truncated_records(tamper, parser_mesh):
    payload = tamper(_fixture_bytes("displacement_stress.frd"))

    with pytest.raises(StructuralResultIntegrityError):
        CalculiXFrdResultParser().parse(payload, parser_mesh)


def test_frd_parser_rejects_unsupported_dataset_and_non_ascii(parser_mesh):
    unsupported = _fixture_bytes("displacement_stress.frd").replace(b"STRESS", b"TEMP", 1)

    with pytest.raises(StructuralResultIntegrityError):
        CalculiXFrdResultParser().parse(unsupported, parser_mesh)

    with pytest.raises(StructuralResultIntegrityError):
        CalculiXFrdResultParser().parse(_fixture_bytes("displacement_stress.frd") + b"\xff", parser_mesh)


@pytest.mark.parametrize(
    "tamper",
    [
        lambda payload: payload.removesuffix(b"9999\n"),
        lambda payload: b"unknown\n" + payload,
        lambda payload: payload.replace(b"9999\n", b"unknown\n9999\n"),
        lambda payload: payload.replace(b" -5  D1", b" -5\tD1", 1),
    ],
)
def test_frd_parser_rejects_missing_trailer_unknown_records_and_tab_mutations(tamper, parser_mesh):
    with pytest.raises(StructuralResultIntegrityError):
        CalculiXFrdResultParser().parse(tamper(_fixture_bytes("displacement_stress.frd")), parser_mesh)


def test_frd_parser_requires_admitted_calculix_program_and_version_records(parser_mesh):
    payload = _fixture_bytes("displacement_stress.frd").replace(
        b"Version 2.22", b"Version 9.99", 1
    )

    with pytest.raises(StructuralResultIntegrityError, match="CalculiX version"):
        CalculiXFrdResultParser().parse(payload, parser_mesh)


@pytest.mark.parametrize(
    "record",
    [
        b"    1UUNTRUSTED          forged\n",
        b"    1UPGM               CalculiX\n",
    ],
)
def test_frd_parser_rejects_extra_duplicate_or_unrecognized_1u_records(parser_mesh, record):
    payload = _fixture_bytes("displacement_stress.frd").replace(
        b"    1UVERSION           Version 2.22\n",
        b"    1UVERSION           Version 2.22\n" + record,
        1,
    )

    with pytest.raises(StructuralResultIntegrityError, match="1U envelope"):
        CalculiXFrdResultParser().parse(payload, parser_mesh)


def test_frd_parser_rejects_unvalidated_element_envelopes(parser_mesh):
    payload = _fixture_bytes("displacement_stress.frd").replace(
        b"1PSTEP", b"3C\n -3\n1PSTEP", 1
    )

    with pytest.raises(StructuralResultIntegrityError, match="element envelope"):
        CalculiXFrdResultParser().parse(payload, parser_mesh)


def test_frd_parser_binds_admitted_element_connectivity_to_mesh(parser_mesh):
    def with_element(connectivity):
        lines = _fixture_bytes("displacement_stress.frd").decode("ascii").splitlines()
        insert_at = lines.index(" -3") + 1
        lines[insert_at:insert_at] = [
            "    3C" + " " * 27 + "  1" + " " * 37 + "1",
            " -1" + f"{7:10d}" + " " * 4 + "6" + " " * 4 + "0" + " " * 4 + "1",
            " -2" + "".join(f"{node_id:10d}" for node_id in connectivity),
            " -3",
        ]
        return ("\n".join(lines) + "\n").encode("ascii")

    assert CalculiXFrdResultParser().parse(with_element(tuple(range(1, 11))), parser_mesh)
    with pytest.raises(StructuralResultIntegrityError, match="connectivity"):
        CalculiXFrdResultParser().parse(with_element((1, 2, 3, 4, 5, 6, 7, 8, 9, 9)), parser_mesh)


def test_frd_parser_allows_only_the_captured_unrelated_error_dataset(parser_mesh):
    error_dataset = (
        b"    1PSTEP                         3           1           1          \n"
        b"  100CL  101 1.000000000           1                     0    1           1\n"
        b" -4  ERROR       1    1\n"
        b" -5  STR(%)      1    1    0    0\n"
        b" -1         1 1.00000E+00\n"
        b" -3\n"
    )
    payload = _fixture_bytes("displacement_stress.frd").replace(b" 9999\n", error_dataset + b" 9999\n")

    parsed = CalculiXFrdResultParser().parse(payload, parser_mesh)
    assert len(parsed.displacements) == 3
    assert len(parsed.stress_samples) == 3


@pytest.mark.parametrize(
    "payload_builder",
    [
        lambda payload: payload.replace(b"\n", b"\r\n"),
        lambda payload: payload.replace(b"\n", b"\r"),
        lambda payload: payload.replace(b"\n", b"\r\n", 1),
    ],
)
def test_frd_parser_accepts_only_uniform_lf_line_endings(payload_builder, parser_mesh):
    with pytest.raises(StructuralResultIntegrityError):
        CalculiXFrdResultParser().parse(payload_builder(_fixture_bytes("displacement_stress.frd")), parser_mesh)


def test_dat_parser_reads_captured_rf_section(parser_mesh):
    parsed = CalculiXDatResultParser().parse_reactions(
        _fixture_bytes("reactions.dat"),
        parser_mesh,
        frozenset({1, 2, 3, 4, 9}),
    )

    assert [reaction.node_id for reaction in parsed] == [1, 2, 3, 4, 9]
    assert {reaction.support_set_name for reaction in parsed} == {"FIXED_NODES"}
    assert parsed[0].vector_n == pytest.approx((1.658556, 1.538604, 1.655428))
    assert parsed[1].vector_n[2] == pytest.approx(-1.657691)


def test_dat_parser_rejects_incomplete_required_support_domain(parser_mesh):
    with pytest.raises(StructuralResultIntegrityError, match="incomplete reaction domain"):
        CalculiXDatResultParser().parse_reactions(
            _fixture_bytes("reactions.dat"), parser_mesh, frozenset({1, 2, 3, 4, 9}),
            required_node_ids=frozenset(parser_mesh.nodes),
        )


@pytest.mark.parametrize(
    "tamper",
    [
        lambda payload: payload.replace(b"         9  1.114289E+01", b"        99  1.114289E+01", 1),
        lambda payload: payload.replace(b"         2  1.678091E+00", b"         1  1.678091E+00", 1),
        lambda payload: payload.replace(b"         1  1.658556E+00", b"         1             NaN", 1),
        lambda payload: payload.replace(b"forces (fx,fy,fz)", b"moments (mx,my,mz)", 1),
        lambda payload: payload[:-2],
        lambda payload: payload.replace(
            b"         3  1.725380E+00 -1.591698E+00  1.764083E+00",
            b"         3  1.725380E+00 -1.591698E+00",
            1,
        ),
    ],
)
def test_dat_parser_rejects_malformed_unknown_duplicate_nonfinite_or_truncated_records(tamper, parser_mesh):
    payload = tamper(_fixture_bytes("reactions.dat"))

    with pytest.raises(StructuralResultIntegrityError):
        CalculiXDatResultParser().parse_reactions(payload, parser_mesh, frozenset({1, 2, 3, 4, 9}))


def test_dat_parser_rejects_reaction_node_outside_allowed_nodes(parser_mesh):
    with pytest.raises(StructuralResultIntegrityError):
        CalculiXDatResultParser().parse_reactions(
            _fixture_bytes("reactions.dat"),
            parser_mesh,
            frozenset({1, 2, 3, 4}),
        )


@pytest.mark.parametrize(
    "tamper",
    [
        lambda payload: payload.replace(b"FIXED_NODES", b"OTHER_NODES", 1),
        lambda payload: payload.replace(b"  1.658556E+00", b" \t1.658556E+00", 1),
        lambda payload: payload.replace(b"\r\n", b"\n"),
        lambda payload: payload.replace(b"\r\n", b"\r"),
        lambda payload: payload.replace(b"\r\n", b"\r\n", 1).replace(b"\r\n", b"\n", 1),
    ],
)
def test_dat_parser_rejects_unexpected_set_tabs_and_non_crlf_line_endings(tamper, parser_mesh):
    payload = _fixture_bytes("reactions.dat")
    with pytest.raises(StructuralResultIntegrityError):
        CalculiXDatResultParser().parse_reactions(tamper(payload), parser_mesh, frozenset({1, 2, 3, 4, 9}))


def test_dat_parser_binds_an_explicit_expected_support_set_name(parser_mesh):
    payload = _fixture_bytes("reactions.dat").replace(b"FIXED_NODES", b"SUPPORT_A")
    parsed = CalculiXDatResultParser().parse_reactions(
        payload,
        parser_mesh,
        frozenset({1, 2, 3, 4, 9}),
        expected_support_set_name="SUPPORT_A",
    )
    assert {reaction.support_set_name for reaction in parsed} == {"SUPPORT_A"}


def _reaction(*, node_id: int = 1):
    return StructuralReactionSample(
        mesh_hash=MESH_HASH,
        node_id=node_id,
        vector_n=(1.0, 0.0, 0.0),
        support_set_name="FIXED_NODES",
        units=StructuralResultUnits(),
    )


def _stress(*, node_id: int = 1, location_id: str | None = None, mesh_hash: str = MESH_HASH):
    return StructuralStressSample(
        identity=StructuralStressSampleIdentity(
            mesh_hash=mesh_hash,
            node_id=node_id,
            location_id=location_id,
        ),
        mesh_hash=mesh_hash,
        representation=StressFieldRepresentation.CALCULIX_EXTRAPOLATED_NODAL_STRESS,
        tensor_mpa=StructuralStressTensor(
            sxx=1.0,
            syy=2.0,
            szz=3.0,
            sxy=0.1,
            syz=0.2,
            szx=0.3,
        ),
        units=StructuralResultUnits(),
    )


def _case_result(*, run_id: str, frd_hash: str, stress_samples=None):
    return StructuralLoadCaseResult(
        run_id=run_id,
        load_case_id="LC-1",
        mesh_hash=MESH_HASH,
        frd_artifact_hash=frd_hash,
        displacements=(
            StructuralDisplacementSample(
                mesh_hash=MESH_HASH,
                node_id=1,
                vector_mm=(0.1, 0.0, 0.0),
                units=StructuralResultUnits(),
            ),
        ),
        stress_samples=tuple(stress_samples if stress_samples is not None else (_stress(),)),
    )


def _execution_manifest_values():
    return {
        "project_id": "PRJ-1",
        "revision": 1,
        "state_hash": "sha256:" + "s" * 64,
        "definition_id": "DEF-1",
        "definition_hash": "sha256:" + "f" * 64,
        "request_hash": "sha256:" + "r" * 64,
        "run_id": "RUN-1",
        "geometry_artifact_id": "GEO-1",
        "geometry_artifact_hash": "sha256:" + "g" * 64,
        "region_map_hash": "sha256:" + "m" * 64,
        "resolver_identity": "resolver",
        "resolver_version": "1",
        "gmsh_identity": "gmsh",
        "gmsh_version": "1",
        "mesh_specification_hash": "sha256:" + "p" * 64,
        "mesh_artifact_id": "MSH-1",
        "mesh_artifact_hash": MESH_HASH,
        "deck_builder_identity": "deck",
        "deck_builder_version": "1",
        "deck_semantic_hash": "sha256:" + "k" * 64,
        "deck_artifact_id": "INP-1",
        "deck_artifact_hash": "sha256:" + "i" * 64,
        "calculix_identity": "ccx",
        "calculix_version": "1",
        "execution_status": StructuralExecutionStatus.SUCCEEDED,
    }


def _durable_request_manifest(*, selected_load_case_ids, case_manifests, execution_status):
    values = _execution_manifest_values()
    values.update(
        {
            "execution_status": execution_status,
            "selected_load_case_ids": tuple(selected_load_case_ids),
            "case_manifests": tuple(case_manifests),
            "deck_semantic_hash": None,
            "deck_artifact_id": None,
            "deck_artifact_hash": None,
        }
    )
    return StructuralExecutionManifest(**values)


def test_case_manifest_and_result_hash_exclude_run_id_but_bind_raw_bytes():
    first = _case_result(run_id="RUN-A", frd_hash=FRD_HASH)
    second = _case_result(run_id="RUN-B", frd_hash=FRD_HASH)
    changed = _case_result(run_id="RUN-B", frd_hash="sha256:" + "b" * 64)

    assert structural_result_hash(first) == structural_result_hash(second)
    assert structural_result_hash(first) != structural_result_hash(changed)

    first_manifest = StructuralCaseExecutionManifest(
        load_case_id="LC-1",
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
        frd_artifact_id="FRD-1",
        frd_artifact_hash=FRD_HASH,
        execution_status=StructuralExecutionStatus.SUCCEEDED,
        run_id="RUN-A",
    )
    second_manifest = first_manifest.model_copy(update={"run_id": "RUN-B"})
    assert structural_case_manifest_hash(first_manifest) == structural_case_manifest_hash(second_manifest)


def test_duplicate_result_identity_requires_distinguishing_location_identity():
    sample = _stress()

    with pytest.raises(ValidationError, match="duplicate stress sample identity"):
        _case_result(run_id="RUN-A", frd_hash=FRD_HASH, stress_samples=(sample, sample))

    distinct = _case_result(
        run_id="RUN-A",
        frd_hash=FRD_HASH,
        stress_samples=(sample, _stress(location_id="element-location-2")),
    )
    assert len(distinct.stress_samples) == 2


def test_duplicate_displacement_identity_is_rejected():
    displacement = StructuralDisplacementSample(
        mesh_hash=MESH_HASH,
        node_id=1,
        vector_mm=(0.1, 0.0, 0.0),
        units=StructuralResultUnits(),
    )

    with pytest.raises(ValidationError, match="duplicate displacement sample identity"):
         StructuralLoadCaseResult(
            load_case_id="LC-1",
            mesh_hash=MESH_HASH,
            frd_artifact_hash=FRD_HASH,
            displacements=(displacement, displacement),
         )


def test_duplicate_reaction_identity_is_rejected():
    with pytest.raises(ValidationError, match="duplicate reaction sample identity"):
        StructuralLoadCaseResult(
            load_case_id="LC-1",
            mesh_hash=MESH_HASH,
            dat_artifact_hash=DAT_HASH,
            reactions=(_reaction(), _reaction()),
        )


def test_reactions_require_dat_and_optional_artifact_hashes_are_nonempty():
    with pytest.raises(ValidationError, match="DAT artifact hash"):
        StructuralLoadCaseResult(
            load_case_id="LC-1",
            mesh_hash=MESH_HASH,
            frd_artifact_hash=FRD_HASH,
            reactions=(_reaction(),),
        )

    with pytest.raises(ValidationError):
        StructuralLoadCaseResult(
            load_case_id="LC-1",
            mesh_hash=MESH_HASH,
            frd_artifact_hash="",
        )

    with pytest.raises(ValidationError):
        StructuralCaseExecutionManifest(
            load_case_id="LC-1",
            mesh_artifact_id="MSH-1",
            mesh_artifact_hash=MESH_HASH,
            frd_artifact_id="FRD-1",
            frd_artifact_hash="",
            execution_status=StructuralExecutionStatus.SUCCEEDED,
        )


def test_optional_artifact_ids_reject_empty_values_on_case_and_execution_manifests():
    with pytest.raises(ValidationError):
        StructuralCaseExecutionManifest(
            load_case_id="LC-1",
            mesh_artifact_id="MSH-1",
            mesh_artifact_hash=MESH_HASH,
            frd_artifact_id="",
            frd_artifact_hash=FRD_HASH,
            execution_status=StructuralExecutionStatus.SUCCEEDED,
         )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("log_artifact_id", "LOG-1"),
        ("log_artifact_hash", "sha256:" + "l" * 64),
        ("frd_artifact_id", "FRD-1"),
        ("frd_artifact_hash", FRD_HASH),
        ("dat_artifact_id", "DAT-1"),
        ("dat_artifact_hash", DAT_HASH),
    ],
)
def test_top_level_optional_artifact_references_require_id_and_hash_pairs(field_name, value):
    with pytest.raises(ValidationError, match="artifact IDs and hashes must be supplied together"):
        StructuralExecutionManifest(**{**_execution_manifest_values(), field_name: value})


@pytest.mark.parametrize(
    "field_name",
    [
        "log_artifact_id",
        "log_artifact_hash",
        "frd_artifact_id",
        "frd_artifact_hash",
        "dat_artifact_id",
        "dat_artifact_hash",
    ],
)
def test_top_level_optional_artifact_references_reject_empty_values(field_name):
    pair = {
        "log_artifact_id": "LOG-1",
        "log_artifact_hash": "sha256:" + "l" * 64,
        "frd_artifact_id": "FRD-1",
        "frd_artifact_hash": FRD_HASH,
        "dat_artifact_id": "DAT-1",
        "dat_artifact_hash": DAT_HASH,
    }
    pair[field_name] = ""
    with pytest.raises(ValidationError):
        StructuralExecutionManifest(**{**_execution_manifest_values(), **pair})

    with pytest.raises(ValidationError):
        StructuralExecutionManifest(
            project_id="PRJ-1",
            revision=1,
            state_hash="sha256:" + "s" * 64,
            definition_id="DEF-1",
            definition_hash="sha256:" + "f" * 64,
            request_hash="sha256:" + "r" * 64,
            run_id="RUN-1",
            geometry_artifact_id="GEO-1",
            geometry_artifact_hash="sha256:" + "g" * 64,
            region_map_hash="sha256:" + "m" * 64,
            resolver_identity="resolver",
            resolver_version="1",
            gmsh_identity="gmsh",
            gmsh_version="1",
            mesh_specification_hash="sha256:" + "p" * 64,
            mesh_artifact_id="MSH-1",
            mesh_artifact_hash=MESH_HASH,
            deck_builder_identity="deck",
            deck_builder_version="1",
            deck_semantic_hash="sha256:" + "k" * 64,
            deck_artifact_id="INP-1",
            deck_artifact_hash="sha256:" + "i" * 64,
            calculix_identity="ccx",
            calculix_version="1",
            execution_status=StructuralExecutionStatus.SUCCEEDED,
            log_artifact_id="",
            log_artifact_hash="sha256:" + "l" * 64,
        )


def test_local_result_ids_require_exact_case_mesh_hash_and_finite_scalars():
    with pytest.raises(ValidationError, match="mesh hash"):
        _case_result(
            run_id="RUN-A",
            frd_hash=FRD_HASH,
            stress_samples=(_stress(mesh_hash="sha256:" + "x" * 64),),
        )

    with pytest.raises(ValidationError):
        StructuralStressTensor(sxx=inf, syy=0.0, szz=0.0, sxy=0.0, syz=0.0, szx=0.0)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: StructuralDisplacementSample(
            mesh_hash=MESH_HASH, node_id=1, vector_mm=(nan, 0.0, 0.0), units=StructuralResultUnits()
        ),
        lambda: StructuralReactionSample(
            mesh_hash=MESH_HASH,
            node_id=1,
            vector_n=(nan, 0.0, 0.0),
            support_set_name="FIXED_NODES",
            units=StructuralResultUnits(),
        ),
        lambda: StructuralStressTensor(sxx=0.0, syy=0.0, szz=0.0, sxy=0.0, syz=0.0, szx=nan),
    ],
)
def test_result_models_reject_nonfinite_values_directly(factory):
    with pytest.raises(ValidationError):
        factory()


def test_result_metadata_has_explicit_units_representation_and_parser_identities():
    assert StructuralResultMaturity.FEA_EXECUTED.value == "FEA_EXECUTED"
    assert StressFieldRepresentation.CALCULIX_EXTRAPOLATED_NODAL_STRESS.value == (
        "calculix_extrapolated_nodal_stress"
    )
    assert StructuralResultParserProvenance().model_dump() == {
        "frd_parser_identity": FRD_RESULT_PARSER_IDENTITY,
        "dat_parser_identity": DAT_RESULT_PARSER_IDENTITY,
        "interpreter_identity": INTERPRETER_IDENTITY,
    }
    assert StructuralResultUnits().model_dump() == {
        "displacement": "mm",
        "stress": "MPa",
        "force": "N",
        "moment": "N*mm",
    }


def test_case_ids_are_nonempty_ordered_and_result_models_are_immutable():
    with pytest.raises(ValidationError, match="load-case IDs"):
        StructuralRequestExecutionManifest(selected_load_case_ids=(), case_manifests=())

    result = _case_result(run_id="RUN-A", frd_hash=FRD_HASH)
    with pytest.raises(ValidationError):
        result.load_case_id = "LC-2"


def test_criterion_result_requires_reason_for_non_pass_status():
    with pytest.raises(ValidationError, match="reason"):
        StructuralCriterionResult(
            criterion_id="criterion-1",
            status=StructuralCriterionStatus.NOT_EVALUABLE,
            reason="",
        )


def _verification(**updates):
    values = {
        "project_id": "PRJ-1",
        "source_revision": 1,
        "source_state_hash": "sha256:" + "s" * 64,
        "definition_id": "DEF-1",
        "definition_hash": "sha256:" + "f" * 64,
        "request_hash": "sha256:" + "r" * 64,
        "execution_manifest_hash": "sha256:" + "n" * 64,
        "result_hash": "sha256:" + "e" * 64,
        "mesh_hash": MESH_HASH,
        "raw_artifact_hashes": (FRD_HASH, DAT_HASH),
        "parser_provenance": StructuralResultParserProvenance(),
        "overall_status": StructuralCriterionStatus.PASS,
        "criterion_results": (
            StructuralCriterionResult(
                criterion_id="criterion-1",
                status=StructuralCriterionStatus.PASS,
            ),
        ),
    }
    values.update(updates)
    return StructuralVerificationResult(**values)


def test_verification_is_source_result_bound_and_hashes_all_provenance_inputs():
    baseline = _verification()
    for field, changed in (
        ("request_hash", "sha256:" + "q" * 64),
        ("result_hash", "sha256:" + "z" * 64),
        ("mesh_hash", "sha256:" + "x" * 64),
        ("raw_artifact_hashes", (DAT_HASH,)),
        ("source_revision", 2),
    ):
        changed_result = _verification(**{field: changed})
        assert structural_verification_hash(changed_result) != structural_verification_hash(baseline)

    with pytest.raises(ValidationError):
        invalid = baseline.model_dump()
        invalid["project_id"] = ""
        StructuralVerificationResult(**invalid)


def test_verification_rejects_duplicate_criterion_ids():
    criterion = StructuralCriterionResult(
        criterion_id="criterion-1",
        status=StructuralCriterionStatus.PASS,
    )
    with pytest.raises(ValidationError, match="criterion IDs must be unique"):
        _verification(criterion_results=(criterion, criterion))


def test_request_manifest_hash_binds_ordered_case_manifest_identities():
    first_case = StructuralCaseExecutionManifest(
        load_case_id="LC-1",
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
        frd_artifact_id="FRD-1",
        frd_artifact_hash=FRD_HASH,
        execution_status=StructuralExecutionStatus.SUCCEEDED,
    )
    second_case = StructuralCaseExecutionManifest(
        load_case_id="LC-2",
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
        frd_artifact_id="FRD-1",
        frd_artifact_hash=FRD_HASH,
        execution_status=StructuralExecutionStatus.SUCCEEDED,
    )
    request_manifest = StructuralRequestExecutionManifest(
        selected_load_case_ids=("LC-1", "LC-2"),
        case_manifests=(first_case, second_case),
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
    )
    assert request_manifest.request_manifest_hash == structural_request_manifest_hash(request_manifest)

    with pytest.raises(ValidationError, match="request manifest hash"):
        StructuralExecutionManifest(
            project_id="PRJ-1", revision=1, state_hash="sha256:" + "s" * 64,
            definition_id="DEF-1", definition_hash="sha256:" + "f" * 64,
            request_hash="sha256:" + "r" * 64, run_id="RUN-1",
            geometry_artifact_id="GEO-1", geometry_artifact_hash="sha256:" + "g" * 64,
            region_map_hash="sha256:" + "m" * 64, resolver_identity="resolver", resolver_version="1",
            gmsh_identity="gmsh", gmsh_version="1", mesh_specification_hash="sha256:" + "p" * 64,
            mesh_artifact_id="MSH-1", mesh_artifact_hash=MESH_HASH,
            deck_builder_identity="deck", deck_builder_version="1",
            calculix_identity="ccx", calculix_version="1",
            execution_status=StructuralExecutionStatus.SUCCEEDED,
            solver_manifest=None,
            log_artifact_id=None, log_artifact_hash=None,
            frd_artifact_id=None, frd_artifact_hash=None,
            dat_artifact_id=None, dat_artifact_hash=None,
            selected_load_case_ids=("LC-1", "LC-2"), case_manifests=(first_case, second_case),
            request_manifest_hash="sha256:" + "0" * 64,
        )


def test_standalone_request_manifest_requires_exact_shared_mesh_identity():
    case = StructuralCaseExecutionManifest(
        load_case_id="LC-1",
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
        execution_status=StructuralExecutionStatus.SUCCEEDED,
    )

    with pytest.raises(ValidationError, match="shared mesh artifact ID and hash are required"):
        StructuralRequestExecutionManifest(
            selected_load_case_ids=("LC-1",),
            case_manifests=(case,),
        )

    with pytest.raises(ValidationError, match="shared mesh artifact"):
        StructuralRequestExecutionManifest(
            selected_load_case_ids=("LC-1",),
            case_manifests=(case,),
            mesh_artifact_id="MSH-OTHER",
            mesh_artifact_hash=MESH_HASH,
        )

    with pytest.raises(ValidationError, match="shared mesh artifact"):
        StructuralRequestExecutionManifest(
            selected_load_case_ids=("LC-1",),
            case_manifests=(case,),
            mesh_artifact_id="MSH-1",
            mesh_artifact_hash="sha256:" + "x" * 64,
        )

    manifest = StructuralRequestExecutionManifest(
        selected_load_case_ids=("LC-1",),
        case_manifests=(case,),
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
    )
    assert manifest.mesh_artifact_id == case.mesh_artifact_id
    assert manifest.mesh_artifact_hash == case.mesh_artifact_hash


def test_request_manifest_accepts_complete_success_and_last_case_failure():
    first_case = StructuralCaseExecutionManifest(
        load_case_id="LC-1",
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
        execution_status=StructuralExecutionStatus.SUCCEEDED,
    )
    second_success = StructuralCaseExecutionManifest(
        load_case_id="LC-2",
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
        execution_status=StructuralExecutionStatus.SUCCEEDED,
    )
    successful = StructuralRequestExecutionManifest(
        selected_load_case_ids=("LC-1", "LC-2"),
        case_manifests=(first_case, second_success),
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
    )
    assert successful.execution_status is StructuralExecutionStatus.SUCCEEDED

    second_failure = StructuralCaseExecutionManifest(
        load_case_id="LC-2",
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
        execution_status=StructuralExecutionStatus.SOLVER_FAILED,
    )
    failed = StructuralRequestExecutionManifest(
        selected_load_case_ids=("LC-1", "LC-2"),
        case_manifests=(first_case, second_failure),
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
        execution_status=StructuralExecutionStatus.SOLVER_FAILED,
    )
    assert failed.case_manifests[-1].execution_status is StructuralExecutionStatus.SOLVER_FAILED


@pytest.mark.parametrize(
    "case_statuses",
    [
        (StructuralExecutionStatus.SUCCEEDED, StructuralExecutionStatus.SUCCEEDED),
        (StructuralExecutionStatus.SOLVER_FAILED, StructuralExecutionStatus.SUCCEEDED),
        (StructuralExecutionStatus.SOLVER_FAILED, StructuralExecutionStatus.SOLVER_FAILED),
    ],
)
def test_failed_request_manifest_rejects_impossible_case_histories(case_statuses):
    cases = tuple(
        StructuralCaseExecutionManifest(
            load_case_id=f"LC-{index}",
            mesh_artifact_id="MSH-1",
            mesh_artifact_hash=MESH_HASH,
            execution_status=status,
        )
        for index, status in enumerate(case_statuses, start=1)
    )
    with pytest.raises(ValidationError, match="failed request manifests"):
        StructuralRequestExecutionManifest(
            selected_load_case_ids=("LC-1", "LC-2"),
            case_manifests=cases,
            mesh_artifact_id="MSH-1",
            mesh_artifact_hash=MESH_HASH,
            execution_status=StructuralExecutionStatus.SOLVER_FAILED,
        )


@pytest.mark.parametrize(
    "case_statuses",
    [
        (StructuralExecutionStatus.SUCCEEDED, StructuralExecutionStatus.SUCCEEDED),
        (StructuralExecutionStatus.SOLVER_FAILED, StructuralExecutionStatus.SUCCEEDED),
        (StructuralExecutionStatus.SOLVER_FAILED, StructuralExecutionStatus.SOLVER_FAILED),
    ],
)
def test_durable_request_manifest_rejects_impossible_case_histories(case_statuses):
    cases = tuple(
        StructuralCaseExecutionManifest(
            load_case_id=f"LC-{index}",
            mesh_artifact_id="MSH-1",
            mesh_artifact_hash=MESH_HASH,
            execution_status=status,
        )
        for index, status in enumerate(case_statuses, start=1)
    )

    with pytest.raises(ValidationError):
        _durable_request_manifest(
            selected_load_case_ids=("LC-1", "LC-2"),
            case_manifests=cases,
            execution_status=StructuralExecutionStatus.SOLVER_FAILED,
        )


def test_durable_request_manifest_accepts_complete_success_and_last_case_failure():
    first_case = StructuralCaseExecutionManifest(
        load_case_id="LC-1",
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
        execution_status=StructuralExecutionStatus.SUCCEEDED,
    )
    second_success = StructuralCaseExecutionManifest(
        load_case_id="LC-2",
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
        execution_status=StructuralExecutionStatus.SUCCEEDED,
    )
    successful = _durable_request_manifest(
        selected_load_case_ids=("LC-1", "LC-2"),
        case_manifests=(first_case, second_success),
        execution_status=StructuralExecutionStatus.SUCCEEDED,
    )
    assert successful.case_manifests[-1].execution_status is StructuralExecutionStatus.SUCCEEDED

    second_case = StructuralCaseExecutionManifest(
        load_case_id="LC-2",
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
        execution_status=StructuralExecutionStatus.SOLVER_FAILED,
    )

    failed = _durable_request_manifest(
        selected_load_case_ids=("LC-1", "LC-2"),
        case_manifests=(first_case, second_case),
        execution_status=StructuralExecutionStatus.SOLVER_FAILED,
    )

    assert failed.case_manifests[-1].execution_status is StructuralExecutionStatus.SOLVER_FAILED


def test_execution_manifest_hash_binds_request_manifest_hash():
    base = dict(
        project_id="PRJ-1",
        revision=1,
        state_hash="sha256:" + "s" * 64,
        definition_id="DEF-1",
        definition_hash="sha256:" + "f" * 64,
        request_hash="sha256:" + "r" * 64,
        run_id="RUN-1",
        geometry_artifact_id="GEO-1",
        geometry_artifact_hash="sha256:" + "g" * 64,
        region_map_hash="sha256:" + "m" * 64,
        resolver_identity="resolver",
        resolver_version="1",
        gmsh_identity="gmsh",
        gmsh_version="1",
        mesh_specification_hash="sha256:" + "p" * 64,
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=MESH_HASH,
        deck_builder_identity="deck",
        deck_builder_version="1",
        deck_semantic_hash="sha256:" + "k" * 64,
        deck_artifact_id="INP-1",
        deck_artifact_hash="sha256:" + "i" * 64,
        calculix_identity="ccx",
        calculix_version="1",
        execution_status=StructuralExecutionStatus.SUCCEEDED,
    )
    first = StructuralExecutionManifest(
        **base,
        request_manifest_hash="sha256:" + "a" * 64,
    )
    second = StructuralExecutionManifest(
        **base,
        request_manifest_hash="sha256:" + "b" * 64,
    )

    assert execution_manifest_hash(first) != execution_manifest_hash(second)


def _analysis_result(**updates):
    source_binding = StructuralSourceBinding(
        project_id="PRJ-1",
        source_revision=1,
        source_state_hash="sha256:" + "s" * 64,
        definition_id="DEF-1",
        definition_hash="sha256:" + "f" * 64,
        target_body_id="BODY-1",
        source_program_hash="sha256:" + "p" * 64,
        geometry_identity="geometry",
        geometry_artifact_id="GEO-1",
        geometry_artifact_hash="sha256:" + "g" * 64,
    )
    values = {
        "source_binding": source_binding,
        "definition_id": "DEF-1",
        "definition_hash": source_binding.definition_hash,
        "request_hash": "sha256:" + "r" * 64,
        "execution_manifest_hash": "sha256:" + "e" * 64,
        "mesh_hash": MESH_HASH,
        "load_case_results": (_case_result(run_id="RUN-A", frd_hash=FRD_HASH),),
    }
    values.update(updates)
    return StructuralAnalysisResult(**values)


def test_analysis_result_hash_binds_source_definition_request_and_execution():
    baseline = _analysis_result()
    changed_source = _analysis_result(
        source_binding=baseline.source_binding.model_copy(
            update={"source_state_hash": "sha256:" + "x" * 64}
        )
    )

    assert structural_result_hash(changed_source) != structural_result_hash(baseline)
    assert structural_result_hash(
        _analysis_result(
            definition_hash="sha256:" + "d" * 64,
            source_binding=baseline.source_binding.model_copy(
                update={"definition_hash": "sha256:" + "d" * 64}
            ),
        )
    ) != structural_result_hash(baseline)
    assert structural_result_hash(
        _analysis_result(request_hash="sha256:" + "q" * 64)
    ) != structural_result_hash(baseline)
    assert structural_result_hash(
        _analysis_result(execution_manifest_hash="sha256:" + "z" * 64)
    ) != structural_result_hash(baseline)


def test_execution_manifest_rejects_case_mesh_reference_not_matching_shared_mesh():
    case = StructuralCaseExecutionManifest(
        load_case_id="LC-1",
        mesh_artifact_id="MSH-OTHER",
        mesh_artifact_hash=MESH_HASH,
        execution_status=StructuralExecutionStatus.SUCCEEDED,
    )

    with pytest.raises(ValidationError, match="shared mesh artifact"):
        StructuralExecutionManifest(
            project_id="PRJ-1",
            revision=1,
            state_hash="sha256:" + "s" * 64,
            definition_id="DEF-1",
            definition_hash="sha256:" + "f" * 64,
            request_hash="sha256:" + "r" * 64,
            run_id="RUN-1",
            geometry_artifact_id="GEO-1",
            geometry_artifact_hash="sha256:" + "g" * 64,
            region_map_hash="sha256:" + "m" * 64,
            resolver_identity="resolver",
            resolver_version="1",
            gmsh_identity="gmsh",
            gmsh_version="1",
            mesh_specification_hash="sha256:" + "p" * 64,
            mesh_artifact_id="MSH-1",
            mesh_artifact_hash=MESH_HASH,
            deck_builder_identity="deck",
            deck_builder_version="1",
            deck_semantic_hash="sha256:" + "k" * 64,
            deck_artifact_id="INP-1",
            deck_artifact_hash="sha256:" + "i" * 64,
            calculix_identity="ccx",
            calculix_version="1",
            execution_status=StructuralExecutionStatus.SUCCEEDED,
            selected_load_case_ids=("LC-1",),
            case_manifests=(case,),
        )


@pytest.mark.parametrize(
    ("tensor", "expected"),
    [
        (StructuralStressTensor(sxx=12, syy=0, szz=0, sxy=0, syz=0, szx=0), 12),
        (StructuralStressTensor(sxx=7, syy=7, szz=7, sxy=0, syz=0, szx=0), 0),
        (StructuralStressTensor(sxx=0, syy=0, szz=0, sxy=5, syz=0, szx=0), sqrt(3) * 5),
    ],
)
def test_von_mises_known_states(tensor, expected):
    assert von_mises_mpa(tensor) == pytest.approx(expected)


def test_criterion_result_records_consumed_result_field():
    result = StructuralCriterionResult(
        criterion_id="criterion-1",
        status=StructuralCriterionStatus.PASS,
        consumed_result_field="nodal_displacement_magnitude_on_region",
    )

    assert result.consumed_result_field == "nodal_displacement_magnitude_on_region"


def test_verification_raw_hashes_include_log_artifact():
    from mechcad_harness.structural.results import StructuralVerificationService

    case = _case_result(run_id="RUN-A", frd_hash=FRD_HASH)
    case = StructuralLoadCaseResult(**{
        **case.model_dump(mode="json"),
        "log_artifact_hash": "sha256:" + "l" * 64,
        "result_hash": "pending",
    })
    definition = __import__("test_structural_service", fromlist=["_definition"])._definition()
    definition_hash = structural_definition_hash(definition)
    result = _analysis_result(
        definition_hash=definition_hash,
        source_binding=__import__("mechcad_harness.structural_request", fromlist=["StructuralSourceBinding"])
        .StructuralSourceBinding(**{
            **_analysis_result().source_binding.model_dump(mode="json"),
            "definition_hash": definition_hash,
        }),
        load_case_results=(case,),
    )
    verification = StructuralVerificationService().evaluate(
        result, definition
    )

    assert case.log_artifact_hash in verification.raw_artifact_hashes


def _cantilever_mesh():
    mesh_bytes = """$MeshFormat
2.2 0 8
$EndMeshFormat
$PhysicalNames
3
2 1 "fixed"
2 2 "free"
3 3 "volume"
$EndPhysicalNames
$Nodes
12
1 10 0 0
2 10 2 0
3 10 0 2
4 10 2 2
5 10 1 0
6 10 1 1
7 10 0 1
8 10 2 1
9 10 1 2
10 0 0 0
11 0 2 0
12 0 0 2
$EndNodes
$Elements
4
1 9 2 1 1 10 11 12 10 11 12
2 9 2 2 2 1 2 3 5 6 7
3 9 2 2 2 2 4 3 8 9 6
4 11 2 3 3 1 2 3 4 5 6 7 8 9 10
$EndElements
""".encode("ascii")
    return ParsedMesh(
        nodes={
            1: (10.0, 0.0, 0.0), 2: (10.0, 2.0, 0.0), 3: (10.0, 0.0, 2.0),
            4: (10.0, 2.0, 2.0), 5: (10.0, 1.0, 0.0), 6: (10.0, 1.0, 1.0),
            7: (10.0, 0.0, 1.0), 8: (10.0, 2.0, 1.0), 9: (10.0, 1.0, 2.0),
            10: (0.0, 0.0, 0.0), 11: (0.0, 2.0, 0.0), 12: (0.0, 0.0, 2.0),
        },
        c3d10={1: tuple(range(1, 11))},
        surface_elements={
            "fixed": [(1, (10, 11, 12, 10, 11, 12))],
            "free": [
                (2, (1, 2, 3, 5, 6, 7)),
                (3, (2, 4, 3, 8, 9, 6)),
            ],
        },
        volume_elset_name="volume",
        physical_groups=(
            PhysicalGroupBinding(semantic_region_id="fixed", physical_group_name="fixed", gmsh_entity_dim=2, gmsh_entity_id=1),
            PhysicalGroupBinding(semantic_region_id="free", physical_group_name="free", gmsh_entity_dim=2, gmsh_entity_id=2),
            PhysicalGroupBinding(semantic_region_id=None, physical_group_name="volume", gmsh_entity_dim=3, gmsh_entity_id=3),
        ),
        mesh_bytes=mesh_bytes,
    )


def _cantilever_request():
    binding = StructuralSourceBinding(
        project_id="PRJ-CANTILEVER", source_revision=1, source_state_hash="sha256:" + "s" * 64,
        definition_id="DEF-CANTILEVER", definition_hash="sha256:" + "d" * 64,
        target_body_id="BODY-CANTILEVER", source_program_hash="sha256:" + "p" * 64,
        geometry_identity="cantilever", geometry_artifact_id="GEO-CANTILEVER",
        geometry_artifact_hash="sha256:" + "g" * 64,
    )
    request = StructuralAnalysisRequest(
        source_binding=binding,
        selected_load_case_ids=("LC-1",),
        mesh_specification=MeshSpecification(global_target_size_mm=1.0, quality_policy_id="q", mesher_settings_version="1"),
        requested_result_fields=(StructuralResultField.DISPLACEMENT, StructuralResultField.REACTIONS),
        execution_settings=StructuralExecutionSettings(
            max_elements=1000, max_runtime_seconds=30, max_output_bytes=100000, retain_raw_artifacts=True,
        ),
    )
    policy = _cantilever_policy(request=request)
    return StructuralAnalysisRequest.model_validate({
        **request.model_dump(mode="json"),
        "analytical_policy_hash": cantilever_validation_policy_hash(policy),
        "request_hash": "pending",
    })


def _cantilever_manifest(request, mesh):
    mesh_hash = _mesh_hash(mesh)
    region_hash = "sha256:" + "r" * 64
    mesh_spec_hash = StructuralResultInterpreter._mesh_specification_hash(request)
    mesh_manifest = StructuralMeshManifest(
        mesh_specification_hash=mesh_spec_hash, gmsh_identity="gmsh", gmsh_version="1",
        element_family="c3d10", node_count=len(mesh.nodes), volume_element_count=1,
        boundary_element_count=3, volume_entity_id=3, physical_groups=mesh.physical_groups,
        mesh_hash=mesh_hash, region_map_hash=region_hash,
    )
    case = StructuralCaseExecutionManifest(
        load_case_id="LC-1", mesh_artifact_id="MSH-CANTILEVER", mesh_artifact_hash=mesh_hash,
        deck_artifact_id="INP-CANTILEVER", deck_artifact_hash="sha256:" + "i" * 64,
        deck_semantic_hash="sha256:" + "k" * 64, frd_artifact_id="FRD-CANTILEVER",
        frd_artifact_hash=FRD_HASH, dat_artifact_id="DAT-CANTILEVER", dat_artifact_hash=DAT_HASH,
        log_artifact_id="LOG-CANTILEVER", log_artifact_hash="sha256:" + "l" * 64,
        execution_status=StructuralExecutionStatus.SUCCEEDED,
    )
    return StructuralExecutionManifest(
        project_id=request.source_binding.project_id, revision=1,
        state_hash=request.source_binding.source_state_hash, definition_id=request.source_binding.definition_id,
        definition_hash=request.source_binding.definition_hash, request_hash=request.request_hash,
        analytical_policy_hash=request.analytical_policy_hash, run_id="RUN-CANTILEVER",
        geometry_artifact_id=request.source_binding.geometry_artifact_id,
        geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
        region_map_hash=region_hash, resolver_identity="resolver", resolver_version="1",
        gmsh_identity="gmsh", gmsh_version="1", mesh_specification_hash=mesh_spec_hash,
        mesh_artifact_id="MSH-CANTILEVER", mesh_artifact_hash=mesh_hash,
        mesh_manifest=mesh_manifest, mesh_manifest_hash=mesh_manifest_hash(mesh_manifest),
        deck_builder_identity="deck", deck_builder_version="1", calculix_identity="ccx",
        calculix_version="2.22", execution_status=StructuralExecutionStatus.SUCCEEDED,
        selected_load_case_ids=("LC-1",), case_manifests=(case,),
    )


def _cantilever_policy(relative_tolerance: float = 0.03, request=None):
    request = request or _cantilever_request()
    mesh = _cantilever_mesh()
    return RectangularCantileverValidationPolicy(
        request_hash=request.request_hash,
        geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
        material_identity="MAT-1",
        length_mm=10.0,
        width_mm=2.0,
        height_mm=2.0,
        elastic_modulus_mpa=1000.0,
        poisson_ratio=0.3,
        resultant_force_n=(0.0, -15.0, 0.0),
        mesh_specification_hash=StructuralResultInterpreter._mesh_specification_hash(request),
        mesh_hash=_mesh_hash(mesh),
        region_map_hash="sha256:" + "r" * 64,
        free_end_region_id="free",
        fixed_end_region_id="fixed",
        free_end_area_mm2=4.0,
        reference_point_mm=(0.0, 1.0, 1.0),
        displacement_relative_tolerance=relative_tolerance,
        reaction_relative_tolerance=relative_tolerance,
    )


def _cantilever_result():
    mesh_hash = _mesh_hash(_cantilever_mesh())
    displacement_samples = tuple(
        StructuralDisplacementSample(
            mesh_hash=mesh_hash,
            node_id=node_id,
            vector_mm=(0.0, value, 0.0),
            units=StructuralResultUnits(),
        )
        for node_id, value in (
            (1, 0.0), (2, 0.0), (3, 0.0), (4, 0.0), (5, -5.625), (6, -5.625),
            (7, 0.0), (8, -5.625), (9, 0.0),
        )
    )
    return StructuralLoadCaseResult(
        load_case_id="LC-1",
        mesh_hash=mesh_hash,
        deck_artifact_hash="sha256:" + "i" * 64,
        frd_artifact_hash=FRD_HASH,
        dat_artifact_hash=DAT_HASH,
        log_artifact_hash="sha256:" + "l" * 64,
        displacements=displacement_samples,
        reactions=tuple(
            StructuralReactionSample(
                mesh_hash=mesh_hash,
                node_id=node_id,
                vector_n={10: (75.0, 3.75, 0.0), 11: (-75.0, 3.75, 0.0), 12: (0.0, 7.5, 0.0)}[node_id],
                support_set_name="FIXED_NODES",
                units=StructuralResultUnits(),
            )
            for node_id in (10, 11, 12)
        ),
        requested_result_fields=(StructuralResultField.DISPLACEMENT, StructuralResultField.REACTIONS),
        region_node_ids=(("free", (1, 2, 3, 4, 5, 6, 7, 8, 9)), ("fixed", (10, 11, 12))),
        total_reaction_force_n=(0.0, 15.0, 0.0),
        reaction_reference_point_mm=(0.0, 1.0, 1.0),
        total_reaction_moment_n_mm=(0.0, 0.0, 150.0),
        applied_force_n=(0.0, -15.0, 0.0),
        applied_moment_n_mm=(15.0, 0.0, -150.0),
    )


def _validate_cantilever(
    *, policy=None, result=None, mesh=None, request=None, manifest=None,
    geometry_observation=None, mesh_artifact_bytes=None,
):
    mesh = mesh or _cantilever_mesh()
    request = request or _cantilever_request()
    manifest = manifest or _cantilever_manifest(request, mesh)
    return StructuralAnalyticalValidator().validate(
        result or _cantilever_result(),
        policy or _cantilever_policy(request=request),
        request=request,
        execution_manifest=manifest,
        mesh=mesh,
        mesh_artifact_bytes=mesh_artifact_bytes or mesh.mesh_bytes,
        geometry_observation=geometry_observation or CantileverGeometryObservation(
            project_id=request.source_binding.project_id,
            source_revision=request.source_binding.source_revision,
            source_state_hash=request.source_binding.source_state_hash,
            definition_id=request.source_binding.definition_id,
            definition_hash=request.source_binding.definition_hash,
            geometry_artifact_id=request.source_binding.geometry_artifact_id,
            geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
            length_mm=10.0, width_mm=2.0, height_mm=2.0, free_end_area_mm2=4.0,
        ),
        material_observation=CantileverMaterialObservation(
            project_id=request.source_binding.project_id,
            source_revision=request.source_binding.source_revision,
            source_state_hash=request.source_binding.source_state_hash,
            definition_id=request.source_binding.definition_id,
            definition_hash=request.source_binding.definition_hash,
            geometry_artifact_id=request.source_binding.geometry_artifact_id,
            geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
            material_identity="MAT-1", elastic_modulus_mpa=1000.0, poisson_ratio=0.3,
        ),
    )


def test_policy_hash_changes_when_tolerance_changes_and_policy_is_frozen():
    first = _cantilever_policy(0.03)
    second = _cantilever_policy(0.04)

    assert cantilever_validation_policy_hash(first) != cantilever_validation_policy_hash(second)
    with pytest.raises(ValidationError):
        first.length_mm = 11.0


def test_validator_uses_quadratic_cps6_surface_integral_and_persists_checks():
    result = _validate_cantilever()

    assert result.status == "pass"
    assert result.validation_hash.startswith("sha256:")
    assert {check.check_id for check in result.checks} == {
        "geometry", "material", "load", "tip_displacement", "reaction_force", "reaction_moment",
    }
    tip = next(check for check in result.checks if check.check_id == "tip_displacement")
    assert tip.observed_value == pytest.approx(-3.75)
    assert tip.observed_value != pytest.approx((-5.625 + -5.625) / 6.0)


def test_cps6_surface_integral_gives_zero_corner_weight_and_preserves_constant_field():
    mesh = _cantilever_mesh()
    case = _cantilever_result().model_copy(update={
        "displacements": tuple(
            sample.model_copy(update={"vector_mm": (0.0, 2.5, 0.0)})
            for sample in _cantilever_result().displacements
        ),
        "result_hash": "pending",
    })

    assert StructuralAnalyticalValidator._tip_displacement(
        case, _cantilever_policy(), mesh, free_end_area_mm2=4.0
    ) == pytest.approx(2.5)


def test_analytical_tip_displacement_uses_signed_applied_force_convention():
    assert StructuralAnalyticalValidator._expected_tip_displacement(_cantilever_policy()) == pytest.approx(-3.75)


def test_validator_reports_fail_for_wrong_tip_displacement():
    wrong = StructuralLoadCaseResult.model_validate({
        **_cantilever_result().model_dump(mode="json"),
        "displacements": [
            {
                **sample.model_dump(mode="json"),
                "vector_mm": (sample.vector_mm[0], 999.0 if sample.node_id == 5 else sample.vector_mm[1], sample.vector_mm[2]),
            }
            for sample in _cantilever_result().displacements
        ],
        "result_hash": "pending",
    })

    assert _validate_cantilever(result=wrong).status == "fail"


def test_validator_rejects_dynamic_analytical_observation_forgery():
    forged = _cantilever_result().model_copy(update={"analytical_tip_displacement_mm": 999.0})

    with pytest.raises(ValueError, match="dynamic analytical observation"):
        _validate_cantilever(result=forged)


def test_validator_rejects_forged_source_result_hash_before_recording():
    forged = _cantilever_result().model_copy(update={"result_hash": "sha256:" + "f" * 64})

    with pytest.raises(ValueError, match="source structural_result_hash"):
        _validate_cantilever(result=forged)


def test_validator_fails_for_wrong_mesh_bytes():
    wrong_mesh = _cantilever_mesh()
    wrong_mesh.mesh_bytes = b"wrong-mesh-bytes"

    with pytest.raises(ValueError, match="authoritative MSH artifact bytes"):
        _validate_cantilever(mesh=wrong_mesh)


def test_validator_fails_when_execution_geometry_artifact_id_does_not_match_request():
    request = _cantilever_request()
    manifest = _cantilever_manifest(request, _cantilever_mesh()).model_copy(
        update={"geometry_artifact_id": "GEO-FORGED"}
    )

    assert _validate_cantilever(request=request, manifest=manifest).status == "fail"


def test_validator_rejects_absent_or_mismatched_predeclared_policy_hash():
    request = _cantilever_request()
    absent = StructuralAnalysisRequest.model_validate({
        **request.model_dump(mode="json"),
        "analytical_policy_hash": None,
        "request_hash": "pending",
    })
    assert _validate_cantilever(request=absent, manifest=_cantilever_manifest(absent, _cantilever_mesh())).status == "fail"

    mismatched = StructuralAnalysisRequest.model_validate({
        **request.model_dump(mode="json"),
        "analytical_policy_hash": "sha256:" + "x" * 64,
        "request_hash": "pending",
    })
    assert _validate_cantilever(
        request=mismatched,
        manifest=_cantilever_manifest(mismatched, _cantilever_mesh()),
        policy=_cantilever_policy(request=mismatched),
    ).status == "fail"


def test_validator_fails_for_wrong_policy_mesh_specification_hash():
    policy = _cantilever_policy().model_copy(update={"mesh_specification_hash": "sha256:" + "x" * 64})

    assert _validate_cantilever(policy=policy).status == "fail"


def test_validator_fails_for_wrong_policy_region_mapping():
    policy = _cantilever_policy().model_copy(update={"region_map_hash": "sha256:" + "x" * 64})

    assert _validate_cantilever(policy=policy).status == "fail"


def test_validator_fails_for_wrong_fixed_end_region():
    policy = _cantilever_policy().model_copy(update={"fixed_end_region_id": "other"})

    assert _validate_cantilever(policy=policy).status == "fail"


def test_validator_fails_for_axial_force_outside_declared_transverse_axis():
    policy = _cantilever_policy().model_copy(update={"resultant_force_n": (2.0, -15.0, 0.0)})

    result = _validate_cantilever(policy=policy)

    assert result.status == "fail"
    assert next(check for check in result.checks if check.check_id == "tip_displacement").reason == (
        "axial force is outside the declared transverse direction"
    )


def test_validator_fails_for_wrong_reaction_reference_point():
    wrong_reference = StructuralLoadCaseResult.model_validate({
        **_cantilever_result().model_dump(mode="json"),
        "reaction_reference_point_mm": (0.0, 0.0, 0.0),
        "result_hash": "pending",
    })

    assert _validate_cantilever(result=wrong_reference).status == "fail"


def test_validator_fails_for_incomplete_free_end_cps6_coverage():
    incomplete = StructuralLoadCaseResult.model_validate({
        **_cantilever_result().model_dump(mode="json"),
        "region_node_ids": [["free", [1, 2, 3, 4, 5, 6, 7, 8]], ["fixed", [10, 11, 12]]],
        "result_hash": "pending",
    })

    assert _validate_cantilever(result=incomplete).status == "fail"


def test_validator_requires_reaction_node_ids_to_equal_trusted_fixed_region_nodes():
    values = _cantilever_result().model_dump(mode="json")
    values["reactions"] = values["reactions"][:1]
    values["result_hash"] = "pending"

    assert _validate_cantilever(result=StructuralLoadCaseResult.model_validate(values)).status == "fail"


def test_validator_recomputes_reactions_from_trusted_samples_not_stored_summaries():
    values = _cantilever_result().model_dump(mode="json")
    values.update({
        "total_reaction_force_n": (999.0, 999.0, 999.0),
        "total_reaction_moment_n_mm": (999.0, 999.0, 999.0),
        "result_hash": "pending",
    })
    forged = StructuralLoadCaseResult.model_validate(values)

    assert _validate_cantilever(result=forged).status == "pass"


def test_validator_rejects_zero_reaction_samples_even_when_stored_summaries_are_nonzero():
    values = _cantilever_result().model_dump(mode="json")
    values.update({
        "reactions": tuple(
            sample.model_copy(update={"vector_n": (0.0, 0.0, 0.0)})
            for sample in _cantilever_result().reactions
        ),
        "result_hash": "pending",
    })
    zero_reactions = StructuralLoadCaseResult.model_validate(values)

    result = _validate_cantilever(result=zero_reactions)

    assert result.status == "fail"
    assert next(check for check in result.checks if check.check_id == "reaction_force").status == "fail"


def test_validator_binds_analysis_result_to_execution_provenance():
    mesh = _cantilever_mesh()
    request = _cantilever_request()
    manifest = _cantilever_manifest(request, mesh)
    analysis = StructuralAnalysisResult(
        source_binding=request.source_binding,
        definition_id=request.source_binding.definition_id,
        definition_hash=request.source_binding.definition_hash,
        request_hash=request.request_hash,
        execution_manifest_hash=execution_manifest_hash(manifest),
        mesh_hash=_mesh_hash(mesh),
        load_case_results=(_cantilever_result(),),
    )

    assert _validate_cantilever(result=analysis, mesh=mesh, request=request, manifest=manifest).status == "pass"

    forged = StructuralAnalysisResult.model_validate({
        **analysis.model_dump(mode="json"),
        "execution_manifest_hash": "sha256:" + "x" * 64,
        "result_hash": "pending",
    })
    assert _validate_cantilever(result=forged, mesh=mesh, request=request, manifest=manifest).status == "fail"


def test_validator_fails_when_free_end_area_denominator_is_not_semantic_area():
    policy = _cantilever_policy().model_copy(update={"free_end_area_mm2": 3.0})

    assert _validate_cantilever(policy=policy).status == "fail"


def test_validator_requires_independent_observed_free_end_area_for_tip():
    request = _cantilever_request()
    observation = CantileverGeometryObservation(
        project_id=request.source_binding.project_id,
        source_revision=request.source_binding.source_revision,
        source_state_hash=request.source_binding.source_state_hash,
        definition_id=request.source_binding.definition_id,
        definition_hash=request.source_binding.definition_hash,
        geometry_artifact_id=request.source_binding.geometry_artifact_id,
        geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
        length_mm=10.0,
        width_mm=2.0,
        height_mm=2.0,
        free_end_area_mm2=4.0,
    ).model_copy(update={"free_end_area_mm2": None})

    result = _validate_cantilever(geometry_observation=observation)

    tip = next(check for check in result.checks if check.check_id == "tip_displacement")
    assert tip.status == "not_evaluable"
    assert "free-end area" in tip.reason


def test_validator_compares_independent_geometry_and_material_observations():
    mesh = _cantilever_mesh()
    request = _cantilever_request()
    manifest = _cantilever_manifest(request, mesh)
    policy = _cantilever_policy(request=request)

    result = StructuralAnalyticalValidator().validate(
        _cantilever_result(), policy, request=request, execution_manifest=manifest, mesh=mesh,
        mesh_artifact_bytes=mesh.mesh_bytes,
        geometry_observation=CantileverGeometryObservation(
            project_id=request.source_binding.project_id,
            source_revision=request.source_binding.source_revision,
            source_state_hash=request.source_binding.source_state_hash,
            definition_id=request.source_binding.definition_id,
            definition_hash=request.source_binding.definition_hash,
            geometry_artifact_id=request.source_binding.geometry_artifact_id,
            geometry_artifact_hash=policy.geometry_artifact_hash, length_mm=11.0, width_mm=2.0, height_mm=2.0,
            free_end_area_mm2=4.0,
        ),
        material_observation=CantileverMaterialObservation(
            project_id=request.source_binding.project_id,
            source_revision=request.source_binding.source_revision,
            source_state_hash=request.source_binding.source_state_hash,
            definition_id=request.source_binding.definition_id,
            definition_hash=request.source_binding.definition_hash,
            geometry_artifact_id=request.source_binding.geometry_artifact_id,
            geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
            material_identity=policy.material_identity, elastic_modulus_mpa=900.0, poisson_ratio=0.3,
        ),
    )

    assert result.status == "fail"


def test_validator_rejects_observation_metadata_not_bound_to_execution():
    request = _cantilever_request()
    manifest = _cantilever_manifest(request, _cantilever_mesh())

    result = StructuralAnalyticalValidator().validate(
        _cantilever_result(), _cantilever_policy(request=request), request=request,
        execution_manifest=manifest, mesh=_cantilever_mesh(), mesh_artifact_bytes=_cantilever_mesh().mesh_bytes,
        geometry_observation=CantileverGeometryObservation(
            project_id=request.source_binding.project_id,
            source_revision=request.source_binding.source_revision,
            source_state_hash=request.source_binding.source_state_hash,
            definition_id=request.source_binding.definition_id,
            definition_hash="sha256:" + "z" * 64,
            geometry_artifact_id=request.source_binding.geometry_artifact_id,
            geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
            length_mm=10.0, width_mm=2.0, height_mm=2.0, free_end_area_mm2=4.0,
        ),
        material_observation=CantileverMaterialObservation(
            project_id=request.source_binding.project_id,
            source_revision=request.source_binding.source_revision,
            source_state_hash=request.source_binding.source_state_hash,
            definition_id=request.source_binding.definition_id,
            definition_hash=request.source_binding.definition_hash,
            geometry_artifact_id=request.source_binding.geometry_artifact_id,
            geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
            material_identity="MAT-1", elastic_modulus_mpa=1000.0, poisson_ratio=0.3,
        ),
    )

    assert result.status == "fail"


def test_validator_requires_independent_observation_provenance():
    request = _cantilever_request()
    manifest = _cantilever_manifest(request, _cantilever_mesh())

    result = StructuralAnalyticalValidator().validate(
        _cantilever_result(), _cantilever_policy(request=request), request=request,
        execution_manifest=manifest, mesh=_cantilever_mesh(), mesh_artifact_bytes=_cantilever_mesh().mesh_bytes,
        geometry_observation=None, material_observation=None,
    )

    assert result.status == "not_evaluable"
    assert {check.status for check in result.checks if check.check_id in {"geometry", "material"}} == {"not_evaluable"}


def test_analytical_result_requires_exactly_all_six_checks():
    values = _validate_cantilever().model_dump(mode="json")
    values["checks"] = values["checks"][:-1]
    values["status"] = "pass"

    with pytest.raises(ValidationError, match="exactly six"):
        StructuralAnalyticalValidationResult.model_validate(values)


def test_analytical_check_rejects_inconsistent_status_and_errors():
    with pytest.raises(ValidationError, match="status and errors"):
        AnalyticalValidationCheck(
            check_id="geometry", expected_value=(1.0,), observed_value=(1.0,),
            absolute_error=None, relative_error=None, tolerance=0.0, status="pass",
        )


def test_analytical_validation_hash_is_deterministic_and_binds_policy():
    validator = StructuralAnalyticalValidator()
    first = _validate_cantilever()
    second = _validate_cantilever()
    changed = _validate_cantilever(policy=_cantilever_policy(0.04, request=_cantilever_request()))

    assert first.validation_hash == second.validation_hash
    assert first.validation_hash != changed.validation_hash
    with pytest.raises(ValidationError):
        first.status = "fail"


def test_analytical_validator_requires_trusted_mesh_and_execution_provenance():
    result = _validate_cantilever()

    assert result.status == "pass"


def test_validator_uses_immutable_mesh_snapshot_against_coordinate_mutation():
    mesh = _cantilever_mesh()
    frozen_mesh = freeze_parsed_mesh(mesh)
    mesh.nodes[1] = (999.0, 999.0, 999.0)

    assert _validate_cantilever(mesh=frozen_mesh).status == "pass"
    with pytest.raises(TypeError):
        frozen_mesh.nodes[1] = (1.0, 1.0, 1.0)


def test_validator_reparses_authoritative_msh_bytes_instead_of_caller_mesh_snapshot():
    mesh = _cantilever_mesh()
    forged = ParsedMesh(
        nodes={**mesh.nodes, 1: (999.0, 999.0, 999.0)},
        c3d10=mesh.c3d10,
        surface_elements=mesh.surface_elements,
        volume_elset_name=mesh.volume_elset_name,
        physical_groups=mesh.physical_groups,
        mesh_bytes=b"foreign-bytes",
    )

    result = _validate_cantilever(
        mesh=forged,
        manifest=_cantilever_manifest(_cantilever_request(), mesh),
        mesh_artifact_bytes=mesh.mesh_bytes,
    )

    assert result.status == "pass"


def test_validator_marks_omitted_displacement_and_reaction_fields_not_evaluable():
    values = _cantilever_result().model_dump(mode="json")
    values.update({
        "displacements": [],
        "reactions": [],
        "result_hash": "pending",
    })

    result = _validate_cantilever(result=StructuralLoadCaseResult.model_validate(values))

    assert result.status == "not_evaluable"
    checks = {check.check_id: check for check in result.checks}
    assert checks["tip_displacement"].status == "not_evaluable"
    assert checks["reaction_force"].status == "not_evaluable"
    assert checks["reaction_moment"].status == "not_evaluable"


def _trusted_interpreter_case(tmp_path, definition_override=None):
    from test_structural_service import _definition

    definition = definition_override or _definition()
    definition_hash = structural_definition_hash(definition)
    state_hash = "sha256:" + "s" * 64
    mesh = b"""$MeshFormat
2.2 0 8
$EndMeshFormat
$PhysicalNames
3
2 1 "fixed"
2 2 "free"
3 3 "volume"
$EndPhysicalNames
$Nodes
10
1 0 0 0
2 10 0 0
3 0 10 0
4 0 0 10
5 5 0 0
6 5 5 0
7 0 5 0
8 0 0 5
9 5 0 5
10 0 5 5
$EndNodes
$Elements
3
1 9 2 1 1 1 3 2 1 3 2
2 9 2 2 2 1 2 3 1 2 3
3 11 2 3 3 1 2 3 4 5 6 7 8 9 10
$EndElements
"""
    source_binding = StructuralSourceBinding(
        project_id="PRJ-1", source_revision=1, source_state_hash=state_hash,
        definition_id=definition.id, definition_hash=definition_hash,
        target_body_id=definition.target_body_id, source_program_hash="sha256:" + "p" * 64,
        geometry_identity="fixture", geometry_artifact_id="GEO-1",
        geometry_artifact_hash="sha256:" + "g" * 64,
    )
    request = StructuralAnalysisRequest(
        source_binding=source_binding,
        selected_load_case_ids=("LC-1",),
        mesh_specification=MeshSpecification(
            global_target_size_mm=5, quality_policy_id="q", mesher_settings_version="1",
        ),
        requested_result_fields=(StructuralResultField.DISPLACEMENT,),
        execution_settings=StructuralExecutionSettings(
            max_elements=1000, max_runtime_seconds=10, max_output_bytes=100000,
            retain_raw_artifacts=True,
        ),
    )
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    step_bytes = b"ISO-10303-21;\nEND-ISO-10303-21;\n"
    step_artifact = store.publish(
        "GEO-1", ArtifactType.STEP, "source.step", step_bytes,
        "mechcad-freecad", "mechcad-freecad@2.1", 1, state_hash,
        backend_provenance=BackendProvenance(
            backend_name="freecad", backend_adapter_version="mechcad-freecad@2.1",
            library_name="FreeCAD", library_version="1.1.3", library_source="bundled",
            library_revision="freecad-1.1.3-bundled",
        ),
    )
    source_binding = source_binding.model_copy(update={
        "geometry_artifact_hash": step_artifact.sha256,
    })
    request = StructuralAnalysisRequest.model_validate({
        **request.model_dump(mode="json"),
        "source_binding": source_binding.model_dump(mode="json"),
        "request_hash": "pending",
    })
    mesh_id = "STRUCT-MSH-" + __import__("hashlib").sha256(
        f"{request.request_hash}||msh".encode("utf-8")
    ).hexdigest()[:16]
    region_map_hash_value = "sha256:" + "r" * 64
    mesh_spec_hash = StructuralResultInterpreter._mesh_specification_hash(request)
    deck_id = StructuralResultInterpreter._expected_artifact_id(request, "inp", "LC-1")
    frd_id = StructuralResultInterpreter._expected_artifact_id(request, "frd", "LC-1")
    log_id = StructuralResultInterpreter._expected_artifact_id(request, "log", "LC-1")
    mesh_artifact = store.publish(
        mesh_id, ArtifactType.MSH, "mesh.msh", mesh, GMSH_PROVIDER_IDENTITY, "4.15.0", 1, state_hash,
        input_hash=mesh_input_hash(
            source_geometry_hash=request.source_binding.geometry_artifact_hash,
            mesh_specification_hash=mesh_spec_hash,
            region_map_hash=region_map_hash_value,
            gmsh_identity=GMSH_PROVIDER_IDENTITY,
            gmsh_version="4.15.0",
        ),
        backend_provenance=BackendProvenance(
            backend_name="gmsh", backend_adapter_version="mechcad-structural-gmsh@1",
            library_name="Gmsh", library_version="4.15.0", library_source="bundled",
            library_revision="gmsh-4.15.0-bundled",
        ),
    )
    deck_bytes = b"*NODE\n"
    if any(isinstance(load, StructuralResultantForce) for case in definition.load_cases for load in case.loads):
        deck_bytes = b"""*NODE
1,0,0,0
2,10,0,0
3,0,10,0
4,0,0,10
5,5,0,0
6,5,5,0
7,0,5,0
8,0,0,5
9,5,0,5
10,0,5,5
*ELEMENT,TYPE=C3D10,ELSET=mat1_vol
3,1,2,3,4,5,6,7,8,9,10
*SURFACE,NAME=free,TYPE=ELEMENT
3,S1
*CLOAD
5,1,3.0
6,1,3.0
7,1,3.0
"""
    deck_artifact = store.publish(
        deck_id, ArtifactType.INP, "case.inp", deck_bytes, DECK_BUILDER_IDENTITY, "1", 1, state_hash,
        input_hash=mesh_artifact.sha256,
    )
    frd_artifact = store.publish(
        frd_id, ArtifactType.FRD, "case.frd", _fixture_bytes("displacement_stress.frd"),
        CALCULIX_PROVIDER_IDENTITY, "2.22", 1, state_hash, input_hash=deck_artifact.sha256,
        backend_provenance=BackendProvenance(
            backend_name="calculix", backend_adapter_version="mechcad-structural-calculix@1",
            library_name="CalculiX", library_version="2.22", library_source="bundled",
            library_revision="calculix-2.22-bundled",
        ),
    )
    dat_id = StructuralResultInterpreter._expected_artifact_id(request, "dat", "LC-1")
    dat_artifact = store.publish(
        dat_id, ArtifactType.DAT, "case.dat", _fixture_bytes("reactions.dat"),
        CALCULIX_PROVIDER_IDENTITY, "2.22", 1, state_hash, input_hash=deck_artifact.sha256,
        backend_provenance=BackendProvenance(
            backend_name="calculix", backend_adapter_version="mechcad-structural-calculix@1",
            library_name="CalculiX", library_version="2.22", library_source="bundled",
            library_revision="calculix-2.22-bundled",
        ),
    )
    log_artifact = store.publish(
        log_id, ArtifactType.LOG, "case.log", b"solver log\n",
        CALCULIX_PROVIDER_IDENTITY, "2.22", 1, state_hash, input_hash=deck_artifact.sha256,
        backend_provenance=BackendProvenance(
            backend_name="calculix", backend_adapter_version="mechcad-structural-calculix@1",
            library_name="CalculiX", library_version="2.22", library_source="bundled",
            library_revision="calculix-2.22-bundled",
        ),
    )
    mesh_manifest = StructuralMeshManifest(
        mesh_specification_hash=mesh_spec_hash,
        gmsh_identity=GMSH_PROVIDER_IDENTITY, gmsh_version="4.15.0", element_family="c3d10",
        node_count=10, volume_element_count=1, boundary_element_count=2, volume_entity_id=3,
        physical_groups=(
            PhysicalGroupBinding(semantic_region_id="fixed", physical_group_name="fixed", gmsh_entity_dim=2, gmsh_entity_id=1),
            PhysicalGroupBinding(semantic_region_id="free", physical_group_name="free", gmsh_entity_dim=2, gmsh_entity_id=2),
            PhysicalGroupBinding(semantic_region_id=None, physical_group_name="volume", gmsh_entity_dim=3, gmsh_entity_id=3),
        ),
        mesh_hash=mesh_artifact.sha256, region_map_hash=region_map_hash_value,
    )
    lowered_loads = tuple(
        LoweredLoadProvenance(
            canonical_load_id=load.load_id,
            semantic_region_id=load.target_region_id,
            resolved_region_map_hash=region_map_hash_value,
            exact_semantic_face_area_mm2=50.0,
            canonical_load_semantic_hash=__import__("mechcad_harness.structural.models", fromlist=["canonical_load_semantic_hash"]).canonical_load_semantic_hash(load),
            source_force_vector_n=(load.magnitude_n, 0.0, 0.0),
            source_application_point_mm=(10.0 / 3.0, 10.0 / 3.0, 0.0),
            normalized_solver_traction_vector_n_per_mm2=(load.magnitude_n / 50.0, 0.0, 0.0),
            lowering_algorithm_id="consistent-nodal-surface-integration@1",
            c3d10_surface_integration_rule_version="consistent-nodal-planar@1",
            produced_nodal_load_semantic_hash=cload_semantic_hash(deck_bytes.decode("ascii")),
            mesh_hash=mesh_artifact.sha256,
            force_conservation_error_n=0.0,
            moment_conservation_error_n_mm=0.0,
        )
        for case_definition in definition.load_cases
        for load in case_definition.loads
        if isinstance(load, StructuralResultantForce)
    )
    case = StructuralCaseExecutionManifest(
        load_case_id="LC-1", mesh_artifact_id=mesh_artifact.artifact_id,
        mesh_artifact_hash=mesh_artifact.sha256, deck_artifact_id=deck_artifact.artifact_id,
        deck_artifact_hash=deck_artifact.sha256, deck_semantic_hash="sha256:" + __import__("hashlib").sha256(deck_bytes).hexdigest(),
        deck_builder_identity=DECK_BUILDER_IDENTITY, deck_builder_version="1",
        frd_artifact_id=frd_artifact.artifact_id,
        frd_artifact_hash=frd_artifact.sha256, execution_status=StructuralExecutionStatus.SUCCEEDED,
        dat_artifact_id=dat_artifact.artifact_id,
        dat_artifact_hash=dat_artifact.sha256,
        log_artifact_id=log_artifact.artifact_id, log_artifact_hash=log_artifact.sha256,
        run_id="RUN-1",
        solver_manifest=StructuralSolverManifest(
            calculix_identity=CALCULIX_PROVIDER_IDENTITY, calculix_version="2.22", exit_code=0,
            backend_provenance=BackendProvenance(
                backend_name="calculix", backend_adapter_version="mechcad-structural-calculix@1",
                library_name="CalculiX", library_version="2.22", library_source="bundled",
                library_revision="calculix-2.22-bundled",
            ),
            job_finished=True, produced_frd=True, produced_dat=True, produced_log=True,
            ),
        lowered_loads=lowered_loads,
    )
    manifest = StructuralExecutionManifest(
        project_id="PRJ-1", revision=1, state_hash=state_hash,
        definition_id=definition.id, definition_hash=definition_hash,
        request_hash=request.request_hash, run_id="RUN-1",
        geometry_artifact_id="GEO-1", geometry_artifact_hash=source_binding.geometry_artifact_hash,
        geometry_provider_provenance=BackendProvenance(
            backend_name="freecad", backend_adapter_version="mechcad-freecad@2.1",
            library_name="FreeCAD", library_version="1.1.3", library_source="bundled",
            library_revision="freecad-1.1.3-bundled",
        ),
        region_map_hash=region_map_hash_value,
        resolver_identity=REGION_RESOLVER_IDENTITY,
        resolver_version=REGION_RESOLVER_VERSION,
        gmsh_identity=GMSH_PROVIDER_IDENTITY, gmsh_version="4.15.0",
        mesh_specification_hash=StructuralResultInterpreter._mesh_specification_hash(request),
        mesh_artifact_id=mesh_artifact.artifact_id, mesh_artifact_hash=mesh_artifact.sha256,
        mesh_manifest=mesh_manifest, mesh_manifest_hash=mesh_manifest_hash(mesh_manifest),
        deck_builder_identity=DECK_BUILDER_IDENTITY, deck_builder_version="1",
        deck_artifact_id=deck_artifact.artifact_id, deck_artifact_hash=deck_artifact.sha256,
        calculix_identity=CALCULIX_PROVIDER_IDENTITY, calculix_version="2.22",
        execution_status=StructuralExecutionStatus.SUCCEEDED,
        solver_manifest=StructuralSolverManifest(
            calculix_identity=CALCULIX_PROVIDER_IDENTITY, calculix_version="2.22", exit_code=0,
            backend_provenance=BackendProvenance(
                backend_name="calculix", backend_adapter_version="mechcad-structural-calculix@1",
                library_name="CalculiX", library_version="2.22", library_source="bundled",
                library_revision="calculix-2.22-bundled",
            ),
            job_finished=True, produced_frd=True, produced_dat=True, produced_log=True,
        ),
        frd_artifact_id=frd_artifact.artifact_id, frd_artifact_hash=frd_artifact.sha256,
        dat_artifact_id=dat_artifact.artifact_id, dat_artifact_hash=dat_artifact.sha256,
        log_artifact_id=log_artifact.artifact_id, log_artifact_hash=log_artifact.sha256,
        artifacts=(
            StructuralArtifactRef(
                artifact_type=artifact.artifact_type.value, artifact_id=artifact.artifact_id,
                sha256=artifact.sha256, producer_identity=artifact.producer_tool_name,
                producer_version=artifact.producer_tool_version,
             ) for artifact in (step_artifact, mesh_artifact, deck_artifact, frd_artifact, dat_artifact, log_artifact)
         ),
         selected_load_case_ids=("LC-1",), case_manifests=(case,), lowered_loads=lowered_loads,
    )
    return tmp_path, request, definition, manifest, frd_artifact


def test_interpreter_rehashes_frd_and_refuses_tampering_before_parser(tmp_path):
    workspace, request, definition, manifest, frd_artifact = _trusted_interpreter_case(tmp_path)
    (workspace / frd_artifact.relative_path).write_bytes(b"tampered")
    parser = Mock()

    with pytest.raises(StructuralResultIntegrityError, match="FRD artifact byte/hash mismatch"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
            frd_parser=parser,
        ).interpret(manifest)

    parser.parse.assert_not_called()


def test_interpreter_rehashes_log_and_rejects_empty_forged_bytes(tmp_path):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    store = ArtifactStore(workspace, project_id="PRJ-1", run_id="RUN-1")
    log_artifact = store.existing(manifest.log_artifact_id)
    (workspace / log_artifact.relative_path).write_bytes(b"")
    empty_hash = "sha256:" + __import__("hashlib").sha256(b"").hexdigest()
    metadata_path = workspace / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / log_artifact.artifact_id / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update({"sha256": empty_hash, "size_bytes": 1})
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    case = manifest.case_manifests[0].model_copy(update={
        "log_artifact_hash": empty_hash, "case_manifest_hash": "pending",
    })
    refs = tuple(
        ref.model_copy(update={"sha256": empty_hash})
        if ref.artifact_id == log_artifact.artifact_id else ref
        for ref in manifest.artifacts
    )
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "log_artifact_hash": empty_hash,
        "case_manifests": [case.model_dump(mode="json")],
        "artifacts": [ref.model_dump(mode="json") for ref in refs],
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match="LOG artifact is empty"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(tampered)


def test_interpreter_rejects_artifact_provenance_and_foreign_gmsh_mismatch(tmp_path):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    store = ArtifactStore(workspace, project_id="PRJ-1", run_id="RUN-1")
    mesh_artifact = store.existing(manifest.mesh_artifact_id)
    metadata_path = workspace / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / mesh_artifact.artifact_id / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["producer_tool_version"] = "foreign-version"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(StructuralResultIntegrityError, match="MSH artifact producer version mismatch"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(manifest)

    foreign_workspace = tmp_path / "foreign-gmsh"
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(foreign_workspace)
    store = ArtifactStore(workspace, project_id="PRJ-1", run_id="RUN-1")
    mesh_artifact = store.existing(manifest.mesh_artifact_id)
    foreign_identity = "foreign-gmsh@9"
    foreign_version = "9.99.0"
    foreign_input_hash = mesh_input_hash(
        source_geometry_hash=request.source_binding.geometry_artifact_hash,
        mesh_specification_hash=manifest.mesh_specification_hash,
        region_map_hash=manifest.region_map_hash,
        gmsh_identity=foreign_identity,
        gmsh_version=foreign_version,
    )
    metadata_path = workspace / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / mesh_artifact.artifact_id / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update({
        "producer_tool_name": foreign_identity,
        "producer_tool_version": foreign_version,
        "input_hash": foreign_input_hash,
    })
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    mesh_manifest = manifest.mesh_manifest.model_copy(update={
        "gmsh_identity": foreign_identity, "gmsh_version": foreign_version,
    })
    refs = tuple(
        ref.model_copy(update={
            "producer_identity": foreign_identity, "producer_version": foreign_version,
        }) if ref.artifact_id == mesh_artifact.artifact_id else ref
        for ref in manifest.artifacts
    )
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "gmsh_identity": foreign_identity,
        "gmsh_version": foreign_version,
        "mesh_manifest": mesh_manifest.model_dump(mode="json"),
        "mesh_manifest_hash": mesh_manifest_hash(mesh_manifest),
        "artifacts": [ref.model_dump(mode="json") for ref in refs],
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match="trusted Gmsh"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(tampered)


@pytest.mark.parametrize(
    ("field", "value"),
    [("resolver_identity", "foreign-region-resolver@9"), ("resolver_version", "9")],
)
def test_interpreter_rejects_tampered_region_resolver_binding(tmp_path, field, value):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        field: value,
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match="region resolver"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(tampered)


def test_interpreter_rejects_artifact_producer_identity_mismatch(tmp_path):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    store = ArtifactStore(workspace, project_id="PRJ-1", run_id="RUN-1")
    mesh_artifact = store.existing(manifest.mesh_artifact_id)
    metadata_path = workspace / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / mesh_artifact.artifact_id / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["producer_tool_name"] = "foreign-producer"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(StructuralResultIntegrityError, match="MSH artifact producer mismatch"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(manifest)

    foreign_workspace = tmp_path / "foreign-geometry"
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(foreign_workspace)
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "geometry_provider_provenance": {
            "backend_name": "foreign-cad",
            "backend_adapter_version": "foreign-cad@9",
            "library_name": "ForeignCAD",
            "library_version": "9.9.9",
            "library_source": "foreign",
        },
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match="geometry provider provenance"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(tampered)


def test_interpreter_rejects_foreign_same_name_version_calculix_provenance(tmp_path):
    workspace, request, definition, manifest, frd_artifact = _trusted_interpreter_case(tmp_path)
    metadata_path = workspace / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / frd_artifact.artifact_id / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["backend_provenance"] = {
        "backend_name": "calculix",
        "backend_adapter_version": "mechcad-structural-calculix@1",
        "library_name": "CalculiX",
        "library_version": "2.22",
        "library_source": "foreign-bundled",
        "library_revision": "foreign-calculix-2.22",
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(StructuralResultIntegrityError, match="FRD artifact backend provenance mismatch"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(manifest)


def test_interpreter_rejects_foreign_same_name_version_mesh_backend(tmp_path):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    store = ArtifactStore(workspace, project_id="PRJ-1", run_id="RUN-1")
    mesh_artifact = store.existing(manifest.mesh_artifact_id)
    metadata_path = workspace / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / mesh_artifact.artifact_id / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["backend_provenance"].update({
        "library_source": "foreign-bundled",
        "library_revision": "foreign-revision",
    })
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(StructuralResultIntegrityError, match="MSH artifact backend provenance mismatch"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(manifest)


def test_interpreter_rejects_foreign_same_name_version_freecad_provider(tmp_path):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    store = ArtifactStore(workspace, project_id="PRJ-1", run_id="RUN-1")
    source_artifact = store.existing(request.source_binding.geometry_artifact_id)
    metadata_path = workspace / source_artifact.relative_path.replace(
        "/source.step", "/metadata.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["backend_provenance"].update({
        "library_source": "foreign-bundled",
        "library_revision": "foreign-revision",
    })
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "geometry_provider_provenance": {
            **manifest.geometry_provider_provenance.model_dump(mode="json"),
            "library_source": "foreign-bundled",
            "library_revision": "foreign-revision",
        },
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match="geometry provider provenance"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(tampered)


@pytest.mark.parametrize(
    "solver_update",
    [
        {"exit_code": 1},
        {"job_finished": False},
        {"produced_frd": False},
        {"produced_dat": False},
        {"produced_log": False},
    ],
)
def test_interpreter_requires_complete_successful_case_solver_manifest(tmp_path, solver_update):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    solver = manifest.case_manifests[0].solver_manifest.model_copy(update=solver_update)
    case = manifest.case_manifests[0].model_copy(update={"solver_manifest": solver, "case_manifest_hash": "pending"})
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "solver_manifest": solver.model_dump(mode="json"),
        "case_manifests": [case.model_dump(mode="json")],
        "request_manifest_hash": None,
    })

    parser = Mock()
    with pytest.raises(StructuralResultIntegrityError, match="successful case solver manifest"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
            frd_parser=parser,
        ).interpret(tampered)
    parser.parse.assert_not_called()


def test_interpreter_requires_actual_success_case_output_references(tmp_path):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    case = manifest.case_manifests[0].model_copy(update={
        "frd_artifact_id": None,
        "frd_artifact_hash": None,
        "dat_artifact_id": None,
        "dat_artifact_hash": None,
        "log_artifact_id": None,
        "log_artifact_hash": None,
        "case_manifest_hash": "pending",
    })
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "frd_artifact_id": None,
        "frd_artifact_hash": None,
        "dat_artifact_id": None,
        "dat_artifact_hash": None,
        "log_artifact_id": None,
        "log_artifact_hash": None,
        "case_manifests": [case.model_dump(mode="json")],
        "request_manifest_hash": None,
    })

    parser = Mock()
    with pytest.raises(StructuralResultIntegrityError, match="successful case output references"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
            frd_parser=parser,
        ).interpret(tampered)
    parser.parse.assert_not_called()


def test_interpreter_rejects_nested_mesh_specification_hash_mismatch(tmp_path):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    mesh_manifest = manifest.mesh_manifest.model_copy(update={
        "mesh_specification_hash": "sha256:" + "x" * 64,
    })
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "mesh_manifest": mesh_manifest.model_dump(mode="json"),
        "mesh_manifest_hash": mesh_manifest_hash(mesh_manifest),
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match="mesh specification hash"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(tampered)


def _resultant_force_definition():
    from test_structural_service import _definition

    definition = _definition()
    force = StructuralResultantForce(
        load_id="RF-1", target_region_id="free", magnitude_n=9.0,
        direction_xyz=(1.0, 0.0, 0.0), frame="component_local",
        distribution="uniform_surface_traction_equivalent",
    )
    first_case = definition.load_cases[0].model_copy(update={"loads": (force,)})
    return definition.model_copy(update={"load_cases": (first_case,)})


@pytest.mark.parametrize("lowered_load_update", [(), "duplicate"])
def test_interpreter_requires_exactly_one_lowering_for_each_resultant_force(tmp_path, lowered_load_update):
    definition = _resultant_force_definition()
    workspace, request, trusted_definition, manifest, _frd_artifact = _trusted_interpreter_case(
        tmp_path, definition_override=definition,
    )
    lowered = manifest.case_manifests[0].lowered_loads[0]
    lowered_loads = () if lowered_load_update == () else (lowered, lowered)
    case = manifest.case_manifests[0].model_copy(update={
        "lowered_loads": lowered_loads,
        "case_manifest_hash": "pending",
    })
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "case_manifests": [case.model_dump(mode="json")],
        "lowered_loads": list(lowered_loads),
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match="exactly one lowered-load provenance"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=trusted_definition,
        ).interpret(tampered)


def test_interpreter_rejects_forged_lowered_force_semantics(tmp_path):
    definition = _resultant_force_definition()
    workspace, request, trusted_definition, manifest, _frd_artifact = _trusted_interpreter_case(
        tmp_path, definition_override=definition,
    )
    lowered = manifest.case_manifests[0].lowered_loads[0].model_copy(update={
        "source_force_vector_n": (999.0, 0.0, 0.0),
    })
    case = manifest.case_manifests[0].model_copy(update={
        "lowered_loads": (lowered,), "case_manifest_hash": "pending",
    })
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "case_manifests": [case.model_dump(mode="json")],
        "lowered_loads": [lowered.model_dump(mode="json")],
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match="canonical load"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=trusted_definition,
        ).interpret(tampered)


def test_lowered_reconstruction_rejects_deck_surface_face_not_in_canonical_region(tmp_path):
    definition = _resultant_force_definition()
    workspace, request, trusted_definition, manifest, _frd_artifact = _trusted_interpreter_case(
        tmp_path, definition_override=definition,
    )
    store = ArtifactStore(workspace, project_id="PRJ-1", run_id="RUN-1")
    mesh_artifact = store.existing(manifest.mesh_artifact_id)
    deck_artifact = store.existing(manifest.case_manifests[0].deck_artifact_id)
    mesh = _parse_verified_mesh((workspace / mesh_artifact.relative_path).read_bytes())
    deck_text = (workspace / deck_artifact.relative_path).read_text(encoding="ascii")
    tampered_deck = deck_text.replace("3,S1\n", "3,S2\n", 1)
    load = trusted_definition.load_cases[0].loads[0]

    with pytest.raises(StructuralResultIntegrityError, match="trusted semantic region faces"):
        StructuralResultInterpreter._reconstruct_resultant_lowering(
            mesh, load, deck_text=tampered_deck,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_application_point_mm", (999.0, 0.0, 0.0), "application point"),
        ("exact_semantic_face_area_mm2", 999.0, "face area"),
        ("force_conservation_error_n", 1.0, "force conservation"),
        ("moment_conservation_error_n_mm", 1.0, "moment conservation"),
    ],
)
def test_interpreter_rejects_forged_lowered_geometry_and_conservation_provenance(
    tmp_path, field, value, message,
):
    definition = _resultant_force_definition()
    workspace, request, trusted_definition, manifest, _frd_artifact = _trusted_interpreter_case(
        tmp_path, definition_override=definition,
    )
    lowered = manifest.case_manifests[0].lowered_loads[0].model_copy(update={field: value})
    case = manifest.case_manifests[0].model_copy(update={
        "lowered_loads": (lowered,), "case_manifest_hash": "pending",
    })
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "case_manifests": [case.model_dump(mode="json")],
        "lowered_loads": [lowered.model_dump(mode="json")],
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match=message):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=trusted_definition,
        ).interpret(tampered)


def test_interpreter_rejects_forged_calculix_manifest_version(tmp_path):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "calculix_version": "9.99",
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match="trusted CalculiX version"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(tampered)


def test_interpreter_rehashes_source_step_before_parsing_results(tmp_path):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    step = ArtifactStore(workspace, project_id="PRJ-1", run_id="RUN-1").existing_in_project("GEO-1")
    assert step is not None
    (workspace / step.relative_path).write_bytes(b"tampered STEP")

    with pytest.raises(StructuralResultIntegrityError, match="source STEP artifact"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(manifest)


def test_mesh_region_validation_rejects_missing_physical_group(parser_mesh):
    definition = __import__("test_structural_service", fromlist=["_definition"])._definition()
    broken_mesh = ParsedMesh(
        nodes=parser_mesh.nodes,
        c3d10=parser_mesh.c3d10,
        surface_elements={"fixed": parser_mesh.surface_elements["fixed"]},
        volume_elset_name=parser_mesh.volume_elset_name,
        physical_groups=parser_mesh.physical_groups,
        mesh_bytes=parser_mesh.mesh_bytes,
    )

    with pytest.raises(StructuralResultIntegrityError, match="missing structural region free"):
        StructuralResultInterpreter._verify_mesh_regions(broken_mesh, definition)


def test_support_centroid_is_area_weighted_over_surface_elements():
    mesh = ParsedMesh(
        nodes={
            1: (0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0), 3: (0.0, 1.0, 0.0),
            4: (0.0, 0.0, 0.0), 5: (2.0, 0.0, 0.0), 6: (0.0, 1.0, 0.0),
        },
        c3d10={1: (1, 2, 3, 4, 5, 6, 1, 2, 3, 4)},
        surface_elements={"fixed": [(1, (1, 2, 3)), (2, (4, 5, 6))]},
        volume_elset_name="volume", physical_groups=(), mesh_bytes=b"centroid",
    )

    assert StructuralResultInterpreter._surface_centroid(mesh, ("fixed",)) == pytest.approx(
        (5.0 / 9.0, 1.0 / 3.0, 0.0),
    )


def test_interpreter_rejects_solver_manifest_without_trusted_version(tmp_path):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "solver_manifest": None,
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match="solver_provenance"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(tampered)


def test_interpreter_rejects_case_deck_semantic_hash_mismatch(tmp_path):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    case = StructuralCaseExecutionManifest.model_validate({
        **manifest.case_manifests[0].model_dump(mode="json"),
        "deck_semantic_hash": "sha256:" + "x" * 64,
        "case_manifest_hash": "pending",
    })
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "case_manifests": [case.model_dump(mode="json")],
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match="deck semantic/byte hash mismatch"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(tampered)


def test_interpreter_rejects_mesh_manifest_count_tampering(tmp_path):
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(tmp_path)
    mesh_manifest = manifest.mesh_manifest.model_copy(update={"node_count": 9})
    tampered = StructuralExecutionManifest.model_validate({
        **manifest.model_dump(mode="json"),
        "mesh_manifest": mesh_manifest.model_dump(mode="json"),
        "mesh_manifest_hash": mesh_manifest_hash(mesh_manifest),
        "request_manifest_hash": None,
    })

    with pytest.raises(StructuralResultIntegrityError, match="node count"):
        StructuralResultInterpreter(
            workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
        ).interpret(tampered)


def test_equilibrium_uses_manifest_lowered_load_not_definition_values(parser_mesh):
    from mechcad_harness.structural.results import StructuralResultInterpreter

    parser_mesh.nodes.update({1: (0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0), 3: (0.0, 1.0, 0.0)})
    lowered = LoweredLoadProvenance(
        canonical_load_id="MANIFEST-FORCE", canonical_load_semantic_hash="test", semantic_region_id="fixed",
        resolved_region_map_hash="sha256:" + "r" * 64, exact_semantic_face_area_mm2=1.0,
        source_force_vector_n=(9.0, 0.0, 0.0), source_application_point_mm=(1.0, 0.0, 0.0),
        normalized_solver_traction_vector_n_per_mm2=(9.0, 0.0, 0.0),
        lowering_algorithm_id="test", c3d10_surface_integration_rule_version="test",
        produced_nodal_load_semantic_hash="sha256:" + "n" * 64, mesh_hash=_mesh_hash(parser_mesh),
        force_conservation_error_n=0.0, moment_conservation_error_n_mm=0.0,
    )
    reaction = StructuralReactionSample(
        mesh_hash=_mesh_hash(parser_mesh), node_id=1, support_set_name="FIXED_NODES",
        vector_n=(-9.0, 0.0, 0.0), units=StructuralResultUnits(),
    )
    definition = __import__("test_structural_service", fromlist=["_definition"])._definition()
    summary = StructuralResultInterpreter(
        workspace=".", project_id="PRJ-1",
    )._reaction_summary(parser_mesh, definition, "LC-1", (reaction,), (lowered,), _mesh_hash(parser_mesh))

    assert summary["applied_force_n"] == (9.0, 0.0, 0.0)
    assert summary["equilibrium_status"] == "applicable"


def test_yield_criterion_allowable_and_safety_factor_are_dimensionless():
    definition = __import__("test_structural_service", fromlist=["_definition"])._definition()
    values = definition.model_dump(mode="json")
    values["material_assignment"]["property_snapshot"].append({
        "property_name": "yield_strength", "value": 100.0, "normalized_unit": "MPa",
        "source_identity": "test", "authority": "typical_reference",
        "conversion_provenance": {"source_unit": "MPa", "normalization_rule": "as_is", "conversion_version": "1"},
    })
    values["material_authority_policy"]["allowed_authorities_by_property"].append({
        "property_name": "yield_strength", "allowed_authorities": ["typical_reference"],
    })
    values["acceptance_criteria"] = [{
        "kind": "yield_safety_factor", "criterion_id": "C-YIELD", "load_case_id": "LC-1",
        "assessment_region_id": "free", "stress_sampling": "element_nodal_extrapolated",
        "minimum_yield_safety_factor": 2.0, "zero_stress_tolerance_mpa": 0.001,
    }]
    definition = __import__("mechcad_harness.models.structural", fromlist=["StructuralAnalysisDefinition"])
    definition = definition.StructuralAnalysisDefinition.model_validate(values)
    case = StructuralLoadCaseResult.model_validate({
        **_case_result(run_id="RUN-A", frd_hash=FRD_HASH, stress_samples=(_stress(),)).model_dump(mode="json"),
        "requested_result_fields": [StructuralResultField.VON_MISES_STRESS],
        "region_node_ids": [["free", [1]]],
        "result_hash": "pending",
    })

    criterion_result = StructuralVerificationService()._evaluate_criterion(
        definition.acceptance_criteria[0], case, definition,
    )

    assert criterion_result.units == "dimensionless"
    assert criterion_result.allowable_value == 2.0


def test_yield_criterion_without_consumed_yield_property_is_not_evaluable():
    definition_values = __import__("test_structural_service", fromlist=["_definition"])._definition().model_dump(mode="json")
    definition_values["acceptance_criteria"] = [{
        "kind": "yield_safety_factor", "criterion_id": "C-YIELD-MISSING", "load_case_id": "LC-1",
        "assessment_region_id": "free", "stress_sampling": "element_nodal_extrapolated",
        "consumed_material_properties": ["elastic_modulus", "poisson_ratio"],
        "minimum_yield_safety_factor": 1.5, "zero_stress_tolerance_mpa": 0.001,
    }]
    definition = __import__("mechcad_harness.models.structural", fromlist=["StructuralAnalysisDefinition"]).StructuralAnalysisDefinition.model_validate(definition_values)
    case = StructuralLoadCaseResult.model_validate({
        **_case_result(run_id="RUN-A", frd_hash=FRD_HASH, stress_samples=(_stress(),)).model_dump(mode="json"),
        "requested_result_fields": [StructuralResultField.VON_MISES_STRESS],
        "region_node_ids": [["free", [1]]], "result_hash": "pending",
    })

    result = StructuralVerificationService()._evaluate_criterion(
        definition.acceptance_criteria[0], case, definition,
    )

    assert result.status is StructuralCriterionStatus.NOT_EVALUABLE
    assert result.reason == "missing_material_property"


def test_criterion_evaluation_rejects_disallowed_material_authority():
    definition = __import__("test_structural_service", fromlist=["_definition"])._definition()
    policy = definition.material_authority_policy.model_copy(update={
        "allowed_authorities_by_property": tuple(
            rule.model_copy(update={"allowed_authorities": ("supplier_datasheet",)})
            for rule in definition.material_authority_policy.allowed_authorities_by_property
        ),
    })
    definition = definition.model_copy(update={"material_authority_policy": policy})
    criterion = MaximumDisplacementCriterion(
        criterion_id="C-AUTH", load_case_id="LC-1", assessment_region_id="fixed",
        maximum_allowed_displacement_mm=1.0,
    )
    case = StructuralLoadCaseResult.model_validate({
        **_case_result(run_id="RUN-A", frd_hash=FRD_HASH).model_dump(mode="json"),
        "requested_result_fields": [StructuralResultField.DISPLACEMENT],
        "region_node_ids": [["fixed", [1]]],
        "result_hash": "pending",
    })

    result = StructuralVerificationService()._evaluate_criterion(criterion, case, definition)

    assert result.status is StructuralCriterionStatus.NOT_EVALUABLE
    assert result.reason == "disallowed_material_authority"


def test_criterion_aggregate_order_is_fail_then_not_evaluable_then_pass():
    fail = StructuralCriterionResult(
        criterion_id="fail", status=StructuralCriterionStatus.FAIL, reason="failed",
    )
    not_evaluable = StructuralCriterionResult(
        criterion_id="not-evaluable", status=StructuralCriterionStatus.NOT_EVALUABLE,
        reason="unsupported_result_representation",
    )
    passed = StructuralCriterionResult(criterion_id="pass", status=StructuralCriterionStatus.PASS)

    verification = _verification(
        overall_status=StructuralCriterionStatus.FAIL,
        criterion_results=(passed, not_evaluable, fail),
    )

    assert verification.overall_status is StructuralCriterionStatus.FAIL


def test_yield_criterion_rejects_unsupported_stress_domain_before_comparison():
    definition_values = __import__("test_structural_service", fromlist=["_definition"])._definition().model_dump(mode="json")
    definition_values["material_assignment"]["property_snapshot"].append({
        "property_name": "yield_strength", "value": 100.0, "normalized_unit": "MPa",
        "source_identity": "test", "authority": "typical_reference",
        "conversion_provenance": {"source_unit": "MPa", "normalization_rule": "as_is", "conversion_version": "1"},
    })
    definition_values["material_authority_policy"]["allowed_authorities_by_property"].append({
        "property_name": "yield_strength", "allowed_authorities": ["typical_reference"],
    })
    definition_values["acceptance_criteria"] = [{
        "kind": "yield_safety_factor", "criterion_id": "C-REP", "load_case_id": "LC-1",
        "assessment_region_id": "free", "minimum_yield_safety_factor": 2.0,
        "zero_stress_tolerance_mpa": 0.001,
    }]
    definition = __import__("mechcad_harness.models.structural", fromlist=["StructuralAnalysisDefinition"]).StructuralAnalysisDefinition.model_validate(definition_values)
    case = StructuralLoadCaseResult.model_validate({
        **_case_result(run_id="RUN-A", frd_hash=FRD_HASH, stress_samples=(_stress(),)).model_dump(mode="json"),
        "requested_result_fields": [StructuralResultField.VON_MISES_STRESS],
        "region_node_ids": [["free", [1]]],
        "result_hash": "pending",
    })

    result = StructuralVerificationService()._evaluate_criterion(
        definition.acceptance_criteria[0], case, definition,
    )

    assert result.status is StructuralCriterionStatus.NOT_EVALUABLE
    assert result.reason == "unsupported_result_representation"


def test_displacement_criterion_uses_only_assessment_region_nodes(tmp_path):
    criterion = MaximumDisplacementCriterion(
        criterion_id="C-DISP", load_case_id="LC-1", assessment_region_id="free",
        maximum_allowed_displacement_mm=1.0,
    )
    base_definition = __import__("test_structural_service", fromlist=["_definition"])._definition()
    definition = base_definition.model_copy(update={"acceptance_criteria": (criterion,)})
    workspace, request, definition, manifest, _frd_artifact = _trusted_interpreter_case(
        tmp_path, definition_override=definition
    )
    result = StructuralResultInterpreter(
        workspace=workspace, project_id="PRJ-1", request=request, definition=definition,
    ).interpret(manifest)

    verification = StructuralVerificationService().evaluate(result, definition)

    assert verification.criterion_results[0].status is StructuralCriterionStatus.PASS
    assert verification.criterion_results[0].consumed_result_field == (
        "nodal_displacement_magnitude_on_region"
    )
