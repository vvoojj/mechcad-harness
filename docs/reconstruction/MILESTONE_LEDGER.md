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
| M5 | `6cbade0` *(shared with M5.5A)* | `PARTIAL` | `NOT_RETAINED` | `HIGH` | [`milestones/M5.md`](milestones/M5.md) |
| M5.5A | `6cbade0` *(shared with M5)* | `NOT_IMPLEMENTED` | `NOT_RETAINED` | `HIGH` | [`milestones/M5.5A.md`](milestones/M5.5A.md) |
| M5.5B | `b0d77e1` | `IMPLEMENTED_WITH_DEVIATIONS` | `NOT_RETAINED` | `HIGH` | [`milestones/M5.5B.md`](milestones/M5.5B.md) |
| M5.5C | `4bc2310` | `IMPLEMENTED_WITH_DEVIATIONS` | `NOT_RETAINED` | `HIGH` | [`milestones/M5.5C.md`](milestones/M5.5C.md) |
| M6A-1 | `e4f4c00` | `IMPLEMENTED_WITH_DEVIATIONS` | `NOT_RETAINED` | `HIGH` | [`milestones/M6A-1.md`](milestones/M6A-1.md) |
| M6A-2B | `60ccc2d` | `IMPLEMENTED_WITH_DEVIATIONS` | `NOT_RETAINED` | `HIGH` | [`milestones/M6A-2B.md`](milestones/M6A-2B.md) |
| M6B | `928be44` | `IMPLEMENTED_WITH_DEVIATIONS` | `NOT_RETAINED` | `HIGH` | [`milestones/M6B.md`](milestones/M6B.md) |
| M6B-3 | `53fa6c4` | `IMPLEMENTED_WITH_DEVIATIONS` | `NOT_RETAINED` | `HIGH` | [`milestones/M6B-3.md`](milestones/M6B-3.md) |
| M6B-4A | `3c7c708` | `IMPLEMENTED_WITH_DEVIATIONS` | `NOT_RETAINED` | `HIGH` | [`milestones/M6B-4A.md`](milestones/M6B-4A.md) |
| M6B-4C | `4468a62` | `IMPLEMENTED_BUT_UNUSED` | `NOT_RETAINED` | `HIGH` | [`milestones/M6B-4C.md`](milestones/M6B-4C.md) |
| M7B-1A-R2 | `19f77a3` | `IMPLEMENTED_WITH_DEVIATIONS` | `NOT_RETAINED` | `HIGH` | [`milestones/M7B-1A-R2.md`](milestones/M7B-1A-R2.md) |
| M7B-1B | `7c7352a` | `IMPLEMENTED_WITH_DEVIATIONS` | `NOT_RETAINED` | `HIGH` | [`milestones/M7B-1B.md`](milestones/M7B-1B.md) |
| M7B-2A | `30b99eb` | `IMPLEMENTED_WITH_DEVIATIONS` | `NOT_RETAINED` | `HIGH` | [`milestones/M7B-2A.md`](milestones/M7B-2A.md) |
| M7B-2B/R2-R4 | `3f7bbc7` | `PRELIMINARY_IMPLEMENTATION` | `NOT_RETAINED` | `HIGH` | [`milestones/M7B-2B-R2-R4.md`](milestones/M7B-2B-R2-R4.md) |

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
M5 begins at 6cbade0ea53f1652d44bb92f92831a0c8daf62c5. It is reconstructed
as a shared M5/M5.5A commit with M5-specific import-blocking deviations.
```
