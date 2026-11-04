"""Offline contracts for the MHA-DT-VN-61 cone pivot post mount screw."""

from __future__ import annotations

import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm, printed_deviations
import build_dt_vn_post_mount_screw as part
import dt_cone_pivot_post_spec as post
import dt_cone_swing_platform_spec as platform
import draw_dt_vn_post_mount_screw as drawing
from _fit_deviations import deviations
import dt_vn_post_mount_screw_spec as spec
from _drawing_contract import drawing_specification_violations
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_40923906 as recipe
from _msc_40923906 import FILLISTER_SIZE

IN = 25.4
# Screw head seated on the counterbore floor: its under-head face is this far
# below the post top, and the shank spans the rest of the post and the plate.
GRIP = post.BLOCK_HEIGHT - post.ATTACHMENT_CBORE_DEPTH


def test_recipe_is_the_u37c_screw() -> None:
    """The registered fillister's head envelope, pitch and fitted cut length."""
    assert spec.THREAD == platform.POST_MOUNT_SPEC.size == "1/4-20"
    assert part.SHANK_DIA == THREAD_MAJOR_MM[spec.THREAD]
    assert part.THREAD_PITCH == IN / 20.0
    assert part.SHANK_LEN == spec.CUT_LENGTH_MM
    assert part.HEAD_DIA == 0.414 * IN
    assert part.HEAD_H == 0.237 * IN


def test_head_fits_the_existing_post_counterbore() -> None:
    assert part.HEAD_DIA < post.ATTACHMENT_CBORE_DIA
    assert part.HEAD_H <= post.ATTACHMENT_CBORE_DEPTH + 1e-9  # never above the top
    assert part.SHANK_DIA < post.ATTACHMENT_THRU_DIA


def test_nominal_end_sits_short_of_the_platform_underside() -> None:
    """The spec-derived cut is inside the functional fit-to-hole acceptance."""
    short = GRIP + platform.PLATE_THICKNESS - part.SHANK_LEN
    assert 0.0 <= short <= spec.POST_SCREW_CUT_TO_FIT_SHORT
    engagement = part.SHANK_LEN - GRIP
    assert engagement / part.SHANK_DIA >= 0.87


def test_supplied_stock_reaches_longest_raised_post_corner() -> None:
    assert spec.LONGEST_FITTED_LENGTH_MM == spec.FLOOR_HIGH_MM + spec.PLATE_THICK_MM
    assert spec.STOCK_REACH_MARGIN_MM == (
        spec.STOCK_LENGTH_MM - spec.FACTORY_TIP_CHAMFER_MM - spec.LONGEST_FITTED_LENGTH_MM
    )
    assert spec.STOCK_REACH_MARGIN_MM > 0.0
    assert spec.CUT_LENGTH_MM < spec.LONGEST_FITTED_LENGTH_MM


def test_no_fixed_cut_length_fits_both_in_band_corners() -> None:
    """U27, geometry first: across the printed post and plate bands, the
    never-proud corner (lowest counterbore floor, thin plate) caps a fixed
    length below what the 0.87D corner (highest floor, after both edge
    breaks) needs.  So no band can go on the print."""
    unit = drawing_unit("parts/dt-cone-pivot-post", _config.parts("dt-cone-pivot-post"))
    places = post.DRAWING_PRECISION_BY_NAME["MainBodyHt"]
    height_lo, height_hi = printed_deviations(post.BLOCK_HEIGHT, places, unit=unit)
    depth_lo, depth_hi = printed_deviations(post.ATTACHMENT_CBORE_DEPTH, 2, unit=unit)
    low = (post.BLOCK_HEIGHT + height_lo) - (post.ATTACHMENT_CBORE_DEPTH + depth_hi)
    high = (post.BLOCK_HEIGHT + height_hi) - (post.ATTACHMENT_CBORE_DEPTH + depth_lo)
    assert (spec.FLOOR_LOW_MM, spec.FLOOR_HIGH_MM) == pytest.approx((low, high))
    thin = platform.PLATE_THICKNESS - spec.PLATE_STOCK_BAND_MM
    assert spec.FIXED_LENGTH_FLUSH_MAX_MM == pytest.approx(low + thin)
    need = (
        high
        + 0.87 * part.SHANK_DIA
        + spec.POST_MOUNT_TAP_EDGE_BREAK
        + spec.CUT_END_BREAK_MAX_MM
    )
    assert spec.FIXED_LENGTH_ENGAGEMENT_MIN_MM == pytest.approx(need)
    assert spec.FIXED_LENGTH_ENGAGEMENT_MIN_MM > spec.FIXED_LENGTH_FLUSH_MAX_MM
    assert spec.FIXED_CUT_LENGTH_EXISTS is False


def test_only_the_factory_thread_reaches_the_tapped_plate() -> None:
    """MSC threads 1.500 in up from the supplied tip; the shank above is plain.
    Even on the lowest floor the plate's tapped hole lies below the thread
    start, so the engagement chain counts full thread only."""
    assert spec.FACTORY_THREAD_START_MM == pytest.approx((4.000 - 1.500) * IN)
    assert spec.FACTORY_THREAD_START_MM < spec.FLOOR_LOW_MM
    assert spec.FACTORY_THREAD_START_MM < spec.CUT_LENGTH_MM


def test_cut_length_prints_as_a_reference_without_a_band() -> None:
    """No fixed length exists, so the model's spec-derived length prints in
    parentheses without a band; the callout carries fit-to-hole acceptance."""
    assert spec.CUT_LENGTH_MM == part.SHANK_LEN
    places = spec.DRAWING_PRECISION_BY_NAME[spec.CUT_LENGTH_DIMENSION]
    # The model's length sits on the inch grid it prints at (#290).
    assert spec.CUT_LENGTH_MM / IN * 10**places == pytest.approx(
        round(spec.CUT_LENGTH_MM / IN * 10**places), abs=1e-6
    )
    assert 0.0 <= GRIP + platform.PLATE_THICKNESS - spec.CUT_LENGTH_MM
    assert GRIP + platform.PLATE_THICKNESS - spec.CUT_LENGTH_MM <= (
        spec.POST_SCREW_CUT_TO_FIT_SHORT
    )
    callout = drawing.DIMENSION_CALLOUTS["CutLength"]
    # The callout still promises no fixed length: never the modelled cut
    # length, never a band on it.
    assert spec.inch_text(spec.CUT_LENGTH_MM, places) not in callout
    assert "±" not in callout and "+" not in callout


def test_cut_to_fit_acceptance_prints_on_the_delegating_callout() -> None:
    """Codex P1 on #857: the callout delegated the cut to assembly, but no
    MHA-DT-00 step stated the acceptance the 0.90D worst case depends on.  The
    acceptance is a spec band -- upper 0 (never proud), lower the most a
    screw may be cut short -- and the callout prints it, generated from that
    band at its own places, not a literal."""
    lower, upper = deviations(spec.POST_SCREW_CUT_TO_FIT_BAND)
    assert upper == 0.0
    assert spec.POST_SCREW_CUT_TO_FIT_SHORT == -lower
    places = spec.CUT_TO_FIT_SHORT_PLACES
    callout = drawing.DIMENSION_CALLOUTS["CutLength"]
    assert callout == spec.CUT_TO_FIT_CALLOUT
    flat = " ".join(callout.split())
    assert flat.startswith("CUT TO FIT AT ASSEMBLY")
    assert f"FLUSH TO {spec.inch_text(-lower, places)} SHORT OF MHA-DT-20 UNDERSIDE" in flat
    assert "NEVER PROUD" in flat
    # The printed allowance is the one the named exception's worst case
    # spends: thinnest plate, full allowance, both breaks at their maximum.
    assert spec.POST_MOUNT_ENGAGEMENT_WORST == pytest.approx(
        platform.PLATE_THICKNESS
        - spec.PLATE_STOCK_BAND_MM
        - (-lower)
        - spec.POST_MOUNT_TAP_EDGE_BREAK
        - spec.CUT_END_BREAK_MAX_MM
    )
    assert spec.POST_MOUNT_ENGAGEMENT_WORST / spec.THREAD_DIA_MM >= spec.MIN_ENGAGEMENT_DIAMETERS
    # No other sheet text restates it: the part notes stay digit-free.
    assert not any(ch.isdigit() for ch in spec.MANUFACTURING_NOTES)


def test_engagement_minimum_prints_on_the_cut_length_callout() -> None:
    """Codex P2 on #857 (PRRT_kwDOPHDy386mOxdw): MHA-DT-VN-61 stated its 0.90D
    engagement shortfall nowhere, yet the policy's named-exceptions section
    wants every affected sheet to state it.  The callout that delegates the
    cut carries the worst-case minimum as a plain fact, floored from the
    spec's worst case -- never a literal."""
    callout = drawing.DIMENSION_CALLOUTS["CutLength"]
    printed = spec.POST_MOUNT_ENGAGEMENT_PRINTED
    assert printed == math.floor(
        spec.POST_MOUNT_ENGAGEMENT_WORST / spec.THREAD_DIA_MM * 100.0
    ) / 100.0
    assert printed >= spec.MIN_ENGAGEMENT_DIAMETERS
    fact = f"ENGAGEMENT {printed:.2f}D MIN"
    assert fact in callout.splitlines()
    # It closes the acceptance the cut delegates to assembly.
    assert callout.splitlines()[-1] == fact


def test_engagement_shortfall_is_declared_for_the_blind_reviewer() -> None:
    """A stated shortfall with no package-local declaration gates like a
    blocker; RV-01 names the fact the sheet prints, as a minor."""
    from machinist_exceptions import load_exceptions

    (entry,) = load_exceptions(_config.CONFIG_DIR, "dt_vn_post_mount_screw", "part")
    assert (entry.id, entry.kind) == ("RV-01", "minor")
    assert f"ENGAGEMENT {spec.POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D MIN" in entry.where
    assert "rule 18" in entry.finding


# Words that cite the exception's LABEL rather than state its fact (Main's
# fleet ruling on the Codex P2): no rule, ruling, policy or exception words,
# and no user-ruling ids such as "U37c".
_BANNED_ON_SHEET = re.compile(
    r"\b(EXCEPTIONS?|ACCEPTED|RULES?|RULINGS?|POLICY|U\d+[A-Z]?)\b", re.IGNORECASE
)


def _mha142_printed_strings() -> dict[str, str]:
    config = _config.parts("dt-vn-post-mount-screw")
    printed = {
        "CutLength callout": drawing.DIMENSION_CALLOUTS["CutLength"],
        "manufacturing notes": spec.MANUFACTURING_NOTES,
    }
    for index, text in drawing.DRAWING_SUMMARY.items():
        printed[f"summary {index}"] = text
    for field in (
        "title",
        "number",
        "stock_name",
        "supplier",
        "material",
        "material_specification",
        "finish",
        "installation_notes",
    ):
        if field in config:
            printed[f"yaml {field}"] = str(config[field])
    return printed


def test_banned_word_scan_catches_a_cited_exception() -> None:
    """Positive control: the scan flags the label forms it exists to keep off."""
    for text in (
        "ENGAGEMENT 0.90D MIN (ACCEPTED EXCEPTION)",
        "PER RULE 12",
        "SEE RULING U37c",
        "POLICY: CUT TO FIT",
    ):
        assert _BANNED_ON_SHEET.search(text), text
    assert not _BANNED_ON_SHEET.search("ENGAGEMENT 0.90D MIN")
    assert not _BANNED_ON_SHEET.search("OF MHA-DT-20 UNDERSIDE, NEVER PROUD")


def test_mha142_prints_no_exception_label() -> None:
    printed = _mha142_printed_strings()
    assert "CutLength callout" in printed and "yaml finish" in printed
    hits = {
        name: match.group(0)
        for name, text in printed.items()
        if (match := _BANNED_ON_SHEET.search(text))
    }
    assert hits == {}


def test_cut_to_fit_allowance_is_exported_once() -> None:
    """The per-hole allowance MHA-DT-00 and the platform stack consume."""
    assert spec.POST_SCREW_CUT_TO_FIT_SHORT == 0.127  # .005 in




def test_cut_end_break_is_the_title_block_edge_break() -> None:
    """Main's run-7 and 2026-11-01 rulings: no part-local break limit at either
    end; the engagement stack spends the title block's general chamfer at the
    screw's cut end and at the platform's tap."""
    assert spec.CUT_END_BREAK_MAX_MM == edge_break_chamfer_mm(unit="in")
    assert spec.POST_MOUNT_TAP_EDGE_BREAK == edge_break_chamfer_mm(unit="in")


def test_worst_case_engagement_holds_the_named_minimum() -> None:
    """Cut to fit, the plate limits engagement: thinnest stock, the full
    fit-to-hole allowance, the tap's entry deburr and the cut end's general
    edge break, both at their maximum, recomputed here from the chain."""
    worst = (
        platform.PLATE_THICKNESS
        - spec.PLATE_STOCK_BAND_MM
        - spec.POST_SCREW_CUT_TO_FIT_SHORT
        - spec.POST_MOUNT_TAP_EDGE_BREAK
        - edge_break_chamfer_mm(unit="in")
    )
    assert spec.POST_MOUNT_ENGAGEMENT_WORST == pytest.approx(worst)
    assert worst / part.SHANK_DIA >= 0.87
    assert spec.POST_MOUNT_ENGAGEMENT_PRINTED >= 0.87


def test_catalog_row_is_the_supplied_stock_and_only_the_part_is_cut() -> None:
    """The registered catalogue row remains supplied 4 in stock; only the
    MHA-DT-VN-61 builder trims it. No shared stock row is overwritten."""
    row = _config.parts(part.PART_NAME)
    assert row["supplier_skus"] == [spec.SKU]
    assert spec.SKU == recipe.PART_NO
    assert FILLISTER_SIZE[1] == pytest.approx(4.0 * IN)
    assert spec.STOCK_LENGTH_MM == FILLISTER_SIZE[1]
    assert part.SHANK_LEN == spec.CUT_LENGTH_MM < spec.STOCK_LENGTH_MM
    # A half-inch-shorter predecessor cannot reach the longest fitted seat.
    assert spec.STOCK_LENGTH_MM - 0.5 * IN < spec.FIXED_LENGTH_ENGAGEMENT_MIN_MM


def _independent_removal() -> float:
    """Brute-force the trim's removed volume (midpoint rule, 2k slices):
    at radius r the groove takes w(r)/P of the circumference, w(r) the
    cutter's axial width, P/8 at the root, widening 2 tan 30 per mm."""
    radius, pitch = part.SHANK_DIA / 2.0, part.THREAD_PITCH
    root = radius - 0.75 * pitch * math.sqrt(3.0) / 2.0
    tip = 0.7 * pitch

    def metal(section: float, steps: int = 400) -> float:
        total = math.pi * section**2
        if section > root:
            width = (section - root) / steps
            for i in range(steps):
                r = root + (i + 0.5) * width
                groove = pitch / 8.0 + 2.0 / math.sqrt(3.0) * (r - root)
                total -= 2.0 * math.pi * r * groove / pitch * width
        return total

    stock, cut = spec.STOCK_LENGTH_MM, spec.CUT_LENGTH_MM
    slices = 2000
    height = tip / slices
    trim = sum(
        metal(radius - tip + (i + 0.5) * height) * height for i in range(slices)
    )
    trim += metal(radius) * (stock - tip - cut)
    return trim


def test_analytic_removal_volume_matches_a_brute_force_integral() -> None:
    assert spec.TRIM_REMOVED_MM3 == pytest.approx(_independent_removal(), rel=1e-4)


def test_cut_end_features_are_driven_by_the_model_dimensions() -> None:
    """The trim follows CutLength by equation."""
    assert part.TRIM_DRIVES == {"TrimAt": '"CutLength@CutLengthReference"'}
    assert part.TRIM_FEATURE == "CutToLength"
    # The trimmed tip cannot reach into what the stock carries: the cut
    # clears the factory tip, and the volume gate outruns the sweep's slack.
    assert spec.STOCK_LENGTH_MM - spec.FACTORY_TIP_CHAMFER_MM > spec.CUT_LENGTH_MM
    assert part.TRIM_VOLUME_TOL_MM3 < 0.01 * spec.TRIM_REMOVED_MM3






def _printed_cut_short_allowance() -> float:
    """The acceptance the sheet prints: "END FLUSH TO <x> SHORT"."""
    match = re.search(r"END FLUSH TO (\d*\.\d+) SHORT", spec.CUT_TO_FIT_CALLOUT)
    assert match, spec.CUT_TO_FIT_CALLOUT
    return round(float(match.group(1)) * IN, 9)


def _short_of_underside(length_mm: float) -> float:
    """How far a screw of this length ends short of the MHA-DT-20 underside on
    the nominal post and plate (negative: proud)."""
    return GRIP + platform.PLATE_THICKNESS - length_mm


def test_the_modelled_length_is_a_cut_the_sheet_accepts() -> None:
    """Codex P2 on #857 (PRRT_kwDOPHDy386mRhqY): the source CAD must satisfy
    its own sheet. The modelled length is the current post/plate flush
    length less the allowance's midpoint, at its printed places."""
    allowance = _printed_cut_short_allowance()
    assert allowance == platform.POST_SCREW_CUT_TO_FIT_SHORT

    def accepted(length_mm: float) -> bool:
        return 0.0 <= _short_of_underside(length_mm) <= allowance

    assert not accepted(spec.FLUSH_LENGTH_MM - allowance - 0.01)
    assert accepted(spec.CUT_LENGTH_MM)
    places = spec.DRAWING_PRECISION_BY_NAME[spec.CUT_LENGTH_DIMENSION]
    middle = (_short_of_underside(0.0) - allowance / 2.0) / IN
    assert spec.CUT_LENGTH_MM / IN == pytest.approx(
        math.floor(middle * 10**places + 0.5) / 10**places
    )
    assert part.SHANK_LEN == spec.CUT_LENGTH_MM


def test_engagement_exception_is_held_by_the_model() -> None:
    """The rule-18 shortfall pending #1019 (floor 0.87D) is a model assert on the
    chain; the sheet prints it on the cut-length callout
    (test_engagement_minimum_prints_on_the_cut_length_callout)."""
    assert spec.MIN_ENGAGEMENT_DIAMETERS == 0.87
    assert spec.ENGAGEMENT_NOMINAL_MM == spec.CUT_LENGTH_MM - GRIP
    assert spec.ENGAGEMENT_NOMINAL_MM / part.SHANK_DIA >= 0.87


def test_sheet_layout_keeps_notes_clear_of_the_view() -> None:
    """1:1 Front view spans ~92 mm around its centre; the note block sits
    between it and the stock rows, the cut length left of the shank."""
    half_h = (spec.CUT_LENGTH_MM + part.HEAD_H) / 2000.0
    view_bottom = drawing.FRONT_CENTER[1] - half_h
    notes_y = drawing.NOTES_XY[1]
    assert notes_y + 0.004 < view_bottom
    lines = len(spec.MANUFACTURING_NOTES.splitlines())
    assert notes_y - lines * 0.0045 > max(y for _, _, y in drawing.STOCK_ROWS) + 0.003
    # The widest callout line (~2.85 mm per capital, warm-c486) clears the
    # head's silhouette, the widest part of the view.
    x, _ = drawing.FRONT_KEEP["CutLength"]
    widest = max(len(line) for line in drawing.DIMENSION_CALLOUTS["CutLength"].splitlines())
    assert x + widest * 0.00285 / 2.0 < drawing.FRONT_CENTER[0] - part.HEAD_DIA / 2000.0 - 0.003
    assert x - widest * 0.00285 / 2.0 > 0.015  # inside the border
    assert not hasattr(drawing, "BREAK_TEXT")


def test_stock_build_uses_its_registered_recipe() -> None:
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == recipe.build_40923906.__name__
    assert part.SPEC.skus == (spec.SKU,)
    assert part.SPEC.supplier == "MSC Industrial Supply"
    assert part.MATERIAL == "Plain Carbon Steel"
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-DT-VN-61"
    assert int(row["quantity"]) == 2
    assert spec.SKU in row["material_specification"]
    assert "SAE J82" in row["material_specification"]
    assert spec.SKU in drawing.DRAWING_SUMMARY[3]


def test_drawing_is_the_modified_stock_sheet() -> None:
    """A cut purchased part takes a manufacturing sheet with its cut length,
    not the dimensionless purchased reference sheet (boss hook's pattern)."""
    registry = DRAWINGS_BY_NAME["dt_vn_post_mount_screw"]
    assert drawing.SPEC is registry
    assert registry.artifact_stem == part.PART_NAME
    assert registry.script == Path(drawing.__file__).resolve()


def test_sheet_passes_the_drawing_owned_precision_rule() -> None:
    violations = drawing_specification_violations(
        Path(drawing.__file__).read_text(encoding="utf-8"),
        filename=Path(drawing.__file__).name,
    )
    assert violations == ()





class _Point:
    def __init__(self, xyz) -> None:
        self.ArrayData = tuple(xyz)

    def MultiplyTransform(self, transform):
        return _Point(transform(self.ArrayData))


class _DoubleArray(tuple):
    """What the fake double_array hands COM: a bare list must never reach
    CreatePoint or SetViewPosition (a real seat reads it as zeros)."""


def _require_double_array(values, what: str) -> None:
    if not isinstance(values, _DoubleArray):
        raise TypeError(f"{what} got {type(values).__name__}, not a double_array")


class _Utility:
    def CreatePoint(self, xyz):
        _require_double_array(xyz, "CreatePoint")
        return _Point(xyz)


class _SketchPoint:
    def __init__(self, xyz) -> None:
        self.X, self.Y, self.Z = xyz


class _Arc:
    """ISketchArc stand-in: what the seat actually made."""

    def __init__(self, center, radius: float) -> None:
        self.center = center
        self.radius = radius

    def GetCenterPoint2(self):
        return _SketchPoint(self.center)

    def GetRadius(self):
        return self.radius


class _Sketch:
    # A sheet point maps to its view-sketch point x1000 (any affine map works).
    ModelToSketchTransform = staticmethod(lambda xyz: tuple(v * 1000.0 for v in xyz))


class _Note:
    def __init__(self, text: str, owner: str) -> None:
        self.text = text
        self.owner = owner

    def GetText(self):
        return self.text


class _Seat:
    """IModelDoc2 + IDrawingDoc + ISketchManager + adapter, recorded."""

    def __init__(self) -> None:
        self.log: list[tuple] = []
        self.notes: list[_Note] = []
        self.active = ""
        self.currentModel = self
        self.SketchManager = self
        self.swApp = self
        self.AddToDB = False
        # (dx, dy, radius factor), in the fake sketch space (sheet mm), applied
        # when AddToDB is off (or ignored); the 6e65 leaf's Front mark read
        # ~1.5 mm for 3.6, centred on the cut end.
        self.snap: tuple[float, float, float] | None = None
        self.honours_add_to_db = True
        self.add_to_db_seen: list[bool] = []

    def GetMathUtility(self):
        return _Utility()

    def ActivateView(self, name):
        self.log.append(("activate", name))
        self.active = name
        return True

    def ClearSelection2(self, _all):
        return True

    def EditRebuild3(self):
        return True

    def CreateCircle(self, *xyz):
        self.log.append(("circle", self.active, tuple(round(v, 9) for v in xyz)))
        self.add_to_db_seen.append(self.AddToDB)
        cx, cy, cz, px, py, _pz = xyz
        radius = math.dist((cx, cy), (px, py))
        if self.snap is not None and not (self.AddToDB and self.honours_add_to_db):
            # Sketch inference: the points land on nearby geometry instead.
            dx, dy, factor = self.snap
            cx, cy, radius = cx + dx, cy + dy, radius * factor
        return _Arc((cx, cy, cz), radius)


def test_activate_front_for_notes_activates_the_front_by_name(monkeypatch) -> None:
    activated: list[str] = []

    class _Doc:
        def ActivateView(self, name):
            activated.append(name)
            return name == "Drawing View1"

    class _Adapter:
        currentModel = _Doc()

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(drawing, "view_name", lambda adapter, view: view)
    drawing.activate_front_for_notes(_Adapter(), "Drawing View1")
    assert activated == ["Drawing View1"]
    with pytest.raises(RuntimeError, match="Front view"):
        drawing.activate_front_for_notes(_Adapter(), "Detail View A (10 : 1)")


# The supplier diagram lives in a rotated, translated MODEL sketch.  The
# drawing view's own sketch below remains a separate sheet-to-crop frame.
class _SupplierSourceTransform:
    def __init__(self, seat) -> None:
        self.seat = seat

    def __call__(self, xyz):
        x, y, z = xyz
        return (y + 0.043, 0.031 - x, z - 0.057)

    def Inverse(self):
        self.seat.log.append(("inverse-source-frame",))

        def sketch_to_model(xyz):
            self.seat.log.append(("sketch-to-model", tuple(xyz)))
            x, y, z = xyz
            return (0.031 - y, -0.043 + x, 0.057 + z)

        return sketch_to_model


class _SupplierView:
    INITIAL_ANGLE = 0.37
    TRANSFORMS = {"ReferencedConfiguration", "UseSheetScale", "ScaleRatio", "Angle", "Position"}

    def __init__(self, seat, center, scale, source_angle) -> None:
        self.name = "MSC source"
        self.ReferencedConfiguration = "Default"
        self.UseSheetScale = 1
        self.ScaleRatio = (0.5, 1.0)
        self.Angle = self.INITIAL_ANGLE
        self.Position = (center[0] + 0.007, center[1] - 0.009)
        self.expected_scale = scale
        self.source_angle = source_angle
        self.sheet_signs = (1.0, 1.0)
        self.projection_factor = 1.0
        self.cropped = False
        self.source_sketch = SimpleNamespace(
            ModelToSketchTransform=_SupplierSourceTransform(seat),
        )
        feature = SimpleNamespace(GetSpecificFeature2=self._source_sketch)
        self.ReferencedDocument = SimpleNamespace(
            FeatureByName=lambda name: self._source_feature(name, feature),
        )
        self.seat = seat

    def __setattr__(self, name, value) -> None:
        if name in self.TRANSFORMS and "seat" in self.__dict__:
            assert not self.seat.annotated, f"{name} changed after dimension import"
            if name == "ScaleRatio":
                _require_double_array(value, "ScaleRatio")
            self.seat.log.append((name, value))
            self.seat.dirty = True
            self.seat.display_dirty = True
        object.__setattr__(self, name, value)

    def _source_feature(self, name, feature):
        assert name == drawing.SUPPLIER_STOCK_FEATURE
        self.seat.log.append(("source-feature", name))
        return feature

    def _source_sketch(self):
        self.seat.log.append(("source-sketch",))
        return self.source_sketch

    def sheet_point(self, xyz):
        x, y, _z = xyz
        angle = self.Angle - self.INITIAL_ANGLE + self.source_angle - math.pi / 2.0
        c, s = math.cos(angle), math.sin(angle)
        ratio = self.ScaleRatio[0] / self.ScaleRatio[1] * self.projection_factor
        return (
            self.Position[0] + ratio * self.sheet_signs[0] * (c * x - s * y),
            self.Position[1] + ratio * self.sheet_signs[1] * (s * x + c * y),
            0.0,
        )

    @property
    def ModelToViewTransform(self):
        assert self.seat.revealed
        assert self.ReferencedConfiguration == drawing.SUPPLIER_STOCK_CONFIGURATION
        assert self.UseSheetScale == 0
        assert tuple(self.ScaleRatio) == self.expected_scale
        assert not self.seat.dirty, "projection used an unrebuilt view transform"
        assert not self.seat.display_dirty, "projection used unrefreshed view display geometry"
        self.seat.log.append(("project-frame", self.Angle, self.Position))
        return self.sheet_point

    def SetViewPosition(self, position, move_children):
        _require_double_array(position, "SetViewPosition")
        self.seat.log.append(("move", tuple(position), move_children))
        self.Position = tuple(position)
        return True

    def UpdateViewDisplayGeometry(self):
        assert not self.seat.dirty
        self.seat.display_dirty = False
        self.seat.log.append(("update",))

    def GetOutline(self):
        return (0.123, -0.087, 0.155, 0.128)

    def GetSketch(self):
        self.seat.log.append(("crop-sketch",))
        return _Sketch()

    def Crop2(self, jagged, no_outline, intensity):
        self.seat.log.append(("crop2", jagged, no_outline, intensity))
        self.cropped = True
        return 1

    def IsCropped(self):
        return self.cropped


class _SupplierSeat(_Seat):
    def __init__(self) -> None:
        super().__init__()
        self.revealed = False
        self.annotated = False
        self.dirty = False
        self.display_dirty = False

    def EditRebuild3(self):
        self.log.append(("rebuild",))
        # A rebuild settles edits, but repaint-dependent geometry can still lag.
        self.dirty = False
        return True


_SUPPLIER_FRAME_CASES = (
    (False, drawing.STOCK_CENTER, drawing.STOCK_SCALE, drawing.STOCK_KEEP, 0.0477901),
    (True, drawing.STOCK_HEAD_CENTER, drawing.STOCK_HEAD_SCALE, drawing.STOCK_HEAD_KEEP, -0.0030099),
)


def _supplier_seat(monkeypatch, center, scale, *, source_angle=math.pi / 2.0):
    import _drawing_projection as projection

    seat = _SupplierSeat()
    stock = _SupplierView(seat, center, scale, source_angle)

    def place(adapter, source, orientation, x, y):
        assert adapter is seat and source == str(drawing.SOURCE)
        assert orientation == "*Front" and (x, y) == center
        seat.log.append(("place",))
        return stock

    def reveal(adapter, view, features, *, view_label):
        assert adapter is seat and view is stock
        assert stock.ReferencedConfiguration == drawing.SUPPLIER_STOCK_CONFIGURATION
        assert features == (drawing.SUPPLIER_STOCK_FEATURE,)
        seat.revealed = True
        seat.log.append(("reveal",))
        return features

    def invoke(obj, _interface, member, *args):
        value = getattr(obj, member)
        return value if member in ("ModelToViewTransform", "ArrayData") else value(*args)

    strict_frame = drawing._assert_supplier_profile_frame

    def verify(*args, **kwargs):
        strict_frame(*args, **kwargs)
        seat.log.append(("verified-frame",))

    def import_dimensions(adapter, view, *, keep, view_label, dimensions_by_feature):
        assert adapter is seat and view is stock
        assert dimensions_by_feature == drawing.SUPPLIER_STOCK_DIMENSIONS
        assert any(entry[0] == "verified-frame" for entry in seat.log)
        seat.log.append(("import", tuple(keep)))
        seat.annotated = True
        return [
            SimpleNamespace(
                name=name, GetSpecificAnnotation=lambda name=name: SimpleNamespace(name=name),
            )
            for name in keep
        ]

    def reposition(adapter, annotations, *, reposition):
        assert adapter is seat
        assert {annotation.name for annotation in annotations} == set(reposition)
        seat.log.append(("reposition", tuple(reposition.items())))
        return annotations

    def reference(adapter, display, **contract):
        assert adapter is seat and display.name == contract["label"]
        seat.log.append(("reference", display.name))

    def verify_crop(adapter, view, circle, cell):
        assert adapter is seat and view is stock and circle is not None
        assert cell == drawing.STOCK_HEAD_CELL
        seat.log.append(("verified-crop",))

    # Existing frame-contract tests count projection calls independently of
    # observational diagnostics; the diagnostic readbacks have their own test.
    monkeypatch.setattr(drawing, "_log_supplier_view_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "double_array", lambda values: _DoubleArray(values))
    monkeypatch.setattr(projection, "double_array", lambda values: _DoubleArray(values))
    monkeypatch.setattr(projection, "_com_invoke", invoke)
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing.hidden_sketches, "_show_hidden_owners", reveal)
    monkeypatch.setattr(drawing.hidden_sketches, "curate_view_dimensions", import_dimensions)
    monkeypatch.setattr(drawing, "curate_dimensions", reposition)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing, "supplier_reference_dimension", reference)
    monkeypatch.setattr(drawing, "_assert_supplier_profile_frame", verify)
    monkeypatch.setattr(drawing, "_assert_supplier_crop_circle", verify_crop)
    return seat, stock


@pytest.mark.parametrize("crop_head,center,scale,keep,semantic_x", _SUPPLIER_FRAME_CASES)
def test_supplier_profile_points_use_the_source_sketch_inverse(
    monkeypatch, crop_head, center, scale, keep, semantic_x,
) -> None:
    seat, stock = _supplier_seat(monkeypatch, center, scale)
    points = drawing._supplier_profile_model_points(
        seat, stock, crop_head=crop_head, label="source mapping",
    )
    expected = (
        (0.031, -0.043, 0.057),
        (0.031, -0.042, 0.057),
        (0.030, -0.043, 0.057),
        (0.031, -0.043 + semantic_x, 0.057),
    )
    assert len(points) == 4
    for actual, target in zip(points, expected, strict=True):
        assert actual == pytest.approx(target, rel=0.0, abs=1e-12)
    assert [entry[1] for entry in seat.log if entry[0] == "sketch-to-model"] == [
        (0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.0, 0.001, 0.0),
        pytest.approx((semantic_x, 0.0, 0.0), rel=0.0, abs=1e-12),
    ]
    kinds = [entry[0] for entry in seat.log]
    assert kinds[:3] == ["source-feature", "source-sketch", "inverse-source-frame"]
    assert "crop-sketch" not in kinds


@pytest.mark.parametrize("crop_head,center,scale,keep,semantic_x", _SUPPLIER_FRAME_CASES)
@pytest.mark.parametrize("source_angle", [math.pi / 2.0, 0.61], ids=["vertical", "oblique"])
def test_supplier_stock_view_settles_the_measured_frame_before_annotations(
    monkeypatch, crop_head, center, scale, keep, semantic_x, source_angle,
) -> None:
    seat, stock = _supplier_seat(monkeypatch, center, scale, source_angle=source_angle)
    result = drawing._supplier_stock_view(
        seat, center=center, scale=scale, label="MSC source", crop_head=crop_head,
    )
    assert result is stock
    assert stock.Angle == pytest.approx(stock.INITIAL_ANGLE - source_angle, abs=1e-12)
    assert stock.sheet_point((0.031, -0.043 + semantic_x, 0.057))[:2] == pytest.approx(
        center, rel=0.0, abs=1e-12,
    )
    assert tuple(stock.ScaleRatio) == scale and stock.UseSheetScale == 0
    assert stock.IsCropped() is crop_head
    assert not seat.annotated
    assert not any(entry[0] == "import" for entry in seat.log)
    drawing._present_supplier_stock_view(seat, stock, keep=keep, label="MSC source")
    kinds = [entry[0] for entry in seat.log]
    first_measure = kinds.index("source-feature")
    assert kinds[:first_measure] == [
        "place", "ReferencedConfiguration", "reveal", "rebuild",
        "UseSheetScale", "ScaleRatio", "rebuild", "update",
    ]
    angle = kinds.index("Angle")
    move = kinds.index("move")
    verified = kinds.index("verified-frame")
    imported = kinds.index("import")
    assert first_measure < kinds.index("project-frame") < angle < move < verified < imported
    assert "rebuild" in kinds[angle + 1:move]
    assert "update" in kinds[angle + 1:move]
    assert "rebuild" in kinds[move + 1:verified]
    assert "update" in kinds[move + 1:verified]
    assert kinds.count("source-feature") == kinds.count("inverse-source-frame") == 2
    assert not (stock.TRANSFORMS | {"move"}).intersection(kinds[imported + 1:])
    assert kinds[imported + 1:] == ["reposition"] + ["reference"] * len(keep)
    if crop_head:
        assert verified < kinds.index("crop-sketch") < kinds.index("circle") < kinds.index("crop2") < imported
        assert kinds.index("circle") < kinds.index("verified-crop") < kinds.index("crop2")
        circle = next(entry for entry in seat.log if entry[0] == "circle")
        cx, cy, _cz, px, py, _pz = (value / 1000.0 for value in circle[2])
        assert (cx, cy) == pytest.approx(center, rel=0.0, abs=1e-12)
        assert math.dist((cx, cy), (px, py)) == pytest.approx(
            drawing.STOCK_HEAD_RADIUS_MM * scale[0] / scale[1] / 1000.0,
        )
        assert next(entry for entry in seat.log if entry[0] == "crop2") == (
            "crop2", False, True, 5,
        )
    else:
        assert not {"crop-sketch", "circle", "crop2"}.intersection(kinds)


@pytest.mark.parametrize("crop_head,center,scale,keep,semantic_x", _SUPPLIER_FRAME_CASES)
@pytest.mark.parametrize(
    "fault", ["none", "rotated", "axial-mirror", "radial-mirror", "scale", "center-x", "center-y"],
)
def test_supplier_final_frame_reader_reprojects_and_rejects_native_drift(
    monkeypatch, crop_head, center, scale, keep, semantic_x, fault,
) -> None:
    seat, stock = _supplier_seat(monkeypatch, center, scale)
    drawing._supplier_stock_view(
        seat,
        center=center,
        scale=scale,
        label="MSC source",
        crop_head=crop_head,
    )
    points = drawing._supplier_profile_model_points(
        seat,
        stock,
        crop_head=crop_head,
        label="target capture",
    )
    stock.ReferencedDocument.FeatureByName = lambda _name: pytest.fail(
        "settled frame must not re-read restored source geometry",
    )
    # Simulate a settled native transform changing behind the recorded view
    # properties. Keep the semantic center exact for the axis-only faults.
    if fault == "rotated":
        object.__setattr__(stock, "Angle", stock.Angle + 0.013)
    elif fault == "axial-mirror":
        stock.sheet_signs = (-1.0, 1.0)
    elif fault == "radial-mirror":
        stock.sheet_signs = (1.0, -1.0)
    elif fault == "scale":
        stock.projection_factor = 1.02
    if fault in {"rotated", "axial-mirror", "radial-mirror", "scale"}:
        actual = stock.sheet_point((0.031, -0.043 + semantic_x, 0.057))
        object.__setattr__(stock, "Position", tuple(
            stock.Position[index] + center[index] - actual[index] for index in range(2)
        ))
    elif fault in {"center-x", "center-y"}:
        index = 0 if fault == "center-x" else 1
        shifted = list(stock.Position)
        shifted[index] += 2e-8  # Strict reader tolerance is 1e-8 metres.
        object.__setattr__(stock, "Position", tuple(shifted))
    assert tuple(stock.ScaleRatio) == scale and stock.UseSheetScale == 0
    seat.log.clear()
    seat.display_dirty = True
    if fault == "none":
        drawing._assert_supplier_profile_frame(
            seat, stock, center, scale, points=points, label="settled source",
        )
    else:
        reason = "center moved" if fault.startswith("center-") else "axes lost"
        with pytest.raises(RuntimeError, match=reason):
            drawing._assert_supplier_profile_frame(
                seat, stock, center, scale, points=points, label="settled source",
            )
    kinds = [entry[0] for entry in seat.log]
    assert not {"source-feature", "inverse-source-frame", "sketch-to-model"}.intersection(kinds)
    assert kinds.count("project-frame") == 1
    assert kinds.count("update") == 1
    assert kinds.index("update") < kinds.index("project-frame")
    assert not (stock.TRANSFORMS | {"move", "crop-sketch", "import"}).intersection(kinds)


@pytest.mark.parametrize(
    "failure,reason",
    [
        ("missing", "cannot create supplier source point"),
        ("zeros", "point marshaling changed"),
        ("short", "point marshaling changed"),
        ("unmapped", "cannot map supplier source point"),
        ("nonfinite", "source model point is invalid"),
    ],
)
def test_supplier_profile_mapping_rejects_bad_native_math_points(
    monkeypatch, failure, reason,
) -> None:
    seat, stock = _supplier_seat(monkeypatch, drawing.STOCK_CENTER, drawing.STOCK_SCALE)

    def create(values):
        point = _Utility().CreatePoint(values)
        if failure == "missing":
            return None
        if failure == "zeros":
            return _Point((0.0, 0.0, 0.0))
        if failure == "short":
            return _Point(point.ArrayData[:2])
        return SimpleNamespace(
            ArrayData=point.ArrayData,
            MultiplyTransform=lambda _transform: (
                None if failure == "unmapped" else _Point((math.nan, 0.0, 0.0))
            ),
        )

    monkeypatch.setattr(seat, "GetMathUtility", lambda: SimpleNamespace(CreatePoint=create))
    with pytest.raises(RuntimeError, match=reason):
        drawing._supplier_profile_model_points(
            seat, stock, crop_head=False, label="bad source math",
        )
    assert not {"project-frame", "crop-sketch", "import"}.intersection(
        entry[0] for entry in seat.log
    )


def test_full_supplier_profile_fits_its_fixed_cell_only_when_horizontal() -> None:
    assert drawing.STOCK_SCALE == (2.0, 1.0)
    points = drawing.SUPPLIER_PROFILE_MM
    xmin = min(point[0] for point in points) / 1000.0
    xmax = max(point[0] for point in points) / 1000.0
    ymin = min(point[1] for point in points) / 1000.0
    ymax = max(point[1] for point in points) / 1000.0
    ratio = drawing.STOCK_SCALE[0] / drawing.STOCK_SCALE[1]
    cx, cy = drawing.STOCK_CENTER
    semantic_x = (xmin + xmax) / 2.0
    horizontal = (
        cx + ratio * (xmin - semantic_x), cy + ratio * ymin,
        cx + ratio * (xmax - semantic_x), cy + ratio * ymax,
    )
    left, bottom, right, top = drawing.STOCK_VIEW_CELL
    assert left <= horizontal[0] < horizontal[2] <= right
    assert bottom <= horizontal[1] < horizontal[3] <= top
    assert ratio * (xmax - xmin) > top - bottom


def _supplier_capture_value():
    vertices = tuple(
        (float(x) / 1000.0, float(y) / 1000.0, 0.0)
        for x, y in drawing.SUPPLIER_PROFILE_MM
    )
    pairs = tuple(
        (index, (index + 1) % len(vertices)) for index in range(len(vertices))
    ) + tuple(drawing.SUPPLIER_PROFILE_SECTIONS)
    model_points = tuple(vertices[index] for pair in pairs for index in pair)
    xmin = min(point[0] for point in vertices)
    xmax = max(point[0] for point in vertices)
    axes = ((0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.0, 0.001, 0.0))
    return drawing.SupplierStockCapture(
        drawing.NativeSketchGeometry(
            model_points, tuple(range(0, len(model_points), 2)), ()
        ),
        (*axes, ((xmin + xmax) / 2.0, 0.0, 0.0)),
        (*axes, (xmin / 2.0, 0.0, 0.0)),
        str(drawing.SOURCE.resolve()),
    )


def _supplier_settled_seat(monkeypatch, *, newline="\n"):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "_log_supplier_view_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(
        drawing, "assert_supplier_annotations_fit", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        drawing, "_assert_supplier_profile_ink", lambda *_args, **_kwargs: None
    )
    presentations = []
    monkeypatch.setattr(
        drawing,
        "assert_supplier_reference_dimension",
        lambda adapter, display, **kwargs: presentations.append((display, kwargs)),
    )
    membership = []
    monkeypatch.setattr(
        drawing,
        "_assert_dimension_source",
        lambda adapter, view, display, **kwargs: membership.append(
            (view, display, kwargs)
        ),
    )
    capture = _supplier_capture_value()
    frames = []
    monkeypatch.setattr(
        drawing, "_assert_supplier_profile_frame",
        lambda _adapter, view, center, scale, *, points, label: frames.append(
            (view.Name, center, scale, points)
        ),
    )
    template = drawing.DRAWING_TEMPLATES[drawing.SPEC.layout]
    monkeypatch.setattr(
        drawing, "sheet_drawable_region",
        lambda *_args, **_kwargs: SimpleNamespace(
            xmin=0.0, ymin=0.0, xmax=template.width_m, ymax=template.height_m,
        ),
    )
    rows = {row.name: row for row in drawing.SUPPLIER_REFERENCE_DIMENSIONS}
    views = []
    for name, keep, scale, cropped in (
        ("stock", drawing.STOCK_KEEP, drawing.STOCK_SCALE, False),
        ("head", drawing.STOCK_HEAD_KEEP, drawing.STOCK_HEAD_SCALE, True),
    ):
        annotations = []
        for dimension_name in keep:
            row = rows[dimension_name]
            band = row.deviations_mm
            tolerance = SimpleNamespace(
                Type=0 if band is None else 3,
                GetMinValue=lambda band=band: 0.0 if band is None else band[0] / 1000.0,
                GetMaxValue=lambda band=band: 0.0 if band is None else band[1] / 1000.0,
            )
            native = SimpleNamespace(
                FullName=f"{row.name}@{drawing.SUPPLIER_STOCK_FEATURE}@source",
                DrivenState=1, Tolerance=tolerance,
            )
            display = SimpleNamespace(
                Type2=row.native_type,
                GetDimension2=lambda _index, native=native: native,
                GetPrimaryTolPrecision2=lambda: drawing.SUPPLIER_PRECISION,
            )

            def no_drawing_point_proof():
                pytest.fail("model import association must not inspect drawing point wrappers")

            annotations.append(SimpleNamespace(
                name=row.name, Visible=1,
                GetSpecificAnnotation=lambda display=display: display,
                GetAttachedEntityTypes=no_drawing_point_proof,
                GetAttachedEntities3=no_drawing_point_proof,
            ))
        views.append(SimpleNamespace(
            Name=name, ReferencedConfiguration=drawing.SUPPLIER_STOCK_CONFIGURATION,
            UseSheetScale=0, ScaleRatio=scale,
            GetReferencedModelName=lambda: str(drawing.SOURCE),
            ReferencedDocument=SimpleNamespace(GetPathName=lambda: str(drawing.SOURCE)),
            IsCropped=lambda cropped=cropped: cropped,
            UpdateViewDisplayGeometry=lambda: None,
            GetAnnotations=lambda annotations=annotations: annotations,
        ))
    monkeypatch.setattr(drawing, "iter_views", lambda _adapter: views)
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            ActivateSheet=lambda _name: True, GetCurrentSheet=lambda: object(),
        ),
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )
    text = drawing.SUPPLIER_STOCK_TITLE
    assert "\n" in text
    state = SimpleNamespace(text=text.replace("\n", newline))
    annotation = SimpleNamespace(Visible=1, OwnerType=1)
    note = SimpleNamespace(
        GetText=lambda: state.text, GetAnnotation=lambda: annotation,
        GetExtent=lambda: (0.03, 0.22, 0.0, 0.15, 0.24, 0.0),
    )
    notes = [(note, text, (0.02, 0.20, 0.18, 0.25))]
    monkeypatch.setattr(
        drawing, "_assert_supplier_source_bodiless",
        lambda *_args: pytest.fail("settled checks must not switch source configurations"),
    )
    return SimpleNamespace(
        adapter=adapter, views=views, notes=notes, capture=capture,
        frames=frames, membership=membership, presentations=presentations, state=state,
    )


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_final_supplier_labels_accept_native_line_endings_but_not_changed_text(monkeypatch, newline):
    seat = _supplier_settled_seat(monkeypatch, newline=newline)
    drawing._check_supplier_stock(seat.adapter, *seat.views, seat.notes, seat.capture)
    assert seat.frames == [
        ("stock", drawing.STOCK_CENTER, drawing.STOCK_SCALE, seat.capture.full_frame),
        ("head", drawing.STOCK_HEAD_CENTER, drawing.STOCK_HEAD_SCALE, seat.capture.head_frame),
    ]
    assert len(seat.membership) == len(drawing.SUPPLIER_REFERENCE_DIMENSIONS)
    assert all(
        call[2]["feature"] == drawing.SUPPLIER_STOCK_FEATURE for call in seat.membership
    )
    assert {call[2]["name"] for call in seat.membership} == {
        row.name for row in drawing.SUPPLIER_REFERENCE_DIMENSIONS
    }
    assert all(
        contract["configuration"] == drawing.SUPPLIER_STOCK_CONFIGURATION
        for _, contract in seat.presentations
    )
    seat.state.text = seat.state.text.replace("REFERENCE ONLY", "REFERENCE")
    with pytest.raises(RuntimeError, match="source label changed"):
        drawing._check_supplier_stock(seat.adapter, *seat.views, seat.notes, seat.capture)


@pytest.mark.parametrize("fault,reason", [
    ("sheet", "cannot activate"), ("view-coverage", "two native views"),
    ("identity", "identity changed"), ("view-path", "path changed"),
    ("model-path", "path changed"), ("configuration", "configuration/scale/crop"),
    ("sheet-scale", "configuration/scale/crop"), ("scale", "configuration/scale/crop"),
    ("crop", "configuration/scale/crop"), ("coverage", "coverage changed"),
    ("hidden", "dimension is hidden"), ("owner", "ownership/type"),
    ("type", "ownership/type"), ("driven", "ownership/type"),
    ("tolerance-type", "limit type"), ("tolerance-band", "limit band"),
    ("tolerance-precision", "limit precision"), ("model-membership", "model member changed"),
    ("presentation", "native presentation changed"), ("note-owner", "source label changed"),
    ("note-hidden", "source label changed"), ("note-bounds", "source label changed"),
])
def test_supplier_settled_capture_retains_native_guards(monkeypatch, fault, reason):
    seat = _supplier_settled_seat(monkeypatch)
    full = seat.views[0]
    annotation = full.GetAnnotations()[0]
    display = annotation.GetSpecificAnnotation()
    native = display.GetDimension2(0)
    if fault == "sheet":
        seat.adapter.currentModel.ActivateSheet = lambda _name: False
    elif fault == "view-coverage":
        monkeypatch.setattr(drawing, "iter_views", lambda _adapter: seat.views[:1])
    elif fault == "identity":
        seat.adapter.swApp.IsSame = lambda *_args: 0
    elif fault == "view-path":
        full.GetReferencedModelName = lambda: "wrong-source.SLDPRT"
    elif fault == "model-path":
        full.ReferencedDocument.GetPathName = lambda: "wrong-source.SLDPRT"
    elif fault == "configuration":
        full.ReferencedConfiguration = "Original"
    elif fault == "sheet-scale":
        full.UseSheetScale = 1
    elif fault == "scale":
        full.ScaleRatio = (1.0, 1.0)
    elif fault == "crop":
        full.IsCropped = lambda: True
    elif fault == "coverage":
        full.GetAnnotations = lambda: []
    elif fault == "hidden":
        annotation.Visible = 0
    elif fault == "owner":
        native.FullName = "SupplierHeadHeight@UnrelatedSketch@source"
    elif fault == "type":
        display.Type2 = -1
    elif fault == "driven":
        native.DrivenState = 0
    elif fault == "tolerance-type":
        native.Tolerance.Type = -1
    elif fault == "tolerance-band":
        native.Tolerance.GetMaxValue = lambda: 0.1
    elif fault == "tolerance-precision":
        display.GetPrimaryTolPrecision2 = lambda: -1
    elif fault in ("model-membership", "presentation"):
        def refuse(*_args, **_kwargs):
            raise RuntimeError(reason)

        monkeypatch.setattr(
            drawing,
            "_assert_dimension_source" if fault == "model-membership" else "assert_supplier_reference_dimension",
            refuse,
        )
    elif fault == "note-owner":
        seat.notes[0][0].GetAnnotation().OwnerType = 0
    elif fault == "note-hidden":
        seat.notes[0][0].GetAnnotation().Visible = 0
    else:
        seat.notes[0][0].GetExtent = lambda: (-0.1, 0.22, 0.0, 0.15, 0.24, 0.0)
    with pytest.raises(RuntimeError, match=reason):
        drawing._check_supplier_stock(seat.adapter, *seat.views, seat.notes, seat.capture)


def test_supplier_diagnostics_read_native_vertices_not_expected_profile(monkeypatch):
    import ast

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "double_array", lambda values: _DoubleArray(values))
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(drawing, "visible_reference_geometry", lambda *_args: [("OtherSketch", "sketch")])
    messages = []
    monkeypatch.setattr(drawing._telemetry, "info", messages.append)
    native_points = [_SketchPoint((0.004, 0.008, 0.0)), _SketchPoint((0.007, 0.012, 0.0))]
    source_transform = SimpleNamespace(
        ArrayData=tuple(range(16)),
        Inverse=lambda: lambda xyz: (xyz[0] + 0.020, xyz[1] - 0.030, xyz[2]),
    )
    segment = SimpleNamespace(
        GetType=lambda: 0, ConstructionGeometry=True,
        GetStartPoint2=lambda: native_points[0], GetEndPoint2=lambda: native_points[1],
    )
    sketch = SimpleNamespace(
        ModelToSketchTransform=source_transform,
        GetSketchPoints2=lambda: native_points, GetSketchSegments=lambda: [segment],
    )
    feature = SimpleNamespace(Visible=1, GetSpecificFeature2=lambda: sketch)
    source = SimpleNamespace(
        FeatureByName=lambda _name: feature, GetPathName=lambda: "source.SLDPRT",
        ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Default")),
    )
    bad_outline = (0.1233162, -0.08746936549327414, 0.1555234, 0.1275858660249454)
    view = SimpleNamespace(
        Name="Drawing View4", ReferencedDocument=source,
        ReferencedConfiguration=drawing.SUPPLIER_STOCK_CONFIGURATION,
        UseSheetScale=0, ScaleRatio=drawing.STOCK_SCALE, Angle=0.41,
        Position=(0.2, 0.1), GetOutline=lambda: bad_outline, IsCropped=lambda: False,
        ModelToViewTransform=SimpleNamespace(ArrayData=tuple(range(16, 32))),
        GetSketch=lambda: SimpleNamespace(
            ModelToSketchTransform=SimpleNamespace(ArrayData=tuple(range(32, 48))),
        ),
    )
    adapter = SimpleNamespace(swApp=SimpleNamespace(GetMathUtility=lambda: _Utility()))
    monkeypatch.setattr(
        drawing, "model_points_in_view",
        lambda _adapter, _view, points, *, label: [(2 * x + 0.2, 2 * y + 0.1) for x, y, _z in points],
    )
    drawing._log_supplier_view_state(adapter, view, stage="control", geometry=True)
    fields = {
        line.split(" ", 3)[3].split("=", 1)[0]: ast.literal_eval(line.split("=", 1)[1])
        for line in messages
    }
    assert fields["pose"]["outline_m"] == bad_outline
    assert fields["pose"]["angle_rad"] == 0.41
    assert fields["source_geometry"]["source_active_configuration"] == "Default"
    assert fields["source_geometry"]["source_points_m"] == [(0.004, 0.008, 0.0), (0.007, 0.012, 0.0)]
    assert fields["source_geometry"]["sheet_vertex_bounds_m"] == pytest.approx((0.248, 0.056, 0.254, 0.064))
    assert fields["source_geometry"]["segments"] == [{
        "type": 0, "construction": True,
        "endpoints_m": [(0.004, 0.008, 0.0), (0.007, 0.012, 0.0)],
    }]
    assert fields["model_to_view"] == tuple(range(16, 32))
    assert fields["sheet_to_view_sketch"] == tuple(range(32, 48))
    assert fields["source_shown_references"] == [("OtherSketch", "sketch")]
    # Missing diagnostic data must be reported, not fabricated or fatal.
    view.ModelToViewTransform = None
    messages.clear()
    drawing._log_supplier_view_state(adapter, view, stage="missing transform")
    assert "read_error" in messages[-1] and "AttributeError" in messages[-1]


@pytest.mark.parametrize("identity", [0, 1])
@pytest.mark.parametrize("failure_stage", ["ink", "annotations"])
def test_supplier_failure_captures_sheet_after_frame_ink_and_annotations(monkeypatch, identity, failure_stage):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    views = [
        SimpleNamespace(
            Name=name, ReferencedConfiguration=drawing.SUPPLIER_STOCK_CONFIGURATION,
            UseSheetScale=0, ScaleRatio=scale, IsCropped=lambda cropped=cropped: cropped,
            GetReferencedModelName=lambda: str(drawing.SOURCE),
            ReferencedDocument=SimpleNamespace(GetPathName=lambda: str(drawing.SOURCE)),
            UpdateViewDisplayGeometry=lambda: None,
        )
        for name, scale, cropped in (
            ("Drawing View4", drawing.STOCK_SCALE, False),
            ("Drawing View5", drawing.STOCK_HEAD_SCALE, True),
        )
    ]
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(ActivateSheet=lambda _name: True, GetCurrentSheet=lambda: object()),
        swApp=SimpleNamespace(IsSame=lambda _first, _second: identity),
    )
    monkeypatch.setattr(drawing, "iter_views", lambda _adapter: views)
    monkeypatch.setattr(drawing, "sheet_drawable_region", lambda *_args, **_kwargs: SimpleNamespace(
        xmin=0.0, ymin=0.0, xmax=0.5, ymax=0.5,
    ))
    calls = []
    monkeypatch.setattr(drawing, "_log_supplier_view_state", lambda _adapter, view, **kwargs: calls.append(
        ("snapshot", view.Name, kwargs["stage"]),
    ))
    monkeypatch.setattr(drawing, "_assert_supplier_profile_frame", lambda _adapter, view, *_args, **_kwargs: calls.append(
        ("frame", view.Name),
    ))
    refusal = RuntimeError(f"native {failure_stage} leaves its cell")

    def ink(_adapter, view, *_args, **_kwargs):
        calls.append(("ink", view.Name))
        if failure_stage == "ink":
            raise refusal

    monkeypatch.setattr(drawing, "_assert_supplier_profile_ink", ink)

    def cell(*_args, **_kwargs):
        calls.append(("annotations",))
        raise refusal

    def capture(actual_adapter, label, message, **kwargs):
        assert actual_adapter is adapter
        assert label == f"{drawing.PART_STEM}-supplier-envelope"
        assert kwargs["sheet_png"] is True
        calls.append(("capture", kwargs["exception"]))
        raise kwargs["exception"]

    monkeypatch.setattr(drawing, "assert_supplier_annotations_fit", cell)
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    monkeypatch.setattr(
        drawing,
        "_assert_supplier_source_bodiless",
        lambda *_args: pytest.fail(
            "settled checks must not switch source configurations"
        ),
    )
    captured_source = _supplier_capture_value()
    with pytest.raises(RuntimeError) as caught:
        drawing._verify_supplier_stock(adapter, *views, [], captured_source)
    assert calls[-1] == ("capture", caught.value)
    if identity:
        assert caught.value is refusal
        assert calls[:4] == [
            ("snapshot", view.Name, f"{view.Name}: settled {phase} refresh")
            for view in views for phase in ("before", "after")
        ]
        expected = [("frame", "Drawing View4"), ("ink", "Drawing View4")]
        if failure_stage == "annotations":
            expected.append(("annotations",))
        assert calls[4:-1] == expected
    else:
        assert "identity changed" in str(caught.value)
        assert len(calls) == 1


def _supplier_ink_seat(monkeypatch, cropped):
    """Capture native endpoints once; final bounds use only immutable floats."""
    import _drawing_detail_crop as crop
    import _drawing_projection as projection

    for module in (drawing, crop):
        monkeypatch.setattr(module, "_early_bound", lambda obj, _interface: obj)
        monkeypatch.setattr(module, "double_array", _DoubleArray)
    monkeypatch.setattr(projection, "double_array", _DoubleArray)

    def invoke(obj, _interface, member, *args):
        if member == "ModelToViewTransform":
            assert messages[-1] == "refresh"
        value = getattr(obj, member)
        return (
            value if member in ("ModelToViewTransform", "ArrayData") else value(*args)
        )

    monkeypatch.setattr(projection, "_com_invoke", invoke)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    points = [(*point, 0.0) for point in drawing.SUPPLIER_PROFILE_MM]
    pairs = [(index, (index + 1) % len(points)) for index in range(len(points))]
    pairs += list(drawing.SUPPLIER_PROFILE_SECTIONS)
    lines = []
    for first, last in pairs:
        start = _SketchPoint(tuple(value / 1000.0 for value in points[first]))
        end = _SketchPoint(tuple(value / 1000.0 for value in points[last]))
        lines.append(
            SimpleNamespace(
                GetType=lambda: 0,
                ConstructionGeometry=True,
                GetStartPoint2=lambda start=start: start,
                GetEndPoint2=lambda end=end: end,
            )
        )
    assert len(lines) == 18

    def source_to_model(xyz):
        return (0.031 - xyz[1], xyz[0] - 0.043, xyz[2] + 0.057)

    source = SimpleNamespace(
        GetSketchSegments=lambda: lines,
        ModelToSketchTransform=SimpleNamespace(Inverse=lambda: source_to_model),
    )
    feature = SimpleNamespace(
        Name=drawing.SUPPLIER_STOCK_FEATURE,
        GetTypeName2=lambda: "ProfileFeature",
        GetSpecificFeature2=lambda: source,
        Visible=0,
        GetErrorCode2=lambda: (0, False),
    )
    model = SimpleNamespace(FeatureByName=lambda _name: feature)
    center = drawing.STOCK_HEAD_CENTER if cropped else drawing.STOCK_CENTER
    scale = drawing.STOCK_HEAD_SCALE if cropped else drawing.STOCK_SCALE
    ratio = scale[0] / scale[1]
    xs = [point[0] / 1000.0 for point in points]
    semantic_x = (min(xs) / 2.0) if cropped else (min(xs) + max(xs)) / 2.0
    projected = []

    def model_to_sheet(xyz):
        projected.append(tuple(xyz))
        return (
            center[0] + ratio * (xyz[1] + 0.043 - semantic_x),
            center[1] + ratio * (0.031 - xyz[0]),
            0.0,
        )

    # Crop sketch coordinates are rotated and translated independently of source.
    circle = _Arc(
        (0.017, -0.023, 0.0),
        drawing.STOCK_HEAD_RADIUS_MM
        * drawing.STOCK_HEAD_SCALE[0]
        / drawing.STOCK_HEAD_SCALE[1]
        / 1000.0,
    )
    circle.GetType = lambda: 1
    circle.IsCircle = lambda: 1
    drawing_segments = [circle] if cropped else []

    def crop_to_sheet(xyz):
        return (
            drawing.STOCK_HEAD_CENTER[0] - (xyz[1] + 0.023),
            drawing.STOCK_HEAD_CENTER[1] + (xyz[0] - 0.017),
            xyz[2],
        )

    sketch = SimpleNamespace(
        GetSketchSegments=lambda: drawing_segments,
        ModelToSketchTransform=SimpleNamespace(Inverse=lambda: crop_to_sheet),
    )

    def forbidden_outline():
        raise AssertionError("GetOutline is not native construction ink")

    view = SimpleNamespace(
        Name="MSC native ink",
        ReferencedConfiguration=drawing.SUPPLIER_STOCK_CONFIGURATION,
        ReferencedDocument=model,
        GetBodiesCount=lambda: 0,
        ModelToViewTransform=model_to_sheet,
        GetSketch=lambda: sketch,
        IsCropped=lambda: cropped,
        GetOutline=forbidden_outline,
        UpdateViewDisplayGeometry=lambda: messages.append("refresh"),
    )
    adapter = SimpleNamespace(swApp=SimpleNamespace(GetMathUtility=lambda: _Utility()))
    messages = []
    monkeypatch.setattr(drawing._telemetry, "info", messages.append)

    geometry = drawing.NativeSketchGeometry(
        tuple(
            source_to_model((point.X, point.Y, point.Z))
            for line in lines
            for point in (line.GetStartPoint2(), line.GetEndPoint2())
        ),
        tuple(range(0, 36, 2)),
        (),
    )

    return SimpleNamespace(
        adapter=adapter,
        view=view,
        lines=lines,
        geometry=geometry,
        feature=feature,
        source=source,
        drawing_segments=drawing_segments,
        circle=circle,
        projected=projected,
        messages=messages,
        cell=drawing.STOCK_HEAD_CELL if cropped else drawing.STOCK_VIEW_CELL,
    )


@pytest.mark.parametrize("cropped", [False, True])
def test_supplier_profile_ink_does_not_use_feature_visibility_as_view_receipt(
    monkeypatch, cropped,
):
    seat = _supplier_ink_seat(monkeypatch, cropped)
    seat.view.GetCorresponding = lambda _feature: pytest.fail(
        "corresponding feature visibility is not a drawing-view receipt"
    )
    drawing._assert_supplier_profile_ink(
        seat.adapter, seat.view, seat.cell, seat.geometry, cropped=cropped,
    )


@pytest.mark.parametrize("cropped", [False, True])
def test_supplier_profile_ink_projects_immutable_target_without_live_source_reads(
    monkeypatch, cropped
):
    seat = _supplier_ink_seat(monkeypatch, cropped)
    if cropped:
        monkeypatch.setattr(
            drawing,
            "native_sketch_view_bounds",
            lambda *_args, **_kwargs: pytest.fail(
                "head crop projected its hidden full carrier"
            ),
        )
    seat.feature.GetSpecificFeature2 = lambda: pytest.fail(
        "final ink read live source sketch"
    )
    seat.source.GetSketchSegments = lambda: pytest.fail(
        "final ink read live source segments"
    )
    seat.source.ModelToSketchTransform.Inverse = lambda: pytest.fail(
        "final ink read source frame"
    )
    for line in seat.lines:
        line.GetStartPoint2 = lambda: pytest.fail("final ink read source endpoint")
    drawing._assert_supplier_profile_ink(
        seat.adapter,
        seat.view,
        seat.cell,
        seat.geometry,
        cropped=cropped,
    )
    assert len(seat.projected) == (0 if cropped else 36)
    assert all(point[2] == 0.057 for point in seat.projected)


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("configuration", "configuration"),
        ("drawing-geometry", "drawing-sketch geometry"),
    ],
)
def test_supplier_profile_ink_rejects_current_view_inventory_changes(
    monkeypatch, fault, reason
):
    seat = _supplier_ink_seat(monkeypatch, False)
    if fault == "configuration":
        seat.view.ReferencedConfiguration = "Default"
    else:
        seat.drawing_segments.append(seat.circle)
    with pytest.raises(RuntimeError, match=reason):
        drawing._assert_supplier_profile_ink(
            seat.adapter, seat.view, seat.cell, seat.geometry, cropped=False
        )


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("shifted", "crop frame"),
        ("size", "crop frame"),
        ("noncircle", "complete circle"),
        ("nonarc", "sketch arc"),
        ("null-inverse", "inverse is unavailable"),
    ],
)
def test_supplier_crop_profile_rejects_bad_geometry_before_consumption(
    monkeypatch, fault, reason
):
    seat = _supplier_ink_seat(monkeypatch, True)
    if fault == "shifted":
        seat.circle.center = (0.018, -0.023, 0.0)
    elif fault == "size":
        seat.circle.radius *= 1.1
    elif fault == "noncircle":
        seat.circle.IsCircle = lambda: 0
    elif fault == "null-inverse":
        seat.view.GetSketch().ModelToSketchTransform.Inverse = lambda: None
    else:
        seat.circle.GetType = lambda: 0
    with pytest.raises(RuntimeError, match=reason):
        drawing._assert_supplier_crop_circle(
            seat.adapter, seat.view, seat.circle, seat.cell
        )


@pytest.mark.parametrize("cropped", [True, False])
def test_supplier_final_crop_state_does_not_require_consumed_profile(monkeypatch, cropped):
    seat = _supplier_ink_seat(monkeypatch, True)
    drawing._assert_supplier_crop_circle(
        seat.adapter, seat.view, seat.circle, seat.cell
    )
    seat.drawing_segments.clear()  # Native Crop2 consumes the selected profile.
    seat.view.IsCropped = lambda: cropped
    if cropped:
        drawing._assert_supplier_profile_ink(
            seat.adapter, seat.view, seat.cell, seat.geometry, cropped=True
        )
    else:
        with pytest.raises(RuntimeError, match="no longer cropped"):
            drawing._assert_supplier_profile_ink(
                seat.adapter, seat.view, seat.cell, seat.geometry, cropped=True
            )


@pytest.mark.parametrize("cropped", [False, True])
def test_supplier_profile_ink_cell_has_zero_slack(monkeypatch, cropped):
    seat = _supplier_ink_seat(monkeypatch, cropped)
    if cropped:
        inverse = seat.view.GetSketch().ModelToSketchTransform.Inverse()
        cx, cy, cz = seat.circle.center
        center = inverse((cx, cy, cz))
        radial = inverse((cx, cy + seat.circle.radius, cz))
        right = center[0] + abs(radial[0] - center[0])
    else:
        right = max(
            seat.view.ModelToViewTransform(
                (0.031 - point.Y, point.X - 0.043, point.Z + 0.057)
            )[0]
            for line in seat.lines
            for point in (line.GetStartPoint2(), line.GetEndPoint2())
        )
    left, bottom, _right, top = seat.cell

    def check(cell):
        if cropped:
            drawing._assert_supplier_crop_circle(
                seat.adapter, seat.view, seat.circle, cell
            )
        else:
            drawing._assert_supplier_profile_ink(
                seat.adapter, seat.view, cell, seat.geometry, cropped=False
            )

    check((left, bottom, right, top))
    with pytest.raises(RuntimeError, match="ink leaves its cell"):
        check((left, bottom, math.nextafter(right, -math.inf), top))


@pytest.mark.parametrize("fault", ["one-ulp", "duplicate"])
def test_supplier_profile_state_matches_vertices_without_float_ordering(fault):
    row = next(
        row
        for row in drawing.SUPPLIER_REFERENCE_DIMENSIONS
        if drawing.SUPPLIER_PROFILE_MM[row.vertices[0]][0]
        == drawing.SUPPLIER_PROFILE_MM[row.vertices[1]][0]
        and drawing.SUPPLIER_PROFILE_MM[row.vertices[0]][1]
        != drawing.SUPPLIER_PROFILE_MM[row.vertices[1]][1]
    )
    points = sorted(
        [(*drawing.SUPPLIER_PROFILE_MM[index], 0.0) for index in row.vertices],
        key=lambda point: point[1],
    )
    points = [
        (math.nextafter(points[0][0], math.inf), *points[0][1:]),
        (math.nextafter(points[1][0], -math.inf), *points[1][1:]),
    ]
    if fault == "duplicate":
        points[1] = points[0]
    if fault == "duplicate":
        with pytest.raises(RuntimeError, match="source-diagram vertices"):
            drawing._assert_supplier_profile_vertices(row, points)
    else:
        drawing._assert_supplier_profile_vertices(row, points)


@pytest.mark.parametrize(
    "actual,expected",
    [
        ([(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]),
        ([(0.0, 0.0, 0.0), (1e-9, 0.0, 0.0)], [(0.0, 0.0, 0.0), (1e-9, 0.0, 0.0)]),
    ],
)
def test_supplier_points_match_refuses_duplicate_or_ambiguous_points(actual, expected):
    assert not drawing._supplier_points_match(actual, expected, tolerance=1e-8)


class _SupplierCensusTransform:
    def __init__(self):
        self.ArrayData = [
            0.0,
            -1.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.043,
            0.031,
            -0.057,
            1.0,
            0.0,
            0.0,
            0.0,
        ]

    def Inverse(self):
        matrix = self.ArrayData
        rotation = [matrix[column * 3 + row] for row in range(3) for column in range(3)]
        translation = [
            -sum(matrix[9 + row] * rotation[row * 3 + axis] for row in range(3))
            for axis in range(3)
        ]
        return _SupplierCensusInverse(rotation + translation + [1.0, 0.0, 0.0, 0.0])


class _SupplierCensusInverse:
    def __init__(self, matrix):
        self.ArrayData = matrix

    def __call__(self, point):
        matrix = self.ArrayData
        return tuple(
            sum(point[row] * matrix[row * 3 + axis] for row in range(3))
            + matrix[9 + axis]
            for axis in range(3)
        )


def _supplier_body_census_seat(monkeypatch, *, original="Original", dirty=False):
    import _supplier_reference_geometry as native_geometry

    monkeypatch.setattr(native_geometry, "_bind", lambda obj, _interface: obj)
    monkeypatch.setattr(native_geometry, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "double_array", _DoubleArray)
    state = SimpleNamespace(configuration=original, dirty=dirty, calls=[], messages=[])
    installed = "Installed"
    counts = {installed: (1, 0), drawing.SUPPLIER_STOCK_CONFIGURATION: (0, 0)}
    geometry = {}
    displays = {}
    pairs = [
        (index, (index + 1) % len(drawing.SUPPLIER_PROFILE_MM))
        for index in range(len(drawing.SUPPLIER_PROFILE_MM))
    ] + list(drawing.SUPPLIER_PROFILE_SECTIONS)
    for configuration in {original, installed, drawing.SUPPLIER_STOCK_CONFIGURATION}:
        lines = []
        for first, last in pairs:
            start, end = (
                _SketchPoint(
                    (
                        *[
                            value / 1000.0
                            for value in drawing.SUPPLIER_PROFILE_MM[index]
                        ],
                        0.0,
                    )
                )
                for index in (first, last)
            )
            lines.append(
                SimpleNamespace(
                    GetType=lambda: 0,
                    ConstructionGeometry=True,
                    GetStartPoint2=lambda start=start: start,
                    GetEndPoint2=lambda end=end: end,
                )
            )
        geometry[configuration] = SimpleNamespace(
            GetSketchSegments=lambda lines=lines: lines,
            lines=lines,
            Is3D=lambda: False,
            GetSketchBlockInstanceCount=lambda: 0,
            GetSketchTextSegments=lambda: (),
            GetUserPointsCount=lambda: 0,
            ModelToSketchTransform=_SupplierCensusTransform(),
        )
        displays[configuration] = []
        for row in drawing.SUPPLIER_REFERENCE_DIMENSIONS:
            band = row.deviations_mm or (0.0, 0.0)
            native = SimpleNamespace(
                FullName=f"{row.name}@{drawing.SUPPLIER_STOCK_FEATURE}@source",
                DrivenState=1,
                Tolerance=SimpleNamespace(
                    Type=0 if row.deviations_mm is None else 3,
                    GetMinValue=lambda band=band: band[0] / 1000.0,
                    GetMaxValue=lambda band=band: band[1] / 1000.0,
                ),
            )
            attachment_points = tuple(
                _SketchPoint(
                    (
                        *[
                            value / 1000.0
                            for value in drawing.SUPPLIER_PROFILE_MM[index]
                        ],
                        0.0,
                    )
                )
                for index in row.vertices
            )
            annotation = SimpleNamespace(
                GetAttachedEntityTypes=lambda: (11, 11),
                GetAttachedEntities3=lambda points=attachment_points: points,
            )
            displays[configuration].append(
                SimpleNamespace(
                    Type2=row.native_type,
                    GetDimension2=lambda _index, native=native: native,
                    GetPrimaryTolPrecision2=lambda: drawing.SUPPLIER_PRECISION,
                    GetAnnotation=lambda annotation=annotation: annotation,
                )
            )

    def feature(name):
        assert name == drawing.SUPPLIER_STOCK_FEATURE
        state.calls.append(("feature", state.configuration))
        return SimpleNamespace(
            GetSpecificFeature2=lambda: geometry[state.configuration],
            GetErrorCode2=lambda: (0, False),
        )

    def show(configuration):
        state.calls.append(("show", configuration))
        state.configuration = configuration
        return True

    def rebuild():
        state.calls.append(("rebuild", state.configuration))
        return True

    def bodies(kind, visible_only):
        assert visible_only is False
        state.calls.append(("bodies", state.configuration, kind))
        return tuple(object() for _ in range(counts[state.configuration][kind]))

    # No save, feature-edit or other geometry-mutation APIs on this fake.
    model = SimpleNamespace(
        ShowConfiguration2=show,
        EditRebuild3=rebuild,
        GetBodies2=bodies,
        GetSaveFlag=lambda: state.dirty,
        IsOpenedReadOnly=lambda: True,
        FeatureByName=feature,
        GetPathName=lambda: str(drawing.SOURCE),
        Parameter=lambda name: next(
            (
                display.GetDimension2(0)
                for display in displays[state.configuration]
                if display.GetDimension2(0).FullName.rsplit("@", 1)[0] == name
            ),
            None,
        ),
    )
    views = [
        SimpleNamespace(
            Name=name,
            ReferencedDocument=model,
            ReferencedConfiguration=configuration,
            GetBodiesCount=lambda: 0,
            GetReferencedModelName=lambda: str(drawing.SOURCE),
            GetCorresponding=lambda obj: obj,
        )
        for name, configuration in (
            ("full", drawing.SUPPLIER_STOCK_CONFIGURATION),
            ("head", drawing.SUPPLIER_STOCK_CONFIGURATION),
            ("solid", installed),
        )
    ]
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(
            IsSame=lambda first, second: int(first is second),
            GetMathUtility=lambda: _Utility(),
        )
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "_bind", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(
        drawing,
        "active_configuration_name",
        lambda _adapter, _model: state.configuration,
    )
    monkeypatch.setattr(drawing._telemetry, "info", state.messages.append)

    def source_displays(_feature):
        state.calls.append(("source-dimensions", state.configuration))
        return displays[state.configuration]

    monkeypatch.setattr(drawing, "_feature_display_dimensions", source_displays)
    capture_native = native_geometry.capture_native_sketch_geometry

    def capture(sketch, *, label):
        state.calls.append(("capture", state.configuration))
        return capture_native(sketch, label=label)

    monkeypatch.setattr(drawing, "capture_native_sketch_geometry", capture)
    return SimpleNamespace(
        adapter=adapter,
        model=model,
        views=views,
        counts=counts,
        state=state,
        installed=installed,
        geometry=geometry,
        displays=displays,
    )


@pytest.mark.parametrize(
    "original", ["Original", "Installed", drawing.SUPPLIER_STOCK_CONFIGURATION]
)
def test_supplier_source_bodiless_reads_actual_bodies_and_restores_original(
    monkeypatch, original
):
    seat = _supplier_body_census_seat(monkeypatch, original=original)
    drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == original
    assert [call for call in seat.state.calls if call[0] == "bodies"] == [
        ("bodies", configuration, kind)
        for configuration in (seat.installed, drawing.SUPPLIER_STOCK_CONFIGURATION)
        for kind in (0, 1)
    ]
    assert seat.state.calls[-1] == ("rebuild", original)
    assert any(
        "solid_bodies=1 sheet_bodies=0" in message for message in seat.state.messages
    )
    assert any(
        f"source restored: original={original!r} configuration={original!r}" in message
        for message in seat.state.messages
    )


@pytest.mark.parametrize(
    "configuration,counts",
    [
        ("Installed", (0, 0)),
        ("Installed", (2, 0)),
        ("Installed", (1, 1)),
        (drawing.SUPPLIER_STOCK_CONFIGURATION, (1, 0)),
        (drawing.SUPPLIER_STOCK_CONFIGURATION, (0, 1)),
    ],
)
def test_supplier_source_bodiless_rejects_actual_body_inventory_and_restores(
    monkeypatch, configuration, counts
):
    seat = _supplier_body_census_seat(monkeypatch)
    seat.counts[configuration] = counts
    with pytest.raises(RuntimeError, match="solid/sheet="):
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"
    assert seat.state.calls[-1] == ("rebuild", "Original")


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("identity", "same source"),
        ("no-installed", "positive control"),
        ("activate", "cannot activate"),
        ("readback", "readback differs"),
        ("rebuild", "cannot rebuild"),
        ("rebuild-config", "rebuild changed configuration"),
    ],
)
def test_supplier_source_bodiless_refuses_unproven_configuration(
    monkeypatch, fault, reason
):
    seat = _supplier_body_census_seat(monkeypatch)
    show, rebuild = seat.model.ShowConfiguration2, seat.model.EditRebuild3
    if fault == "identity":
        seat.views[0].ReferencedDocument = object()
    elif fault == "no-installed":
        seat.views[2].ReferencedConfiguration = drawing.SUPPLIER_STOCK_CONFIGURATION
    elif fault == "activate":
        seat.model.ShowConfiguration2 = lambda name: (
            False if name == seat.installed else show(name)
        )
    elif fault == "readback":
        seat.model.ShowConfiguration2 = lambda name: (
            True if name == seat.installed else show(name)
        )
    elif fault == "rebuild":
        seat.model.EditRebuild3 = lambda: (
            False if seat.state.configuration == seat.installed else rebuild()
        )
    else:

        def change_configuration():
            if seat.state.configuration == seat.installed:
                seat.state.configuration = "Wrong"
            return rebuild()

        seat.model.EditRebuild3 = change_configuration
    with pytest.raises(RuntimeError, match=reason):
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"


@pytest.mark.parametrize("exception_type", [RuntimeError, KeyboardInterrupt])
@pytest.mark.parametrize("restore_fails", [False, True])
def test_supplier_source_bodiless_preserves_body_read_exception(
    monkeypatch, restore_fails, exception_type
):
    seat = _supplier_body_census_seat(monkeypatch)
    refusal = exception_type("native body read failed")
    bodies, show = seat.model.GetBodies2, seat.model.ShowConfiguration2

    def fail_supplier(kind, visible_only):
        if seat.state.configuration == drawing.SUPPLIER_STOCK_CONFIGURATION:
            raise refusal
        return bodies(kind, visible_only)

    seat.model.GetBodies2 = fail_supplier
    if restore_fails:
        seat.model.ShowConfiguration2 = lambda name: (
            False if name == "Original" else show(name)
        )
    with pytest.raises(exception_type) as caught:
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert caught.value is refusal
    if restore_fails:
        assert any("restoration also failed" in note for note in refusal.__notes__)
    else:
        assert seat.state.configuration == "Original"


def test_supplier_source_bodiless_refuses_failed_restore_after_successful_census(
    monkeypatch,
):
    seat = _supplier_body_census_seat(monkeypatch)
    show = seat.model.ShowConfiguration2
    seat.model.ShowConfiguration2 = lambda name: (
        False if name == "Original" else show(name)
    )
    with pytest.raises(RuntimeError, match="cannot activate 'Original'"):
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)


def test_supplier_source_bodiless_tolerates_diagnostic_view_count_failure(monkeypatch):
    seat = _supplier_body_census_seat(monkeypatch)

    def unavailable():
        raise RuntimeError("view selection count unavailable")

    seat.views[2].GetBodiesCount = unavailable
    drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"
    assert any(
        "view selection count unavailable" in message for message in seat.state.messages
    )


def test_supplier_body_census_precedes_finalize_not_settled_checks():
    import ast
    import inspect
    import textwrap

    tree = ast.parse(
        textwrap.dedent(inspect.getsource(drawing._build_read_only_source))
    )
    calls = {
        name: [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
        ]
        for name in (
            "_supplier_stock_sheet",
            "_assert_supplier_source_bodiless",
            "finalize_drawing",
        )
    }
    assert all(len(nodes) == 1 for nodes in calls.values())
    assert (
        calls["_supplier_stock_sheet"][0].lineno
        < calls["_assert_supplier_source_bodiless"][0].lineno
        < calls["finalize_drawing"][0].lineno
    )
    for check in (
        drawing._check_supplier_stock,
        drawing._verify_supplier_stock,
        drawing._assert_supplier_profile_frame,
        drawing._assert_supplier_profile_ink,
    ):
        check_tree = ast.parse(textwrap.dedent(inspect.getsource(check)))
        assert not any(
            isinstance(node, ast.Call)
            and (
                isinstance(node.func, ast.Name)
                and node.func.id
                in (
                    "_assert_supplier_source_bodiless",
                    "active_configuration_name",
                    "_supplier_profile_model_points",
                    "capture_native_sketch_geometry",
                )
                or isinstance(node.func, ast.Attribute)
                and node.func.attr
                in (
                    "ShowConfiguration2",
                    "EditRebuild3",
                    "GetBodies2",
                    "GetStartPoint2",
                    "GetEndPoint2",
                )
            )
            for node in ast.walk(check_tree)
        )
        if check is not drawing._assert_supplier_profile_ink:
            assert not any(
                isinstance(node, ast.Attribute)
                and node.attr in ("X", "Y", "Z", "ModelToSketchTransform")
                for node in ast.walk(check_tree)
            )


def test_supplier_source_bodiless_refuses_existing_dirtiness_before_configuration_switch(
    monkeypatch,
):
    seat = _supplier_body_census_seat(monkeypatch, dirty=True)
    with pytest.raises(RuntimeError, match="already dirty before clean capture"):
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"
    assert seat.state.dirty is True
    assert not any(
        call[0] in ("show", "bodies", "capture") for call in seat.state.calls
    )
    assert any("dirty=True" in message for message in seat.state.messages)


def test_supplier_source_bodiless_refuses_configuration_churn_dirtiness(monkeypatch):
    seat = _supplier_body_census_seat(monkeypatch)
    show = seat.model.ShowConfiguration2

    def dirty_switch(configuration):
        seat.state.dirty = True
        return show(configuration)

    seat.model.ShowConfiguration2 = dirty_switch
    with pytest.raises(
        RuntimeError, match="already dirty before clean capture"
    ) as caught:
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"
    assert seat.state.dirty is True
    assert any(
        "dirty_before=False dirty_after=True" in message
        for message in seat.state.messages
    )
    assert any("dirtied the source" in note for note in caught.value.__notes__)
    assert not any(call[0] == "capture" for call in seat.state.calls)


def test_supplier_source_bodiless_keeps_primary_error_when_restoration_dirties_source(
    monkeypatch,
):
    seat = _supplier_body_census_seat(monkeypatch)
    seat.counts[drawing.SUPPLIER_STOCK_CONFIGURATION] = (1, 0)
    show = seat.model.ShowConfiguration2

    def dirty_restore(configuration):
        if configuration == "Original":
            seat.state.dirty = True
        return show(configuration)

    seat.model.ShowConfiguration2 = dirty_restore
    with pytest.raises(RuntimeError, match="solid/sheet=") as caught:
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"
    assert any("dirtied the source" in note for note in caught.value.__notes__)


def test_supplier_source_bodiless_refuses_and_logs_unreadable_readonly_state(
    monkeypatch,
):
    seat = _supplier_body_census_seat(monkeypatch)

    def unavailable():
        raise RuntimeError("read-only state unavailable")

    seat.model.IsOpenedReadOnly = unavailable
    with pytest.raises(RuntimeError, match="read-only state unavailable"):
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"
    assert not any(call[0] in ("show", "capture") for call in seat.state.calls)
    assert any(
        "read-only state unavailable" in message for message in seat.state.messages
    )


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("endpoint", "invalid native line inventory/endpoints"),
        ("duplicate", "invalid native line inventory/endpoints"),
        ("nonline", "invalid native line inventory/endpoints"),
        ("nonconstruction", "invalid native line inventory/endpoints"),
        ("count", "invalid native line inventory/endpoints"),
        ("nonfinite-endpoint", "invalid native line inventory/endpoints"),
        ("short-frame", "malformed sketch transform"),
        ("nonfinite-frame", "malformed sketch transform"),
        ("correspondence", "drawing correspondence"),
    ],
)
def test_supplier_target_capture_rejects_canonical_defects_and_restores(
    monkeypatch, fault, reason
):
    seat = _supplier_body_census_seat(monkeypatch)
    sketch = seat.geometry[drawing.SUPPLIER_STOCK_CONFIGURATION]
    if fault == "endpoint":
        sketch.lines[0].GetStartPoint2().X += 0.0001
    elif fault == "duplicate":
        sketch.lines[-1] = sketch.lines[0]
    elif fault == "nonline":
        sketch.lines[0].GetType = lambda: 1
    elif fault == "nonconstruction":
        sketch.lines[0].ConstructionGeometry = False
    elif fault == "count":
        sketch.lines.pop()
    elif fault == "nonfinite-endpoint":
        sketch.lines[0].GetEndPoint2().Z = math.nan
    elif fault == "short-frame":
        sketch.ModelToSketchTransform.ArrayData.pop()
    elif fault == "nonfinite-frame":
        sketch.ModelToSketchTransform.ArrayData[0] = math.inf
    else:
        seat.views[0].GetCorresponding = lambda _segment: None
    with pytest.raises(RuntimeError, match=reason):
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"
    assert seat.state.calls[-1] == ("rebuild", "Original")
    diagnostics = [
        message
        for message in seat.state.messages
        if "MSC configured source geometry configuration=" in message
        and "native_line_inventory=" in message
    ]
    assert len(diagnostics) == 1
    assert f"configuration={drawing.SUPPLIER_STOCK_CONFIGURATION!r}" in diagnostics[0]
    assert "ModelToSketchTransform=" in diagnostics[0]


def test_supplier_target_capture_accepts_reversed_one_ulp_native_lines(monkeypatch):
    seat = _supplier_body_census_seat(monkeypatch)
    sketch = seat.geometry[drawing.SUPPLIER_STOCK_CONFIGURATION]
    sketch.lines.reverse()
    for line in sketch.lines:
        start, end = line.GetStartPoint2(), line.GetEndPoint2()
        start.X = math.nextafter(start.X, math.inf)
        end.X = math.nextafter(end.X, -math.inf)
        line.GetStartPoint2 = lambda end=end: end
        line.GetEndPoint2 = lambda start=start: start
    capture = drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert len(capture.geometry.line_offsets) == 18
    assert seat.state.configuration == "Original"


def test_supplier_capture_accepts_different_original_geometry_without_reading_it(
    monkeypatch,
):
    from dataclasses import FrozenInstanceError

    seat = _supplier_body_census_seat(monkeypatch)
    original = seat.geometry["Original"]
    original.lines.clear()
    original.ModelToSketchTransform.ArrayData[:] = [math.nan]
    original.GetSketchSegments = lambda: pytest.fail("original geometry was read")
    original.GetSketchTextSegments = lambda: pytest.fail("original ink was read")
    original.ModelToSketchTransform.Inverse = lambda: pytest.fail(
        "original frame was read"
    )
    capture = drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"
    assert [call for call in seat.state.calls if call[0] == "capture"] == [
        ("capture", drawing.SUPPLIER_STOCK_CONFIGURATION),
    ]
    assert all(
        call[1] == drawing.SUPPLIER_STOCK_CONFIGURATION
        for call in seat.state.calls
        if call[0] in ("feature", "source-dimensions")
    )
    target = seat.geometry[drawing.SUPPLIER_STOCK_CONFIGURATION]
    target_point = target.lines[0].GetStartPoint2()
    first_point = (target_point.X, target_point.Y, target_point.Z)
    assert capture.geometry.model_points[0] == pytest.approx(
        (
            0.031 - first_point[1],
            first_point[0] - 0.043,
            first_point[2] + 0.057,
        )
    )
    expected_axes = (
        (0.031, -0.043, 0.057),
        (0.031, -0.042, 0.057),
        (0.030, -0.043, 0.057),
    )
    for probes in (capture.full_frame, capture.head_frame):
        for actual, expected in zip(probes[:3], expected_axes, strict=True):
            assert actual == pytest.approx(expected, rel=0.0, abs=1e-12)
    assert capture.full_frame[3] == pytest.approx((0.031, -0.043 + 0.0477901, 0.057))
    assert capture.head_frame[3] == pytest.approx((0.031, -0.043 - 0.0030099, 0.057))
    snapshot = capture.geometry.model_points
    target_point.X += 0.5
    target.lines.clear()
    assert capture.geometry.model_points == snapshot
    with pytest.raises(FrozenInstanceError):
        capture.source_path = "changed"
    with pytest.raises(FrozenInstanceError):
        capture.geometry.model_points = ()


def test_supplier_source_geometry_restores_after_target_native_read_exception(
    monkeypatch,
):
    seat = _supplier_body_census_seat(monkeypatch)
    refusal = RuntimeError("native target endpoints unavailable")

    def unavailable():
        raise refusal

    seat.geometry[drawing.SUPPLIER_STOCK_CONFIGURATION].lines[
        0
    ].GetStartPoint2 = unavailable
    with pytest.raises(RuntimeError) as caught:
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert caught.value is refusal
    assert seat.state.configuration == "Original"
    assert seat.state.calls[-1] == ("rebuild", "Original")
    assert any("source restored:" in message for message in seat.state.messages)


@pytest.mark.parametrize(
    "status",
    [
        (4, False),
        (False, False),
        (None, False),
        ("0", False),
        None,
        0,
        (),
        (0,),
        (0, False, False),
    ],
)
def test_supplier_feature_status_refuses_before_target_native_inventory(
    monkeypatch, status
):
    seat = _supplier_body_census_seat(monkeypatch)
    feature = seat.model.FeatureByName(drawing.SUPPLIER_STOCK_FEATURE)
    feature.GetErrorCode2 = lambda: status
    feature.GetSpecificFeature2 = lambda: pytest.fail(
        "invalid feature reached native inventory"
    )
    seat.model.FeatureByName = lambda _name: feature
    with pytest.raises(RuntimeError, match="feature error/unreadable status"):
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"
    assert any(
        f"source_sketch_feature_error={status!r}" in message
        for message in seat.state.messages
    )


@pytest.mark.parametrize("status", [(0, None), (0, True), [0, False]])
def test_supplier_feature_status_ignores_undefined_success_warning(monkeypatch, status):
    seat = _supplier_body_census_seat(monkeypatch)
    feature_by_name = seat.model.FeatureByName

    def feature(name):
        result = feature_by_name(name)
        result.GetErrorCode2 = lambda: status
        return result

    seat.model.FeatureByName = feature
    drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"


def test_supplier_feature_status_rejects_missing_target_native_feature(monkeypatch):
    seat = _supplier_body_census_seat(monkeypatch)
    seat.model.FeatureByName = lambda _name: None
    with pytest.raises(RuntimeError, match="missing supplier sketch"):
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"


def test_supplier_feature_status_native_exception_preserves_identity_and_restores(
    monkeypatch,
):
    seat = _supplier_body_census_seat(monkeypatch)
    refusal = RuntimeError("native feature status unavailable")
    feature_by_name = seat.model.FeatureByName

    def unavailable():
        raise refusal

    def feature(name):
        result = feature_by_name(name)
        if seat.state.configuration == drawing.SUPPLIER_STOCK_CONFIGURATION:
            result.GetErrorCode2 = unavailable
            result.GetSpecificFeature2 = lambda: pytest.fail(
                "failed status reached native inventory"
            )
        return result

    seat.model.FeatureByName = feature
    with pytest.raises(RuntimeError) as caught:
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert caught.value is refusal
    assert seat.state.configuration == "Original"
    assert seat.state.calls[-1] == ("rebuild", "Original")


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("blocks", "sketch blocks"),
        ("text", "sketch text"),
        ("user_points", "sketch user points"),
    ],
)
def test_supplier_target_capture_rejects_nonsegment_ink(monkeypatch, kind, reason):
    seat = _supplier_body_census_seat(monkeypatch)
    sketch = seat.geometry[drawing.SUPPLIER_STOCK_CONFIGURATION]
    if kind == "blocks":
        sketch.GetSketchBlockInstanceCount = lambda: 1
    elif kind == "text":
        sketch.GetSketchTextSegments = lambda: (object(),)
    else:
        sketch.GetUserPointsCount = lambda: 1
    with pytest.raises(RuntimeError, match=reason):
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"
    assert seat.state.calls[-1] == ("rebuild", "Original")


@pytest.mark.parametrize("cropped", [False, True])
def test_supplier_final_projection_uses_captured_target_after_actual_restore(
    monkeypatch, cropped
):
    census = _supplier_body_census_seat(monkeypatch)
    census.geometry["Original"].lines.clear()
    census.geometry["Original"].ModelToSketchTransform.ArrayData[:] = [math.nan]
    capture = drawing._assert_supplier_source_bodiless(census.adapter, *census.views)
    assert census.state.configuration == "Original"
    saved_calls = tuple(census.state.calls)

    def unavailable(*_args, **_kwargs):
        pytest.fail("settled proof accessed live source/configuration state")

    census.model.ShowConfiguration2 = unavailable
    census.model.EditRebuild3 = unavailable
    census.model.FeatureByName = unavailable
    for sketch in census.geometry.values():
        sketch.GetSketchSegments = unavailable
        sketch.ModelToSketchTransform.Inverse = unavailable
    ink = _supplier_ink_seat(monkeypatch, cropped)
    ink.view.ReferencedDocument.FeatureByName = unavailable
    ink.source.GetSketchSegments = unavailable
    ink.source.ModelToSketchTransform.Inverse = unavailable
    for line in ink.lines:
        line.GetStartPoint2 = unavailable
        line.GetEndPoint2 = unavailable
    center = drawing.STOCK_HEAD_CENTER if cropped else drawing.STOCK_CENTER
    scale = drawing.STOCK_HEAD_SCALE if cropped else drawing.STOCK_SCALE
    drawing._assert_supplier_profile_frame(
        ink.adapter,
        ink.view,
        center,
        scale,
        points=capture.head_frame if cropped else capture.full_frame,
        label="restored immutable target frame",
    )
    drawing._assert_supplier_profile_ink(
        ink.adapter,
        ink.view,
        ink.cell,
        capture.geometry,
        cropped=cropped,
    )
    assert tuple(census.state.calls) == saved_calls
    assert len(ink.projected) == (4 if cropped else 40)


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("endpoint", "source-diagram vertices"),
        ("duplicate", "source-diagram vertices"),
        ("nonfinite", "source-diagram vertices"),
        ("identity", "dimension identity changed"),
        ("missing", "dimension coverage changed"),
        ("repeated", "dimension coverage changed"),
        ("attachment-count", "two diagram vertices"),
        ("attachment-kind", "two diagram vertices"),
        ("native-type", "ownership/type"),
        ("driven-state", "ownership/type"),
        ("tolerance-type", "limit type"),
        ("tolerance-band", "limit band"),
        ("tolerance-precision", "limit precision"),
    ],
)
def test_supplier_capture_checks_actual_target_source_dimensions(
    monkeypatch, fault, reason
):
    seat = _supplier_body_census_seat(monkeypatch)
    displays = seat.displays[drawing.SUPPLIER_STOCK_CONFIGURATION]
    display = displays[0]
    annotation = display.GetAnnotation()
    native = display.GetDimension2(0)
    points = annotation.GetAttachedEntities3()
    if fault == "endpoint":
        points[0].X += 0.001
    elif fault == "duplicate":
        annotation.GetAttachedEntities3 = lambda: (points[0], points[0])
    elif fault == "nonfinite":
        points[0].Z = math.nan
    elif fault == "identity":
        seat.model.Parameter = lambda _name: object()
    elif fault == "missing":
        displays.pop()
    elif fault == "repeated":
        displays.append(display)
    elif fault == "attachment-count":
        annotation.GetAttachedEntities3 = lambda: points[:1]
    elif fault == "attachment-kind":
        annotation.GetAttachedEntityTypes = lambda: (2, 2)
    elif fault == "native-type":
        display.Type2 = -1
    elif fault == "driven-state":
        native.DrivenState = 0
    elif fault == "tolerance-type":
        native.Tolerance.Type = -1
    elif fault == "tolerance-band":
        native.Tolerance.GetMaxValue = lambda: 0.5
    else:
        display.GetPrimaryTolPrecision2 = lambda: -1
    with pytest.raises(RuntimeError, match=reason):
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"
    assert seat.state.calls[-1] == ("rebuild", "Original")
    assert (
        "source-dimensions",
        drawing.SUPPLIER_STOCK_CONFIGURATION,
    ) in seat.state.calls


@pytest.mark.parametrize(
    "restore_failure", ["activate", "readback", "rebuild", "rebuild-config", "dirty"]
)
def test_supplier_capture_primary_survives_every_restore_failure(
    monkeypatch, restore_failure
):
    seat = _supplier_body_census_seat(monkeypatch)
    refusal = KeyboardInterrupt("native target source points interrupted")
    display = seat.displays[drawing.SUPPLIER_STOCK_CONFIGURATION][0]

    def interrupted():
        raise refusal

    display.GetAnnotation = interrupted
    show, rebuild = seat.model.ShowConfiguration2, seat.model.EditRebuild3

    def restoring(configuration):
        if configuration == "Original":
            if restore_failure == "activate":
                return False
            if restore_failure == "readback":
                return True
            if restore_failure == "dirty":
                seat.state.dirty = True
        return show(configuration)

    def rebuilding():
        if seat.state.configuration == "Original":
            if restore_failure == "rebuild":
                return False
            if restore_failure == "rebuild-config":
                seat.state.configuration = "Wrong"
        return rebuild()

    seat.model.ShowConfiguration2 = restoring
    seat.model.EditRebuild3 = rebuilding
    with pytest.raises(KeyboardInterrupt) as caught:
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert caught.value is refusal
    assert any("restoration also failed" in note for note in refusal.__notes__)


def test_supplier_final_diagnostics_read_only_pose_not_live_source(monkeypatch):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    messages = []
    monkeypatch.setattr(drawing._telemetry, "info", messages.append)
    # Deliberately no ReferencedDocument/GetSketch/geometry API on this view.
    view = SimpleNamespace(
        Name="settled source",
        ReferencedConfiguration=drawing.SUPPLIER_STOCK_CONFIGURATION,
        UseSheetScale=0,
        ScaleRatio=drawing.STOCK_SCALE,
        Angle=0.0,
        Position=drawing.STOCK_CENTER,
        GetOutline=lambda: drawing.STOCK_VIEW_CELL,
        IsCropped=lambda: False,
        ModelToViewTransform=SimpleNamespace(ArrayData=tuple(range(16))),
    )
    drawing._log_supplier_view_state(object(), view, stage="settled")
    assert len(messages) == 2
    assert all("read_error" not in message for message in messages)
    assert "pose=" in messages[0] and "model_to_view=" in messages[1]


def test_supplier_capture_binds_raw_source_display_dimensions(monkeypatch):
    seat = _supplier_body_census_seat(monkeypatch)
    displays = seat.displays[drawing.SUPPLIER_STOCK_CONFIGURATION]

    class RawSourceDisplay:
        def __init__(self, display):
            self.display = display

        def __getattr__(self, member):
            pytest.fail(f"raw source display used before native binding: {member}")

    raw_displays = [RawSourceDisplay(display) for display in displays]
    bound = []

    def bind(raw, interface):
        assert interface == "IDisplayDimension"
        bound.append(raw)
        return raw.display

    monkeypatch.setattr(
        drawing, "_feature_display_dimensions", lambda _feature: raw_displays
    )
    monkeypatch.setattr(drawing, "_bind", bind)
    drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert bound == raw_displays
    assert seat.state.configuration == "Original"


def _readonly_msc_build(monkeypatch, tmp_path):
    """In-memory native boundaries; only the persisted-byte witness uses a file."""
    import hashlib

    source_path = tmp_path / "msc-source.SLDPRT"
    source_path.write_bytes(b"original MSC source bytes")
    monkeypatch.setattr(drawing, "SOURCE", source_path)
    state = SimpleNamespace(
        dirty=False,
        read_only=True,
        path=str(source_path),
        configuration="Installed",
        sheet=None,
        captured=False,
        events=[],
        messages=[],
        prepared_hook=None,
        presentation_hook=None,
        finalize_hook=None,
        drawing_closed=False,
    )
    source = SimpleNamespace(
        GetPathName=lambda: state.path,
        GetSaveFlag=lambda: state.dirty,
        IsOpenedReadOnly=lambda: state.read_only,
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Installed"),
        ),
    )

    def activate_sheet(name):
        state.sheet = name
        state.events.append(("sheet", name))
        return True

    document = SimpleNamespace(ActivateSheet=activate_sheet)
    adapter = SimpleNamespace(
        currentModel=None,
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )

    class NativeView(SimpleNamespace):
        def __getattribute__(self, name):
            if (
                name in ("Name", "GetReferencedModelName", "ReferencedDocument")
                and state.drawing_closed
            ):
                raise RuntimeError("native drawing view disconnected after CloseDoc")
            return super().__getattribute__(name)

    def view(name):
        return NativeView(
            Name=name,
            ReferencedDocument=source,
            ReferencedConfiguration=drawing.SUPPLIER_STOCK_CONFIGURATION,
            GetReferencedModelName=lambda: str(source_path),
            UpdateViewDisplayGeometry=lambda: None,
        )

    full, head = (view(name) for name in ("full", "head"))
    placed = []

    def opened(actual_adapter, path, *, label):
        assert actual_adapter is adapter and path == source_path
        state.events.append(("open-read-only", label))
        adapter.currentModel = source
        return source

    def sha256(path):
        assert path == source_path
        value = hashlib.sha256(path.read_bytes()).hexdigest()
        state.events.append(("hash", value))
        return value

    def new_drawing(actual_adapter, **_kwargs):
        assert actual_adapter.currentModel is source
        state.events.append(("drawing",))
        actual_adapter.currentModel = document
        return document, object()

    def place(_adapter, path, orientation, *_args, **_kwargs):
        assert path == str(source_path)
        assert state.sheet == drawing.SHEET_NAMES[0]
        assert not state.captured and not state.dirty
        native = view("front" if not placed else "iso")
        native.ReferencedConfiguration = "Installed"
        placed.append(native)
        state.events.append(("create-view", orientation))
        return native

    def prepare(_adapter):
        assert state.sheet == drawing.SHEET_NAMES[1]
        assert not state.captured and not state.dirty
        state.events.append(("prepare-supplier",))
        if state.prepared_hook is not None:
            state.prepared_hook()
        return full, head

    def capture(_adapter, actual_full, actual_head, front):
        assert actual_full is full and actual_head is head and front is placed[0]
        assert (
            state.sheet == drawing.SHEET_NAMES[1]
            and not state.dirty
            and state.read_only
        )
        assert not state.captured
        state.events.append(("capture",))
        state.captured = True
        return _supplier_capture_value()

    def import_front(_adapter, front, **_kwargs):
        assert front is placed[0]
        assert state.sheet == drawing.SHEET_NAMES[0] and state.captured
        state.events.append(("front-import",))
        return []

    def front_presentation(*_args):
        assert state.captured and state.read_only
        state.dirty = True  # Actual imported SetText is known to do this.
        state.events.append(("front-presentation",))

    def supplier_presentation(_adapter, actual_full, actual_head):
        assert (actual_full, actual_head) == (full, head)
        assert (
            state.sheet == drawing.SHEET_NAMES[1] and state.captured and state.read_only
        )
        state.events.append(("supplier-presentation",))
        state.dirty = True
        if state.presentation_hook is not None:
            state.presentation_hook()
        return []

    async def finalize(_adapter, _outputs, **kwargs):
        state.events.append(("finalize",))
        assert state.read_only
        for callback in kwargs["settled_checks"]:
            callback()
        try:
            if state.finalize_hook is not None:
                state.finalize_hook()
            return {"drawing": "complete"}
        finally:
            state.drawing_closed = True
            state.events.append(("drawing-closed",))

    def forensics(_adapter, _label, _message, **kwargs):
        assert kwargs["sheet_png"] is True
        state.events.append(("forensics", kwargs["exception"]))
        raise kwargs["exception"]

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, native: native.Name)
    monkeypatch.setattr(
        drawing, "active_configuration_name", lambda *_args: state.configuration
    )
    monkeypatch.setattr(drawing._telemetry, "info", state.messages.append)
    monkeypatch.setattr(drawing, "_open_supplier_source_read_only", opened)
    monkeypatch.setattr(drawing, "_source_file_sha256", sha256)
    monkeypatch.setattr(
        drawing, "read_required_properties", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(drawing, "new_project_drawing", new_drawing)
    monkeypatch.setattr(
        drawing, "create_blank_drawing_sheets", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *_args: None)
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing, "_supplier_stock_sheet", prepare)
    monkeypatch.setattr(drawing, "_assert_supplier_source_bodiless", capture)
    monkeypatch.setattr(drawing.hidden_sketches, "curate_view_dimensions", import_front)
    monkeypatch.setattr(drawing, "assert_imported_precision", lambda *_args: None)
    monkeypatch.setattr(drawing, "_reference_cut_length", lambda *_args: None)
    monkeypatch.setattr(drawing, "set_dimension_callouts", front_presentation)
    for name in (
        "activate_front_for_notes",
        "add_property_linked_note",
    ):
        monkeypatch.setattr(drawing, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "_present_supplier_stock_sheet", supplier_presentation)
    monkeypatch.setattr(
        drawing,
        "_verify_finished_controls",
        lambda *_args: state.events.append(("finished-check",)),
    )
    monkeypatch.setattr(
        drawing,
        "_verify_supplier_stock",
        lambda *_args: state.events.append(("supplier-check",)),
    )
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", forensics)
    return SimpleNamespace(
        adapter=adapter,
        source=source,
        state=state,
        path=source_path,
        placed=placed,
        full=full,
        head=head,
    )


def test_msc_readonly_build_captures_clean_before_any_presentation(
    monkeypatch, tmp_path
):
    import asyncio

    seat = _readonly_msc_build(monkeypatch, tmp_path)
    result = asyncio.run(drawing.build(seat.adapter))
    assert result == {"drawing": "complete"}
    kinds = [event[0] for event in seat.state.events]
    assert kinds[0] == "hash" and kinds[1] == "open-read-only"
    assert kinds.count("capture") == 1
    assert (
        kinds.index("prepare-supplier")
        < kinds.index("capture")
        < kinds.index("front-import")
        < kinds.index("front-presentation")
        < kinds.index("supplier-presentation")
        < kinds.index("finalize")
        < kinds.index("finished-check")
        < kinds.index("supplier-check")
    )
    assert seat.state.dirty is True and seat.state.read_only is True
    assert seat.path.read_bytes() == b"original MSC source bytes"
    hashes = [event[1] for event in seat.state.events if event[0] == "hash"]
    assert len(hashes) == 4 and len(set(hashes)) == 1
    assert any("'dirty': True" in message for message in seat.state.messages)
    assert any("drawing lifecycle exit" in message for message in seat.state.messages)


@pytest.mark.parametrize("stage", ["initial", "preparation"])
def test_msc_readonly_build_refuses_dirty_source_before_capture(
    monkeypatch, tmp_path, stage
):
    import asyncio

    seat = _readonly_msc_build(monkeypatch, tmp_path)
    if stage == "initial":
        seat.state.dirty = True
    else:
        seat.state.prepared_hook = lambda: setattr(seat.state, "dirty", True)
    with pytest.raises(RuntimeError, match="already dirty before clean capture"):
        asyncio.run(drawing.build(seat.adapter))
    assert not seat.state.captured
    assert not any(
        event[0] in ("front-presentation", "finalize") for event in seat.state.events
    )
    assert seat.state.dirty is True


@pytest.mark.parametrize(
    "fault", ["read-only", "model-path", "view-path", "view-identity", "bytes"]
)
def test_msc_readonly_build_refuses_source_loss_before_finalize(
    monkeypatch, tmp_path, fault
):
    import asyncio

    seat = _readonly_msc_build(monkeypatch, tmp_path)

    def changed():
        if fault == "read-only":
            seat.state.read_only = False
        elif fault == "model-path":
            seat.state.path = str(tmp_path / "different.SLDPRT")
        elif fault == "view-path":
            seat.full.GetReferencedModelName = lambda: str(
                tmp_path / "different.SLDPRT"
            )
        elif fault == "view-identity":
            seat.full.ReferencedDocument = object()
        else:
            seat.path.write_bytes(b"source changed before finalization")

    seat.state.presentation_hook = changed
    reason = (
        "not read-only"
        if fault == "read-only"
        else "SHA-256 changed"
        if fault == "bytes"
        else "identity/path changed"
    )
    with pytest.raises(RuntimeError, match=reason):
        asyncio.run(drawing.build(seat.adapter))
    assert not any(event[0] == "finalize" for event in seat.state.events)
    assert any(event[0] == "forensics" for event in seat.state.events)


@pytest.mark.parametrize("fault", ["bytes", "read-only", "source-path"])
def test_msc_readonly_build_finally_refuses_successful_save_that_changes_source(
    monkeypatch, tmp_path, fault
):
    import asyncio

    seat = _readonly_msc_build(monkeypatch, tmp_path)

    def changed():
        seat.state.dirty = False
        if fault == "bytes":
            seat.path.write_bytes(b"source bytes changed by drawing SaveAs3")
        elif fault == "read-only":
            seat.state.read_only = False
        else:
            seat.state.path = str(tmp_path / "changed-source.SLDPRT")

    seat.state.finalize_hook = changed
    reason = (
        "SHA-256 changed"
        if fault == "bytes"
        else "not read-only"
        if fault == "read-only"
        else "identity/path changed"
    )
    with pytest.raises(RuntimeError, match=reason):
        asyncio.run(drawing.build(seat.adapter))
    assert seat.state.dirty is False
    assert any(event[0] == "finalize" for event in seat.state.events)


@pytest.mark.parametrize("exception_type", [RuntimeError, KeyboardInterrupt])
@pytest.mark.parametrize("mutation", ["none", "bytes", "bytes-and-readonly"])
def test_msc_readonly_build_preserves_finalizer_primary_with_integrity_note(
    monkeypatch,
    tmp_path,
    exception_type,
    mutation,
):
    import asyncio

    seat = _readonly_msc_build(monkeypatch, tmp_path)
    primary = exception_type("native drawing finalization failed")

    def fail():
        seat.state.dirty = False
        if mutation != "none":
            seat.path.write_bytes(b"source changed despite failed finalization")
        if mutation == "bytes-and-readonly":
            seat.state.read_only = False
        raise primary

    seat.state.finalize_hook = fail
    with pytest.raises(exception_type) as caught:
        asyncio.run(drawing.build(seat.adapter))
    assert caught.value is primary
    if mutation == "none":
        assert not getattr(primary, "__notes__", ())
    else:
        assert any(
            "source integrity check also failed" in note and "SHA-256 changed" in note
            for note in primary.__notes__
        )
        if mutation == "bytes-and-readonly":
            assert any("not read-only" in note for note in primary.__notes__)


@pytest.mark.parametrize("fault", ["readonly", "path"])
def test_msc_target_capture_rechecks_native_source_protection_after_switch(
    monkeypatch, fault
):
    seat = _supplier_body_census_seat(monkeypatch)
    if fault == "readonly":
        seat.model.IsOpenedReadOnly = lambda: (
            seat.state.configuration != drawing.SUPPLIER_STOCK_CONFIGURATION
        )
    else:
        seat.model.GetPathName = lambda: (
            "wrong-source.SLDPRT"
            if seat.state.configuration == drawing.SUPPLIER_STOCK_CONFIGURATION
            else str(drawing.SOURCE)
        )
    reason = "not read-only" if fault == "readonly" else "identity/path changed"
    with pytest.raises(RuntimeError, match=reason):
        drawing._assert_supplier_source_bodiless(seat.adapter, *seat.views)
    assert seat.state.configuration == "Original"
    assert not any(call[0] == "capture" for call in seat.state.calls)


def test_msc_readonly_build_never_queries_views_after_finalizer_closes_drawing(
    monkeypatch, tmp_path
):
    import asyncio

    seat = _readonly_msc_build(monkeypatch, tmp_path)
    assert asyncio.run(drawing.build(seat.adapter)) == {"drawing": "complete"}
    assert seat.state.drawing_closed is True
    with pytest.raises(RuntimeError, match="disconnected after CloseDoc"):
        seat.full.GetReferencedModelName()
    assert seat.state.events[-1][0] == "hash"
    assert any("drawing lifecycle exit" in message for message in seat.state.messages)
