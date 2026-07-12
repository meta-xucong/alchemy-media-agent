# PX Mainline Request: Photography Set Execution And Continuation

## Request Status

```text
request_id: PHOTOGRAPHY-MAINLINE-004
status: requested
request_owner: Photography Module
implementation_owner: Scenario Runtime / Project Mode / final-delivery owners
blocking_phase: P6 professional-set production and real-provider acceptance
```

## Existing Safe State

`origin/main@71a4679` provides the gated `PHOTOGRAPHY-MAINLINE-003` seam for
one single-hero output or reference reshoot. The Photography module now has a
planning-only three-role professional-set and continuation contract. It does
not expose that contract through the current production manifest because the
shared runtime cannot execute or package it without losing role identity.

## Required Shared Contract

Provide a generic specialized-template execution seam that can consume a
frozen module-owned deliverable plan while keeping all pixels, review, retry
and result selection in shared runtime ownership.

For Photography, the first plan contains:

```text
session_hero
environmental_context
detail_or_moment
```

The shared seam must:

1. carry immutable role IDs and role-specific shot facts from
   `SpecializedScenarioPlanningResult` into series planning and provider
   requests without teaching General those Photography roles;
2. request exactly one delivered winner per Photography role while preserving
   append-only retry attempts and comparing all eligible attempts;
3. retain the exact pinned profile binding, color/finish anchor, identity truth
   and reference-channel contract across every role and retry;
4. let Project Mode select `professional_set` for the Photography template
   instead of falling through its current General `campaign_poster` selection;
5. provide an append-only specialized-role continuation lineage whose child
   reuses the frozen parent plan and requires exact explicit reconfirmation for
   a named photographer profile;
6. renegotiate shared capabilities when a continuation adds new evidence,
   including `nonhuman_subject_identity`, without a text-only fallback; and
7. expose a beginner result package containing only final role winners, with
   retry-superseded originals folded into workflow/history details.

## Required Failure Semantics

```text
professional_set requested before shared seam lands -> explicit unsupported block or unavailable control
named continuation lacks explicit reconfirmation     -> block
named profile version/checksum changes               -> block; never use General fallback
new identity evidence cannot negotiate fidelity      -> block before provider
role plan mutates between plan/generate/retry         -> immutable-plan conflict
one role has no eligible final result                 -> incomplete set, never relabel another role
```

The current silent mode fallback from `professional_set` to `single_hero` must
not be presented as a successful professional set.

## Isolation Requirements

- General must not receive Photography roles, profile fields, defaults or
  package summaries.
- E-Commerce keeps its own listing/A+/slot continuation contracts and must not
  import Photography internals.
- The Photography module must not call providers, shared vision review, retry
  loops, or the final resolver directly.
- Named profiles remain explicit UI selections only; prompt/LLM/project
  history cannot activate or replace one.
- Gate-off behavior remains byte-for-byte compatible with the existing
  placeholder template.

## Required Tests

1. Gate off/on and single-hero behavior remain unchanged.
2. `professional_set` carries three distinct frozen role payloads end to end.
3. Shared review/retry/final delivery resolves one winner per role across all
   attempts.
4. Project Mode set creation and role continuation survive persistence reload.
5. Named continuation accepts only the exact explicit binding snapshot.
6. Non-human new evidence uses the shared high-fidelity capability or blocks.
7. General and E-Commerce public/result behavior remains unchanged.
8. Real-provider text and reference-conditioned outputs pass the Photography
   P6 quality matrix before the deployment gate is enabled broadly.
