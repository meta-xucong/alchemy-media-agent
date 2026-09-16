# V3 Universal Visual Review Scope and Evidence Separation Specification

**Document:** DOC316
**Contract revision:** `DOC316_V1`
**Status:** implementation baseline
**Scope:** V3 shared post-generation visual review, all general generation modes
**Upstream authorities:** DOC55, DOC59, DOC93, DOC94, DOC95, DOC96, DOC118, DOC127, DOC260

## 1. User requirement

> 不仅仅套图扩展模式，其他模式应该也是，质量审核标准应该具备通用性。

The repair must not add a special exemption for `delivery_suite`/套图扩展模式. The same universal visual-quality contract must apply to every V3 generation mode. Mode semantics are an additional contract that explains what the selected mode is allowed to vary and what its deliverable roles are; they are not a replacement for, or a hidden rewrite of, universal quality review.

## 2. Theory-first correction model

### 2.1 Intended behavior

Every generated image is evaluated through three explicit questions:

1. **Universal visual quality:** Is the rendered pixel result technically usable, coherent with the user's core intent, readable, clean, natural where a human is visible, and faithful to explicitly locked references?
2. **Mode semantics:** Does the result satisfy the selected mode's own variation axis, role coverage, format/layout, or exploration distance?
3. **Evidence certification:** Did the system receive enough trusted pixel/review evidence to make an automatic delivery decision?

The questions are composable and their outcomes must remain distinguishable.

### 2.2 Observed mismatch

The previous path could return a good real-pixel candidate with an evidence-only issue such as `face_integrity_unverified`. The final delivery gate correctly withheld automatic delivery, but the package and V3 UI described the result as “automatic quality review failed”. That wording conflated an incomplete certificate with a demonstrated visual defect. In addition, a mode-specific role review could be mistaken for a universal image-quality failure if the review scope was not explicit.

### 2.3 Owning layers and authority

| Concern | Authoritative layer | Supporting layer | Must not decide |
| --- | --- | --- | --- |
| Pixel quality and hard visual defects | shared `VisionOutputInspector` / `VisualInspectionReport` | provider evidence | mode-specific role coverage |
| Allowed variation and deliverable roles | `ModeAwareRoleDirector` | mode execution contract | universal pixel quality |
| Evidence completeness | DOC260 evidence plan + provider/vision receipt | review merger | whether pixels are aesthetically good |
| Automatic final delivery | DOC118/DOC127 final-delivery gate | public projection | user-facing claim that quality failed when evidence is merely incomplete |

The canonical `VisualInspectionReport.status` and the existing final-delivery gate remain safety authorities. This document adds an explicit, derived classification for public explanation; it does not make an unverified result automatically deliverable.

## 3. Universal review contract

The shared contract is mode-agnostic and uses orthogonal dimensions:

- `technical_integrity`
- `core_subject_and_user_intent`
- `composition_and_readability`
- `aesthetic_finish`
- `artifact_cleanliness`
- `human_naturalness_when_visible`
- `reference_fidelity_when_provided`

Its current general-mode coverage is explicit and exhaustive: `selection_candidates`,
`delivery_suite`, `creative_exploration`, and `format_layout_adaptation`. A new
generation mode must register with this shared scope before it can claim the
same review guarantee.

The reviewer must not mark a result defective merely because a mode-allowed variable differs from the initial wording. Depending on the selected mode, pose, expression, gaze, head angle, crop, framing, background detail, camera interpretation, or concept distance may intentionally vary. Literal prompt similarity is not the universal quality criterion. Explicitly locked identity/product/reference channels and hard user requirements remain binding under DOC93/DOC96 and the relevant template contract.

The universal issue-code set is shared by all modes. Mode-specific role/format issue codes may be added by the mode director, but they are reported in a separate `mode_semantics` section and must not silently become universal quality defects.

## 4. Three-axis result model

Each output receives the following derived, additive public fields:

```json
{
  "quality_assessment": "pass | warning | fail_retryable | fail_final | needs_manual_review | not_assessed",
  "quality_failure": false,
  "evidence_state": "certified | incomplete | unavailable",
  "review_reason": "quality_issue | evidence_incomplete | review_uncertain | not_evaluated"
}
```

Rules:

1. `fail_retryable` and `fail_final` mean the review found a quality/contract defect; `quality_failure` is true.
2. `manual_review` containing only evidence/uncertainty codes (for example `face_integrity_unverified`, `low_confidence_review`, `review_evidence_*`, or provider unavailability) maps to `quality_failure=false`, `quality_assessment=not_assessed` (or `needs_manual_review` when a substantive quality issue is also present), and `review_reason=evidence_incomplete`.
3. A verified `pass` or `warning` remains quality-positive, but automatic delivery still requires the existing complete evidence receipt.
4. Missing evidence can withhold automatic delivery; it must not be rendered as proof that the image itself is bad.
5. A manual/evidence hold on one output does not erase the per-output review facts or review-only pixels for the other outputs. Final automatic delivery remains governed by the existing package-level gate until a separate partial-delivery contract is approved.

## 5. All-mode application

The following modes consume the same universal contract:

| Mode | Universal review | Separate mode-semantic review |
| --- | --- | --- |
| `selection_candidates` / 相似方案 | yes | controlled distance and same-direction coherence |
| `delivery_suite` / 套图扩展 | yes | role coverage, useful variation, suite coherence |
| `creative_exploration` / 创意探索 | yes | concept distance and core-subject preservation |
| `format_layout_adaptation` / 格式与版式适配 | yes | canvas, crop, layout, and readable-format compliance |

No mode receives a weaker universal quality threshold. No mode is required to be literally identical to the starting prompt when its contract authorizes controlled variation.

## 6. Implementation plan

### 6.1 Shared review layer

- Define one DOC316 universal review-scope descriptor and evidence-only classification helper in the shared visual cluster.
- Reuse it in package merging and public review projection.
- Preserve existing status, retry, evidence-plan, and final-delivery semantics.
- Change manual-review summaries so evidence-only holds explicitly say that no quality failure was established.
- Make the output-record cache validate the touched `output.json` fingerprint in addition to the output-root revision. Evidence resolution must not reuse a stale record after an out-of-band update or corruption.

### 6.2 Provider prompt/materialization

- Make the mode-agnostic rule explicit in both the normal and frozen-contract visual-inspection prompts.
- Keep mode role/format checks outside the universal issue-code list.
- Expose the universal scope descriptor in the active review contract so all four modes can be regression-tested against the same contract.

### 6.3 Public API and UI

- Add additive `quality_assessment`, `quality_failure`, `evidence_state`, and `review_reason` fields to post-generation review output.
- Expose the universal scope and a safe mode-semantic summary separately.
- Keep final-delivery status values backward-compatible.
- Replace the blanket “自动质量审查未通过” copy with evidence-specific or uncertain-review copy when no quality failure was established.

### 6.4 Review-only visibility

Review-only images remain clearly non-final, but the public review projection preserves output-level review facts and eligible review candidates while the final-delivery gate is withheld. This avoids treating one incomplete certificate as deletion of the whole generated evidence set without weakening final-delivery safety.

## 7. Non-goals and safety boundaries

- Do not lower thresholds or add a suite-mode exception.
- Do not make missing face/reference/provider evidence an automatic pass.
- Do not move professional role maps into General Template or the shared foundation.
- Do not change retry budgets, provider routing, or prompt content to conceal a workflow defect.
- Do not change the frozen DOC118/DOC127 final-delivery statuses in this repair.

## 8. Regression and acceptance gates

The implementation is accepted only when all of the following pass:

1. Evidence-only manual review is classified as `quality_failure=false` and is described as incomplete evidence/manual confirmation.
2. A real quality defect remains a quality failure and retains its retry/final disposition.
3. Valid real-pixel pass/warning remains certified and eligible under existing gates.
4. All four generation modes expose the same universal review scope; mode-specific checks remain separate.
5. Review-only output projection preserves generated pixels and does not make them final.
6. Existing DOC55/DOC118/DOC127/DOC260/DOC276 regression tests remain green.
7. Static JavaScript syntax and focused frontend copy/projection tests pass.

## 9. Validation receipt

Implementation and audit completed on 2026-09-16.

Changed scope:

- Shared review classification and package/public projection: `review_scope.py`, `quality_review.py`, `service.py`, and visual-cluster exports.
- Provider inspection prompt/materialization: `vision_provider.py`.
- Evidence-cache freshness: `outputs.py` validates the individual `output.json` fingerprint.
- Desktop/mobile review-only projection and hold wording: `app.js`, `mobile.js`.
- Regression coverage: `test_v3_doc316_universal_review_scope.py`.

Validation:

- `test_v3_doc316_universal_review_scope.py`: 6 passed.
- Relevant integrated regression set (DOC316, DOC276, post-generation vision review, DOC260, DOC66, DOC59, frontend shell): 145 passed, 2 existing FastAPI deprecation warnings.
- Python `compileall`, desktop/mobile `node --check`, and `git diff --check`: passed.

Release receipt:

- Commit and GitHub push are recorded in the final handoff after this document is committed.
- VPS deployment is intentionally not part of this document-only/logic repair handoff; it requires a separate release instruction.
