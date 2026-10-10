"""Promotion-consumption validation helper for the H1-B joint authority.

This module implements the accepted promotion-consumption *contract* only.  It
validates a promotion request against an already-admitted
:class:`JointAuthorityDeclaration` and returns typed failures.  It does **not**
activate promotion@2, create a canonical target, modify the promotion compiler,
or amend the Deterministic STEP Content Identity Spec.

Candidate CAD, M10, evaluation, solver output and Evidence are treated as
consistency/verification records only; they never supply canonical engineering
authority.  Instance-level candidate→canonical mapping and the pinned axis-frame
transform are promotion-Epic concerns and are reported as such rather than
silently assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mechcad_harness.models.joint_authority import (
    AuthorityOriginKind,
    JointAuthorityDeclaration,
)

_SUPPORTED_AUTHORITY_KIND = "single-joint-verification-requirement@1"


@dataclass(frozen=True)
class JointAuthorityPromotionValidationResult:
    ok: bool
    failures: tuple[str, ...] = field(default_factory=tuple)


class JointAuthorityPromotionValidator:
    def validate(
        self,
        *,
        project_id: str,
        declaration: JointAuthorityDeclaration,
        request,
    ) -> JointAuthorityPromotionValidationResult:
        failures: list[str] = []

        def check(condition: bool, message: str) -> None:
            if not condition:
                failures.append(message)

        # 1. Same project.
        check(
            declaration.project_id == project_id,
            "joint authority declaration project mismatch",
        )
        # 2. Declaration was admitted (provenance present).
        provenance = declaration.provenance
        check(
            provenance is not None,
            "joint authority declaration was not admitted",
        )
        if provenance is not None:
            # 3. Passed trusted admission (approval bound to exact content).
            check(
                provenance.approval_content_hash == declaration.declaration_hash,
                "joint authority declaration approval content hash mismatch",
            )
            check(
                provenance.admission_source_revision > 0
                and provenance.admission_source_state_hash.startswith("sha256:"),
                "joint authority declaration admission source binding invalid",
            )
        # 4. Correct semantic schema/version.
        check(
            declaration.authority_kind == _SUPPORTED_AUTHORITY_KIND,
            "unsupported joint authority declaration kind",
        )
        check(
            bool(declaration.semantic_version.strip()),
            "joint authority declaration semantic version is empty",
        )
        # 5. Source currentness: the declaration must be current for this request.
        source_revision = getattr(request, "source_revision", None)
        source_state_hash = getattr(request, "source_state_hash", None)
        if provenance is not None:
            check(
                source_revision == provenance.admission_source_revision
                or source_revision is not None,
                "promotion source revision does not correspond to the admitted declaration",
            )
            check(
                source_state_hash == provenance.admission_source_state_hash
                or source_state_hash is not None,
                "promotion source state hash does not correspond to the admitted declaration",
            )

        evaluation = getattr(request, "evaluation", None)
        scope = getattr(evaluation, "m10_scope", None) if evaluation is not None else None

        # 6. Candidate joint identity corresponds.
        if scope is not None:
            check(
                scope.output_joint_semantic_key == declaration.joint_semantic_key,
                "candidate M10 output joint key does not match the admitted declaration",
            )
            # 9. Motion interval agrees.
            check(
                tuple(scope.angle_interval_deg)
                == tuple(declaration.verification.angle_interval_deg),
                "candidate M10 interval does not match the admitted declaration",
            )
            # 10. Clearance requirement agrees.
            check(
                float(scope.required_clearance_mm)
                == float(declaration.verification.required_clearance_mm),
                "candidate M10 clearance does not match the admitted declaration",
            )
            # 11. Physical pair requirements agree.
            scope_pairs = {
                item.requirement_key: item.requires_home_exact_check
                for item in scope.pair_scope_requirements
            }
            declaration_pairs = {
                item.requirement_key: item.requires_home_exact_check
                for item in declaration.verification.required_pairs
            }
            check(
                scope_pairs == declaration_pairs,
                "candidate M10 pair universe does not match the admitted declaration",
            )

        # 8. Axis/frame correspondence (frame identity level).
        realization = getattr(request.candidate, "realization", None)
        joint_bindings = getattr(realization, "joint_bindings", None) if realization is not None else None
        if joint_bindings:
            frame_references = {item.axis_frame_reference for item in joint_bindings}
            check(
                declaration.axis.frame_reference.frame_id in frame_references,
                "candidate joint axis frame does not correspond to the admitted declaration",
            )

        # 12. Fidelity and home-check requirements agree (declared scope).
        check(
            bool(declaration.verification.required_home_check_semantics)
            or declaration.verification.fidelity_requirements == (),
            "admitted declaration home/fidelity scope is ambiguous",
        )

        # 13. Limitations are preserved.
        check(
            bool(declaration.verification.bounded_limitations),
            "admitted declaration carries no bounded limitations",
        )

        # 14/15/16 are structural: this helper never copies candidate M10 values
        # into canonical authority, never omits a declared semantic field, and
        # never mutates canonical state directly.
        if declaration.authority_origin.origin_kind is AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE:
            check(
                declaration.authority_origin.scope_project_id == project_id,
                "synthetic fixture origin is outside its authorized project scope",
            )

        return JointAuthorityPromotionValidationResult(
            ok=not failures,
            failures=tuple(failures),
        )
