"""Scenario Pack registry for the V3 Scenario Hub."""

from __future__ import annotations

from .base import ScenarioPack
from .contracts import ScenarioPackManifest, ScenarioPackResolution, ScenarioPackStatus, ScenarioSelection
from .ecommerce import EcommerceScenarioPack
from .general import GeneralCreativeScenarioPack
from .placeholders import (
    BrandIPScenarioPack,
    NewMediaScenarioPack,
    PrivateDomainScenarioPack,
)


DEFAULT_SCENARIO_ID = "general_creative"


class ScenarioPackRegistry:
    """Registry of active and placeholder Scenario Packs."""

    def __init__(self, packs: list[ScenarioPack] | None = None) -> None:
        default_packs = [
            GeneralCreativeScenarioPack(),
            EcommerceScenarioPack(),
            NewMediaScenarioPack(),
            PrivateDomainScenarioPack(),
            BrandIPScenarioPack(),
        ]
        self._packs = {pack.scenario_id: pack for pack in (default_packs if packs is None else packs)}

    def list_packs(self, include_inactive: bool = True) -> list[ScenarioPack]:
        packs = list(self._packs.values())
        if include_inactive:
            return packs
        return [pack for pack in packs if pack.manifest.status == ScenarioPackStatus.ACTIVE]

    def list_manifests(self, include_inactive: bool = True) -> list[ScenarioPackManifest]:
        return [pack.manifest for pack in self.list_packs(include_inactive=include_inactive)]

    def get_pack(self, scenario_id: str) -> ScenarioPack | None:
        return self._packs.get(scenario_id)

    def resolve(self, selection: ScenarioSelection | dict | None = None) -> ScenarioPackResolution:
        selection_model = self._coerce_selection(selection)
        pack = self.get_pack(selection_model.scenario_id)
        if pack is None:
            unknown_pack = ScenarioPack(
                ScenarioPackManifest(
                    scenario_id=selection_model.scenario_id,
                    display_name=selection_model.scenario_id,
                    category="unknown",
                    status=ScenarioPackStatus.INACTIVE,
                    description="Unknown Scenario Pack.",
                    metadata={"resolution_error": "unknown_scenario"},
                )
            )
            return unknown_pack.resolve(selection_model)
        return pack.resolve(selection_model)

    def default_pack(self) -> ScenarioPack:
        pack = self.get_pack(DEFAULT_SCENARIO_ID)
        if pack is None:
            raise RuntimeError("Default General Creative Scenario Pack is not registered")
        return pack

    def _coerce_selection(self, selection: ScenarioSelection | dict | None) -> ScenarioSelection:
        if selection is None:
            return ScenarioSelection(scenario_id=DEFAULT_SCENARIO_ID)
        if isinstance(selection, ScenarioSelection):
            return selection
        return ScenarioSelection.model_validate(selection)
