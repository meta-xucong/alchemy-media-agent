# Doc162 — V3 Bounded Brain Contract Recovery and Shared Anchor Host Closure

Status: implementation specification; Doc161 pixel correction has one verified front pass, while formal Professional M5 remains open.

## 1. Evidence and remaining problem

The bounded Doc161 rerun produced three materially different outcomes from the same frozen Professional front contract:

1. one GPT Image 2 result passed shared hybrid Vision review (`overall=0.91`, `human_realism=0.89`) and correctly kept identity while releasing source wardrobe, scene and hairstyle;
2. one result was correctly withheld because source wardrobe and hair were over-inherited;
3. one attempt was blocked before Provider because the Remote Brain returned JSON whose semantic `visual_task_profile` did not satisfy the strict schema.

This proves that the Human Realism and reference-ownership correction is effective. It does not yet prove formal M5 completion. The successful pixel came through the internal preparation job seam, while the existing `AnchorPackPreparationService` still lacks a concrete Product API host that can turn shared Vision evidence into a likeness-first winner and continue the serial front → three-quarter → profile pack.

## 2. Authority and invariant

This document extends Docs 93, 95, 96, 113, 134, 135, 160 and 161. It does not replace their ownership rules.

The governing invariant is:

```text
one frozen request
→ Remote Brain authors one complete semantic contract
→ normal shared runtime freezes it
→ Remote Brain signs the final canonical Provider prompt
→ shared Provider and shared Vision execute
→ the formal AnchorPack service projects evidence and selects likeness-first winners
```

No local component may invent creative content, repair malformed Brain JSON, append renderer wording, lower Vision thresholds or introduce a Professional-private Provider/reviewer/retry/storage path.

## 3. Bounded Remote Brain semantic-contract recovery

Strict real-image planning receives at most one additional Remote Brain schema re-answer when, and only when, the first remote response is valid transport JSON but one of the required semantic sections is rejected by the typed merger.

The recovery must:

- reuse the same immutable `BrainRunRequest`, requested count, template policy, assets and evidence;
- identify only the rejected schema sections in a server-owned recovery marker;
- ask the same Remote Brain to return the complete compact contract again;
- perform no local JSON patching, keyword inference, prompt generation or fallback;
- happen before any Provider request;
- record attempted/succeeded/failed audit fields without recording the malformed response;
- fail closed if the second answer is still incomplete or invalid.

Transport failure, timeout, policy rejection or an unavailable Brain is not a schema-recovery trigger. Existing fail-closed behavior remains authoritative.

## 4. Formal shared AnchorPack host

A concrete Product API host must adapt the existing `AnchorPackPreparationService` to the existing shared runtime. The host is orchestration glue, not a new visual subsystem.

For every frozen `AnchorGenerationRequest`, it must:

1. resolve the ready root upload and any already selected anchor output IDs from existing stores;
2. create one internal Professional preparation Job carrying only the typed view role, candidate ordinal, pack binding and serial reference evidence IDs;
3. run the normal ScenarioRuntime, Remote Brain, canonical prompt finalizer, shared Provider, shared Vision and bounded retry path;
4. reject a blocked Job, missing pixels, metadata-only review, unverified review or binding mismatch;
5. project the existing shared Vision score card and issue codes into `AnchorReviewDecision` and `IdentityScoreSummary`;
6. let `AnchorPackPreparationService` select the front and supplementary winners by its existing likeness-first selection key;
7. persist only the existing append-only pack/history records through the existing catalog.

The host must preserve the existing 2/3/5 provider-native derivative reference budget. It may not expose raw local paths, prompts, private bindings, provider responses or biometric vectors through a public route.

## 5. Shared Vision projection contract

Professional Face Identity preparation adds typed score dimensions to the frozen shared review contract. These dimensions describe what Vision must score; they are not prompt terms and never enter the Provider prompt:

- same-person readability;
- distinctive-feature readability;
- age/identity direction fidelity;
- human realism;
- prompt-owned channel obedience;
- pose/view compliance;
- overall visual quality;
- AI-overperfection penalty.

The host consumes only a `vision_model` or `hybrid`, `verified` shared review. Missing required score dimensions make the candidate fail closed. Shared Vision status remains authoritative; the host cannot reinterpret `fail_retryable` as pass. Existing objective identity-metric fusion remains ephemeral and may strengthen the shared score, but no biometric vector is persisted.

## 6. Explicit non-goals

This work must not:

- add child, kidswear, East Asian, smile, skin, wardrobe, hairstyle or studio recipes;
- add regular-expression or keyword-based semantic recovery;
- change the Doc161 identity derivative crop for a passing case;
- increase retry budgets or create an outer image request replay;
- weaken Human Realism, identity or shared Vision gates;
- change Standard Mode, General, E-Commerce or Photography deliverable semantics;
- claim M5, Gate C/D or production readiness from a single passing front image.

## 7. Acceptance

Code acceptance requires:

1. first malformed strict semantic contract → one Remote Brain-only re-answer → valid result accepted;
2. two malformed answers → fail closed, with exactly two Brain calls and zero Provider calls;
3. non-schema Brain failures do not trigger the semantic recovery;
4. the Product API host is bound to the existing lifecycle route and existing shared services;
5. exact front/three-quarter/profile candidate counts and serial reference evidence remain 3/3/3 and 2/3/5 provider-native derivatives;
6. shared Vision evidence maps to a complete typed identity score summary without local visual inference;
7. metadata-only, unverified, blocked and missing-pixel results cannot become anchor candidates or winners;
8. no Professional-private Provider/review/retry/storage is introduced;
9. focused and full V3 regressions, compile checks and diff checks pass.

Pixel acceptance restarts with one fresh formal preparation run. A complete M5 pass requires a verified front winner, verified three-quarter winner, verified profile winner, append-only lineage, prompt/reference parity and an activation-ready pack. If any bounded stage has no passing winner, later stages remain blocked and the evidence is sealed without gate relaxation.
