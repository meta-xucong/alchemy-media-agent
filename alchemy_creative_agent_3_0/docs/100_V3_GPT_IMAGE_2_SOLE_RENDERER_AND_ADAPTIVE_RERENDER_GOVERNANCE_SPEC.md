# 100 V3 GPT Image 2 Sole Renderer And Adaptive Rerender Governance Spec

## 1. Decision

Doc100 is the current production rendering authority for V3.

```text
GPT Image 2 API is the sole production final-pixel renderer.
V3 may analyze, rank, review, and rewrite instructions around that renderer.
V3 must not replace, patch, composite, or repaint final pixels with a local
generative model, GPU sidecar, face-swap model, or identity-native renderer.
```

This corrects the production direction introduced by Doc98 and Doc99. Those
documents and the standalone service are retained only as isolated research
artifacts. They are not registered providers and cannot be activated by V3
environment variables.

## 2. Compatibility

Doc100 preserves the existing architecture:

```text
Project -> Template -> Scenario Pack -> Job
  -> Central Brain checkpoints
  -> Visual Capability Cluster
  -> Generation Router
  -> GPT Image 2 API
  -> real image review
  -> bounded issue-specific rerender when justified
  -> best reviewed delivery
```

It does not move visual rules into Central Brain, add a second template system,
change Project history, or create a V1/V2 runtime dependency.

The following earlier work remains authoritative:

- Doc50 for Visual Capability Cluster ownership.
- Doc53 for bounded quality retry and loop safety.
- Doc66 for selected-reference and real-review closure.
- Doc83 for final-delivery versus superseded-result presentation.
- Doc85, Doc93, Doc95, and Doc97 for reference truth, channel ownership,
  complementary identity evidence, and adaptive reference ranking.
- Doc96 objective identity measurements remain review evidence only.

Doc100 supersedes only the following production behavior:

- local or sidecar generative models producing final images;
- local face-region replacement as a production identity fix;
- automatic routing from V3 to the Doc98 identity sidecar;
- provider capability metadata unlocking another pixel renderer;
- Doc98/99 configuration inside the production V3 application.

## 3. Ownership Boundaries

### 3.1 Central Brain

Central Brain owns intent, strategy, prompt decisions, and checkpoint summaries.
It does not call a local image model and does not contain renderer-specific
identity logic.

### 3.2 Visual Capability Cluster

The cluster may:

- classify person, product, scene, style, and layout continuity requirements;
- retain uploaded root truth and user-selected strong references;
- rank a bounded reference pack for the requested view and framing;
- inspect real outputs with multimodal and objective signals;
- identify actionable failure codes;
- build a narrow retry patch and revised reference order;
- compare original and rerendered candidates.

The cluster must not modify final image pixels.

### 3.3 Generation Router

The V3 production router must select `openai_gpt_image` for real generation.
Its configured model remains `gpt-image-2`. Missing OpenAI-compatible GPT Image
2 configuration is a clear configuration error; another renderer is not a
silent quality fallback.

### 3.4 Optional Local Compute

Local CPU/GPU tools may be introduced later only for non-destructive analysis,
such as face detection, geometry comparison, artifact detection, or reference
ranking. Their output is metadata. They cannot become a final renderer or alter
the user-delivered image.

## 4. Initial Generation

Before the first API call V3 must:

1. Preserve the complete positive user request and explicit negatives.
2. Resolve prompt-owned versus reference-owned channels.
3. Keep uploaded identity or product truth in the reference set.
4. Put explicit user-selected references first without deleting root truth.
5. Bound and compress transport copies without changing stored originals.
6. Send the final provider prompt and reference pack to GPT Image 2.

Text-to-image and reference-conditioned image generation are both GPT Image 2
operations. Selecting a previous result changes the next request into a
reference-conditioned operation from the user's perspective, but does not
change the renderer.

## 5. Review And Rerender State Machine

```text
generated
  -> review pass -------------------------> eligible for delivery
  -> review warning, no safe correction --> keep for user/manual choice
  -> retryable issue ---------------------> build one issue-specific patch
                                             -> GPT Image 2 rerender
                                             -> review again
                                             -> compare all reviewed attempts
                                             -> deliver best eligible result
```

Every rerender creates a new candidate. It never overwrites the original file,
output record, review evidence, or timeline event.

### 5.1 Retry Budgets

Quality retry budgets remain:

```text
standard: at most 1 quality rerender
strict:   at most 2 quality rerenders
explore:  0 by default; at most 1 only when explicitly enabled
```

These are quality rerenders, not provider transport retries.

### 5.2 Transport Retry Versus Quality Rerender

Transport retry repeats the same intended generation after timeout, 5xx, rate
limit, or malformed upstream delivery. It must not change the visual brief.

Quality rerender is a new GPT Image 2 candidate after a real output was reviewed
and a retryable visual defect was identified. It carries a targeted correction
patch and may change reference order.

The two counters and audit records must remain separate.

### 5.3 Loop Safety

V3 must stop rerendering when any condition is true:

- the mode budget is exhausted;
- the same primary issue repeats after correction;
- no actionable retry patch exists;
- the issue is non-retryable or requires user clarification;
- the newest candidate is worse and a better reviewed candidate is retained;
- upstream transport failure exhausts its separate bounded policy.

No open-ended retry, recursive retry, or retry-until-pass behavior is allowed.

## 6. Issue-Specific Correction

### 6.1 Identity Drift

For identity drift V3 must:

1. retain the uploaded identity root;
2. prefer an explicit user-selected master when present;
3. quarantine weak generated anchors;
4. choose complementary front, three-quarter, or profile evidence appropriate
   to the requested view;
5. restate immutable bone structure and facial relationships;
6. keep hair, makeup, wardrobe, lighting, camera, scene, and finish prompt-owned
   unless the user explicitly locks those channels;
7. ask GPT Image 2 for a whole-image rerender.

V3 must not paste, swap, or locally repaint a face. This avoids inconsistent
skin, lighting, perspective, hair boundaries, and identity seams.

### 6.2 Product Drift

For product drift V3 strengthens product-truth references, protected geometry,
material, color, label, and structure constraints, then rerenders the whole
image with GPT Image 2. It does not locally replace the product.

### 6.3 AI-Looking Human Rendering

The Human Realism module supplies targeted corrections for plastic skin,
uniform pore texture, waxy highlights, synthetic eyes, excessive symmetry,
unreal body proportions, and over-retouched commercial finish. The retry must
preserve attractive facial design and the requested aesthetic; realism is not a
license to darken skin, damage facial proportions, or make the subject less
appealing.

### 6.4 Artifacts And Prompt Misses

Watermarks, generated text, malformed anatomy, source-style leakage, and missed
prompt-owned channels receive only their corresponding correction atoms. A
retry patch must not rewrite unrelated successful directions.

## 7. Best-Result Closure

After all allowed attempts, delivery selection evaluates every reviewed
candidate, not merely the newest. The final result must:

- prefer candidates that pass hard integrity and policy gates;
- use identity/product fidelity, prompt obedience, realism, and commercial
  finish as separate dimensions;
- retain a previous candidate when the rerender regresses;
- mark non-delivered attempts as superseded rather than deleting them;
- expose only final-delivery images on primary result surfaces while preserving
  the complete record in project artifacts and review history.

## 8. Production Isolation Requirements

The following are mandatory:

```text
no identity_native_sidecar in the V3 provider registry
no V3 identity-sidecar settings in production app configuration
no automatic sidecar selection in ProductionImageGenerationProvider
no sidecar capability metadata that unlocks local pixel repair
no runtime import from services/v3_identity_sidecar
```

`services/v3_identity_sidecar` may remain in the repository for research. Its
README and package metadata must state that it is isolated, non-production, and
cannot create user deliverables.

## 9. Implementation Sequence

1. Mark Doc98 and Doc99 superseded for production.
2. Remove the sidecar provider from V3 runtime, registry, and application config.
3. Remove actual-sidecar capability overrides from Product API repair routing.
4. Make identity repair strategy always choose ranked whole-image rerender.
5. Make the V3 production router require the GPT Image 2 API path.
6. Retain the standalone sidecar only as an isolated research artifact.
7. Add source, registry, routing, retry-budget, and stale-capability tests.
8. Run focused, full V3, root, compile, frontend syntax, and diff checks.

## 10. Acceptance Tests

Production correction passes only when:

- real V3 selection returns `openai_gpt_image` even if another default image
  provider is configured;
- missing GPT Image 2 credentials fail clearly instead of selecting another
  renderer;
- stale Doc98 environment variables or metadata cannot select the sidecar;
- the production registry contains no sidecar provider;
- identity repair remains `regenerate_from_ranked_identity_pack` even when old
  identity-native capability metadata is injected;
- standard, strict, and explore retry budgets remain 1, 2, and 0;
- superseded attempts remain append-only and best-result closure tests pass;
- no production runtime file imports the isolated research service;
- all existing Project, General Template, E-Commerce, review, and frontend
  regressions continue to pass.

## 11. Quality Claim Boundary

Doc100 makes an architectural correctness claim, not a guaranteed visual score
for every upstream sample. Commercial quality is improved by stronger reasoning,
references, review, and bounded rerender while preserving GPT Image 2 as the
highest-quality available renderer. Real quality claims still require controlled
multi-scene, multi-style, identity, product, and human-realism output review.
