"""B0 hard gate: read-only H1-B storage compatibility verification.

Runs BEFORE any production ``DesignState`` schema or hashing modification. It
proves, over every historical revision and current pointer found in the
repository workspaces, that the accepted ``state-hash@2`` projection is
byte-identical to the frozen ``state-hash@1`` projection and to the stored hash
for every currently-loadable state, and that the planned
``ADD /joint_authority_declarations/<id>`` mutation is valid.

This test is strictly read-only with respect to the workspace: it never writes a
revision, pointer, manifest, or evidence record. It writes only its own evidence
report under the isolated design package.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.models import DesignState
from mechcad_harness.state import RevisionSnapshot
from mechcad_harness.changes import (
    ChangeConflictError,
    ChangeOperation,
    InvalidChangePathError,
    OperationType,
    apply_operation,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = (
    REPO_ROOT
    / ".verification-runs"
    / "h1b-trusted-joint-authority-design-20261008-3da666f43be2"
    / "B0_EVIDENCE.json"
)


def _sha256(payload: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _projection_v1(state_dict: dict) -> dict:
    payload = dict(state_dict)
    payload.pop("joint_authority_declarations", None)
    return payload


def _projection_v2(state_dict: dict) -> dict:
    payload = dict(state_dict)
    if not payload.get("joint_authority_declarations"):
        payload.pop("joint_authority_declarations", None)
    return payload


def _discover_workspaces() -> list[Path]:
    roots: set[Path] = set()
    for rev_dir in REPO_ROOT.rglob("revisions"):
        if rev_dir.is_dir() and any(rev_dir.glob("REV-*.json")):
            roots.add(rev_dir.parent)
    return sorted(roots)


def _load_snapshot(path: Path) -> RevisionSnapshot:
    return RevisionSnapshot.model_validate_json(path.read_text(encoding="utf-8"))


def test_b0_storage_compatibility() -> None:
    workspaces = _discover_workspaces()
    assert workspaces, "no workspaces with revisions discovered"

    revision_rows: list[dict] = []
    pointer_rows: list[dict] = []
    projection_mismatches: list[str] = []
    preexisting_unloadable: list[str] = []
    loadable_mismatches: list[str] = []

    for workspace in workspaces:
        for rev_path in sorted((workspace / "revisions").glob("REV-*.json")):
            snapshot = _load_snapshot(rev_path)
            state_dict = snapshot.state.model_dump(mode="json")
            h1 = _sha256(_projection_v1(state_dict))
            h2 = _sha256(_projection_v2(state_dict))
            stored = snapshot.state_hash
            label = f"{snapshot.project_id}:{snapshot.revision}"
            if h1 != h2:
                projection_mismatches.append(label)
            row = {
                "workspace": str(workspace.relative_to(REPO_ROOT)),
                "project_id": snapshot.project_id,
                "revision": snapshot.revision,
                "schema_version": snapshot.schema_version,
                "stored": stored,
                "state_hash_v1": h1,
                "state_hash_v2": h2,
                "v1_eq_v2": h1 == h2,
                "v1_eq_stored": h1 == stored,
                "v2_eq_stored": h2 == stored,
            }
            revision_rows.append(row)
            if h1 != stored:
                preexisting_unloadable.append(label)
            elif h2 != stored:
                loadable_mismatches.append(label)

        current_path = workspace / "current.json"
        if current_path.is_file():
            pointer = json.loads(current_path.read_text(encoding="utf-8"))
            snapshot = _load_snapshot(
                workspace / "revisions" / f"REV-{pointer['revision']:06d}.json"
            )
            state_dict = snapshot.state.model_dump(mode="json")
            h2 = _sha256(_projection_v2(state_dict))
            pointer_rows.append(
                {
                    "workspace": str(workspace.relative_to(REPO_ROOT)),
                    "project_id": pointer["project_id"],
                    "revision": pointer["revision"],
                    "stored": pointer["state_hash"],
                    "state_hash_v2": h2,
                    "v2_eq_stored": h2 == pointer["state_hash"],
                }
            )

    loadable_by_label = {
        f"{row['project_id']}:{row['revision']}": row["v1_eq_stored"]
        for row in revision_rows
    }
    loadable_pointer_mismatches: list[str] = []
    preexisting_unloadable_pointers: list[str] = []
    for row in pointer_rows:
        label = f"{row['project_id']}:{row['revision']}"
        if loadable_by_label.get(label) is True:
            if not row["v2_eq_stored"]:
                loadable_pointer_mismatches.append(label)
        else:
            preexisting_unloadable_pointers.append(label)

    # Deterministic serialization: recomputing yields identical bytes.
    for row in revision_rows:
        snapshot = _load_snapshot(
            REPO_ROOT / row["workspace"] / "revisions" / f"REV-{row['revision']:06d}.json"
        )
        state_dict = snapshot.state.model_dump(mode="json")
        assert _sha256(_projection_v2(state_dict)) == row["state_hash_v2"]

    # ADD /joint_authority_declarations/<id> validity (read-only, synthetic payload).
    payload: dict = {"joint_authority_declarations": []}
    apply_operation(
        payload,
        ChangeOperation(
            operation=OperationType.ADD,
            path="/joint_authority_declarations/DECL-1",
            value={"id": "DECL-1"},
        ),
    )
    assert payload["joint_authority_declarations"] == [{"id": "DECL-1"}]
    with pytest.raises(ChangeConflictError):
        apply_operation(
            payload,
            ChangeOperation(
                operation=OperationType.ADD,
                path="/joint_authority_declarations/DECL-1",
                value={"id": "DECL-1"},
            ),
        )
    none_payload: dict = {"joint_authority_declarations": None}
    with pytest.raises(InvalidChangePathError):
        apply_operation(
            none_payload,
            ChangeOperation(
                operation=OperationType.ADD,
                path="/joint_authority_declarations/DECL-1",
                value={"id": "DECL-1"},
            ),
        )

    report = {
        "gate": "B0",
        "status": "PENDING",
        "workspaces": [str(w.relative_to(REPO_ROOT)) for w in workspaces],
        "revision_count": len(revision_rows),
        "pointer_count": len(pointer_rows),
        "projection_mismatches": projection_mismatches,
        "loadable_mismatches": loadable_mismatches,
        "loadable_pointer_mismatches": loadable_pointer_mismatches,
        "preexisting_unloadable": preexisting_unloadable,
        "preexisting_unloadable_pointers": preexisting_unloadable_pointers,
        "add_validity": "pass",
        "revisions": revision_rows,
        "pointers": pointer_rows,
    }
    EVIDENCE_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    # H1-B invariants (hard gate).
    assert not projection_mismatches, f"v1/v2 projection mismatch: {projection_mismatches}"
    assert not loadable_mismatches, f"loadable revision v2 mismatch: {loadable_mismatches}"
    assert not loadable_pointer_mismatches, (
        f"loadable pointer v2 mismatch: {loadable_pointer_mismatches}"
    )
    report["status"] = "PASS"
    EVIDENCE_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
