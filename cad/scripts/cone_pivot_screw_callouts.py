"""Source-authored manufacturing text shared by the pivot screw and its drawing.

Depend on the geometric/thread contract, never import this module back into it.
The base recipe consumes thread geometry without inheriting callout-map edits.
"""

from cone_pivot_screw_spec import THREAD_DESIGNATION

SIDE_DIMENSION_CALLOUTS = {
    "ThreadLg": THREAD_DESIGNATION,
}
