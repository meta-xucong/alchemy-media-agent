"""Template manifest registry for V3 Project Mode."""

from .contracts import (
    BrandMemoryReadMode,
    ProjectTemplateManifest,
    TemplateActivationError,
    TemplateContextReadPolicy,
    TemplateContextWritePolicy,
    TemplateInputField,
    TemplateInputFieldType,
    TemplateOutputSummaryPolicy,
)
from .registry import (
    ProjectTemplateRegistry,
    TEMPLATE_LOCKED_MESSAGE,
    TEMPLATE_PLACEHOLDER_MESSAGE,
    TEMPLATE_UNAVAILABLE_MESSAGE,
    default_template_manifests,
)

__all__ = [
    "BrandMemoryReadMode",
    "ProjectTemplateManifest",
    "ProjectTemplateRegistry",
    "TEMPLATE_LOCKED_MESSAGE",
    "TEMPLATE_PLACEHOLDER_MESSAGE",
    "TEMPLATE_UNAVAILABLE_MESSAGE",
    "TemplateActivationError",
    "TemplateContextReadPolicy",
    "TemplateContextWritePolicy",
    "TemplateInputField",
    "TemplateInputFieldType",
    "TemplateOutputSummaryPolicy",
    "default_template_manifests",
]

