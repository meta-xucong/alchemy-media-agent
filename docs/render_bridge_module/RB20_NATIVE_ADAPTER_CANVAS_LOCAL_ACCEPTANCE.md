# RB20: native-default adapter and prompt-canvas local acceptance

## Status and sources

This candidate is **code/offline ready for local acceptance**, not certified live
Codex, Windows, image-quality or billing acceptance. Do not merge or deploy it
merely because unit tests or CI pass.

- Alchemy: PR #39, `codex/v2-codex-cli-normalization`, stacked on PR #38.
- Bridge: PR #2, `codex/codex-cli-param-adapter`, stacked on PR #1.
- Paired Bridge candidate: `80f155d4e1217d1f7f9304bfb9154d16071ec67d`.
- Record the exact Alchemy PR head from the accompanying handoff and verify it
  after fetching. Do not substitute main or an older local checkout.
- [RB13](RB13_FULL_PRODUCT_PRIMARY_ROUTING_CONTRACT.md) is the current parameter,
  canvas and recovery contract. RB19's original capability-limit section describes
  the pre-adapter milestone, not current optional-control behavior.

## Changes that need acceptance

1. V1, V2, V3 and Lab new units opt into Codex native defaults. Optional API-only
   controls no longer force API fallback. Required masks, postprocessing or
   unverified conditioning remain capability gates rather than being dropped.
2. Historical tasks preserve their frozen identities and contracts. Versioned
   and legacy capability descriptors coexist; no ledger deletion or regeneration
   is a migration strategy.
3. Explicit current-prompt canvas takes precedence over stale manual/template
   controls. Supported dimensions/ratios remain exact; otherwise the selected
   renderer's native default is used, not a different claimed aspect ratio.
4. V1 revisions use the current feedback's canvas, not the historical prompt.
   V2 v13 planning cache avoids decisions made under the old precedence rule.
   V3 freezes synchronized effective canvas options and avoids stale auto-crop
   requirements when the effective canvas is native auto.
5. V2 fallback queues respect configuration, terminal failures stop propagation,
   lost claims prevent subsequent dispatch, and progress counts actual attempts.
   Backup request budgets are cumulative; process cleanup has bounded waits.

## A. Fetch without damaging local work

Read repository AGENTS.md. First record git status, HEAD and remotes in both
existing local repositories. Preserve all local modifications, runtime data,
credentials, originals and unknown-task evidence. Do not reset, clean, force-push
or overwrite an active worktree. Fetch the named branches and use separate test
worktrees at the exact handoff commits when the existing checkout is dirty.

Keep existing data outside checkout paths. Use separate test data/configuration
copies when appropriate; never copy production secrets into the report. Do not
upgrade a running process while admitted work is unresolved. Identify which
processes are actually using which checkout before a controlled restart.

## B. Offline and configuration checks first

- Use each repository's declared dependencies and test instructions. Install the
  updated `render_bridge_primary` distribution into the independent V2 environment;
  its wheel must include `codex_adapter.py`. Do not add V1 to V2's import path.
- Run the new adapter, canvas, failover and historical-recovery tests. The Alchemy
  workflow lists the current selections, including `test_prompt_canvas_authority`
  and the provider-specific `test_*_exact_canvas` files.
- Run Bridge's complete contract suite and schema-export check. Run Alchemy's
  paired ASGI script against this Bridge checkout with
  `--require-codex-adapter`; this is synthetic, not live generation.
- Read actual Bridge/Agent configuration and the installed Codex version. Only
  the reviewed exact CLI versions 0.157.1/0.163.0 are accepted. Prefer an already
  available reviewed 0.163.0 for the transparency scenario; do not silently
  install or accept another version.
- The doctor can inspect configuration/version/help. A successful doctor result,
  login status or an operator flag is not proof that image generation works.
  Never set verification flags merely to make the test pass.
- Check real engine/database, worker, one dispatcher, Agent, source workspace
  and profile readiness using the existing local setup instructions. An SDK
  installation is not a running engine. All Alchemy processes must agree on the
  absolute primary control/state paths, while Bridge keeps independent storage.
- Verify capability responses preserve the legacy outer contract and advertise
  `parameter_contract.codex_adapter.values` plus its nested native options.
  New requests must carry `parameters.codex_adapter=codex_cli_imagegen_v1`.

## C. Live acceptance is a separate, bounded stage

Before a real call, confirm authorized test accounts, non-sensitive materials,
image count and cost ceiling, including possible ordinary API fallback costs.
Do not assume this document grants paid-call authority. Use the existing login;
do not expose credentials or create/expand persistent access without approval.

Suggested minimum after approval: one image through each product and one V1
revision, with count=1 and the normal authenticated product entrypoints. Stop on
the first unexplained failure or unexpected API route. Do not repeat a paid job
just to obtain a cleaner report.

| Entry | Input conflict | Required transport evidence |
| --- | --- | --- |
| V1 | prompt says 16:9 portrait; old UI size is 1024x1536 | effective canvas must not become 2:3; original prompt retained |
| V2 | prompt says 16:9; old size/aspect fields conflict | no contradictory 2:3 control section; new cache policy; actual route recorded |
| V3 | Brain explicit 16:9 versus typed 1024x1536 | synchronized frozen provider options and final hints; no later typed override |
| Lab | prompt says 16:9 versus existing variant canvas | no 16:9-to-3:2 approximation; optional high quality uses native adaptation |
| V1 revision | prior portrait image; current feedback says 16:9 | current feedback controls new canvas; source bytes and original record unchanged |

Codex CLI has no structured size argument: `size=auto` is expected. Inspect the
actual final image-tool prompt for the intended 16:9 and absence of a conflicting
derived 2:3 instruction. Measure returned original dimensions separately. A
16:9 prompt is not proof of a 16:9 image, and a correctly routed result that
violates the request must be reported as an output-acceptance failure.

Reference/transparency scenarios require separately approved calls if not covered
by that budget. Inspect observable imageGeneration/tool evidence for explicit
reference paths and, on 0.163.0, transparency; inspect actual alpha and reference
use. Developer instructions alone are not proof of parameter obedience. 0.157.1
has no transparency option, so do not certify transparent output on that version.

For ordinary API-path acceptance, apply each configured model/transport contract:
GPT Image 2 supports 1536x864; Seedream4 has different size constraints; Gemini
uses its declared ratio set. Third-party gateway acceptance is a separate fact
from official model documentation. Do not change endpoints/protocols during
this test to disguise an incompatible route.

## D. Recovery and failure evidence

Use isolated synthetic fixtures for destructive fault injection. Do not kill a
paid in-flight job, erase unknown journals, clear start latches, switch its origin
or submit a second provider while execution is uncertain. A cancellation request
does not prove an already-dispatched remote operation stopped.

Correlate a failure by time and product run/job/unit, then distinguish planning,
Bridge preflight, accepted/unknown execution, artifact collection, product review,
registration and billing. For V2, preserve cache status, effective model queue,
stage events, actual attempt counts and safe error codes. No visible Claude call
can be normal on cache/recovery paths; an empty trace is not enough to infer cause.

## E. Return one concise acceptance report

Include exact two repository SHAs, Windows and CLI versions, process/checkouts,
tests passed/failed/not run, per-product route and safe task/attempt/receipt IDs,
requested/sent/decoded canvas, original hashes and bytes, observed tool evidence,
review/delivery status and confirmed debit count. Distinguish Bridge success from
API fallback. Redact tokens, credentials, full private prompts, local account
paths and reference-image/base64 contents.

Cloud evidence includes 331 cross-product tests, 172 independent V2 selection
tests, 266 Bridge tests and mixed-version ASGI checks; counts can overlap. Seven
broader failures were also reproduced on the untouched Alchemy b90f6237 baseline:
one V1 backup-LLM test, three V2 QR cases, one V2 critic-availability test, and two
V3 creative-exploration director count cases. These are not claimed fixed or green.

Do not report complete usability until the authorized live product flows,
image/tool behavior, recovery, review and billing gates actually pass.
