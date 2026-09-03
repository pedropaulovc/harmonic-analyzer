r"""Pure-data dimensional contract shared by the knife-hanger stud and drawing.

PURE DATA: modeled nominals + the marked-dimension map, so one edit rebuilds
both the SLDPRT and SLDDRW recipe.  Thread designation and the catalog-owned
shank nominals are re-derived from the fastener catalog row -- ONE hardware
source; the drawing never invents a thread the part does not build.

ONE merged part (stud + integral washer + hex nut + turned collar + tip):
top.png stud crops (tmp_measure/crops/top_stud1/2.png) show a big hex nut on
a washer with a turned, center-drilled tip at both crossbar junctions.  The
lower THREAD_LEN threads into the knife-mount top (tapped 1/2-13 x 12) and is
MODELED at the reduced THREAD_DIA -- just under the mount's 10.716 tap drill
(repo convention: modeled thread engagement < tap drill) -- so the assembly
interference gate sees zero stud/mount overlap; the plain shank above rides
the casting crossbar's O13.49 close-clearance bore at the full major; washer,
hex, collar, and tip stand above the casting top face.  Two used in
summing.SLDASM at (x -15, z -83.972 / +90.148), bottom at machine y 987.45.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SPEC = fastener("knife-hanger-stud")

# Shank stack, bottom to top (local y=0 at the threaded bottom end):
THREAD_LEN = 12.0  # threaded into the knife-mount top
THREAD_DIA = 10.6  # modeled engagement dia: just under the mount's 10.716
#   1/2-13 tap drill (repo convention: thread engagement modeled < tap drill,
#   cf. the #10-24 screws at 3.45 vs 3.797), so the stud never interferes
#   with the knife-mount's tapped hole.  Never dimensioned: the thread
#   designation leadered to the neck owns that feature.
MOUNT_GAP = 0.25  # knife-mount top (999.45) to casting underside (999.7)
CROSSBAR_SPAN = 36.5  # through the casting crossbar (999.7 .. 1036.2)

SHANK_DIA = _SPEC.model_diameter_mm  # 1/2-13 nominal major (rides O13.49)
SHANK_LEN = _SPEC.length_mm  # 48.75 = THREAD_LEN + MOUNT_GAP + CROSSBAR_SPAN
THREAD = _SPEC.thread  # "1/2-13"
THREAD_DESIGNATION = f"{THREAD} UNC"  # leadered to the threaded neck

# Above the casting top face (local y 48.75), bottom to top:
WASHER_DIA = 28.0
WASHER_T = 2.5
NUT_AF = 19.0  # integral hex across-flats
NUT_H = 11.0
COLLAR_DIA = 11.0
COLLAR_H = 3.0
TIP_DIA = 6.0
TIP_LEN = 4.0
CDRILL_DIA = 2.0  # plain drilled centre in the tip end face
CDRILL_DEPTH = 1.5
SHOULDER_ROOT_R_MAX = 0.25  # permitted fillet at every turned shoulder root

TOTAL_LEN = SHANK_LEN + WASHER_T + NUT_H + COLLAR_H + TIP_LEN  # 69.25

# The end view carries the washer and collar diameters (the concentric
# stack's two larger circles) plus the hex across-flats as a drawing-native
# linear; the side view carries every stack length as an extrude DEPTH
# dimension (an axis-along-Y stud projects edge-on circle silhouettes that
# SolidWorks will not point-select) and the shank and tip diameters as
# linears across the profile.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WasherProfile": {"WasherDia"},
    "CollarProfile": {"CollarDia"},
    "ShankProfile": {"ShankDia"},
    "TipProfile": {"TipDia"},
    "Thread": {"ThreadLg"},
    "Shank": {"ShankLg"},
    "Washer": {"WasherT"},
    "HexNut": {"NutHt"},
    "Collar": {"CollarHt"},
    "Tip": {"TipLg"},
}
END_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "WasherProfile": {"WasherDia"},
    "CollarProfile": {"CollarDia"},
}
SIDE_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "ShankProfile": {"ShankDia"},
    "TipProfile": {"TipDia"},
    "Thread": {"ThreadLg"},
    "Shank": {"ShankLg"},
    "Washer": {"WasherT"},
    "HexNut": {"NutHt"},
    "Collar": {"CollarHt"},
    "Tip": {"TipLg"},
}

# Leadered callouts on the views (the drilled centre is hidden in the
# profile, so it is called out on the end view where its circle shows).
CENTER_DRILL_CALLOUT = f"<MOD-DIAM>{CDRILL_DIA:.2f} DRILL X {CDRILL_DEPTH:.2f} DEEP"

# Notes: every size is a dimension or a leadered callout, so the notes carry
# only the thread extent, the one-piece fact and the shoulder-root allowance
# (cad/docs/drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "\n".join(
    (
        "THREADED ON THE LOWER END ONLY; PLAIN SHANK ABOVE.",
        "ONE PIECE; NOT A LOOSE NUT AND WASHER.",
        f"TURNED SHOULDER ROOTS R{SHOULDER_ROOT_R_MAX:.2f} MAX.",
    )
)
END_VIEW_NOTE = "HEX-STACK END VIEW"
