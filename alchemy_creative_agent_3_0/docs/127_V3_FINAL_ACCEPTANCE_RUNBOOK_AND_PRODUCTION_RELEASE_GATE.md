# Doc127 — V3 Final Acceptance Runbook And Production Release Gate

Status: active, single operational guide for the remaining V3 acceptance
campaign. This document turns the existing architecture and module contracts
into one ordered, reproducible acceptance program. It does not replace their
implementation authority.

Current integration baseline when this guide was written:
`origin/main@70e8aad8cac01df88dd4a498d8aaacc398c3720c`.

## 1. Purpose And Non-Goals

V3 has completed a substantial amount of contract, runtime, isolation, and
offline-regression work. A green test suite is necessary, but it cannot prove
that a real reference image reaches the renderer, that the real Central Brain
made the creative direction, that real pixels received a certifying review, or
that the browser presents the final state honestly.

This runbook closes that remaining gap in one controlled campaign. Its output
is an evidence-backed release decision, not another collection of prompt
experiments.

The target production path is:

```text
protected user intent + authorized reference facts
-> remote Central Brain (creative direction where required)
-> template structural contract and frozen shared execution envelope
-> GPT Image 2 complete-image generation or edit
-> shared vision_model/hybrid review
-> shared bounded retry and append-only history
-> only the certified final winner is delivered
```

It is expressly **not** a plan to restore local fonts, OCR, canvas/HTML/SVG
overlays, fixed visual recipes, static marketplace suites, template-private
providers, or manual prompt piling. A test fixture may describe a user need;
it must not encode a new vertical-specific creative recipe in the shared
runtime.

## 2. Authority And Historical-Document Routing

Use the following authority map whenever two older documents appear to demand
different behaviour.

| Topic | Forward authority | Operational interpretation |
| --- | --- | --- |
| Provider-native complete images and requested in-image copy | Doc111 | GPT Image 2 creates the complete image. Do not certify or revive `CopyRenderPlan`, local font, OCR, deterministic overlay, coordinate, safe-area, or canvas paths. Text fidelity is assessed from final pixels and human review only. |
| Frozen runtime, template ownership, exact count, constraint resolution | Doc113 | The frozen envelope and resolved constraint ledger are the only execution truth. General owns no E-Commerce deliverable plan. |
| apparel-on-person and young-person realism | Doc114 and Doc124 | These are cross-domain Human Realism/reference regressions, not a child or kidswear module. Test explicit young-person apparel alongside adults, portraits, non-person products, and different photographic moods. |
| real reference admission and provider failures | Doc117 and Doc119 | Reference rejection must be attributable before it is labelled as such. No pixels means no review, retry, or delivery. Gateway-managed failover owns a single outer materialization request. |
| review, retry, public delivery truth | Doc118, Doc121, Doc122, and Doc123 | Only verified `vision_model`/`hybrid` pass or warning can certify automatic delivery. `metadata_only`, local-only, manual confirmation, missing pixels, or unresolved review are not a pass. |
| General project continuation/browser behavior | Doc104, Doc108, and Doc109 | The General browser path remains scenario-neutral and is independently observable after refresh/reopen. |
| E-Commerce | E17–E19 and Doc104/105 continuation portions | The user explicitly selects E-Commerce; remote Brain makes N whole-image directions; shared runtime executes them. E19 is the real-provider evidence record. |
| Photography | Doc106, Doc112, Doc115, Doc116, P10, and P11 | Photography has remote-Brain creative direction, shared real-pixel certification, and template-owned structural roles only. |
| Codex native planner | Doc126 | It is General-only, conversation-only planning. It cannot generate certified files, import artefacts, or satisfy any Web/Provider/Gate C/Gate D/P10 gate. |

### 2.1 Explicitly superseded historical material

Doc107 and Doc110's deterministic text-pixel proposal, and the deterministic
text/OCR paragraphs in the historical portion of Doc105, are retained only so
old records can be read. They are **not forward acceptance requirements** and
must not be implemented or enabled. Doc111 supersedes them for new work.

Doc104's Gate C/D history is useful evidence, but its older local-heuristic or
deterministic-text references cannot certify the current release. The browser
continuation finding may be reused only after the release-confirmation check in
this runbook. Doc79 and other older evaluation logs are archival context, not
release authority.

## 3. Current Starting Position

The following table prevents a historical success from being mistaken for a
current release approval.

| Area | What is presently established | What remains before production claim |
| --- | --- | --- |
| Shared runtime and isolation | Docs113–124 are integrated with focused and full offline regressions. `origin/main` is the code baseline above. | Re-run the release preflight and retain real-run provenance on this exact or later frozen commit. |
| General Gate D | Doc104/109 records a successful controlled General continuation/reopen path. | Run the concise browser release-confirmation if the deployed UI, API, lifecycle, or runtime commit differs; retain current evidence. |
| Shared real-reference/human chain | A controlled branch report describes a hybrid-reviewed young-person apparel result, but its job/output provenance is not durable in the present service. | Run the Doc114 cross-domain matrix below on the controlled current deployment. |
| E-Commerce Gate C | E19 records one bounded, authorized, hybrid-reviewed historical case. | Re-certify on the frozen release build, then complete exact-count, browser, human commercial review, and failure evidence for Gate D. |
| Photography P10 | A controlled single-image front-end chain has been observed; it did not by itself prove every real-pixel certification condition or a complete three-role set. | Complete P10's four-scene, two-input-mode, single/professional-set matrix with visible review provenance. |
| Codex native planner | Doc126 planning-only N1 contract and tests are integrated. | No production acceptance is pending from it. It stays excluded from image delivery gates. |

Until Sections 5–11 are complete, the E-Commerce and Photography production
flags stay off. General may remain available only under its existing controlled
deployment policy; it is not evidence that specialist templates are ready.

## 4. Evidence, Roles, And Safety Rules

### 4.1 Acceptance roles

| Role | Responsibility |
| --- | --- |
| Mainline operator | freezes commit/configuration, runs the shared preflight, preserves evidence, classifies faults, and approves no production flag alone. |
| Material owner | supplies a written rights/source/watermark statement and the intended factual constraints for every reference image. |
| Template owner | observes the template-specific browser workflow and signs the visual/business result; may not bypass shared generation/review/retry. |
| Human reviewer | reviews final pixels against the applicable rubric and records a clear accept, reject, or hold decision. |

### 4.2 Restricted evidence package

Create one external acceptance folder for the whole campaign, for example:

```text
ACPT-YYYYMMDD-v3-release-<short-commit>/
  00-environment.json
  01-material-authority.json
  02-automated-preflight.txt
  runs/<acceptance-run-id>/manifest.json
  runs/<acceptance-run-id>/review.md
  runs/<acceptance-run-id>/provenance-redacted.json
  browser/<acceptance-run-id>/steps-and-screenshots/
  release-decision.md
```

Keep source images, generated images, browser screenshots, provider request or
response bodies, access tokens, endpoint details, and raw personal data out of
Git. The repository may contain only this runbook, tests, non-sensitive IDs,
and a short status conclusion. Store a redacted evidence reference, content
hash, job ID, output ID, and reviewer decision for each run.

Every `manifest.json` must contain at least:

```text
acceptance_run_id, timestamp/timezone, commit, deployment, config_fingerprint,
template/scenario, requested_count/size, material_rights_reference,
user_request_and_facts, frozen_plan_or_envelope_id,
brain_provider/model/llm_used/fallback_used/plan_count,
provider/model/operation_count, source-asset bindings,
candidate/output IDs and hashes, review mode/verdict/verification/confidence,
retry history, public-delivery state, refresh/reopen result, human decision.
```

Do not copy secrets into a manifest. A configuration fingerprint says whether
the relevant switches were enabled, not their values or credentials.

### 4.3 Universal terminal-state truth

| Observed result | Required public/result state | May count as acceptance pass? |
| --- | --- | --- |
| Real pixels + verified `vision_model`/`hybrid` `pass` or `warning` + final winner | `ready` | Yes, after applicable human review. |
| Real pixels + verified retryable failure | retry only through the shared bounded path; superseded candidate remains history | Only if a later final winner reaches the row above. |
| `manual_confirmation_required` | `withheld_manual_confirmation` and visible in history/UI | No automatic pass or delivery. |
| `metadata_only`, local-only, missing/unknown review | `not_evaluated` or withheld | No. |
| No pixels, provider rejected, timeout, invalid request, or brain failure | structured `blocked`/`failed`; no candidate/delivery | No. |

`content_policy_violation` is a policy block, not a signal to rewrite the
subject, age, reference, or model to evade a policy. An unattributed 4xx stays
`image_edit_invalid_request_unattributed` until structured evidence proves
that the reference input was rejected. A no-pixel request never enters visual
review or retry.

For a specialized frozen role, a successful shared retry must also rebind that
role's current winner to the retry candidate before certification is projected.
The superseded candidate stays in append-only history. A role may never show a
withheld certification while a separate generic delivery surface reports the
same retry output as ready; that is a runtime-truth defect, not a successful
acceptance result.

## 5. Phase 0 — Freeze The Controlled Acceptance Environment

Run this phase once before spending real provider budget. Stop immediately if
any item fails.

1. Deploy a clean controlled instance at the frozen `origin/main` commit. Do
   not use an old long-running process merely because its `.env` looks right.
2. Record the commit, deployment identity, time zone, database/storage
   namespace, and a redacted config fingerprint. The process must have:
   remote Central Brain reachable where the selected template requires it;
   GPT Image 2 selected as the production renderer; gateway-managed failover
   configured; actual effective client timeout sufficient for the gateway
   budget; and `V3_VISION_INSPECTION_ENABLED` (or its active equivalent) able
   to produce `vision_model` or `hybrid` review.
3. Keep E-Commerce and Photography production flags off in every production
   environment. Enable a specialist flag only in this named controlled
   instance and record it. Codex native planner is not enabled as a renderer.
4. Build the material register. Every reference has a rights statement,
   source/owner, watermark check, allowed evaluation scope, asset ID, and
   intended role. Desktop examples or historical files without a sidecar are
   not silently promoted to fixtures.
5. Run and attach:

```powershell
python -m pytest alchemy_creative_agent_3_0/tests -q
python -m compileall -q alchemy_creative_agent_3_0/app alchemy_creative_agent_3_0/tests
node --check src_skeleton/app/static/app.js
git diff --check
python -m pytest tests/test_doc126_codex_native_imagegen.py -q
```

The last test checks the planning-only plugin contract, not image quality. If
the first four checks are not run from the actual frozen source tree, record
why and do not call the campaign release-ready.

## 6. Phase 1 — Shared Chain Smoke And Failure Honesty

This phase proves the governed path before vertical acceptance begins.

| Case | Required observation |
| --- | --- |
| General T2I smoke | One explicit General request obtains a frozen envelope, the expected Brain provenance when required, one GPT Image 2 operation, and a certifying final review. It contains no E-Commerce/Photography vocabulary. |
| General reference/edit smoke | One authorized ordinary reference follows admission -> native provider input -> real pixels -> review -> final/withheld truth. It must not duplicate the source input. |
| Brain fail-closed | A controlled unavailable/malformed/incorrect-count Brain condition blocks before provider execution for a template that requires remote Brain. No local-rule image appears. |
| No-pixel/provider-failure truth | Use a safe controlled fault injection or an observed real terminal failure; do not manufacture a policy violation. Prove structured classification, zero final candidate, no review/retry/delivery, and correct state after refresh. |
| Review withholding | Exercise `metadata_only` or manual-confirmation using a deterministic test seam, not a fake production pass. Prove it is visible and cannot be counted as certified delivery. |

When a specialized template executes independent frozen roles, the same
no-pixel outcome must also be visible per role as a safe operational tuple:
operation (`image_generate` or `image_edit`), reference count, outer-request
count, classified failure code, `blocked` state, and the sanitized runtime
budget (`gateway_managed_failover`, configured gateway budget, outer timeout,
and outer-attempt cap when known). This evidence distinguishes a gateway-owned
terminal timeout from a false local lifecycle claim without exposing raw
Provider messages, endpoint details, credentials, prompts, account/line
identifiers, or candidate identifiers. A generic role exception alone is not
enough evidence for acceptance diagnosis.

The in-process Project worker is not restart-resumable. On a singleton V3
runtime restart, a persisted `generating` or `finalizing` Job whose recorded
worker runtime differs from the current runtime must become terminal
`background_generation_process_restarted`: `automatic_replay=false`, Provider
outcome `unknown`, no fabricated review or delivery, and one append-only
Project timeline record. A fresh acceptance operation requires a new Job and
new evidence row; the interrupted Job is never resumed or silently replayed.

The provider smoke is not allowed to become a separate retry router. One
logical output becomes one gateway-managed outer materialization operation;
the gateway alone can choose an internal healthy upstream. SDK/client retries
are disabled or recorded as zero. If the effective client timeout contradicts
the recorded timeout, fix the process configuration and restart before
continuing.

## 7. Phase 2 — General Browser Release-Confirmation (Gate D)

Doc104/109 records an earlier pass. Re-run the following compact sequence when
the controlled deployment changed after that record; otherwise attach that
record and confirm the current code paths are unchanged.

```text
new General project
-> generate a real reviewed final image
-> select its canonical final output
-> continue in the same visual direction
-> add one authorized reference image
-> mark one rejected direction
-> continue after review/retry settlement
-> refresh and reopen the project
```

Pass criteria:

- the selected canonical output and the intended reference binding are each
  present exactly once in the continuation provider input;
- the rejected direction persists and is not silently reused;
- only final winners count as ordinary project images;
- the UI exposes terminal success, blocked, or held state without an endless
  spinner, misleading empty result, or hidden review state;
- project/job provenance, candidate history, review/retry state, and result
  survive refresh/reopen; and
- General remains General: it does not create platform packages, slots,
  specialist continuation controls, or vertical creative context.

Capture the exact browser URL only in restricted evidence if it exposes a
private host. Capture screenshots before and after refresh plus the matching
redacted job/project query.

## 8. Phase 3 — Shared Real-Reference And Human-Realism Matrix (Doc114/117/124)

Use six authorized cases. This is deliberately cross-domain so a regression
fixture cannot turn into a child or apparel sub-system. Each case needs real
pixels, `vision_model`/`hybrid` certification, human review, and the same
evidence fields from Section 4.

| ID | Authorized input and request | Required assertions |
| --- | --- | --- |
| R1 | explicit young person wearing a distinctive garment; age-appropriate ordinary setting | `person`/`visible_person` evidence and shared `human_realism` are frozen; age, clothing structure, anatomy, lighting, and integration are natural; no adultification, no policy bypass. |
| R2 | adult product-on-person with product reference | product truth and person/human-realism facts coexist without E-Commerce recipe leakage. |
| R3 | same-person portrait reference with prompt-owned hair/wardrobe/scene | identity-critical geometry persists; prompt-owned channels remain prompt-owned under Doc93. |
| R4 | non-person product reference | Human Realism remains inactive; product/reference path stays intact. |
| R5 | bright/high-key real-person image | natural skin/specularity, anatomy, lighting, and scene integration without plastic or beautification artefacts. |
| R6 | moody/low-key/cinematic real-person image | realism improves without forcing high-key commercial skin or flattening the requested mood. |

For R1 and R2, any reference/edit 4xx must be classified from evidence. Do not
change a young subject into an adult, replace the user reference with text, or
switch to another model to force a pass. If a policy block occurs, record it
as a blocked provider result and continue only with another independently
authorized, policy-compliant case if the material owner chooses to supply one.

Human review is factual, not a request to add dozens of rigid prompt clauses:
age appropriateness, believable facial/body/hand proportions, natural
expression and skin texture, clothing fit/folds, coherent light/shadow,
foreground/background integration, preserved reference truth, and absence of
unrequested text, logo, watermark, collage, or anatomy defects. A verified
review may demand the existing bounded retry; it must never create a private
young-person or apparel prompt recipe.

## 9. Phase 4 — E-Commerce Gate C And Gate D

Run this phase only after Sections 5–8 pass. The operator must explicitly
select `ecommerce_template`; a General phrase such as "Amazon product" is not
an E-Commerce test.

### 9.1 Gate C: controlled real product chain

Use a material-register product with factual product truth, an explicit seller
request, and versioned platform evidence. Run one 1-image case on the current
frozen release. It passes only if all of the following are retained in E19's
evidence record:

```text
llm_used=true; fallback_used=false; exactly N=1 natural-language Brain plan;
provider-native product reference input; one GPT Image 2 final pixel output;
vision_model/hybrid verified final verdict; bounded shared retry semantics;
append-only history; one ordinary final delivery after refresh.
```

The historical one-case E19 result is useful comparison material, but it is
not a substitute for this current-build result. Inspect visible labels/text as
pixels: if they are materially wrong, use only the shared provider-native
bounded redraw or withhold the image. Never repair it with local OCR/font or
overlay machinery.

### 9.2 Gate D: exact-count, UI, and human commercial acceptance

With authorized material, perform four independent requests for `N=1,2,4,7`.
For each request:

1. the Brain emits exactly N whole-image natural-language directions;
2. the TemplateDeliverablePlan/envelope and provider operations retain exactly
   N, or an explicitly declared provider/platform capacity limit blocks before
   generation—there is no silent truncation;
3. every output role uses shared generation, review, bounded retry, winner
   selection, append-only history, and one final winner per requested output;
4. a refresh/reopen shows N final deliveries or a diagnosable held/blocked
   state per individual output; and
5. the reviewer signs product truth, request relevance, commercial usability,
   final-pixel condition, and any requested text/claim accuracy.

Also attach automated negative evidence for unavailable/fallback/malformed or
wrong-count Brain failures, General/Photography Brain isolation, historical
recipe/slot/overlay non-replay, capacity block behavior, and UI truth. The UI
must not show a pseudo-enabled slot redo button. If Doc105 continuation is
available, test it only as its append-only child job contract; it cannot
overwrite the parent or become a private retry path.

E-Commerce is production-ready only after both Gate C and Gate D are accepted
in this campaign. A single pretty image, a mock, a metadata record, or a human
assertion without final-pixel provenance is insufficient.

## 10. Phase 5 — Photography P10

Run P10 only after the shared matrix passes and only in the controlled instance
with the Photography production flag enabled. Production remains disabled.

For each of the four scene classes—portrait, landscape, still life, and
animal—run both text-to-image and authorized reference-reshoot paths. For each
input mode, run both `single_hero` and `professional_set`.

| Mode | Required outcome |
| --- | --- |
| `single_hero` | One remote-Brain-created natural-language direction, one role, shared generation/review/retry, and one certified final winner. |
| `professional_set` | Exactly `session_hero`, `environmental_context`, and `detail_or_moment` remain structural lineage roles. Remote Brain writes the concrete direction for each. Each role has its own terminal outcome and exactly one certified final winner, so the project exposes three—not one silently downgraded—final outputs. |

This yields sixteen real cases (4 scene classes × T2I/reference-reshoot ×
single/professional). Run sequentially within the same campaign; do not launch
all at once and confuse quota/router behavior with template quality.

Additional mandatory P10 checks:

- named photographer profile requires explicit user reconfirmation of the
  same ID, version, and checksum for a continuation; mismatch blocks;
- an animal/pet identity reference uses the shared high-fidelity nonhuman
  identity capability; missing/unsupported input blocks instead of degrading
  to text;
- every final result exposes review mode, verification state, certification
  status, and held/manual status in job/project history and the result page;
- `metadata_only` or `manual_confirmation_required` cannot appear as a P10
  success, automatic delivery, or production-gate statistic; and
- no photography private provider, reviewer, retry, selector, General suite,
  or E-Commerce semantic leaks into the execution.

The P10 reviewer additionally checks that the photos are coherent as a
session, that reference truth/profile binding remains fixed, and that a
professional-set role is meaningfully distinct without relying on prewritten
camera, pose, lighting, crop, or scene recipes.

## 11. Phase 6 — Cross-Template, Failure, And Browser Closure

Before release, execute the following final audit against the same commit.

| Check | Required result |
| --- | --- |
| Template isolation | General Brain requests exclude E-Commerce creative context/platform/slot terms and Photography roles. Photography/E-Commerce requests do not fall back into General on failure. |
| Frozen plan truth | Provider, review, retry, and public result consume the frozen envelope/ledger; a plan/environment mismatch blocks rather than falls back to legacy/shadow mode. |
| Gateway ownership | One logical materialization operation produces no V3/SDK duplicate outer request. Internal gateway routing/failover is bounded and traceable without leaking account/provider internals to users. |
| Process lifecycle | `job_created`, generating, generated/blocked/failed/withheld, project aggregation, restart, polling, and refresh all reach an honest terminal state. No background job can remain indefinitely in a false generating state. |
| Browser rendering | reference thumbnails load; existing final images rehydrate after refresh; blocked/held/failed results are distinguishable from empty output; no stale spinner or duplicated result card remains. |
| Legacy compatibility | old projects/jobs can be read. Old recipe/slot/overlay/text-plan aliases cannot enter new Brain/provider prompts, execution envelopes, or delivery logic. |
| Codex native planner boundary | plugin remains opt-in planning only, has no renderer/API key/artifact import/review/retry/delivery path, and cannot alter Web acceptance results. |

If a check detects a defect, classify it rather than masking it:

1. **Contract/runtime defect:** fix shared code, add a regression test, deploy
   a new commit, and repeat every affected phase.
2. **Provider terminal failure with no pixels:** retain redacted upstream
   timing/classification, notify the upstream owner, and repeat only after the
   route is healthy. Do not add a second V3 retry layer.
3. **Verified retryable visual defect:** use the existing bounded shared retry;
   retain the rejected candidate in history and judge only the later final.
4. **Manual/metadata-only result:** repair review availability/projection and
   rerun; it cannot be upgraded by a human assertion alone.
5. **Material/rights problem:** stop the case until the material owner supplies
   a compliant reference. Do not substitute a scraped/unknown example.
6. **Policy block:** preserve the user intent and recorded block. Do not evade
   it by changing age, removing reference truth, or routing around policy.

## 12. Release Decision And Production Enablement

The mainline operator creates `release-decision.md` only after every required
row below is evidenced on the frozen release or has been re-run after any
relevant change.

| Release condition | Required decision |
| --- | --- |
| Phase 0 automated preflight and configuration | pass |
| Phase 1 shared chain and failure honesty | pass |
| General Gate D release-confirmation | pass or documented unchanged historical pass with code-path comparison |
| Doc114/117/124 six-case real-reference matrix | pass, or each non-pass clearly scoped to a provider policy/material block and not hidden as quality success |
| E-Commerce Gate C + Gate D | both pass before E-Commerce production flag may be enabled |
| Photography P10 16-case matrix | pass before Photography production flag may be enabled |
| Cross-template/browser/lifecycle closure | pass |
| Security/evidence audit | no secrets or private media committed; all restricted evidence references resolve |
| Owners' human signoff | material owner and template reviewer sign the applicable rows; mainline operator records the final decision |

There are three possible conclusions:

```text
accepted for controlled template production:
  all applicable rows pass; enable only the corresponding template gate.

accepted foundation, specialist gate held:
  shared/General rows pass, but E-Commerce or Photography lacks its own matrix;
  keep that specialist production flag off.

blocked:
  any missing real provenance, non-certifying review, failed lifecycle,
  unavailable required Brain/provider, rights issue, or unresolved critical
  defect. No flag changes.
```

Do not call V3 globally "production-ready" unless the conclusion specifies
which templates and gates were accepted. Every enablement is a separate
configuration change, commit/release note, and post-enable smoke record.

## 13. Revalidation Rules

Re-run only the smallest sufficient slice after a change, but never reuse
evidence across a change that can alter its premise.

| Changed surface | Minimum revalidation |
| --- | --- |
| Brain request, envelope, ledger, activation, prompt materialization, provider route/timeout, review/retry, reference admission | Phase 1 plus affected Phase 3/4/5 real cases and Phase 6. |
| General project/browser state or API projection | Phase 2 and relevant Phase 6 browser checks. |
| E-Commerce template/plan/UI | E-Commerce Phase 4 plus isolation checks. |
| Photography template/profile/identity/UI | complete affected P10 matrix cells plus isolation checks; rerun all sixteen if role-count or shared execution changes. |
| upstream account health only, no V3 code/config change | record a new provider health/preflight result and rerun only interrupted real cases. |
| Codex native planner only | Doc126 tests; it does not reopen Web production gates. |

## 14. One-Page Operator Checklist

```text
[ ] Freeze current main commit and a clean controlled deployment.
[ ] Confirm Brain, GPT Image 2, gateway budget, and vision/hybrid review are
    actually active in the running process.
[ ] Register authorized, watermark-free materials outside Git.
[ ] Run automated preflight and attach results.
[ ] Prove shared T2I/edit, no-pixel, review-withholding, and fail-closed truth.
[ ] Confirm General browser continuation/reopen truth.
[ ] Complete six cross-domain real-reference/Human-Realism cases.
[ ] Complete E-Commerce Gate C, then exact N=1/2/4/7 Gate D and human review.
[ ] Complete Photography P10: 4 scenes x 2 inputs x 2 output modes.
[ ] Run isolation/lifecycle/browser/legacy/Codex-planner boundary audit.
[ ] Assemble restricted provenance, screenshots, hashes, and signoffs.
[ ] Set only the template flags whose rows are actually accepted; otherwise
    document the hold and leave the default production gate closed.
```

## 15. Completion Rule

This runbook is complete when the campaign produces a signed restricted
evidence package and a precise release conclusion. A future implementation
task is complete only when its regression, real-pixel, and browser obligations
above have the corresponding evidence—not when it merely adds tests, an image,
or a status field.
