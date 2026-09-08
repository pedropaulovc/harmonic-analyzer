# Rack finish attachment control

The first complete rack finish-layout trial at `010840e1` failed before saving:
the strict semantic attachment guard rejected the repositioned finish. Both
source hashes remained unchanged. The failed run's `outputs` field records
files already on disk, not a successful replacement rack drawing.

The owned unsaved drawing and the earlier saved production drawing supplied
a direct native comparison. The saved control had one attached edge,
`IsSame == 1`, and was non-dangling. The failed candidate had no attached
entities despite `IsDangling == False`. A non-dangling check alone would
therefore have accepted the lost association.

The [point trials](probes/production-010840e1/finish-point-trials.json) varied
the calls on that unsaved candidate, retaining the source and saved control
bytes:

- `SetLeaderAttachmentPointAtIndex` returned true but removed the association
  at the current exact XYZ, the right-rim XY with the original Z, and the
  right-rim XY with source-rim Z. These are the tested call shapes, not a claim
  about every possible SolidWorks context.
- `SetAttachedEntities` alone restored exact edge identity but routed the
  leader back to the original lower-left attachment point.
- Selecting the resolved bore edge through `IEntity.Select4`, with its view
  and right-rim selection point in `ISelectData`, before `SetAttachedEntities`
  preserved exact edge identity and the right-rim route. This remains semantic
  entity selection; the point is not used to search for an entity.

The production correction must require that explicit selection and
reattachment sequence, verify selection and resulting attachment identity,
and reject a failed rebuild or dangling/empty/wrong attachment. The full
production lifecycle additionally verifies rim termination, current finish
ink, clearance and source-byte preservation after cold reopen and move/scale.
These experimental observations alone do not establish final print acceptance.
