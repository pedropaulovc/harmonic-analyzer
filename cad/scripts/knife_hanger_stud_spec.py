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
#   with the knife-mount's tapped hole.
MOUNT_GAP = 0.25  # knife-mount top (999.45) to casting underside (999.7)
CROSSBAR_SPAN = 36.5  # through the casting crossbar (999.7 .. 1036.2)

SHANK_DIA = _SPEC.model_diameter_mm  # 1/2-13 nominal major (rides O13.49)
SHANK_LEN = _SPEC.length_mm  # 48.75 = THREAD_LEN + MOUNT_GAP + CROSSBAR_SPAN
THREAD = _SPEC.thread  # "1/2-13"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

# Above the casting top face (local y 48.75), bottom to top:
WASHER_DIA = 28.0
WASHER_T = 2.5
NUT_AF = 19.0  # integral hex across-flats
NUT_H = 11.0
COLLAR_DIA = 11.0
COLLAR_H = 3.0
TIP_DIA = 6.0
TIP_LEN = 4.0
CDRILL_DIA = 2.0  # cosmetic center-drill cut in the tip end face
CDRILL_DEPTH = 1.5

TOTAL_LEN = SHANK_LEN + WASHER_T + NUT_H + COLLAR_H + TIP_LEN  # 69.25

# The end view carries the washer diameter (the outermost circle of the
# concentric stack); the side view carries the thread/shank/nut/tip lengths
# as the extrude DEPTH dimensions (named ThreadLg/ShankLg/NutHt/TipLg in the
# build) -- an axis-along-Y stud projects edge-on circle silhouettes that
# SolidWorks will not point-select, so drawing-native edge dimensions cannot
# pick them.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WasherProfile": {"WasherDia"},
    "Thread": {"ThreadLg"},
    "Shank": {"ShankLg"},
    "HexNut": {"NutHt"},
    "Tip": {"TipLg"},
}
END_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "WasherProfile": {"WasherDia"},
}
SIDE_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "Thread": {"ThreadLg"},
    "Shank": {"ShankLg"},
    "HexNut": {"NutHt"},
    "Tip": {"TipLg"},
}

# thread_control_notes assumes a full-length thread; this stud is threaded on
# the lower THREAD_LEN only, so the thread contract is spelled out directly.
DRAWING_NOTES = "\n".join(
    (
        f"{THREAD_DESIGNATION} PER ASME B1.1-2024, "
        f"LOWER END X {THREAD_LEN:.2f} LONG.",
        "ACCEPT THREADS USING SYSTEM 21 PER ASME B1.3-2007 (R2022).",
        "DISTAL START CHAMFER C0.50 +/-0.05 X 45 DEG +/-1 DEG.",
        "THREAD LIMITS APPLY AFTER FINISH.",
        "THREADED END FACE PERPENDICULAR 0.05 TO THREAD "
        "PITCH-DIAMETER AXIS.",
        "THREAD GEOMETRY OMITTED IN VIEWS; SHANK OUTLINE REFERENCE ONLY.",
        f"THREADED END MODELED AT REDUCED DIA {THREAD_DIA:.2f}, "
        "UNDER 10.716 TAP DRILL.",
        "PLAIN SHANK ABOVE THREAD RIDES A 13.49 CLOSE-CLEARANCE BORE.",
        "INTEGRAL WASHER, HEX, COLLAR, AND TIP: TURN AND MILL FROM ONE BLANK.",
        f"WASHER DIA {WASHER_DIA:.2f} +/-0.10 X {WASHER_T:.2f} +/-0.10 HIGH.",
        f"HEX {NUT_AF:.2f} +/-0.10 ACROSS FLATS X {NUT_H:.2f} +/-0.10 HIGH.",
        "HEX CENTER WITHIN DIA 0.10 OF SHANK AXIS.",
        f"COLLAR DIA {COLLAR_DIA:.2f} +/-0.10 X {COLLAR_H:.2f} +/-0.10 HIGH.",
        f"TIP DIA {TIP_DIA:.2f} +/-0.10 X {TIP_LEN:.2f} +/-0.10 LONG.",
        f"CENTER DRILL TIP END FACE DIA {CDRILL_DIA:.2f} X "
        f"{CDRILL_DEPTH:.2f} DEEP (COSMETIC).",
        "WASHER BEARING FACE PERPENDICULAR 0.10 TO SHANK AXIS.",
    )
)
END_VIEW_NOTE = "HEX-STACK END VIEW"
