# RB19: full-product Bridge-primary implementation and acceptance

Date: 2026-10-24. Alchemy baseline: a15ff3e979363e83f678a99bf0ba9dfd33e15bf1.
Companion: meta-xucong/alchemy-render-bridge PR #1, branch
codex/bridge-progress-20261023, fff524484fa98845033e21f2d24664a361d09efe.
This is code and synthetic validation, not deployment or actual-account acceptance.
No main branch or companion PR is merged by this milestone.

## Implemented scope

Each product evaluates the primary route at its real image-transport boundary.
V1 and Lab retain planning/assets/billing preflight and final publication; V2
retains its own request/store/template/claim/review authority without V1 imports;
V3 retains canonical materialization, candidate checkpoints, shared review and
slots. Existing explicit mocks, planning-only and explicit MCP materialization
are not intercepted. Normal product images retain normal review/delivery and
pricing policy, unlike the older review-only development trial.

The neutral journal freezes each owner/product/unit's semantic identity before
transport. Capability/health rejection before submission and a first typed
queue_capacity/bridge_draining response permit the existing API provider. Any
ambiguous create, admitted task, running/unknown execution or receipt remains
Bridge-owned. An origin lookup 404 after uncertain create never proves rejection.
Existing queued work cannot migrate because of queue time or later capacity.

Bridge alone atomically enforces the configurable shared queue (default10).
Its depth is diagnostic, not a client-side admission permit. Per-product journals
are isolated. Original receipt bytes/hash/decoded dimensions are preserved; V3
explicitly bypasses its ordinary aspect-ratio crop for Bridge originals. Unsupported
hard controls are never deleted or disguised as prompt instructions.

Product workers recover the exact frozen job/unit instead of replanning, changing
IDs or consuming fresh-generation retry budgets. Multi-output partial checkpoints
are retained privately until product publication. Cancellation is owner-scoped,
blocks further units, and cannot turn uncertain work into a second provider call.
Once final billing begins, a durable transaction boundary freezes the exact debit
identity and refuses cancellation rather than hiding already-paid images. Existing
idempotency keys, cached pixels and original debit arguments survive response loss
and configuration changes; no refund or pricing-policy changes are introduced.

After durable registration, an immutable ACK intent is saved before the HTTP call.
A bounded host maintenance loop retries only ACK/cancel intents after restart,
including while new admission is disabled. It never renders, imports or creates a
task. Public route evidence excludes private frozen requests, paths and checkpoints.

## Test and audit evidence

Final local selections on the integrated implementation:
- 508 passed: Bridge compatibility, neutral core, administrator, actual V1/Lab/V3
  entries and selected original product/export paths (342 existing deprecation warnings).
- 245 passed: current-main Brain, reference-plan, continuity and review seams.
- 828 passed: complete standalone V2 suite, against the neutral package without
  exposing V1 source imports through PYTHONPATH.
- 41 passed: Node V3 frontend contract suites. JavaScript syntax, shell syntax,
  dependency consistency and whitespace checks passed.
- Companion Bridge complete locked offline suite:259 passed. Additional25 rounds
  of9-to10 concurrent admission each accepted exactly one request; full-queue
  replay and reopened storage retained the original handle.

Independent audits reproduced and repaired actual defects: stale concurrent poll
overwriting receipt metadata, omitted receipt execution bindings, partial outputs
published before billing, late cancellation creating another batch unit, cancellation
hiding paid results, mutable debit identity during recovery, and post-terminal ACK
loss without background reconciliation. Focused deterministic regressions cover the
specific observations; thresholds, review gates and capability controls were not
weakened to make tests pass.

The reusable scripts/verify_render_bridge_primary_contract.py runs against the
pinned companion's actual HTTP handlers/domain via ASGI with a synthetic executor.
It verifies queue competition, full replay, original receipt/hash/bytes/dimensions,
ACK, lost create after actual admission, restart, health affecting only new work,
and same-task cancellation. Additional independent simulations cover late admission
with cancellation and lost ACK followed by maintenance. These are real code paths
with synthetic pixels, not real Codex/paid-provider or network/Windows acceptance.

CI runs core contracts on Linux/Windows, product entry suites, the pinned companion
handler check, browser tests and the original capacity/retention workflow. Exact-head
CI must be checked in the new PR; local success is not a claim that CI already passed.
The historical Doc203 MCP suite's7 failures were independently reproduced unchanged
on baseline a15ff3e (66passed/7failed). They are not attributed to this implementation,
not silently marked fixed, and were not used to relax MCP production behavior.

## Important capability limits

Current codex-image advertises quality=auto, original PNG/JPEG postconditions,
and original_dimensions_recorded. It does not promise native low/medium/high,
exact requested dimensions, transparent background, masks, compression, high input
fidelity or strong identity/multi-reference fusion. These requests record
bridge_capability_unsupported and use their original provider without modification.

V2/Lab currently synthesize high quality by default and V3 medium; those defaults
therefore correctly fall back. The implementation does NOT redefine them as advisory
or force them to auto. Compatible auto requests exercise Bridge-first behavior.
V1's schema defaults to auto, but its final frozen plan remains authoritative.
Execution profile and underlying model are separate: the Bridge receipt does not
report an actual renderer model, so provenance explicitly says not_reported instead
of inventing a Codex model name. API-provider internal retry policy is unchanged;
this journal fences adapter dispatch, not a claim of exactly one upstream HTTP call.

## Local acceptance handoff

1. Preserve local changes, databases and existing data. Use the new feature branch
   and the exact companion commit above, not the old5b6c/59cbd handoff pins.
2. Install each product's normal environment plus the independent neutral package
   where required. V2 Windows/Linux setup now installs it; the V1 container copies it.
3. Set identical absolute ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG and
   ALCHEMY_RENDER_BRIDGE_PRIMARY_STATE_ROOT paths for all local processes. Use durable
   paths/mounts outside the checkout and product-specific ledger subdirectories.
   Bridge URL, source token and workspace must agree; do not paste secrets into reports.
4. Existing administrator controls govern the route. Enable codex-image only after
   local exact-version/tool acceptance. native_enabled controls only the older trial.
   Fake-only configuration never silently enables real product generation.
5. With authorized cost/material scope, validate compatible auto requests in each
   real product; hard-capability fallback; queue full/replay; service failure;
   restart/unknown/cancel; same original bytes and no duplicate output/debit. Check
   the ordinary review/slot and billing results, not just a Bridge artifacts_ready.
6. For0.163.0, account-health probing is a separate opt-in capability.0.157.1 with
   account probing returns unknown; executable support is not account/tool acceptance.
7. Do not delete unknown journals, clear latches, re-encode originals, or invoke a
   second provider to turn an ambiguous test green. Restore/reconcile the original
   task. Report exact SHA, route reason, original hash/dimensions, safe output/task
   identities and pass/fail/not-run stages without credentials or private paths.

Real Windows/Codex/account/provider review, actual image quality and live billing
remain local acceptance. The earlier local CLI-layer receipt documented in RB12 is
useful history but does not certify this full-product routing implementation.
