"""Geometric-control (GD&T) spec vocabulary — pure data, importable from BOTH tiers.

A ``<part>_spec.py`` describes its geometric controls as rows of
:class:`GeometricControl` / :class:`PartDatum`; the PART build authors them as
DimXpert model PMI (``_part_pmi.author_part_pmi``) and the DRAWING imports the
resulting annotations onto the sheet (``_drawing_common.import_part_pmi``)
instead of typing frozen ``tolerance="..."`` strings per sheet.  Like
``_fit_limits`` / ``_surface_finish`` this module carries NO COM and imports
nothing from either tier, so ``check:partiso`` stays clean.

``gtol_frame_xml`` moved here from ``_drawing_common`` (which now re-exports
it): the SAME current-format frame XML fills a sheet-authored ``IGtol`` and a
DimXpert-created one (probed 2026-07-28, ``probe_dimxpert_gtol.py`` Q4), and
the part tier may not import a drawing module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Union
from xml.etree import ElementTree

# SOLIDWORKS 2022+ frame-XML symbol names per geometric characteristic.
GTOL_SYMBOLS = {
    "circular_runout": "GTOL-SRUN",
    "cylindricity": "GTOL-CYL",
    "flatness": "GTOL-FLAT",
    "parallelism": "GTOL-PARA",
    "position": "GTOL-POSI",
    "profile_surface": "GTOL-SPROF",
    "perpendicularity": "GTOL-PERP",
    "straightness": "GTOL-STRAIGHT",
    "total_runout": "GTOL-TRUN",
}

# characteristic -> swDimXpertGtolType_e MEMBER NAME. The integer values are
# read off the installed swdimxpert.tlb at author time (`_part_pmi`), never
# hard-coded here — the offline API bundle does not ship this enum.
DIMXPERT_GTOL_MEMBERS = {
    "circular_runout": "CircularRunout",
    "cylindricity": "Cylindricity",
    "flatness": "Flatness",
    "parallelism": "Parallelism",
    "position": "Position",
    "profile_surface": "SurfaceProfile",
    "perpendicularity": "Perpendicularity",
    "straightness": "Straightness",
    "total_runout": "TotalRunout",
}


def gtol_frame_xml(
    characteristic: str,
    tolerance: str,
    *,
    datums: Sequence[str] = (),
    diameter: bool = False,
) -> str:
    """Build the SOLIDWORKS-2022+ feature-control-frame XML payload."""
    symbol = GTOL_SYMBOLS.get(characteristic)
    if symbol is None:
        raise ValueError(f"unsupported geometric characteristic: {characteristic!r}")
    if not tolerance:
        raise ValueError("feature-control-frame tolerance cannot be blank")
    if len(datums) > 3 or any(not d or len(d) > 2 for d in datums):
        raise ValueError(f"invalid datum reference sequence: {tuple(datums)!r}")
    root = ElementTree.Element("GtolFrame")
    ElementTree.SubElement(root, "ToleranceSymbol").text = symbol
    range_info = ElementTree.SubElement(root, "ToleranceRangeInfo")
    ElementTree.SubElement(range_info, "PrimaryToleranceValue").text = tolerance
    if diameter:
        ElementTree.SubElement(range_info, "PrimaryRangeSymbol").text = "phi"
    for datum in datums:
        compartment = ElementTree.SubElement(root, "DatumCompartment")
        detail = ElementTree.SubElement(compartment, "DatumDetail")
        ElementTree.SubElement(detail, "DatumLetter").text = datum
    return ElementTree.tostring(root, encoding="unicode", short_empty_elements=True)


@dataclass(frozen=True)
class CylinderFace:
    """The unique cylindrical face of ``diameter_mm`` (optionally disambiguated
    by a point its axis span must contain, in part coordinates, mm)."""

    diameter_mm: float
    contains_y_mm: float | None = None
    tolerance_mm: float = 0.05


@dataclass(frozen=True)
class PlanarFace:
    """The unique planar face whose outward normal ≈ ``normal`` and whose plane
    sits at ``offset_mm`` along that normal (part coordinates, mm)."""

    normal: tuple[float, float, float]
    offset_mm: float
    tolerance_mm: float = 0.05


FaceSpec = Union[CylinderFace, PlanarFace]


@dataclass(frozen=True)
class PartDatum:
    """A DimXpert datum authored on the model.

    ``letter`` is ASSERTED, not chosen: DimXpert auto-assigns identifiers in
    insertion order, so author datums in alphabetical order and the helper
    fails loud if the read-back identifier differs.
    """

    letter: str
    face: FaceSpec
    leader_length_m: float = 0.06


@dataclass(frozen=True)
class GeometricControl:
    """One feature-control frame authored on the model as DimXpert PMI."""

    key: str
    characteristic: str
    tolerance: str
    face: FaceSpec
    datums: tuple[str, ...] = ()
    diameter: bool = False

    def __post_init__(self) -> None:
        if self.characteristic not in GTOL_SYMBOLS:
            raise ValueError(
                f"{self.key}: unsupported characteristic {self.characteristic!r}"
            )
        if self.characteristic not in DIMXPERT_GTOL_MEMBERS:
            raise ValueError(
                f"{self.key}: no DimXpert gtol type for {self.characteristic!r}"
            )

    @property
    def frame_xml(self) -> str:
        return gtol_frame_xml(
            self.characteristic,
            self.tolerance,
            datums=self.datums,
            diameter=self.diameter,
        )
