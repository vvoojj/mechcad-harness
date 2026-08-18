# M3 Dependency Invalidation Design

## Goal

Determine which derived dependency nodes become stale after canonical `DesignState` changes, without executing recalculation or embedding derived records in canonical state.

## Scope

M3 adds deterministic dependency matching, direct and transitive invalidation, immutable filesystem invalidation records, immutable evidence records, and fail-closed freshness queries. It does not add agents, orchestration, scheduling, execution, CAD, FEA, databases, or external services.

## Architecture

`ChangeEngine` continues to validate and persist canonical revisions. Its result gains a small `AppliedChangeResult` boundary containing the resulting `RevisionSnapshot`, generated changeset ID, and changed canonical paths. A separate M3 service consumes that result, matches paths against static YAML rules, walks configured downstream dependency edges, and persists one immutable invalidation record for the new revision.

Evidence remains outside `DesignState` and is immutable once written. Each evidence record identifies a configured dependency node, its originating state revision, and the exact state hash for provenance. Freshness checks first verify that the referenced canonical revision and hash are valid, then require complete M3 invalidation records for every revision strictly after the evidence revision through the current revision. A matching invalidation makes evidence `STALE`; complete coverage without a match makes it `CURRENT`; missing coverage, invalid provenance, or an unknown node makes it `UNKNOWN`.

The invalidation that produces revision N is not considered when evaluating evidence created at revision N. Therefore evidence created after recalculation against revision N can be current immediately.

## Path Semantics

Dependency patterns use slash-separated canonical path segments. A pattern segment is either a literal or a single-segment `*` wildcard. A rule matches when every pattern segment matches the corresponding changed path segment; the pattern may be a prefix of a longer changed path. Thus `/materials/*` matches `/materials/MAT-001/material`, and `/components/*/transmission` matches descendants such as `/components/PRT-001/transmission/module`. This matching behavior is separate from M2 ownership matching unless shared helpers can preserve existing ownership behavior and tests.

## Configuration

`config/dependencies.yaml` contains a small static rule set for materials, transmission, placement, and requirements. It also contains explicit directed dependency edges sufficient to exercise transitive invalidation, such as `analysis.loads -> analysis.structural -> validation.structural`. Duplicate affected nodes are removed and output is sorted deterministically. Cycles fail with `DependencyCycleError` during graph construction.

## Persistence

Invalidations are stored at `projects/<project_id>/invalidations/REV-XXXXXX.json`. Each record contains project, revision, parent revision, optional changeset ID, changed paths, direct nodes, transitive nodes, and UTC creation time. Existing revision invalidation files raise an error rather than being overwritten.

Evidence is stored at `projects/<project_id>/evidence/<evidence_id>.json`. Existing IDs raise `EvidenceConflictError`. Evidence is never copied into state snapshots and stale evidence is never deleted.

## Freshness

`CURRENT` requires valid exact-revision provenance, a known dependency node, complete invalidation coverage for every revision after the evidence revision through current, and no later invalidation affecting that node. `STALE` requires the same conditions except at least one later invalidation affects the node. `UNKNOWN` is returned when freshness cannot be safely proven, including missing invalidation records, invalid evidence provenance, or unknown nodes. Unknown and stale evidence never satisfy a fresh-evidence query.

Revisions created before M3 are outside the assumed coverage boundary. They receive `UNKNOWN` freshness unless the required post-evidence invalidation records have been explicitly established.

## Testing

Tests cover path prefix matching, wildcards, unrelated paths, direct and transitive invalidation, deduplication and deterministic order, cycle/configuration errors, immutable persistence, exact state-hash provenance, missing history fail-closed behavior, revision-own invalidation exclusion, stale replacement evidence, and the complete M0-M2 regression suite.
