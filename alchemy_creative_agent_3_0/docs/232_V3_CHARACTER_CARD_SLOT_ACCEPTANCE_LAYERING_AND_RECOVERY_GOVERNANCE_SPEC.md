# Doc232: V3 Character Card Slot Acceptance Layering and Recovery Governance

Date: 2026-07-24

Status: governance spec. This document records the layering rule and the
minimum separation plan after the controlled `expression.laugh` review-only
acceptance closure. It does not implement a refactor, open production gates, or
claim full Expression Set completion.

## 1. Product baseline

Professional Character Card acceptance must preserve the shortest authoritative
slot path:

```text
candidate(s) -> shared review -> winner -> slot receipt
existing output -> shared review -> slot receipt
```

Everything else is supporting infrastructure. The core path may use Provider or
MCP to materialize pixels, but once a candidate or existing output is present,
the formal acceptance decision is owned by shared review and the slot receipt.

For the current validation, success means only:

```text
existing output v3_output_a27b83988d28f9010cd1
-> shared Vision affect/framing pass
-> expression.laugh winner_selected
-> persisted slot receipt
-> reload/public projection consistency
```

It does not mean:

- `expression.anger` or `expression.sad` has started or passed;
- Body Silhouette has started or passed;
- the entire Expression Set module is active;
- the visual asset is fully ready for every downstream professional use case.

## 2. Layer definitions

### 2.1 Core Acceptance Path

Core owns the final slot truth:

- module and slot identity;
- candidate identity;
- output identity;
- shared review result;
- winner selection;
- prompt/reference parity evidence required for the slot;
- slot receipt persistence and safe public projection.

Core must not depend on MCP handoff recovery, retry-round bookkeeping,
operation-window scans, legacy metadata compatibility, or whole-module
activation. If a complete existing target is uniquely identified and passes the
requested shared review gates, auxiliary recovery state must not block slot
receipt writing.

Core failure examples:

- two outputs claim the same slot winner;
- review receipt output id does not match the slot output id;
- the slot accepts a candidate without shared review;
- a failed or unverified review is promoted to a winner;
- a single-slot receipt is rejected only because unrelated module slots are
  still empty.

### 2.2 Enhanced Quality Contracts

Enhanced owns quality gates that make a slot useful and user-visible:

- face/front framing parity;
- identity and reference parity;
- laugh affect evidence and expression/framing dimensions;
- human realism and anti-AI review dimensions;
- bounded repair and best-candidate selection criteria.

Enhanced quality gates must be requested by the slot contract or current user
intent. They should produce shared review receipts and issue codes. They should
not be duplicated inside persistence, route handlers, or MCP recovery logic.

Enhanced failure examples:

- laugh affect is weak;
- face/front framing deltas exceed the slot contract;
- same-person readability is below the active slot threshold;
- output has visible AI polish or artifact issues.

### 2.3 Auxiliary Reliability and Compatibility

Auxiliary protects resumability and durable identity:

- MCP handoffs and materialization status;
- fingerprints and rendering contracts;
- crash checkpoints;
- cross-process locking/CAS;
- exact operation lookup;
- stale or ambiguous handoff defense;
- legacy metadata projection and compatibility.

Auxiliary must prevent identity confusion and replay corruption, but it must not
turn a complete Core target into a new generation request. If Auxiliary cannot
prove identity safety, it should block slot writing with structured evidence and
preserve records append-only. It should not advance the candidate loop, create a
replacement job, consume another handoff, alter prompts, or run extra retries.

Auxiliary failure examples:

- handoff checkpoint identity does not match job/candidate/output/result;
- two durable records claim the same operation;
- a stale pending handoff tries to override an existing generated checkpoint;
- a generated output cannot be safely rebound after a crash.

## 3. Canonical Slot Acceptance / CandidateRun context

Future cleanup should converge on one context object as the handoff between
layers. The proposed context is conceptual in this document; do not add broad
implementation until focused tests are in place.

Minimum fields:

- `asset_id`
- `card_version_id`
- `module`
- `slot_key`
- `generation_channel`
- `attempt_round`
- `candidate_index`
- `candidate_count`
- `output_id`
- `candidate_id`
- `job_id`
- `generation_result_id`
- `review_owner`
- `review_status`
- `review_receipt`
- `prompt_reference_parity`
- `quality_contracts`
- `auxiliary_projection`

Authority rule:

- Core reads `candidate_id`, `output_id`, `review_receipt`, and
  `prompt_reference_parity`.
- Enhanced writes review evidence into `review_receipt`.
- Auxiliary writes only `auxiliary_projection`; it may prove identity safety or
  report mismatch, but it must not redefine winner selection.

## 4. Blocking priority

When a new defect appears, classify it before changing code:

| Class | Owns | Blocks slot write? | May create new job/output? |
| --- | --- | --- | --- |
| Core | winner, output, review receipt, slot receipt | yes | no |
| Enhanced | requested quality gate and public visual quality | yes when gate is requested | no, except through bounded candidate policy |
| Auxiliary | crash/replay/legacy/durable identity | only when identity safety is unproven | no |

Rules:

1. Core mismatch always fails closed.
2. Enhanced failure preserves the candidate and review receipt, then follows the
   existing bounded candidate/repair budget.
3. Auxiliary mismatch preserves evidence and blocks slot writing only when
   identity safety is at risk.
4. Auxiliary must never silently fall back to ordinary generation when the user
   asked for review-only collection of an existing output.
5. Whole-module activation is a module policy, not a prerequisite for
   single-slot receipt persistence.

## 5. Current targeted audit and minimum isolation points

The current implementation works after Doc231-B, but still mixes layers. Do not
rewrite it in one pass. Split only after adding focused contract tests.

| Area | Current mixed responsibility | Layer classification | Minimum isolation point |
| --- | --- | --- | --- |
| `CharacterCardPreparationService._prepare_slot` | candidate loop, shared review gate, MCP exception mapping, retry round, card failure state | Core + Enhanced + Auxiliary | Extract a pure `SlotAcceptanceCore` that evaluates candidate -> review -> winner. Keep MCP exception mapping in an adapter. |
| `ProductApiAnchorPackPreparationHost` MCP resume helpers | operation lookup, stale handoff recovery, checkpoint matching, generated-output review-only target selection | Auxiliary around Core | Extract `CanonicalSlotAcceptanceTargetResolver` and `McpRecoveryAdapter`; Host should orchestrate target -> review -> candidate result. |
| `VisualAssetLibraryLifecycleService._persist_character_card_success_receipts` | slot receipt persistence and module state projection | Core | Keep as Core write-slot path; it should not depend on activation policy. |
| `activate_character_card_module` / module activation policy | requires a complete module | Module policy | Keep separate from single-slot receipt persistence; missing anger/sad must not block laugh slot collection. |
| `route_handlers.post_visual_asset_character_card_prepare` | public payload validation and review-only dispatch | Adapter | Normalize `review-only slot request` into canonical context; do not infer identity from route/planning/job/handoff/output in multiple places. |

## 6. Minimum contract tests before refactor

Before moving code, add tests proving:

1. A complete existing target can be accepted without creating a new
   job/candidate/handoff/output.
2. An Auxiliary stale pending handoff cannot override a complete generated
   checkpoint.
3. Missing unrelated Expression Set slots do not block `expression.laugh` slot
   receipt persistence.
4. Whole-module activation still remains fail-closed until the module policy is
   satisfied.
5. Enhanced gates can reject the candidate with structured review receipts
   without changing Core target identity.
6. Auxiliary identity mismatch blocks slot write without falling back to
   generation.

## 7. Non-goals

This document does not authorize:

- prompt changes;
- Vision threshold relaxation;
- increased candidate or retry budget;
- manual pass;
- new Provider/MCP generation;
- broad storage or Host refactor without red tests;
- declaring full Expression Set or production readiness from a single-slot
  success.

Short form:

```text
Protect Core. Configure Enhanced. Contain Auxiliary.
```
