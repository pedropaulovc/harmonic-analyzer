"""MHA-PD-23 transgear pin: the sheet's notes owner.

The build writes the Manufacturing Notes property from
``pd_transgear_pin_callouts.DRAWING_NOTES``; this module names that text as
the notes owner, ahead of the spec's retired ``DRAWING_NOTES``, so the
feature manifest carries the notes the sheet prints (notes 1 and 2 that the
declared features call out). The part build does not import it, so it
re-keys no part.
"""

from pd_transgear_pin_callouts import DRAWING_NOTES as _PRINTED

DRAWING_NOTES = _PRINTED
