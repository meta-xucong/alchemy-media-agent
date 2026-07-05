# 57 V3 E-Commerce Lifestyle Count And Watermark QA Spec

## 1. Status And Authority

This document adds three targeted quality upgrades for the next V3 E-Commerce
and commercial-output phase:

```text
1. product suite lifestyle images must become more real-world / outdoor /
   in-use when the user or slot asks for lifestyle, instead of defaulting to
   conservative premium studio shots
2. E-Commerce Template image count must be unified with the same user-facing
   generation-count control used by V3 workbench
3. faint AI-generated watermarks, signatures, badges, or corner marks must be
   detected more strictly and either hidden, blocked, or retried under Doc53
```

Authority chain:

```text
Doc42:
  Owns E-Commerce Template project-mode unfreeze and business suite structure.

Doc52:
  Owns broader suite direction, curation, and commercial-quality loop.

Doc53:
  Owns automatic retry guardrails and append-only retry execution.

Doc55:
  Owns real post-generation inspection and review merge.

Doc57:
  Owns the three quality corrections above: lifestyle realism, ecommerce count
  control unification, and strict faint watermark QA.
```

If there is a conflict about these three topics, Doc57 wins over older generic
wording in documents `42`, `52`, `53`, and `55`.

Doc57 does not:

```text
rewrite Project Mode
replace ScenarioRuntime
replace Product API
replace the Visual Capability Cluster
call V1/V2 runtime code
expose provider/model engineering controls to beginner users
```

## 2. Problem Summary

### 2.1 Lifestyle outputs are too studio-like

Observed problem:

```text
Product suite "lifestyle" variations often remain premium studio product
photography. They look polished, but not enough like real outdoor, home, street,
travel, kitchen, desk, gym, cafe, or in-use commercial scenes.
```

Target:

```text
When a slot is lifestyle / scenario / in-use / outdoor / social-life oriented,
V3 should create a real-world usage scene while preserving product identity.
```

### 2.2 E-Commerce count control is not unified

Observed problem:

```text
The E-Commerce Template can internally plan a full suite of business slots, but
the V3 workbench already exposes a simple "生成数量" control. These two concepts
are not fully unified.
```

Target:

```text
User-facing generation count controls how many images are generated now.
E-Commerce suite strategy decides which slots are most useful within that
count, not an uncontrolled fixed full-suite count.
```

### 2.3 Faint AI watermark traces are not strict enough

Observed problem:

```text
Some outputs may contain very faint lower-corner "AI generated" style marks,
signature-like traces, badges, or watermark residue. Current review mentions
watermark_or_signature, but faint corner artifacts are not strict enough as a
commercial blocker.
```

Target:

```text
Any visible or faint generated watermark/signature/badge/corner mark must be
treated as not commercially clean. The default UI should not recommend it as a
good result. If retry is safe, V3 should retry with a stronger patch.
```

## 3. Architecture Fit

All three upgrades remain inside existing V3 structure:

```text
E-Commerce suite strategy:
  ecommerce Scenario Pack / Visual Capability Cluster policy child

count unification:
  Project API metadata + ScenarioSelection parameters + ecommerce planner

watermark QA:
  Visual Capability Cluster post-generation inspection + Doc53 retry executor
```

No new central framework is required.

## 4. Lifestyle Realism Upgrade

### 4.1 Add lifestyle scene intent policy

Suggested location:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/ecommerce_lifestyle.py
```

or as a child policy inside the existing ecommerce planner if the current pack
already owns slot recipes.

Responsibilities:

```text
detect lifestyle/scenario/in-use slot
choose real-world scene category from product category and user input
add environmental realism constraints
avoid over-defaulting to studio/pedestal/background-only shots
preserve product identity and commercial clarity
```

### 4.2 Lifestyle scene categories

Scene categories should be selected from product/use context:

```text
home_use
kitchen_table
bathroom_counter
bedroom_vanity
office_desk
cafe_table
street_snap
outdoor_summer
travel_bag
gym_locker
camping_picnic
car_interior
pet_home
family_scene
creator_flatlay_in_use
```

For each category, prompt should include:

```text
real environment
natural object placement
human use or implied use when appropriate
ambient light or location-appropriate lighting
minor natural imperfections
product remains clear and recognizable
commercially clean composition
```

### 4.3 Studio-vs-lifestyle balance

E-Commerce suite should not eliminate studio shots. It should balance:

```text
main image:
  clean studio / white / neutral commercial shot when platform needs it

feature/detail image:
  studio or controlled setting is acceptable

lifestyle/scenario image:
  must be real-world, outdoor, home, street, travel, desk, kitchen, gym, cafe,
  or other plausible usage context

social cover:
  may be editorial / lifestyle / campaign-like, not only studio product hero
```

### 4.4 Prompt rules

For lifestyle slots, add:

```text
show the product naturally used or placed in a believable real-world setting
avoid pure studio pedestal composition unless explicitly requested
include natural environment cues, ambient light, and realistic spatial context
keep product shape, material, label, color, and proportions accurate
```

Negative guidance:

```text
avoid sterile studio-only scene for lifestyle slot
avoid empty showroom look
avoid floating product
avoid unrelated props that confuse product identity
avoid random text, labels, watermarks, or fake badges
```

### 4.5 Beginner-facing wording

Default UI should not expose technical slot policy. It may say:

```text
已把生活方式图改成更真实的使用场景
```

or:

```text
这张更偏真实场景，适合社媒和详情页氛围图
```

## 5. E-Commerce Count Control Unification

### 5.1 Product rule

The existing workbench count control is authoritative for the current run:

```text
requested_image_count
```

E-Commerce suite planner must respect it:

```text
requested_image_count = 1:
  choose the single most useful slot for the user request

requested_image_count = 2:
  choose two complementary slots

requested_image_count = 3:
  choose a compact mini-suite

requested_image_count = 4:
  choose the strongest four-slot suite
```

Do not silently generate six business slots when the user selected two.

### 5.2 Slot selection priority

Slot priority must adapt to prompt, uploaded product type, and platform.

Default priority:

```text
1. hero/main commercial image
2. lifestyle/in-use scene
3. feature/selling-point image
4. detail/material/texture image
5. trust/package/comparison image
6. social cover/ad image
```

If user says:

```text
白底 / 主图
```

prioritize:

```text
main image, clean product image
```

If user says:

```text
生活方式 / 外景 / 使用场景 / 社媒
```

prioritize:

```text
lifestyle scene, social cover, hero
```

If user says:

```text
卖点 / 功能 / 参数
```

prioritize:

```text
feature image, detail image, hero
```

### 5.3 Data flow

Frontend already sends:

```text
metadata.requested_image_count
metadata.requested_image_size
suite_slot_request
```

Implementation must ensure:

```text
ProjectModeService passes requested_image_count into ecommerce scenario parameters
EcommerceScenarioPackPlanner receives requested_count
planner trims or expands planned slots to requested_count
generate loop candidate/image count matches requested_count
status metadata exposes requested_image_count and generated_image_count
```

### 5.4 Count vs slot request conflict

If explicit `suite_slot_request` has more slots than requested count:

```text
generate only requested_count slots now
store the remaining slots as future suggested actions
do not silently exceed requested count
```

If `suite_slot_request` has fewer slots than requested count:

```text
fill remaining slots with planner-selected complementary slots
```

### 5.5 Beginner-facing wording

Show only simple text:

```text
本次生成 3 张：主图、生活方式图、卖点图
```

Do not show:

```text
suite_slot_request
scenario_parameters
planner internals
```

## 6. Strict Faint Watermark QA

### 6.1 Expand issue taxonomy

Doc55 already has:

```text
watermark_or_signature
```

Doc57 adds stricter sub-issue codes:

```text
faint_corner_watermark
ai_generated_badge_trace
signature_like_artifact
lower_right_mark_artifact
third_party_aigc_metadata
provider_provenance_mismatch
product_label_drift
product_label_unreadable
product_logo_or_label_obscured
commercial_cleanliness_failure
```

These map to:

```text
watermark_or_signature
```

for Doc53 retry compatibility.

### 6.2 Inspection behavior

VisionOutputInspector must check:

```text
lower-right corner
lower-left corner
top-right corner
top-left corner
image edges
semi-transparent text traces
signature-like strokes
AI / generated / watermark-like badges
logo-looking artifacts that were not uploaded or requested
third-party AIGC metadata in the saved output file
missing expected OpenAI provenance signal when an OpenAI GPT image route was requested
visible product label/logo drift, unreadability, or obstruction when a product reference is supplied
```

The first implementation may combine:

```text
metadata test signals
OCR or image-text detection if available
corner crop heuristic
simple contrast/edge artifact heuristics
vision model review when configured
manual fake issue metadata for tests
```

But low confidence must be handled carefully:

```text
high confidence watermark:
  fail_retryable if patch exists

medium confidence faint watermark:
  warning or fail_retryable depending on strictness mode

low confidence ambiguous texture:
  manual_review, do not auto retry
```

### 6.3 Retry patch

For watermark/signature issues:

```json
{
  "prompt_additions": [
    "Generate a clean commercial image with no watermark, signature, badge, AI-generated mark, logo-like artifact, or corner stamp.",
    "Keep all corners and edges clean and free of text-like marks."
  ],
  "negative_additions": [
    "watermark",
    "signature",
    "AI generated mark",
    "badge",
    "corner text",
    "lower-right logo",
    "semi-transparent text",
    "random letters"
  ],
  "artifact_repair": [
    "remove faint corner marks and any text-like residue"
  ],
  "user_visible_reason": "V3 发现图片边角疑似有水印痕迹，已补做一张更干净的版本。"
}
```

For third-party AIGC metadata or provider provenance mismatch:

```json
{
  "prompt_additions": [
    "Generate a clean commercial image with no third-party AIGC label, metadata badge, provider mark, or source stamp.",
    "Keep all corners and edges clean and free of generated-origin text or badge traces."
  ],
  "negative_additions": [
    "third-party AIGC label",
    "AI generated badge",
    "provider provenance mark",
    "source stamp",
    "corner text",
    "metadata badge"
  ],
  "artifact_repair": [
    "remove any third-party AIGC label, source mark, and provider badge trace"
  ]
}
```

Retry remains governed by Doc53:

```text
append-only
budget-limited
no provider/account/network retry
same issue repeated -> stop
```

### 6.4 Default curation behavior

If watermark/signature issue is high confidence:

```text
do not recommend as best output
hide from default recommended group if cleaner alternatives exist
show only in folded history/details
trigger retry when safe
```

If medium confidence:

```text
show warning in folded review details
prefer cleaner alternatives
retry only if strict mode or issue is clear enough
```

## 7. Implementation Plan

### Phase 1: Documentation and authority notes

Add Doc57 and update documents `42`, `52`, `53`, and `55` with authority notes.

### Phase 2: E-Commerce lifestyle policy

Add or update ecommerce suite policy to:

```text
classify lifestyle slots
choose real-world scene categories
inject lifestyle prompt/negative rules
preserve product identity locks
```

### Phase 3: Count unification

Update:

```text
frontend payload audit
ProjectModeService ecommerce scenario parameters
EcommerceScenarioPackPlanner
ProductJobStatus metadata
tests
```

Ensure:

```text
requested_image_count controls this run
generated slots equal requested count unless provider failure occurs
slot summary is beginner-facing
```

### Phase 4: Faint watermark QA

Update:

```text
visual_cluster/vision_inspector.py
visual_cluster/quality_review.py
product_api/service.py retry bridge only if needed by metadata mapping
```

Add strict issue mapping and retry patches.

### Phase 5: Frontend display

No new default engineering controls.

Add folded friendly summaries:

```text
已检查水印/边角文字
已生成更真实的生活方式场景
本次生成 N 张：...
```

## 8. Tests

### 8.1 Lifestyle tests

```text
ecommerce lifestyle slot prompt includes real-world setting
outdoor/social prompt avoids studio-only lifestyle
main image can remain clean studio while lifestyle slot is real scene
product identity constraints remain present
```

### 8.2 Count tests

```text
requested_image_count=1 returns one ecommerce slot/image
requested_image_count=2 returns two ecommerce slots/images
requested_image_count=4 returns four ecommerce slots/images
suite_slot_request longer than requested_count is trimmed
suite_slot_request shorter than requested_count is filled
status metadata exposes requested_image_count and generated_image_count
```

### 8.3 Watermark tests

```text
fake faint_corner_watermark becomes fail_retryable or warning by confidence
fake ai_generated_badge_trace maps to watermark_or_signature
third_party_aigc_metadata becomes fail_retryable when confidence is high
provider_provenance_mismatch becomes fail_retryable for OpenAI GPT image routes
product_label_drift and product_label_unreadable become fail_retryable when label/logo preservation is required by the slot
retry patch contains no-watermark and clean-corner guidance
retry output is appended, not overwritten
provider error does not become watermark retry
low-confidence ambiguous texture becomes manual_review, not retry
recommended outputs exclude high-confidence watermark images when cleaner
alternatives exist
```

### 8.4 Frontend tests

```text
UI does not expose engineering fields
folded review can show watermarks checked
ecommerce count summary uses beginner language
no scenario_parameters or suite_slot_request appears in beginner UI
```

## 9. Acceptance Criteria

This phase is complete when:

```text
1. lifestyle ecommerce images are visibly more real-world/in-use when requested
2. requested_image_count controls ecommerce outputs for the current run
3. faint watermark/signature/corner marks are detected more strictly
4. retry uses Doc53 guardrails and appends outputs
5. default UI remains beginner-friendly
6. General Template behavior is not polluted by ecommerce slot language
```

Commercial quality target:

```text
E-Commerce suites should contain a credible mix of clean commercial shots and
real-use lifestyle images, generate only the number of images the user asked
for, and avoid recommending any output with watermark-like artifacts.
```
