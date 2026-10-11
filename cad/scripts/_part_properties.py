"""Part identity, title-block properties and tolerance stamping.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
from _com import _early_bound, _read_member
from _source_identity import _git_commit_year, _git_sha


def part_properties(part_name: str) -> dict[str, str]:
    """SolidWorks custom properties for ``part_name`` from the parts registry.

    ``Revision`` is the next compact release number from ``release.yaml``;
    per-part registry revisions are retained only as historical source data and
    never override the release identity stamped into shipped CAD.  ``Title`` is
    always the part's slug: it is what the title block's PART cell prints, one
    convention on every sheet (user ruling 2026-09-26), so a registry
    ``title:`` never reaches it (``test_buildgraph.test_part_cell_prints_the_slug``).
    """
    import _config

    props: dict[str, str] = {
        "Title": part_name,
        "Revision": _config.release_revision(),
        "Generator": f"harmonic-analyzer @ {_git_sha()}",
        # The title block's "(c) <year> <holder>" line reads this via
        # $PRPSHEET:{COPYRIGHT_YEAR}; SolidWorks has no built-in year-only
        # property and its date built-ins change on every rebuild.
        "COPYRIGHT_YEAR": _git_commit_year(),
    }
    # Title-block general tolerances (title_block.yaml) — read by the drawing
    # template's title block via $PRPSHEET, so EVERY part carries them,
    # registered in the parts registry or not.
    props["TOL_LIN_X"] = str(_config.title_block("linear_1pl")["display"])
    props["TOL_LIN_XX"] = str(_config.title_block("linear_2pl")["display"])
    props["TOL_LIN_XXX"] = str(_config.title_block("linear_3pl")["display"])
    props["TOL_ANG"] = str(_config.title_block("angular")["display"])
    props["TOL_SURFACE"] = str(_config.title_block("surface")["display"])
    # Edge-break and thread-class rows (2026-09 template): the sheet-format
    # notes are $PRPSHEET links, so the numbers live here, not in the DRWDOT.
    props["TOL_EDGE_BREAK_R"] = str(_config.title_block("edge_break")["display_r"])
    props["TOL_CHAMFER_MAX"] = str(_config.title_block("edge_break")["display_chamfer"])
    props["THREAD_TYPE"] = str(_config.title_block("thread")["type"])
    props["THREAD_CLASS"] = str(_config.title_block("thread")["class"])
    # DRILLED HOLES general tolerance (unilateral); the title block's DRILLED
    # HOLES row reads these via $PRPSHEET and supplies the +/- around them.
    props["TOL_HOLE_MINUS"] = str(_config.title_block("drilled_hole")["display_minus"])
    props["TOL_HOLE_PLUS"] = str(_config.title_block("drilled_hole")["display_plus"])
    # Per-channel stretched springs (build_ch_channel_assembly) are length variants of
    # the registered base part -- they inherit its material / tolerance / fit so
    # the tolerance audit stays clean without 10 redundant registry rows.
    registry_name = part_name
    if part_name.startswith("vn-channel-spring-installed-stretch"):
        registry_name = "vn-channel-spring-installed"
    try:
        reg = _config.parts(registry_name)
    except KeyError:
        return props
    field_map = {
        "Number": "number",
        "Material": "material",
        "Tolerance Class": "tolerance_class",
        "Fit Class": "fit_class",
        "Process": "process",
        "Confidence": "confidence",
    }
    for prop, key in field_map.items():
        if key in reg and reg[key] is not None:
            props[prop] = str(reg[key])
    return props


# DimXpert block-tolerance document properties (Tools > Options > Document
# Properties > DimXpert), ids extracted from swconst.tlb R2026x. Values from
# title_block.yaml — the same numbers the TOL_* custom properties display in
# the drawing title block.
_PREF_DIMXPERT_METHOD = 637  # swPartDimXpertToleranceMethod -> 0 = BlockTolerance


_PREF_TOL1_DECIMALS = 405  # swPartDimXpertLengthUnitTol1Decimals (get-only, see below)


_PREF_TOL2_DECIMALS = 406  # swPartDimXpertLengthUnitTol2Decimals (get-only, see below)


_PREF_TOL1_VALUE = 123  # swPartDimXpertLengthUnitTol1Value (meters)


_PREF_TOL2_VALUE = 124  # swPartDimXpertLengthUnitTol2Value (meters)


_PREF_ANGULAR_VALUE = (
    126  # swPartDimXpertAngularUnitTolValue (radians; get-only, see below)
)


_PREF_OPT_NONE = 0  # swDetailingNoOptionSpecified


_METERS_PER_INCH = 0.0254


@_telemetry.traced("part.block_tolerances")
def apply_block_tolerances(adapter: Any) -> None:
    """Stamp the title-block general tolerances as DimXpert block-tolerance doc
    properties on the active part, so the SLDPRT's MBD metadata matches what the
    drawing title block states.

    Probe-verified on this seat (3DEXPERIENCE R2026x, 2026-07-13): the method and
    the linear Tolerance 1/2 VALUES set fine, but the decimals prefs (405/406) and
    the angular value (126) reject every write (``SetUserPreference*`` returns
    False under both int encodings, options 0-3, before/after rebuild, on a saved
    doc) despite the API help documenting them settable — get-only in practice.
    The get-only prefs therefore ride the seat's default part TEMPLATE, which
    makes the template a build prerequisite: it must carry the wanted decimals
    split (Tol1=2dp, Tol2=3dp — the stock default) and the title-block angular
    value (set by hand in the .prtdot). This stamps what it can and RAISES on any
    failure — a rejected settable write OR get-only drift. Drift must fail, not
    warn: the template is not a cache-key input, so a drifted seat would publish
    parts whose DimXpert metadata disagrees with title_block.yaml into the shared
    remote cache under the same key as a correct seat.
    """
    import _config

    model = adapter.currentModel
    ext = _read_member(model, "Extension")
    lin2 = float(_config.title_block("linear_2pl")["value_in"]) * _METERS_PER_INCH
    lin3 = float(_config.title_block("linear_3pl")["value_in"]) * _METERS_PER_INCH
    ang = math.radians(float(_config.title_block("angular")["value_deg"]))
    sets = [
        (
            "DimXpert method=block",
            ext.SetUserPreferenceInteger,
            _PREF_DIMXPERT_METHOD,
            0,
        ),
        (
            "DimXpert tol1 (.xx) value",
            ext.SetUserPreferenceDouble,
            _PREF_TOL1_VALUE,
            lin2,
        ),
        (
            "DimXpert tol2 (.xxx) value",
            ext.SetUserPreferenceDouble,
            _PREF_TOL2_VALUE,
            lin3,
        ),
    ]
    for label, setter, pref, value in sets:
        if not adapter._attempt(
            lambda: setter(pref, _PREF_OPT_NONE, value), default=False
        ):
            raise RuntimeError(f"{label} write rejected (pref {pref})")
    _telemetry.success("DimXpert block tolerances stamped")
    drift = []
    if ext.GetUserPreferenceInteger(_PREF_TOL1_DECIMALS, _PREF_OPT_NONE) != 2:
        drift.append("tol1 decimals != 2")
    if ext.GetUserPreferenceInteger(_PREF_TOL2_DECIMALS, _PREF_OPT_NONE) != 3:
        drift.append("tol2 decimals != 3")
    got_ang = ext.GetUserPreferenceDouble(_PREF_ANGULAR_VALUE, _PREF_OPT_NONE)
    if abs(got_ang - ang) > 1e-9:
        drift.append(f"angular {math.degrees(got_ang):g}° != {math.degrees(ang):g}°")
    if drift:
        raise RuntimeError(
            "DimXpert block-tolerance drift on get-only prefs -- the seat's default "
            "part template must carry these (open the default .prtdot, set Document "
            "Properties > DimXpert accordingly, save), else this seat would publish "
            f"metadata-drifted parts into the shared cache: {'; '.join(drift)}"
        )


# Document summary metadata (File > Properties > Summary — also what Windows
# Explorer shows). swSummInfoTitle=0, swSummInfoAuthor=2 (swSummInfoField_e).
_SUMMARY_TITLE = 0


_SUMMARY_AUTHOR = 2


PROJECT_AUTHOR = "Pedro Paulo Vezza Campos"


@_telemetry.traced("part.summary_info")
def apply_summary_info(adapter: Any, *, title: str, model: Any = None) -> None:
    """Write and read-verify the document summary Title + Author.

    Same early-bound split as the drawing summary stamper: SummaryInfo is a
    property, so early binding exposes the getter as ``SummaryInfo(field)`` and
    the setter as ``SetSummaryInfo(field, value)``.  ``model`` defaults to the
    active document, like ``apply_custom_properties``.
    """
    model = _early_bound(adapter.currentModel if model is None else model, "IModelDoc2")
    for summary_field, value in (
        (_SUMMARY_TITLE, title),
        (_SUMMARY_AUTHOR, PROJECT_AUTHOR),
    ):
        model.SetSummaryInfo(summary_field, value)
        if model.SummaryInfo(summary_field) != value:
            raise RuntimeError(
                f"summary field {summary_field} did not persist ({value!r})"
            )
    _telemetry.success(
        f"summary info stamped (Title={title!r}, Author={PROJECT_AUTHOR!r})"
    )
