from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.imported_component import (
    ImportedCadComponent,
    ImportedArtifactNotFoundError,
    ImportedArtifactIntegrityError,
    UnsupportedImportedFormatError,
    imported_component_hash,
    resolve_imported_component,
)


class TestImportedCadComponent:
    def test_basic_creation(self):
        comp = ImportedCadComponent(
            component_id="gear-1",
            artifact_id="ART-abc123",
            artifact_hash="sha256:" + "a" * 64,
            format="step",
            source_revision=5,
            source_state_hash="sha256:" + "b" * 64,
        )
        assert comp.component_id == "gear-1"
        assert comp.artifact_id == "ART-abc123"
        assert comp.format == "step"
        assert comp.source_revision == 5

    def test_invalid_artifact_hash_format(self):
        with pytest.raises(ValueError, match="artifact_hash must be a sha256 hash"):
            ImportedCadComponent(
                component_id="gear-1",
                artifact_id="ART-abc123",
                artifact_hash="md5:" + "a" * 32,
                format="step",
                source_revision=5,
                source_state_hash="sha256:" + "b" * 64,
            )

    def test_invalid_source_state_hash_format(self):
        with pytest.raises(ValueError, match="source_state_hash must be a sha256 hash"):
            ImportedCadComponent(
                component_id="gear-1",
                artifact_id="ART-abc123",
                artifact_hash="sha256:" + "a" * 64,
                format="step",
                source_revision=5,
                source_state_hash="invalid",
            )

    def test_empty_component_id(self):
        with pytest.raises(ValueError):
            ImportedCadComponent(
                component_id="",
                artifact_id="ART-abc123",
                artifact_hash="sha256:" + "a" * 64,
                format="step",
                source_revision=5,
                source_state_hash="sha256:" + "b" * 64,
            )

    def test_zero_revision(self):
        with pytest.raises(ValueError):
            ImportedCadComponent(
                component_id="gear-1",
                artifact_id="ART-abc123",
                artifact_hash="sha256:" + "a" * 64,
                format="step",
                source_revision=0,
                source_state_hash="sha256:" + "b" * 64,
            )


class TestImportedComponentHash:
    def test_deterministic_hash(self):
        comp1 = ImportedCadComponent(
            component_id="gear-1",
            artifact_id="ART-abc123",
            artifact_hash="sha256:" + "a" * 64,
            format="step",
            source_revision=5,
            source_state_hash="sha256:" + "b" * 64,
        )
        comp2 = ImportedCadComponent(
            component_id="gear-1",
            artifact_id="ART-abc123",
            artifact_hash="sha256:" + "a" * 64,
            format="step",
            source_revision=5,
            source_state_hash="sha256:" + "b" * 64,
        )
        assert imported_component_hash(comp1) == imported_component_hash(comp2)

    def test_different_artifact_hash_changes_identity(self):
        comp1 = ImportedCadComponent(
            component_id="gear-1",
            artifact_id="ART-abc123",
            artifact_hash="sha256:" + "a" * 64,
            format="step",
            source_revision=5,
            source_state_hash="sha256:" + "b" * 64,
        )
        comp2 = ImportedCadComponent(
            component_id="gear-1",
            artifact_id="ART-abc123",
            artifact_hash="sha256:" + "c" * 64,
            format="step",
            source_revision=5,
            source_state_hash="sha256:" + "b" * 64,
        )
        assert imported_component_hash(comp1) != imported_component_hash(comp2)


class TestResolveImportedComponent:
    def test_successful_resolution(self):
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
                5,
                "sha256:" + "b" * 64,
            )
            
            comp = resolve_imported_component(
                artifact_id="ART-test",
                artifact_hash=artifact.sha256,
                store=store,
                component_id="gear-1",
            )
            
            assert comp.component_id == "gear-1"
            assert comp.artifact_id == "ART-test"
            assert comp.artifact_hash == artifact.sha256
            assert comp.source_revision == 5
            assert comp.source_state_hash == "sha256:" + "b" * 64

    def test_missing_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(tmpdir, project_id="test-project", run_id="test-run")
            
            with pytest.raises(ImportedArtifactNotFoundError):
                resolve_imported_component(
                    artifact_id="ART-nonexistent",
                    artifact_hash="sha256:" + "a" * 64,
                    store=store,
                    component_id="gear-1",
                )

    def test_hash_mismatch(self):
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
                    artifact_hash="sha256:" + "c" * 64,
                    store=store,
                    component_id="gear-1",
                )

    def test_unsupported_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(tmpdir, project_id="test-project", run_id="test-run")
            
            stl_content = b"STL content"
            artifact = store.publish(
                "ART-test",
                ArtifactType.STL,
                "test.stl",
                stl_content,
                "test-producer",
                "1.0",
                1,
                "sha256:" + "b" * 64,
            )
            
            with pytest.raises(UnsupportedImportedFormatError):
                resolve_imported_component(
                    artifact_id="ART-test",
                    artifact_hash=artifact.sha256,
                    store=store,
                    component_id="gear-1",
                )

    def test_source_provenance_derived_from_artifact(self):
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
