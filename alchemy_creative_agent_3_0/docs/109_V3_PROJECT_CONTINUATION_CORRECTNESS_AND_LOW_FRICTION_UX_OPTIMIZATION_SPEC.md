# 109 V3 Project Continuation Correctness And Low-Friction UX Optimization Spec

## Status

**Required corrective specification. Slices A and B, plus Slice C's
deterministic review/activation contract, are implemented on mainline. The
live Gate D rerun was completed on 2026-07-14 with real browser, Provider,
final-pixel-review, and controlled-restart evidence. That acceptance closes
this General Project Mode corrective gate; it does not by itself activate any
specialized template for production.**

This document turns the failed 2026-07-12 Doc104 Gate D live General-project
run into a bounded mainline implementation plan. It is not an E-Commerce,
Photography, brand-kit, or text-pixel design document.

The work is shared foundation and General Project Mode work:

```text
correct reference evidence
-> truthful job lifecycle
-> real review result
-> one clear user-facing workspace
```

Professional suite roles, platform rules, slots, export packages, named
photographers, and specialist terminology remain outside General.

## 1. Decision

The original 2026-07-12 Doc104 Gate D run **failed**. It proved project
persistence and media storage, but it also showed that the continuation
contract could use the wrong image, report completion too early, and
misrepresent the result board. The 2026-07-14 rerun recorded in Section 10
supersedes that acceptance outcome: Gate D now passes while retaining the
original failure as the reason for this corrective specification.

No specialized template may claim production readiness from the prior Gate D
preflight. E-Commerce remains behind its activation gate.

## 2. Live Evidence That This Specification Addresses

The isolated live project was `project_d55aa9bf43`. Times below are China
Standard Time and artifacts remain Git-ignored under `.codex-longrun/`.

| Observation | Evidence | Required interpretation |
| --- | --- | --- |
| Policy rejection | A request combining a named brand, watermark removal, and a logo request received provider HTTP 400 `content_policy_violation`; V3 made one fresh request, created no candidates, and did not retry. | Correct non-retryable provider classification; user-facing explanation needs improvement. This is not an aiself timeout or duplicate SDK request. |
| Files and media routes work | A later continuation persisted PNG, preview, thumbnail, and download files. The preview endpoint returned HTTP 200 and a fresh page rendered both final images. | A "picture missing" report is not a storage/provider-output failure. |
| Selected output is not a provider reference | Selected generated asset `asset_7fe81ccd25` persisted without a canonical output URL. The next provider input plan contained `v3_asset_589d26fd42c84d1a` twice. | The selected result fell back to the uploaded source and was not faithfully continued. This is a blocking correctness defect. |
| Completion is premature | The first task was announced generated before all requested output/retry work finished; the next task was announced generated before its bounded visual retry settled. | `generated` currently means "a candidate exists", not "the user has a final delivery". The UI may not enable continuation at that point. |
| Result board is inaccurate | The page said "3 张可查看图片" although only two final records had media URLs; the third was an unresolved selected-reference record rendered as "图片准备中". | A reference is not a generated delivery image. Counting and rendering must use canonical media-backed records only. |
| Quality/feedback failure | Two final images have distinct file hashes but are materially the same dark reflective shoe composition; the persisted feedback said the style was too dark and its lighting was poor. | The run does not prove useful variation, feedback compliance, or selected-result continuity. |
| Review provenance is insufficient | Saved records contain `output_review_metadata_only`. The retry reason was based on metadata/planning signals rather than live image inspection. | Metadata review cannot certify visual quality, near-duplicate avoidance, or compliance with an aesthetic rejection. |
| Inactive semantic leakage remains | A simple non-human product continuation prompt still contained Doc90 face geometry, hair, makeup, and same-person instructions. | Doc102/108 isolation is not complete for reference-conditioned Project Mode; inactive human directives must not reach the provider. |

## 3. Non-Negotiable Invariants

### 3.1 Canonical selected-output binding

A selected generated result is valid continuation evidence only when it has a
canonical, immutable binding:

```text
project_id + job_id + candidate_id + asset_id
-> output_id + renderable preview/download URI + source integrity identity
```

Rules:

1. The selection route resolves the selected candidate or asset to an
   `OutputRecord` before persisting a positive generated reference.
2. A selected generated `OutputRef` must carry `output_id`, preview URI,
   thumbnail URI, download URI, and the immutable source identity needed by
   the provider resolver.
3. If an output record is not yet materialized, selection returns a plain
   "图片仍在整理，完成后即可设为参考" state. It must not write an asset-only
   positive reference.
4. A missing selected generated source is an evidence-resolution failure. It
   must never silently substitute an uploaded source image, a different output,
   or a prompt-only approximation.
5. Legacy asset-only selection records remain readable history. They are not
   eligible provider inputs until a resolver can prove one exact canonical
   output record. Otherwise the UI asks the user to choose an available image.

### 3.2 Reference resolver and provider-input integrity

The shared provider resolver accepts only a typed resolved-reference list, not
raw project asset identifiers.

```text
selected generated output -> its exact persisted output file
uploaded product truth    -> approved source/crop/derivative for its channels
style-only reference      -> its assigned channels only
```

Before a provider call it must:

1. de-duplicate by immutable source identity and canonical file content;
2. preserve source order only after de-duplication;
3. emit an audit entry for each retained, intentionally suppressed, and
   unresolved reference;
4. reject an empty required-reference plan rather than falling back to another
   source; and
5. record exactly what provider input was used in the frozen job record.

One uploaded image must never appear twice merely because it is both a project
upload and a failed fallback for a selected generated output.

For an uploaded product whose whole frame is not assigned as style context,
the resolver must use its approved product-truth derivative or crop rather
than letting a full source background, lighting, or composition dominate an
image-edit request. This extends Doc85/Doc93 channel ownership; it does not
invent product-suite behavior in General.

### 3.3 Honest finalization lifecycle

`generated` is reserved for a settled delivery result. A job now has these
user-relevant states:

```text
planning
-> generating
-> finalizing (reviewing, selecting best attempt, bounded retry if needed)
-> generated | blocked | failed
```

Contract:

| State | User sees | Allowed action |
| --- | --- | --- |
| `planning` / `generating` | One progress surface and the current plain-language activity | Wait, leave and safely return later; no second continuation job from changing context. |
| `finalizing` | "图片已生成，正在检查并整理最终结果" | Wait or leave safely; result cards and continuation CTA remain disabled. |
| `generated` | Final media-backed delivery cards and one next action | Select, reject, upload a reference, or continue. |
| `blocked` | A concise cause and an edit path | Edit the request or start a new deliberate attempt; no blind automatic repeat for policy rejection. |
| `failed` | A concise recoverable/unrecoverable explanation | Retry only when the documented failure class permits it. |

The backend is authoritative. The frontend must not infer terminal success from
the first candidate, a timeline event, or a locally recovered output URL.

Compatibility:

- a legacy terminal job without finalization metadata is read as
  `generated_legacy` for history only;
- existing old project data remains readable;
- old jobs are not retroactively rewritten; and
- a continuation is allowed only after canonical references are resolved under
  the new contract.

### 3.4 Review truthfulness

Review provenance is explicit:

```text
live_pixel_review
metadata_only
not_available
```

`metadata_only` may report structural facts (files exist, retry record exists,
or a declared constraint was planned), but it may not certify visual quality,
reference fidelity, variation, brightness, composition, or negative-feedback
compliance.

A live visual acceptance run must have a real image inspection route over the
final pixels. It must at minimum produce bounded evidence for:

- media availability and image readability;
- near-duplicate/role-collapse risk across the delivery set;
- explicit visible artifact/mark/text checks when relevant;
- explicit user feedback that is visually testable, such as "too dark" or
  "same composition"; and
- a clear `not_verifiable` outcome rather than fabricated certainty when a
  requested aesthetic cannot be evaluated.

Local perceptual or embedding measures may be ephemeral review signals; they
are not user identity data and must not be persisted as biometric vectors.

### 3.5 Prompt and activation isolation

The frozen capability plan remains the only authority for provider, review,
retry, and visible summaries.

For a no-person General product continuation:

- no face geometry, hair, makeup, same-person, gaze, or portrait repair
  language may enter the final provider prompt;
- Human Realism activates only when actual person/skin/hand evidence requires
  it under the existing shared rules;
- current request and user rejection take precedence over a selected style
  reference in their assigned channels; and
- a selected reference cannot silently reintroduce a rejected dominant
  attribute such as a dark exposure or copied full-frame composition.

When positive selection and negative feedback conflict on the same visual
dimension, V3 must either resolve them with explicit channel scope (for
example preserve product identity while changing exposure) or ask one concise
user question. It must not pretend both directives were satisfied.

## 4. Low-Friction General Project UX

### 4.1 Product principle

The General workspace answers one question at a time:

```text
What is ready now, and what is the single useful next action?
```

It must not make a beginner interpret job IDs, provider states, retry history,
reference fallbacks, or multiple competing calls to action.

### 4.2 One workspace, progressive disclosure

The default project detail order is:

1. compact project title and one-line goal;
2. current state and **one** primary action;
3. final delivery images, when ready;
4. compact "当前参考与避开方向" panel;
5. continuation composer only after the user chooses to continue; and
6. collapsed "过程记录" and "项目记录" sections.

Archive/delete, long-term style saving, technical prompt display, and internal
retry history are secondary disclosures. They must not compete with the
primary next action.

General uses neutral wording:

```text
生成图片
继续生成
选为后续参考
加入参考图
标记不喜欢
```

It must not say "电商套图", "slot", "平台", "导出包", or use professional
package expectations. Existing General wording such as "继续生成套图" must be
changed to neutral copy.

### 4.3 Image, reference, and history separation

| Surface | May contain | Must not contain |
| --- | --- | --- |
| Final results | canonical final-delivery records with a renderable media URL | unresolved references, planned assets, superseded attempts |
| Current references | uploaded sources and selected generated references with an exact source binding | a fake generated-image card for a reference without media |
| Process history | retry-superseded and diagnostic candidates, folded by default | default delivery count or primary continuation anchors |
| Timeline | plain user actions and terminal state changes | raw provider JSON, capability trace, prompt audit, storage paths |

The final-image count is the count of unique canonical final-delivery media
records, never `selected_output_refs.length` and never a synthetic fallback.

### 4.4 Error and recovery copy

Provider errors map to user actions, without exposing raw JSON:

| Failure class | User copy | Primary action |
| --- | --- | --- |
| Content-policy rejection | "这段需求不能按原样生成。请调整需求或使用权利清晰、原始干净的素材后再试。" | 编辑需求 |
| Transit timeout / provider instability | "图片服务暂时没有完成这次生成，项目内容已保留。" | 在终态后重新生成 |
| Reference unresolved | "你选的图片还没有可用的最终文件，请等待整理完成或换一张图片。" | 等待或换图 |
| Finalizing | "图片已生成，正在检查并整理最终结果。" | 无第二个生成 CTA |

No user-facing copy may suggest removing a watermark, evading provider policy,
or blindly repeat a non-retryable policy request.

### 4.5 Polling and state refresh

The browser uses one project-workspace coordinator per open project/job.

- Only one in-flight refresh cycle may exist.
- Navigating away, opening a different project, or reaching a terminal state
  cancels the old coordinator.
- The coordinator reads one coherent workspace snapshot or versioned status,
  rather than independently racing project, timeline, output, and job reads.
- Poll cadence backs off while nothing changes and stops at a terminal state.
- A refresh may update the display only from a newer server revision.

This removes the repeated endpoint storm and prevents a stale recovery loop
from repainting a newer project state.

## 5. Required Implementation Slices

### Slice A — reference resolution and finalization (backend first)

1. Add the canonical selected-output resolver and output-reference hydration.
2. Add provider input de-duplication and the no-substitution guard.
3. Add authoritative finalization status and reject/hold continuation while
   finalization is active.
4. Persist immutable audit records for resolution, suppression, and
   final-delivery selection.
5. Add compatibility readers for legacy project/job records.

### Slice B — General workspace correctness and simplification

1. Render final media records only in the result board and count.
2. Keep unresolved/legacy references in the reference panel with honest copy.
3. Render a single primary state action and a single continuation composer.
4. Replace General "套图" wording and hide advanced actions by default.
5. Consolidate refresh ownership and cancel stale pollers.
6. Map policy and reference failures to plain-language, actionable notices.

### Slice C — review and active-capability closure

1. Wire live pixel inspection into the real-provider acceptance configuration.
2. Make metadata-only review non-certifying.
3. Remove inactive human/portrait contributions from reference-conditioned
   no-person prompts, reviews, and retry patches.
4. Add feedback/near-duplicate verdicts to the bounded review contract.

## 6. Required Test Matrix

### Backend contract and regression

- Selecting a materialized candidate persists matching output ID and media
  URLs, then continuation receives that exact file.
- Selecting an unresolved candidate is rejected/held; it cannot create an
  asset-only provider reference.
- A missing selected file never falls back to another uploaded file.
- The same source passed through multiple project paths is sent once to the
  provider and has one retained audit entry.
- A job with required count greater than one, review, or bounded retry remains
  non-terminal until its delivery set settles.
- Old jobs and asset-only selection records remain readable without gaining
  unsafe continuation rights.
- No-person General product/reference fixture contains no portrait/human
  prompt, review, or retry language unless its frozen plan activates it.
- Negative "too dark" feedback plus a selected dark reference either yields a
  scoped repair or an explicit conflict state; it cannot silently claim a pass.

### Frontend regression

- Result count equals unique final media-backed output count.
- A selected reference with no media never renders as a result image card.
- Process history is folded and excluded from final counts.
- Finalizing state offers no second generation CTA and no selectable transient
  candidate.
- One primary action is visible for every workspace state.
- General contains no E-Commerce suite/slot/platform/export wording.
- A policy rejection shows edit-oriented plain copy rather than raw error JSON
  or a retry-first affordance.
- Opening/closing/switching projects leaves at most one polling coordinator.

### Live Gate D rerun

Use an owner-approved, rights-clear source and a policy-safe brief. Verify:

```text
create project
-> generate a final delivery
-> select one materialized output
-> verify exact selected-output provider input on continuation
-> add a reference
-> reject a visibly testable direction
-> continue only after finalization
-> inspect final pixels for difference and feedback compliance
-> return/reopen project
-> verify media, references, rejection, final state, and one clear CTA
```

Gate D passes only when all contract, browser, and live-pixel evidence agree.

## 7. Ownership and Release Boundary

The mainline owns Slices A--C because they alter shared Project Mode,
provider-reference, review/retry, lifecycle, and General UI contracts.

E-Commerce and Photography branches may consume the resulting shared states
and canonical output references, but they must not duplicate the resolver,
finalization, review, or polling behavior. Neither branch should surface a
production action that depends on this work until the mainline rerun passes.

## 8. Completion Definition

This corrective phase is complete only when:

1. every selected generated reference has an exact materialized source or is
   honestly unavailable;
2. no provider input contains accidental duplicate or substitute references;
3. terminal delivery is not announced before review/retry settles;
4. General result, reference, and process surfaces are visually and
   semantically separate;
5. General has one simple next action and neutral wording;
6. real pixel review, not metadata-only review, supports the Gate D quality
   verdict; and
7. the live Gate D rerun passes with recorded evidence.

These conditions now have recorded Gate D evidence. V3 foundation still has
separate specialized-template gates; this General-project result alone does
not activate E-Commerce, Photography, or provider-native text production.

## 9. 2026-07-13 Mainline Implementation Record

This record describes the implementation that preceded the real acceptance.
The formerly failed Gate D is now closed by the evidence in Section 10; this
does not turn it into a specialist-template production-readiness claim.

| Area | Implemented mainline behavior | Recorded Gate D evidence |
| --- | --- | --- |
| Canonical selected output | Selection now resolves an exact materialized V3 output record before writing a positive project reference. The persisted binding carries the output ID, all media URIs, file path, and a SHA-256 source identity. Missing or ambiguous records return an explicit held state; they cannot fall back to another candidate or an upload. | Browser selection persisted `v3_output_1ab82ddf4f5e4adcb57f` with its canonical file and media binding. |
| Provider input | Project continuations put project references ahead of duplicate upload paths, deduplicate by content and role, and retain a provider-resolution audit with retained, suppressed, and unresolved sources. A required project selected-output source that is not canonical/materialized blocks the request. | `job_331dffa1db` recorded `image_edit_with_reference_images`, retained the exact selected output, and did not substitute a different uploaded file. |
| Lifecycle and delivery | Background generation is persisted as `generating`; rendered candidates are `finalizing` while shared review/retry settles; only then may the job become `generated`. In-flight jobs expose no selectable cards and Project Mode holds selection. | The browser observed `generating` then `finalizing`; only terminal `generated` exposed the two continuation delivery cards. |
| Gateway-managed terminal timeout | When the gateway-managed path outlives its configured provider deadline plus a short conversion margin, a background watchdog records one `blocked` terminal result with a bounded timeout audit and no V3 replay. The timeout is attempt-bound: a delayed worker cannot overwrite it, and a later deliberate run cannot be closed by an old watchdog. | This successful continuation did not exercise the timeout terminal path; its single logical request completed without V3 replay. |
| Project result surfaces | Project-output APIs and desktop/mobile boards expose final-delivery media only. Retry/process artifacts stay append-only in storage/audit rather than being counted or rendered as delivery cards. Legacy asset-only records remain readable but are suppressed from continuation context. | Controlled restart and browser reopen restored four media-backed cards; no placeholder or asset-only selected reference was rendered as a delivery card. |
| Refresh behavior | The desktop output request has one in-flight coordinator and opening a project performs one authoritative output refresh rather than a short/long overlapping pair. Recovery does not promote a known `generating` or `finalizing` job from a local output URL. | Browser return, reload, controlled service restart, and project reopen each recovered the persisted terminal records without initiating a new generation. |
| Pixel-review truthfulness | Reference-conditioned real generation requests a live vision route. `metadata_only` now returns non-certifying `manual_review` with explicit unverifiable dimensions. When the user has rejected a visual direction, live review must return a feedback verdict and, when a selected generated reference is attached, a distinct/near-duplicate verdict; a missing verdict is held for manual review rather than reported as a pass. | Both final continuation outputs were `pass` under hybrid `openai_compatible_vision` review, with final pixels visibly cooler, wider, and free of generated text/brand marks. |

Focused regression coverage is in
`test_v3_doc109_project_delivery_closure.py`, together with the amended
Project Mode and commercial-shell tests. The coverage proves the deterministic
contract above, including exact candidate resolution, no substitution,
content deduplication, legacy suppression, finalization holds,
final-delivery-only rendering, metadata-only non-certification, active-plan
isolation, and bounded feedback/near-duplicate review verdicts. It does not
replace the live-pixel feedback/near-duplicate acceptance evidence required by
Gate D.

## 10. 2026-07-14 Gate D Accepted Live Evidence

The controlled local acceptance instance was run with a rights-clear,
unbranded glass-sphere reference in `project_dbc3ecab02`. No production
default gate was changed.

| Gate requirement | Recorded result |
| --- | --- |
| Browser project workflow | Created/continued a General project through the real V3 workspace; the project held the uploaded product reference and two persisted rejected-direction notes. |
| Materialized source selection | The browser selected exactly `v3_output_1ab82ddf4f5e4adcb57f`; its project binding persisted its output ID, media routes, file path, and source-integrity hash. |
| Exact Provider reference | Continuation job `job_331dffa1db` recorded `image_edit_with_reference_images`. Its frozen provider-input plan retained the selected output plus the uploaded product-truth source and its approved product crop; no selected-output substitution occurred. |
| Lifecycle | The continuation moved through `generating` and `finalizing` before `generated`; no second V3 logical request was made. |
| Final pixels and review | Two final `gpt-image-2` images (`v3_output_5e43ce13cba946e18744`, `v3_output_a4e375fc362c48e69e19`) preserved the glass sphere, removed the rejected warm/reference-like room direction, and had no generated text, logo, watermark, or extra objects. Both received `pass` from hybrid review with `openai_compatible_vision`, not `metadata_only`. |
| Return, restart, and reopen | After a controlled acceptance-instance restart, the project restored four media-backed delivery records, the exact selected source, both active references, both rejection notes, and terminal job `generated`. The browser reopened the project with one clear continuation CTA. |

The first two candidates in the run were visibly reviewed as needing a
directional correction; their recorded feedback evidence was deliberately
carried into the subsequent selected-output continuation. The accepted
continuation is the final pixel and reference-fidelity evidence for this gate.
