# PR34 browser acceptance follow-up (2026-10-15)

## Correction model and frozen scope

- Total objective: review-only images remain visible without promotion to formal delivery; export contains only eligible selected images.
- This phase: close DOT's two browser-test gaps and put export/browser checks into CI. No production behavior changes, merge, deployment or provider calls.
- Baseline: `ef7de90de64c0852fdfe2bd7fbe633633a94a822`, branch `codex/v3-review-raw-images`; main remains `569dffea`.
- Allowed changes: Doc263 browser test, capacity-retention CI workflow, this report.
- D0/I1/A1: established product contract, asynchronous fixture integration, independent read-only review required. Main agent is the sole writer. Hook/runtime routing attestation unavailable (`HOOK_UNVERIFIED`, `ROUTE_UNVERIFIED`).

Intended behavior: the browser opens the actual project surface, applies the full Job response and renders the candidate before clicking it. A quality failure uses the existing quality-failure wording, never evidence-incomplete wording.

Observed mismatch: on unchanged baseline, real local Chromium ran the two review-only tests; both failed. Desktop expected obsolete wording. Mobile's project referenced a different Job from the injected state, and the mock returned an empty object during the authoritative full refresh.

Owning layer: test fixtures and acceptance orchestration. The production full-detail response remains authoritative; injected transient state and overlay visibility are not completion evidence. Keep production load order and export implementation unchanged.

Minimal correction: align project/Job/candidate identity, serve the complete Job via mocked GET, start without an injected current Job, wait for applied Job and rendered target, use an identity selector and ordinary click. Exercise immediate and explicitly deferred responses. Correct the desktop assertion and keep the reverse evidence-incomplete assertion. Execute both files in CI.

## Verification record

Baseline: 2 failed, 6 deselected in real Chromium, confirming both reported gaps. All data is synthetic and API transport is mocked.

The first corrected run exposed a separate fixture ordering issue: the gallery renderer had run before server outputs arrived (2 failures, 11 passes). Detail loading does not refresh that separate surface. Its renderer now runs after the full response is applied; production code was not changed.

Final local results:

- Python 3.12, pytest 8.3.3, Playwright 1.62.0, actual Chromium: **9 browser cases + 4 export cases passed** (13 total, no skips).
- A fresh venv without system site packages, using exactly the new CI dependencies, repeated both files: **13 passed** in 10.75 seconds. JUnit was saved outside the repository.
- Focused desktop and immediate/deferred mobile cases: **3 passed per round, three consecutive rounds** (overlap with the above, not additive).
- `node --test tests/*.test.mjs`: **181 passed**.
- Workflow YAML parse, Python AST, desktop/mobile JavaScript syntax and `git diff --check`: passed.
- New `v3-review-export-browser` CI job runs both complete files and publishes JUnit; triggers now include V3 source/tests and this documentation. Remote CI status must be checked against the pushed head, not inherited from the previous SHA.

Independent audit: `/root/pr34_browser_acceptance_audit`, parent `/root`, requested `madv2_audit_a1_luna_xhigh` (`gpt-6-luna`, `xhigh`), terminal result **PASS** before parent completion. The auditor independently ran 9 browser cases, 4 export cases, and the mobile pair three times (2 passed each round). It found no weakened assertion or hidden async race in the frozen test/workflow diff. Actual route settings were not independently observable: `ROUTE_UNVERIFIED`, review-admissible; `HOOK_UNVERIFIED`. This is not a claim of independently verified model routing.

The audit covered the final test/workflow diff against `ef7de90`; this result paragraph was appended afterward. Main stays clean at `569dffea`. PR #34 remains Draft; no merge or deployment is authorized by this phase receipt.

Reproduction from the feature worktree:

```text
python -m pip install pytest==8.3.3 pydantic==2.13.4 Pillow==12.3.0 httpx==0.28.1 python-dotenv==1.2.2 playwright==1.62.0
python -m playwright install chromium
python -m pytest -q alchemy_creative_agent_3_0/tests/test_v3_generic_export_review_gate.py alchemy_creative_agent_3_0/tests/test_v3_doc263_ecommerce_ui_recovery_browser.py
node --test tests/*.test.mjs
```

On Linux CI, Chromium installation uses `--with-deps`. The local tests exercise real HTML/JS and normal Chromium clicks with synthetic API responses; they are not production HTTP, real-device layout, or real-provider acceptance.

## Boundaries

### CI definition follow-up

The first pushed follow-up (`88f348ad`) did not start CI jobs: run `38692200870` failed at workflow validation with zero check runs. YAML parsing alone did not validate GitHub expression contexts. The new job-level environment used `runner.temp`, which is not available at that evaluation level. Correction: use `github.workspace/.ci-v3-review-media` for the job-level isolated data root (as the existing jobs do), and retain `runner.temp` only in step-level fields where it is available. This changes CI orchestration only. Do not count the rejected run as a product test failure or a passed CI receipt.

Actionlint 1.7.12 reproduced the exact forbidden-context error before correction and passed afterward (shellcheck/pyflakes integrations disabled). The same independent auditor confirmed the proposed one-line correction against GitHub's context-availability contract and reached terminal completion; no product tests or code changed in this follow-up.

DOT reported Doc260 retry evidence-plan failure on both PR and `569dffea`; this phase does not change that separate behavior or count it as passing. Track separately before claiming broader V3 acceptance. No real provider, VPS, production migration or live-browser production acceptance is part of this phase.
