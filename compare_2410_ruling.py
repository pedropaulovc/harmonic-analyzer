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

# Proposed purchased rack: SDP/SI S1811Y-RB-2P, 32 DP 20 deg, 416 stainless,
# face .230 +-.005, height .480 +.000/-.002, pitch line .4487 above the base.
NEW_FACE = 0.230 * IN
NEW_FACE_BAND = 0.005 * IN
NEW_HEIGHT = 0.480 * IN
NEW_PITCH_HEIGHT = 0.4487 * IN
NEW_ROOT_FROM_BASE = NEW_PITCH_HEIGHT - F.DEDENDUM_FACTOR * F.MODULE_MM
new_base_y = crest_y + NEW_HEIGHT
new_rail_height = rail_top - new_base_y
new_tap_y_local = screw_row_y - new_base_y
# Rack front set back from the rail's (platen's) front face: keeps the 12T
# pinion's full depth over the rack's front (today's margin 0.163 at the
# worst case with the strip's .62 inset) and air to the rear bushing.
SETBACK = 1.0
SETBACK_BAND = 0.25
front_margin_today = A.FEED.FULL_DEPTH_MIN - A.RACK_FRONT_FROM_SLEEVE_REAR_WORST
front_margin_new = front_margin_today + (SETBACK - SETBACK_BAND) - A.RACK_TEETH_Z_INSET
bushing_other_terms = (
    A.BUSHING_RACK_AIR_NOMINAL - A._RACK_THICKNESS_BAND - A.BUSHING_RACK_AIR_WORST
)
new_rack_back = zc(A.BAR_FRONT_Z) + SETBACK + NEW_FACE
bushing_front = zc(A.REAR_BUSHING_Z0) - RB.LENGTH
bushing_air_nominal_new = bushing_front - new_rack_back
bushing_air_worst_new = (
    bushing_air_nominal_new - NEW_FACE_BAND - SETBACK_BAND - bushing_other_terms
)

# Rack screws: McMaster 91792A108 #4-40 x 3/8 pan head (the MHA-PD-VN-60 lock
# screw), down through the rail's top into blind taps in the rack's base.
SCREW_LEN = 0.375 * IN
SCREW_MAJOR = 0.112 * IN
PAN_HEAD_DIA = 0.219 * IN
PAN_HEAD_H = 0.080 * IN
CB_DIA = 0.250 * IN
CB_DEPTH = 0.145 * IN
CLEAR_DIA = 0.120 * IN  # close fit: the rack is transfer-drilled through it
under_head = new_rail_height - CB_DEPTH
reach_into_rack = SCREW_LEN - under_head
FIRST_THREAD_LOSS = IN / 40.0
engagement = reach_into_rack - FIRST_THREAD_LOSS
TAP_FULL = 0.25 * IN
TAP_DRILL = 0.30 * IN
solid_under_drill = NEW_ROOT_FROM_BASE - TAP_DRILL
rack_screw_x = tuple(
    (G.SCREW_STATION_X[i] + G.SCREW_STATION_X[i + 1]) / 2.0 for i in range(4)
)
nearest_tap = min(
    abs(x - s) for x in rack_screw_x for s in (*G.SCREW_STATION_X, *G.HOLE_X)
)
rack_z_centre = zc(A.BAR_FRONT_Z) + SETBACK + NEW_FACE / 2.0
pinion_axis_y = pitch_y - F.PITCH_DIA / 2.0
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
rack_front = t + SETBACK
ax.add_patch(Rectangle((t, new_base_y), rail_depth, new_rail_height, fc="0.45", ec="k"))
ax.text(t + rail_depth + 0.5, new_base_y + 4.5, "bottom rail\n(PD-11 section,\n0.84 taller)",
        ha="left", fontsize=6.5)
ax.add_patch(Rectangle((rack_front, crest_y), NEW_FACE, NEW_HEIGHT, fc="#bfc5cc", ec="k"))
for k in range(3):
    ax.plot([rack_front, rack_front + NEW_FACE], [crest_y + k * 0.0, crest_y], color="k", lw=0.3)
ax.axhline(crest_y + (NEW_HEIGHT - NEW_ROOT_FROM_BASE), xmin=0, xmax=0, color="k")
ax.plot([rack_front, rack_front + NEW_FACE], [new_base_y - NEW_ROOT_FROM_BASE] * 2, "k:", lw=0.7)
ax.text(rack_front + NEW_FACE / 2, crest_y + 3.0, "rack\n.230 x .480\n416 SS", ha="center", fontsize=6.5)
# rack screw (section at a rack-screw station, between the platen screws)
cb_floor = rail_top - CB_DEPTH
ax.add_patch(Rectangle((rack_z_centre - CB_DIA / 2, cb_floor), CB_DIA, CB_DEPTH, fc="w", ec="k", lw=0.6))
ax.add_patch(Rectangle((rack_z_centre - PAN_HEAD_DIA / 2, cb_floor), PAN_HEAD_DIA, PAN_HEAD_H,
                       fc="#e06666", ec="k"))
ax.add_patch(Rectangle((rack_z_centre - SCREW_MAJOR / 2, cb_floor - SCREW_LEN), SCREW_MAJOR, SCREW_LEN,
                       fc="#e06666", ec="k", alpha=0.75))
ax.plot([rack_z_centre - 1.4, rack_z_centre + 1.4], [new_base_y - TAP_DRILL] * 2, color="r", lw=0.6)
ax.text(t + rail_depth + 0.5, 2.0, "4x #4-40 x 3/8\npan head (VN-60)\ninto blind taps\nin the rack",
        fontsize=6.5, color="#a00000")
ax.text(t - 0.3, crest_y + 2.0, "no solder", fontsize=7, color="g", ha="right")
ax.set_title("Proposed: rack screwed to the bottom rail on the bench;\n"
             "rail to the platen by the existing lower row (front unchanged)", fontsize=9)

# Rear elevation of the proposed rail + rack (looking forward from behind).
ax = fig.add_subplot(grid[1, :])
L = A.GUIDE_LENGTH
ax.add_patch(Rectangle((0, new_base_y), L, new_rail_height, fc="0.55", ec="k"))
ax.add_patch(Rectangle((0, crest_y), L, NEW_HEIGHT, fc="#bfc5cc", ec="k"))
for x in G.SCREW_STATION_X:
    ax.add_patch(Circle((x, screw_row_y), 1.42, fc="#c9a227", ec="k"))
for x in G.HOLE_X:
    ax.add_patch(Circle((x, screw_row_y), 1.42, fc="#7aa6d6", ec="k"))
for x in rack_screw_x:
    ax.plot([x, x], [rail_top, new_base_y - TAP_FULL], color="#e06666", lw=2.2)
    ax.add_patch(Rectangle((x - CB_DIA / 2, rail_top - CB_DEPTH), CB_DIA, CB_DEPTH, fc="none", ec="#a00000"))
ax.axhline(0, color="k", lw=0.5, ls=":")
ax.set_xlim(-5, L + 5)
ax.set_ylim(-5, rail_top + 3)
ax.set_aspect("equal")
ax.set_title(
    "Proposed rail + rack, rear elevation: 5 platen-screw taps (gold, existing lower row), 4 lock taps "
    "(blue, unchanged), 4 rack screws (red) midway between the platen screws",
    fontsize=9,
)
ax.set_xlabel("mm from the platen's left edge")

fig.suptitle(
    "#2410 owner ruling 2026-11-13: no backer, no solder; rack screwed to the rail, rail to the platen",
    fontsize=12,
)
fig.tight_layout()
fig.savefig(sys.argv[1], dpi=110)

print(f"crest {crest_y:.3f}  new rack base {new_base_y:.3f}  today rail bottom {rail_bottom_today:.3f}")
print(f"bottom rail height {new_rail_height:.3f} ({new_rail_height / IN:.4f} in), grows "
      f"{rail_bottom_today - new_base_y:.3f}; tap row local {new_tap_y_local:.3f} "
      f"({new_tap_y_local / IN:.4f} in), wall above tap major {new_rail_height - new_tap_y_local - SCREW_MAJOR / 2:.3f}")
print(f"rack root from base {NEW_ROOT_FROM_BASE:.3f}; under-head {under_head:.3f}; reach {reach_into_rack:.3f}; "
      f"engagement {engagement:.3f} = {engagement / SCREW_MAJOR:.2f} D; solid under drill {solid_under_drill:.3f}")
print(f"rack screw x {[round(x, 2) for x in rack_screw_x]}; nearest Z tap {nearest_tap:.2f}")
print(f"front full-depth margin today {front_margin_today:.3f}, proposed worst {front_margin_new:.3f}")
print(f"bushing air today worst {A.BUSHING_RACK_AIR_WORST:.3f}; proposed nominal "
      f"{bushing_air_nominal_new:.3f} worst {bushing_air_worst_new:.3f}")
print(f"head top below rail top {CB_DEPTH - PAN_HEAD_H:.3f}; rack z band {rack_front:.3f}..{rack_front + NEW_FACE:.3f}")
print(f"pinion axis y {pinion_axis_y:.3f}; pinion z {pinion_front:.3f}..{pinion_rear:.3f}")
