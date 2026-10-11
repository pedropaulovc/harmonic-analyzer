"""Part-owned datums, geometric controls and cross-row validation.

Separate from concrete selectors so shared PMI validation does not fold every type.

A ``<part>_spec.py`` describes its geometric controls as rows of
:class:`GeometricControl` / :class:`PartDatum`; the PART build authors them as
plain model annotations (``_part_pmi.author_part_pmi``) and the DRAWING
projects the same typed rows onto native sheet annotations
(``_drawing_common.project_part_pmi``) instead of typing frozen
``tolerance="..."`` strings per sheet.  Like the fit-deviation vocabulary /
``_surface_finish`` this module carries NO COM and imports nothing from
either tier, so ``check:partiso`` stays clean.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from _gtol_face import FaceSpec
from _gtol_frame import gtol_frame_xml
from _gtol_identity import datum_key, pmi_annotation_name
from _gtol_symbols import GTOL_SYMBOLS, ToleranceZone


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
