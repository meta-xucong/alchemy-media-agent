"""Module-local registry of inactive Photography technique modules."""

from __future__ import annotations

from ..contracts import PhotographyTechniqueModuleDescriptor


TECHNIQUE_SKELETONS = (
    ("photography_brief_direction", "Photography Brief Direction", ()),
    ("photographer_profile_binding", "Photographer Profile Binding", ("photography_brief_direction",)),
    ("photography_camera_optics", "Camera And Optics Direction", ("photography_brief_direction",)),
    ("photography_lighting_direction", "Lighting Direction", ("photography_brief_direction",)),
    ("photography_composition_direction", "Composition Direction", ("photography_brief_direction",)),
    ("photography_subject_direction", "Subject Direction", ("photography_brief_direction",)),
    ("photography_color_finish", "Color And Finish Direction", ("photography_brief_direction",)),
    ("photography_retouch_direction", "Retouch Direction", ("photography_color_finish",)),
    ("photography_shot_list_direction", "Shot List Direction", ("photography_brief_direction",)),
    ("photography_professional_review", "Professional Photography Review", ("photography_brief_direction",)),
)


class PhotographyTechniqueModuleRegistry:
    def __init__(self, descriptors: list[PhotographyTechniqueModuleDescriptor] | None = None) -> None:
        self._descriptors: dict[str, PhotographyTechniqueModuleDescriptor] = {}
        for descriptor in descriptors or []:
            self.register(descriptor)

    @classmethod
    def with_p1_skeletons(cls) -> "PhotographyTechniqueModuleRegistry":
        return cls(
            [
                PhotographyTechniqueModuleDescriptor(
                    capability_id=capability_id,
                    display_name=display_name,
                    status="inactive",
                    activation_ready=False,
                    dependencies=list(dependencies),
                    contribution_stages=[],
                    metadata={"phase": "P1", "contributes_runtime_behavior": False},
                )
                for capability_id, display_name, dependencies in TECHNIQUE_SKELETONS
            ]
        )

    def register(self, descriptor: PhotographyTechniqueModuleDescriptor) -> None:
        if descriptor.capability_id in self._descriptors:
            raise ValueError(f"photography technique module already registered: {descriptor.capability_id}")
        self._descriptors[descriptor.capability_id] = descriptor

    def get(self, capability_id: str) -> PhotographyTechniqueModuleDescriptor | None:
        return self._descriptors.get(capability_id)

    def list_descriptors(self) -> list[PhotographyTechniqueModuleDescriptor]:
        return [self._descriptors[key] for key in sorted(self._descriptors)]
