# Doc152 — V3 Shared Non-Template Smile and Expression Authenticity

## Status

Implemented shared Human Realism refinement. It closes a semantic gap exposed
by controlled photographic comparisons: a smile may be natural and desirable,
yet a repeated uniform camera-presentational smile is an identifiable
synthetic-image prior.

## Decision

For every visible real person with the existing
`expression_ownership_requirement=situation_owned_unless_explicit_user_direction`:

1. An explicitly requested expression remains user-owned.
2. A smile remains valid when the Remote Brain authors it as a credible
   response of this individual in this situation.
3. Pleasant lighting, commercial polish, or an otherwise generic lifestyle
   scene do not by themselves justify a default presentational smile.
4. Before final prompt approval, the Remote Brain performs a semantic
   counterfactual: if the same generic smiling stock subject could replace the
   individual without changing the direction, it rewrites the whole
   situation-owned direction.

The counterfactual is internal reasoning, not a renderer phrase, expression
catalogue, smile classifier, or local Boolean. The Brain remains free to
author laughter, a small smile, a thoughtful face, concentration, surprise,
or another contextually appropriate state when warranted by the full request.

## Pixel verification

The existing shared vision/hybrid review receives the frozen Human Realism
contract. It may return only the already-generic
`human_expression_context` evidence when pixels show an unrequested generic
camera-presentational expression. It must not create a child, gender,
template, or smile-specific review code. A retry transfers that evidence to
the Remote Brain, which replaces the full canonical prompt; the runtime must
not append a negative phrase or facial recipe.

## Boundaries

- No prohibition on smiling and no compulsory neutral expression.
- No local detection of teeth, mouth shape, smile strength, age, gender,
  region, product category, or template.
- No prompt atoms, negative-word stack, regular expression, static expression
  menu, provider routing change, local repair, or special retry.
- General, E-Commerce and Photography share the same Human Realism contract.
- Local MCP remains a canonical-prompt parity relay. It may demonstrate image
  quality but cannot replace vision/hybrid certification or production review.

## Acceptance

1. The final Brain re-sign request explicitly preserves a user-owned or
   situation-grounded smile while rejecting a generic presentational default.
2. The enforced vision prompt uses only `human_expression_context` for this
   concern and contains no historical smile labels.
3. Contract tests show no local expression recipes or demographic/template
   branches reach the renderer.
