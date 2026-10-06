# Doc329 — V3 Per-Output Delivery Authority And Correction Model

Status: **PROPOSED IMPLEMENTATION CONTRACT**. This is a cross-cutting V3 foundation correction. It does not add a state framework, alter image-quality standards, or convert General Template into a vertical suite planner.

Baseline: `1a66b245ce058062eece2c1519e6a10eaf3e55d1`. Read with Doc328, V3 Doc321, Docs 95/96, Doc276, and E-Commerce E34/Doc280.

## 1. Correction model

### Intended behavior

Every generated output has its own immutable identity, source attempt/role, review receipt, and final-delivery disposition. The set of best eligible images may span multiple attempts. Formal selection, Brand Memory, ordinary Project outputs, public status, and formal export must all respect that same exact per-output set.

### Observed mismatch

Some paths reason at different levels:

- Review history contains multiple attempts, but the current review package may contain only the most recent attempt’s inspections.
- Best-result logic marks preferred output IDs, while final delivery and Project visibility can still be computed from a narrower current inspection package.
- Direct selection uses a job-level “some output is deliverable” gate, then can select any sibling asset.
- Brand Memory filtering can retain every candidate reference, even when only one candidate was selected.
- E-Commerce export collects outputs by intent rather than exact final-delivery eligibility.
- Desktop completion consumes a terminal job but classifies only some failure states as failed.

The owning correction is to restore one image-scoped authority end to end. Do not add another collection of loosely coordinated status flags.

## 2. Authoritative facts and projections

| Fact | Authority | Projection rule |
|---|---|---|
| Output identity and bytes | Existing Product/Output Store records bound to the current job, asset, and candidate. | Do not infer identity from array position or a sibling image. |
| Review evidence | Existing complete review receipt, with exact output ID, asset ID, verified real-pixel evidence, status, and any required Doc276 certification. | Keep the evidence attached to the output/attempt that produced it. A retry’s status cannot overwrite a prior output’s evidence. Malformed, missing, duplicate, or incomplete bindings remain non-certifying under Doc321. |
| Per-output delivery eligibility | Existing `_public_final_delivery_projection` / Doc321 semantics and current required certification gates. | `pass`/`warning` outputs that satisfy all applicable evidence/certification rules are eligible. `manual_review`, `fail_retryable`, `fail_final`, unreviewed, or uncertified outputs are not formal delivery unless an existing explicit contract says otherwise. An eligible sibling remains eligible when another image is held. |
| Best result | Existing `reviewed_delivery_preference` and append-only attempt history. | Compare candidates for the same output role using each candidate’s own evidence. Select the best eligible candidate for each role; do not mark a failed/unreviewed image as formal winner, and do not replace good initial output merely because a retry is newer. |
| Candidate browsing | Existing typed selection/candidate surface and current `not_evaluated` semantics. | A user may inspect or explicitly choose an unreviewed candidate only through an existing browsing/reference workflow. That action is not final delivery, review certification, or permission to write it to Brand Memory as an accepted result. No new public enum is introduced without a separate contract change. |
| Formal user selection | Direct Product API `select_result` and the exact eligible ID set. | Explicit selection is validated atomically before persistence. Any explicitly requested ineligible or unknown item rejects the whole formal selection with an actionable reason. Default selection chooses eligible outputs only. Empty or zero-match selection does not become `selected`. |
| Brand Memory update | Existing selected asset/candidate association and `MemoryUpdate`. | Persist only accepted IDs and reference records whose source asset or candidate association intersects the selected eligible set. Empty match means skip the update. Do not repopulate empty intersections with all selected IDs/references. Project Mode keeps its current non-automatic update behavior and explicit confirmation flow. |
| Product status and Project board | Product status plus current Project output/review projection. | Ordinary final-result lists expose only exact eligible winner outputs. Review-only/history surfaces may expose retained pixels with their real status and a non-delivery reason. Do not use preference metadata alone to certify delivery. |
| E-Commerce export | Existing E-Commerce output intent/packaging contract plus exact eligible output set. | Formal delivery manifest lists only eligible winner images, with the original bound review disposition. Any distinct history export must be labeled as review/history and preserve real statuses. `metadata_ready` means packaging metadata exists; it is not visual approval or final delivery. Do not create a second history ledger. |
| Desktop completion | Existing typed Product status, final-delivery projection, and recoverable-partial facts. | Classify `failed`, `not_found`, and `blocked` as failures unless valid partial delivery is explicitly present; show partial delivery distinctly; only report full success for complete valid delivery. A withheld review with generated pixels remains a warning/held state, not an approved delivery. |
| Brain requests | Existing V3 provider settings and adapter request construction. | OpenAI availability and actual request use the same resolved absolute base/endpoint. Anthropic Messages includes the project’s already-supported `anthropic-version: 2023-06-01` header. Provider adapter changes do not alter visual review or retry authority. |

## 3. Selection contract details

1. Recompute or receive eligibility from the canonical job result once at the formal selection boundary; do not use UI-provided review fields.
2. Normalize candidate IDs and asset IDs using existing matching rules. An explicit request containing an unknown ID, an ineligible output, or a mix of eligible and ineligible outputs is rejected as a whole before writing `selected_result`, job status, or Brand Memory.
3. With no explicit IDs, choose the eligible output set, not all stored assets.
4. When delivery has not been evaluated, preserve only the existing explicit candidate-browsing use case. The response and downstream references must continue to expose `not_evaluated`; never manufacture a delivery pass.
5. When there are no eligible outputs and no permitted browsing action, return the existing withheld/held outcome, not `selected` with an empty result.
6. Do not silently substitute another image for the one the user explicitly requested.

## 4. Retry and receipt contract details

- Retry results remain append-only.
- The delivery candidate set is the union of role-specific winners, not necessarily one attempt-wide batch.
- Every winner must resolve to its own original output record and original review evidence.
- Any best-result marker is a preference/projection hint only; it cannot override a missing, failed, duplicate, stale, or mismatched review receipt.
- If an output’s review evidence cannot be recovered exactly, it is not eligible. Keep it in history and fail closed for delivery.
- Preserve atomic scenario-specific batch contracts when they already exist. The general per-output rule does not weaken a specialized contract.

## 5. Brand Memory details

Keep output, asset, and candidate identifiers in their own domains. For the selected eligible output records `U`, derive `A(U)` as their bound source asset IDs and `C(U)` as their bound selected candidate IDs from the existing output/asset records. Do not compare output IDs directly to `accepted_asset_ids` or reference asset IDs.

Compute:

```text
accepted' = proposed accepted_asset_ids ∩ A(U)
references' = proposed references whose candidate_id maps to C(U)
             OR whose source_asset_id maps to A(U)
```

Then:

- If there is no matching accepted item/reference, skip the update entirely.
- If a candidate ID is the only stable association, resolve it through the selected asset’s existing `selected_candidate_id` binding.
- The reference record’s generated reference ID is not automatically the source asset ID.
- If both candidate and source asset associations are present but disagree (one points into the selected set and the other points outside it, or they resolve to different source/candidate pairs), reject that reference from the update; do not accept whichever field happens to match.
- Keep user intent and explicitly requested `apply_memory_update` behavior; this contract tightens the scope of what can be persisted, not the user’s opt-in control.
- Do not automatically edit already persisted Brand Profiles. Historical data triage is a separate read-only task.

## 6. Provider request contract details

### OpenAI Chat Completions

- Resolve configuration once, then use the same resolved value for availability and request creation.
- Missing OpenAI base URL resolves to the existing official API host and `/v1` path exactly once.
- Explicit base URL/gateway remains authoritative. Support trailing slash and an existing `/v1` suffix without duplicate path components.
- The final URL is absolute before HTTPX is called.
- This contract covers the V3 Brain route under test; it does not claim all OpenAI-compatible third-party gateways share the official default.

### Anthropic Messages

- Add the version header to the existing hand-built HTTP request; do not migrate the whole adapter to an SDK.
- Use `2023-06-01`, already used by this repository’s Anthropic HTTP clients.
- Keep `x-api-key`, `content-type`, request path, model, and body behavior intact.
- OpenAI and other provider headers remain unchanged.

## 7. Non-goals and forbidden shortcuts

- No new general “result status framework,” shadow eligibility database, new copy of accepted IDs, or fallback eligibility branch.
- No making a whole task fail because one sibling failed when Doc321 allows independent eligible outputs.
- No relaxing review evidence, required certifications, identity quality, thresholds, or retry limits.
- No using `delivery_preferred_output` alone as evidence of eligibility.
- No turning manual review or `fail_final` into `ready_for_manual_review` for convenience.
- No real provider call as a debugging step; use mocked outbound request tests.

## 8. Completion invariant

For a fixed job revision with no explicit user-selected subset, the following automatic-delivery output ID sets must agree:

```text
W = status final_delivery outputs
  = ordinary Project final outputs
  = automatic formal export files
```

When the user explicitly selects a subset `U`, assert `U ⊆ W`; selection and selection-dependent export projections may contain only `U`, while any projection that reports `W` must describe it as eligible/available outputs rather than the user’s chosen subset. Do not force `W = U` or silently replace either set. The selected Brand Memory references must map exactly to selected assets/candidates in `U`. Review history may be a superset, but must identify held, failed, unreviewed, or superseded status accurately and cannot be mistaken for formal delivery.
