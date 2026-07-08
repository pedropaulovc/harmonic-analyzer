r"""Engineering drawing (SLDDRW + PDF) for the pen v-block (MHA-053).

The pilot ASME Y14.5-2018 drawing for the project: it turns the built
``pen-v-block.SLDPRT`` into a machinist-complete, third-angle multiview drawing
with model dimensions, center marks, a general-notes block and a title block,
then exports a PDF (and a PNG for the quick eye pass).

Why pen-v-block: a brass milled block (``machined_block`` +/-0.10, no fit class)
implicated in none of the open tolerance/DFM findings, so the print stamps a
genuinely correct, non-contradictory tolerance story (see
``docs/tolerance-gdt-assessment.md`` sec 11 for the drawing conventions honored
here: third-angle + projection symbol + standard in the title block, general
decimal-place tolerance block, center-lines on circular features, dimensions off
the model rather than hidden lines).

The generic drawing COM lives in the vendored adapter
(``solidworks_mcp.adapters.solidworks.drawing``); this script is only the
part-specific composition. Run (SolidWorks already open)::

    uv run python cad\scripts\build_drawing_pen_v_block.py
"""

from __future__ import annotations

import sys

from _common import CAD_ROOT, OUT_SLDPRT, check, force_rebuild, run_build

import _telemetry

from solidworks_mcp.adapters.solidworks import drawing as dwg

PART_NAME = "pen-v-block"
SLDPRT = (OUT_SLDPRT / f"{PART_NAME}.SLDPRT").resolve()
OUT_SLDDRW = CAD_ROOT / "out" / "slddrw"

# 1.5:1 keeps the 32 x 18 mm block readable (~48 x 27 mm) while leaving clear
# vertical room on the A-size (279 x 216 mm) sheet for the stacked front/top
# views, the notes band above them, and the baseline dimensions below.
SHEET_SCALE = (1.5, 1.0)

# ASME machinist-complete general notes. The fit story is the plain general
# block (no fit class on this part), so nothing tighter is asserted.
NOTES = [
    "NOTES:",
    "1. DIMENSIONS IN MILLIMETERS.",
    "2. INTERPRET DRAWING PER ASME Y14.5-2018.",
    "3. REMOVE ALL BURRS AND SHARP EDGES.",
    "4. MATERIAL: BRASS.",
    "5. UNLESS OTHERWISE SPECIFIED, GENERAL TOLERANCE .XX +/- 0.10 mm.",
    "6. MACHINED SURFACE FINISH 3.2 um Ra UNLESS OTHERWISE NOTED.",
]

# Title-block rows (top to bottom). A custom block, so it carries exactly the
# machinist-critical identity with no stock-template inch/company baggage. The
# scale is filled from the view's actual (auto-fit) scale, not assumed.
def _title_rows(scale_str: str) -> list[str]:
    return [
        "PEN V-BLOCK      MHA-053   REV A",
        f"MATERIAL: BRASS        SCALE {scale_str}",
        "THIRD ANGLE   mm   ASME Y14.5-2018",
    ]


async def build(adapter) -> dict[str, str]:
    # 1. Open the part; capture its on-disk path for the view references.
    res = await adapter.open_model(str(SLDPRT))
    check("open pen-v-block.SLDPRT", res)
    model_path = res.data.path
    _telemetry.info(f"model path: {model_path}")

    # 2. New (blank) drawing document -> becomes the active model. (Uses the
    #    drawing helper's template resolution, not the adapter's create_drawing,
    #    which reads the wrong template preference slot.)
    dwg.new_drawing(adapter)

    # 3. Sheet setup: ASME third-angle, A-size landscape; mm units (the part is
    #    an inch document, so the drawing must be flipped to mm). Standard views
    #    auto-fit their own scale, which is read back for the title block below.
    dwg.setup_sheet(adapter, scale=SHEET_SCALE, first_angle=False)
    dwg.set_units_mm(adapter, decimals=2)

    # ASME third-angle projection symbol (truncated-cone glyph), lower-right above
    # the title block. Drawn NOW, while the sheet is freshly active: sheet sketch
    # geometry lands in whatever view is active, and inserting dimensions later
    # leaves a view active, so drawing it after the views would put it inside one.
    dwg.add_third_angle_symbol(adapter, 0.186, 0.055, size=0.005)

    # 4. The three aligned standard views (third-angle) + a pictorial isometric.
    if not dwg.create_standard_views(adapter, model_path, first_angle=False):
        _telemetry.warn("standard views failed; placing front/top/right manually")
        dwg.place_view(adapter, model_path, "*Front", 0.09, 0.09)
        dwg.place_view(adapter, model_path, "*Top", 0.09, 0.15)
        dwg.place_view(adapter, model_path, "*Right", 0.17, 0.09)
    # Anchor the aligned front view in the lower-left (its top/right children
    # follow), then drop the redundant right projection: front + top + iso fully
    # define this part, and removing it frees the bottom-right for the title
    # block (fewest views that fully define the part is the ASME preference).
    # Projected views report no orientation name, so the right view is the
    # non-front view horizontally aligned with front (same y-center, greater x).
    views = list(dwg.iter_views(adapter))
    front = next(
        (v for v in views if dwg.orientation_name(adapter, v).lower().endswith("front")),
        None,
    )
    scale_str = "NTS"
    if front is not None:
        dwg.set_view_position(adapter, front, 0.108, 0.046)
        scale_str = dwg.format_scale(dwg.get_view_scale(adapter, front))
        _telemetry.info(f"actual view scale: {scale_str}")
        fbox = dwg.view_outline(adapter, front)
        fname = dwg.view_name(adapter, front)
        fcx = (fbox[0] + fbox[2]) / 2
        fcy = (fbox[1] + fbox[3]) / 2
        for v in list(dwg.iter_views(adapter)):
            if dwg.view_name(adapter, v) == fname:
                continue
            box = dwg.view_outline(adapter, v)
            if not box:
                continue
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            if abs(cy - fcy) < 0.02 and cx > fcx + 0.01:  # aligned right of front
                dwg.delete_view(adapter, v)
                break
    # The pictorial iso view carries no dimensions; remember it by name to skip.
    iso_view = dwg.place_view(adapter, model_path, "*Isometric", 0.238, 0.168)
    iso_name = dwg.view_name(adapter, iso_view)
    await force_rebuild(adapter)
    for view in dwg.iter_views(adapter):
        box = dwg.view_outline(adapter, view)
        if box:
            _telemetry.info(
                f"view {dwg.view_name(adapter, view)} "
                f"[{dwg.orientation_name(adapter, view)}] outline(mm)="
                f"({box[0]*1000:.0f},{box[1]*1000:.0f})-({box[2]*1000:.0f},{box[3]*1000:.0f})"
            )

    # 5. Per orthographic view: pull the parametric model dims + auto center marks
    #    on circular features (the two vertical bores read as circles in Top).
    n_views = 0
    all_anns: list = []
    for view in dwg.iter_views(adapter):
        name = dwg.view_name(adapter, view)
        if name == iso_name:
            continue  # no dimensions on the pictorial view
        n_views += 1
        anns = dwg.insert_model_dims(adapter, view, marked_only=False)
        all_anns.extend(anns)
        dwg.auto_center_marks(adapter, view, holes=True)
        _telemetry.info(f"view {name}: {len(anns)} dims inserted")
    # Every hole in this part is a through cut, so tag each diameter callout THRU.
    # The two identical Ø8 bores consolidate to one "2X Ø8.00 THRU". The front
    # hole seats the marker CLAMP SET SCREW: it is modeled at the M3 tap-drill
    # diameter (2.5 mm), so it is called out as the thread "M3X0.5 THRU", not as a
    # plain Ø2.5 drill (a set screw needs a tapped hole).
    thru = dwg.annotate_holes_thru(
        adapter, all_anns, text="THRU", thread_map={2.5: "M3X0.5"}
    )
    _telemetry.info(f"dimensioned {n_views} orthographic views; {thru} THRU callouts")
    await force_rebuild(adapter)

    # 6. General notes (upper-left) + title-block identity text (lower-right).
    #    5 mm line pitch keeps the 7-line block clear of the top view's upper
    #    bore-spacing dimension (a 6 mm pitch dropped note 6 onto the 11.00 dim).
    for i, line in enumerate(NOTES):
        dwg.add_note(adapter, line, 0.018, 0.205 - i * 0.005)
    for i, row in enumerate(_title_rows(scale_str)):
        dwg.add_note(adapter, row, 0.180, 0.032 - i * 0.008)
    await force_rebuild(adapter)

    # 7. Save SLDDRW + export PDF + PNG.
    OUT_SLDDRW.mkdir(parents=True, exist_ok=True)
    slddrw = OUT_SLDDRW / f"{PART_NAME}.SLDDRW"
    pdf = OUT_SLDDRW / f"{PART_NAME}.PDF"
    png = OUT_SLDDRW / f"{PART_NAME}.png"
    out = dwg.save_drawing(
        adapter, str(slddrw), pdf_path=str(pdf), png_path=str(png)
    )
    for key, path in out.items():
        _telemetry.info(f"artefact {key}: {path}")
    if "drawing" not in out:
        raise RuntimeError("drawing was not saved")
    return out


if __name__ == "__main__":
    sys.exit(run_build(build))
