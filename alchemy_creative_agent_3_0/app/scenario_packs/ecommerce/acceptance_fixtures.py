"""Owner-approved real-output acceptance fixture contracts for E-Commerce."""

from __future__ import annotations

from typing import Any

from ...schemas.models import V3BaseModel


FIXTURE_HARNESS_VERSION = "v3_ecommerce_fixture_harness_2026_07_12"


class EcommerceAcceptanceFixture(V3BaseModel):
    fixture_id: str
    owner_consent: bool = False
    source_facts: list[str] = []
    role_map: dict[str, str] = {}
    platform: str
    market: str
    placement_context: str | None = None
    allowed_claims: list[str] = []
    metadata: dict[str, Any] = {}


class EcommerceFixtureAcceptanceRecord(V3BaseModel):
    fixture_id: str
    provider_run_id: str | None = None
    gate_c_status: str = "not_run"
    terminal_seconds: float | None = None
    planner_metadata_only: bool = True
    image_similarity_only: bool = False
    human_scores: dict[str, float] = {}
    retry_superseded_closed: bool = False
    text_review_required: bool = False
    text_review_passed: bool = False
    passed: bool = False


class EcommerceFixtureRegistry:
    """In-memory registry: fixtures are descriptors, never bundled source images."""

    def __init__(self) -> None:
        self._fixtures: dict[str, EcommerceAcceptanceFixture] = {}

    def register(self, fixture: EcommerceAcceptanceFixture) -> EcommerceAcceptanceFixture:
        if not fixture.owner_consent:
            raise ValueError("E-Commerce acceptance fixtures require explicit owner consent.")
        if not fixture.source_facts or not fixture.role_map:
            raise ValueError("Fixture must declare source facts and a role map.")
        self._fixtures[fixture.fixture_id] = fixture
        return fixture

    def get(self, fixture_id: str) -> EcommerceAcceptanceFixture | None:
        return self._fixtures.get(fixture_id)

    def validate_acceptance(self, record: EcommerceFixtureAcceptanceRecord) -> list[str]:
        fixture = self.get(record.fixture_id)
        issues: list[str] = []
        if fixture is None:
            return ["fixture is not registered"]
        if not fixture.owner_consent:
            issues.append("fixture lacks owner consent")
        if record.planner_metadata_only:
            issues.append("planner metadata alone cannot pass real-output acceptance")
        if record.image_similarity_only:
            issues.append("image similarity alone cannot pass real-output acceptance")
        if record.gate_c_status != "passed" or not record.provider_run_id:
            issues.append("real Provider/Review Gate C evidence is required")
        if record.terminal_seconds is None or record.terminal_seconds <= 0:
            issues.append("bounded terminal evidence is required")
        required_scores = {"product_fidelity", "role_differentiation", "realism", "delivery_closure"}
        if not required_scores.issubset(record.human_scores):
            issues.append("human-scored product, role, realism, and delivery evidence is required")
        if not record.retry_superseded_closed:
            issues.append("retry-superseded delivery closure is required")
        fixture_requires_text_review = bool(fixture.metadata.get("text_review_required"))
        if (fixture_requires_text_review or record.text_review_required) and not record.text_review_passed:
            issues.append("required provider-native literal-copy/claim acceptance has not passed")
        if record.passed and issues:
            issues.append("record cannot be marked passed while acceptance evidence is incomplete")
        return issues
