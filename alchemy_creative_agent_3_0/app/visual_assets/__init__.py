"""Professional Mode visual-asset contracts.

The package is intentionally additive and inert until an explicit Professional
Mode binding is created. Standard Mode does not import or consult it.
"""

from .binding import bind_professional_mode, select_reference_views
from .anchor_pack import (
    AnchorCandidateAttempt,
    AnchorCandidateResult,
    AnchorGenerationRequest,
    AnchorPackPreparationRequest,
    AnchorPackPreparationResult,
    AnchorPackPreparationService,
    AnchorReviewDecision,
)
from .catalog import InMemoryVisualAssetCatalog, PersistentVisualAssetCatalog, PeopleAssetRevision
from .runtime_bridge import CanonicalProviderPromptReceipt, ProfessionalModeRuntimeBridge
from .contracts import (
    AnchorView,
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    PeopleAsset,
    ProfessionalModeBinding,
    RootSourceProvenance,
)

__all__ = [
    "AnchorView",
    "AnchorCandidateAttempt",
    "AnchorCandidateResult",
    "AnchorGenerationRequest",
    "AnchorPackPreparationRequest",
    "AnchorPackPreparationResult",
    "AnchorPackPreparationService",
    "AnchorReviewDecision",
    "FaceIdentityModule",
    "IdentityAnchorPackVersion",
    "IdentityScoreSummary",
    "PeopleAsset",
    "ProfessionalModeBinding",
    "RootSourceProvenance",
    "InMemoryVisualAssetCatalog",
    "PersistentVisualAssetCatalog",
    "PeopleAssetRevision",
    "CanonicalProviderPromptReceipt",
    "ProfessionalModeRuntimeBridge",
    "bind_professional_mode",
    "select_reference_views",
]
