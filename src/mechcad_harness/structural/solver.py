from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mechcad_harness.structural.models import CALCULIX_PROVIDER_IDENTITY, StructuralSolverManifest
from mechcad_harness.structural.runtime import DiscoveredRuntime

CALCULIX_PROVIDER_VERSION = "1"


class CalculiXSolverError(Exception):
    pass


@dataclass
class SolverRunResult:
    manifest: StructuralSolverManifest
    log_text: str
    frd_bytes: bytes | None
    dat_bytes: bytes | None


class StructuralCalculiXSolverProvider:
    identity = CALCULIX_PROVIDER_IDENTITY
    provider_version = CALCULIX_PROVIDER_VERSION

    def __init__(self, discovery: DiscoveredRuntime, *, timeout_seconds: float = 600.0):
        self._discovery = discovery
        self._timeout = timeout_seconds

    def execute(self, deck_text: str) -> SolverRunResult:
        discovery = self._discovery.require_available()
        with tempfile.TemporaryDirectory(prefix="mechcad-ccx-") as directory:
            cwd = Path(directory)
            job = "struct_job"
            inp_path = cwd / f"{job}.inp"
            inp_path.write_text(deck_text, encoding="ascii")
            try:
                result = subprocess.run([discovery.executable, job], cwd=cwd, capture_output=True,
                                         text=True, timeout=self._timeout, check=False)
            except FileNotFoundError as exc:
                return SolverRunResult(
                    manifest=StructuralSolverManifest(
                        calculix_identity=self.identity,
                        calculix_version=discovery.version or "unknown",
                        backend_provenance=discovery.provenance,
                        exit_code=None, job_finished=False, produced_log=True),
                    log_text=f"calculix launch failed: {exc}", frd_bytes=None, dat_bytes=None)
            except subprocess.TimeoutExpired as exc:
                return SolverRunResult(
                    manifest=StructuralSolverManifest(
                        calculix_identity=self.identity,
                        calculix_version=discovery.version or "unknown",
                        backend_provenance=discovery.provenance,
                        exit_code=None, job_finished=False, produced_log=True),
                    log_text=f"calculix timed out after {self._timeout}s", frd_bytes=None, dat_bytes=None)
            log_text = (result.stdout or "") + (result.stderr or "")
            frd_bytes = (cwd / f"{job}.frd").read_bytes() if (cwd / f"{job}.frd").is_file() else None
            dat_bytes = (cwd / f"{job}.dat").read_bytes() if (cwd / f"{job}.dat").is_file() else None
            job_finished = "Job finished" in (result.stdout or "")
            produced_frd = frd_bytes is not None
            produced_dat = dat_bytes is not None
            manifest = StructuralSolverManifest(
                calculix_identity=self.identity,
                calculix_version=discovery.version or "unknown",
                backend_provenance=discovery.provenance,
                exit_code=result.returncode,
                job_finished=job_finished,
                produced_frd=produced_frd,
                produced_dat=produced_dat,
                produced_log=bool(log_text.strip()),
                solver_message=(result.stdout or "").strip()[-2000:],
            )
            return SolverRunResult(manifest=manifest, log_text=log_text, frd_bytes=frd_bytes, dat_bytes=dat_bytes)
