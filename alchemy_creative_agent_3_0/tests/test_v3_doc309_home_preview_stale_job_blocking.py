from pathlib import Path
from types import SimpleNamespace

from alchemy_creative_agent_3_0.app.project_mode import V3ProjectModeService
from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectRecord


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "alchemy_creative_agent_3_0" / "app" / "project_mode" / "service.py"
DESKTOP = ROOT / "src_skeleton" / "app" / "static" / "app.js"
MOBILE = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"
DOC = ROOT / "alchemy_creative_agent_3_0" / "docs" / "309_V3_HOME_PREVIEW_STALE_JOB_BLOCKING_REPAIR_SPEC.md"


def _project() -> ProjectRecord:
    return ProjectRecord(
        project_id="project_stale_job_regression",
        title="Preview ordering regression",
        user_goal="Keep the newest deliverable visible.",
        short_summary="Keep the newest deliverable visible.",
        job_ids=["job_old", "job_new"],
        created_at="2026-09-01T00:00:00+00:00",
        updated_at="2026-09-01T00:01:00+00:00",
        metadata={"veyra_user_id": 7},
    )


def test_home_preview_passes_effective_gate_newest_first() -> None:
    service = object.__new__(V3ProjectModeService)
    project = _project()
    records = [
        SimpleNamespace(job_id="job_old", created_at="2026-09-01T00:10:00+00:00"),
        SimpleNamespace(job_id="job_new", created_at="2026-09-02T00:10:00+00:00"),
    ]
    observed: list[list[str]] = []
    service.product_service = SimpleNamespace(
        output_store=SimpleNamespace(
            list_by_project=lambda project_id, limit: records,
        )
    )

    def fake_delivery_gate(candidate, *, limit, owner_user_id, compact):
        # The real gate iterates project.job_ids in reverse. Observe the
        # effective order rather than the temporary candidate record order.
        observed.append(list(reversed(candidate.job_ids)))
        return [{"project_id": candidate.project_id, "output_id": "newest-output"}]

    service._project_output_items = fake_delivery_gate

    result = service._project_delivery_preview_items(
        project,
        limit=1,
        owner_user_id=7,
        compact=True,
    )

    assert result == [{"project_id": project.project_id, "output_id": "newest-output"}]
    assert observed == [["job_new", "job_old"]]


def test_doc309_contract_and_frontend_timeouts_are_present() -> None:
    service_source = SERVICE.read_text(encoding="utf-8")
    desktop_source = DESKTOP.read_text(encoding="utf-8")
    mobile_source = MOBILE.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")

    assert 'update={"job_ids": list(reversed(candidate_job_ids))}' in service_source
    assert "v3HomePreviewRequestTimeoutMs = 30000" in desktop_source
    assert "v3RequestWithTimeout(outputRequestPath, v3HomePreviewRequestTimeoutMs)" in desktop_source
    assert "mobileV3HomePreviewRequestTimeoutMs = 30000" in mobile_source
    assert "mobileV3RequestWithTimeout(" in mobile_source
    assert "mobileV3HomePreviewRequestTimeoutMs" in mobile_source
    assert "let homePreviewSettled = false" in mobile_source
    assert "if (!homePreviewSettled) renderMobileV3ProjectCards();" in mobile_source
    assert "does not change Brain or Provider" in doc
    assert "stale historical job" in doc
    assert "GitHub" in doc and "VPS" in doc
