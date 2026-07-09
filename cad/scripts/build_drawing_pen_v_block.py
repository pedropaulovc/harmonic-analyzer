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

Two layers back this script: the GENERIC drawing COM (views, dims, callouts, the
cone glyph, save) lives in the vendored adapter (``solidworks_mcp.adapters.
solidworks.drawing``), and the harmonic-analyzer CONVENTIONS shared across parts
(template, notes, title rows, projection-symbol placement) live in ``_drawing``.
This script is only the pen-v-block COMPOSITION: its view layout and the curated
dimension scheme. Run (SolidWorks already open)::

    uv run python cad\scripts\build_drawing_pen_v_block.py
"""

from __future__ import annotations

import sys

from _common import CAD_ROOT, OUT_SLDPRT, check, force_rebuild, run_build

import _drawing as pd
import _telemetry

from solidworks_mcp.adapters.solidworks import drawing as dwg

PART_NAME = "pen-v-block"
MATERIAL = "Brass"
SLDPRT = (OUT_SLDPRT / f"{PART_NAME}.SLDPRT").resolve()
# Dedicated output homes: the native drawing under cad/out/slddrw, the PDF under
# cad/out/pdf, and the render under cad/out/png as ``<part>_drawing.png`` (the
# ``_drawing`` suffix keeps it distinct from the part-render PNGs in cad/out/png/<part>/).
OUT_SLDDRW = CAD_ROOT / "out" / "slddrw"
OUT_PDF = CAD_ROOT / "out" / "pdf"
OUT_PNG = CAD_ROOT / "out" / "png"

# 1.5:1 keeps the 32 x 18 mm block readable (~48 x 27 mm) while leaving clear
# vertical room on the A-size (279 x 216 mm) sheet for the stacked front/top
# views, the notes band above them, and the baseline dimensions below. (Standard
# views auto-fit to 2:1; the title block reads the ACTUAL scale back.)
SHEET_SCALE = (1.5, 1.0)

# Two hole-callout groups are expected: "2X Ø8.00 THRU" (the two consolidated bores)
# and the set-screw hole's NATIVE Hole Wizard callout ("5-40 UNC / THRU"). The model
# now carries the #5-40 thread (a real tapped Hole Wizard feature -- see
# build_pen_v_block), so the thread text comes straight from the model with no thread
# map. Asserting this before export guards against SolidWorks silently inserting no
# model dims (empty views -> a PDF missing the make-critical callouts) going green.
EXPECTED_HOLE_CALLOUTS = 2

# SolidWorks also auto-inserts a redundant descriptive note for the wizard hole
# ("#5-40 Tapped Hole") that duplicates the leadered thread callout -- drop it by text.
REDUNDANT_HOLE_NOTE = "Tapped Hole"

# Redundant auto-inserted dims to drop (curated by parametric NAME): one of the two
# identical Ø8 bore centrelines (both read 8.00 -> the 2X callout shares one), and
# the 20 mm TopRun, which the 32.00 overall + the two 6 mm chamfer legs already fix.
REDUNDANT_DIMS = ("Bore1Z", "TopRun")


async def build(adapter) -> dict[str, str]:
    # 1. Open the part; capture its on-disk path for the view references.
    res = await adapter.open_model(str(SLDPRT))
    check("open pen-v-block.SLDPRT", res)
    model_path = res.data.path
    _telemetry.info(f"model path: {model_path}")

    # 2. New drawing from the project template (falls back to the seat default).
    pd.new_drawing(adapter)

    # 3. Sheet setup: ASME third-angle, A-size landscape; mm units (the part is an
    #    inch document, so the drawing must be flipped to mm).
    dwg.setup_sheet(adapter, scale=SHEET_SCALE, first_angle=False)
    dwg.set_units_mm(adapter, decimals=2)

    # ASME third-angle projection symbol, lower-right above the title block. Drawn
    # NOW, while the sheet is freshly active: sheet sketch geometry lands in whatever
    # view is active, and inserting dimensions later leaves a view active, so drawing
    # it after the views would put it inside one. Raises if it could not be authored.
    pd.add_projection_symbol(adapter)

    # 4. The three aligned standard views (third-angle) + a pictorial isometric.
    #    Create3rdAngleViews2 makes the ALIGNED, projected set; fail loud if it can't
    #    (a resolvable model path is a precondition we just satisfied via open_model).
    #    No manual fallback: placing independent *Front/*Top/*Right loses the third-
    #    angle alignment/projection, so it would silently ship a non-conforming print.
    if not dwg.create_standard_views(adapter, model_path, first_angle=False):
        raise RuntimeError(
            "Create3rdAngleViews2 failed to place the aligned standard views; "
            "refusing to ship a drawing without a proper third-angle projection set"
        )
    # Anchor the aligned front view in the lower-left (its top/right children
    # follow), then drop the redundant right projection: front + top + iso fully
    # define this part, and removing it frees the bottom-right for the title block
    # (fewest views that fully define the part is the ASME preference). Projected
    # views report no orientation name, so the right view is the non-front view
    # horizontally aligned with front (same y-center, greater x).
    views = list(dwg.iter_views(adapter))
    front = next(
        (v for v in views if dwg.orientation_name(adapter, v).lower().endswith("front")),
        None,
    )
    # The front/top/iso set AND the title-block scale both depend on the front view;
    # a missing one means an incomplete print, so fail rather than ship it.
    if front is None:
        raise RuntimeError("front view was not created; refusing to save an incomplete print")
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

    # Every hole is a through cut -> tag each diameter callout THRU; the two identical
    # Ø8 bores consolidate to one "2X Ø8.00 THRU". The set-screw hole's native Hole
    # Wizard callout already reads "5-40 UNC" (the model carries the thread), so no
    # thread map: annotate_holes_thru just appends its THRU.
    thru = dwg.annotate_holes_thru(adapter, all_anns, text="THRU")
    if thru != EXPECTED_HOLE_CALLOUTS:
        raise RuntimeError(
            f"expected {EXPECTED_HOLE_CALLOUTS} hole-callout groups "
            f"(2X Ø8.00 THRU + the #5-40 set-screw callout), got {thru} -- model "
            "dimensions likely failed to insert; refusing to export an incomplete print"
        )
    # Drop SolidWorks' auto descriptive note ("#5-40 Tapped Hole"): the leadered
    # "5-40 UNC THRU" callout already carries the thread, so the note is a duplicate.
    dropped = dwg.remove_notes_matching(adapter, REDUNDANT_HOLE_NOTE)
    _telemetry.info(f"removed {dropped} redundant hole-description note(s)")

    # Curate the auto-inserted scheme into ASME form: drop the redundant duplicate
    # bore centreline + the intermediate TopRun (the overall + chamfer legs fix it).
    dwg.curate_dimensions(adapter, all_anns, delete=REDUNDANT_DIMS)
    # Explicit overall HEIGHT (18): the front view otherwise defines height only as
    # side-wall + chamfer leg, with no single overall figure (best-effort).
    if dwg.add_overall_dimension(adapter, front, vertical=True):
        _telemetry.info("added overall-height dimension")
    else:
        _telemetry.warn("overall-height dimension not added (edge selection missed)")
    _telemetry.info(f"dimensioned {n_views} orthographic views; {thru} hole callouts")
    await force_rebuild(adapter)

    # 6. General notes (upper-left) + title-block identity (lower-right), from the
    #    project shared conventions.
    pd.add_notes_block(adapter, pd.standard_notes(material=MATERIAL))
    pd.add_title_block(
        adapter,
        pd.title_rows(
            name="PEN V-BLOCK", number="MHA-053", rev="A",
            material=MATERIAL, scale_str=scale_str,
        ),
    )
    await force_rebuild(adapter)

    # 7. Save SLDDRW (cad/out/slddrw) + PDF (cad/out/pdf) + PNG (cad/out/png). Require
    #    ALL THREE: this is an SLDDRW + PDF + PNG deliverable, so a missing one fails.
    for d in (OUT_SLDDRW, OUT_PDF, OUT_PNG):
        d.mkdir(parents=True, exist_ok=True)
    slddrw = OUT_SLDDRW / f"{PART_NAME}.SLDDRW"
    pdf = OUT_PDF / f"{PART_NAME}.PDF"
    png = OUT_PNG / f"{PART_NAME}_drawing.png"
    out = dwg.save_drawing(adapter, str(slddrw), pdf_path=str(pdf), png_path=str(png))
    for key, path in out.items():
        _telemetry.info(f"artefact {key}: {path}")
    missing = {"drawing", "pdf", "png"} - out.keys()
    if missing:
        raise RuntimeError(f"drawing pipeline did not produce: {', '.join(sorted(missing))}")
    return out


if __name__ == "__main__":
    sys.exit(run_build(build))
