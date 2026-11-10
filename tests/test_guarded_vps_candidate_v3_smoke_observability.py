from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "guarded-vps-candidate-v3-smoke.yml"


def test_candidate_smoke_uses_state_derived_api_unknown_classification() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    active_work_check = source.index("if ! active_work_report=")
    active_work_pass = source.index("printf '%s\\n' \"$active_work_report\"")

    assert active_work_check < active_work_pass
    assert "allow_failed_empty_v2_api_unknowns" not in source
    assert "abandon-api-unknown-job-id" not in source
    assert "GUARDED_CANDIDATE_V3_ELIGIBLE_API_UNKNOWN_JOB_IDS" not in source


def test_candidate_smoke_preflight_exit_follows_bridge_preflight() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    bridge_preflight = source.index("grep -Fxq 'GUARDED_CANDIDATE_V3_BRIDGE_PREFLIGHT=pass'")
    preflight_only = source.index('if [[ "$CANDIDATE_V3_PREFLIGHT_ONLY" == "true" ]]; then')
    preflight_pass = source.index('echo "GUARDED_CANDIDATE_V3_PREFLIGHT_ONLY=pass"', preflight_only)

    assert bridge_preflight < preflight_only < preflight_pass
    assert "eligible_api_receipt" not in source
    assert "candidate_v3_api_unknown_receipt_invalid" not in source
