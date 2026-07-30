"""Geometric-control (GD&T) spec vocabulary — pure data, importable from BOTH tiers.

A ``<part>_spec.py`` describes its geometric controls as rows of
:class:`GeometricControl` / :class:`PartDatum`; the PART build authors them as
plain model annotations (``_part_pmi.author_part_pmi``) and the DRAWING
projects the same typed rows onto native sheet annotations
(``_drawing_common.project_part_pmi``) instead of typing frozen
``tolerance="..."`` strings per sheet.  Like ``_fit_limits`` /
``_surface_finish`` this module carries NO COM and imports nothing from
either tier, so ``check:partiso`` stays clean.

``gtol_frame_xml`` moved here from ``_drawing_common`` (which now re-exports
it): the same current-format frame XML fills a sheet-authored ``IGtol`` and a
model-authored one, and the part tier may not import a drawing module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence, Union
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

ToleranceZone = Literal["linear", "diametral"]
_PMI_NAME_PREFIX = "HARMONIC_PMI_"


def datum_key(letter: str) -> str:
    """Return the stable spec key for a datum feature symbol."""
    return f"datum:{letter}"


def pmi_annotation_name(key: str) -> str:
    """Return the unique model-annotation name persisted for ``key``."""
    return f"{_PMI_NAME_PREFIX}{key.replace(':', '_')}"


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
class GtolFrameSignature:
    """The production semantics carried by one SOLIDWORKS frame XML."""

    characteristic_symbol: str
    tolerance: str
    datums: tuple[str, ...]
    tolerance_zone: ToleranceZone


def gtol_frame_signature(xml: str) -> GtolFrameSignature:
    """Parse the load-bearing subset of a SOLIDWORKS frame XML payload.

    SOLIDWORKS may add default elements when it serializes a frame, so raw XML
    string equality is too strict.  Conversely, substring matching is unsafe:
    it misses datum order and diametral-zone state.  This normalized signature
    compares every production field this repository authors.
    """
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ValueError(f"invalid feature-control-frame XML: {exc}") from exc

    def texts(local_name: str) -> list[str]:
        return [
            str(element.text or "")
            for element in root.iter()
            if element.tag.rsplit("}", 1)[-1] == local_name
        ]

    symbols = texts("ToleranceSymbol")
    tolerances = texts("PrimaryToleranceValue")
    if len(symbols) != 1 or not symbols[0]:
        raise ValueError(f"frame XML has {len(symbols)} tolerance symbols")
    if len(tolerances) != 1 or not tolerances[0]:
        raise ValueError(f"frame XML has {len(tolerances)} primary tolerances")

    range_symbols = [value for value in texts("PrimaryRangeSymbol") if value]
    if any(value != "phi" for value in range_symbols) or len(range_symbols) > 1:
        raise ValueError(f"unsupported primary range symbols: {range_symbols!r}")
    tolerance_zone: ToleranceZone = "diametral" if range_symbols else "linear"
    return GtolFrameSignature(
        characteristic_symbol=symbols[0],
        tolerance=tolerances[0],
        datums=tuple(texts("DatumLetter")),
        tolerance_zone=tolerance_zone,
    )


@dataclass(frozen=True)
class CylinderFace:
    """The unique cylindrical face of ``diameter_mm`` (optionally disambiguated
    by a point its axis span must contain, in part coordinates, mm)."""

    diameter_mm: float
    contains_x_mm: float | None = None
    contains_y_mm: float | None = None
    tolerance_mm: float = 0.05

    def __post_init__(self) -> None:
        if self.diameter_mm <= 0.0:
            raise ValueError("cylinder diameter must be positive")
        if self.tolerance_mm <= 0.0:
            raise ValueError("cylinder match tolerance must be positive")


@dataclass(frozen=True)
class ConeFace:
    """The unique conical face with the specified half-angle.

    ``contains_x_mm`` optionally requires the face bounding box to cross a
    part-coordinate X station. This distinguishes coaxial conical patches
    without depending on volatile face enumeration order.
    """

    half_angle_degrees: float
    contains_x_mm: float | None = None
    tolerance_degrees: float = 0.01
    tolerance_mm: float = 0.05

    def __post_init__(self) -> None:
        if not 0.0 < self.half_angle_degrees < 90.0:
            raise ValueError("cone half-angle must be between 0 and 90 degrees")
        if self.tolerance_degrees <= 0.0:
            raise ValueError("cone angle tolerance must be positive")
        if self.tolerance_mm <= 0.0:
            raise ValueError("cone match tolerance must be positive")


@dataclass(frozen=True)
class PlanarFace:
    """The unique planar face whose outward normal ≈ ``normal`` and whose plane
    sits at ``offset_mm`` along that normal (part coordinates, mm)."""

    normal: tuple[float, float, float]
    offset_mm: float
    tolerance_mm: float = 0.05

    def __post_init__(self) -> None:
        if len(self.normal) != 3 or not any(float(value) for value in self.normal):
            raise ValueError("plane normal must be a non-zero 3-vector")
        if self.tolerance_mm <= 0.0:
            raise ValueError("plane match tolerance must be positive")


@dataclass(frozen=True)
class SphereFace:
    """The unique spherical face of ``diameter_mm`` and optional centre."""

    diameter_mm: float
    center_mm: tuple[float, float, float] | None = None
    tolerance_mm: float = 0.05

    def __post_init__(self) -> None:
        if self.diameter_mm <= 0.0:
            raise ValueError("sphere diameter must be positive")
        if self.center_mm is not None and len(self.center_mm) != 3:
            raise ValueError("sphere center must be a 3-vector")
        if self.tolerance_mm <= 0.0:
            raise ValueError("sphere match tolerance must be positive")


@dataclass(frozen=True)
class TorusFace:
    """The unique toroidal face with the specified generating radii."""

    major_radius_mm: float
    minor_radius_mm: float
    center_mm: tuple[float, float, float] | None = None
    tolerance_mm: float = 0.05

    def __post_init__(self) -> None:
        # SolidWorks permits negative major radii for lemon tori, so only the
        # physically positive minor radius is constrained here.
        if self.minor_radius_mm <= 0.0:
            raise ValueError("torus minor radius must be positive")
        if self.center_mm is not None and len(self.center_mm) != 3:
            raise ValueError("torus center must be a 3-vector")
        if self.tolerance_mm <= 0.0:
            raise ValueError("torus match tolerance must be positive")


FaceSpec = Union[CylinderFace, ConeFace, PlanarFace, SphereFace, TorusFace]


@dataclass(frozen=True)
class PartDatum:
    """A datum feature symbol authored on the model (``InsertDatumTag2``)."""

    letter: str
    face: FaceSpec

    def __post_init__(self) -> None:
        if not self.letter or len(self.letter) > 2:
            raise ValueError(f"invalid datum letter: {self.letter!r}")

    @property
    def key(self) -> str:
        return datum_key(self.letter)

    @property
    def annotation_name(self) -> str:
        return pmi_annotation_name(self.key)


@dataclass(frozen=True)
class GeometricControl:
    """One feature-control frame authored on the model (``InsertGtol``)."""

    key: str
    characteristic: str
    tolerance: str
    face: FaceSpec
    datums: tuple[str, ...] = ()
    tolerance_zone: ToleranceZone = "linear"

    def __post_init__(self) -> None:
        if self.characteristic not in GTOL_SYMBOLS:
            raise ValueError(
                f"{self.key}: unsupported characteristic {self.characteristic!r}"
            )
        if not self.key:
            raise ValueError("geometric-control key cannot be blank")
        if self.tolerance_zone not in ("linear", "diametral"):
            raise ValueError(
                f"{self.key}: unsupported tolerance zone {self.tolerance_zone!r}"
            )
        # Validate the complete frame contract at spec construction time.  This
        # catches blank tolerances, overlong datum sequences, and invalid datum
        # letters before a build reaches SolidWorks.
        self.frame_xml

    @property
    def annotation_name(self) -> str:
        return pmi_annotation_name(self.key)

    @property
    def frame_xml(self) -> str:
        return gtol_frame_xml(
            self.characteristic,
            self.tolerance,
            datums=self.datums,
            diameter=self.tolerance_zone == "diametral",
        )


def validate_part_pmi(
    datums: Sequence[PartDatum], controls: Sequence[GeometricControl]
) -> None:
    """Validate cross-row identity and datum-reference contracts."""
    datum_letters = [datum.letter for datum in datums]
    if len(set(datum_letters)) != len(datum_letters):
        raise ValueError(f"duplicate datum letters: {datum_letters!r}")

    control_keys = [control.key for control in controls]
    if len(set(control_keys)) != len(control_keys):
        raise ValueError(f"duplicate geometric-control keys: {control_keys!r}")

    row_keys = [datum.key for datum in datums] + control_keys
    if len(set(row_keys)) != len(row_keys):
        raise ValueError(f"datum/control key collision: {row_keys!r}")
    annotation_names = [pmi_annotation_name(key) for key in row_keys]
    if len(set(annotation_names)) != len(annotation_names):
        raise ValueError(f"annotation-name collision: {annotation_names!r}")

    known_datums = set(datum_letters)
    for control in controls:
        missing = set(control.datums) - known_datums
        if missing:
            raise ValueError(
                f"{control.key}: unknown datum references {sorted(missing)!r}"
            )
