# V3 Project Workspace Scene Subpages And Selection UX Patch Spec

## Status

Accepted patch document after document 45 user acceptance review.

This patch does not change the V3 foundation:

```text
V3 base
  -> Project
      -> Template
          -> Scenario Pack
              -> Project-scoped Job
```

It fixes the product experience inside an already-open project.

## User Acceptance Problems

The current document 45 implementation has four visible problems:

1. The four "continue this project" cards all open the same workbench, so the
   cards feel fake and the user cannot tell what each card is for.
2. Generated images are visible, but selecting a preferred image is not obvious.
   After a local service restart, restored generated images can be displayed but
   cannot reliably enter positive project context.
3. The project page shows the original user request, but not what V3 did with
   it: the plain workflow, optimized visual direction, final provider prompt, or
   the reason consistency can be maintained.
4. The child workbench still feels like a developer console. It exposes too many
   controls at once and does not follow the beginner-facing, image-first Project
   Mode principle.

## Product Principle

The project homepage is not an operation console.

It must contain only:

```text
project overview
generated images
confirmed references
plain workflow/artifacts
navigation cards
```

Each navigation card opens a different child scene. A child scene shows only the
controls and explanations needed for that task.

## Four Child Scenes

### Scene 1: Brief And Generate

Purpose:

```text
Tell V3 what to make next.
```

Visible content:

- simple request textarea
- optional purpose preset
- optional reference upload
- optional brand/feeling fields
- E-Commerce-only product fields only when the project template is E-Commerce
- primary generate button

Must hide:

- result board
- select controls
- brand memory save controls
- raw debug data

Beginner copy:

```text
写一句你想要什么图。V3 会自动整理画面方向和生成用提示词。
```

### Scene 2: Review Images

Purpose:

```text
Look at generated images and decide whether any direction is useful.
```

Visible content:

- current generated image cards
- enlarge/download
- "设为后续参考" button on each image
- "不喜欢这个方向" feedback button on each image
- a plain summary of what V3 completed

Must hide:

- prompt textarea
- upload fields
- brand memory save form

### Scene 3: Confirm Direction

Purpose:

```text
Choose the image direction that future jobs should remember.
```

Visible content:

- image-choice tiles
- selected/unselected state
- one-click select buttons
- selected reference board summary
- what will be remembered next time

Must support:

- selecting one specific candidate by `selected_candidate_id`
- selecting restored generated outputs after service restart by reading
  `ProductJobStatus` restored from `V3GeneratedOutputStore`
- removing an already selected reference from positive context

### Scene 4: Continue Or Save

Purpose:

```text
Use confirmed direction to continue the project or save the style for later.
```

Visible content:

- same-style continuation starter
- upload-new-reference continuation starter
- save Brand Memory action when selected references exist
- clear explanation of what will be reused

Must hide:

- first-generation clutter
- irrelevant template switchers
- provider/model/job implementation labels

## Project Output Board Patch

Generated image cards on the project homepage must be actionable:

- image preview
- download
- set as project reference
- mark as disliked direction
- visual selected state when already selected

The empty confirmed reference card must say what to do, not merely report
"0 items":

```text
还没有确认参考。
在上方图片卡点"设为后续参考"，V3 后续会沿着它继续。
```

## Restored Job Selection Patch

When the service restarts, `ProductJobRecord` may be gone while generated image
files still exist in `V3GeneratedOutputStore`.

Required behavior:

1. `GET /jobs/{job_id}` can restore a generated `ProductJobStatus` from output
   files.
2. Project selection must use that restored status if the in-memory selection
   path returns `not_found`.
3. The selected candidate/output must become:
   - `project.selected_output_refs`
   - active generated `ProjectReferenceAsset`
   - selected output state
   - positive `ProjectContextPackage.selected_output_assets`
4. Timeline records a plain-language selection event.

## Workflow And Prompt Artifact Patch

The artifact drawer must become useful but still beginner-friendly.

Collapsed label:

```text
工作流与提示词
```

Cards inside:

1. What V3 understood
2. How V3 optimized the direction
3. How consistency is maintained
4. Final prompt details

Display policy:

- Always show plain workflow steps.
- Show optimized direction and style notes when available.
- Show final provider prompt only inside a collapsed "高级查看" block.
- For restored historical outputs where the prompt text was not persisted, show
  a truthful fallback:

```text
这是从本地图片文件恢复的历史结果。图片和项目关系已恢复，但当时的完整提示词没有保存在图片文件中。
```

Future generated outputs should persist:

- compiled visual direction
- final provider prompt
- negative constraints
- style notes
- layout notes

These are for optional review/export only. Normal UI still stays image-first.

## Frontend Implementation Map

Primary files:

```text
src_skeleton/app/static/index.html
src_skeleton/app/static/styles.css
src_skeleton/app/static/app.js
tests/test_v3_commercial_frontend_shell.py
```

Required additions:

- `v3SubpageBody` container
- scene renderers:
  - `renderV3BriefScene`
  - `renderV3ReviewScene`
  - `renderV3SelectScene`
  - `renderV3ContinueScene`
- output actions:
  - `selectV3OutputItem`
  - `rejectV3OutputItem`
- artifact helpers:
  - `v3WorkflowArtifact`
  - `v3PromptArtifact`
  - `renderV3WorkflowArtifacts`

Rules:

- Subpage scene changes must not navigate away from the project page.
- Template switching remains forbidden inside an existing project.
- `v3ProjectOutputBoard` and `v3ResultBoard` must both expose image selection.
- The old full grid may be reused internally, but only the active scene should
  be visible.
- Beginner-facing text must describe outcomes, not internal implementation.

## Backend Implementation Map

Primary files:

```text
alchemy_creative_agent_3_0/app/project_mode/service.py
alchemy_creative_agent_3_0/app/product_api/service.py
alchemy_creative_agent_3_0/app/generation_router/providers.py
alchemy_creative_agent_3_0/tests/test_v3_project_mode.py
```

Required additions:

- Project selection fallback from restored `ProductJobStatus`
- Persist final provider prompt metadata for future generated outputs
- Include prompt/workflow summary in job status metadata when available

Do not expose API keys, provider credentials, raw local file paths, or internal
debug payloads in beginner-facing UI.

## Acceptance Tests

Backend:

- restored generated job can be selected into a project after service restart
- selected restored output appears in project context
- output store persists final prompt metadata for new generated outputs

Frontend/static:

- four scene renderer functions exist
- subpage body exists and is scene-driven
- project output cards contain select and dislike actions
- result cards contain select action
- workflow artifact renderer exists
- visible normal V3 copy avoids forbidden engineering labels

Browser QA:

- open V3
- open a project with generated images
- confirm project card has thumbnails
- click each of the four step cards
- confirm each child scene has different title/body/actions
- select one generated image
- confirm "confirmed references" changes from empty to at least one reference
- open workflow/prompt drawer and confirm plain workflow is visible

## Audit Before Coding

This patch is acceptable only if:

- it preserves Project Mode architecture
- the homepage stays simple
- each step card has a distinct purpose
- selected image context works after service restart
- workflow/prompt details are optional and folded
- V3 remains independent from V1/V2/Lab
- tests cover the restored-output path and frontend scene contracts
