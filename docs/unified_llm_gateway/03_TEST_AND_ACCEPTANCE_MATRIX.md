# Test and Acceptance Matrix

Status: focused implementation regressions and final independent code re-audit
passed. The corrected-code real-image acceptance and VPS release remain pending.

## Unit and contract tests

| Case | V1 | V2 | V3 | LAB | Required evidence |
|---|---:|---:|---:|---:|---|
| Defaults are Claude Sonnet 5.5, Kimi K3, then GPT-6.1-sol | ✓ | ✓ | ✓ | ✓ | Effective ordered candidate list, no secret values |
| Exactly one text gateway key configures both candidates | ✓ | ✓ | ✓ | ✓ | Candidate calls share one injected key; no per-model key fields |
| Main succeeds | ✓ | ✓ | ✓ | ✓ | One request, primary model recorded, fallback false |
| Primary connect/DNS/TLS failure | ✓ | ✓ | ✓ | ✓ | Bounded move to backup, same logical request |
| Primary read/overall timeout | ✓ | ✓ | ✓ | ✓ | Backup gets remaining shared budget |
| Primary 429/5xx/upstream unavailable | ✓ | ✓ | ✓ | ✓ | Backup selected with typed reason |
| Shared-key 401/403 | ✓ | ✓ | ✓ | ✓ | Fast terminal failure; no pointless candidate sweep |
| Candidate-specific model 403/unavailable | ✓ | ✓ | ✓ | ✓ | Advance only for structured candidate-scoped gateway error |
| Malformed local request/protocol body | ✓ | ✓ | ✓ | ✓ | No failover masking adapter defect |
| Safety/policy refusal | ✓ | ✓ | ✓ | ✓ | No route-around attempt |
| Invalid structured output | ✓ | ✓ | ✓ | ✓ | Bounded schema repair/fallback, identical validator |
| All candidates fail | ✓ | ✓ | ✓ | ✓ | Attributable failure; no false success |
| No secret in logs/status/errors | ✓ | ✓ | ✓ | ✓ | Redaction assertions |

## Product-specific regression tests

### V1

- Verify configured fallback model name is the model actually sent to the
  gateway; cover the current stale `BACKUP_LLM_MODEL` path.
- Verify Claude/OpenAI protocol adapters both receive the one canonical key.
- Verify `swift` remains local-only and balanced/studio/atelier preserve their
  existing effort values.
- Verify the settings screen has one unified text gateway key field and does
  not expose model-specific text credentials. Preserve explicitly labeled
  image-provider key fields and image routing.
- Verify primary and backup model IDs are editable in desktop/mobile, saved
  with the matching protocol provider, and become the actual routed candidates.
- Simulate a primary that continues yielding data beyond its configured read
  idle threshold and prove the V1 per-candidate wall-clock cap cancels it
  while the fallback still receives its allotted slice. Cover both V1 prompt
  enrichment and the V1 JSON planner.
- If a V1 same-candidate repair/retry path is enabled by its existing
  contract, verify it shares the candidate's original deadline and cannot
  consume or reset the fallback slice.

### V2

- Verify main Claude invocation and Kimi/GPT fallback candidates receive the same secret via
  protocol-correct transient environment/header construction.
- Verify checkpoint output survives fallback and the next stage continues from
  that checkpoint; the resulting creative prompt remains Claude-authored or
  derives from the compressed Claude checkpoint when such a checkpoint exists.
- Verify a classified first-stage Claude route failure with no checkpoint
  dispatches Kimi and then GPT on the same frozen request/schema as needed and accepts only the
  existing V2 contract; verify it does not use deterministic creative logic.
- Verify policy/permission boundaries and multimodal-required blocking remain
  intact; verify V2 does not import V1 modules.
- Verify fallback timing cannot reset or exceed the logical stage/job budget.
- Verify a Claude soft timeout first runs the bounded compressed/micro Claude
  continuation; Kimi/GPT fallback is eligible only after that continuation budget
  is exhausted. Hard route failures may still advance immediately when no
  recoverable Claude continuation is pending.
- Verify the single gateway key is write-only through V2 runtime settings,
  persists outside JSON settings with owner-only file permissions, and is
  refreshed by independent queue-worker processes before orchestration.
- Verify V2's OpenAI-compatible fallbacks use absolute async deadlines and reserve
  a bounded time slice for each remaining candidate, and
  primary Claude invocations receive the computed remaining stage timeout.
- Verify every V2 fallback option has a known adapter mapping, the selected
  option reaches that adapter with the shared key, unknown models fail closed,
  and Claude CLI-native fallback is disabled so the controller owns every
  model transition and provenance record.
- Verify V2 carries the configured semantic effort to supported compatible
  candidates, omits it for unsupported models, and preserves the order Kimi K3,
  GPT-6.1-sol, then any remaining legacy setting.
- Verify no raw GPT provider response is persisted; only bounded non-content
  provenance is retained.

### V3

- Verify Claude is attempted first, then Kimi and GPT after eligible failures,
  without changing the frozen request or stage identity.
- Verify one-key protocol mapping to Anthropic Messages and OpenAI-compatible
  request paths.
- Verify each transport candidate receives only its dynamically allocated
  share of the existing shared budget; the V3 finalizer handoff reserve remains
  at least 220 seconds when currently required.
- Verify the code's 520-second default separately from the 550-second value
  explicitly configured by the checked-in local/VPS deployment examples; both
  preserve the 220-second handoff/finalizer reserve.
- Verify constrained schema repair and same-candidate recovery consume the
  candidate's allocated share and cannot reduce the 220-second reserve or
  extend the logical deadline.
- Verify one primary timeout advances through eligible Kimi/GPT candidates
  without a second full Claude transport attempt or resetting the execution clock.
- Verify output from any candidate must pass the full Brain schema and
  sign-off contract.
- Verify required remote Brain failure after all candidates stops before the
  image provider is called.
- Fail all V3 model candidates, including an explicitly configured additional
  candidate, and verify the terminal safe receipt retains up to four model IDs,
  classified outcomes, and bounded elapsed times without
  prompt, response, or secret data.

### LAB

- Verify text planning uses the ordered Claude/Kimi/GPT model list with the same
  key, actual-model provenance, and bounded deadline.
- Simulate a slow primary response and, where the existing LAB text contract
  permits same-candidate repair/retry, prove the first call and recovery share
  one absolute candidate deadline; the backup must retain its allocated
  remainder of the 210-second logical budget.
- Configure a stale LAB text model that differs from V1's canonical primary;
  verify LAB text status and requests follow V1's canonical primary/backup,
  while LAB vision model selection remains unchanged.
- Verify a refusal is terminal for both text-only and image-conditioned LAB
  requests; image-conditioned paths must not bypass failure classification.
- Keep a separate assertion that this text change does not silently change
  `LAB_VISION_PROVIDER` or image-model routing.

## Local real-image acceptance (only after code audit PASS)

1. Record main commit, local diff hash, effective non-secret model order, and
   that one unified text key is configured.
2. Submit one ordinary V3 General Template request using a simple benign
   prompt, no reference images, and one requested output.
3. Confirm Brain provenance identifies the actual text model. If Claude fails
   with eligible route errors, confirm Kimi K3 then GPT-6.1-sol completed the same Brain
   contract and the receipt records the failover.
4. Confirm the selected image renderer received the finalized V3 prompt and
   produced exactly one real image candidate.
5. Confirm shared review/delivery reaches the expected final state; fail the
   gate if the request was mock, deterministic-only, no-op, or if image
   generation started after a required Brain failure.
6. Preserve job/request IDs, output path, model/fallback receipt, and safe logs
   in Doc06. Never persist API keys or full secret-bearing env output.
7. Display the resulting local image to the user and request user acceptance;
   generation success alone does not complete total acceptance.
