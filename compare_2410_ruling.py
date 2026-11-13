"""#2410 owner ruling (2026-11-13): no backer, no solder. The rack is screwed
to the bottom rail on the bench, the rail to the platen by the existing lower
row. Side sections (today / proposed) next to the engineerguy end-on frame,
plus a rear elevation of the proposed rail + rack with every hole station.

Run from the worktree root:
  PYTHONPATH=cad/scripts uv run --frozen python compare_2410_ruling.py OUT.png
"""
import math
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
from PIL import Image

import build_pd_paper_drive_assembly as A
import build_pd_platen_guide as G
import pd_platen_rack_spec as rack
import pd_platen_spec as p
import pd_transgear_feed_pinion_spec as F
import pd_transgear_rear_bushing_spec as RB

IN = 25.4
FRAME = (
    "C:/src/harmonic-analyzer/references/engineerguy-youtube/stills/full/v4_t00135.png"
)

# Coordinates: y up from the platen's bottom edge, z rearward from the paper face.
def zc(z_machine: float) -> float:
    return z_machine - A.PLATE_FRONT_Z


def yc(y_machine: float) -> float:
    return y_machine - A.PLATE_Y0


t = A.PLATE_THICKNESS
crest_y = yc(A.RACK_TIP_Y)
pitch_y = yc(A.RACK_PITCH_Y)
rail_bottom_today = yc(A.GUIDE_Y[0])
rail_top = rail_bottom_today + A.GUIDE_HEIGHT
bar_bottom = rail_top + A.BOTTOM_RAIL_CLEARANCE
rail_depth = A.GUIDE_DEPTH
screw_row_y = p.GUIDE_HOLE_Y[0]

# Owner 2026-11-13: keep the 3/16 brass A 1B12-Y324 strip, smaller screws.
# The bottom rail grows down to the strip's top and seats it on its underside.
STRIP_H = rack.RACK_HEIGHT
STRIP_W = rack.RACK_THICKNESS
STRIP_H_ROOM = 0.003 * IN  # drawn-bar proxy (#2694)
strip_top_y = crest_y + STRIP_H
new_rail_height = rail_top - strip_top_y
new_tap_y_local = screw_row_y - strip_top_y
root_from_top = STRIP_H - rack.ADDENDUM - rack.DEDENDUM
root_from_top_worst = root_from_top - STRIP_H_ROOM
TAN20 = math.tan(math.radians(20.0))
tooth_at_root = rack.PITCH / 2.0 + 2.0 * rack.DEDENDUM * TAN20


def tooth_width_below_root(d: float) -> float:
    return tooth_at_root - 2.0 * d * TAN20


# Rack front set back from the rail's (platen's) front face so the 12T's full
# depth still covers the strip's front (today: .62 inset, margin 0.163).
SETBACK = 1.0
SETBACK_BAND = 0.25
front_margin_today = A.FEED.FULL_DEPTH_MIN - A.RACK_FRONT_FROM_SLEEVE_REAR_WORST
front_margin_new = front_margin_today + (SETBACK - SETBACK_BAND) - A.RACK_TEETH_Z_INSET
bushing_other_terms = (
    A.BUSHING_RACK_AIR_NOMINAL - A._RACK_THICKNESS_BAND - A.BUSHING_RACK_AIR_WORST
)
bushing_front = zc(A.REAR_BUSHING_Z0) - RB.LENGTH
strip_back_worst = t + SETBACK + SETBACK_BAND + STRIP_W + STRIP_H_ROOM
bushing_air_worst_new = bushing_front - strip_back_worst - bushing_other_terms
pinion_axis_y = pitch_y - F.PITCH_DIA / 2.0
bushing_top_y = pinion_axis_y + RB.OD / 2.0
rail_bushing_y_gap = strip_top_y - bushing_top_y

# Screws: the existing #0-80 x 1/4 slotted fillister, McMaster 91794A055
# (MHA-PD-VN-55), used at its stock length (no trimming).
import _mcmaster_91794a055 as SCR

SCREW_MAJOR = SCR.SHANK_DIA
HEAD_DIA = SCR.HEAD_DIA
HEAD_H = SCR.HEAD_H
THREAD_PITCH = SCR.PITCH
UNDER_HEAD_FLOOR = 0.128 * IN  # rail left under the head
CB_DIA = 0.110 * IN  # #35 drill, from the rail top
CLEAR_DIA = 0.067 * IN  # #51 close clearance through the floor
TAP_DRILL = 0.0465 * IN  # #56
CUT_LEN = SCR.SHANK_LEN
STOCK_BAND = 0.03 * IN  # +0/-.03 (pd_vn_transgear_disc_screw_spec.STOCK_LENGTH_BAND)
reach = (CUT_LEN - STOCK_BAND - UNDER_HEAD_FLOOR, CUT_LEN - UNDER_HEAD_FLOOR)
engagement = tuple(r - THREAD_PITCH for r in reach)
FULL_THREAD = 0.122 * IN
DRILL_DEPTH = 0.130 * IN  # full diameter
point = TAP_DRILL / 2.0 / math.tan(math.radians(59.0))
cb_depth = new_rail_height - UNDER_HEAD_FLOOR
below_root_drill = DRILL_DEPTH - root_from_top_worst
below_root_thread = FULL_THREAD - root_from_top_worst
below_root_point = DRILL_DEPTH + point - root_from_top_worst
# Stations: a whole number of circular pitches apart, centred on the platen,
# so once one hole sits over a tooth all of them do.
N_PITCH = 22
centre = G.SCREW_STATION_X[2]
rack_screw_x = tuple(centre + k * N_PITCH * rack.PITCH / 2.0 for k in (-3, -1, 1, 3))
nearest_tap = min(
    abs(x - s) for x in rack_screw_x for s in (*G.SCREW_STATION_X, *G.HOLE_X)
)
strip_front = t + SETBACK
screw_z = strip_front + STRIP_W / 2.0
pinion_rear = zc(A.FEED_Z0)
pinion_front = pinion_rear - F.FACE_WIDTH

fig = plt.figure(figsize=(17, 12.5))
grid = fig.add_gridspec(2, 3, height_ratios=(1.25, 0.75), width_ratios=(1.2, 1.0, 1.0))

ax = fig.add_subplot(grid[0, 0])
img = Image.open(FRAME)
ax.imshow(img.crop((420, 0, 1400, 760)))
ax.set_title(
    "Original, end-on (engineerguy video 4/4, 2:15): one solid brass rack bar,\n"
    "teeth on its lower face, seated straight against the dark steel rail; no backer",
    fontsize=9,
)
ax.axis("off")


def platen_and_bar(ax):
    ax.add_patch(Rectangle((0, -8), t, 38, fc="0.3", ec="k"))
    ax.text(t / 2, 28, "PD-02\nplaten", ha="center", va="top", fontsize=7, color="w")
    ax.add_patch(
        Rectangle((zc(A.BAR_FRONT_Z), bar_bottom), A.BAR_DEPTH, 30 - bar_bottom,
                  fc="0.88", ec="0.5", ls="--")
    )
    ax.text(zc(A.BAR_FRONT_Z) + A.BAR_DEPTH / 2, bar_bottom + 2.5, "support bar PD-07",
            ha="center", fontsize=7)
    ax.add_patch(
        Rectangle((pinion_front, pinion_axis_y - F.OUTSIDE_DIA / 2), F.FACE_WIDTH,
                  F.OUTSIDE_DIA, fc="#d9d9d9", ec="k", alpha=0.8)
    )
    ax.axhline(pitch_y, color="g", lw=0.6, ls="--")
    ax.text(pinion_front + 0.3, pinion_axis_y - 1.0, "12T feed pinion PD-10\n(set by feel)",
            fontsize=6.5)
    ax.add_patch(
        Rectangle((bushing_front, pinion_axis_y - RB.OD / 2), RB.LENGTH, RB.OD,
                  fc="#c0c0ff", ec="k")
    )
    ax.text(bushing_front + RB.LENGTH / 2, pinion_axis_y + RB.OD / 2 + 0.4, "rear\nbushing",
            ha="center", fontsize=6.5)
    # existing lower-row platen screw (fillister, from the front, into the rail)
    head_h = p.CBORE_DEPTH - p.HEAD_RECESS
    ax.add_patch(Rectangle((p.HEAD_RECESS, screw_row_y - 2.32), head_h, 4.65, fc="#c9a227", ec="k"))
    ax.add_patch(Rectangle((p.CBORE_DEPTH, screw_row_y - 1.42), 6.35, 2.84,
                           fc="#c9a227", ec="k", alpha=0.6))
    ax.axvline(0, color="b", lw=0.8)
    ax.text(-0.3, 22, "paper\nface", ha="right", fontsize=7, color="b")
    ax.axhline(0, color="k", lw=0.5, ls=":")
    ax.text(-0.3, 0.3, "platen edge", ha="right", fontsize=6.5)
    ax.set_xlim(-6, 24)
    ax.set_ylim(-13, 28)
    ax.set_aspect("equal")
    ax.set_xlabel("mm rearward from the paper face")
    ax.set_ylabel("mm above the platen's bottom edge")


ax = fig.add_subplot(grid[0, 1])
platen_and_bar(ax)
backer_top = crest_y + rack.BAR_HEIGHT
ax.add_patch(Rectangle((t, crest_y + rack.RACK_HEIGHT), rack.BAR_THICKNESS,
                       rack.BACKER_HEIGHT, fc="#b08d57", ec="k"))
ax.text(t + 3, backer_top - 3.5, "PD-05\nbacker", ha="center", fontsize=7)
ax.add_patch(Rectangle((zc(A.RACK_TEETH_FRONT_Z), crest_y), A.RACK_TEETH_THICKNESS,
                       rack.RACK_HEIGHT, fc="#c9a227", ec="k"))
ax.text(zc(A.RACK_TEETH_FRONT_Z) + 2.4, crest_y + 1.5, "3/16 rack", ha="center", fontsize=6.5)
ax.add_patch(Rectangle((t, rail_bottom_today), rail_depth, A.GUIDE_HEIGHT, fc="0.45", ec="k"))
ax.text(t + rail_depth / 2, rail_bottom_today + 5.2, "PD-11 rail", ha="center", fontsize=7, color="w")
ax.text(t - 0.3, crest_y + 2.0, "2 solder\njoints", fontsize=7, color="red", ha="right")
ax.set_title("Today: rack soldered to the PD-05 backer, backer soldered\n"
             "to the platen; PD-11 rail screwed on above it", fontsize=9)

ax = fig.add_subplot(grid[0, 2])
platen_and_bar(ax)
ax.add_patch(Rectangle((t, strip_top_y), rail_depth, new_rail_height, fc="0.45", ec="k"))
ax.text(t + rail_depth + 0.5, strip_top_y + 6.0, "bottom rail,\nown part:\nPD-11 section\n+8.27 taller", fontsize=6.5)
ax.add_patch(Rectangle((strip_front, crest_y), STRIP_W, STRIP_H, fc="#c9a227", ec="k"))
ax.plot([strip_front, strip_front + STRIP_W], [strip_top_y - root_from_top] * 2, "k:", lw=0.7)
ax.text(t + rail_depth + 0.5, -10.5, "3/16 brass rack\nA 1B12-Y324\n(unchanged)", fontsize=6.5)
cb_floor = strip_top_y + UNDER_HEAD_FLOOR
ax.add_patch(Rectangle((screw_z - CB_DIA / 2, cb_floor), CB_DIA, rail_top - cb_floor, fc="w", ec="k", lw=0.5))
ax.add_patch(Rectangle((screw_z - HEAD_DIA / 2, cb_floor), HEAD_DIA, HEAD_H, fc="#e06666", ec="k", lw=0.5))
ax.add_patch(Rectangle((screw_z - SCREW_MAJOR / 2, cb_floor - CUT_LEN), SCREW_MAJOR, CUT_LEN,
                       fc="#e06666", ec="k", lw=0.5))
ax.text(t + rail_depth + 0.5, strip_top_y + 0.3, "4x #0-80 x 1/4\nfillister (VN-55\nSKU), stock length,\ninto taps in the\nstrip top",
        fontsize=6.5, color="#a00000")
ax.text(t - 0.3, crest_y + 2.0, "no solder", fontsize=7, color="g", ha="right")
ax.set_title("Proposed: 3/16 brass rack screwed up under the bottom rail on\n"
             "the bench; rail to the platen by the existing lower row", fontsize=9)

# Rear elevation of the proposed rail + rack (looking forward from behind).
bottom = grid[1, :].subgridspec(1, 2, width_ratios=(3.2, 1.0))
ax = fig.add_subplot(bottom[0, 0])
L = A.GUIDE_LENGTH
ax.add_patch(Rectangle((0, strip_top_y), L, new_rail_height, fc="0.55", ec="k"))
ax.add_patch(Rectangle((0, crest_y), L, STRIP_H, fc="#c9a227", ec="k"))
for x in G.SCREW_STATION_X:
    ax.add_patch(Circle((x, screw_row_y), 1.42, fc="#c9a227", ec="k"))
for x in G.HOLE_X:
    ax.add_patch(Circle((x, screw_row_y), 1.42, fc="#7aa6d6", ec="k"))
for x in rack_screw_x:
    ax.add_patch(Rectangle((x - CB_DIA / 2, cb_floor), CB_DIA, rail_top - cb_floor, fc="none", ec="#a00000"))
    ax.plot([x, x], [cb_floor, strip_top_y - FULL_THREAD], color="#e06666", lw=1.6)
ax.axhline(0, color="k", lw=0.5, ls=":")
ax.set_xlim(-5, L + 5)
ax.set_ylim(-5, rail_top + 3)
ax.set_aspect("equal")
ax.set_title(
    "Proposed rail + rack, rear elevation: 5 platen-screw taps (gold, existing lower row), 4 lock taps "
    f"(blue, unchanged), 4 rack screws (red) {N_PITCH} rack pitches apart, each over a tooth",
    fontsize=9,
)
ax.set_xlabel("mm from the platen's left edge")

ax = fig.add_subplot(bottom[0, 1])
# Strip end-on along its length (x), crest down, 10:1-ish: one tooth under a tap.
top = 0.0
root = -root_from_top_worst
pitch_line = root - rack.DEDENDUM
crest = pitch_line - rack.ADDENDUM
half_p = rack.PITCH / 2.0
xs, ys = [-1.6 * rack.PITCH, -1.6 * rack.PITCH], [top, root]
for k in (-1, 0, 1):
    c = k * rack.PITCH
    w_root = tooth_at_root / 2.0
    w_crest = (rack.PITCH / 2.0 - 2.0 * rack.ADDENDUM * TAN20) / 2.0
    xs += [c - w_root, c - w_crest, c + w_crest, c + w_root]
    ys += [root, crest, crest, root]
xs += [1.6 * rack.PITCH, 1.6 * rack.PITCH]
ys += [root, top]
ax.fill(xs, ys, fc="#c9a227", ec="k", lw=0.7)
for cx, ok in ((0.0, True), (half_p, False)):
    colour = "g" if ok else "r"
    ax.add_patch(Rectangle((cx - TAP_DRILL / 2, top - DRILL_DEPTH), TAP_DRILL, DRILL_DEPTH, fc="none", ec=colour, lw=1.0))
    ax.plot([cx - TAP_DRILL / 2, cx, cx + TAP_DRILL / 2], [top - DRILL_DEPTH, top - DRILL_DEPTH - point, top - DRILL_DEPTH], color=colour, lw=1.0)
    ax.plot([cx - SCREW_MAJOR / 2] * 2, [top, top - FULL_THREAD], color=colour, lw=0.5, ls="--")
    ax.plot([cx + SCREW_MAJOR / 2] * 2, [top, top - FULL_THREAD], color=colour, lw=0.5, ls="--")
ax.text(0.0, top + 0.25, "over a tooth:\nstays in metal", ha="center", fontsize=6.5, color="g")
ax.text(half_p + 0.3, crest - 0.3, "over a space:\nbreaks through", ha="left", fontsize=6.5, color="r")
ax.set_aspect("equal")
ax.set_xlim(-1.7 * rack.PITCH, 2.6 * rack.PITCH)
ax.set_ylim(crest - 1.0, top + 1.2)
ax.set_title("#0-80 tap in the strip top, shortest strip\n(drill solid, thread dashed)", fontsize=9)
ax.set_xlabel("mm along the rack")

fig.suptitle(
    "#2410 owner rulings 2026-11-13: no backer, no solder; the 3/16 brass rack screwed to the rail, rail to the platen",
    fontsize=12,
)
fig.tight_layout()
fig.savefig(sys.argv[1], dpi=110)

print(f"strip top {strip_top_y:.3f}; rail bottom today {rail_bottom_today:.3f}; rail height {new_rail_height:.3f} "
      f"({new_rail_height / IN:.4f} in), grows {rail_bottom_today - strip_top_y:.3f}; tap row local {new_tap_y_local:.3f} ({new_tap_y_local / IN:.4f})")
print(f"root from strip top {root_from_top:.3f} (worst {root_from_top_worst:.3f}); tooth at root {tooth_at_root:.3f}")
print(f"max reach vs full thread {reach[1]:.3f} <= {FULL_THREAD:.3f}"); print(f"reach {reach[0]:.3f}..{reach[1]:.3f}; engagement {engagement[0]:.3f}..{engagement[1]:.3f} = "
      f"{engagement[0] / SCREW_MAJOR:.2f}..{engagement[1] / SCREW_MAJOR:.2f} D; full thread {FULL_THREAD:.3f}; drill {DRILL_DEPTH:.3f} + point {point:.3f}")
print(f"over a tooth (worst strip): drill {below_root_drill:.3f} below root, tooth width there {tooth_width_below_root(below_root_drill):.3f} vs drill {TAP_DRILL:.3f}; "
      f"thread {below_root_thread:.3f} below root, width {tooth_width_below_root(below_root_thread):.3f} vs major {SCREW_MAJOR:.3f}; point tip {below_root_point:.3f} below root")
print(f"over a space: drill breaks {below_root_drill:.3f} into the gap")
print(f"counterbore depth from rail top {cb_depth:.3f} ({cb_depth / IN:.3f}); head top below rail top {cb_depth - HEAD_H:.3f}")
print(f"rack screw x {[round(x, 2) for x in rack_screw_x]}; nearest Z tap {nearest_tap:.2f}")
print(f"front full-depth margin today {front_margin_today:.3f}, proposed worst {front_margin_new:.3f}")
print(f"bushing air today worst {A.BUSHING_RACK_AIR_WORST:.3f}; proposed worst {bushing_air_worst_new:.3f}; rail bottom over bushing top {rail_bushing_y_gap:.3f}")
