# E19 Real Provider Gate C/D Acceptance Record

Status: Gate C has one controlled real-provider pass; Gate D and production
readiness remain blocked pending the remaining human/front-end acceptance
matrix.

## Purpose

E19 is the only E-Commerce-owned record for real Provider Gate C/D evidence.
It does not create a provider, a pixel reviewer, a retry loop, a visual recipe,
or a production activation switch. It records whether the existing shared V3
path was actually observed in a controlled environment:

```text
authorized product facts + explicit seller request + versioned platform evidence
-> remote Central Brain
-> exactly N natural-language complete-image directions
-> shared GPT Image 2 generation with the product reference as native input
-> shared vision_model or hybrid review
-> bounded shared retry and append-only final delivery
```

`metadata_only`, a local-image heuristic, a mocked Brain, test images, or a
human assertion cannot replace any required real-run evidence.

## Frozen E-Commerce Boundary

The acceptance run must select `ecommerce_template` explicitly. Product,
Amazon, Taobao, Ozon, or marketplace words in a General request do not enter
this vertical.

The E-Commerce request may provide only factual input: product truth, user
constraints, approved literal copy when the user asks for it, and versioned
platform facts. The Central Brain alone writes the whole-image directions.
The Brain request, template deliverable plan, and provider prompt must not
execute or contain a static platform set, category slot, camera/crop/scene
recipe, default selling point or marketing copy, `CopyRenderPlan`, overlay,
canvas, font, OCR, local text rendering, or historical recipe/overlay data.

Shared V3 owns provider execution, reference conditioning, vision review,
bounded retry, winner selection, and append-only delivery history. E-Commerce
must not add a private provider call, reviewer, retry path, or final selector.

## Evidence Storage and Material Rules

Do not commit source images, generated images, contact sheets, provider bodies,
access tokens, endpoints, or secrets. Store those in the approved restricted
acceptance location and give the run an external evidence reference.

Before a run, the operator must record outside Git:

- a product reference asset identifier and a plain-language rights statement
  confirming it is owned or licensed for this evaluation;
- confirmation that the asset is watermark-free and may be uploaded as a
  `product_reference`;
- the original product facts and the seller's explicit request;
- the platform-evidence version used by the job;
- the controlled deployment/operator and the non-sensitive configuration
  fingerprint.

The previously inspected `C:\Users\T14S\Desktop\case` demonstration folder
has image files but no rights, source, or licence sidecar. It is therefore not
an E19 fixture and must not be uploaded for this Gate.

## Required Real-Run Record

For every actual run, retain the following values in the restricted evidence
location and transcribe only non-sensitive identifiers and conclusions here.

| Field | Required evidence |
| --- | --- |
| Code base | E-Commerce branch/commit and rebased `origin/main` commit |
| Runtime | deployment name, non-sensitive config fingerprint, renderer model, and review mode |
| Material authority | external reference ID and rights/watermark approval reference |
| Request | explicit `ecommerce_template`, requested N, product facts, seller constraints, platform-evidence version |
| Brain | provider/model/provenance, `llm_used=true`, `fallback_used=false`, and an N-item natural-language plan |
| Reference path | uploaded reference binding and shared provider-native reference-conditioning evidence |
| Renderer | actual GPT Image 2 media output IDs, dimensions, mime types, and output count N |
| Review | `vision_model` or `hybrid` verdicts, issue codes, and final-winner rationale |
| Retry/delivery | attempt IDs, bounded retry outcome, append-only history, and the ordinary-results final winners only |
| Persistence | post-refresh query of result, Brain provenance, review/retry history, and any failure reason |
| Human decision | reviewer, Gate C/D result, rejected claims, and follow-up action |

No evidence row may be filled from a fixture provider or a client-side mock.

## Required Negative and Isolation Evidence

The real acceptance package must also reference the automated evidence for:

1. requested counts 1, 2, 4, and 7 remain exact through plan, output, and
   export; a declared platform/provider capacity shortfall becomes structured
   `blocked` rather than truncation;
2. unavailable Brain, `fallback_used=true`, `llm_used!=true`, missing/empty or
   incomplete plan, and count mismatch each block before provider execution and
   do not emit a local-rule image;
3. General and Photography Brain requests contain no
   `ecommerce_creative_context`, marketplace rule, E-Commerce output role, or
   suite/slot semantics;
4. historical recipe, slot, overlay, and text-plan fields remain read
   compatible but cannot reach a new E-Commerce Brain request or provider
   prompt;
5. the E-Commerce front end has an understandable success/blocked/failed
   state, does not show a pseudo-enabled slot redo control, and does not show
   retry candidates as ordinary final delivery; General exposes no E-Commerce
   entry or semantics.

The focused test set in E18 is the baseline for this evidence. It validates
contracts; it cannot certify a real provider output.

## 2026-07-14 Preflight Record (historical; Gate C blockers later cleared below)

| Field | Result |
| --- | --- |
| E-Commerce branch / HEAD | `codex/ecommerce-llm-architecture-correction` / `fc3f5c20ef69b864aff0830dd51a960c5c0336c3` |
| Rebased main | `origin/main@fc3f5c20ef69b864aff0830dd51a960c5c0336c3` |
| Brain configuration | credential presence detected; no real Brain invocation performed |
| Renderer configuration | GPT Image 2 production renderer selectable; no real renderer invocation performed |
| Vision configuration | credentials detectable, but `V3_VISION_INSPECTION_ENABLED` is not enabled in this acceptance process; no `vision_model`/`hybrid` verdict can be produced |
| Authorized product reference | absent from the repository and not documented for the desktop demonstration images |
| Job/project/media IDs | none; no real job was created |
| Gate C result | **blocked** — no authorized, watermark-free product-reference fixture and no enabled shared visual review |
| Gate D result | **blocked** — depends on successful Gate C evidence and human commercial-quality review |
| Production status | **not production ready**; the E-Commerce production gate remains closed |

This record deliberately does not infer success from credential presence, unit
tests, General Gate D, or a single unreviewed image. Once the two blockers are
removed, run a new controlled E19 entry and retain the full real-output
evidence outside Git before changing any readiness state.

## 2026-07-14 Controlled Gate C Evidence — one authorized product case

This is a bounded development acceptance record, not a production release.
The user explicitly authorized use of one existing V3 historical upload for
this controlled test in the current mainline session. That authorization does
not make the source a reusable public fixture or expand its rights beyond this
acceptance run.

| Field | Result |
| --- | --- |
| Main code | `origin/main@42eda8f` for the executed run; follow-up provenance-only de-duplication correction is `2875c25` |
| Controlled runtime | local port 8017 only; Photography production gate temporarily enabled only in this controlled process; no production default changed |
| Material authority | user-authorized historical V3 upload `v3_asset_4b12e066339a4817`; one watermark-free square bottle reference, restricted to this controlled evidence |
| Request | explicit `ecommerce_template`; one 1024×1024 product image; preserve the bottle, cork, pink liquid, and source label without inventing/rewriting copy or claims |
| Brain | `deepseek` / `deepseek-v4-pro-260425`; `llm_used=true`, `fallback_used=false`; exactly one natural-language direction frozen at planning and reused at generation |
| Renderer | job `job_3c3c2a5b57`; output `v3_output_a4399af63c5f4c41a605`; `openai_gpt_image` / `gpt-image-2`; one PNG at 1024×1024 |
| Reference path | provider-native edit path; exactly two physical provider inputs: one product-truth crop and one original, both from the same source asset; no duplicate source upload |
| Review | shared `hybrid` inspection by `openai_compatible_vision`; `pass`, verification state `verified`, confidence `0.88`, no detected/retryable issue codes |
| Retry/delivery | visual automatic retry intentionally disabled for the single-request gateway test; zero retry attempts were needed; one final output remained in append-only job history |
| Persistence | final job query returned `generated`, one candidate, frozen-Brain reuse provenance, GPT Image 2 provenance, and post-generation hybrid-review evidence |
| Human decision | mainline visual inspection found the source bottle shape, cork, pink liquid, label placement, and existing label structure preserved; a user commercial-quality signoff is still required for Gate D |

The preflight blockers for this one Gate C case are therefore cleared. This
does **not** clear Gate D, multilingual/text acceptance, the full requested
count matrix, or the E-Commerce production gate. No static recipe, local text
renderer, font/OCR path, or private E-Commerce review/retry path was added.

## 2026-07-15 Current-build Gate C N=1 — planning evidence and authority clarification

This controlled attempt used the Doc127/E20 material register and the freshly
refreshed `c628e64035663ba25e7e5ea6d485caaf87468f1d` runtime. It is not yet a
Provider Gate C result. The restricted manifest is
`ACPT-20260715-ecommerce-N1-c628e640`; no media, raw request, credential, or
endpoint is recorded in Git.

| Field | Result |
| --- | --- |
| Main code | `origin/main@c628e64035663ba25e7e5ea6d485caaf87468f1d` |
| Project / reference | `project_3cec293a47` / `project_reference_d19f6ab45c`, binding the restricted material register `MAT-ACPT-20260715-KIDSWEAR-01` as active `product` reference |
| Browser admission | user explicitly selected the E-Commerce template; the rendered project showed the fixed template and one active product reference |
| Planned job | `job_d6dc5f5ba6`; remote `deepseek` / `deepseek-v4-pro-260425`; `llm_used=true`, `fallback_used=false`, one plan image, one natural-language direction, and one remote intent |
| Continuation-identity clarification | `ecommerce_output_1` is an E17-allowed opaque continuation identity, bound only after the remote Brain returns the exact N=1 natural-language intent. It is not a semantic visual recipe and does not enter Brain input or the Provider prompt. The earlier contrary interpretation is a non-result. |
| Provider / review / retry | **not yet invoked**: no generation result, zero candidates, zero final-delivery outputs, no review and no retry. The same planned job is eligible for its single shared generation. |
| Gate C result | **pending** — the Brain planning contract has passed, but Provider, review, retry, delivery, and persistence evidence are still required. |
| Gate D / production | **not started / not production ready**; all production gates remain closed. |

The current controlled instance subsequently advanced to
`origin/main@cf170833`; its Project-summary UI fix does not alter this
E-Commerce runtime/Brain contract. Continue the one permitted shared generate
for this same planned job, then record the actual GPT Image 2, review, retry,
delivery, and post-refresh result before deciding Gate C.
