r"""Reproduction script: maker's nameplate (book ch. 26, pp. 70-71).

The small brass plate screwed to the base dates and attributes the machine.
The ch.26 p.71 macro shows a rounded-corner brass plate: bright raised border,
lettering "Wm. Gaertner & Co / Chicago, U. S. A." and a scroll cartouche on a
dark field. The user ruling of 2026-10-09 (ch.26 p.71; ch.30 p002/p003/p006)
makes the traced OUTER edge the plate outline, rather than surrounding the
artwork with the former 100 x 55 plate. The #290 inch rebake scales it to
3.95 x 1.79 (``fr_nameplate_spec``). The nearby stamped '2' is a separate
base feature, not modelled here.

Acid-etched (owner ruling 2026-11-20 (Pedro), #2313: "A" -- etch the field
~.010 (.008-.012); letters and border proud and polished). The field is
etched to one time-set depth (``fr_nameplate_drawing_spec.FIELD_DEPTH``,
printed as its limits); the border and the filled letters and ornament stand
proud at the plate face. This replaced the engraved plate, whose .016 sunk
field carried the traced artwork's OUTLINES engraved .012 deeper.

The lettering and ornament are traced from the photo, not a font. The
original line-art was buffered into ~0.47 mm closed ribbons and unioned
offline (shapely), and the 2026-10-09 and #290 rebakes scaled it to the
plate in final plate-local millimetres (R2010, ``INSUNITS`` mm). The #2313
one-off derivation (shapely/ezdxf, outside the repo; the engraving DXF it
read is in git history before this change) filled those traced outlines: a
letter or ornament is its outline ribbon's outer loop shrunk by half the
ribbon width (the traced line), less each counter's, shrunk the same way.
The pinstripe and the eight traced screw-head rings were dropped: the
border's inner edge is the field loop. The art lives in three files:

* ``fr-nameplate-field.dxf``, unchanged: the pinstripe's INNER edge, one
  loop (its corner notches leave generous border lands under the screw
  heads). Cut ``FIELD_DEPTH`` deep, it sinks the whole field.
* ``fr-nameplate-letters.dxf``: every letter and ornament loop and every
  counter. Bossed back up from that floor to the face, the even-odd regions
  are the proud letters with their counters left etched. ``FIELD_AREA_MM2``
  less ``LETTERS_AREA_MM2`` is the etched field's net area. One sketch of
  both files (the field less its islands) was refused as a cut on the seat
  three times (farm runs 20261120T203523656Z, 20261120T205259953Z,
  20261120T211405935Z, mid-plane and single-ended alike); the field loop
  alone is the cut this part has always made.
* ``fr-nameplate-resist.dxf``, the shop's artwork, named on the sheet: loop
  0 is the outline, then the finished field eroded by the etch depth, so the
  resist (border plus letters) is widened by ``FIELD_DEPTH`` per edge for an
  etch undercutting about 1:1 [INFERENCE in the ruling], and the letters'
  tops come out at their finished size. Where two features stand closer than
  twice the depth (the scroll ends at the cartouche), the widened resist
  bridges them.

``fr-nameplate-outline.dxf`` is the outline alone, imported for the slab.
``OUTLINE_AREA_MM2`` is its shoelace area. ``CORNER_R`` is the least-squares
circular radius of the traced lower-left outer corner (maximum radial
residual below 0.001 mm after scaling); the imported contour, not a fitted
rounded rectangle, defines the actual outline.

The Makers seat ignores ``IImportDxfDwgData::SetPosition`` and
``SetSheetScale`` for flat modelspace DXFs, so every import uses scale=1,
position=(0,0). The SolidWorks-free ``test_fr_nameplate_geometry`` guards
the files, the field/letters/outline/resist areas and nesting, and the screw
stations against the border.

Mounting (2026-09-02 re-derive off ch26 p.71 ``page001_img01``): FOUR brass
slotted round-head screws, one per corner, heads riding the border's corner
lands. They are the shared #4-40 brass ``fr-vn-fillister-screw``
(``_fastener_catalog``; stock Ø2.8448 major diameter, Ø4.6482 head), so the plate carries
four #4 CLOSE clearance holes (wizard Ø3.048, the build_pd_guide_lock idiom) and
the harmonic base carries four blind #4-40 taps under them. The plate envelope,
the screw stations and the mount transform live in ``fr_nameplate_spec`` (pure
data) so ``build_fr_harmonic_base`` and ``build_fr_frame_assembly`` derive the tap
positions and the screw drops from ONE source without importing this build.

Layout: width along +X, height along +Y from the origin corner, decorated face on
the Front plane at z = 0. The body extrudes in -Z (``reverse_direction``) so the
decorated z=0 face is the EXPOSED FRONT face (outward normal +Z): the traced
artwork, drawn to read from +Z, then reads correctly on the face you actually
see, with no mirror. (build_pd_platen is untextured and extrudes +Z; only this
decorated plate needs the decorated face frontmost.)

Drawing references (``fr_nameplate_drawing_spec``): the outline is an
imported contour and the etched field's cut is mid-plane, so no feature
dimension carries the plate's width or height, a far-edge hole station or a
depth below the decorated face. Two construction-only sketches, saved hidden,
carry them as driving dimensions the drawing imports: ``FaceReference`` on the
Front plane (the decorated face) and ``SectionReference`` on
``SectionAPlane``, section A-A's cutting plane (hidden).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fr_nameplate.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _document_units import apply_package_model_units
from _limit_tolerance import set_limits
from _drawing_precision import apply_drawing_precision
from _feature_tree import _feature_by_name, name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _paths import REFERENCES_DIR
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _holes import CLEARANCE_MM, HoleSpec, wizard_holes
from _visibility import blank_reference_geometry
from fr_nameplate_drawing_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FACE_REFERENCE,
    FIELD_DEPTH,
    FIELD_DEPTH_LIMITS,
    FIELD_DXF_NAME,
    ISOMETRIC_VIEW_NOTE,
    LETTERS_DXF_NAME,
    MANUFACTURING_NOTES,
    OUTLINE_DXF_NAME,
    REFERENCE_SKETCHES,
    SECTION_PLANE,
    SECTION_REFERENCE,
    SECTION_REFERENCE_POINTS,
    SECTION_Y,
)
from fr_nameplate_spec import (
    PLATE_HEIGHT,
    PLATE_THICKNESS,
    PLATE_WIDTH,
    SCREW_XY,
    UNIT,
)

import _telemetry

PART_NAME = "fr-nameplate"
MATERIAL = "Brass"  # bright etched brass plate (see _appearance.apply_material)

# Plate dimensions/stations live in the pure-data contract used by base and frame.
CORNER_R = 4.032846449419005  # mm; measured circular fit, not an outline driver
OUTLINE_DXF = REFERENCES_DIR / OUTLINE_DXF_NAME
OUTLINE_AREA_MM2 = 4547.480744565876

# The etched field's edge: the notched inner edge of the traced pinstripe
# (keeping the screw heads on the raised border instead of sinking their
# bearing lands); FIELD_AREA_MM2 is that one loop's gross area. The letters
# and ornament bossed back from it, less their etched counters, net
# LETTERS_AREA_MM2 (the even-odd area of the letters DXF's loops).
FIELD_DXF = REFERENCES_DIR / FIELD_DXF_NAME
FIELD_AREA_MM2 = 3665.6669540813814
LETTERS_DXF = REFERENCES_DIR / LETTERS_DXF_NAME
LETTERS_AREA_MM2 = 616.9850497085362

# Four corner mounting screws (the shared stock #4-40 brass fillister-screw,
# Ø2.8448 major diameter) at SCREW_XY in the border band: #4 CLOSE clearance
# (Ø3.048 -- the same HoleSpec build_pd_guide_lock cuts for the same screw;
# memory/fastener-policy-us-customary). History: the holes were #2-56 normal
# fit Ø2.591 from a "#2 screw" guess; the 2026-09-02 p.71 re-read sized the
# heads (~Ø5.5 on the 100 plate) to the catalog #4-40 fillister, whose Ø2.9
# nominal / Ø2.845 major would not pass a Ø2.591 hole.
SCREW_HOLE_SPEC = HoleSpec("clearance", "#4", fit="close")
SCREW_HOLE_DIA = CLEARANCE_MM[(SCREW_HOLE_SPEC.size, SCREW_HOLE_SPEC.fit)]  # 3.048

# FaceReference's construction chords. Each is REFERENCE_CHORD long (an
# unprinted length): on a plate edge it starts FACE_EDGE_STATION from the
# corner, on the edge's straight run (the traced corners round off within
# 4.02 of each corner), so the width's and the height's extension lines rise
# from the flats; from a hole centre it stays inside the hole along its centre
# mark. The right column's station is the bottom-right hole's, the top row's
# the top-left hole's (SCREW_XY runs bottom-left, bottom-right, top-left,
# top-right).
REFERENCE_CHORD = 1.0
FACE_EDGE_STATION = 5.0
RIGHT_HOLE = SCREW_XY[1]
TOP_HOLE = SCREW_XY[2]


def _construction_chord(
    adapter, feature: str, start: tuple[float, float], end: tuple[float, float]
) -> str:
    """One construction line, placed with inference off (ms_stop_geom recipe)."""
    set_sketch_direct_db(adapter, True)
    line = check(feature, adapter.add_line(*start, *end))
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not segment.ConstructionGeometry:
        raise RuntimeError(f"{feature}: construction flag rejected")
    return line


def _square_chord(
    adapter,
    feature: str,
    line: str,
    relation: str,
    length: float,
    dims: SketchDims,
    name: str,
) -> None:
    """Hold ``line`` horizontal or vertical at ``length``."""
    check(feature, adapter.add_sketch_constraint(line, None, relation))
    dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        f"{relation}_distance",
        length,
        f"{feature} {name}",
    )
    dims.record(name)


def _face_reference(adapter) -> None:
    """The outline's width and height and the far-edge hole stations.

    On the Front plane (the decorated face), sketch (u, v) = model (X, Y),
    construction only and hidden. A shown reference sketch prints, so each
    chord lies on what the face view draws: up the left and right edges and
    along the bottom and top edges, each from FACE_EDGE_STATION; from the
    right column's hole centre toward the right edge and from the top row's
    toward the top edge. The width spans the side chords' starts, the height
    the bottom and top chords' starts, and each station a hole centre to its
    edge chord's start. 6 x 4 DOF less: the left and bottom starts on the
    origin's axes (2), the right and top starts level with them (2), six
    square relations and fourteen dims = 0.
    """
    feature = FACE_REFERENCE
    dims = SketchDims()
    station, chord = FACE_EDGE_STATION, REFERENCE_CHORD
    check(f"create sketch {feature}", adapter.create_sketch("Front"))
    left = _construction_chord(
        adapter, feature, (0.0, station), (0.0, station + chord)
    )
    anchor_point_to_origin(
        adapter, f"{left}.start", 0.0, station, f"{feature} left edge chord"
    )
    dims.record("LeftEdgeStation")
    _square_chord(adapter, feature, left, "vertical", chord, dims, "LeftChord")
    right = _construction_chord(
        adapter, feature, (PLATE_WIDTH, station), (PLATE_WIDTH, station + chord)
    )
    check(
        feature,
        adapter.add_sketch_constraint(
            f"{right}.start", f"{left}.start", "horizontal_points"
        ),
    )
    dimension_between(
        adapter,
        f"{left}.start",
        f"{right}.start",
        "horizontal_distance",
        PLATE_WIDTH,
        f"{feature} plate width",
    )
    dims.record("PlateWidth")
    _square_chord(adapter, feature, right, "vertical", chord, dims, "RightChord")
    bottom = _construction_chord(
        adapter, feature, (station, 0.0), (station + chord, 0.0)
    )
    anchor_point_to_origin(
        adapter, f"{bottom}.start", station, 0.0, f"{feature} bottom edge chord"
    )
    dims.record("BottomEdgeStation")
    _square_chord(
        adapter, feature, bottom, "horizontal", chord, dims, "BottomChord"
    )
    top = _construction_chord(
        adapter, feature, (station, PLATE_HEIGHT), (station + chord, PLATE_HEIGHT)
    )
    check(
        feature,
        adapter.add_sketch_constraint(
            f"{top}.start", f"{bottom}.start", "vertical_points"
        ),
    )
    dimension_between(
        adapter,
        f"{bottom}.start",
        f"{top}.start",
        "vertical_distance",
        PLATE_HEIGHT,
        f"{feature} plate height",
    )
    dims.record("PlateHeight")
    _square_chord(adapter, feature, top, "horizontal", chord, dims, "TopChord")
    right_x, right_y = RIGHT_HOLE
    right_hole = _construction_chord(
        adapter, feature, (right_x, right_y), (right_x + chord, right_y)
    )
    dimension_between(
        adapter,
        f"{right_hole}.start",
        f"{right}.start",
        "horizontal_distance",
        PLATE_WIDTH - right_x,
        f"{feature} right hole station",
    )
    dims.record("RightHoleStation")
    dimension_between(
        adapter,
        f"{bottom}.start",
        f"{right_hole}.start",
        "vertical_distance",
        right_y,
        f"{feature} right hole height",
    )
    dims.record("RightHoleY")
    _square_chord(
        adapter, feature, right_hole, "horizontal", chord, dims, "RightHoleChord"
    )
    top_x, top_y = TOP_HOLE
    top_hole = _construction_chord(
        adapter, feature, (top_x, top_y), (top_x, top_y + chord)
    )
    dimension_between(
        adapter,
        f"{top_hole}.start",
        f"{top}.start",
        "vertical_distance",
        PLATE_HEIGHT - top_y,
        f"{feature} top hole station",
    )
    dims.record("TopHoleStation")
    dimension_between(
        adapter,
        f"{left}.start",
        f"{top_hole}.start",
        "horizontal_distance",
        top_x,
        f"{feature} top hole across",
    )
    dims.record("TopHoleX")
    _square_chord(
        adapter, feature, top_hole, "vertical", chord, dims, "TopHoleChord"
    )
    ensure_fully_defined(adapter, feature)
    check(f"exit sketch {feature}", adapter.exit_sketch())
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)


def _section_plane(adapter) -> None:
    """Section A-A's cutting plane: the Top plane carried SECTION_Y along +Y,
    so a sketch on it keeps the Top plane's (u, v) = model (X, -Z)."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create plane {SECTION_PLANE}",
        adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=SECTION_Y
            )
        ),
    )
    name_last_feature(adapter, SECTION_PLANE)


def _import_art(adapter, path, name: str) -> None:
    """Import one artwork DXF onto the Front plane as the sketch ``name``."""
    from solidworks_mcp.adapters.base import ImportDxfDwgParameters

    if not path.is_file():
        raise RuntimeError(f"artwork DXF not found: {path}")
    check(
        f"import {path.name}",
        adapter.import_dxf_dwg(
            ImportDxfDwgParameters(
                file_path=str(path),
                plane="Front",
                scale=1.0,
                position=[0.0, 0.0],
                merge_points=True,
                import_hatch=False,
                import_dimensions=False,
                add_constraints=False,
            )
        ),
    )
    name_last_feature(adapter, name)


def _sketch_census(adapter, name: str) -> str:
    """The seat's contour and region counts for sketch ``name``, for a refused
    feature's error (a profile that did not close has neither)."""
    try:
        feature = _early_bound(_feature_by_name(adapter, name), "IFeature")
        sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
        return (
            f"{int(sketch.GetSketchContourCount())} contour(s), "
            f"{int(sketch.GetSketchRegionCount())} region(s)"
        )
    except Exception as exc:  # noqa: BLE001 - context for an error being raised
        return f"census unreadable: {type(exc).__name__}: {exc}"


def _require_on_section_plane(adapter, sketch: str) -> None:
    """create_sketch falls back to a standard plane when a named one fails to
    select; the sketch's parents must name SECTION_PLANE."""
    feature = _early_bound(_feature_by_name(adapter, sketch), "IFeature")
    parents = [
        str(_early_bound(parent, "IFeature").Name)
        for parent in (feature.GetParents() or ())
    ]
    if SECTION_PLANE not in parents:
        raise RuntimeError(f"{sketch} is not on {SECTION_PLANE}: parents {parents}")


@_telemetry.traced("part.nameplate.reference_point", label_param="label")
def _add_reference_point(adapter, uv: tuple[float, float], label: str) -> str:
    """One sketch point straight into the sketch DB (no inference snap),
    registered for the adapter's dimension refs
    (build_dt_cone_tip_block's idiom)."""
    sketch_manager = _early_bound(adapter.currentSketchManager, "ISketchManager")
    previous = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        point = sketch_manager.CreatePoint(uv[0] / 1000.0, uv[1] / 1000.0, 0.0)
    finally:
        sketch_manager.AddToDB = previous
    if point is None:
        raise RuntimeError(f"cannot create the {label} reference point")
    return adapter._register_sketch_entity("Point", point)


def _section_reference(adapter) -> None:
    """The etched field's depth below the face.

    On SECTION_PLANE, sketch (u, v) = model (X, -Z), points only and hidden.
    Each SECTION_REFERENCE_POINTS point lies on a cut-face line section A-A
    draws: the decorated face and the field's floor. The depth spans the
    face point to the floor point. Points, not chords: A-A shows this sketch
    to keep its dimension, and a construction chord on a cut-face line
    printed grey dashes over the outline (ENFORCE review).
    2 x 2 DOF less: the face point on the origin's axis (1) at its station
    (1), and the floor point's depth and station (2) = 0.
    """
    feature = SECTION_REFERENCE
    dims = SketchDims()
    check(f"create sketch {feature}", adapter.create_sketch(SECTION_PLANE))
    face_x, face_z = SECTION_REFERENCE_POINTS["face"]
    face = _add_reference_point(adapter, (face_x, -face_z), f"{feature} face")
    anchor_point_to_origin(
        adapter, face, face_x, -face_z, f"{feature} face point"
    )
    dims.record("FacePointStation")
    x, z = SECTION_REFERENCE_POINTS["field"]
    field = _add_reference_point(adapter, (x, -z), f"{feature} field")
    dimension_between(
        adapter, face, field, "vertical_distance", -z, f"{feature} FieldDepth"
    )
    dims.record("FieldDepth")
    dimension_between(
        adapter,
        face,
        field,
        "horizontal_distance",
        x - face_x,
        f"{feature} field point station",
    )
    dims.record("FieldPointStation")
    ensure_fully_defined(adapter, feature)
    check(f"exit sketch {feature}", adapter.exit_sketch())
    name_last_feature(adapter, feature)
    _require_on_section_plane(adapter, feature)
    dims.apply(adapter, feature)


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ExtrusionParameters,
        ImportDxfDwgParameters,
    )

    check("create_part", adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Only the screw-coordinate globals drive geometry. The imported outline and
    # field are fixed photo contours, not editable BorderW/FieldW/FieldH rectangles.
    # Explicit mm is load-bearing: this is an INCH document, so bare numbers would
    # evaluate in inches and move the placement sketch by a factor of 25.4.
    for n, (x, y) in enumerate(SCREW_XY):
        set_global(adapter, f"Screw{n}X", f"{x}mm")
        set_global(adapter, f"Screw{n}Y", f"{y}mm")

    # The Hole Wizard declares placement dim names + drive equations inline.
    # Collect its deferred drive jobs for one batch after the finished model's
    # rebuild, when every dimension target must resolve.
    drive_jobs: list[tuple[str, str]] = []

    # The slab's contour IS the original outer loop's outer edge, including the
    # traced corner curvature; importing it avoids approximating the photo with a
    # native rounded rectangle. Placement/scale are already baked into the file.
    if not OUTLINE_DXF.is_file():
        raise RuntimeError(f"outline DXF not found: {OUTLINE_DXF}")
    check(
        "import outline DXF",
        adapter.import_dxf_dwg(
            ImportDxfDwgParameters(
                file_path=str(OUTLINE_DXF),
                plane="Front",
                scale=1.0,
                position=[0.0, 0.0],
                merge_points=True,
                import_hatch=False,
                import_dimensions=False,
                add_constraints=False,
            )
        ),
    )
    name_last_feature(adapter, "OutlineProfile")
    # A boss extrude takes its profile from the open or PRE-SELECTED sketch only
    # (unlike the cut path, it never looks up the last ProfileFeature), and the
    # DXF import leaves its sketch closed and unselected: farm leaf 2026-10-10
    # failed "Failed to create extrusion feature" right here without this select.
    check("select outline profile", adapter.select_feature("OutlineProfile"))
    check(
        "extrude plate",
        # Extrude the body in -Z so the decorated z=0 face (where the field is
        # etched) is the EXPOSED FRONT face (normal +Z), not buried behind the
        # body -- the traced lettering then reads correctly with no mirror.
        adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_THICKNESS, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "PlateSlab")
    name_dimensions(adapter, "PlateSlab", ["PlateThick"])
    bbox_extent_check(adapter, "plate width (traced outline)", "x", PLATE_WIDTH)
    bbox_extent_check(adapter, "plate height (traced outline)", "y", PLATE_HEIGHT)
    volume_check(
        adapter, "traced plate slab", OUTLINE_AREA_MM2 * PLATE_THICKNESS, 0.02
    )

    # Four corner screw through-holes: ONE native Hole Wizard clearance
    # feature (4 placement points) for the #4-40 brass fillister mounting
    # screws -- #4 CLOSE fit Ø3.048 (SCREW_HOLE_SPEC; memory/fastener-policy-
    # us-customary). Cut BEFORE the etched field: wizard_holes locates its
    # face by enumerating every face of the body (COM roundtrips per face),
    # and the traced artwork explodes the body into thousands of wall faces
    # -- placing this feature after the former engraving measured >20 min of
    # face-walk (both runs hung here, front and back face alike). On the bare
    # slab the pristine back face at z=-PLATE_THICKNESS carries all four
    # stations and through-all is geometrically identical from either side.
    pre = adapter.get_mass_properties()
    screw_drives = tuple((f'"Screw{n}X"', f'"Screw{n}Y"') for n in range(len(SCREW_XY)))
    screw_cut = wizard_holes(
        adapter,
        SCREW_HOLE_SPEC,
        [[x, y, -PLATE_THICKNESS] for x, y in SCREW_XY],
        (0.0, 0.0, -1.0),
        "mounting screw holes (#4 clearance, close)",
        name="ScrewHoles",
        expect_dia_mm=SCREW_HOLE_DIA,
        placement_dims=[
            ((f"S{n}X", dx), (f"S{n}Z", dy))
            for n, (dx, dy) in enumerate(screw_drives)
        ],
    )
    drive_jobs += screw_cut.placement_drive_jobs
    v_holes = len(SCREW_XY) * math.pi * (SCREW_HOLE_DIA / 2.0) ** 2 * PLATE_THICKNESS
    removed = float(pre.data.volume) - float((adapter.get_mass_properties()).data.volume)
    _telemetry.info(f"screw holes removed {removed:.1f} mm^3 (analytic {v_holes:.1f})")
    if abs(removed - v_holes) > 0.02 * v_holes:
        raise RuntimeError(f"screw holes removed {removed:.1f}, expected {v_holes:.1f}")

    # The etched field (see the module docstring): the field loop cut
    # FIELD_DEPTH deep, then the letters and ornament bossed back up to the
    # face, their counters left etched. The field loop is the inner pinstripe
    # edge, NOT a rectangular inset: its corner notches keep the raised border
    # lands under all four screw heads. The artwork is traced to read from +Z;
    # because the body extrudes -Z the decorated z=0 face is the exposed front
    # (outward normal +Z), so both imports read correctly with no mirror.
    # Both-directions 2x depth about z=0 lands the cut FIELD_DEPTH into the -z
    # body; the boss runs FIELD_DEPTH from z=0 in -Z, back to the face.
    pre = adapter.get_mass_properties()
    _import_art(adapter, FIELD_DXF, "FieldProfile")
    cut = adapter.create_cut_extrude(
        ExtrusionParameters(depth=2.0 * FIELD_DEPTH, both_directions=True)
    )
    if not cut.is_success:
        raise RuntimeError(
            f"cut etched field failed ({_sketch_census(adapter, 'FieldProfile')}): "
            f"{cut.error}"
        )
    name_last_feature(adapter, "EtchedField")
    _import_art(adapter, LETTERS_DXF, "LettersProfile")
    # A boss takes only the PRE-SELECTED sketch (see the slab above).
    check("select letters profile", adapter.select_feature("LettersProfile"))
    boss = adapter.create_extrusion(
        ExtrusionParameters(depth=FIELD_DEPTH, reverse_direction=True)
    )
    if not boss.is_success:
        raise RuntimeError(
            f"boss letters failed ({_sketch_census(adapter, 'LettersProfile')}): "
            f"{boss.error}"
        )
    name_last_feature(adapter, "ProudLetters")
    v_field = (FIELD_AREA_MM2 - LETTERS_AREA_MM2) * FIELD_DEPTH
    removed = float(pre.data.volume) - float(
        (adapter.get_mass_properties()).data.volume
    )
    _telemetry.info(f"etched field removed {removed:.1f} mm^3 (analytic {v_field:.1f})")
    if abs(removed - v_field) > 0.02 * v_field:
        raise RuntimeError(
            f"etched field removed {removed:.1f}, expected {v_field:.1f}"
        )

    # The hidden references the sheet prints (no solid change).
    _face_reference(adapter)
    _section_plane(adapter)
    _section_reference(adapter)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so geometry must not move. This part has no single analytic-total
    # volume_check (its incremental cuts are asserted in place above), so the
    # neutrality proof captures the as-built volume and re-asserts it unchanged.
    final_volume = float((adapter.get_mass_properties()).data.volume)
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    volume_check(
        adapter, "driven nameplate (equations neutral)", final_volume, 1e-3 * final_volume
    )

    # Manufacturing drawing support (#628): every printed model dimension's
    # places live on the part (fr_nameplate_drawing_spec), then the print's
    # dimensions are marked and the title-block properties stamped. One model
    # band: the etched field's depth prints its owner-ruled limits (#2313);
    # every other dimension prints the title block's grade for its places.
    set_limits(
        adapter,
        SECTION_REFERENCE,
        "FieldDepth",
        limits=FIELD_DEPTH_LIMITS,
        places=DRAWING_PRECISION[SECTION_REFERENCE]["FieldDepth"],
        display_unit=UNIT,
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Saved hidden: the drawing shows each sketch in the view that dimensions
    # it (_drawing_hidden_sketches).
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    blank_reference_geometry(adapter, ((SECTION_PLANE, "PLANE"),))

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": MANUFACTURING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
