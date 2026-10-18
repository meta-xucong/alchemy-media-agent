# Implementation and Code Audit Receipt

Status: the final implementation diff passed fresh independent code re-audit and focused regression tests. Corrected-code local V3 real-image acceptance remains pending; Doc06 records a prior source snapshot only.

## Frozen implementation target

- Main baseline commit: `501a625e0e09b73d49e0b4dfc711fc50444e4310`
- Document audit status: design-v7 PASS; aggregate document SHA256 is recorded
  in `04_DESIGN_AUDIT_RECEIPT.md`.
- Historical implementation revision/hash: the initial independent review
  applied to the earlier diff fingerprint below. Later corrections were
  separately re-audited as recorded in the final follow-up section; this old
  fingerprint is not the current source fingerprint.
  - Tracked diff SHA256: `d568e9798fea096beeb53b963bc24e99e2450e9d5c3045da213803d1d88c4327`.
  - `custom_media_agent_2_0/tests/test_unified_llm_gateway_failover.py` SHA256:
    `a18ef4645bb68c69e1d26f26607b53a2f416e663c2b3257cbafc1776e737a40f`.
  - `tests/test_unified_llm_gateway_v1_lab.py` SHA256:
    `b4413d87df62743d4517adfe5f23bda37b4d679050ab57867b03532b30cdcbed`.
- Hash input is recorded as a three-part tuple to avoid ambiguous combined-path
  serialization: exact stdout bytes of `git diff --binary -- alchemy_creative_agent_3_0
  custom_media_agent_2_0 scripts src_skeleton tests`, plus raw bytes of each
  untracked focused test file hashed separately above.
- Historical changed-file scope: 28 modified tracked code/test/deployment/UI
  files plus the two new focused failover test modules. The separate
  `docs/unified_llm_gateway/` family is excluded from that earlier hash.
- Focused tests/outputs:
  - V1/LAB gateway regressions: 16 passed.
  - V2 failover suite: 11 passed; selected GPT fallback, unsupported effort,
    and canonical fallback queue tests: 3 passed; checkpoint, continuation,
    and fallback stage tests: 14 passed. Test fixtures accept the new timeout
    and reasoning-effort arguments, and the V2 test factory clears inherited
    gateway credentials to prevent unintended network calls.
  - V3 terminal route/attempt receipt tests, including Anthropic refusal-block
    fail-closed behavior: 4 passed.
  - V3 provider timeout suite: 34 passed.
  - V3 Doc175 remote Brain suite: 26 passed.
  - Python compileall: V1/LAB, V2 and V3 edited production modules passed.
  - `git diff --check`: passed with Git line-ending warnings only.
  - Broader V1 run: 110 passed, 1 failed in an existing history-owner smoke
    test. No full V2 API or V3 adapter suite pass is claimed.
- Test-isolation incident: before the V2 test factory was updated to clear
  inherited unified gateway settings, one checkpoint selection run executed
  while the process had a gateway key and base URL configured. Its GPT fallback
  path may have issued real text-model requests; test output cannot confirm
  whether or how many requests reached the gateway. It did not run V3 image
  generation. All subsequent focused V2 tests used cleared credentials unless
  a test explicitly installed a fake gateway transport.
- Auditor child identity and terminal state for the earlier audit:
  `/root/design_audit_v2`, independent read-only review found the Anthropic
  refusal-block gap and stale V2 test doubles. Both findings were corrected;
  final review of later corrections is recorded below.

## Required audit result

Check the frozen scope, full diff, file/symbol boundaries, model order,
single-key use, protocol adaptation, timeout/failure matrix, V1 exact fallback
model use, V2 checkpoint/isolation rules, V3 remote Brain contract and
no-image-on-failed-Brain behavior, LAB isolation, secret redaction, and every
focused test. Return `PASS`, `FAIL`, or `INSUFFICIENT_EVIDENCE`. Do not run
external provider calls while auditing code.

## Theory-first correction model: V3 connect timeout

- Intended behavior: Doc01 §4 requires an 8-second connect timeout while the
  request-specific remaining candidate budget remains the bound for read,
  write, pool wait, and the outer worker deadline.
- Observed mismatch: the local acceptance receipt shows the GPT fallback
  spending 239.269 seconds in `connect_timeout`. V3's Anthropic client sets an
  explicit 8-second connect bound, but both OpenAI SDK calls passed a scalar
  timeout. OpenAI SDK 2.53.0 and HTTPX 0.28.1 interpret that scalar as the
  timeout for all phases, including connect. The retained direct streaming
  collector separately allowed 20 seconds, contrary to Doc01.
- Owning layer: V3 Brain provider transport adapter in
  `alchemy_creative_agent_3_0/app/llm_brain/providers.py`; the shared logical
  deadline and failover policy remain authoritative.
- Conflict: the Doc01 8-second connect bound is correct; the SDK call's scalar
  timeout accidentally duplicates the candidate budget into the connect phase.
  The transport timeout object is supporting configuration, while the existing
  candidate deadline and outer worker deadline remain the hard limits.
- Minimal complete correction: pass an HTTPX `Timeout` object to both OpenAI
  SDK Responses and non-streaming Chat Completions calls, with connect capped
  at 8 seconds and the other phase limits bounded by the remaining candidate
  timeout. Align the retained direct HTTPX streaming collector with the same
  8-second contract and lock it with a regression assertion. Do not change
  model order, logical budget, retry count, route URLs, JSON recovery, or image
  behavior. Make focused SDK tests independent of developer `.env` credentials.
- Phase gate: the initial implementation audit applied only to its recorded
  fingerprint. The timeout correction received its own focused tests and fresh
  independent audit below, so corrected-code real-generation acceptance may
  proceed.

## V3 connect-timeout correction audit

- Auditor: `/root/design_audit_v2`, independent read-only review.
- Result: PASS. The Responses SDK, non-stream Chat Completions SDK, and retained
  direct HTTPX streaming collector all cap connect at 8 seconds. Read, write,
  and pool timeout values remain bounded by the effective candidate timeout;
  the existing candidate and logical deadlines remain authoritative.
- Focused verification: SDK timeout tests 2 passed; V3 provider-timeout suite
  34 passed; the auditor additionally ran same-request failover, candidate
  budget allocation, and streaming connect-cap checks. Combined focused audit
  evidence: 39 passed. Compileall and `git diff --check` passed.
- Test isolation: both SDK tests set explicit fake unified gateway credentials
  and assert connect/read/write/pool values; they do not depend on local `.env`.
- Current implementation fingerprint: tracked diff SHA256
  `d568e9798fea096beeb53b963bc24e99e2450e9d5c3045da213803d1d88c4327`,
  `custom_media_agent_2_0/tests/test_unified_llm_gateway_failover.py` SHA256
  `a18ef4645bb68c69e1d26f26607b53a2f416e663c2b3257cbafc1776e737a40f`, and
  `tests/test_unified_llm_gateway_v1_lab.py` SHA256
  `b4413d87df62743d4517adfe5f23bda37b4d679050ab57867b03532b30cdcbed`.
- This audit made no external provider calls. The 239-second connection wait
  is explained by the timeout configuration defect; the lower-level reason
  that connection could not be established then remains unproven.
- Post-audit acceptance diagnostic: a direct in-process route-handler call
  omitted the public endpoint's `auto_generate.metadata.require_real_images`
  intent. The durable Job therefore selected `MOCK_GENERATION`; its
  `generated` status is explicitly excluded from real-image acceptance. This
  was a harness-entry mistake, not evidence that a real provider was replaced
  after dispatch. The supported endpoint freezes real intent when the UI sends
  `auto_generate`; current frontend call sites do so. No additional generation
  or provider retries were made after the mock fixture was identified.

## Independent code audit result

- Auditor: `/root/design_audit_v2`, independent read-only review.
- Result: PASS; no blocking findings.
- Auditor independently recomputed and matched all three fingerprint parts
  above. It confirmed the V3 Anthropic refusal fix does not call the GPT backup,
  the V2 checkpoint mocks and credential-isolation fixture are corrected, and
  no other blocker was found.
- Independently run focused deterministic tests: V1/LAB 16 passed; V2
  checkpoint selection 14 passed; V3 critical routing tests 4 passed plus the
  Anthropic refusal case 1 passed. Compileall and `git diff --check` passed.
- Historical V2 test-isolation incident remains disclosed above. Current code
  audit itself made no provider calls. The first guarded local V3 run blocked at
  the Brain planning gate; a later official-endpoint run completed real image
  generation. Both receipts are recorded in Doc06.

## Findings

None blocking.

## Post-receipt local gateway revalidation

This is append-only follow-up evidence. It does not replace or modify the
fingerprinted independent audit above.

- Workspace state: branch `main`; `HEAD` and `origin/main` both resolve to
  `501a625e0e09b73d49e0b4dfc711fc50444e4310`. The implementation remains
  uncommitted. Only read-only VPS status commands were used; no remote files,
  services, or settings were changed, and no provider call was made.
- Corrections after the recorded fingerprint: V1 no longer builds text
  candidates without both explicit gateway settings; V3's default remote
  availability requires both gateway key and base URL; bootstrap no longer
  substitutes personal or image-provider credentials for the gateway key.
  Tests now distinguish gateway routing from per-candidate JSON recovery and
  assert the Claude → Kimi → GPT fallback sequence.
- Focused validation on the current working tree: V1/LAB unified gateway
  suite, 19 passed; V2 unified gateway plus checkpoint/fallback compatibility
  suite, 19 passed; V3 Brain adapter suite, 67 passed using the repository's
  offline harness and fake gateway credentials. PowerShell parser check and
  `git diff --check` passed.
- Local configuration check (values suppressed): V1 and V2 each have both
  gateway fields configured. V3 reports `configured` when initialized through
  the V1 host environment; importing its adapter alone in a bare process does
  not load the host `.env`. No live gateway request was made.
- Remote alignment check: GitHub `main` is `501a625e0e09b73d49e0b4dfc711fc50444e4310`.
  The V1/V3 container image reports revision `51ba1e2d39e5bd27331c2f98af60859ab6c6b9cb`,
  which is three commits behind that main. Its mounted `.env` and container
  environment have no gateway key/base. The V2 API, worker, and sync-worker
  services are active, but both loaded systemd env files have empty gateway
  key/base and no runtime `llm_gateway.env` was found. The existing PR #35,
  “Align Alchemy upstream model defaults,” remains open and GitHub reports it
  as not mergeable; its diff contains no `LLM_GATEWAY_*` settings, sets V3's
  model to GPT, and configures only GPT as the V2 fallback, so it does not
  implement the requested unified Claude → Kimi → GPT route. Its description
  says it does not deploy to the VPS. The running V2 orchestrator source hash
  also differs from the local working-tree source hash.
- Final independent re-audit after the V1/LAB candidate-attempt receipt fix:
  PASS. The reviewed correction makes V1 planning fail closed when remote
  planning is enabled but the unified gateway is not configured, and keeps
  V1/LAB model-attempt receipts bounded and secret-free. The V3 product and
  scenario runtime projections use the same strict receipt sanitizer. No
  provider calls were made by this source audit.
- Latest focused regression evidence after those corrections: V1/LAB 5 passed;
  V3 product/scenario receipt projections 26 passed; V3 terminal model-attempt
  receipt 1 passed. The previously recorded V1/LAB 19, V2 19, and V3 adapter
  67 passing focused suites remain additional evidence for unchanged paths.
- VPS release and runtime alignment are not certified by this source audit.
  Doc06's earlier image run does not certify this later working-tree state.
