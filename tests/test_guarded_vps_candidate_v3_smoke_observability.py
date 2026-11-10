from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "guarded-vps-candidate-v3-smoke.yml"


def test_candidate_smoke_only_reports_api_unknown_ids_after_guard_accepts_them() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    allow_flag = source.index('if [ "$allow_failed_empty_v2_api_unknowns" = true ]; then')
    active_work_check = source.index("if ! active_work_report=")
    active_work_pass = source.index("printf '%s\\n' \"$active_work_report\"")
    receipt = source.index("GUARDED_CANDIDATE_V3_ELIGIBLE_API_UNKNOWN_JOB_IDS")

    assert allow_flag < active_work_check < active_work_pass < receipt
    assert 'verified_api_job_ids="${abandon_api_ids//$\'\\n\'/,}"' in source


def test_candidate_smoke_forwards_verified_job_ids_before_preflight_exit() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    bridge_preflight = source.index("grep -Fxq 'GUARDED_CANDIDATE_V3_BRIDGE_PREFLIGHT=pass'")
    preflight_only = source.index('if [[ "$CANDIDATE_V3_PREFLIGHT_ONLY" == "true" ]]; then')
    receipt_forward = source.index("eligible_api_receipt=", preflight_only)
    preflight_pass = source.index('echo "GUARDED_CANDIDATE_V3_PREFLIGHT_ONLY=pass"', preflight_only)

    assert bridge_preflight < preflight_only < receipt_forward < preflight_pass
    assert "grep -F 'GUARDED_CANDIDATE_V3_ELIGIBLE_API_UNKNOWN_JOB_IDS=' \"$lifecycle_log\"" in source
    assert "candidate_v3_api_unknown_receipt_invalid" in source
    assert "job_[0-9a-f]{12}" in source
