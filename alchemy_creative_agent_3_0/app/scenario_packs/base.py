"""Base Scenario Pack behavior."""

from __future__ import annotations

from .contracts import ScenarioPackManifest, ScenarioPackResolution, ScenarioPackStatus, ScenarioSelection


class ScenarioPack:
    """Small product-level pack boundary before the central creative brain."""

    manifest: ScenarioPackManifest

    def __init__(self, manifest: ScenarioPackManifest | None = None) -> None:
        if manifest is not None:
            self.manifest = manifest

    @property
    def scenario_id(self) -> str:
        return self.manifest.scenario_id

    @property
    def can_create_jobs(self) -> bool:
        return self.manifest.can_create_jobs

    def resolve(self, selection: ScenarioSelection | None = None) -> ScenarioPackResolution:
        selection = selection or ScenarioSelection(scenario_id=self.scenario_id)
        selected_mode_id = selection.mode_id or self.manifest.default_mode_id
        selected_preset_id = selection.preset_id
        warnings: list[str] = []

        if selected_mode_id and self.manifest.supported_mode_ids and selected_mode_id not in self.manifest.supported_mode_ids:
            warnings.append(f"mode_id '{selected_mode_id}' is not supported by scenario '{self.scenario_id}'")
            selected_mode_id = self.manifest.default_mode_id

        if selected_preset_id and self.manifest.preset_ids and selected_preset_id not in self.manifest.preset_ids:
            warnings.append(f"preset_id '{selected_preset_id}' is not supported by scenario '{self.scenario_id}'")
            selected_preset_id = None

        if self.manifest.status != ScenarioPackStatus.ACTIVE:
            warnings.append(f"scenario '{self.scenario_id}' is not active in the current V3 stage")

        return ScenarioPackResolution(
            selection=selection,
            manifest=self.manifest,
            status=self.manifest.status,
            can_create_jobs=self.can_create_jobs,
            selected_mode_id=selected_mode_id,
            selected_preset_id=selected_preset_id,
            warnings=warnings,
            metadata={
                "scenario_pack": self.scenario_id,
                "scenario_pack_status": self.manifest.status,
            },
        )
