---
name: projection-symbol-third-angle
description: "The DRWDOT's projection symbol IS correct third-angle (circles on the frustum's SMALL-end side — orientation matters, not left/right). The 9b37bceb 'fix' + its runtime gate were the regression; #428 reverted both. Never re-add a circles-right-of-frustum assert."
metadata:
  type: project
---

Verified 2026-07-28 by eye on fresh renders (magnifying-bracket, arbor-pedestal,
template blob `0023983d`): the title-block symbol draws the two-circle view on
the LEFT and the frustum with its SMALL end pointing LEFT — circles adjacent to
the small end, which is the third-angle convention (view on the observer's
side). First-angle would put the circles by the LARGE end. **Left/right alone
says nothing** — both mirror forms of third-angle are valid.

History (why this keeps coming back):

- A blind machinist review (PR #354, spring-hook round 1) *claimed* the symbol
  was first-angle — accepted untested as a "repo-wide follow-up".
- `9b37bceb` (Jul 21) acted on it: flipped the template block AND added a
  runtime gate + test asserting `circle_x > frustum_x` in the block-definition
  sketch. The gate was **orientation-blind** — it never checked which way the
  frustum points, so it merely pinned the flipped block's coordinates.
- PR #428 (Jul 26) reverted all of it: the "fix" had made the printed sheets
  first-angle; the restored original was correct all along. The revert also
  removed the gate and its test.
- The `drawing-spec-purity` branch predated the revert; its rebase resurrected
  the gate (kept on the branch side of a modify/delete conflict), which then
  failed EVERY drawing task against main's restored template. Removed again in
  `4f6f44ae`. See [[stack-pinned-off-main-rots]] — same PR, same rot mode.

**How to apply:** if a projection-convention claim surfaces again, judge it
from a RENDER of the symbol (crop the title block; circles-by-small-end =
third angle), never from block-definition x-coordinates. Any future gate must
classify the frustum's taper direction, not left/right order.
