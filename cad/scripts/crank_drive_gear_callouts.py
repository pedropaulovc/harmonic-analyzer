"""Source-authored manufacturing text shared by the drive gear and its drawing.

Separate from geometric scalars consumed by the swing-platform recipe.
"""

DIMENSION_CALLOUTS = {
    # Reamed slip fit on the crankshaft journal (nominal-or-under, like the
    # arbor journals): min 0.03 diametral clearance, inside the project's
    # 0.025..0.075 shaft-in-bushing policy. Also settles which tolerance-block
    # row governs the bore (neither .XX +/-0.51 nor DRILLED +0.10/0 -- the
    # model dimension's own limits do).
    "BoreDia": "THRU - REAM",
}
