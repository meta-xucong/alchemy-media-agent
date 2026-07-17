# Professional Mode M5 Child Real-Pixel Rerun — 2026-07-18

## Status

```text
SOURCE: previous child reference supplied by the user
REMOTE BRAIN: USED, FALLBACK: FALSE
GPT IMAGE 2 PIXELS: RECEIVED
SHARED VISION REVIEW: REAL HYBRID RESULT RECEIVED
FRONT: 3 CANDIDATES + 1 BOUNDED RETRY, NO PASSING WINNER
THREE-QUARTER: NOT STARTED (front winner missing)
PROFILE: NOT STARTED (front and three-quarter winners missing)
M5: BLOCKED, NON-COUNTING EVIDENCE
NO PRODUCTION / GATE C-D / P10 CLAIM
```

This is an append-only evidence record for a fresh run using the actual child
reference from the earlier workflow. It uses the existing V3 Remote Brain,
GPT Image 2 Provider, and shared Vision inspector. It does not create a second
Provider, reviewer, retry loop, or storage path.

## Source and runtime provenance

- Root source: `codex-clipboard-95dbd7be-b038-4c49-971d-5467fdce6433.png`
- Root SHA-256:
  `93786216f2a33fbdd668b7b68e2b9b2fb8a5092de26e9173314a79021684e079`
- Remote Brain metadata: `provider=deepseek`,
  `model=deepseek-v4-pro-260425`, `llm_used=true`, `fallback_used=false`.
- Provider metadata: `provider=openai_gpt_image`, `model=gpt-image-2`,
  `1024x1024` PNG pixels received.
- The Provider received the existing two identity derivatives
  (`portrait_identity_crop` and `portrait_identity_geometry_crop`); the full
  source frame was suppressed. No new reference budget or renderer was added.

The first Chinese-language probe was deliberately excluded from M5 evidence:
the remote response was mojibake and the Brain interpreted the request as a
three-scene cyberpunk suite. The counted probe was repeated in unambiguous
English with one output per request so “three candidates” could not become
three different roles.

## Front candidate lineage

The three independent front candidates were generated from the same root and
the same identity-only reference policy:

| Candidate | Job / output | SHA-256 | Shared Vision result |
| --- | --- | --- | --- |
| A | `job_358bf3d235` / `v3_output_1aa2e2661c62485db057` | `eb7d7b26b769217f1c77797e6906c15a31c8eb92b3bea77ca0ab8ed8f41517e1` | `fail_retryable`: human skin/retouch, human rendering artifact |
| B | `job_a43f53d179` / `v3_output_b5e520923403490e9ab0` | `98ee0cc0102c6ff1cf12167acad50d6ed873ea8e492056e206c972af28c92cb7` | `fail_retryable`: human skin/retouch, human rendering artifact, generic stock finish |
| C | `job_3284b50ee2` / `v3_output_c9d5397f0ba049a6978d` | `50f94a997230055be4f8f7fdf71a1df629ddfcc19350caf51cb0797ea564ba17` | `fail_retryable`: human skin/retouch, human rendering artifact, generic stock finish, flat lighting |

Candidate A had the strongest available identity read (`identity_consistency`
and `same_person_readability` both `1.0`; face geometry `0.88–0.90`) and was
selected as the only bounded-retry target. No candidate was declared a winner
before retry because shared Vision found a retryable real-pixel defect.

## One bounded retry

Retry output:

```text
job_id: job_64ff347a26
output_id: v3_output_a88c5fc8f6954fd3bf43
output_sha256: c22f796d3a39ea0c2f5ef26e6c7798aacb249495a13d359d8149df099d79bc7c
attempt: 1
```

The retry preserved the child age direction, blue top, straight-on framing,
white background, and identity geometry. Shared Vision returned a real
`hybrid` / `verified` report with `status=fail_retryable` and confidence
`0.86`. It still reported:

```text
human_skin_or_retouch
human_rendering_artifact
human_scene_coherence
```

The reviewer specifically observed overly smooth skin, limited natural texture,
and a slightly too-perfect face/eye rendering. This is a genuine quality block,
not a missing-pixel or metadata-only review.

## Acceptance decision

The front stage has no passing winner after its one permitted repair. The
serial contract therefore stops before three-quarter: a failed front cannot be
used as an identity anchor for later views, and no profile view may be created
without the front and three-quarter winners. No anchor view, active pack, or
Professional M5 certification was written from these outputs.

This run does prove that the correct child source reaches the real Brain and
existing GPT Image 2 Provider, that the two-image identity derivative budget is
honored, and that shared Vision can identify the remaining anti-AI/human-
realism defect. It does **not** prove M5, Gate C/D, P10, or production
readiness.

## Follow-up required before another counted M5 attempt

1. Keep the shared Vision gate unchanged; do not accept the smooth result by
   lowering thresholds.
2. Fix the shared prompt/provider materialization or upstream rendering path so
   a real child face retains ordinary skin texture and non-perfect asymmetry.
3. Re-run front 3→1 plus one bounded repair. Only after a passing front winner
   may the existing 3-candidate three-quarter and profile stages run with the
   strict 2/3/5 serial reference budgets.

