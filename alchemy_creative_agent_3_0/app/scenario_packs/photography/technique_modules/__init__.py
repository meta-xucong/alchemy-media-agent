"""Photography technique module descriptors and General P3 contributors."""

from .general import GENERAL_TECHNIQUE_CAPABILITIES, GeneralPhotographyTechniqueDirector
from .registry import PhotographyTechniqueModuleRegistry

__all__ = [
    "GENERAL_TECHNIQUE_CAPABILITIES",
    "GeneralPhotographyTechniqueDirector",
    "PhotographyTechniqueModuleRegistry",
]
