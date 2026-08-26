from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from mechcad_harness.artifacts.models import ArtifactType
from mechcad_harness.artifacts.storage import ArtifactStore, ArtifactVerificationError
from mechcad_harness.models.structural import (
    StructuralAnalysisDefinition,
    StructuralBodyAcceleration,
    StructuralCriterion,
    StructuralMaterialPropertyName,
    StructuralResultField,
    StructuralResultantForce,
    StructuralSurfacePressure,
    evaluate_material_authority_policy,
    structural_definition_hash,
)
from mechcad_harness.structural.models import (
    CALCULIX_PROVIDER_IDENTITY,
    DECK_BUILDER_IDENTITY,
    GMSH_PROVIDER_IDENTITY,
    REGION_RESOLVER_IDENTITY,
    REGION_RESOLVER_VERSION,
    StructuralAnalysisResult,
    StructuralCaseExecutionManifest,
    StructuralCriterionResult,
    StructuralCriterionStatus,
    StructuralExecutionManifest,
    StructuralExecutionStatus,
    StructuralLoadCaseResult,
    StructuralRequestExecutionManifest,
    StructuralResultParserProvenance,
    canonical_load_semantic_hash,
    execution_manifest_hash,
    mesh_input_hash,
    lowered_load_semantic_hash,
    mesh_manifest_hash,
    structural_request_manifest_hash,
)
from mechcad_harness.structural.mesh import C3D10_LOCAL_FACES, ParsedMesh, canonical_c3d10_nodes
from mechcad_harness.structural.deck import (
    DeckBuildError,
    cload_semantic_hash,
    map_surface_to_volume_faces,
    parse_cload_semantics,
)
from mechcad_harness.structural.runtime import CALCULIX_IDENTITY, FREECAD_IDENTITY, GMSH_IDENTITY
from mechcad_harness.backends.provenance import provenance_from_identity
from mechcad_harness.structural.tolerances import RESULTANT_FORCE_CONSERVATION_TOLERANCE_N
from mechcad_harness.structural.models import (
    StressFieldRepresentation,
    StructuralDisplacementSample,
    StructuralReactionSample,
    StructuralResultUnits,
    StructuralStressSample,
    StructuralStressSampleIdentity,
    StructuralStressTensor,
)


class StructuralResultIntegrityError(ValueError):
    """Raised when solver result bytes leave the admitted CalculiX subset."""


def von_mises_mpa(tensor: StructuralStressTensor) -> float:
    """Derive von Mises stress without changing the parsed tensor domain."""
    value = math.sqrt(
        0.5 * (
            (tensor.sxx - tensor.syy) ** 2
            + (tensor.syy - tensor.szz) ** 2
            + (tensor.szz - tensor.sxx) ** 2
        )
        + 3.0 * (tensor.sxy**2 + tensor.syz**2 + tensor.szx**2)
    )
    if not math.isfinite(value):
        raise StructuralResultIntegrityError("von Mises result is nonfinite")
    return value


@dataclass(frozen=True)
class ParsedCalculiXFrd:
    mesh_hash: str
    displacements: tuple[StructuralDisplacementSample, ...]
    stress_samples: tuple[StructuralStressSample, ...]


NodeReaction = StructuralReactionSample


@dataclass(frozen=True)
class _FrdDataset:
    name: str
    values: tuple[tuple[int, tuple[float, ...]], ...]


_FRD_COMPONENTS = {
    "DISP": ("D1", "D2", "D3"),
    "STRESS": ("SXX", "SYY", "SZZ", "SXY", "SYZ", "SZX"),
}
_FRD_NUMBER = re.compile(r"[ +-]\d\.\d{5}E[+-]\d{2}")
_DAT_NUMBER = re.compile(r"(?:  | [+-])\d\.\d{6}E[+-]\d{2}")
_FRD_MINIMAL_1U_RECORDS = (
    "    1UMechCAD structural linear-static deck",
    "    1UPGM               CalculiX",
    f"    1UVERSION           Version {CALCULIX_IDENTITY.library_version}",
)
_FRD_FULL_1U_RECORD_KINDS = (
    "header", "user", "date", "time", "host", "program", "version",
    "compile_time", "directory", "database", "material",
)


def _frd_1u_record_kind(record: str) -> str | None:
    if record == _FRD_MINIMAL_1U_RECORDS[0]:
        return "header"
    if record == "    1UUSER":
        return "user"
    if re.fullmatch(r"    1UDATE              \d{1,2}\.[a-z]+\.\d{4}", record):
        return "date"
    if re.fullmatch(r"    1UTIME              \d{2}:\d{2}:\d{2}", record):
        return "time"
    if record == "    1UHOST":
        return "host"
    if record == _FRD_MINIMAL_1U_RECORDS[1]:
        return "program"
    if record == _FRD_MINIMAL_1U_RECORDS[2]:
        return "version"
    if re.fullmatch(r"    1UCOMPILETIME       .+", record):
        return "compile_time"
    if record == "    1UDIR":
        return "directory"
    if record == "    1UDBN":
        return "database"
    if record == "    1UMAT    1MAT1":
        return "material"
    return None


def _integrity(message: str) -> StructuralResultIntegrityError:
    return StructuralResultIntegrityError(message)


def _decode_lines(raw_lines: list[bytes]) -> list[str]:
    try:
        return [line.decode("ascii", errors="strict") for line in raw_lines]
    except UnicodeDecodeError as exc:
        raise _integrity("result bytes must be strict ASCII") from exc


def _frd_lines(content: bytes) -> list[str]:
    if not content:
        raise _integrity("result bytes must not be empty")
    if not content.endswith(b"\n") or b"\r" in content:
        raise _integrity("FRD result bytes must use uniform LF record terminators")
    return _decode_lines(content[:-1].split(b"\n"))


def _dat_lines(content: bytes) -> list[str]:
    if not content:
        raise _integrity("result bytes must not be empty")
    if not content.endswith(b"\r\n"):
        raise _integrity("DAT result bytes must use uniform CRLF record terminators")
    body = content[:-2]
    if b"\r" in body.replace(b"\r\n", b"") or b"\n" in body.replace(b"\r\n", b""):
        raise _integrity("DAT result bytes must use uniform CRLF record terminators")
    return _decode_lines(body.split(b"\r\n"))


def _mesh_hash(mesh: ParsedMesh) -> str:
    return "sha256:" + hashlib.sha256(mesh.mesh_bytes).hexdigest()


def _parse_frd_number(field: str, *, line_number: int) -> float:
    if not _FRD_NUMBER.fullmatch(field):
        raise _integrity(f"invalid FRD numeric field at line {line_number}")
    value = float(field)
    if not math.isfinite(value):
        raise _integrity(f"nonfinite FRD numeric field at line {line_number}")
    return value


def _parse_dat_number(field: str, *, line_number: int) -> float:
    if not _DAT_NUMBER.fullmatch(field):
        raise _integrity(f"invalid DAT numeric field at line {line_number}")
    value = float(field)
    if not math.isfinite(value):
        raise _integrity(f"nonfinite DAT numeric field at line {line_number}")
    return value


def _parse_node(field: str, *, line_number: int) -> int:
    if len(field) != 10 or not re.fullmatch(r" {0,9}\d{1,10}", field):
        raise _integrity(f"invalid node identity at line {line_number}")
    node_id = int(field)
    if node_id <= 0:
        raise _integrity(f"node identity must be positive at line {line_number}")
    return node_id


def _parse_frd_envelope_count(record: str, marker: str, *, line_number: int) -> int:
    count_field = record[6:-38] if len(record) >= 72 else ""
    envelope_kind = "element" if marker.strip() == "3C" else "mesh"
    if (
        not record.startswith(marker)
        or record[-38:-1] != " " * 37
        or not record.endswith("1")
        or not count_field.strip().isdigit()
        or count_field != count_field.strip().rjust(len(count_field))
    ):
        raise _integrity(f"malformed FRD {envelope_kind} envelope at line {line_number}")
    count = int(count_field)
    if count <= 0:
        raise _integrity("FRD envelope count must be positive")
    return count


def _parse_frd_datasets(lines: list[str], *, mesh: ParsedMesh | None = None) -> tuple[_FrdDataset, ...]:
    if len(lines) < 6 or lines[0] != "    1C" or lines[-1] != " 9999":
        raise _integrity("FRD requires the exact CalculiX envelope and final 9999 trailer")

    cursor = 1
    envelope_records = []
    while cursor < len(lines) and lines[cursor].startswith("    1U"):
        if "\t" in lines[cursor]:
            raise _integrity(f"malformed FRD envelope record at line {cursor + 1}")
        envelope_records.append(lines[cursor])
        cursor += 1
    normalized_envelope = tuple(record.rstrip(" ") for record in envelope_records)
    if normalized_envelope != _FRD_MINIMAL_1U_RECORDS and tuple(
        _frd_1u_record_kind(record) for record in normalized_envelope
    ) != _FRD_FULL_1U_RECORD_KINDS:
        if any(
            record.startswith("    1UVERSION") and record != _FRD_MINIMAL_1U_RECORDS[2]
            for record in normalized_envelope
        ):
            raise _integrity("FRD requires the admitted CalculiX version 2.22 record")
        raise _integrity("FRD contains an unrecognized, duplicate, or unordered 1U envelope record")
    if cursor >= len(lines) - 1:
        raise _integrity("truncated FRD mesh envelope")

    mesh_header = lines[cursor]
    mesh_node_count = _parse_frd_envelope_count(mesh_header, "    2C", line_number=cursor + 1)
    cursor += 1

    mesh_nodes: set[int] = set()
    while cursor < len(lines) and lines[cursor] != " -3":
        record = lines[cursor]
        if len(record) != 49 or not record.startswith(" -1"):
            raise _integrity(f"malformed FRD mesh node record at line {cursor + 1}")
        node_id = _parse_node(record[3:13], line_number=cursor + 1)
        if node_id in mesh_nodes:
            raise _integrity(f"duplicate FRD mesh node {node_id}")
        for offset in range(3):
            _parse_frd_number(record[13 + 12 * offset : 25 + 12 * offset], line_number=cursor + 1)
        mesh_nodes.add(node_id)
        cursor += 1
    if cursor == len(lines) - 1 or len(mesh_nodes) != mesh_node_count:
        raise _integrity("truncated or incomplete FRD mesh envelope")
    cursor += 1

    if cursor < len(lines) - 1 and lines[cursor].startswith("    3C"):
        element_header = lines[cursor]
        element_count = _parse_frd_envelope_count(element_header, "    3C", line_number=cursor + 1)
        cursor += 1
        seen_elements: set[int] = set()
        for _ in range(element_count):
            if cursor + 1 >= len(lines) - 1:
                raise _integrity("truncated FRD element envelope")
            element_record = lines[cursor]
            connectivity_record = lines[cursor + 1]
            if (
                len(element_record) != 28
                or element_record[:3] != " -1"
                or not element_record[3:13].strip().isdigit()
                or element_record[3:13] != element_record[3:13].strip().rjust(10)
                or element_record[13:17] != " " * 4
                or not element_record[17].isdigit()
                or element_record[18:22] != " " * 4
                or not element_record[22].isdigit()
                or element_record[23:27] != " " * 4
                or not element_record[27].isdigit()
            ):
                raise _integrity(f"malformed FRD element record at line {cursor + 1}")
            element_id = int(element_record[3:13])
            if element_id in seen_elements:
                raise _integrity(f"duplicate FRD element {element_id}")
            seen_elements.add(element_id)
            if (
                len(connectivity_record) != 103
                or connectivity_record[:3] != " -2"
                or any(
                    not field.strip().isdigit() or field != field.strip().rjust(10)
                    for field in (connectivity_record[3 + 10 * index : 13 + 10 * index] for index in range(10))
                )
            ):
                raise _integrity(f"malformed FRD element connectivity at line {cursor + 2}")
            connectivity = tuple(
                int(connectivity_record[3 + 10 * index : 13 + 10 * index])
                for index in range(10)
            )
            mesh_connectivity = mesh.c3d10.get(element_id) if mesh is not None else None
            admitted_connectivity = {
                mesh_connectivity,
                mesh_connectivity[:8] + (mesh_connectivity[9], mesh_connectivity[8])
                if mesh_connectivity is not None else None,
            }
            if mesh_connectivity is None or connectivity not in admitted_connectivity:
                raise _integrity(f"FRD element connectivity does not match the trusted mesh for element {element_id}")
            cursor += 2
        if cursor >= len(lines) - 1 or lines[cursor] != " -3":
            raise _integrity("truncated FRD element envelope terminator")
        if mesh is None or seen_elements != set(mesh.c3d10):
            raise _integrity("FRD element envelope does not cover the trusted mesh")
        cursor += 1

    datasets: list[_FrdDataset] = []
    seen_steps: set[int] = set()
    while cursor < len(lines) - 1:
        step_line = lines[cursor]
        if (
            len(step_line) != 70
            or step_line[:10] != "    1PSTEP"
            or step_line[10:35] != " " * 25
            or not step_line[35].isdigit()
            or step_line[36:47] != " " * 11
            or not step_line[47].isdigit()
            or step_line[48:59] != " " * 11
            or not step_line[59].isdigit()
            or step_line[60:70] != " " * 10
        ):
            raise _integrity(f"unsupported FRD PSTEP header at line {cursor + 1}")
        step = int(step_line[35])
        if step in seen_steps:
            raise _integrity(f"duplicate FRD PSTEP {step}")
        seen_steps.add(step)
        if cursor + 2 >= len(lines) - 1:
            raise _integrity("truncated FRD result block header")
        control = lines[cursor + 1]
        if (
            len(control) != 75
            or control[:8] != "  100CL "
            or control[8:12] != " 101"
                or control[12] != " "
                or control[13:24] != "1.000000000"
                or not control[24:36].strip().isdigit()
                or control[24:36] != control[24:36].strip().rjust(12)
                or control[36:57] != " " * 21
            or control[57] != "0"
            or control[58:62] != " " * 4
            or control[62] != "1"
            or control[63:74] != " " * 11
            or control[74] != "1"
        ):
            raise _integrity(f"unsupported FRD 100CL header at line {cursor + 2}")
        declared_records = int(control[24:36])
        if declared_records <= 0:
            raise _integrity("FRD 100CL record count must be positive")

        header = lines[cursor + 2]
        if len(header) != 23 or header[:5] != " -4  " or header[5:17].rstrip(" ") == "":
            raise _integrity(f"malformed FRD dataset header at line {cursor + 3}")
        name = header[5:17].rstrip(" ")
        if header[5:17] != name.ljust(12) or not header[17].isdigit() or header[18:22] != " " * 4 or header[22] != "1":
            raise _integrity(f"malformed FRD dataset header at line {cursor + 3}")
        component_count = int(header[17])
        if name == "ERROR":
            expected_components = ("STR(%)",)
            value_count = 1
        elif name in _FRD_COMPONENTS:
            expected_components = _FRD_COMPONENTS[name] + (("ALL",) if name == "DISP" else ())
            value_count = len(_FRD_COMPONENTS[name])
        else:
            raise _integrity(f"unsupported FRD dataset {name}")
        if component_count != len(expected_components):
            raise _integrity(f"wrong component count for FRD dataset {name}")

        component_start = cursor + 3
        component_lines = lines[component_start : component_start + len(expected_components)]
        if len(component_lines) != len(expected_components):
            raise _integrity(f"truncated FRD component declarations for {name}")
        expected_lines = {
            "DISP": (
                " -5  D1          1    2    1    0",
                " -5  D2          1    2    2    0",
                " -5  D3          1    2    3    0",
                " -5  ALL         1    2    0    0    1ALL",
            ),
            "STRESS": (
                " -5  SXX         1    4    1    1",
                " -5  SYY         1    4    2    2",
                " -5  SZZ         1    4    3    3",
                " -5  SXY         1    4    1    2",
                " -5  SYZ         1    4    2    3",
                " -5  SZX         1    4    3    1",
            ),
            "ERROR": (" -5  STR(%)      1    1    0    0",),
        }[name]
        if tuple(component_lines) != expected_lines:
            raise _integrity(f"unsupported FRD component declarations for {name}")

        values: list[tuple[int, tuple[float, ...]]] = []
        seen_nodes: set[int] = set()
        cursor = component_start + len(expected_components)
        while cursor < len(lines) and lines[cursor] != " -3":
            record = lines[cursor]
            if not record.startswith(" -1"):
                raise _integrity(f"malformed FRD result record at line {cursor + 1}")
            expected_length = 3 + 10 + 12 * value_count
            if len(record) != expected_length:
                raise _integrity(f"wrong FRD record width at line {cursor + 1}")
            node_id = _parse_node(record[3:13], line_number=cursor + 1)
            if node_id in seen_nodes:
                raise _integrity(f"duplicate FRD node result {node_id}")
            seen_nodes.add(node_id)
            if len(record) != 13 + 12 * value_count:
                raise _integrity(f"truncated FRD result record at line {cursor + 1}")
            parsed_values = tuple(
                _parse_frd_number(record[13 + 12 * offset : 25 + 12 * offset], line_number=cursor + 1)
                for offset in range(value_count)
            )
            values.append((node_id, parsed_values))
            cursor += 1
        if cursor == len(lines):
            raise _integrity(f"truncated FRD dataset {name}")
        if len(values) != declared_records:
            raise _integrity(f"FRD {name} record count does not match 100CL")
        datasets.append(_FrdDataset(name=name, values=tuple(values)))
        cursor += 1
    if cursor != len(lines) - 1:
        raise _integrity("FRD contains an unknown or trailing record")
    return tuple(datasets)


def _require_frd_dataset(datasets: tuple[_FrdDataset, ...], name: str) -> _FrdDataset:
    matches = tuple(dataset for dataset in datasets if dataset.name == name)
    if len(matches) != 1:
        raise _integrity(f"FRD requires exactly one {name} dataset")
    return matches[0]


class CalculiXFrdResultParser:
    identity = "mechcad-calculix-frd-result-parser@1"

    def parse(
        self,
        content: bytes,
        mesh: ParsedMesh,
        *,
        requested_result_fields: tuple[StructuralResultField, ...] | None = None,
        required_node_ids: frozenset[int] | None = None,
    ) -> ParsedCalculiXFrd:
        mesh_hash = _mesh_hash(mesh)
        datasets = _parse_frd_datasets(_frd_lines(content), mesh=mesh)
        requested = requested_result_fields or (
            StructuralResultField.DISPLACEMENT,
            StructuralResultField.VON_MISES_STRESS,
        )
        displacement = (
            _require_frd_dataset(datasets, "DISP")
            if StructuralResultField.DISPLACEMENT in requested
            else None
        )
        stress = (
            _require_frd_dataset(datasets, "STRESS")
            if StructuralResultField.VON_MISES_STRESS in requested
            else None
        )

        displacements: list[StructuralDisplacementSample] = []
        if displacement is not None:
            for node_id, values in displacement.values:
                if node_id not in mesh.nodes:
                    raise _integrity(f"FRD displacement references unknown mesh node {node_id}")
                displacements.append(
                    StructuralDisplacementSample(
                        mesh_hash=mesh_hash,
                        node_id=node_id,
                        vector_mm=values,
                        units=StructuralResultUnits(),
                    )
                )

        stress_samples: list[StructuralStressSample] = []
        if stress is not None:
            for node_id, values in stress.values:
                if node_id not in mesh.nodes:
                    raise _integrity(f"FRD stress references unknown mesh node {node_id}")
                identity = StructuralStressSampleIdentity(mesh_hash=mesh_hash, node_id=node_id)
                stress_samples.append(
                    StructuralStressSample(
                        identity=identity,
                        mesh_hash=mesh_hash,
                        representation=StressFieldRepresentation.CALCULIX_EXTRAPOLATED_NODAL_STRESS,
                        tensor_mpa=StructuralStressTensor(
                            sxx=values[0], syy=values[1], szz=values[2],
                            sxy=values[3], syz=values[4], szx=values[5],
                        ),
                        units=StructuralResultUnits(),
                    )
                )
        if required_node_ids is not None:
            required = set(required_node_ids)
            if displacement is not None and not required.issubset(
                {sample.node_id for sample in displacements}
            ):
                raise _integrity("incomplete DISP domain")
            if stress is not None and not required.issubset(
                {sample.identity.node_id for sample in stress_samples}
            ):
                raise _integrity("incomplete STRESS domain")
        return ParsedCalculiXFrd(
            mesh_hash=mesh_hash,
            displacements=tuple(displacements),
            stress_samples=tuple(stress_samples),
        )


class CalculiXDatResultParser:
    identity = "mechcad-calculix-dat-result-parser@1"

    def parse_reactions(
        self,
        content: bytes,
        mesh: ParsedMesh,
        allowed_nodes: frozenset[int],
        *,
        expected_support_set_name: str = "FIXED_NODES",
        expected_support_set_names: tuple[str, ...] | None = None,
        required_node_ids: frozenset[int] | None = None,
    ) -> tuple[NodeReaction, ...]:
        support_set_names = expected_support_set_names or (expected_support_set_name,)
        if not support_set_names or len(set(support_set_names)) != len(support_set_names) or any(
            not re.fullmatch(r"[A-Z][A-Z0-9_]*", name) for name in support_set_names
        ):
            raise _integrity("expected DAT support set identity is not a valid captured set name")
        lines = _dat_lines(content)
        header_prefix = " forces (fx,fy,fz) for set "
        header_suffix = " and time  0.1000000E+01"
        header_indices = [
            index
            for index, line in enumerate(lines)
            if line.startswith(header_prefix) and line.endswith(header_suffix)
        ]
        reactions: list[NodeReaction] = []
        seen_nodes: set[int] = set()
        mesh_hash = _mesh_hash(mesh)
        sections = []
        for index, header_index in enumerate(header_indices):
            header = lines[header_index]
            support_set_name = header[len(header_prefix) : -len(header_suffix)]
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", support_set_name):
                raise _integrity("DAT RF section support set does not match the expected identity")
            sections.append((support_set_name, header_index + 1, header_indices[index + 1] if index + 1 < len(header_indices) else len(lines)))
        if tuple(name for name, _start, _end in sections) != tuple(support_set_names):
            raise _integrity("DAT RF sections do not match the expected support regions")
        for support_set_name, start, end in sections:
            cursor = start
            while cursor < end and lines[cursor] == "":
                cursor += 1
            while cursor < end:
                record = lines[cursor]
                if not record:
                    raise _integrity(f"blank line inside DAT RF records at line {cursor + 1}")
                if len(record) != 52 or not record.startswith(" "):
                    raise _integrity(f"malformed DAT RF record at line {cursor + 1}")
                node_id = _parse_node(record[:10], line_number=cursor + 1)
                if node_id not in mesh.nodes:
                    raise _integrity(f"DAT reaction references unknown mesh node {node_id}")
                if node_id not in allowed_nodes:
                    raise _integrity(f"DAT reaction node {node_id} is outside the allowed support nodes")
                if node_id in seen_nodes:
                    raise _integrity(f"duplicate DAT reaction node {node_id}")
                seen_nodes.add(node_id)
                values = tuple(
                    _parse_dat_number(record[10 + 14 * offset : 24 + 14 * offset], line_number=cursor + 1)
                    for offset in range(3)
                )
                reactions.append(
                    StructuralReactionSample(
                        mesh_hash=mesh_hash,
                        node_id=node_id,
                        support_set_name=support_set_name,
                        vector_n=values,
                        units=StructuralResultUnits(),
                    )
                )
                cursor += 1
        if not reactions:
            raise _integrity("DAT RF section contains no reaction records")
        if required_node_ids is not None and seen_nodes != set(required_node_ids):
            raise _integrity("incomplete reaction domain")
        return tuple(reactions)


EQUILIBRIUM_POLICY_ID = "structural-equilibrium@1"


def _vector_add(left: tuple[float, float, float], right: tuple[float, float, float]):
    return tuple(left[index] + right[index] for index in range(3))


def _vector_scale(value: tuple[float, float, float], factor: float):
    return tuple(component * factor for component in value)


def _cross(left: tuple[float, float, float], right: tuple[float, float, float]):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _norm(value: tuple[float, float, float]) -> float:
    return math.sqrt(sum(component * component for component in value))


def _vectors_close(left, right, *, absolute_tolerance: float = 1e-9) -> bool:
    return all(
        math.isclose(left[index], right[index], rel_tol=0.0, abs_tol=absolute_tolerance)
        for index in range(3)
    )


def _mesh_digest(mesh: ParsedMesh) -> str:
    return "sha256:" + hashlib.sha256(mesh.mesh_bytes).hexdigest()


def _parse_verified_msh(content: bytes) -> ParsedMesh:
    """Parse the ASCII MSH 2 subset emitted by the admitted Gmsh provider."""
    try:
        text = content.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise _integrity("MSH bytes must be strict ASCII") from exc
    lines = text.splitlines()
    if "$MeshFormat" not in lines or "2.2 0 8" not in lines:
        raise _integrity("unsupported MSH format")

    physical_names: dict[tuple[int, int], str] = {}
    nodes: dict[int, tuple[float, float, float]] = {}
    c3d10: dict[int, tuple[int, ...]] = {}
    surface_elements: dict[str, list[tuple[int, tuple[int, ...]]]] = {}
    physical_groups = []

    def section(name: str) -> list[str]:
        try:
            start = lines.index("$" + name) + 2
            end = lines.index("$End" + name, start)
        except ValueError as exc:
            raise _integrity(f"MSH is missing {name} section") from exc
        try:
            count = int(lines[start - 1])
        except ValueError as exc:
            raise _integrity(f"MSH {name} section has an invalid count") from exc
        records = lines[start:end]
        if len(records) != count:
            raise _integrity(f"MSH {name} record count mismatch")
        return records

    for record in section("PhysicalNames"):
        match = re.fullmatch(r"(\d+)\s+(\d+)\s+\"([^\"]+)\"", record)
        if match is None:
            raise _integrity("malformed MSH physical-name record")
        physical_names[(int(match.group(1)), int(match.group(2)))] = match.group(3)

    for record in section("Nodes"):
        fields = record.split()
        if len(fields) != 4:
            raise _integrity("malformed MSH node record")
        try:
            node_id = int(fields[0])
            coordinates = tuple(float(value) for value in fields[1:4])
        except ValueError as exc:
            raise _integrity("malformed MSH node value") from exc
        if node_id <= 0 or node_id in nodes or not all(math.isfinite(value) for value in coordinates):
            raise _integrity("invalid or duplicate MSH node identity")
        nodes[node_id] = coordinates

    for record in section("Elements"):
        fields = record.split()
        if len(fields) < 4:
            raise _integrity("malformed MSH element record")
        try:
            element_id, element_type, tag_count = (int(fields[0]), int(fields[1]), int(fields[2]))
            tags = [int(value) for value in fields[3 : 3 + tag_count]]
            element_nodes = tuple(int(value) for value in fields[3 + tag_count :])
        except ValueError as exc:
            raise _integrity("malformed MSH element value") from exc
        if element_id <= 0 or tag_count < 1 or len(tags) != tag_count:
            raise _integrity("invalid MSH element identity or tags")
        physical_id = tags[0]
        entity_id = tags[1] if len(tags) > 1 else physical_id
        if element_type == 11:
            if len(element_nodes) != 10 or element_id in c3d10:
                raise _integrity("invalid or duplicate C3D10 element")
            if any(node_id not in nodes for node_id in element_nodes):
                raise _integrity("C3D10 references an unknown mesh node")
            c3d10[element_id] = canonical_c3d10_nodes(element_nodes)
            group_name = physical_names.get((3, physical_id))
            if group_name:
                physical_groups.append((None, group_name, 3, entity_id))
        elif element_type in (2, 9):
            expected_nodes = 3 if element_type == 2 else 6
            if len(element_nodes) != expected_nodes:
                raise _integrity("invalid MSH boundary element")
            region = physical_names.get((2, physical_id))
            if not region:
                raise _integrity("MSH boundary element has no semantic physical group")
            if any(node_id not in nodes for node_id in element_nodes):
                raise _integrity("boundary element references an unknown mesh node")
            surface_elements.setdefault(region, []).append((element_id, element_nodes))
            physical_groups.append((region, region, 2, entity_id))

    if not nodes or not c3d10 or not surface_elements:
        raise _integrity("MSH has no complete structural mesh")
    unique_groups = set(physical_groups)
    from mechcad_harness.structural.models import PhysicalGroupBinding

    bindings = tuple(
        PhysicalGroupBinding(
            semantic_region_id=semantic_region_id,
            physical_group_name=group_name,
            gmsh_entity_dim=dimension,
            gmsh_entity_id=entity_id,
        )
        for semantic_region_id, group_name, dimension, entity_id in sorted(
            unique_groups, key=lambda item: (item[2], item[1], item[3])
        )
    )
    return ParsedMesh(
        nodes=nodes,
        c3d10=c3d10,
        surface_elements=surface_elements,
        volume_elset_name="volume",
        physical_groups=bindings,
        mesh_bytes=content,
    )


def _parse_verified_mesh(content: bytes) -> ParsedMesh:
    if content.lstrip().startswith(b"$MeshFormat"):
        return _parse_verified_msh(content)
    if content.lstrip().startswith(b"*NODE"):
        from mechcad_harness.structural.mesh import _parse_inp

        try:
            mesh = _parse_inp(content.decode("ascii", errors="strict"))
        except (UnicodeDecodeError, ValueError, KeyError) as exc:
            raise _integrity("malformed INP mesh source") from exc
        return mesh
    raise _integrity("unsupported trusted mesh source")


def parse_trusted_mesh_bytes(content: bytes) -> ParsedMesh:
    """Parse mesh bytes through the admitted structural mesh parser."""
    return _parse_verified_mesh(content)


def parse_trusted_msh_bytes(content: bytes) -> ParsedMesh:
    """Parse only the admitted ASCII MSH artifact format."""
    if not content.lstrip().startswith(b"$MeshFormat"):
        raise _integrity("trusted analytical mesh must be an MSH artifact")
    return _parse_verified_msh(content)


class StructuralResultInterpreter:
    """Admit only source-bound, byte-verified successful CalculiX outputs."""

    def __init__(
        self,
        *,
        workspace: str | Path,
        project_id: str,
        request=None,
        definition: StructuralAnalysisDefinition | None = None,
        frd_parser: CalculiXFrdResultParser | None = None,
        dat_parser: CalculiXDatResultParser | None = None,
        mesh_parser: Callable[[bytes], ParsedMesh] | None = None,
    ):
        self.workspace = Path(workspace)
        self.project_id = project_id
        self.request = request
        self.definition = definition
        self.frd_parser = frd_parser or CalculiXFrdResultParser()
        self.dat_parser = dat_parser or CalculiXDatResultParser()
        self.mesh_parser = mesh_parser or parse_trusted_msh_bytes

    def interpret(self, request_manifest: StructuralExecutionManifest, request=None, definition=None) -> StructuralAnalysisResult:
        request = request or self.request
        definition = definition or self.definition
        if request is None or definition is None:
            raise StructuralResultIntegrityError("result interpretation requires the bound request and definition")
        self._verify_manifest_binding(request_manifest, request, definition)
        store = ArtifactStore(
            self.workspace,
            project_id=request_manifest.project_id,
            run_id=request_manifest.run_id,
        )

        source_step = store.read_verified_in_project(
            request.source_binding.geometry_artifact_id,
            expected_type=ArtifactType.STEP,
            expected_hash=request.source_binding.geometry_artifact_hash,
        )
        if source_step is None:
            raise StructuralResultIntegrityError("source STEP artifact is missing or byte-untrusted")
        source_artifact, _source_bytes = source_step
        if (
            source_artifact.artifact_type is not ArtifactType.STEP
            or source_artifact.sha256 != request.source_binding.geometry_artifact_hash
            or source_artifact.bound_revision != request.source_binding.source_revision
            or source_artifact.bound_state_hash != request.source_binding.source_state_hash
            or source_artifact.project_id != request.source_binding.project_id
        ):
            raise StructuralResultIntegrityError("source STEP artifact binding mismatch")
        if (
            not self._is_trusted_freecad_provenance(request_manifest.geometry_provider_provenance)
            or source_artifact.backend_provenance != request_manifest.geometry_provider_provenance
        ):
            raise StructuralResultIntegrityError("source geometry provider provenance mismatch")

        # Read and hash every selected artifact before invoking either result parser.
        mesh_input_identity = mesh_input_hash(
            source_geometry_hash=request.source_binding.geometry_artifact_hash,
            mesh_specification_hash=request_manifest.mesh_specification_hash,
            region_map_hash=request_manifest.region_map_hash,
            gmsh_identity=request_manifest.gmsh_identity,
            gmsh_version=request_manifest.gmsh_version,
        )
        mesh_bytes = self._read_artifact(
            store, request_manifest.mesh_artifact_id, request_manifest.mesh_artifact_hash,
            ArtifactType.MSH, "MSH", request_manifest,
            producer_identity=request_manifest.gmsh_identity,
            producer_version=request_manifest.gmsh_version,
            input_hash=mesh_input_identity,
            expected_backend_provenance=provenance_from_identity(GMSH_IDENTITY),
        )[0]
        case_bytes: list[tuple[StructuralCaseExecutionManifest, bytes, bytes | None, bytes | None, bytes | None]] = []
        for case in request_manifest.case_manifests:
            if case.run_id not in (None, request_manifest.run_id):
                raise StructuralResultIntegrityError("case manifest run identity mismatch")
            for kind, artifact_id in (
                ("inp", case.deck_artifact_id), ("frd", case.frd_artifact_id),
                ("dat", case.dat_artifact_id), ("log", case.log_artifact_id),
            ):
                if artifact_id is not None and artifact_id != self._expected_artifact_id(request, kind, case.load_case_id):
                    raise StructuralResultIntegrityError(f"{case.load_case_id} {kind} artifact identity mismatch")
            deck_identity = case.deck_builder_identity or request_manifest.deck_builder_identity
            deck_version = case.deck_builder_version or request_manifest.deck_builder_version
            deck_bytes = self._read_artifact(
                store, case.deck_artifact_id, case.deck_artifact_hash,
                ArtifactType.INP, "deck", request_manifest,
                producer_identity=deck_identity,
                producer_version=deck_version,
                input_hash=request_manifest.mesh_artifact_hash,
            )[0]
            if case.deck_semantic_hash != "sha256:" + hashlib.sha256(deck_bytes).hexdigest():
                raise StructuralResultIntegrityError("deck semantic/byte hash mismatch")
            solver_manifest = case.solver_manifest
            frd_bytes = None
            if StructuralResultField.DISPLACEMENT in request.requested_result_fields or StructuralResultField.VON_MISES_STRESS in request.requested_result_fields:
                frd_bytes = self._read_artifact(
                    store, case.frd_artifact_id, case.frd_artifact_hash,
                    ArtifactType.FRD, "FRD", request_manifest,
                    producer_identity=solver_manifest.calculix_identity,
                    producer_version=solver_manifest.calculix_version,
                    input_hash=case.deck_artifact_hash,
                    expected_backend_provenance=solver_manifest.backend_provenance,
                )[0]
            dat_bytes = None
            if StructuralResultField.REACTIONS in request.requested_result_fields:
                dat_bytes = self._read_artifact(
                    store, case.dat_artifact_id, case.dat_artifact_hash,
                    ArtifactType.DAT, "DAT", request_manifest,
                    producer_identity=solver_manifest.calculix_identity,
                    producer_version=solver_manifest.calculix_version,
                    input_hash=case.deck_artifact_hash,
                    expected_backend_provenance=solver_manifest.backend_provenance,
                )[0]
            log_bytes = self._read_artifact(
                store, case.log_artifact_id, case.log_artifact_hash,
                ArtifactType.LOG, "LOG", request_manifest,
                producer_identity=solver_manifest.calculix_identity,
                producer_version=solver_manifest.calculix_version,
                input_hash=case.deck_artifact_hash,
                expected_backend_provenance=solver_manifest.backend_provenance,
            )[0]
            case_bytes.append((case, deck_bytes, frd_bytes, dat_bytes, log_bytes))

        try:
            shared_mesh = self.mesh_parser(mesh_bytes)
        except StructuralResultIntegrityError:
            raise
        except Exception as exc:
            raise StructuralResultIntegrityError(f"MSH mesh parse failed: {exc}") from exc
        shared_mesh_hash = _mesh_digest(shared_mesh)
        if shared_mesh_hash != request_manifest.mesh_artifact_hash:
            raise StructuralResultIntegrityError("MSH artifact byte/hash mismatch")
        self._verify_mesh_manifest(shared_mesh, request_manifest, request)
        self._verify_mesh_regions(shared_mesh, definition)
        self._verify_lowered_load_provenance(
            shared_mesh, request_manifest, definition,
            {case.load_case_id: deck_bytes for case, deck_bytes, *_ in case_bytes},
        )

        results = []
        for case, _deck_bytes, frd_bytes, dat_bytes, _log_bytes in case_bytes:
            results.append(self._interpret_case(
                case, shared_mesh, shared_mesh_hash, frd_bytes, dat_bytes, request, definition,
            ))
        return StructuralAnalysisResult(
            run_id=request_manifest.run_id,
            source_binding=request.source_binding,
            definition_id=definition.id,
            definition_hash=structural_definition_hash(definition),
            request_hash=request.request_hash,
            execution_manifest_hash=execution_manifest_hash(request_manifest),
            mesh_hash=shared_mesh_hash,
            load_case_results=tuple(results),
            parser_provenance=StructuralResultParserProvenance(
                frd_parser_identity=self.frd_parser.identity,
                dat_parser_identity=self.dat_parser.identity,
            ),
        )

    def load_trusted_mesh(
        self,
        request_manifest: StructuralExecutionManifest,
        request=None,
        definition=None,
    ) -> tuple[ParsedMesh, bytes]:
        """Reload and parse the authoritative mesh artifact for validation."""
        request = request or self.request
        definition = definition or self.definition
        if request is None or definition is None:
            raise StructuralResultIntegrityError(
                "trusted mesh loading requires the bound request and definition"
            )
        self._verify_manifest_binding(request_manifest, request, definition)
        mesh_input_identity = mesh_input_hash(
            source_geometry_hash=request.source_binding.geometry_artifact_hash,
            mesh_specification_hash=request_manifest.mesh_specification_hash,
            region_map_hash=request_manifest.region_map_hash,
            gmsh_identity=request_manifest.gmsh_identity,
            gmsh_version=request_manifest.gmsh_version,
        )
        store = ArtifactStore(
            self.workspace,
            project_id=request_manifest.project_id,
            run_id=request_manifest.run_id,
        )
        content, _artifact = self._read_artifact(
            store,
            request_manifest.mesh_artifact_id,
            request_manifest.mesh_artifact_hash,
            ArtifactType.MSH,
            "MSH",
            request_manifest,
            producer_identity=request_manifest.gmsh_identity,
            producer_version=request_manifest.gmsh_version,
            input_hash=mesh_input_identity,
            expected_backend_provenance=provenance_from_identity(GMSH_IDENTITY),
        )
        try:
            mesh = self.mesh_parser(content)
        except StructuralResultIntegrityError:
            raise
        except Exception as exc:
            raise StructuralResultIntegrityError(f"MSH mesh parse failed: {exc}") from exc
        if _mesh_digest(mesh) != request_manifest.mesh_artifact_hash:
            raise StructuralResultIntegrityError("MSH artifact byte/hash mismatch")
        self._verify_mesh_manifest(mesh, request_manifest, request)
        self._verify_mesh_regions(mesh, definition)
        return mesh, content

    def _verify_manifest_binding(self, manifest, request, definition):
        if not isinstance(manifest, StructuralExecutionManifest):
            raise StructuralResultIntegrityError("missing structural execution manifest")
        if manifest.execution_status is not StructuralExecutionStatus.SUCCEEDED:
            raise StructuralResultIntegrityError("execution manifest is not successful")
        if manifest.calculix_version != CALCULIX_IDENTITY.library_version:
            raise StructuralResultIntegrityError(
                "execution manifest does not carry the trusted CalculiX version"
            )
        if (
            manifest.gmsh_identity != GMSH_PROVIDER_IDENTITY
            or manifest.gmsh_version != GMSH_IDENTITY.library_version
        ):
            raise StructuralResultIntegrityError("trusted Gmsh identity/version mismatch")
        if (
            manifest.resolver_identity != REGION_RESOLVER_IDENTITY
            or manifest.resolver_version != REGION_RESOLVER_VERSION
        ):
            raise StructuralResultIntegrityError("trusted region resolver identity/version mismatch")
        if not self._is_trusted_freecad_provenance(manifest.geometry_provider_provenance):
            raise StructuralResultIntegrityError("source geometry provider provenance mismatch")
        binding = request.source_binding
        checks = (
            manifest.project_id == self.project_id == binding.project_id,
            manifest.revision == binding.source_revision,
            manifest.state_hash == binding.source_state_hash,
            manifest.definition_id == binding.definition_id == definition.id,
            manifest.definition_hash == binding.definition_hash == structural_definition_hash(definition),
            manifest.request_hash == request.request_hash,
            manifest.analytical_policy_hash == request.analytical_policy_hash,
            manifest.geometry_artifact_id == binding.geometry_artifact_id,
            manifest.geometry_artifact_hash == binding.geometry_artifact_hash,
            manifest.calculix_identity == CALCULIX_PROVIDER_IDENTITY,
            manifest.mesh_specification_hash == self._mesh_specification_hash(request),
            manifest.mesh_manifest is not None
            and manifest.mesh_manifest_hash == mesh_manifest_hash(manifest.mesh_manifest)
            and manifest.mesh_manifest.region_map_hash == manifest.region_map_hash,
            len(manifest.case_manifests) != 1 or (
                manifest.solver_manifest is not None
                and manifest.solver_manifest.calculix_identity == manifest.calculix_identity
                and manifest.solver_manifest.calculix_version == manifest.calculix_version
                and manifest.solver_manifest.calculix_version == CALCULIX_IDENTITY.library_version
                and manifest.solver_manifest.backend_provenance == self._trusted_calculix_provenance()
            ),
        )
        if not all(checks):
            labels = (
                "project", "revision", "state", "definition_id", "definition_hash", "request_hash",
                "analytical_policy_hash",
                "geometry_id", "geometry_hash", "calculix_identity", "mesh_specification_hash",
                "mesh_manifest", "solver_provenance",
            )
            failed = ", ".join(label for label, valid in zip(labels, checks) if not valid)
            raise StructuralResultIntegrityError(
                f"execution manifest source/request/definition binding mismatch: {failed}"
            )
        request.validate_against(definition)
        if manifest.selected_load_case_ids != request.selected_load_case_ids:
            raise StructuralResultIntegrityError("execution manifest load-case selection mismatch")
        if not manifest.case_manifests or tuple(case.load_case_id for case in manifest.case_manifests) != request.selected_load_case_ids:
            raise StructuralResultIntegrityError("execution manifest case manifests are missing or unordered")
        if any(case.execution_status is not StructuralExecutionStatus.SUCCEEDED for case in manifest.case_manifests):
            raise StructuralResultIntegrityError("execution manifest contains a failed load case")
        if any(
            case.solver_manifest is None
            or case.solver_manifest.calculix_identity != manifest.calculix_identity
            or case.solver_manifest.calculix_version != manifest.calculix_version
            or case.solver_manifest.calculix_version != CALCULIX_IDENTITY.library_version
            or case.solver_manifest.backend_provenance != self._trusted_calculix_provenance()
            or not case.deck_builder_identity
            or case.deck_builder_identity != manifest.deck_builder_identity
            or case.deck_builder_version != manifest.deck_builder_version
            or case.deck_semantic_hash is None
            for case in manifest.case_manifests
        ):
            raise StructuralResultIntegrityError("load-case solver provenance mismatch")
        if any(
            case.solver_manifest is None
            or case.solver_manifest.exit_code != 0
            or case.solver_manifest.job_finished is not True
            or case.solver_manifest.produced_frd is not True
            or case.solver_manifest.produced_dat is not True
            or case.solver_manifest.produced_log is not True
            for case in manifest.case_manifests
        ):
            raise StructuralResultIntegrityError("successful case solver manifest semantics mismatch")
        if any(
            any(getattr(case, field) is None for field in (
                "frd_artifact_id", "frd_artifact_hash", "dat_artifact_id", "dat_artifact_hash",
                "log_artifact_id", "log_artifact_hash",
            ))
            for case in manifest.case_manifests
        ):
            raise StructuralResultIntegrityError("successful case output references are required")
        if any(
            case.mesh_artifact_id != manifest.mesh_artifact_id
            or case.mesh_artifact_hash != manifest.mesh_artifact_hash
            for case in manifest.case_manifests
        ):
            raise StructuralResultIntegrityError("case manifest mesh binding mismatch")
        if len(manifest.case_manifests) == 1:
            case = manifest.case_manifests[0]
            if any(
                getattr(manifest, field) != getattr(case, field)
                for field in (
                    "deck_artifact_id", "deck_artifact_hash", "frd_artifact_id", "frd_artifact_hash",
                    "dat_artifact_id", "dat_artifact_hash", "log_artifact_id", "log_artifact_hash",
                )
            ):
                raise StructuralResultIntegrityError("top-level and case artifact bindings mismatch")
        request_manifest = StructuralRequestExecutionManifest(
            selected_load_case_ids=manifest.selected_load_case_ids,
            case_manifests=manifest.case_manifests,
            mesh_artifact_id=manifest.mesh_artifact_id,
            mesh_artifact_hash=manifest.mesh_artifact_hash,
            analytical_policy_hash=manifest.analytical_policy_hash,
            execution_status=manifest.execution_status,
        )
        if manifest.request_manifest_hash != request_manifest.request_manifest_hash:
            raise StructuralResultIntegrityError("request manifest hash mismatch")
        if tuple(load for case in manifest.case_manifests for load in case.lowered_loads) != manifest.lowered_loads:
            raise StructuralResultIntegrityError("lowered-load provenance does not match case manifests")

    @staticmethod
    def _mesh_specification_hash(request):
        payload = request.mesh_specification.model_dump(mode="json")
        return "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _expected_artifact_id(request, kind: str, load_case_id: str) -> str:
        payload = f"{request.request_hash}|{load_case_id}|{kind}".encode("utf-8")
        return f"STRUCT-{kind.upper()}-{hashlib.sha256(payload).hexdigest()[:16]}"

    def _read_artifact(
        self,
        store,
        artifact_id,
        expected_hash,
        expected_type,
        label,
        manifest,
        *,
        producer_identity,
        producer_version,
        input_hash=None,
        expected_backend_provenance=None,
    ):
        if not artifact_id or not expected_hash or not producer_identity or not producer_version:
            raise StructuralResultIntegrityError(f"{label} artifact is required but missing")
        try:
            verified = store.read_verified_strict(
                artifact_id, expected_type=expected_type, expected_hash=expected_hash
            )
        except ArtifactVerificationError as exc:
            raise StructuralResultIntegrityError(f"{label} {exc}") from exc
        if verified is None:
            raise StructuralResultIntegrityError(f"{label} artifact is missing or untrusted")
        artifact, content = verified
        if expected_type is ArtifactType.LOG and not content:
            raise StructuralResultIntegrityError(f"{label} artifact is empty")
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        if digest != expected_hash or artifact.sha256 != expected_hash or artifact.size_bytes != len(content):
            raise StructuralResultIntegrityError(f"{label} artifact byte/hash mismatch")
        if artifact.artifact_id != artifact_id or artifact.project_id != manifest.project_id or artifact.run_id != manifest.run_id:
            raise StructuralResultIntegrityError(f"{label} artifact identity mismatch")
        if artifact.artifact_type is not expected_type:
            raise StructuralResultIntegrityError(f"{label} artifact type mismatch")
        if artifact.bound_revision != manifest.revision or artifact.bound_state_hash != manifest.state_hash:
            raise StructuralResultIntegrityError(f"{label} artifact source binding mismatch")
        if artifact.producer_tool_name != producer_identity:
            raise StructuralResultIntegrityError(f"{label} artifact producer mismatch")
        if artifact.producer_tool_version != producer_version:
            raise StructuralResultIntegrityError(f"{label} artifact producer version mismatch")
        if expected_backend_provenance is not None and artifact.backend_provenance != expected_backend_provenance:
            raise StructuralResultIntegrityError(f"{label} artifact backend provenance mismatch")
        if input_hash is not None and artifact.input_hash != input_hash:
            raise StructuralResultIntegrityError(f"{label} artifact input binding mismatch")
        ref = next((ref for ref in manifest.artifacts if ref.artifact_id == artifact_id), None)
        if ref is None:
            raise StructuralResultIntegrityError(f"{label} artifact manifest reference is missing")
        if (
            ref.sha256 != expected_hash or ref.artifact_type != expected_type.value
            or ref.producer_identity != producer_identity or ref.producer_version != producer_version
        ):
            raise StructuralResultIntegrityError(f"{label} artifact manifest reference mismatch")
        return content, artifact

    @staticmethod
    def _is_trusted_freecad_provenance(provenance) -> bool:
        return provenance is not None and (
            provenance.backend_name == FREECAD_IDENTITY.name
            and provenance.backend_adapter_version == FREECAD_IDENTITY.adapter_version
            and provenance.library_name == FREECAD_IDENTITY.library_name
            and provenance.library_version == FREECAD_IDENTITY.library_version
            and provenance.library_source == FREECAD_IDENTITY.library_source
            and provenance.library_revision == FREECAD_IDENTITY.library_revision
        )

    @staticmethod
    def _trusted_calculix_provenance():
        return provenance_from_identity(CALCULIX_IDENTITY)

    @staticmethod
    def _verify_mesh_regions(mesh: ParsedMesh, definition: StructuralAnalysisDefinition):
        for region in definition.regions:
            nodes = mesh.surface_elements.get(region.region_id)
            if not nodes:
                raise StructuralResultIntegrityError(
                    f"mesh physical group is missing structural region {region.region_id}"
                )
            if any(node_id not in mesh.nodes for _, element_nodes in nodes for node_id in element_nodes):
                raise StructuralResultIntegrityError("mesh physical group references an unknown node")

    @staticmethod
    def _verify_mesh_manifest(mesh: ParsedMesh, manifest: StructuralExecutionManifest, request):
        expected = manifest.mesh_manifest
        if expected is None:
            raise StructuralResultIntegrityError("mesh manifest is required")
        if expected.mesh_specification_hash != StructuralResultInterpreter._mesh_specification_hash(request):
            raise StructuralResultIntegrityError("mesh manifest mesh specification hash mismatch")
        if expected.mesh_hash != manifest.mesh_artifact_hash:
            raise StructuralResultIntegrityError("mesh manifest hash does not match MSH artifact")
        if expected.gmsh_identity != manifest.gmsh_identity or expected.gmsh_version != manifest.gmsh_version:
            raise StructuralResultIntegrityError("mesh manifest Gmsh provenance mismatch")
        if expected.element_family != "c3d10":
            raise StructuralResultIntegrityError("mesh manifest element family is unsupported")
        if expected.node_count != len(mesh.nodes):
            raise StructuralResultIntegrityError("parsed mesh node count does not match mesh manifest")
        if expected.volume_element_count != len(mesh.c3d10):
            raise StructuralResultIntegrityError("parsed mesh volume count does not match mesh manifest")
        boundary_count = sum(len(elements) for elements in mesh.surface_elements.values())
        if expected.boundary_element_count != boundary_count:
            raise StructuralResultIntegrityError(
                f"parsed mesh boundary count does not match mesh manifest: {boundary_count} != {expected.boundary_element_count}"
            )
        expected_groups = tuple(sorted(expected.physical_groups, key=lambda group: (
            group.gmsh_entity_dim, group.physical_group_name, group.gmsh_entity_id,
        )))
        actual_groups = tuple(sorted(mesh.physical_groups, key=lambda group: (
            group.gmsh_entity_dim, group.physical_group_name, group.gmsh_entity_id,
        )))
        if actual_groups != expected_groups:
            raise StructuralResultIntegrityError(
                f"parsed mesh physical groups do not match mesh manifest: {actual_groups!r} != {expected_groups!r}"
            )
        if expected.region_map_hash != manifest.region_map_hash:
            raise StructuralResultIntegrityError("mesh manifest region map hash mismatch")

    @staticmethod
    def _verify_lowered_load_provenance(mesh: ParsedMesh, manifest: StructuralExecutionManifest, definition, deck_bytes_by_case):
        case_by_id = {case.id: case for case in definition.load_cases}
        for case_manifest in manifest.case_manifests:
            canonical_case = case_by_id.get(case_manifest.load_case_id)
            if canonical_case is None:
                raise StructuralResultIntegrityError("lowered-load provenance references an unknown load case")
            lowered_by_id = {
                lowered.canonical_load_id: lowered
                for lowered in case_manifest.lowered_loads
            }
            if len(lowered_by_id) != len(case_manifest.lowered_loads):
                raise StructuralResultIntegrityError(
                    "each canonical resultant force requires exactly one lowered-load provenance"
                )
            canonical_resultants = tuple(
                load for load in canonical_case.loads
                if isinstance(load, StructuralResultantForce)
            )
            if set(lowered_by_id) != {load.load_id for load in canonical_resultants}:
                raise StructuralResultIntegrityError(
                    "each canonical resultant force requires exactly one lowered-load provenance"
                )
            deck_bytes = deck_bytes_by_case.get(case_manifest.load_case_id)
            if deck_bytes is None:
                raise StructuralResultIntegrityError("deck bytes are unavailable for lowered-load verification")
            try:
                deck_text = deck_bytes.decode("ascii", errors="strict")
            except UnicodeDecodeError as exc:
                raise StructuralResultIntegrityError("deck CLOAD lowering is not strict ASCII") from exc

            expected_cload: dict[int, tuple[float, float, float]] = {}
            for canonical in canonical_resultants:
                lowered = lowered_by_id[canonical.load_id]
                expected = StructuralResultInterpreter._reconstruct_resultant_lowering(
                    mesh, canonical, deck_text=deck_text,
                )
                expected_force, expected_point, expected_area, expected_traction, expected_nodal, force_error, moment_error = expected
                if lowered.canonical_load_semantic_hash != canonical_load_semantic_hash(canonical):
                    raise StructuralResultIntegrityError("lowered-load provenance canonical load semantic hash mismatch")
                if lowered.mesh_hash != manifest.mesh_artifact_hash:
                    raise StructuralResultIntegrityError("lowered-load provenance mesh mismatch")
                if lowered.resolved_region_map_hash != manifest.region_map_hash:
                    raise StructuralResultIntegrityError("lowered-load provenance region-map mismatch")
                if lowered.semantic_region_id != canonical.target_region_id:
                    raise StructuralResultIntegrityError("lowered-load provenance region mismatch")
                if not _vectors_close(lowered.source_force_vector_n, expected_force):
                    raise StructuralResultIntegrityError("lowered-load provenance does not match canonical load force")
                if not math.isclose(lowered.exact_semantic_face_area_mm2, expected_area, rel_tol=0.0, abs_tol=1e-9):
                    raise StructuralResultIntegrityError("lowered-load provenance face area does not match trusted mesh region")
                expected = StructuralResultInterpreter._reconstruct_resultant_lowering(
                    mesh, canonical, deck_text=deck_text,
                    traction_area=lowered.exact_semantic_face_area_mm2,
                )
                expected_force, expected_point, expected_area, expected_traction, expected_nodal, force_error, moment_error = expected
                if not _vectors_close(lowered.source_application_point_mm, expected_point):
                    raise StructuralResultIntegrityError("lowered-load provenance application point does not match trusted mesh region")
                if not _vectors_close(lowered.normalized_solver_traction_vector_n_per_mm2, expected_traction):
                    raise StructuralResultIntegrityError("lowered-load provenance traction does not match canonical load")
                if not math.isclose(lowered.force_conservation_error_n, force_error, rel_tol=0.0, abs_tol=1e-6):
                    raise StructuralResultIntegrityError("lowered-load provenance force conservation error is not independently verified")
                if not math.isclose(lowered.moment_conservation_error_n_mm, moment_error, rel_tol=0.0, abs_tol=1e-6):
                    raise StructuralResultIntegrityError("lowered-load provenance moment conservation error is not independently verified")
                if force_error > RESULTANT_FORCE_CONSERVATION_TOLERANCE_N or moment_error > RESULTANT_FORCE_CONSERVATION_TOLERANCE_N:
                    raise StructuralResultIntegrityError("canonical resultant force lowering is not conserved")
                if lowered.lowering_algorithm_id != "consistent-nodal-surface-integration@1":
                    raise StructuralResultIntegrityError("unsupported lowered-load algorithm")
                if lowered.c3d10_surface_integration_rule_version != "consistent-nodal-planar@1":
                    raise StructuralResultIntegrityError("unsupported lowered-load integration rule")
                for node_id, vector in expected_nodal.items():
                    existing = expected_cload.get(node_id, (0.0, 0.0, 0.0))
                    expected_cload[node_id] = tuple(
                        existing[index] + vector[index] for index in range(3)
                    )
                if lowered.produced_nodal_load_semantic_hash != lowered_load_semantic_hash(expected_cload):
                    raise StructuralResultIntegrityError("lowered-load provenance nodal CLOAD hash is not independently verified")

            try:
                actual_cload = parse_cload_semantics(deck_text)
            except Exception as exc:
                raise StructuralResultIntegrityError("deck CLOAD lowering is malformed") from exc
            if set(actual_cload) != set(expected_cload) or any(
                not _vectors_close(actual_cload[node_id], expected_cload[node_id])
                for node_id in expected_cload
            ):
                raise StructuralResultIntegrityError("deck CLOAD lowering does not match trusted mesh and canonical loads")
            if cload_semantic_hash(deck_text) != lowered_load_semantic_hash(expected_cload):
                raise StructuralResultIntegrityError("deck CLOAD lowering hash does not match trusted nodal semantics")

    @staticmethod
    def _reconstruct_resultant_lowering(
        mesh: ParsedMesh,
        load: StructuralResultantForce,
        *,
        deck_text: str | None = None,
        traction_area: float | None = None,
    ):
        if deck_text is None:
            elements = mesh.surface_elements.get(load.target_region_id)
            if not elements:
                raise StructuralResultIntegrityError(
                    f"lowered-load provenance region is missing from mesh: {load.target_region_id}"
                )
            try:
                mapped = map_surface_to_volume_faces(mesh, load.target_region_id)
            except (DeckBuildError, KeyError) as exc:
                raise StructuralResultIntegrityError(
                    "lowered-load provenance cannot reconstruct the trusted C3D10 surface"
                ) from exc
            mapped_by_boundary_id = {item[0]: item for item in mapped}
            if len(mapped_by_boundary_id) != len(elements):
                raise StructuralResultIntegrityError("lowered-load provenance has duplicate mesh boundary identities")
            surface_geometry = [
                (
                    element_nodes,
                    mapped_by_boundary_id[boundary_id][3],
                )
                for boundary_id, element_nodes in elements
            ]
        else:
            surface_geometry = StructuralResultInterpreter._deck_surface_geometry(
                mesh, deck_text, load.target_region_id,
            )

        area = 0.0
        centroid_acc = [0.0, 0.0, 0.0]
        triangle_data: list[tuple[tuple[int, int, int], float]] = []
        direction_norm = math.sqrt(sum(component * component for component in load.direction_xyz))
        force = tuple(load.magnitude_n * component / direction_norm for component in load.direction_xyz)
        nodal: dict[int, tuple[float, float, float]] = {}
        for element_nodes, midside_nodes in surface_geometry:
            if len(element_nodes) != 6 or any(node_id not in mesh.nodes for node_id in element_nodes):
                raise StructuralResultIntegrityError("lowered-load provenance has an invalid semantic surface element")
            a, b, c = (mesh.nodes[node_id] for node_id in element_nodes[:3])
            cross = _cross(
                tuple(b[index] - a[index] for index in range(3)),
                tuple(c[index] - a[index] for index in range(3)),
            )
            triangle_area = 0.5 * _norm(cross)
            if triangle_area <= 0:
                raise StructuralResultIntegrityError("lowered-load provenance has a zero-area semantic surface element")
            triangle_centroid = tuple(
                (a[index] + b[index] + c[index]) / 3.0 for index in range(3)
            )
            area += triangle_area
            for index in range(3):
                centroid_acc[index] += triangle_centroid[index] * triangle_area
            if len(midside_nodes) != 3:
                raise StructuralResultIntegrityError("lowered-load provenance cannot reconstruct C3D10 midside nodes")
            triangle_data.append((midside_nodes, triangle_area))
        if area <= 0:
            raise StructuralResultIntegrityError("lowered-load provenance semantic face area is unavailable")
        load_area = traction_area if traction_area is not None else area
        if load_area <= 0 or not math.isfinite(load_area):
            raise StructuralResultIntegrityError("lowered-load provenance semantic face area is invalid")
        traction = tuple(force[index] / load_area for index in range(3))
        for midside_nodes, triangle_area in triangle_data:
            contribution = tuple(triangle_area * value / 3.0 for value in traction)
            for node_id in midside_nodes:
                existing = nodal.get(node_id, (0.0, 0.0, 0.0))
                nodal[node_id] = tuple(existing[index] + contribution[index] for index in range(3))
        point = tuple(value / area for value in centroid_acc)
        nodal_force = tuple(sum(vector[index] for vector in nodal.values()) for index in range(3))
        nodal_moment = tuple(
            sum(_cross(mesh.nodes[node_id], vector)[index] for node_id, vector in nodal.items())
            for index in range(3)
        )
        expected_moment = _cross(point, force)
        force_error = _norm(tuple(nodal_force[index] - force[index] for index in range(3)))
        moment_error = _norm(tuple(nodal_moment[index] - expected_moment[index] for index in range(3)))
        return force, point, area, traction, nodal, force_error, moment_error

    @staticmethod
    def _deck_surface_geometry(mesh: ParsedMesh, deck_text: str, region_id: str):
        deck_nodes: dict[int, tuple[float, float, float]] = {}
        volume_elements: dict[int, tuple[int, ...]] = {}
        surfaces: dict[str, list[tuple[int, str]]] = {}
        section = None
        current_surface = None
        for raw_line in deck_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("*"):
                lower = line.lower()
                current_surface = None
                if lower == "*node" or lower.startswith("*node,"):
                    section = "node"
                elif lower.startswith("*element") and "type=c3d10" in lower:
                    section = "element"
                elif lower.startswith("*surface") and "type=element" in lower:
                    match = re.search(r"name=([^,]+)", line, re.IGNORECASE)
                    current_surface = match.group(1).strip() if match else None
                    section = "surface"
                else:
                    section = None
                continue
            try:
                if section == "node":
                    fields = [field.strip() for field in line.split(",")]
                    if len(fields) != 4:
                        raise ValueError
                    deck_nodes[int(fields[0])] = tuple(float(value) for value in fields[1:4])
                elif section == "element":
                    fields = [field.strip() for field in line.split(",")]
                    volume_elements[int(fields[0])] = tuple(int(value) for value in fields[1:])
                elif section == "surface" and current_surface is not None:
                    fields = [field.strip() for field in line.split(",")]
                    if len(fields) != 2:
                        raise ValueError
                    surfaces.setdefault(current_surface, []).append((int(fields[0]), fields[1].upper()))
            except (TypeError, ValueError) as exc:
                raise StructuralResultIntegrityError("lowered-load provenance cannot parse deck surface geometry") from exc
        entries = surfaces.get(region_id)
        if not entries:
            raise StructuralResultIntegrityError(
                f"lowered-load provenance deck is missing semantic surface {region_id}"
            )
        if not volume_elements or not deck_nodes:
            raise StructuralResultIntegrityError("lowered-load provenance deck has no reconstructible C3D10 mesh")
        try:
            canonical_faces = map_surface_to_volume_faces(mesh, region_id)
        except (DeckBuildError, KeyError) as exc:
            raise StructuralResultIntegrityError(
                "lowered-load provenance cannot reconstruct the trusted semantic region faces"
            ) from exc
        expected_entries = Counter((volume_id, face_key) for _, volume_id, face_key, _ in canonical_faces)
        if Counter(entries) != expected_entries:
            raise StructuralResultIntegrityError(
                "lowered-load provenance deck surface references do not match trusted semantic region faces"
            )
        result = []
        for element_id, face_key in entries:
            element_nodes = volume_elements.get(element_id)
            face_indices = C3D10_LOCAL_FACES.get(face_key)
            if element_nodes is None or face_indices is None or len(element_nodes) != 10:
                raise StructuralResultIntegrityError("lowered-load provenance deck has an invalid C3D10 surface reference")
            face_nodes = tuple(element_nodes[index - 1] for index in face_indices)
            if any(node_id not in deck_nodes or node_id not in mesh.nodes for node_id in face_nodes):
                raise StructuralResultIntegrityError("lowered-load provenance deck surface references an unknown node")
            if any(
                not _vectors_close(deck_nodes[node_id], mesh.nodes[node_id], absolute_tolerance=1e-9)
                for node_id in face_nodes
            ):
                raise StructuralResultIntegrityError("lowered-load provenance deck node coordinates do not match trusted mesh")
            result.append((face_nodes, face_nodes[3:]))
        return result

    def _interpret_case(self, case, mesh, mesh_hash, frd_bytes, dat_bytes, request, definition):
        assessment_nodes = self._assessment_node_ids(mesh, definition, case.load_case_id)
        parsed_frd = (
            self.frd_parser.parse(
                frd_bytes, mesh, requested_result_fields=request.requested_result_fields,
                required_node_ids=assessment_nodes,
            )
            if frd_bytes is not None else None
        )
        displacement = parsed_frd.displacements if parsed_frd else ()
        stress = parsed_frd.stress_samples if parsed_frd else ()
        support_regions = tuple(
            support.target_region_id
            for support in definition.boundary_conditions
            if case.load_case_id in support.applies_to_load_case_ids
        )
        if dat_bytes is not None:
            if not support_regions:
                raise StructuralResultIntegrityError("reaction support domain is empty")
            support_nodes = frozenset(
                node_id
                for region_id in support_regions
                for _element_id, element_nodes in mesh.surface_elements.get(region_id, ())
                for node_id in element_nodes
            )
            reactions = self.dat_parser.parse_reactions(
                dat_bytes, mesh, support_nodes,
                expected_support_set_names=tuple((region_id + "_nodes").upper() for region_id in support_regions),
                required_node_ids=support_nodes,
            )
        else:
            reactions = ()
        region_node_ids = tuple(
            (region_id, tuple(sorted({
                node_id
                for _element_id, element_nodes in mesh.surface_elements.get(region_id, ())
                for node_id in element_nodes
            })))
            for region_id in sorted(mesh.surface_elements)
        )
        max_disp = max(
            ((math.sqrt(sum(value * value for value in sample.vector_mm)), sample) for sample in displacement),
            key=lambda item: item[0], default=None,
        )
        max_stress = max(
            ((von_mises_mpa(sample.tensor_mpa), sample) for sample in stress),
            key=lambda item: item[0], default=None,
        )
        summary = self._reaction_summary(
            mesh, definition, case.load_case_id, reactions, case.lowered_loads, mesh_hash,
        )
        return StructuralLoadCaseResult(
            run_id=case.run_id,
            load_case_id=case.load_case_id,
            mesh_hash=mesh_hash,
            deck_artifact_hash=case.deck_artifact_hash,
            frd_artifact_hash=case.frd_artifact_hash if frd_bytes is not None else None,
            dat_artifact_hash=case.dat_artifact_hash if dat_bytes is not None else None,
            log_artifact_hash=case.log_artifact_hash,
            displacements=tuple(displacement),
            stress_samples=tuple(stress),
            reactions=tuple(reactions),
            requested_result_fields=request.requested_result_fields,
            region_node_ids=region_node_ids,
            maximum_displacement_mm=max_disp[0] if max_disp else None,
            maximum_displacement_node_id=max_disp[1].node_id if max_disp else None,
            maximum_displacement_location_mm=mesh.nodes[max_disp[1].node_id] if max_disp else None,
            maximum_von_mises_stress_mpa=max_stress[0] if max_stress else None,
            maximum_von_mises_stress_node_id=max_stress[1].identity.node_id if max_stress else None,
            **summary,
        )

    @staticmethod
    def _assessment_node_ids(mesh, definition, case_id):
        region_ids = {
            criterion.assessment_region_id
            for criterion in definition.acceptance_criteria
            if criterion.load_case_id == case_id
        }
        if not region_ids:
            return None
        return frozenset(
            node_id
            for region_id in region_ids
            for _element_id, element_nodes in mesh.surface_elements.get(region_id, ())
            for node_id in element_nodes
        )

    def _reaction_summary(self, mesh, definition, case_id, reactions, lowered_loads, mesh_hash):
        if not reactions:
            return {}
        support_regions = tuple(
            support.target_region_id for support in definition.boundary_conditions
            if case_id in support.applies_to_load_case_ids
        )
        support_nodes = tuple(sorted({
            node_id for region_id in support_regions
            for _element_id, element_nodes in mesh.surface_elements.get(region_id, ())
            for node_id in element_nodes
        }))
        if not support_nodes:
            raise StructuralResultIntegrityError("reaction support domain is empty")
        reference = self._surface_centroid(mesh, support_regions)
        total = (0.0, 0.0, 0.0)
        moment = (0.0, 0.0, 0.0)
        for reaction in reactions:
            total = _vector_add(total, reaction.vector_n)
            moment = _vector_add(moment, _cross(
                tuple(mesh.nodes[reaction.node_id][axis] - reference[axis] for axis in range(3)),
                reaction.vector_n,
            ))
        applied_force, applied_moment = self._applied_resultant(
            mesh, case_id, lowered_loads, reference,
        )
        if applied_force is None:
            return {
                "total_reaction_force_n": total,
                "reaction_reference_point_mm": reference,
                "total_reaction_moment_n_mm": moment,
                "equilibrium_status": "unavailable",
                "equilibrium_diagnostic": "lowered_load_provenance_unavailable_for_load_case",
            }
        return {
            "total_reaction_force_n": total,
            "reaction_reference_point_mm": reference,
            "total_reaction_moment_n_mm": moment,
            "applied_force_n": applied_force,
            "applied_moment_n_mm": applied_moment,
            "force_equilibrium_residual_n": _norm(_vector_add(total, applied_force)),
            "moment_equilibrium_residual_n_mm": _norm(_vector_add(moment, applied_moment)),
            "equilibrium_policy_id": EQUILIBRIUM_POLICY_ID,
            "equilibrium_status": "applicable",
            "equilibrium_diagnostic": "lowered_resultant_load_provenance_verified",
        }

    def _applied_resultant(self, mesh, case_id, lowered_loads, reference):
        if not lowered_loads:
            return None, None
        force = (0.0, 0.0, 0.0)
        moment = (0.0, 0.0, 0.0)
        for load in lowered_loads:
            value = load.source_force_vector_n
            force = _vector_add(force, value)
            point = load.source_application_point_mm
            moment = _vector_add(moment, _cross(
                tuple(point[axis] - reference[axis] for axis in range(3)), value,
            ))
        return force, moment

    @staticmethod
    def _surface_centroid(mesh, region_ids):
        total_area = 0.0
        centroid = [0.0, 0.0, 0.0]
        for region_id in region_ids:
            elements = mesh.surface_elements.get(region_id, ())
            if not elements:
                raise StructuralResultIntegrityError(
                    f"mesh physical group is missing structural region {region_id}"
                )
            for _element_id, element_nodes in elements:
                a, b, c = (mesh.nodes[node_id] for node_id in element_nodes[:3])
                ab = tuple(b[index] - a[index] for index in range(3))
                ac = tuple(c[index] - a[index] for index in range(3))
                cross = _cross(ab, ac)
                area = 0.5 * _norm(cross)
                if area <= 0:
                    raise StructuralResultIntegrityError("support surface contains a zero-area element")
                point = tuple((a[index] + b[index] + c[index]) / 3.0 for index in range(3))
                total_area += area
                for index in range(3):
                    centroid[index] += point[index] * area
        if total_area <= 0:
            raise StructuralResultIntegrityError("reaction support domain is empty")
        return tuple(value / total_area for value in centroid)


class StructuralVerificationService:
    """Evaluate canonical criteria over a complete, already trusted result."""

    def evaluate(self, result: StructuralAnalysisResult, definition: StructuralAnalysisDefinition):
        if result.definition_id != definition.id or result.definition_hash != structural_definition_hash(definition):
            raise StructuralResultIntegrityError("result definition binding mismatch")
        if result.source_binding.definition_id != definition.id or result.source_binding.project_id == "":
            raise StructuralResultIntegrityError("result source binding mismatch")
        case_by_id = {case.load_case_id: case for case in result.load_case_results}
        criterion_results = tuple(
            self._evaluate_criterion(criterion, case_by_id.get(criterion.load_case_id), definition)
            for criterion in definition.acceptance_criteria
        )
        statuses = {item.status for item in criterion_results}
        overall = (
            StructuralCriterionStatus.FAIL
            if StructuralCriterionStatus.FAIL in statuses
            else StructuralCriterionStatus.NOT_EVALUABLE
            if not criterion_results or StructuralCriterionStatus.NOT_EVALUABLE in statuses
            else StructuralCriterionStatus.PASS
        )
        raw_hashes = tuple(
            artifact_hash
            for case in result.load_case_results
            for artifact_hash in (
                case.mesh_hash, case.deck_artifact_hash, case.frd_artifact_hash, case.dat_artifact_hash,
                case.log_artifact_hash,
            )
            if artifact_hash is not None
        )
        return __import__("mechcad_harness.structural.models", fromlist=["StructuralVerificationResult"]).StructuralVerificationResult(
            project_id=result.source_binding.project_id,
            source_revision=result.source_binding.source_revision,
            source_state_hash=result.source_binding.source_state_hash,
            definition_id=result.definition_id,
            definition_hash=result.definition_hash,
            request_hash=result.request_hash,
            execution_manifest_hash=result.execution_manifest_hash,
            result_hash=result.result_hash,
            mesh_hash=result.mesh_hash,
            raw_artifact_hashes=raw_hashes or (result.mesh_hash,),
            parser_provenance=result.parser_provenance,
            overall_status=overall,
            criterion_results=criterion_results,
        )

    def _evaluate_criterion(self, criterion: StructuralCriterion, case, definition):
        consumed = (
            "nodal_displacement_magnitude_on_region"
            if criterion.kind == "maximum_displacement"
            else "von_mises_stress_on_region"
        )
        if case is None:
            return StructuralCriterionResult(
                criterion_id=criterion.criterion_id, status=StructuralCriterionStatus.NOT_EVALUABLE,
                reason="missing_load_case_result", consumed_result_field=consumed,
            )
        authority = evaluate_material_authority_policy(
            criterion, definition.material_assignment, definition.material_authority_policy,
        )
        if authority.status != "eligible":
            reason = "missing_material_property" if any(
                rejection.reason == "missing_snapshot" for rejection in authority.rejection_reasons
            ) else "disallowed_material_authority"
            return StructuralCriterionResult(
                criterion_id=criterion.criterion_id, status=StructuralCriterionStatus.NOT_EVALUABLE,
                reason=reason, consumed_result_field=consumed,
            )
        region_nodes = dict(case.region_node_ids).get(criterion.assessment_region_id)
        if not region_nodes:
            return StructuralCriterionResult(
                criterion_id=criterion.criterion_id, status=StructuralCriterionStatus.NOT_EVALUABLE,
                reason="missing_assessment_region", consumed_result_field=consumed,
            )
        if criterion.kind == "maximum_displacement":
            if StructuralResultField.DISPLACEMENT not in case.requested_result_fields:
                return StructuralCriterionResult(
                    criterion_id=criterion.criterion_id, status=StructuralCriterionStatus.NOT_EVALUABLE,
                    reason="result_field_not_requested", consumed_result_field=consumed,
                )
            samples = [
                sample for sample in case.displacements if sample.node_id in region_nodes
            ]
            if not samples:
                return StructuralCriterionResult(
                    criterion_id=criterion.criterion_id, status=StructuralCriterionStatus.NOT_EVALUABLE,
                    reason="missing_result_samples", consumed_result_field=consumed,
                )
            observed = max(_norm(sample.vector_mm) for sample in samples)
            status = StructuralCriterionStatus.PASS if observed <= criterion.maximum_allowed_displacement_mm else StructuralCriterionStatus.FAIL
            return StructuralCriterionResult(
                criterion_id=criterion.criterion_id, status=status,
                consumed_result_field=consumed, observed_value=observed,
                allowable_value=criterion.maximum_allowed_displacement_mm, units="mm",
                reason="" if status is StructuralCriterionStatus.PASS else "maximum_displacement_exceeded",
            )
        if StructuralResultField.VON_MISES_STRESS not in case.requested_result_fields:
            return StructuralCriterionResult(
                criterion_id=criterion.criterion_id, status=StructuralCriterionStatus.NOT_EVALUABLE,
                reason="result_field_not_requested", consumed_result_field=consumed,
            )
        if criterion.stress_sampling != "element_nodal_extrapolated" or any(
            sample.representation is not StressFieldRepresentation.CALCULIX_EXTRAPOLATED_NODAL_STRESS
            for sample in case.stress_samples
        ):
            return StructuralCriterionResult(
                criterion_id=criterion.criterion_id, status=StructuralCriterionStatus.NOT_EVALUABLE,
                reason="unsupported_result_representation", consumed_result_field=consumed,
            )
        if StructuralMaterialPropertyName.YIELD_STRENGTH not in criterion.consumed_material_properties:
            return StructuralCriterionResult(
                criterion_id=criterion.criterion_id, status=StructuralCriterionStatus.NOT_EVALUABLE,
                reason="missing_material_property", consumed_result_field=consumed,
            )
        samples = [sample for sample in case.stress_samples if sample.identity.node_id in region_nodes]
        if not samples:
            return StructuralCriterionResult(
                criterion_id=criterion.criterion_id, status=StructuralCriterionStatus.NOT_EVALUABLE,
                reason="missing_result_samples", consumed_result_field=consumed,
            )
        observed = max(von_mises_mpa(sample.tensor_mpa) for sample in samples)
        yield_snapshot = next(
            (
                snapshot for snapshot in definition.material_assignment.property_snapshot
                if snapshot.property_name is StructuralMaterialPropertyName.YIELD_STRENGTH
            ),
            None,
        )
        if yield_snapshot is None:
            return StructuralCriterionResult(
                criterion_id=criterion.criterion_id, status=StructuralCriterionStatus.NOT_EVALUABLE,
                reason="missing_material_property", consumed_result_field=consumed,
            )
        safety_factor = None if observed <= criterion.zero_stress_tolerance_mpa else yield_snapshot.value / observed
        meets_factor = safety_factor is None or safety_factor >= criterion.minimum_yield_safety_factor
        status = StructuralCriterionStatus.PASS if meets_factor else StructuralCriterionStatus.FAIL
        return StructuralCriterionResult(
            criterion_id=criterion.criterion_id, status=status, consumed_result_field=consumed,
            observed_value=observed, allowable_value=criterion.minimum_yield_safety_factor,
            safety_factor=safety_factor, units="dimensionless",
            reason="" if status is StructuralCriterionStatus.PASS else "yield_safety_factor_below_minimum",
        )


@dataclass(frozen=True)
class StructuralAnalysisEvaluation:
    result: StructuralAnalysisResult
    verification: object
