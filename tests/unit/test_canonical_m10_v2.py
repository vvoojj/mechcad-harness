from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

import mechcad_harness.candidates.canonical_m10 as canonical_m10
from mechcad_harness.candidates.canonical_m10 import (
    CanonicalM10BodyDisposition,
    CanonicalM10PairClassification,
    CanonicalM10VerificationService,
)
from mechcad_harness.candidates.canonical_cad import CanonicalPhysicalCadCompiler
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
    _projection_from_mechanism,
)
from mechcad_harness.cad_assembly import M10_EXECUTION_SEMANTICS_VERSION
from mechcad_harness.continuous_proof import (
    ContinuousSingleAxisProofRequest,
    ContinuousSingleAxisProofResult,
    _semantic_proof_request_hash_from_assembly_identity,
    _semantic_proof_result_hash_from_assembly_identity,
)
from mechcad_harness.kinematic_sweep import (
    _semantic_sweep_request_hash_from_assembly_identity,
    _semantic_sweep_result_hash_from_assembly_identity,
)
from mechcad_harness.models import (
    CanonicalJointPhysicalBinding,
    CanonicalM10VerificationObligation,
    CanonicalPhysicalMechanism,
    CanonicalPhysicalPairRequirement,
)
from mechcad_harness.multi_joint_kinematics import kinematic_model_hash
from mechcad_harness.semantic_m10_kinematics import semantic_single_joint_kinematic_model_hash
from mechcad_harness.state.hashing import canonical_json
from test_canonical_m10_scope_v2 import _scope
from test_canonical_cad_realization_v2 import _fixture as _canonical_cad_fixture
from test_m12_canonical_m10 import _home_result, _proof_result


def test_canonical_m10_v2_declares_only_the_accepted_n2_field_sets():
    inventory_type = getattr(canonical_m10, "CanonicalM10PairInventoryV2", None)
    request_type = getattr(canonical_m10, "CanonicalM10EvaluationRequestV2", None)
    proof_type = getattr(canonical_m10, "CanonicalM10PairProofV2", None)
    home_type = getattr(canonical_m10, "CanonicalM10HomeExactCheckV2", None)
    outcome_type = getattr(canonical_m10, "CanonicalM10VerificationOutcomeV2", None)
    assert inventory_type is not None, "canonical M10 inventory@2 is not implemented"
    assert request_type is not None, "canonical M10 request@2 is not implemented"
    assert proof_type is not None, "canonical M10 pair proof@2 is not implemented"
    assert home_type is not None, "canonical M10 home check@2 is not implemented"
    assert outcome_type is not None, "canonical M10 outcome@2 is not implemented"

    assert set(inventory_type.model_fields) == {
        "schema_version", "project_id", "revision", "state_hash", "mechanism_id",
        "mechanism_hash", "cad_realization_hash", "semantic_scope_hash",
        "constituent_dispositions", "expected_pair_universe", "classifications",
        "checked_pairs", "excluded_pairs", "inventory_hash",
    }
    assert set(request_type.model_fields) == {
        "schema_version", "project_id", "revision", "state_hash", "mechanism_id",
        "mechanism_hash", "cad_realization_hash",
        "semantic_single_joint_kinematic_model_hash", "mapping_hashes",
        "semantic_scope_hash", "inventory", "request_hash",
    }
    assert set(outcome_type.model_fields) == {
        "schema_version", "project_id", "revision", "state_hash", "mechanism_id",
        "mechanism_hash", "cad_realization_hash", "scope", "inventory", "request",
        "status", "pair_proofs", "home_exact_checks", "outcome_hash",
    }
    wrapper_fields = {
        "schema_version", "pair", "moving_instance_id", "stationary_instance_id",
        "request", "result", "request_hash", "result_hash",
        "semantic_assembly_hash",
    }
    assert set(proof_type.model_fields) == wrapper_fields | {"proof_hash"}
    assert set(home_type.model_fields) == wrapper_fields | {"check_hash"}

    legacy_request_fields = set(canonical_m10.CanonicalM10EvaluationRequest.model_fields)
    assert len(legacy_request_fields) == 13
    assert len(request_type.model_fields) == 12
    assert "binding_semantic_hash" in legacy_request_fields
    assert "binding_semantic_hash" not in request_type.model_fields
    assert "model_hash" in legacy_request_fields
    assert "model_hash" not in request_type.model_fields


class _FakeM10Application:
    def __init__(self):
        self.proof_calls = 0
        self.home_calls = 0

    def prove_continuous_single_axis_clearance(self, **kwargs):
        self.proof_calls += 1
        return _proof_result(kwargs)

    def analyze_assembly_kinematics(self, **kwargs):
        self.home_calls += 1
        return _home_result(kwargs)


def _canonical_m10_v4_fixture(tmp_path, *, variant="A"):
    base_mechanism, base_reconstruction, resolver = _canonical_cad_fixture(
        tmp_path, variant=variant
    )
    provisional_binding = CanonicalJointPhysicalBinding(
        joint_id="joint-output",
        expected_parent_instance_id="instance-parent",
        expected_child_instance_id="instance-child",
        axis_frame_reference="frame:parent-axis@1",
        semantic_hash="sha256:" + "c" * 64,
        semantic_version="canonical-joint-meaning@1",
    )
    binding = CanonicalJointPhysicalBinding.model_validate(
        provisional_binding.model_dump(mode="python")
        | {
            "semantic_hash": CanonicalM10VerificationService._joint_semantic_hash(
                provisional_binding
            ),
            "binding_hash": "pending",
        }
    )
    obligation = CanonicalM10VerificationObligation(
        joint_semantic_key=binding.joint_id,
        angle_interval_deg=(-10.0, 20.0),
        required_clearance_mm=2.0,
        physical_pair_requirements=(
            CanonicalPhysicalPairRequirement(
                requirement_key="mount-to-output-clearance",
                first_instance_id="instance-parent",
                first_interface_id="axis",
                second_instance_id="instance-child",
                second_interface_id="axis",
                requires_home_exact_check=True,
            ),
        ),
        fidelity_requirements=(),
        required_home_check_semantics=("verify-home-clearance@1",),
        bounded_limitations=("single-axis-only",),
    )
    mechanism = CanonicalPhysicalMechanism.model_validate(
        base_mechanism.model_dump(mode="python")
        | {
            "joint_bindings": (binding,),
            "m10_obligations": (obligation,),
            "mechanism_hash": "pending",
        }
    )
    reconstruction = CanonicalMechanismReconstruction.model_validate(
        base_reconstruction.model_dump(mode="python")
        | {
            "canonical_mechanism": mechanism,
            "normalized_projection_hash": _projection_from_mechanism(
                mechanism
            ).projection_hash,
        }
    )
    cad = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)
    application = _FakeM10Application()
    return mechanism, reconstruction, cad, application


def test_canonical_m10_v2_executes_and_restart_revalidates_without_provider_calls(
    tmp_path, monkeypatch
):
    outcome_type = getattr(canonical_m10, "CanonicalM10VerificationOutcomeV2", None)
    assert outcome_type is not None, "canonical M10 outcome@2 is not implemented"
    mechanism, reconstruction, cad, application = _canonical_m10_v4_fixture(tmp_path)
    service = CanonicalM10VerificationService(application)

    outcome = service.execute(reconstruction, cad)

    assert outcome.schema_version == "canonical-m10-verification-outcome@2"
    assert outcome.mechanism_hash == mechanism.mechanism_hash
    assert outcome.cad_realization_hash == cad.realization_hash
    model = service._derive_canonical_inputs(reconstruction, cad)[2]
    assert outcome.request.semantic_single_joint_kinematic_model_hash == (
        semantic_single_joint_kinematic_model_hash(model)
    )
    evaluator_only_variant = model.model_copy(
        update={"evaluator_version": "legacy-evaluator-only-variant"}
    )
    assert kinematic_model_hash(evaluator_only_variant) != kinematic_model_hash(model)
    assert semantic_single_joint_kinematic_model_hash(evaluator_only_variant) == (
        outcome.request.semantic_single_joint_kinematic_model_hash
    )
    assert outcome.request.semantic_scope_hash == canonical_m10.semantic_canonical_m10_scope_hash(
        outcome.scope
    )
    assert outcome.inventory.semantic_scope_hash == outcome.request.semantic_scope_hash
    assert outcome.scope.scope_hash != outcome.request.semantic_scope_hash
    assert all(
        proof.schema_version == "canonical-m10-pair-proof@2"
        for proof in outcome.pair_proofs
    )
    assert all(
        check.schema_version == "canonical-m10-home-exact-check@2"
        for check in outcome.home_exact_checks
    )

    proof = outcome.pair_proofs[0]
    proof_payload = {
        "schema_version": "canonical-m10-pair-proof@2",
        "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
        "pair": list(proof.pair),
        "moving_instance_id": proof.moving_instance_id,
        "stationary_instance_id": proof.stationary_instance_id,
        "semantic_proof_request_hash": _semantic_proof_request_hash_from_assembly_identity(
            proof.request, proof.semantic_assembly_hash
        ),
        "semantic_proof_result_hash": _semantic_proof_result_hash_from_assembly_identity(
            proof.result, proof.request, proof.semantic_assembly_hash
        ),
        "semantic_assembly_hash": proof.semantic_assembly_hash,
    }
    expected_proof_hash = "sha256:" + hashlib.sha256(
        canonical_json(proof_payload)
    ).hexdigest()
    assert proof.proof_hash == expected_proof_hash
    assert proof.proof_hash == (
        "sha256:55d95d49807926d02bc5502ff5d026be1653df80823aa1d00bf68b28ed4d20a1"
    )
    assert "source_assembly_hash" not in proof_payload
    assert "request_hash" not in proof_payload
    assert "result_hash" not in proof_payload

    check = outcome.home_exact_checks[0]
    check_payload = {
        "schema_version": "canonical-m10-home-exact-check@2",
        "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
        "pair": list(check.pair),
        "moving_instance_id": check.moving_instance_id,
        "stationary_instance_id": check.stationary_instance_id,
        "semantic_sweep_request_hash": _semantic_sweep_request_hash_from_assembly_identity(
            check.request, check.semantic_assembly_hash
        ),
        "semantic_sweep_result_hash": _semantic_sweep_result_hash_from_assembly_identity(
            check.result, check.request, check.semantic_assembly_hash
        ),
        "semantic_assembly_hash": check.semantic_assembly_hash,
    }
    expected_check_hash = "sha256:" + hashlib.sha256(
        canonical_json(check_payload)
    ).hexdigest()
    assert check.check_hash == expected_check_hash
    assert check.check_hash == (
        "sha256:ed4548b417e2366e0685f6852a3039d09080653244d01619935df1cdf4b6fbdb"
    )
    assert "source_assembly_hash" not in check_payload
    assert "request_hash" not in check_payload
    assert "result_hash" not in check_payload

    outcome_payload = {
        "schema_version": outcome.schema_version,
        "project_id": outcome.project_id,
        "mechanism_id": outcome.mechanism_id,
        "mechanism_hash": outcome.mechanism_hash,
        "cad_realization_hash": outcome.cad_realization_hash,
        "semantic_scope_hash": canonical_m10.semantic_canonical_m10_scope_hash(
            outcome.scope
        ),
        "inventory_hash": outcome.inventory.inventory_hash,
        "request_hash": outcome.request.request_hash,
        "status": outcome.status.value,
        "proof_hashes": [proof.proof_hash],
        "check_hashes": [check.check_hash],
    }
    expected_outcome_hash = "sha256:" + hashlib.sha256(
        canonical_json(outcome_payload)
    ).hexdigest()
    assert outcome.outcome_hash == expected_outcome_hash
    assert outcome.outcome_hash == (
        "sha256:762a112efe42d0f03d4cf6601ea65c44caa7e97124116874ba9802b59706ffc9"
    )

    restored = outcome_type.model_validate(outcome.model_dump(mode="json"))
    provider_calls = (application.proof_calls, application.home_calls)
    def no_cad_restart(*args, **kwargs):
        raise AssertionError("canonical M10 restart must not compile CAD")

    monkeypatch.setattr(CanonicalPhysicalCadCompiler, "realize", no_cad_restart)
    service.verify_persisted(restored, reconstruction, cad)
    assert (application.proof_calls, application.home_calls) == provider_calls


def _scope_request_chain():
    scope = _scope()
    disposition_type = canonical_m10.CanonicalM10ConstituentDispositionV2
    classification_type = canonical_m10.CanonicalM10PairClassificationRecordV2
    dispositions = (
        disposition_type(
            physical_instance_id="fixed",
            cad_instance_id="cad-fixed",
            disposition=CanonicalM10BodyDisposition.FIXED,
        ),
        disposition_type(
            physical_instance_id="output",
            cad_instance_id="cad-output",
            disposition=CanonicalM10BodyDisposition.OUTPUT_RIGID,
            output_transform_group="joint-output",
        ),
    )
    classifications = (
        classification_type(
            pair=("cad-fixed", "cad-output"),
            classification=CanonicalM10PairClassification.CHECK_CLEARANCE,
            requires_home_exact_check=True,
        ),
    )
    inventory = canonical_m10.CanonicalM10PairInventoryV2(
        project_id=scope.project_id,
        revision=scope.revision,
        state_hash=scope.state_hash,
        mechanism_id=scope.mechanism_id,
        mechanism_hash=scope.mechanism_hash,
        cad_realization_hash="sha256:" + "d" * 64,
        semantic_scope_hash=canonical_m10.semantic_canonical_m10_scope_hash(scope),
        constituent_dispositions=dispositions,
        expected_pair_universe=(("cad-fixed", "cad-output"),),
        classifications=classifications,
        checked_pairs=(("cad-fixed", "cad-output"),),
    )
    request = canonical_m10.CanonicalM10EvaluationRequestV2(
        project_id=scope.project_id,
        revision=scope.revision,
        state_hash=scope.state_hash,
        mechanism_id=scope.mechanism_id,
        mechanism_hash=scope.mechanism_hash,
        cad_realization_hash=inventory.cad_realization_hash,
        semantic_single_joint_kinematic_model_hash="sha256:" + "e" * 64,
        mapping_hashes=("sha256:" + "a" * 64, "sha256:" + "b" * 64),
        semantic_scope_hash=inventory.semantic_scope_hash,
        inventory=inventory,
    )
    return scope, inventory, request


def test_inventory_and_request_hash_payloads_are_exact_and_scope_bound():
    scope, inventory, request = _scope_request_chain()
    expected_inventory_payload = {
        "schema_version": "canonical-m10-pair-inventory@2",
        "project_id": scope.project_id,
        "mechanism_id": scope.mechanism_id,
        "mechanism_hash": scope.mechanism_hash,
        "cad_realization_hash": inventory.cad_realization_hash,
        "semantic_scope_hash": inventory.semantic_scope_hash,
        "constituent_disposition_hashes": [
            item.disposition_hash
            for item in sorted(
                inventory.constituent_dispositions,
                key=lambda item: (item.physical_instance_id, item.cad_instance_id),
            )
        ],
        "expected_pair_universe": [["cad-fixed", "cad-output"]],
        "classification_hashes": [inventory.classifications[0].classification_hash],
        "checked_pairs": [["cad-fixed", "cad-output"]],
        "excluded_pairs": [],
    }
    assert inventory.inventory_hash == "sha256:" + hashlib.sha256(
        canonical_json(expected_inventory_payload)
    ).hexdigest()
    assert inventory.inventory_hash == (
        "sha256:d021f66cd3fe3a4d8ed95fd4cef10294554ab3b2d5701748281f6259784671dc"
    )

    expected_request_payload = {
        "schema_version": "canonical-m10-evaluation-request@2",
        "project_id": request.project_id,
        "mechanism_id": request.mechanism_id,
        "mechanism_hash": request.mechanism_hash,
        "cad_realization_hash": request.cad_realization_hash,
        "semantic_single_joint_kinematic_model_hash": (
            request.semantic_single_joint_kinematic_model_hash
        ),
        "mapping_hashes": list(request.mapping_hashes),
        "semantic_scope_hash": request.semantic_scope_hash,
        "inventory_hash": inventory.inventory_hash,
    }
    assert request.request_hash == "sha256:" + hashlib.sha256(
        canonical_json(expected_request_payload)
    ).hexdigest()
    assert request.request_hash == (
        "sha256:27e227893e725946099eb74e4dec1982fc843840dcb1dbce3f54f953e6e65ae9"
    )
    assert not {
        "binding_semantic_hash", "model_hash", "scope_hash", "requirement_hash"
    } & set(expected_request_payload)

    moved_inventory = canonical_m10.CanonicalM10PairInventoryV2.model_validate(
        inventory.model_dump(mode="json")
        | {
            "revision": inventory.revision + 1,
            "state_hash": "sha256:" + "c" * 64,
            "inventory_hash": "pending",
        }
    )
    assert moved_inventory.inventory_hash == inventory.inventory_hash
    moved_request = canonical_m10.CanonicalM10EvaluationRequestV2.model_validate(
        request.model_dump(mode="json")
        | {
            "revision": request.revision + 1,
            "state_hash": "sha256:" + "c" * 64,
            "inventory": moved_inventory.model_dump(mode="json"),
            "request_hash": "pending",
        }
    )
    assert moved_request.request_hash == request.request_hash

    other_project_inventory = canonical_m10.CanonicalM10PairInventoryV2.model_validate(
        inventory.model_dump(mode="json")
        | {"project_id": "PRJ-OTHER", "inventory_hash": "pending"}
    )
    assert other_project_inventory.inventory_hash != inventory.inventory_hash
    changed_model_request = canonical_m10.CanonicalM10EvaluationRequestV2.model_validate(
        request.model_dump(mode="json")
        | {
            "semantic_single_joint_kinematic_model_hash": "sha256:" + "f" * 64,
            "request_hash": "pending",
        }
    )
    assert changed_model_request.request_hash != request.request_hash
    for invalid_mapping_hashes in (
        tuple(reversed(request.mapping_hashes)),
        (request.mapping_hashes[0], request.mapping_hashes[0]),
    ):
        with pytest.raises(ValueError, match="sorted and unique"):
            canonical_m10.CanonicalM10EvaluationRequestV2.model_validate(
                request.model_dump(mode="json")
                | {
                    "mapping_hashes": invalid_mapping_hashes,
                    "request_hash": "pending",
                }
            )


def test_canonical_inventory_order_is_semantic_set_order_and_mixed_versions_reject():
    _, inventory, request = _scope_request_chain()
    reordered = canonical_m10.CanonicalM10PairInventoryV2.model_validate(
        inventory.model_dump(mode="json")
        | {
            "constituent_dispositions": list(reversed(inventory.constituent_dispositions)),
            "inventory_hash": "pending",
        }
    )
    assert reordered.inventory_hash == inventory.inventory_hash

    duplicate_dispositions = inventory.model_dump(mode="json")
    duplicate_dispositions["constituent_dispositions"] = [
        *duplicate_dispositions["constituent_dispositions"],
        duplicate_dispositions["constituent_dispositions"][0],
    ]
    duplicate_dispositions["inventory_hash"] = "pending"
    with pytest.raises(ValueError, match="unique|duplicate|complete"):
        canonical_m10.CanonicalM10PairInventoryV2.model_validate(
            duplicate_dispositions
        )

    duplicate_classifications = inventory.model_dump(mode="json")
    duplicate_classifications["classifications"] = [
        *duplicate_classifications["classifications"],
        duplicate_classifications["classifications"][0],
    ]
    duplicate_classifications["inventory_hash"] = "pending"
    with pytest.raises(ValueError, match="duplicate|incomplete"):
        canonical_m10.CanonicalM10PairInventoryV2.model_validate(
            duplicate_classifications
        )

    legacy_disposition = canonical_m10.CanonicalM10ConstituentDisposition(
        physical_instance_id="fixed",
        cad_instance_id="cad-fixed",
        disposition=CanonicalM10BodyDisposition.FIXED,
    )
    mixed = inventory.model_dump(mode="json")
    mixed["constituent_dispositions"] = [
        legacy_disposition.model_dump(mode="json"),
        inventory.constituent_dispositions[1].model_dump(mode="json"),
    ]
    mixed["inventory_hash"] = "pending"
    with pytest.raises(ValidationError):
        canonical_m10.CanonicalM10PairInventoryV2.model_validate(mixed)

    forged_disposition = inventory.constituent_dispositions[0].model_copy(
        update={"disposition": CanonicalM10BodyDisposition.OUTPUT_RIGID}
    )
    forged_inventory = inventory.model_copy(
        update={
            "constituent_dispositions": (
                forged_disposition,
                inventory.constituent_dispositions[1],
            ),
            "inventory_hash": "pending",
        }
    )
    with pytest.raises(ValueError, match="disposition@2 hash"):
        canonical_m10.canonical_m10_pair_inventory_hash_v2(forged_inventory)

    bad_scope = request.model_dump(mode="json") | {
        "semantic_scope_hash": "sha256:" + "f" * 64,
        "request_hash": "pending",
    }
    with pytest.raises(ValueError, match="semantic scope"):
        canonical_m10.CanonicalM10EvaluationRequestV2.model_validate(bad_scope)


def test_inventory_classification_set_order_is_normalized_and_duplicates_reject():
    scope = _scope()
    dispositions = tuple(
        canonical_m10.CanonicalM10ConstituentDispositionV2(
            physical_instance_id=f"physical-{suffix}",
            cad_instance_id=f"cad-{suffix}",
            disposition=CanonicalM10BodyDisposition.FIXED,
        )
        for suffix in ("a", "b", "c")
    )
    pairs = (("cad-a", "cad-b"), ("cad-a", "cad-c"), ("cad-b", "cad-c"))
    classifications = tuple(
        canonical_m10.CanonicalM10PairClassificationRecordV2(
            pair=pair,
            classification=CanonicalM10PairClassification.OTHER_EXPLICIT_OUT_OF_SCOPE,
            reason="not in the canonical obligation",
        )
        for pair in pairs
    )

    def inventory_for(disposition_order, classification_order):
        return canonical_m10.CanonicalM10PairInventoryV2(
            project_id=scope.project_id,
            revision=scope.revision,
            state_hash=scope.state_hash,
            mechanism_id=scope.mechanism_id,
            mechanism_hash=scope.mechanism_hash,
            cad_realization_hash="sha256:" + "d" * 64,
            semantic_scope_hash=canonical_m10.semantic_canonical_m10_scope_hash(scope),
            constituent_dispositions=disposition_order,
            expected_pair_universe=pairs,
            classifications=classification_order,
            excluded_pairs=pairs,
        )

    baseline = inventory_for(dispositions, classifications)
    reordered = inventory_for(
        tuple(reversed(dispositions)), tuple(reversed(classifications))
    )
    assert reordered.inventory_hash == baseline.inventory_hash

    with pytest.raises(ValueError, match="duplicated"):
        inventory_for(dispositions, (*classifications, classifications[0]))


def test_canonical_m10_v2_chain_is_invariant_to_raw_step_rotation(tmp_path):
    mechanism_a, reconstruction_a, cad_a, application_a = _canonical_m10_v4_fixture(
        tmp_path, variant="A"
    )
    mechanism_b, reconstruction_b, cad_b, application_b = _canonical_m10_v4_fixture(
        tmp_path, variant="B"
    )
    outcome_a = CanonicalM10VerificationService(application_a).execute(
        reconstruction_a, cad_a
    )
    outcome_b = CanonicalM10VerificationService(application_b).execute(
        reconstruction_b, cad_b
    )

    assert mechanism_a.mechanism_hash == mechanism_b.mechanism_hash
    assert cad_a.assembly_hash != cad_b.assembly_hash
    assert cad_a.realization_hash == cad_b.realization_hash
    assert outcome_a.request.request_hash == outcome_b.request.request_hash
    assert outcome_a.inventory.inventory_hash == outcome_b.inventory.inventory_hash
    assert outcome_a.outcome_hash == outcome_b.outcome_hash
    assert outcome_a.pair_proofs[0].request.source_assembly_hash != (
        outcome_b.pair_proofs[0].request.source_assembly_hash
    )
    assert outcome_a.pair_proofs[0].request_hash != outcome_b.pair_proofs[0].request_hash
    assert outcome_a.pair_proofs[0].result_hash != outcome_b.pair_proofs[0].result_hash
    assert outcome_a.pair_proofs[0].proof_hash == outcome_b.pair_proofs[0].proof_hash
    assert outcome_a.home_exact_checks[0].check_hash == (
        outcome_b.home_exact_checks[0].check_hash
    )


def test_canonical_m10_outcome_rejects_scope_and_foreign_mechanism_substitution(tmp_path):
    _, reconstruction, cad, application = _canonical_m10_v4_fixture(tmp_path)
    service = CanonicalM10VerificationService(application)
    outcome = service.execute(reconstruction, cad)

    changed_scope = type(outcome.scope).model_validate(
        outcome.scope.model_dump(mode="json")
        | {"joint_semantic_key": "different-joint", "scope_hash": "pending"}
    )
    with pytest.raises(ValueError, match="semantic scope chain"):
        type(outcome).model_validate(
            outcome.model_dump(mode="json")
            | {"scope": changed_scope.model_dump(mode="json"), "outcome_hash": "pending"}
        )

    foreign_hash = "sha256:" + "f" * 64
    foreign_scope = type(outcome.scope).model_validate(
        outcome.scope.model_dump(mode="json")
        | {"mechanism_hash": foreign_hash, "scope_hash": "pending"}
    )
    foreign_inventory = type(outcome.inventory).model_validate(
        outcome.inventory.model_dump(mode="json")
        | {"mechanism_hash": foreign_hash, "inventory_hash": "pending"}
    )
    foreign_request = type(outcome.request).model_validate(
        outcome.request.model_dump(mode="json")
        | {
            "mechanism_hash": foreign_hash,
            "inventory": foreign_inventory.model_dump(mode="json"),
            "request_hash": "pending",
        }
    )
    foreign_outcome = type(outcome).model_validate(
        outcome.model_dump(mode="json")
        | {
            "mechanism_hash": foreign_hash,
            "scope": foreign_scope.model_dump(mode="json"),
            "inventory": foreign_inventory.model_dump(mode="json"),
            "request": foreign_request.model_dump(mode="json"),
            "outcome_hash": "pending",
        }
    )
    with pytest.raises(ValueError, match="inventory binding|mechanism"):
        service.verify_persisted(foreign_outcome, reconstruction, cad)

    proof = outcome.pair_proofs[0]
    foreign_raw_hash = "sha256:" + "9" * 64
    foreign_request = ContinuousSingleAxisProofRequest.model_validate(
        proof.request.model_dump(mode="json")
        | {"source_assembly_hash": foreign_raw_hash, "request_hash": "pending"}
    )
    foreign_result = ContinuousSingleAxisProofResult.model_validate(
        proof.result.model_dump(mode="json")
        | {
            "source_assembly_hash": foreign_raw_hash,
            "request_hash": foreign_request.request_hash,
            "result_hash": "sha256:" + "0" * 64,
        }
    )
    foreign_result = foreign_result.model_copy(
        update={"result_hash": canonical_m10.m10_result_hash(foreign_result)}
    )
    foreign_proof = type(proof).model_validate(
        proof.model_dump(mode="json")
        | {
            "request": foreign_request.model_dump(mode="json"),
            "result": foreign_result.model_dump(mode="json"),
            "request_hash": foreign_request.request_hash,
            "result_hash": foreign_result.result_hash,
            "proof_hash": "pending",
        }
    )
    foreign_raw_outcome = type(outcome).model_validate(
        outcome.model_dump(mode="json")
        | {
            "pair_proofs": (foreign_proof.model_dump(mode="json"),),
            "outcome_hash": "pending",
        }
    )
    with pytest.raises(ValueError, match="source assembly hash"):
        service.verify_persisted(foreign_raw_outcome, reconstruction, cad)


def test_canonical_outcome_hash_sorts_proof_and_check_references_by_pair(tmp_path):
    _, reconstruction, cad, application = _canonical_m10_v4_fixture(tmp_path)
    outcome = CanonicalM10VerificationService(application).execute(reconstruction, cad)
    proof = outcome.pair_proofs[0]
    check = outcome.home_exact_checks[0]
    other_proof = proof.model_copy(
        update={"pair": ("cad-a", "cad-z"), "proof_hash": "sha256:" + "f" * 64}
    )
    other_check = check.model_copy(
        update={"pair": ("cad-a", "cad-z"), "check_hash": "sha256:" + "e" * 64}
    )
    ordered = outcome.model_copy(
        update={"pair_proofs": (proof, other_proof), "home_exact_checks": (check, other_check)}
    )
    reversed_order = outcome.model_copy(
        update={
            "pair_proofs": (other_proof, proof),
            "home_exact_checks": (other_check, check),
        }
    )
    assert canonical_m10.canonical_m10_verification_outcome_hash_v2(
        ordered
    ) == canonical_m10.canonical_m10_verification_outcome_hash_v2(reversed_order)

    duplicate_proofs = outcome.model_dump(mode="json") | {
        "pair_proofs": [
            outcome.pair_proofs[0].model_dump(mode="json"),
            outcome.pair_proofs[0].model_dump(mode="json"),
        ],
        "outcome_hash": "pending",
    }
    with pytest.raises(ValueError, match="proofs do not exactly cover|exactly cover"):
        type(outcome).model_validate(duplicate_proofs)

    mixed_wrappers = outcome.model_dump(mode="json") | {
        "pair_proofs": [
            canonical_m10.CanonicalM10PairProof(
                pair=outcome.pair_proofs[0].pair,
                moving_instance_id=outcome.pair_proofs[0].moving_instance_id,
                stationary_instance_id=outcome.pair_proofs[0].stationary_instance_id,
                request=outcome.pair_proofs[0].request,
                result=outcome.pair_proofs[0].result,
                request_hash=outcome.pair_proofs[0].request_hash,
                result_hash=outcome.pair_proofs[0].result_hash,
            ).model_dump(mode="json")
        ],
        "outcome_hash": "pending",
    }
    with pytest.raises(ValidationError):
        type(outcome).model_validate(mixed_wrappers)
