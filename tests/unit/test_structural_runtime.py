from __future__ import annotations

import subprocess

from mechcad_harness.structural.runtime import (
    FREECAD_IDENTITY,
    discover_calculix,
    discover_freecad,
    discover_gmsh,
)


def _configured_gmsh(monkeypatch):
    executable = r"C:\fake\gmsh.exe"
    monkeypatch.setenv("MECHCAD_GMSH", executable)
    monkeypatch.delenv("MECHCAD_FREECAD_BIN_DIR", raising=False)
    monkeypatch.setattr(
        "mechcad_harness.structural.runtime.Path.is_file",
        lambda _path: True,
    )
    return executable


def test_gmsh_discovery_rejects_probe_failure_without_fallback(monkeypatch):
    executable = _configured_gmsh(monkeypatch)
    monkeypatch.setattr(
        "mechcad_harness.structural.runtime.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 1, stdout="", stderr="probe failed"
        ),
    )
    monkeypatch.setattr("mechcad_harness.structural.runtime.shutil.which", lambda _name: None)

    discovery = discover_gmsh()

    assert discovery.available is False
    assert discovery.executable == executable
    assert discovery.version is None
    assert discovery.provenance is None


def test_gmsh_discovery_rejects_observed_version_mismatch(monkeypatch):
    executable = _configured_gmsh(monkeypatch)
    monkeypatch.setattr(
        "mechcad_harness.structural.runtime.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 0, stdout="Version 4.14.0\n", stderr=""
        ),
    )

    discovery = discover_gmsh()

    assert discovery.available is False
    assert discovery.executable == executable
    assert discovery.version == "4.14.0"
    assert discovery.provenance is None


def test_gmsh_discovery_accepts_only_observed_expected_version(monkeypatch):
    executable = _configured_gmsh(monkeypatch)
    calls = []

    def run(*args, **kwargs):
        calls.append(args[0])
        return subprocess.CompletedProcess(args, 0, stdout="4.15.0\n", stderr="")

    monkeypatch.setattr("mechcad_harness.structural.runtime.subprocess.run", run)

    discovery = discover_gmsh()

    assert discovery.available is True
    assert discovery.executable == executable
    assert discovery.version == "4.15.0"
    assert discovery.provenance is not None
    assert discovery.provenance.library_version == "4.15.0"
    assert discovery.provenance.library_source == "bundled"
    assert discovery.provenance.library_revision == "gmsh-4.15.0-bundled"
    assert calls
    assert calls[0][0] == executable


def test_freecad_discovery_rejects_executable_that_reports_untrusted_version(monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", r"C:\fake\freecadcmd.exe")
    monkeypatch.setattr(
        "mechcad_harness.structural.runtime.Path.is_file",
        lambda _path: True,
    )
    monkeypatch.setattr(
        "mechcad_harness.structural.runtime.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 0, stdout="FreeCAD 0.21.2\n", stderr=""
        ),
    )

    discovery = discover_freecad()

    assert discovery.available is False
    assert discovery.executable == r"C:\fake\freecadcmd.exe"
    assert discovery.version == "0.21.2"
    assert discovery.provenance is None


def test_calculix_discovery_rejects_forged_executable_version(monkeypatch):
    monkeypatch.setenv("MECHCAD_CCX", r"C:\fake\ccx.exe")
    monkeypatch.setattr(
        "mechcad_harness.structural.runtime.Path.is_file",
        lambda _path: True,
    )
    monkeypatch.setattr(
        "mechcad_harness.structural.runtime.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 0, stdout="This is Version 9.99\n", stderr=""
        ),
    )

    discovery = discover_calculix()

    assert discovery.available is False
    assert discovery.executable == r"C:\fake\ccx.exe"
    assert discovery.version == "9.99"
    assert discovery.provenance is None


def test_trusted_freecad_identity_requires_complete_library_provenance():
    assert FREECAD_IDENTITY.library_source == "bundled"
    assert FREECAD_IDENTITY.library_revision == "freecad-1.1.3-bundled"
