# Doc213 — Character Card shared-review repair evidence must reach the next handoff

Status: implementation milestone  
Owner: V3 foundation visual cluster + Professional Character Card slot lifecycle  
Supersedes conflicting narrow behavior in earlier Character Card validation notes where three candidates were treated as independent random attempts even after shared Vision produced a concrete retryable repair signal.

## Problem

During controlled Professional Character Card validation, `expression.laugh` candidate 1 produced a mostly successful laugh keyframe, but shared Vision rejected it as retryable because prompt-owned channels leaked from the reference:

- source hair over-inherited from the identity reference;
- slight professional AI over-perfection.

Candidate 2 was then prepared with the exact same canonical prompt hash as candidate 1. That proves the shared review signal did not reach the next Brain/provider/MCP handoff. The system effectively gambled on another random sample instead of repairing the observed defect.

This is a pipeline design bug, not a laugh-quality prompt problem.

## Authoritative behavior

When a Character Card candidate has a shared review result with retryable repair evidence:

1. Character Card slot lifecycle may continue to the next candidate only within the existing `3 candidates + 1 bounded repair` budget.
2. The next candidate request must carry a sanitized shared-review repair context.
3. The Product API host must project that context into standard retry evidence metadata:
   - `visual_retry_reason_codes`;
   - `resolved_retry_provenance.observed_review_evidence`;
   - an internal `character_card_prior_review_repair` digest for audit.
4. ScenarioRuntime must expose that evidence through `canonical_prompt_context.retry_evidence` so Remote Brain can sign a new complete canonical prompt.
5. If Remote Brain is unavailable and the already-approved Character Card slot-delta recovery path is used, the recovery prompt must consume the same repair context so it does not repeat the same prompt hash.
6. Provider and MCP remain equivalent materialization exits. Both consume the same canonical prompt and the same repair evidence projection.

## Non-goals

- Do not loosen shared Vision or laugh evidence floors.
- Do not add candidate budget.
- Do not add Character Card private scoring, private reviewer, private provider, or prompt recipe.
- Do not relabel old failed smile/laugh candidates as winners.
- Do not expose raw prompts, file paths, provider responses, or private binding identifiers in public UI/API receipts.

## Layering

Foundation visual cluster owns:

- normalization of shared-review issue codes into bounded semantic repair observations;
- the reusable repair context contract.

Professional Character Card owns:

- slot lifecycle;
- carrying the prior repair context from a failed candidate to the next candidate;
- preserving append-only candidate history.

Product API Host owns:

- projection of Character Card request repair context into server-owned runtime metadata;
- ensuring the metadata is internal and sanitized.

ScenarioRuntime owns:

- canonical prompt context projection to Remote Brain;
- bounded slot-delta recovery when Remote Brain is unavailable.

## Conflict note

Earlier validation assumptions allowed candidate 2/3 to be semantically identical to candidate 1. Doc213 changes that rule:

> Once shared review produces a retryable repair signal, the next candidate is still a candidate, but it is no longer allowed to be an identical-prompt random retry. It must be a shared-review-informed candidate.

This does not remove candidate diversity. It prevents the system from ignoring known defects.

## Acceptance tests

- A failed candidate with `source_hair_overinherited` causes the next `CharacterCardCandidateRequest` to carry `prior_review_repair`.
- Host projection includes `visual_retry_reason_codes` and `resolved_retry_provenance.observed_review_evidence`.
- Host projection does not expose raw prompt, raw provider response, local file paths, or private binding data.
- Expression slot-delta recovery prompt differs when repair context is present, while preserving laugh intent and face.front framing.
- General, E-Commerce, Photography, and non-Character Card paths do not receive Character Card repair metadata.
