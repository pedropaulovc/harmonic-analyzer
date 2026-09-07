"""Source-authored manufacturing text shared by the fillister and its drawing.

Depend on the geometric/thread contract, never import this module back into it.
The platen-clip recipe consumes head geometry without inheriting callout edits.
"""

from fillister_screw_spec import THREAD_DESIGNATION

SIDE_DIMENSION_CALLOUTS = {"ShankLg": "UNDERHEAD LENGTH"}
DIMENSION_TEXT = {"ShankDia": THREAD_DESIGNATION}
