from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mechcad_harness.backends.provenance import provenance_from_identity
from mechcad_harness.backends.models import BackendIdentity, BackendProvenance

FREECAD_BIN_DIR_ENV = "MECHCAD_FREECAD_BIN_DIR"
FREECADCMD_ENV = "MECHCAD_FREECADCMD"
GMSH_ENV = "MECHCAD_GMSH"
CCX_ENV = "MECHCAD_CCX"

# Validated trusted runtime identities.  Provider/backend identity is owned by
# composition, never supplied by agents or callers.
FREECAD_IDENTITY = BackendIdentity(
    name="freecad",
    adapter_version="mechcad-freecad@2.1",
    library_name="FreeCAD",
    library_version="1.1.3",
    library_source="bundled",
    library_revision="freecad-1.1.3-bundled",
    capabilities=("cad.geometry", "cad.step"),
)

GMSH_IDENTITY = BackendIdentity(
    name="gmsh",
    adapter_version="mechcad-structural-gmsh@1",
    library_name="Gmsh",
    library_version="4.15.0",
    library_source="bundled",
    library_revision="gmsh-4.15.0-bundled",
    capabilities=("mesh.occ", "mesh.c3d10"),
)

CALCULIX_IDENTITY = BackendIdentity(
    name="calculix",
    adapter_version="mechcad-structural-calculix@1",
    library_name="CalculiX",
    library_version="2.22",
    library_source="bundled",
    library_revision="calculix-2.22-bundled",
    capabilities=("solve.linear_static", "solve.c3d10"),
)


class RuntimeUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class DiscoveredRuntime:
    available: bool
    executable: str | None
    version: str | None
    identity: BackendIdentity
    provenance: BackendProvenance | None = None

    def require_available(self) -> "DiscoveredRuntime":
        if not self.available or self.executable is None:
            raise RuntimeUnavailableError(f"{self.identity.name} runtime is unavailable")
        return self


def _validate_freecad_bin_dir(directory: str) -> str | None:
    candidate = Path(directory) / "freecadcmd.exe" if os.name == "nt" else Path(directory) / "freecadcmd"
    if candidate.is_file():
        return str(candidate)
    candidate = Path(directory) / "FreeCADCmd"
    if candidate.is_file():
        return str(candidate)
    return None


def discover_freecad() -> DiscoveredRuntime:
    configured = os.environ.get(FREECADCMD_ENV)
    if configured and Path(configured).is_file():
        return _runtime_for_executable(
            configured, FREECAD_IDENTITY,
            _probe_version(configured, ("--version",), r"FreeCAD\s+([0-9]+\.[0-9]+\.[0-9]+)")
        )
    bin_dir = os.environ.get(FREECAD_BIN_DIR_ENV)
    if bin_dir:
        exe = _validate_freecad_bin_dir(bin_dir)
        if exe:
            return _runtime_for_executable(
                exe, FREECAD_IDENTITY,
                _probe_version(exe, ("--version",), r"FreeCAD\s+([0-9]+\.[0-9]+\.[0-9]+)")
            )
    found = shutil.which("FreeCADCmd") or shutil.which("freecadcmd") or shutil.which("FreeCAD")
    if found:
        return _runtime_for_executable(
            found, FREECAD_IDENTITY,
            _probe_version(found, ("--version",), r"FreeCAD\s+([0-9]+\.[0-9]+\.[0-9]+)")
        )
    return DiscoveredRuntime(False, None, None, FREECAD_IDENTITY, None)


def _version_probe(executable: str, *, flag: str, prefix: str) -> str | None:
    try:
        with tempfile.TemporaryDirectory(prefix="mechcad-rt-ver-") as directory:
            result = subprocess.run([executable, flag], cwd=directory, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines() + result.stderr.splitlines():
        if line.strip().startswith(prefix):
            return line.strip().removeprefix(prefix).strip()
    return None


def _probe_version(executable: str, flags: tuple[str, ...], pattern: str) -> str | None:
    for flag in flags:
        with tempfile.TemporaryDirectory(prefix="mechcad-rt-probe-") as directory:
            try:
                result = subprocess.run(
                    [executable, flag],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                continue
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _runtime_for_executable(
    executable: str, identity: BackendIdentity, observed_version: str | None
) -> DiscoveredRuntime:
    compatible = observed_version == identity.library_version
    provenance = (
        provenance_from_identity(identity, library_version=observed_version)
        if compatible and observed_version is not None
        else None
    )
    return DiscoveredRuntime(
        compatible, executable, observed_version, identity, provenance
    )


def discover_gmsh() -> DiscoveredRuntime:
    configured = os.environ.get(GMSH_ENV)
    if configured and Path(configured).is_file():
        return _runtime_for_executable(
            configured,
            GMSH_IDENTITY,
            _probe_version(
                configured,
                ("--version", "-version"),
                r"(?:Gmsh\s+)?(?:version\s+)?([0-9]+\.[0-9]+\.[0-9]+)",
            ),
        )
    if configured:
        return DiscoveredRuntime(False, configured, None, GMSH_IDENTITY, None)
    return DiscoveredRuntime(False, None, None, GMSH_IDENTITY, None)


def discover_calculix() -> DiscoveredRuntime:
    configured = os.environ.get(CCX_ENV)
    if configured and Path(configured).is_file():
        return _runtime_for_executable(
            configured, CALCULIX_IDENTITY,
            _probe_version(configured, ("-v", "--version"), r"version\s+([0-9]+\.[0-9]+)")
        )
    bin_dir = os.environ.get(FREECAD_BIN_DIR_ENV)
    if bin_dir:
        candidate = Path(bin_dir) / ("ccx.exe" if os.name == "nt" else "ccx")
        if candidate.is_file():
            return _runtime_for_executable(
                str(candidate), CALCULIX_IDENTITY,
                _probe_version(str(candidate), ("-v", "--version"), r"version\s+([0-9]+\.[0-9]+)")
            )
    found = shutil.which("ccx")
    if found:
        return _runtime_for_executable(
            found, CALCULIX_IDENTITY,
            _probe_version(found, ("-v", "--version"), r"version\s+([0-9]+\.[0-9]+)")
        )
    return DiscoveredRuntime(False, None, None, CALCULIX_IDENTITY, None)
