"""Professional Mode visual-asset contracts.

The package is intentionally additive and inert until an explicit Professional
Mode binding is created. Standard Mode does not import or consult it.
"""

from .binding import bind_professional_mode, select_reference_views
from .authority import (
    AssetChannelClaim,
    ReferenceAdmissionDecision,
    ReferenceAdmissionResolver,
    ReferenceAdmissionResult,
    ReferenceChannelEvidence,
    ReferenceChannelPlan,
    ReferenceEvidencePacket,
    VisualAssetBindingSet,
)
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
from .lifecycle import (
    AnchorPackPreparationHost,
    PeopleAssetActivationRequest,
    PeopleAssetCreateRequest,
    PeopleAssetLifecycleService,
    PeopleAssetPrepareRequest,
)
from .execution import (
    ProfessionalModeExecutionContext,
    ProfessionalModeExecutionRequest,
    ProfessionalModeExecutionAdapter,
    ProfessionalModePreparationResult,
)
from .consumers import (
    ProfessionalConsumerContext,
    ProfessionalConsumerRequest,
    ProfessionalModeConsumerAdapter,
)
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
    "AssetChannelClaim",
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
    "ReferenceAdmissionDecision",
    "ReferenceAdmissionResolver",
    "ReferenceAdmissionResult",
    "ReferenceChannelEvidence",
    "ReferenceChannelPlan",
    "ReferenceEvidencePacket",
    "VisualAssetBindingSet",
    "ProfessionalModeRuntimeBridge",
    "PeopleAssetActivationRequest",
    "PeopleAssetCreateRequest",
    "PeopleAssetLifecycleService",
    "PeopleAssetPrepareRequest",
    "AnchorPackPreparationHost",
    "ProfessionalModeExecutionAdapter",
    "ProfessionalModeExecutionContext",
    "ProfessionalModeExecutionRequest",
    "ProfessionalModePreparationResult",
    "ProfessionalConsumerContext",
    "ProfessionalConsumerRequest",
    "ProfessionalModeConsumerAdapter",
    "bind_professional_mode",
    "select_reference_views",
]
