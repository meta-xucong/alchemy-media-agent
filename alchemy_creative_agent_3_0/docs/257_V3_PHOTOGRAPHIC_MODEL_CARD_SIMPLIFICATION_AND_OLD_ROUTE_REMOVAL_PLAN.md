# Doc257 — Professional Model-Card Prompt Diff

## Decision

The early Professional Character Card route already produced the better visual
direction: mature photographer-shot child model-card imagery with clean studio
light, commercial polish, and natural human texture.

Doc257 does not replace that route. It reuses it.

Doc257 only removes later bad prompt additions and adds the smallest standard
model-card angle / crop wording needed for Character Card consistency.

## Scope

Doc257 changes only:

```text
Face / Expression prompt projection
Face / Expression negative-prompt projection
the image-constraint wording source used by those projections
```

Doc257 does not change:

```text
three-candidate generation
winner selection
FormalSlotReceipt
save / reload
slot write
activation
MCP recovery
Provider route
Brain sign-off
existing images
existing receipts
existing review records
```

## Reuse the verified baseline

Keep the mature photographic baseline:

```text
photographer-shot child model-card portrait
clean white studio background
commercial soft light
natural child presence
identity preserved from reference
real camera photographic rendering
beautiful, polished, not over-processed
```

Do not optimize this baseline further inside Doc257. The quality route is
treated as good enough. The only change is prompt cleanup plus minimal framing
standardization.

## Remove from active prompt / negative prompt

Remove these later increments from new Face `standard_front` and Professional
Expression delivery prompts:

```text
passport / ID / biometric headshot pressure
big-head face-dominant compliance language
over-strict face midline / eye-level / symmetry wording
absolute realism checklist
micro-defect checklist
fake pore / fake asymmetry / random flaw instructions
AI detector / undetectable / evasion language
noise / blur / compression / ugliness as realism tricks
canvas size treated as crop proof
transport quality treated as crop proof
```

Keep existing general safety and quality negatives. Only remove the bad
over-realism, detector-evasion, and ID-photo-style increments.

## Add the minimum model-card framing wording

Add only positive standard Character Card framing wording:

```text
front / 45-degree / side / rear view according to the slot
consistent photographer distance across the set
complete hair outline
small natural headroom
close model-card crop with visible neck, collar and upper shoulders
clean white studio model-card background
```

Canvas size, 2:3 output, provider quality, MCP transport, and white background
are transport/rendering details. They are not proof of景别 and must not become
a new gate.

## Expression rule

Expression delivery uses:

```text
same model-card framing wording
+ existing laugh / anger / sad affect wording
```

Expression does not get a new evaluator, new receipt, new slot rule, or new
Face-local implementation. Affect wording stays Expression-owned.

## Old docs and flags

Doc248 / Doc252 / Doc254 / Doc255 and their trusted flags become compatibility
read only for this product path.

They may explain old records. They must not create new:

```text
prompt text
negative prompt text
generation gate
review gate
retry condition
success condition
slot authority
```

Existing old receipts, images, evidence, and tests are not physically deleted
or rewritten by Doc257.

## AI-detectability

AI-detectability is post-generation observation only.

Allowed:

```text
record visible AI-looking artifacts in the comparison report
compare which output looks more like a photographer-shot model-card image
```

Forbidden:

```text
prompt or negative prompt about being undetectable
detector-evasion optimization
noise / blur / compression / fake flaws
retry because of detector score
Core / receipt / activation changes because of detector score
```

## Review evidence

Doc257 does not create, require, or backfill review evidence.

If Doc256, Doc252, Doc248, review score, or score-card fields are missing:

```text
do not synthesize them
do not infer them from prompt wording
do not infer them from canvas size
do not persist subjective visual judgment as proof
```

Visual comparison may discuss the result, but it is not a new Formal gate.

## Minimal tests

Only test the prompt diff.

Required:

1. Face `standard_front` prompt contains the minimum model-card framing wording.
2. Expression prompt contains the same framing wording and preserves affect
   wording.
3. Old ID-photo / absolute-realism / micro-defect / detector-evasion wording no
   longer appears in active prompt or negative prompt.
4. Body, 25-degree auxiliary, target-only, and historical compatibility paths
   are not touched.
5. One existing narrow Core / receipt smoke test still passes.

Do not add a large matrix. Do not test unrelated Brain / Provider / MCP /
harness recovery here.

## Implementation

1. Add the prompt-diff tests.
2. Remove the bad prompt / negative-prompt increments.
3. Add the minimum model-card framing wording.
4. Run the prompt tests and one narrow Core / receipt smoke test.
5. Run one controlled visual comparison against the old winner.

The visual comparison is not formal slot acceptance:

```text
no slot write
no receipt
no activation
no extra candidate set
no retry loop
no route repair
```

## Rollback

Rollback is a single prompt-projection revert.

If the new output is worse:

```text
revert the prompt-projection commit
keep all receipts and assets unchanged
do not revive Doc248 / Doc252 gates as a patch
revise the prompt wording theory first
```

Short form:

```text
Use the good old photographic baseline.
Delete the bad prompt increments.
Add only standard model-card framing wording.
Leave the formal acceptance machine alone.
```
