"""Feature-control-frame XML and signatures, shared by parts and drawings.

Keeping this payload contract separate avoids importing face selectors for frames.

``gtol_frame_xml`` originated in ``_drawing_common``: the same current-format
frame XML fills a sheet-authored ``IGtol`` and a model-authored one, and the
part tier may not import a drawing module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Sequence
from xml.etree import ElementTree

from _gtol_symbols import GTOL_SYMBOLS, ToleranceZone

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


def gtol_frame_xml(
    characteristic: str,
    tolerance: str,
    *,
    datums: Sequence[str] = (),
    diameter: bool = False,
    projected_zone_height_mm: float | None = None,
    translated: Sequence[str] = (),
) -> str:
    """Build the SOLIDWORKS-2022+ feature-control-frame XML payload, using the
    repository's mm annotation convention.

    Projected-zone nodes and their ordering come from the installed
    ``swGtolFrameXmlSchema-public-2.xsd`` (``FeatureInfoType``), not from
    legacy ``IGtol.SetPTZHeight2`` or text appended to the tolerance.

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
    if projected_zone_height_mm is not None and (
        isinstance(projected_zone_height_mm, bool)
        or not isinstance(projected_zone_height_mm, (int, float))
        or not isfinite(projected_zone_height_mm)
        or projected_zone_height_mm <= 0.0
    ):
        raise ValueError("projected zone height must be finite and positive in mm")
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
    if projected_zone_height_mm is not None:
        feature_info = ElementTree.SubElement(root, "FeatureInfo")
        ElementTree.SubElement(feature_info, "ProjectedToleranceZone").text = "true"
        # The native XSD uses xs:decimal, whose lexical form excludes exponents.
        ElementTree.SubElement(feature_info, "Projection").text = format(
            Decimal(str(projected_zone_height_mm)), "f"
        )
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
    projected_zone_height_mm: float | None = None
    translated: tuple[str, ...] = ()


def gtol_frame_signature(xml: str) -> GtolFrameSignature:
    """Parse the load-bearing subset of a SOLIDWORKS frame XML payload.

    SOLIDWORKS may add default elements when it serializes a frame, so raw XML
    string equality is too strict.  Conversely, substring matching is unsafe:
    it misses datum order and diametral-zone state.  This normalized signature
    compares every production field this repository authors.
    """
    root = _frame_root(xml)
    if root.tag.rsplit("}", 1)[-1] != "GtolFrame":
        raise ValueError("feature-control-frame XML root must be GtolFrame")

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
    try:
        tolerance_value = Decimal(tolerances[0])
    except InvalidOperation as exc:
        raise ValueError("frame XML primary tolerance is not numeric") from exc
    if not tolerance_value.is_finite():
        raise ValueError("frame XML primary tolerance is not finite")
    # Conversion/readback may serialize ".010" instead of "0.010".
    tolerance = format(tolerance_value, "f")
    if "." in tolerance:
        tolerance = tolerance.rstrip("0").rstrip(".")

    range_symbols = [value for value in texts("PrimaryRangeSymbol") if value]
    if any(value != "phi" for value in range_symbols) or len(range_symbols) > 1:
        raise ValueError(f"unsupported primary range symbols: {range_symbols!r}")
    tolerance_zone: ToleranceZone = "diametral" if range_symbols else "linear"

    def children(parent: ElementTree.Element, name: str) -> list[ElementTree.Element]:
        return [child for child in parent if child.tag.rsplit("}", 1)[-1] == name]

    feature_infos = children(root, "FeatureInfo")
    if len(feature_infos) > 1:
        raise ValueError("frame XML has multiple FeatureInfo elements")
    projected_zone_height_mm = None
    projected_flags: list[ElementTree.Element] = []
    if feature_infos:
        feature_info = feature_infos[0]
        projected_flags = children(feature_info, "ProjectedToleranceZone")
        projections = children(feature_info, "Projection")
        ranges = children(feature_info, "ProjectionRange")
        if any(len(values) > 1 for values in (projected_flags, projections, ranges)):
            raise ValueError("frame XML has duplicate projected zone fields")
        flag = (projected_flags[0].text or "").strip() if projected_flags else "false"
        if flag not in ("true", "false", "1", "0"):
            raise ValueError(f"invalid projected zone flag: {flag!r}")

        def decimal_value(element: ElementTree.Element) -> Decimal:
            value = (element.text or "").strip()
            if re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value) is None:
                raise ValueError(f"invalid projected zone decimal: {value!r}")
            try:
                return Decimal(value)
            except InvalidOperation as exc:
                raise ValueError(f"invalid projected zone decimal: {value!r}") from exc

        if ranges and decimal_value(ranges[0]) != 0:
            raise ValueError("unsupported projected zone range")
        projection = decimal_value(projections[0]) if projections else Decimal(0)
        if flag in ("true", "1"):
            projected_zone_height_mm = float(projection)
            if not isfinite(projected_zone_height_mm) or projected_zone_height_mm <= 0:
                raise ValueError("projected zone height must be finite and positive in mm")
        elif projection != 0:
            raise ValueError("projected zone height is present without its enabled symbol")
    if len(texts("ProjectedToleranceZone")) != len(projected_flags):
        raise ValueError("projected zone symbol must be a child of FeatureInfo")
    datums, translated = _datum_references(root)
    return GtolFrameSignature(
        characteristic_symbol=symbols[0],
        tolerance=tolerance,
        datums=datums,
        tolerance_zone=tolerance_zone,
        projected_zone_height_mm=projected_zone_height_mm,
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
