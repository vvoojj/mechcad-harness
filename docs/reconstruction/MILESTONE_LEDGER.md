# MechCAD Reconstruction Milestone Ledger

This ledger tracks reconstructed historical milestone state. It is not a
statement of the current production capability baseline.

| Milestone | Git Boundary | Implementation | Historical Verification | Confidence | Canonical Record |
| --------- | ------------ | -------------- | ----------------------- | ---------- | ---------------- |
| M0 | `7185351` | `IMPLEMENTED_WITH_DEVIATIONS` | `HISTORICALLY_UNVERIFIED` | `MEDIUM_HIGH` | [`milestones/M0.md`](milestones/M0.md) |
| M1 | `37f3ff3` *(shared with M2)* | `IMPLEMENTED` | `HISTORICALLY_UNVERIFIED` | `HIGH` | [`milestones/M1.md`](milestones/M1.md) |
| M2 | `37f3ff3` *(shared with M1)* | `IMPLEMENTED_WITH_DEVIATIONS` | `HISTORICALLY_UNVERIFIED` | `HIGH` | [`milestones/M2.md`](milestones/M2.md) |
| M3 | `df584f0` | `IMPLEMENTED_WITH_DEVIATIONS` | `NOT_RETAINED` | `HIGH` | [`milestones/M3.md`](milestones/M3.md) |
| M4 | `a958c397` | `IMPLEMENTED_WITH_DEVIATIONS` | `NOT_RETAINED` | `HIGH` | [`milestones/M4.md`](milestones/M4.md) |

## Boundary Note

```text
M1 State Foundation and M2 ChangeSet Foundation first enter retained Git
history in the same commit:

37f3ff3ea143400adb460e4650e1b580a4f1488d

M1 and M2 are distinct architectural milestones despite sharing one Git
boundary. M1 is reconstructed as a distinct capability milestone without a
separately retained Git commit.
```

## Next Reconstruction Target

```text
M5 begins at 6cbade0ea53f1652d44bb92f92831a0c8daf62c5 and has not yet
undergone its own forensic reconstruction.
```
