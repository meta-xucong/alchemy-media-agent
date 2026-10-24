# RB12: current-main Render Bridge integration

## Goal and correction model

The total goal is local Windows Alchemy + Render Bridge + the owner's Codex CLI
integration. This increment only integrates and tests the current source revisions;
real CLI, real image/review quality and authorized fallback cost acceptance remain
local gates. No main-branch merge or deployment is authorized by this increment.

Alchemy main `1eaba553967883c279ec12e8bdfd4e61955a3f1e` is integrated into the
published Bridge feature history without rewriting it. This preserves Doc341–349
job-bound result display, character/first accepted continuity, reference-aware
variation/continuation, diagnostics and output-removal behavior. Bridge remains an
optional, default-disabled Standard/general single-image review-only adapter.

The review authority changed on main: completed provider timeout, provider error
and malformed JSON are terminal manual-review outcomes, not reasons to invoke the
whole visual review again. The previous Bridge timeout fixture contradicted that
policy. Correct the fixture and explicitly test terminal outcomes, while retaining
same-checkpoint recovery for interrupted review and unavailable/unconfigured
review providers. Do not restore obsolete timeout retries in production code.
Registration/ACK proves native persistence, not passed review or formal delivery.
A generated job status is not a passed visual-review verdict.

Main's first accepted anchor finalizer now runs after review continuation and
supports one image. It must still use the canonical formal-delivery projection;
Bridge review-only outputs must never become automatic continuity anchors or
completed General suite roles. Add integrated tests at this shared-authority seam,
not a parallel Bridge anchor policy. Frozen canonical reference order and original
bytes, project semantic revisions, plan keys and output identities stay unchanged.

## Bridge counterpart

The local development counterpart is branch `codex/bridge-progress-20261023`,
commit `a89fef357ba69b5ca7ad5cb25c68474a38a01a44` in
`meta-xucong/alchemy-render-bridge`, following the previous `fef12f65` handoff.
Its aborted-turn recovery is explicit same-attempt reconciliation, not permission
for Alchemy to re-render or switch uncertain in-flight tasks to Sub2API. Keep
unknown outcomes queryable; accept a later matching receipt once through the
same native checkpoint/review-only/ACK path. Never delete execution journals to
unblock a slot. HTTP integration remains versioned and independent of Bridge code.

The counterpart accepts `accepted_cli_version` exactly `codex-cli 0.157.1` or
`codex-cli 0.163.0` for execution (the prefix is required).
The account-health RPC probe supports 0.163.0 only. With 0.157.1 and account probing
enabled, health remains unknown; do not promise automatic health recovery for that
combination. A supported executable version does not prove account or image-tool
acceptance. Keep the default-off probe and verify the actual local capability.

The pinned counterpart also adds a separate completed-rollout recovery gate for
Agent stream loss. It accepts only the already-bound task/attempt, same thread and
turn, exactly one completed generated original and a terminal `task_complete` at
the end of the local rollout. It writes a versioned evidence record and reacquires
`upload_only`; it never resumes or creates a Codex turn. This is distinct from the
existing `turn_aborted(reason="interrupted")` review-only recovery.

## Verification

Local sanitized verification on 2026-10-24: **401 passed** in the full Bridge plus
affected original-path selection (290 existing deprecation warnings); **245 passed**
in the persisted current-main review/Brain/reference/continuity seam selection;
**13 passed** in the three Node current-job/desktop/mobile regression files. The
final strengthened anchor assertions were additionally rerun with all 36 native
registration cases passing; this overlaps the 401 and is not an extra test count.
Dependency consistency and whitespace checks passed. Browser/Windows execution
is delegated to exact-head CI, not claimed from these Linux checks. Historical
RB03/RB08 receipts remain evidence for their pinned older revisions, not this head.
All automated tests use isolated data and synthetic provider/review fixtures.

### Local Windows real CLI evidence

On 2026-10-24, isolated loopback Alchemy (`8017`) and Bridge (`8788`) both started
and reported the explicit `fake-image,codex-image` allowlist. One authorized
Bridge task used the local `codex-cli 0.163.0` / `gpt-6.1-sol` configuration. Codex
generated exactly one PNG; its actual 1254x1254 original was 2,199,572 bytes with
SHA-256 `86fec176ab29efd7fa4ecf0789f858acb98d8a03a68124fff9939a615979078b`.
The Agent live stream ended before collection, so the task was retained rather
than regenerated. The completed-rollout recovery then used the same task/attempt
and an `upload_only` claim to create receipt `receipt_a8463161c37442168c6e39169725db87`.
The Bridge artifact bytes had the identical SHA-256, size and dimensions; no resize,
re-encode or second generation occurred. This direct Bridge receipt remained
`artifacts_ready`: absent a real Veyra-authenticated Alchemy user/project, no Native
registration or ACK was fabricated. It is evidence for the local Bridge/CLI layer,
not end-to-end host review, formal delivery, billing or fallback acceptance.

## Test-authority corrections

The isolated current-main Brain suite exposed three stale transport fixtures still
setting only legacy credentials, although current routing consumes the unified
gateway. Set a synthetic unified gateway key/base/model in those three fixtures;
do not add a production legacy-credential fallback. The unsupported-model test
must explicitly enable its mocked remote decision to test that reason rather than
being masked by CI's default-off switch. Persist this suite in the mock CI job.

The background-health fixture once failed at the exact 60-second boundary and
passed on immediate rerun. Independent float arithmetic reproduced elapsed values
just below 60 when arbitrary wall/monotonic fractions cross an exponent boundary.
Both synthetic-clock fixtures now use exact integer-valued starting clocks. The
production stability threshold and clock-jump protection are unchanged.

### Bounded cross-process HTTP evidence

Two scenarios passed against the exact Bridge counterpart above: normal receipt,
and execution-unknown followed by coordinator restart and a later receipt for the
same remote attempt. Alchemy's actual NativeBridgeService/BridgeClient communicated
with a separate real Bridge HTTP/domain process. NativeGatewayDouble and fake
pixels were explicit fixtures, not actual host authentication/Brain/shared review
or live CLI recovery. Each scenario planned and registered once; repeated polling
did not duplicate registration; accepted ACK replay was idempotent. Both remained
nonformal and reported no charge in the synthetic gateway. All services stopped.

## CI follow-up: legacy review-card fixture

The current-main Doc341 renderer requires explicit final-attempt lineage or a
current-job `review_output_ids` binding before showing a review-only image. The
legacy Doc263 quality-failure fixture supplied only `hidden_output_ids`, which
withholds delivery but does not establish current-final review identity. CI
correctly excluded that unbound image. Preserve the runtime gate: update the
fixture to first assert exclusion without lineage, then supply the matching
review ID and assert exactly one review-only card and no formal-delivery action.
This is a browser contract fixture correction, not an output visibility bypass.

Local follow-up validation: Doc341 Node projection tests 2/2 passed; all 9 Doc263
browser cases collected successfully. Local Chromium download from the official
Playwright CDN returned a truncated/non-ZIP archive, so rendered browser execution
is not claimed locally. The exact new-head GitHub browser job remains the acceptance
source for this fixture change. No production renderer code was changed.
