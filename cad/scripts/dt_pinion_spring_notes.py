"""Feature-declaration facts of the MHA-DT-24 sheet that its drawing reads from
modules it does not otherwise import.

The strip's thickness band is the stock's (``dt_pinion_spring_section``,
McMaster-Carr 2325K19, +/-0.00075 in); the material specification prints it,
and ``draw_dt_pinion_spring``'s ``strip`` blank declares it so the traveler's
forming recipe can walk the thickness corners.  No part build imports this
module.
"""

from __future__ import annotations

from dt_pinion_spring_section import THICK_BAND as THICK_BAND
