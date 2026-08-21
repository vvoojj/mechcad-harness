from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.imported_component import (
    ImportedCadComponent,
    ImportedArtifactNotFoundError,
    ImportedArtifactIntegrityError,
    resolve_imported_component,
)


class TestArtifactByteIntegrity:
    def test_artifact_store_existing_verifies_byte_integrity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(tmpdir, project_id="test-project", run_id="test-run")
            
            step_content = b"STEP content"
            artifact = store.publish(
                "ART-test",
                ArtifactType.STEP,
                "test.step",
                step_content,
                "test-producer",
                "1.0",
                1,
                "sha256:" + "b" * 64,
            )
            
            result = store.existing("ART-test")
            assert result is not None
            assert result.sha256 == artifact.sha256
            
            artifact_path = Path(tmpdir) / artifact.relative_path
            actual_hash = f"sha256:{hashlib.sha256(artifact_path.read_bytes()).hexdigest()}"
            assert actual_hash == artifact.sha256

    def test_mutated_step_bytes_fail_integrity_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(tmpdir, project_id="test-project", run_id="test-run")
            
            step_content = b"Original STEP content"
            artifact = store.publish(
                "ART-test",
                ArtifactType.STEP,
                "test.step",
                step_content,
                "test-producer",
                "1.0",
                1,
                "sha256:" + "b" * 64,
            )
            
            artifact_path = Path(tmpdir) / artifact.relative_path
            artifact_path.write_bytes(b"Mutated STEP content")
            
            result = store.existing("ART-test")
            assert result is None

    def test_resolver_fails_on_byte_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(tmpdir, project_id="test-project", run_id="test-run")
            
            step_content = b"Original STEP content"
            artifact = store.publish(
                "ART-test",
                ArtifactType.STEP,
                "test.step",
                step_content,
                "test-producer",
                "1.0",
                1,
                "sha256:" + "b" * 64,
            )
            
            artifact_path = Path(tmpdir) / artifact.relative_path
            artifact_path.write_bytes(b"Mutated STEP content")
            
            with pytest.raises(ImportedArtifactNotFoundError):
                resolve_imported_component(
                    artifact_id="ART-test",
                    artifact_hash=artifact.sha256,
                    store=store,
                    component_id="gear-1",
                )


class TestCallerCannotForgeProvenance:
    def test_source_provenance_derived_from_artifact_not_caller(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(tmpdir, project_id="test-project", run_id="test-run")
            
            step_content = b"STEP content"
            artifact = store.publish(
                "ART-test",
                ArtifactType.STEP,
                "test.step",
                step_content,
                "test-producer",
                "1.0",
                42,
                "sha256:" + "c" * 64,
            )
            
            comp = resolve_imported_component(
                artifact_id="ART-test",
                artifact_hash=artifact.sha256,
                store=store,
                component_id="gear-1",
            )
            
            assert comp.source_revision == 42
            assert comp.source_state_hash == "sha256:" + "c" * 64

    def test_resolver_rejects_wrong_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(tmpdir, project_id="test-project", run_id="test-run")
            
            step_content = b"STEP content"
            artifact = store.publish(
                "ART-test",
                ArtifactType.STEP,
                "test.step",
                step_content,
                "test-producer",
                "1.0",
                1,
                "sha256:" + "b" * 64,
            )
            
            with pytest.raises(ImportedArtifactIntegrityError):
                resolve_imported_component(
                    artifact_id="ART-test",
                    artifact_hash="sha256:" + "d" * 64,
                    store=store,
                    component_id="gear-1",
                )


class TestProductionApplicationTrust:
    def test_build_assembly_uses_application_workspace(self):
        from mechcad_harness.application import ProductionApplication
        from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance
        from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
        from mechcad_harness.imported_component import ImportedCadComponent
        from mechcad_harness.agents.fake import FakeAgentAdapter
        from mechcad_harness.agents.models import AgentIdentity
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ownership_path = Path(tmpdir) / "ownership.yaml"
            ownership_path.write_text("owners:\n  - path: /\n    owner: test\n")
            dependency_path = Path(tmpdir) / "dependencies.yaml"
            dependency_path.write_text("rules: []\n")
            
            identity = AgentIdentity(
                agent_name="test-agent",
                agent_version="1.0",
                role="test",
                protocol_version="1.0",
            )
            adapter = FakeAgentAdapter(identity)
            app = ProductionApplication.create(
                workspace=tmpdir,
                project_id="test-project",
                agent_adapter=adapter,
                ownership_path=ownership_path,
                dependency_path=dependency_path,
            )
            
            assert str(app.state_manager.workspace) == tmpdir
