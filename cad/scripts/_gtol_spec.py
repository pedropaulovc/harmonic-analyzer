"""Geometric-control (GD&T) spec vocabulary — pure data, importable from BOTH tiers.

A ``<part>_spec.py`` describes its geometric controls as rows of
:class:`GeometricControl` / :class:`PartDatum`; the PART build authors them as
plain model annotations (``_part_pmi.author_part_pmi``) and the DRAWING
projects the same typed rows onto native sheet annotations
(``_drawing_common.project_part_pmi``) instead of typing frozen
``tolerance="..."`` strings per sheet.  Like ``_fit_deviations`` /
``_surface_finish`` this module carries NO COM and imports nothing from
either tier, so ``check:partiso`` stays clean.

``gtol_frame_xml`` moved here from ``_drawing_common`` (which now re-exports
it): the same current-format frame XML fills a sheet-authored ``IGtol`` and a
model-authored one, and the part tier may not import a drawing module.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, Sequence, Union
from xml.etree import ElementTree

# SOLIDWORKS 2022+ frame-XML symbol names per geometric characteristic.
GTOL_SYMBOLS = {
    "angularity": "GTOL-ANGULAR",
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
# The translation modifier is its symbol code after the letter in the
# DatumLetter text (the schema's "string value for datum letter displayed in
# the edit box"), spelt as SOLIDWORKS prints it: farm run 20261009T204136744Z
# printed "<GTOL-POSI> | 0.05 | C | B | <MOD-TRANS2>", the triangle in B's
# compartment and no vector.  The compartment's ``<Translation>`` flag (Gtol
# Frame XML Schema, the Datum dialog's triangle) is not used: with i, j, k
# absent, empty, "false" or after the letter it printed the dialog's
# translation vector, "[0,0,0]" or "[false,false,false]", beside the triangle
# (farm runs 20261009T174542021Z, 20261009T182549169Z).
TRANSLATION_GLYPH = "<MOD-TRANS2>"
_TRANSLATION_MODIFIER = "MOD-TRANS"
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
    translated: Sequence[str] = (),
) -> str:
    """Build the SOLIDWORKS-2022+ feature-control-frame XML payload.

    ``translated`` names the datum references that carry the ASME Y14.5-2018
    translation modifier (the open triangle after the letter,
    ``TRANSLATION_GLYPH``).  A clocking
    datum feature of size at a basic distance from the primary takes it, so
    its simulator may slide along that distance and only orients.
    """
    symbol = GTOL_SYMBOLS.get(characteristic)
    if symbol is None:
        raise ValueError(f"unsupported geometric characteristic: {characteristic!r}")
    if not tolerance:
        raise ValueError("feature-control-frame tolerance cannot be blank")
    if len(datums) > 3 or any(not d or len(d) > 2 for d in datums):
        raise ValueError(f"invalid datum reference sequence: {tuple(datums)!r}")
    if not set(translated) <= set(datums) or (datums and datums[0] in translated):
        raise ValueError(
            f"translation modifier on {tuple(translated)!r} must name a "
            f"non-primary datum of {tuple(datums)!r}"
        )
    root = ElementTree.Element("GtolFrame")
    ElementTree.SubElement(root, "ToleranceSymbol").text = symbol
    range_info = ElementTree.SubElement(root, "ToleranceRangeInfo")
    ElementTree.SubElement(range_info, "PrimaryToleranceValue").text = tolerance
    if diameter:
        ElementTree.SubElement(range_info, "PrimaryRangeSymbol").text = "phi"
    for datum in datums:
        compartment = ElementTree.SubElement(root, "DatumCompartment")
        detail = ElementTree.SubElement(compartment, "DatumDetail")
        ElementTree.SubElement(detail, "DatumLetter").text = (
            f"{datum}{TRANSLATION_GLYPH}" if datum in translated else datum
        )
    return ElementTree.tostring(root, encoding="unicode", short_empty_elements=True)


@dataclass(frozen=True)
class GtolFrameSignature:
    """The production semantics carried by one SOLIDWORKS frame XML."""

    characteristic_symbol: str
    tolerance: str
    datums: tuple[str, ...]
    tolerance_zone: ToleranceZone
    translated: tuple[str, ...] = ()


def gtol_frame_signature(xml: str) -> GtolFrameSignature:
    """Parse the load-bearing subset of a SOLIDWORKS frame XML payload.

    SOLIDWORKS may add default elements when it serializes a frame, so raw XML
    string equality is too strict.  Conversely, substring matching is unsafe:
    it misses datum order and diametral-zone state.  This normalized signature
    compares every production field this repository authors.
    """
    root = _frame_root(xml)

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
    datums, translated = _datum_references(root)
    return GtolFrameSignature(
        characteristic_symbol=symbols[0],
        tolerance=tolerances[0],
        datums=datums,
        tolerance_zone=tolerance_zone,
        translated=translated,
    )


def gtol_frame_datums(xml: str) -> tuple[str, ...]:
    """The datum letters one frame XML references, in order.

    Unlike ``gtol_frame_signature`` this needs no characteristic: a composite
    frame's lower tier shares the upper tier's symbol cell, and SOLIDWORKS
    read its XML back with one empty ``<ToleranceSymbol>`` (knife mount, farm
    run 20261009T200747541Z) while it still names its datums.
    """
    return _datum_references(_frame_root(xml))[0]


def _frame_root(xml: str) -> ElementTree.Element:
    # SOLIDWORKS reads a letter's symbol code back unescaped:
    # IGtolFrame.GetSymbolXml returned "<DatumLetter>C<MOD-TRANS2></DatumLetter>"
    # for the authored "C&lt;MOD-TRANS2&gt;" (farm run 20261009T200747541Z:
    # "mismatched tag", fr-top-frame slot frames).  The schema has no
    # element named for a symbol code, so such a tag is the code as text.
    xml = re.sub(r"<((?:MOD|GTOL)-[A-Z0-9]+)>", r"&lt;\1&gt;", xml)
    try:
        return ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ValueError(f"invalid feature-control-frame XML: {exc}") from exc


def _datum_references(
    root: ElementTree.Element,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(datum letters, translated letters) of a parsed frame XML.

    A translated letter carries the modifier's symbol code ("C<MOD-TRANS2>");
    its datum is still C.
    """
    datums: list[str] = []
    translated: list[str] = []
    for letter in root.iter():
        if letter.tag.rsplit("}", 1)[-1] != "DatumLetter":
            continue
        text = str(letter.text or "")
        name = re.sub(rf"<{_TRANSLATION_MODIFIER}\d*>", "", text)
        datums.append(name)
        if name != text:
            translated.append(name)
    return tuple(datums), tuple(translated)


def translation_print_problem(texts: Sequence[str], translated: Sequence[str]) -> str:
    """Why a frame's printed text items misstate its translation modifiers,
    or "" when they print exactly as ASME Y14.5-2018 writes them.

    ``texts`` are the frame's display-data text items in print order
    (``IDisplayData.GetTextAtIndex``).  Each translated datum's letter must be
    followed directly by one modifier glyph (``<MOD-TRANS...>``), and nothing
    may print a bracketed vector: farm run 20261009T174542021Z printed
    "C", "B", "<MOD-TRANS2>", "[0,0,0]" for the frame C|B▷.
    """
    items = [str(text).strip() for text in texts]
    vectors = [text for text in items if "[" in text or "]" in text]
    if vectors:
        return f"prints a translation vector {vectors!r} in {items!r}"
    modifiers = [i for i, text in enumerate(items) if _TRANSLATION_MODIFIER in text]
    if len(modifiers) != len(translated):
        return (
            f"prints {len(modifiers)} translation modifier(s) for "
            f"{len(translated)} translated datum(s) in {items!r}"
        )
    for datum, index in zip(translated, modifiers):
        own = items[index].split("<", 1)[0].strip()
        before = items[index - 1] if index else ""
        if own != datum and not (own == "" and before == datum):
            return f"prints its translation modifier off datum {datum} in {items!r}"
    return ""


@dataclass(frozen=True)
class CylinderFace:
    """The unique cylindrical face of ``diameter_mm`` (optionally disambiguated
    by a point its axis span must contain, in part coordinates, mm).

    The three station coordinates are independent and AND together, which is
    what it takes to name ONE bore of a symmetric family: the harmonic base's
    four column sockets share their diameter, depth and height and differ only
    in X and Z, so a diameter (or a diameter and an X) matches two or four
    faces and resolves none of them.
    """

    diameter_mm: float
    contains_x_mm: float | None = None
    contains_y_mm: float | None = None
    contains_z_mm: float | None = None
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
    sits at ``offset_mm`` along that normal (part coordinates, mm).

    ``contains_x_mm`` and ``contains_z_mm`` AND together like the cylinder
    stations above: the top frame's four cap-recess floors are COPLANAR (one Y
    offset, one annulus area each), so naming one takes both plan stations.
    """

    normal: tuple[float, float, float]
    offset_mm: float
    contains_z_mm: float | None = None
    contains_x_mm: float | None = None
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
