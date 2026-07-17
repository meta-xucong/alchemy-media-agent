# Professional Mode M5 Real-Pixel Provider Run — 2026-07-17

## Status

```text
V3 DEFAULT PROVIDER AUTHORIZED BY USER: YES
REMOTE BRAIN: USED, FALLBACK: FALSE
GPT IMAGE 2 PIXELS: RECEIVED
SHARED VISION REVIEW / RETRY / FINAL WINNER: BLOCKED (NO TERMINAL REVIEW)
THREE-VIEW FACE PACK: NOT COMPLETED
M5: BLOCKED, NON-COUNTING EVIDENCE
NO PRODUCTION / GATE C-D / P10 CLAIM
```

This is an append-only evidence record for one user-authorized run on the
isolated Professional Mode branch. It uses the existing V3 Product API,
Remote Brain, GPT Image 2 Provider, and shared review seam. It does not create
a second Provider, reviewer, retry loop, storage path, browser route, or MCP
route.

## Runtime and authorization boundary

- Branch was rebased to the then-current `origin/main@756b0c7`; the default
  V3 Provider configuration was used without MCP.
- The V3 settings-backed credential was used only in-process after the user
  explicitly authorized this test. The key value is not recorded, exported,
  or persisted by this evidence.
- Provider metadata reported `provider=openai_gpt_image` and
  `model=gpt-image-2`. The configured V3 upstream host was not reclassified as
  the official OpenAI endpoint, and this run is not official Provider Gate
  evidence.
- Remote Brain metadata reported `provider=deepseek`,
  `model=deepseek-v4-pro-260425`, `llm_used=true`, and `fallback_used=false`.
- The production/browser gates remain closed.

## Source and output fingerprints

Only hashes and safe identifiers are retained; the private source path and
prompt body are intentionally omitted.

```text
source_filename: portrait_reference.png
source_bytes: 344872
source_sha256: 19A7F099245086B4310299F18A9972CBA0703523E581DBEA71255D35C1032917
job_id: job_64987888ab
candidate_id: candidate_cd7bf28c53
output_id: v3_output_85311475617d40c2ad01
asset_id: asset_28d317e518
output_original_sha256: 1994CEEF21CF1B03AB14F4792D60083EA07C3145C28E09F34A306C19A064A3EE
output_preview_sha256: 3A35F16FE35D2C2622A1B5F77871B6D8353ADA123817A8FFFC81624B0B2C796B
output_thumbnail_sha256: 17ADAC397B9E1D5D201BB7C5BB02DD715A4314F7AC48D5EB4674BD3C8CA54AFF
```

The Provider materialized one PNG output at 1024×1536. Its safe provenance
reported two derived identity references from the one uploaded source:
`portrait_identity_crop` (`feature_detail`) and
`portrait_identity_geometry_crop` (`head_geometry`). The full source frame
was suppressed from Provider input, the source integrity fingerprint was
retained, and `required_unavailable=[]`, `unresolved=[]`, and
`operation_outcome=pixels_received` were recorded.

## Review and acceptance boundary

The Product API entered the shared post-generation review path after the real
pixels were written. The local process did not receive a terminal Vision
review result through the configured proxy and was stopped after a bounded
wait. Consequently:

- no `vision_model`/`hybrid` review receipt is counted;
- no identity score or semantic review pass is claimed;
- no bounded repair/retry winner was selected;
- no output was activated as an anchor-pack view;
- no final delivery is certified.

The generated front-like portrait was visually inspected only as a
non-certifying diagnostic. It broadly retained the source person's dark bob,
eye/nose/mouth arrangement, and natural complexion direction, but appeared
more symmetrized/generic than the source. This observation must not be used as
an automated score or as M5 acceptance.

## Why M5 remains blocked

M5 requires the complete serial evidence chain:

```text
front: 3 candidates -> likeness-first winner
three-quarter: 3 candidates from root + front winner -> winner
profile: 3 candidates from root + front + three-quarter winners -> winner
each stage -> shared pixel review -> bounded retry -> final winner
all three winners -> human comparison and activation evidence
```

This run proves only that the existing V3 default Brain/Provider can receive
the supplied portrait and return one real GPT Image 2 artifact through the
Professional binding. It does not prove the three-view quality contract,
shared review closure, Provider Gate C/D, General Gate D, Photography P10,
E-Commerce Gate C/D, or production readiness.

## Follow-up

Before another real call, the mainline maintainer should first make the shared
Vision review transport return a bounded terminal receipt in this environment,
then run the serial three-view contract with a strict request budget and save
the review/retry/final-winner evidence for each view. Until that happens,
Professional Mode remains blocked and non-production.
