# MechCAD Documentation Guide

This is the documentation entry point for MechCAD. Do not preload every document for every task. Start with the smallest context bundle that matches the task, then follow links only when the task crosses a subsystem boundary.

## Start Here

| Need | Read first | Add only when needed |
|---|---|---|
| Understand MechCAD overall | [Project Overview](architecture/MECHCAD_PROJECT_OVERVIEW.md) | [System Contract](architecture/MECHCAD_SYSTEM_CONTRACT.md) |
| Change canonical engineering state | [System Contract](architecture/MECHCAD_SYSTEM_CONTRACT.md) | [Subsystem Contracts](architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md), relevant M2/M3 specs |
| Understand an engineering workflow | [Engineering Workflow](architecture/MECHCAD_ENGINEERING_WORKFLOW.md) | [Runtime Flow](architecture/MECHCAD_RUNTIME_FLOW.md) |
| Add or review an agent | [System Contract](architecture/MECHCAD_SYSTEM_CONTRACT.md) | [Subsystem Contracts](architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md), relevant M6 specs/plans |
| Add or review a deterministic tool | [System Contract](architecture/MECHCAD_SYSTEM_CONTRACT.md) | M5/M5.5 specs, provider source, relevant tests |
| Add or review CAD | [Runtime Flow](architecture/MECHCAD_RUNTIME_FLOW.md) | [System Contract](architecture/MECHCAD_SYSTEM_CONTRACT.md), M8C-1/M8C-2 records, CAD source/tests |
| Add or review kinematics | [System Contract](architecture/MECHCAD_SYSTEM_CONTRACT.md) | [Runtime Flow](architecture/MECHCAD_RUNTIME_FLOW.md), M8C-3/M9-3/M10-2 records |
| Add a mechanical domain | [Domain Extension Guide](architecture/MECHCAD_DOMAIN_EXTENSION_GUIDE.md) | [System Contract](architecture/MECHCAD_SYSTEM_CONTRACT.md), [Capability Matrix](architecture/MECHCAD_CAPABILITY_MATRIX.md) |
| Determine capability maturity | [Capability Matrix](architecture/MECHCAD_CAPABILITY_MATRIX.md) | [Documentation Gaps](architecture/MECHCAD_DOCUMENTATION_GAPS.md), cited specs/plans |
| Perform the independent integration audit | [Integration Audit](audit/MECHCAD_INTEGRATION_AUDIT.md) | [System Contract](architecture/MECHCAD_SYSTEM_CONTRACT.md), [Capability Matrix](architecture/MECHCAD_CAPABILITY_MATRIX.md), cited implementation/tests |

## Architecture Bundle

Read these together only for architecture-wide work:

1. [Project Overview](architecture/MECHCAD_PROJECT_OVERVIEW.md)
2. [System Contract](architecture/MECHCAD_SYSTEM_CONTRACT.md)
3. [Engineering Workflow](architecture/MECHCAD_ENGINEERING_WORKFLOW.md)
4. [Runtime Flow](architecture/MECHCAD_RUNTIME_FLOW.md)
5. [Subsystem Contracts](architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md)
6. [Capability Matrix](architecture/MECHCAD_CAPABILITY_MATRIX.md)
7. [Domain Extension Guide](architecture/MECHCAD_DOMAIN_EXTENSION_GUIDE.md)
8. [Documentation Gaps](architecture/MECHCAD_DOCUMENTATION_GAPS.md)

The architecture bundle describes intended contracts and maturity. It does not prove that the repository implements or connects those contracts.

## Audit Bundle

For an implementation/integration audit, load:

1. [Integration Audit Procedure](audit/MECHCAD_INTEGRATION_AUDIT.md)
2. [System Contract](architecture/MECHCAD_SYSTEM_CONTRACT.md)
3. [Capability Matrix](architecture/MECHCAD_CAPABILITY_MATRIX.md)
4. [M9 System Acceptance](audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md), [M10-2 Completion](audit/MECHCAD_M10_2_COMPLETION_REPORT.md), and [M8C Closure](audit/MECHCAD_M8C_SYSTEM_CLOSURE_AUDIT.md)
5. Only the source files, tests, manifests, and accepted specs named by the capability under review

Do not treat this guide, a filename, an import, or an isolated test as runtime integration evidence. Leave audit verdict fields as `TO_BE_AUDITED` until the audit is actually performed.

## Source Precedence

When documents disagree, use this order:

1. Accepted specifications in `docs/superpowers/specs/`
2. Accepted plans and completion records in `docs/superpowers/plans/`
3. Current architecture contracts in `docs/architecture/`
4. Current production implementation and tests
5. Historical/current project description in `MechCAD_Harness_Project_Description.md`

Historical material preserves intent and explains superseded roadmap statements. It does not replace current contracts or runtime audit evidence.

## Maturity Vocabulary

Use only these normative values:

- `FOUNDATION`: accepted reusable baseline foundation; included in baseline conformance audit.
- `REQUIRED_CURRENT`: required current contract; included in baseline conformance audit.
- `TARGET_NEXT`: selected next integration or capability work; audited only for connected readiness when selected.
- `FUTURE`: longer-term architecture; documentation only for current acceptance.

Domain labels such as `Domain reference`, `Yagi example`, and `Reference adapter` are classifications or notes, not maturity values.

## Task-Sized Loading Rules

- Do not read all `docs/superpowers/specs/` and `docs/superpowers/plans/` unless performing architecture reconciliation or audit preparation.
- For a single subsystem, read its contract, one relevant architecture flow, the cited specification, and the relevant implementation/tests.
- For a cross-subsystem change, add the downstream consumer and upstream authority contracts before editing.
- For a domain change, start with the Domain Extension Guide and keep domain documents separate from generic contracts.
- For an audit, use the audit procedure and capability matrix first, then load only the evidence required for the selected rows.
- If a document claims `CURRENT`, verify whether it means `FOUNDATION` or `REQUIRED_CURRENT`; `CURRENT` is descriptive prose, not a matrix maturity value.

## Historical Reference

[MechCAD Harness Project Description](MechCAD_Harness_Project_Description.md) is a historical + evolving project overview. Read it for mission, milestone reconciliation, and current project status. Do not use it alone as implementation or integration proof.
