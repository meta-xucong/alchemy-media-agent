from alchemy_creative_agent_3_0.app.shared_capabilities import (
    CapabilityInput,
    CapabilityResult,
    CapabilityRunStatus,
    CapabilityStatus,
    SharedCapabilityModule,
    SharedCapabilityRegistry,
)


class FakeCapability(SharedCapabilityModule):
    def __init__(self, module_id: str, order: int) -> None:
        self.module_id = module_id
        self.order = order
        self.version = "test"

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        return CapabilityResult(
            module_id=self.module_id,
            version=self.version,
            status=CapabilityStatus.SUCCESS,
            confidence=1.0,
            facts={"prior_count": len(capability_input.prior_results)},
            audit_trail=[f"{self.module_id}: ok"],
        )


class FailingCapability(SharedCapabilityModule):
    module_id = "failing"
    version = "test"
    order = 2

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        raise RuntimeError("intentional failure")


def _input() -> CapabilityInput:
    return CapabilityInput(job_id="job_test", scenario_id="general_creative", user_input="create a poster")


def test_shared_capability_registry_runs_modules_in_deterministic_order() -> None:
    registry = SharedCapabilityRegistry([FakeCapability("second", 20), FakeCapability("first", 10)])

    result = registry.run(_input())

    assert result.status == CapabilityRunStatus.COMPLETE
    assert [item.module_id for item in result.results] == ["first", "second"]
    assert result.results[0].facts["prior_count"] == 0
    assert result.results[1].facts["prior_count"] == 1
    assert result.model_dump(mode="json")["status"] == "complete"


def test_optional_capability_failure_degrades_without_required_failure() -> None:
    registry = SharedCapabilityRegistry([FakeCapability("ok", 1), FailingCapability()])

    result = registry.run(_input())

    assert result.status == CapabilityRunStatus.DEGRADED
    assert result.required_failures == []
    assert result.results[-1].status == CapabilityStatus.ERROR
    assert result.warnings[-1].code == "capability_execution_failed"


def test_required_capability_failure_marks_run_failed() -> None:
    registry = SharedCapabilityRegistry([FakeCapability("ok", 1), FailingCapability()])

    result = registry.run(_input(), required_module_ids=["failing"])

    assert result.status == CapabilityRunStatus.FAILED
    assert result.required_failures == ["failing"]


def test_missing_required_capability_marks_run_failed() -> None:
    registry = SharedCapabilityRegistry([FakeCapability("ok", 1)])

    result = registry.run(_input(), module_ids=["missing"], required_module_ids=["missing"])

    assert result.status == CapabilityRunStatus.FAILED
    assert result.required_failures == ["missing"]
    assert result.warnings[0].code == "capability_not_registered"
