"""Module-local registry of inactive first-wave Photography scene directors."""

from __future__ import annotations

from ..contracts import PhotographySceneDirectorDescriptor


FIRST_WAVE_SCENES = (
    ("portrait", "portrait_photography_direction", "Portrait Photography"),
    ("landscape", "landscape_photography_direction", "Landscape Photography"),
    ("still_life", "still_life_photography_direction", "Still Life Photography"),
    ("animal", "animal_photography_direction", "Animal Photography"),
)


class PhotographySceneDirectorRegistry:
    def __init__(self, descriptors: list[PhotographySceneDirectorDescriptor] | None = None) -> None:
        self._descriptors: dict[str, PhotographySceneDirectorDescriptor] = {}
        for descriptor in descriptors or []:
            self.register(descriptor)

    @classmethod
    def with_first_wave_skeletons(cls) -> "PhotographySceneDirectorRegistry":
        return cls(
            [
                PhotographySceneDirectorDescriptor(
                    scene_id=scene_id,
                    capability_id=capability_id,
                    display_name=display_name,
                    status="inactive",
                    activation_ready=False,
                    metadata={"phase": "P1", "contributes_runtime_behavior": False},
                )
                for scene_id, capability_id, display_name in FIRST_WAVE_SCENES
            ]
        )

    def register(self, descriptor: PhotographySceneDirectorDescriptor) -> None:
        if descriptor.scene_id in self._descriptors:
            raise ValueError(f"photography scene director already registered: {descriptor.scene_id}")
        self._descriptors[descriptor.scene_id] = descriptor

    def get(self, scene_id: str) -> PhotographySceneDirectorDescriptor | None:
        return self._descriptors.get(scene_id)

    def list_descriptors(self) -> list[PhotographySceneDirectorDescriptor]:
        return [self._descriptors[key] for key in sorted(self._descriptors)]
