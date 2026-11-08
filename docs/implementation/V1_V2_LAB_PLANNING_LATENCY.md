# V1, V2 and LAB planning latency

## Objective and correction model

The total objective is to remove proven avoidable waiting in V1/V2/LAB without
reducing image quality, review, stability or final-image visibility. The current
phase audits the actual paths, implements bounded changes, and verifies them
before integration and deployment. Passing offline tests alone does not establish
a production speedup or visual equivalence across future requests.

The shared Render Bridge Codex node already applies HTTP Responses, reduced skill
catalog context and timing instrumentation to all products. Keep its 300-second
stream-idle tolerance, native image generation, model settings and reference
handling. No additional transport change is needed for these product adapters.

V1/LAB `visual_review.review_image_output` is a local review path. V2 output and
visual-evidence review likewise do not call the V3 vision/automatic regeneration
loop. The V3 whole-set refinement defect therefore must not be transplanted into
these products as a supposed diagnosis. V2 Claude checkpoints depend on prior
creative decisions; its serialized output units preserve cancellation authority.
Keep those stages, image-unit order, review rules and existing retry budgets.

Observed avoidable work belongs to the text-planning layer:

1. V1 sends the complete user prompt and structured asset context at top level,
   and copies them again from `current_plan.variables`. Remove only copies whose
   values exactly equal the corresponding authoritative top-level values. Keep
   the generated scaffold, unique/custom variables, user text and reference
   evidence. Do not mutate the saved plan or image-provider request.
2. V2 checkpoint/inline rules repeat transform mode, fidelity mode and the full
   Claude instruction already held in `prompt_transform`. Keep the complete
   structured profile and replace only repeated prose with an instruction to
   follow that profile. This does not change the existing prompt-budget policy,
   selected-template authority, asset fusion or Claude continuation stages.
3. LAB quality planning awaits independent style enhancements serially. Each
   call uses its own prompt/style and the same fixed request/selected styles;
   none consumes another enhancement's result. Run batches of at most two text
   calls, retain result order and join the batch before continuing. All enhanced
   prompts still finish before any image generation. Keep serial image variants,
   explicit user interval, model/effort/token limits and the existing quality
   fallback. Remove `normalized_idea` from this private LLM payload because it
   is exactly the same request value as retained `original_idea`.

## Verification boundaries

Focused regression tests must show exact retained prompt/context/profile values,
unchanged source records, bounded LAB overlap and ordering, and joined task
cancellation. Existing transport cancellation, billing/publication, LAB recovery,
Claude continuation, prompt-budget and reference tests cover the unchanged owning
contracts. Compare payload sizes and deterministic planning waves; do not label
synthetic latency reductions as measured production improvement. No exploratory
provider calls, quality downgrades, shorter timeout, skipped review or automatic
new image attempts are part of this repair.

## Verified implementation

The focused regression set has 184 passing cases: 109 V1/LAB cases, nine V2
deduplication cases, 64 existing V2 checkpoint/inline/QR cases, and two V2
first-unit cancellation cases. The cancellation cases run separately because
`test_v2_api.py` leaves its process-global image provider set to mock; mixing
them in that process bypasses the fake Bridge route. One missing-gateway test
also requires LAB planning enabled to exercise the intended guard. These were
test-environment corrections; no production behavior was changed to satisfy them.
New V1/LAB coverage is included in the existing regression workflow; V2's
existing `test_claude_*.py` selection includes the new V2 cases.

Direct before/after comparisons reconstructed the old builders from main
`68c601223dd524d695a0bc6c71faeec42e55114e`. Three V1 fixtures retained equivalent
content while reducing payloads from 2043/2040/2097 to 1841/1839/1877 characters.
Nine V2 mode/stage combinations retained every field except the duplicated rules
suffix, reducing each request by 168–521 characters. Four LAB calls with a fixed
synthetic 40 ms provider returned identical inputs/results; peak overlap changed
from one to two and measured planning time from about 190 to 93 ms. These numbers
describe fixtures, not production image latency. A separate read-only A1 review
found no implementation defect. Runtime deployment verification remains a
separate acceptance step.
