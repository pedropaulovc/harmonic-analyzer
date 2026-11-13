"""#2401 owner escalation figure: the original bend, the shop-made form, and
the finished radius each route leaves after springback.  Inch units."""

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

PHOTO = r"C:/src/harmonic-analyzer/references/albert-michelsons-harmonic-analyzer/ch19_images/page001_img01.jpeg"
OUT = r"C:/src/dfm2401/gooseneck-bend-options.png"

# Springback [calc]: unloading curvature = Mp / EI, 1/2 x .065 4130-N.
D, d = 0.5, 0.37
Z = (D**3 - d**3) / 6.0
I = math.pi / 64.0 * (D**4 - d**4)
E = 29.7e6


def finished(r_tool: float, yield_ksi: float) -> float:
    return 1.0 / (1.0 / r_tool - yield_ksi * 1e3 * Z / (E * I))


DIE_R = 3.0
FORM_R = 2.90
die = (finished(DIE_R, 63), finished(DIE_R, 75))
form = (finished(FORM_R, 63), finished(FORM_R, 75))

fig, axes = plt.subplots(1, 3, figsize=(16, 6.2), gridspec_kw={"width_ratios": [0.8, 1.25, 1.1]})

# (a) original photo, the bend.
ax = axes[0]
img = plt.imread(PHOTO)
ax.imshow(img[0:200, 250:440])
ax.set_title("(a) Original (ch19 img01): one smooth\n90° bend, bright bare tube", fontsize=10)
ax.axis("off")

# (b) the shop-made form, option B.
ax = axes[1]
R_TUBE = 0.25
GROOVE_BOTTOM = FORM_R - R_TUBE
RIM = 3.75
ax.add_patch(Circle((0, 0), RIM, fc="#d9dde3", ec="k", lw=1.2))
ax.add_patch(Circle((0, 0), GROOVE_BOTTOM, fc="none", ec="#555", lw=0.8, ls="--"))
ax.add_patch(Circle((0, 0), 0.27, fc="white", ec="k"))
# vise jaws (seen end-on they are behind/in front of the disc; drawn as the clamped band)
ax.add_patch(Rectangle((-3.12, -RIM - 0.2), 6.24, 1.9, fc="#8a8f99", alpha=0.45, ec="k"))
ax.text(0, -RIM + 0.55, "6 in vise grips the disc faces", ha="center", fontsize=8)
# tube before: tangent at the left, leg up, tail down past the pin
x0 = -FORM_R
ax.plot([x0, x0], [0, 7.0], color="#1f77b4", lw=6, alpha=0.35, solid_capstyle="butt")
ax.plot([x0, x0], [0, -2.47], color="#1f77b4", lw=6, alpha=0.35, solid_capstyle="butt")
ax.text(x0 - 0.35, 5.5, "leg before the pull", rotation=90, fontsize=8, color="#1f77b4", va="center")
# tube after: wrapped over the top, leg pointing right
th = [math.radians(a) for a in range(180, 85, -2)]
ax.plot([FORM_R * math.cos(t) for t in th], [FORM_R * math.sin(t) for t in th], color="#d62728", lw=6, solid_capstyle="butt")
ax.plot([0, 7.0], [FORM_R, FORM_R], color="#d62728", lw=6, solid_capstyle="butt")
ax.plot([x0, x0], [0, -2.47], color="#d62728", lw=6, solid_capstyle="butt")
ax.text(4.0, FORM_R + 0.45, "leg after the pull (hand, ~50 lbf at its end)", fontsize=8, color="#d62728", ha="center")
ax.annotate("", xy=(6.6, FORM_R + 0.15), xytext=(x0 + 0.1, 6.6), arrowprops=dict(arrowstyle="->", color="#444", connectionstyle="arc3,rad=-0.45"))
# tail pin: a 1/4-20 bolt across the groove, outside the tail
pin = (x0 - R_TUBE - 0.14, -1.0)
ax.add_patch(Circle(pin, 0.125, fc="k"))
ax.annotate("1/4-20 bolt across the groove\nholds the ~2 in tail (scrap)", xy=pin, xytext=(-7.2, -2.2), fontsize=8, arrowprops=dict(arrowstyle="-"))
ax.annotate(f"groove bottom R{GROOVE_BOTTOM:.2f}\n(tube centreline R{FORM_R:.2f},\nsized for springback)", xy=(GROOVE_BOTTOM * math.cos(math.radians(40)), GROOVE_BOTTOM * math.sin(math.radians(40))), xytext=(1.6, -1.6), fontsize=8, arrowprops=dict(arrowstyle="-"))
ax.text(0, RIM + 0.25, "6061 disc Ø7.5 x 1, groove .52 wide", ha="center", fontsize=8)
ax.text(-7.2, 6.6, "tube packed with dry sand,\nends plugged", fontsize=8)
ax.set_xlim(-7.5, 7.5)
ax.set_ylim(-4.2, 7.4)
ax.set_aspect("equal")
ax.set_title("(b) Option B: shop-made grooved form, in the vise", fontsize=10)
ax.axis("off")

# (c) finished centreline radius after springback, each route.
ax = axes[2]
rows = [
    ("print R3.0, .X band", (2.9, 3.1), "#bbbbbb"),
    ("A / D: 3 in CLR die", die, "#9467bd"),
    (f"B: form at R{FORM_R:.2f}", form, "#2ca02c"),
]
for i, (label, (lo, hi), colour) in enumerate(rows):
    ax.barh(i, max(hi - lo, 0.004), left=lo, height=0.5, color=colour)
    ax.text(hi + 0.01, i, f"R{lo:.2f}-{hi:.2f}", va="center", fontsize=9)
ax.axvspan(2.9, 3.1, color="#eeeeee", zorder=0)
ax.set_yticks(range(len(rows)), [r[0] for r in rows])
ax.invert_yaxis()
ax.set_xlim(2.8, 3.3)
ax.set_xlabel("finished bend centreline radius, in\n[calc: springback = Mp/EI, yield 63-75 ksi]")
ax.set_title("(c) Springback opens the radius:\nthe die finishes outside R3.0's band", fontsize=10)
ax.grid(axis="x", alpha=0.3)

fig.suptitle("#2401 MHA-SM-01: how the shop makes the R3.0 bend in 1/2 x .065 4130-N", fontsize=12)
fig.tight_layout()
fig.savefig(OUT, dpi=110)
print(OUT, die, form)
