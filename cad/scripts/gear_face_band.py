"""The faced-width band of the 64T crank-drive gear (MHA-DT-07).

Its own module, not ``cone_pitch``: only the 64T and the stacks that read it
import it, so editing it rebuilds them and nothing else.  The twenty cone
gears carry their own, wider band (dt_cone_gear_spec.FACE_WIDTH_BAND, #2314).
"""

# (upper, lower) faced width of the 64T crank-drive gear (dt_cone_gear_stack):
# the cylinder bank's L20 d' rule, +/-.001 in per gear (#290).
GEAR_FACE_WIDTH_BAND = (0.0254, -0.0254)
