from __future__ import annotations

from pathlib import Path

from mechcad_harness.backends.models import BackendIdentity, BackendProvenance
from mechcad_harness.structural.deck import StructuralDeckBuilder
from mechcad_harness.structural.geometry import (
    FaceDescriptor,
    GeometryRealization,
    StructuralFreeCADGeometryAdapter,
    StructuralRegionResolver,
    _resolve_one,
)
from mechcad_harness.structural.mesh import ParsedMesh, StructuralGmshMeshingProvider
from mechcad_harness.structural.models import (
    GMSH_PROVIDER_IDENTITY,
    PhysicalGroupBinding,
    ResolvedRegionMap,
    StructuralMeshManifest,
    region_map_hash,
    resolved_region_hash,
)
from mechcad_harness.structural.preflight import ConstraintPreflight
from mechcad_harness.structural.solver import SolverRunResult, StructuralCalculiXSolverProvider
from mechcad_harness.structural.runtime import DiscoveredRuntime

FAKE_FREECAD_IDENTITY = BackendIdentity(
    name="fake-freecad-geometry", adapter_version="fake-freecad-geometry@0",
    library_name="FakeCAD", capabilities=("cad.geometry",))
FAKE_GMSH_IDENTITY = BackendIdentity(
    name="fake-gmsh", adapter_version="fake-gmsh@0", library_name="FakeGmsh", capabilities=("mesh.c3d10",))
FAKE_CALCULIX_IDENTITY = BackendIdentity(
    name="fake-calculix", adapter_version="fake-calculix@0", library_name="FakeCalculiX", capabilities=("solve.c3d10",))


class FakeDiscoveredRuntime(DiscoveredRuntime):
    def require_available(self) -> "FakeDiscoveredRuntime":
        return self


def _fake_provenance(identity: BackendIdentity) -> BackendProvenance:
    return BackendProvenance(
        backend_name=identity.name, backend_adapter_version=identity.adapter_version,
        library_name=identity.library_name, library_version="fake")


class FakeStructuralFreeCADGeometryAdapter(StructuralFreeCADGeometryAdapter):
    identity = "fake-structural-region-resolver@0"

    def __init__(self, *, solid_count: int = 1, shape_valid: bool = True):
        self._solid_count = solid_count
        self._shape_valid = shape_valid
        self._discovery = FakeDiscoveredRuntime(True, None, "fake", FAKE_FREECAD_IDENTITY,
                                                _fake_provenance(FAKE_FREECAD_IDENTITY))

    def realize_geometry(self, step_path) -> GeometryRealization:
        faces = [
            FaceDescriptor(area=200.0, centroid=(0.0, 10.0, 5.0), normal=(-1.0, 0.0, 0.0),
                          bbox=(0, 0, 0, 0, 20, 10), planarity=0.0),
            FaceDescriptor(area=200.0, centroid=(100.0, 10.0, 5.0), normal=(1.0, 0.0, 0.0),
                          bbox=(100, 0, 0, 100, 20, 10), planarity=0.0),
            FaceDescriptor(area=1000.0, centroid=(50.0, 0.0, 5.0), normal=(0.0, -1.0, 0.0),
                          bbox=(0, 0, 0, 100, 0, 10), planarity=0.0),
            FaceDescriptor(area=1000.0, centroid=(50.0, 20.0, 5.0), normal=(0.0, 1.0, 0.0),
                          bbox=(0, 20, 0, 100, 20, 10), planarity=0.0),
            FaceDescriptor(area=2000.0, centroid=(50.0, 10.0, 0.0), normal=(0.0, 0.0, -1.0),
                          bbox=(0, 0, 0, 100, 20, 0), planarity=0.0),
            FaceDescriptor(area=2000.0, centroid=(50.0, 10.0, 10.0), normal=(0.0, 0.0, 1.0),
                          bbox=(0, 0, 10, 100, 20, 10), planarity=0.0),
        ]
        return GeometryRealization(shape_valid=self._shape_valid, solid_count=self._solid_count, faces=faces)


class FakeStructuralRegionResolver(StructuralRegionResolver):
    identity = "fake-structural-region-resolver@0"
    resolver_version = "0"

    def __init__(self, tolerances=None):
        if tolerances is None:
            super().__init__()
        else:
            super().__init__(tolerances)

    def resolve(self, regions, realization, *, source_geometry_hash: str) -> ResolvedRegionMap:
        if realization.solid_count != 1:
            from mechcad_harness.structural.geometry import RegionResolutionError
            raise RegionResolutionError("fake: expected one solid")
        resolved = []
        for region in regions:
            r = _resolve_one(region, realization.faces, self._tolerances)
            r = r.model_copy(update={"source_geometry_hash": source_geometry_hash,
                                      "region_realization_hash": resolved_region_hash(r.model_copy(update={"source_geometry_hash": source_geometry_hash}))})
            resolved.append(r)
        rmap = ResolvedRegionMap(
            source_geometry_hash=source_geometry_hash, resolver_identity=self.identity,
            resolver_version=self.resolver_version, match_policy_id=self._tolerances.policy_id,
            regions=tuple(resolved), region_map_hash="pending")
        return rmap.model_copy(update={"region_map_hash": region_map_hash(rmap.regions,
                             source_geometry_hash=source_geometry_hash, match_policy_id=self._tolerances.policy_id)})


class FakeStructuralGmshMeshingProvider(StructuralGmshMeshingProvider):
    identity = "fake-gmsh@0"
    provider_version = "0"

    def __init__(self, *, element_family: str = "c3d10", fail: bool = False):
        self._discovery = FakeDiscoveredRuntime(True, None, "fake", FAKE_GMSH_IDENTITY,
                                                _fake_provenance(FAKE_GMSH_IDENTITY))
        self._fail = fail
        self._element_family = element_family

    def mesh(self, step_path, region_map, *, mesh_spec_hash: str, target_size_mm=None, element_family: str = "c3d10"):
        if self._fail:
            from mechcad_harness.structural.mesh import MeshProviderError
            raise MeshProviderError("fake gmsh failure")
        nodes = {
            1: (0.0, 0.0, 0.0), 2: (10.0, 0.0, 0.0), 3: (0.0, 10.0, 0.0), 4: (0.0, 0.0, 10.0),
            5: (5.0, 0.0, 0.0), 6: (5.0, 5.0, 0.0), 7: (0.0, 5.0, 0.0), 8: (0.0, 0.0, 5.0),
            9: (5.0, 0.0, 5.0), 10: (0.0, 5.0, 5.0),
        }
        c3d10 = {1: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)}
        surface_elements = {
            "fixed": [(1, (1, 3, 2, 7, 6, 5))],
            "free": [(2, (1, 2, 4, 5, 9, 8))],
        }
        regions = region_map.regions if region_map is not None else ()
        groups = tuple(
            PhysicalGroupBinding(
                semantic_region_id=region.region_id,
                physical_group_name=region.region_id,
                gmsh_entity_dim=2,
                gmsh_entity_id=index,
            )
            for index, region in enumerate(regions, start=1)
        ) + (PhysicalGroupBinding(
            semantic_region_id=None, physical_group_name="volume", gmsh_entity_dim=3, gmsh_entity_id=1,
        ),)
        parsed = ParsedMesh(nodes=nodes, c3d10=c3d10, surface_elements=surface_elements,
                            volume_elset_name="volume", physical_groups=groups, mesh_bytes=b"MSH")
        manifest = StructuralMeshManifest(
            mesh_specification_hash=mesh_spec_hash, gmsh_identity=FAKE_GMSH_IDENTITY.name,
            gmsh_version="fake", element_family=element_family, node_count=len(nodes),
            volume_element_count=len(c3d10), boundary_element_count=2, volume_entity_id=1,
            physical_groups=groups,
            mesh_hash="sha256:" + __import__("hashlib").sha256(b"MSH").hexdigest(),
             region_map_hash=region_map.region_map_hash if region_map is not None else "")
        return parsed, manifest, b"MSH"


class FakeStructuralDeckBuilder(StructuralDeckBuilder):
    identity = "fake-deck-builder@0"
    builder_version = "0"

    def __init__(self):
        super().__init__()


def _fake_frd_bytes() -> bytes:
    def number(value):
        return f"{value: .5E}"

    lines = [
        "    1C",
        "    1UMechCAD structural linear-static deck",
        "    1UPGM               CalculiX",
        "    1UVERSION           Version 2.22",
        f"    2C{' ' * 27}{10:3d}{' ' * 37}1",
    ]
    for node_id in range(1, 11):
        lines.append(" -1" + f"{node_id:10d}" + number(0.0) * 3)
    lines.append(" -3")
    lines.extend((
        "    1PSTEP" + " " * 25 + "1" + " " * 11 + "1" + " " * 11 + "1" + " " * 10,
        "  100CL  101 1.000000000" + " " * 9 + f"{10:3d}" + " " * 21 + "0" + " " * 4 + "1" + " " * 11 + "1",
        " -4  DISP        4    1",
        " -5  D1          1    2    1    0",
        " -5  D2          1    2    2    0",
        " -5  D3          1    2    3    0",
        " -5  ALL         1    2    0    0    1ALL",
    ))
    for node_id in range(1, 11):
        lines.append(" -1" + f"{node_id:10d}" + number(0.0) * 3)
    lines.append(" -3")
    lines.extend((
        "    1PSTEP" + " " * 25 + "2" + " " * 11 + "1" + " " * 11 + "1" + " " * 10,
        "  100CL  101 1.000000000" + " " * 9 + f"{10:3d}" + " " * 21 + "0" + " " * 4 + "1" + " " * 11 + "1",
        " -4  STRESS      6    1",
        " -5  SXX         1    4    1    1",
        " -5  SYY         1    4    2    2",
        " -5  SZZ         1    4    3    3",
        " -5  SXY         1    4    1    2",
        " -5  SYZ         1    4    2    3",
        " -5  SZX         1    4    3    1",
    ))
    for node_id in range(1, 11):
        lines.append(" -1" + f"{node_id:10d}" + "".join(number(value) for value in (1, 2, 3, 4, 5, 6)))
    lines.extend((" -3", " 9999"))
    return ("\n".join(lines) + "\n").encode("ascii")


def _fake_dat_bytes() -> bytes:
    lines = [" forces (fx,fy,fz) for set FIXED_NODES and time  0.1000000E+01", ""]
    for node_id in (1, 2, 3, 5, 6, 7):
        lines.append(f"{node_id:10d}" + f"{0.0:14.6E}" * 3)
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


class FakeStructuralCalculiXSolverProvider(StructuralCalculiXSolverProvider):
    identity = "fake-calculix@0"
    provider_version = "0"

    def __init__(self, *, status="succeeded", exit_code: int = 0, job_finished: bool = True,
                 produce_frd: bool = True, produce_dat: bool = True, fail_on_call: int | None = None):
        self._discovery = FakeDiscoveredRuntime(True, None, "fake", FAKE_CALCULIX_IDENTITY,
                                                _fake_provenance(FAKE_CALCULIX_IDENTITY))
        self._status = status
        self._exit_code = exit_code
        self._job_finished = job_finished
        self._produce_frd = produce_frd
        self._produce_dat = produce_dat
        self._fail_on_call = fail_on_call
        self.calls = 0

    def execute(self, deck_text: str) -> SolverRunResult:
        from mechcad_harness.structural.models import StructuralSolverManifest
        self.calls += 1
        if self._fail_on_call == self.calls:
            return SolverRunResult(
                manifest=StructuralSolverManifest(
                    calculix_identity=self.identity, calculix_version="fake",
                    backend_provenance=self._discovery.provenance,
                    exit_code=201, job_finished=True, produced_log=True,
                    solver_message=f"fake solver failure on call {self.calls}"),
                log_text=f"fake solver failure on call {self.calls}", frd_bytes=None, dat_bytes=None)
        if self._status == "unavailable":
            return SolverRunResult(
                manifest=StructuralSolverManifest(
                    calculix_identity=self.identity, calculix_version="fake",
                    backend_provenance=self._discovery.provenance,
                    exit_code=None, job_finished=False, produced_log=True),
                log_text="fake solver unavailable", frd_bytes=None, dat_bytes=None)
        return SolverRunResult(
            manifest=StructuralSolverManifest(
                calculix_identity=self.identity, calculix_version="fake",
                backend_provenance=self._discovery.provenance,
                exit_code=self._exit_code, job_finished=self._job_finished,
                produced_frd=self._produce_frd, produced_dat=self._produce_dat, produced_log=True,
                solver_message="fake job finished" if self._job_finished else "fake failed"),
            log_text=f"fake solver log {self.calls}",
            frd_bytes=_fake_frd_bytes() if self._produce_frd else None,
            dat_bytes=_fake_dat_bytes() if self._produce_dat else None)
