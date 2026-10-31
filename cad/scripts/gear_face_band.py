"""The faced-width band every gear in the solid cone stack shares.

Its own module, not ``cone_pitch``: only the gears and the stack read it, so
editing it rebuilds them and nothing else.
"""

# (upper, lower) faced width of every gear in the solid cone stack -- the
# twenty cone gears and the 64T crank-drive gear (dt_cone_gear_stack): the
# cylinder bank's L20 d' rule, +/-.001 in per gear (#290).  One constant, so
# the two gear sheets and the stack cannot fork.
GEAR_FACE_WIDTH_BAND = (0.0254, -0.0254)
