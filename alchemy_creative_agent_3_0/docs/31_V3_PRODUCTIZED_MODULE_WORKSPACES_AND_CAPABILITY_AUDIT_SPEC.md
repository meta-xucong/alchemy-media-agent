# 31 V3 Productized Module Workspaces And Capability Audit Specification

This document refines the V3 commercial frontend after documents `27`, `30`,
and the current E-Commerce generation closure.

Document `30` fixed the V3 entry surface: the first screen is card modules plus
V3-owned history. This document fixes the second-level workspace experience:
after a user clicks `General Creative` or `E-Commerce`, the two modules must
feel like different beginner-facing products, not the same engineering form
with a few hidden fields.

Project Mode note:

```text
Documents 32-37 wrap this workspace model in a Project layer. After Project
Mode, users should enter a project first, then open General Template inside
that project. E-Commerce is frozen during the Project Mode foundation phase and
must not create project jobs until a later accepted E-Commerce Project Mode
spec reactivates it.
```

Document 50 note:

```text
The V1/V2-derived shared capability audit in this document is now wrapped by
document 50. Future visual enhancement must be consolidated into one V3-native
Visual Capability Cluster under `app/shared_capabilities`. This document remains
valid for beginner-facing UI and productized workspace language, but document 50
is the authority for shared visual module ownership, cluster dispatch, and
strong verification.

Document 51 extends that same cluster with commercial consistency Pro behavior:
strong selected-image references, explicit identity/product/brand locks,
visual review, retry patches, best-output selection, and negative visual memory.
If this document's older capability-audit wording is less specific, use
document 51 for the implementation details.
```

---

## 1. Problem Found

The current V3 workspace is functionally usable, but the product language and
module separation are not mature enough:

```text
1. The side panel still exposes engineering-like planning and check language.
2. General Creative and E-Commerce share nearly the same visible composer.
3. The result area does not emphasize generated images strongly enough.
4. V1/V2-derived shared capabilities are not clearly audited as active backend
   helpers.
```

The target user is a beginner who wants to upload an image, type a simple
request, and get usable commercial images. They do not need to understand
capability modules, route names, prompt compilation, product-truth locks, or
export manifests.

---

## 2. Product Rule

V3 may keep one reusable workspace shell, but each active module must configure
that shell into a distinct product experience.

Required distinction:

```text
V3 Home
  -> New Project + recent V3 projects

Project Detail
  -> template cards
  -> active General Template workspace
  -> project timeline

General Creative Workspace
  -> poster / cover / brand visual / product-style creative images
  -> optional reference images
  -> optional brand/tone
  -> no marketplace, listing, keyword, competitor, or commerce pack language

E-Commerce Workspace
  -> locked in the Project Mode foundation phase
  -> visible as a future template card
  -> no project job creation until reactivated by a later accepted spec
```

The same backend central brain can perform the complex reasoning. The frontend
must show only the useful result of that reasoning in simple product language.

In Project Mode, `General Creative Workspace` should be interpreted as
`General Template Workspace inside Project Detail`.

---

## 3. Forbidden Beginner-Facing Language

Do not show these terms in the normal V3 workspace:

```text
provider
adapter
seed
sampler
ControlNet
ComfyUI
prompt compiler
capability module
closure check
product truth lock
Truth:
Selling point:
marketplace image set planner
job id
route
manifest
raw export filename list
```

Debug-only views may expose technical language later, but no debug surface is
part of this phase.

---

## 4. General Creative Workspace

### 4.1 User Promise

Use General Creative when the user wants:

```text
poster
social cover
brand key visual
campaign image
product-style hero visual without E-Commerce listing rules
```

Beginner copy examples:

```text
通用创意 Agent
适合海报、封面、活动图、品牌视觉。写一句需求，V3 会自动整理画面方向并出图。
```

### 4.2 Visible Controls

Show:

```text
quick-start cards:
  活动海报
  社媒封面
  产品感主图

main request textarea
optional reference image upload
optional brand/project name
optional desired feeling
generate creative image action
result board
simple outcome summary
```

Hide:

```text
platform selector
market selector
product parameter fields
keywords / roots
competitor reference field
risky claims field
E-Commerce suite planning panel
E-Commerce export panel
```

### 4.3 Summary Copy

The right panel should be titled:

```text
这次 V3 帮你完成了
```

Allowed summary examples:

```text
已理解这张图的使用场景
已整理画面风格和氛围
已参考你上传的图片
已保护需要保留的文字或主体
已检查生成结果是否符合需求
```

The UI must not show raw shared capability result labels.

---

## 5. Legacy Pre-Project E-Commerce Workspace

This section describes the pre-Project-Mode E-Commerce workspace. It is useful
historical context, but it must not be used to keep E-Commerce active during
the Project Mode foundation phase.

Project Mode rule:

```text
E-Commerce becomes a locked template card until a later accepted
E-Commerce Project Mode spec reactivates it.
```

### 5.1 User Promise

Use E-Commerce when the user wants:

```text
product main image
selling-point image
lifestyle/scenario image
detail/material image
trust/comparison image
ad cover or store image
```

Beginner copy examples:

```text
电商特调 Agent
适合商品主图、卖点图、详情页配图。上传商品图，写一句需求即可生成套图。
```

### 5.2 Visible Controls

Show:

```text
quick-start cards:
  一键电商套图
  平台上架套图
  参考风格复用

main request textarea
product/reference image upload
optional platform selector
optional target market input
optional brand/store tone
primary action: 生成电商套图
image-first suite result board
plain suite plan summary
```

Use a secondary details block for:

```text
product facts / facts that cannot be changed
keywords / roots
competitor or style reference notes
risky claims to avoid or verify
```

The secondary block must be visibly optional. A beginner should be able to skip
it and still generate a suite.

### 5.3 Summary Copy

Allowed summary examples:

```text
已识别商品主体和必须保留的信息
已把套图拆成主图、卖点图、场景图和信任图
已为每张图安排不同用途
已避免乱加文字、徽章和未经确认的宣传说法
```

If selling points are available, show them as product-language priorities, not
as raw `Selling point:` entries.

### 5.4 Result Board

The E-Commerce result board must prefer slot names over internal asset IDs:

```text
电商主图
卖点图 1
卖点图 2
场景图
细节证明图
信任背书图
投放封面
```

Each card should prioritize:

```text
generated image preview
slot label
plain purpose
download action
```

Do not show buyer-intent strings, business-goal enum strings, manifest
filenames, or job IDs by default.

---

## 6. V1/V2 Enhanced Capability Audit Rule

The V1/V2 advantages migrated in document `24` are backend capabilities. They
must not become visible frontend complexity.

Current ownership refinement:

```text
After document 50, these backend helpers should be treated as child modules of
the V3 Visual Capability Cluster, not as loose standalone helpers. They may
remain in their existing files during migration, but all visual enhancement,
visual reuse, reference binding, visual grammar, consistency guarding, and
output visual review must be dispatched through the cluster framework.
```

Expected active shared capability behavior in the pre-Project-Mode stage:

```text
General Creative:
  case retrieval and visual grammar help with blank-page creative direction
  uploaded images trigger asset role analysis and binding when present
  prompt constraints protect layout, subject, style, and exact text where relevant
  output review contributes plain warnings or quality hints

E-Commerce:
  uploaded product images trigger asset role analysis and product preservation
  product facts feed information integrity and prompt constraints
  scenario pack recipes turn commerce thinking into suite slots
  commerce critic and output review contribute plain warnings
```

Project Mode replacement:

```text
General Template remains the only active project-generation template.
E-Commerce shared capability behavior should not run from the normal Project
Mode UI until E-Commerce is reactivated by a later accepted spec.
```

Audit requirement:

```text
1. Tests or direct API probes must prove shared capability results are present
   in backend job records for both General Creative and E-Commerce.
2. Normal frontend copy must translate those effects into beginner language.
3. V3 must not import V1/V2 runtime modules or call V1/V2 job/generation APIs.
4. After document 50 implementation, static ownership audit must prove no
   reusable visual enhancement logic remains privately owned by Central Brain,
   PromptCompilerAgent, Project Mode, templates, or providers.
```

---

## 7. Legacy Implementation Steps

These steps document the pre-Project-Mode workspace polish. They should not be
used as the next implementation order after documents `32`-`37`.

Project Mode implementation order must follow:

```text
1. Project data/API layer
2. project-first V3 home
3. project detail shell
4. General Template project flow
5. E-Commerce locked-state enforcement
6. Project Mode audit and tests
```

### Step 1 - Documentation

1. Add this document.
2. Add it to `README.md`.
3. Add a V3.8D section to `13_STEP_BY_STEP_DELIVERY_PLAN.md`.

### Step 2 - HTML

1. Keep `v3HomeView` unchanged except for copy if needed.
2. Split workspace preset rows by scenario:
   - `v3GeneralPresetRow`
   - `v3EcommercePresetRow`
3. Add scenario-specific helper copy elements.
4. Move advanced E-Commerce fields into a secondary optional block.
5. Hide the visible job id in the beginner workspace.
6. Rename the side-panel title from technical planning language to a product
   outcome summary.
7. Hide the E-Commerce plan panel for General Creative.

### Step 3 - JavaScript

1. Add a scenario copy map for titles, intro text, placeholders, upload hints,
   primary action labels, and empty result states.
2. `renderV3ScenarioState()` must configure the visible workspace by scenario,
   not just hide a few fields.
3. `renderV3GeneralSummary()` must render plain outcome lines only.
4. `renderV3EcommerceSummary()` must render plain commerce suite outcomes only.
5. E-Commerce plan rows must use slot labels and simple purposes.
6. Export manifest details must not render by default in the beginner panel.
7. Result cards must prioritize preview image, slot/title, plain purpose, and
   download action.

### Step 4 - CSS

1. Keep the Alchemy Lab-like card-module style.
2. Make result cards visually image-first.
3. Ensure optional E-Commerce details are compact and clearly secondary.
4. Ensure mobile layout stacks without text overlap.

### Step 5 - Tests And Audit

1. Update frontend shell tests to assert productized copy.
2. Assert forbidden engineering copy does not appear in the V3 section/script.
3. Run shared capability tests from document `24`.
4. Run General Creative and E-Commerce scenario tests.
5. Run JS syntax, Python compile, diff check, and long-run state validation.

---

## 8. Legacy Acceptance Criteria

This phase is complete only when:

```text
1. V3 home still shows only template cards and V3 project history. The older
   job-history reading is superseded by documents `32`-`45`.
2. General Creative and E-Commerce open visibly different workspaces.
3. General Creative does not show commerce platform, keyword, competitor, or
   listing-style fields.
4. E-Commerce starts from product image + simple request and moves advanced
   details into an optional secondary area.
5. Generated images are the visual focus of the result board.
6. Side-panel summaries use beginner-friendly outcome language.
7. No raw capability/module/provider/job-id language appears in the normal V3
   workspace.
8. V1/V2-derived shared capabilities are verified as active backend helpers.
9. V3 still calls only `/api/v3/creative-agent/*` for V3 work.
10. Relevant backend, frontend, syntax, and audit checks pass.
```

Project Mode replacement acceptance criteria are defined in documents `35`,
`36`, and `37`. In the Project Mode foundation phase, success means:

```text
1. V3 home is project-first.
2. General Template is the only active generation template.
3. E-Commerce is visible but locked.
4. Project jobs include project context.
5. selected outputs drive continuation.
6. raw job history is no longer the primary user-facing history object.
```
