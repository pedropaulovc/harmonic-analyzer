"""Words the MHA-PD-26 sheet prints under its tap callout.

Kept out of ``pd_feed_rack_spec``, which the bottom guide, the shared screw and
the paper-drive assembly import, so rewording the callout re-keys only this
sheet.  This module reads the spec for every value it prints.
"""

from __future__ import annotations

from pd_feed_rack_spec import ENGAGEMENT_STATEMENT, MM_PER_IN, TAP_TOOTH_OFFSET_MAX

# Each tap's own limit about its tooth centre.  The tooth-wall stack and
# RV-03's ".000 MIN TO TOOTH ROOT" assume it; the stations' .XXX spacing from
# the first tap would admit twice it plus the strip's index error (codjiflo
# P2 on a17aebb).
TOOTH_CENTRE_STATEMENT = f"ON TOOTH CENTRES \u00b1{f'{TAP_TOOTH_OFFSET_MAX / MM_PER_IN:.3f}'.removeprefix('0')}"
# Rule 7/20: the taps stand on tooth centres, and their engagement (RV-02);
# their places along the strip are the stations' dimensions (rule 26).
TAP_CALLOUT_BELOW = f"{TOOTH_CENTRE_STATEMENT}\n{ENGAGEMENT_STATEMENT}"
