# V3 Suite Brain Shot-Materialization Correction

Status: implemented and locally validated against the prior project; the first
post-fix pixel run still collapsed the second shot into a near-clone, and the
authority correction below resolved that conflict on the next stable run

## Objective

Make a fresh `general_template` `delivery_suite` run turn the frozen neutral
variation contract into visibly different shot duties. A non-primary output
that carries `viewpoint`, `pose`, `gesture`, or `context` must not be satisfied
by a crop, scale, detail, or depth-of-field change alone. The same subject,
style, explicit scene, wardrobe, lighting, and other protected user choices
must remain intact.

The target flow remains:

```text
neutral variation contract -> Remote Brain shot plan -> complete canonical prompt -> renderer
```

The Remote Brain remains the only author of the complete provider prompt.

## Observed mismatch

At baseline commit `7dd55d82525406d12dda06ce52e1937083761793`, a fresh local
run for project `project_e4dd268d36` used a contract whose second row contained
`viewpoint` and `pose`. The two received images were both frontal, near-camera
shots with the same bench interaction and forward-leaning pose; the second
image mainly changed crop/distance and detail. The persisted `image_set_plan`
also described the set as changing only shooting scale. Both outputs passed
the existing mode review because that review checked role/contract metadata,
not whether the Brain-authored shot text materially realized the non-neutral
axes.

The transport, contract digest, Brain receipts, provider call, pixel receipt,
and general scene quality were all valid. The defect is therefore semantic
materialization at the Brain prompt boundary, not provider availability,
contract transport, persistence, or image-pixel admission.

## Historical reference and boundary

The pre-upload baseline (`c75e8a37`) documented useful principles: a suite has
purposeful image duties, a side/three-quarter lane changes body/head angle, a
wide/context lane changes scene duty, and a batch must not repeat the same
pose, angle, crop, and expression as cloned stills. Those principles are
reusable evidence only.

They do not authorize restoring hard-coded portrait/ecommerce recipes to the
shared General Template, changing the public variation schema, or appending a
local Provider prompt suffix. Current V3 governance keeps scene-specific
deliverables in specialized templates and keeps complete renderer wording
Brain-owned.

## Correction model

The contract's axes are neutral semantic obligations. The Brain needs an
explicit, shared interpretation of their visual effect:

- `viewpoint` changes the camera/subject view or visible face/body plane. The
  difference must be visible at a glance when outputs are compared: a clear
  three-quarter or side relationship, or another decisive camera/subject
  orientation that changes the visible face/torso plane; a slight right/left
  wording, crop, or camera-distance change alone is insufficient.
- `pose` changes the body's arrangement, weight, torso/head relationship, or
  interaction with a visibly different silhouette, shoulder line, limb
  relationship, or contact geometry while preserving the same subject and
  core user intent. A tiny weight shift or detail emphasis alone is
  insufficient.
- `gesture` changes the meaningful hand/arm/action relationship to the scene.
- `context` changes the subject/environment relationship or scene duty while
  preserving the same requested visual world.
- `framing`, `scale`, `detail`, and `depth` are presentation changes only and
  cannot stand in for a requested shot-changing axis.

For a multi-output `delivery_suite`, the Brain must make every non-primary
row carrying a shot-changing axis materially distinct in the `image_set_plan`
and in its complete canonical prompt. The decisive shot change must be stated
first; the row must not be described as the same pose with a closer crop.
Controlled variation may adapt an explicit core action rather than discard it.
It must preserve protected current-request meaning and must not copy axis
names, role metadata, or local recipes into renderer wording.

## Minimal implementation

1. Strengthen the shared Brain planning and finalization instructions with the
   neutral axis semantics, visible-at-a-glance threshold, decisive
   three-quarter/side guidance, and the no-crop-only rule.
2. Keep the existing typed contract, digest, role catalog, Provider authority,
   review thresholds, and public API unchanged.
3. Add deterministic payload-contract tests proving the instructions are
   present for General multi-image requests and absent from specialized paths
   as a local role recipe. Keep existing isolation assertions intact.
4. Run the exact prior Japanese project prompt locally in a fresh job and
   inspect both persisted final prompts and pixels. Acceptance requires good
   scene/beauty/realism plus a clear shot-family difference, not merely a
   passing metadata receipt.

## Non-goals

- No provider-side prompt append, keyword matcher, or image post-process.
- No change to user prompt fidelity, reference ownership, Human Realism, or
  quality-review thresholds.
- No restoration of Doc58/59/62 scenario-specific wording into the General
  runtime.
- No deployment until the new local real-output evidence is satisfactory.

## Acceptance evidence

The fixed version is eligible for GitHub/VPS delivery only when:

1. Focused contract/payload tests and the affected compatibility tests pass.
2. The local fresh run completes with two certified real outputs. Completed by
   `job_72e10548a6`: outputs
   `v3_output_077ac3527f8543419ef4` and
   `v3_output_5500e8242881417dae8e`, both `1024x1536`, with real-pixel review
   and mode-differentiation review passing.
3. The persisted Brain shot plan and canonical prompts contain distinct,
   concrete shot directions consistent with their contract rows.
   The second canonical prompt starts with a right-front close three-quarter
   view and specifies a visible torso-plane, shoulder-line, and elbow change.
4. Pixel inspection shows the outputs are one coherent project but not the
   same frontal pose/crop with only scale or detail changed. The first output
   is the original frontal bench-supported presentation; the second is a
   visibly rotated, closer three-quarter composition with a different body
   plane and readable role separation.
5. The fixed commit is audited, pushed to `origin/main`, and the VPS is
   verified at that exact commit and healthy.
