"""Grouped SolidWorks mixins for the PyWin32 adapter."""

from .assembly import SolidWorksAssemblyMixin
from .features import SolidWorksFeaturesMixin
from .io import SolidWorksIOMixin
from .manufacturing import SolidWorksManufacturingMixin
from .measure import SolidWorksMeasureMixin
from .motion import SolidWorksMotionMixin
from .parametrics import SolidWorksParametricsMixin
from .reference_geometry import SolidWorksReferenceGeometryMixin
from .selection import SolidWorksSelectionMixin
from .sketch import SolidWorksSketchMixin

__all__ = [
    "SolidWorksAssemblyMixin",
    "SolidWorksFeaturesMixin",
    "SolidWorksIOMixin",
    "SolidWorksManufacturingMixin",
    "SolidWorksMeasureMixin",
    "SolidWorksMotionMixin",
    "SolidWorksParametricsMixin",
    "SolidWorksReferenceGeometryMixin",
    "SolidWorksSelectionMixin",
    "SolidWorksSketchMixin",
]
