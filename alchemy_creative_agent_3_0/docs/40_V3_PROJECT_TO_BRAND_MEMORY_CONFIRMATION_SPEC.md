# 40 V3 Project To Brand Memory Confirmation Spec

This document defines how a V3 project may contribute learnings to long-term
Brand Memory.

Brand Memory is long-term. Project memory is local to one design chain. They
must not be mixed silently.

## 1. Purpose

V3's long-term value is high-consistency design chains.

There are two memory levels:

```text
Project Memory
  The state of one project: selected outputs, references, avoid notes, timeline.

Brand Memory
  A reusable long-term brand profile that can influence future projects.
```

This phase adds an explicit confirmation flow from Project Memory to Brand
Memory.

## 2. Non-Goals

Do not automatically save every selected image into Brand Memory.

Do not force every project to have a brand.

Do not overwrite a brand profile without review.

Do not let E-Commerce activation depend on this phase unless the user wants
cross-project brand consistency for commerce.

## 3. Activation Preconditions

Only show Brand Memory save actions when:

```text
project has at least one selected output or active reference
project has a meaningful goal summary
project is not currently generating
```

If no brand profile exists, allow:

```text
create a new brand memory from this project
```

If a brand profile exists, allow:

```text
add this project's confirmed direction to brand memory
```

## 4. User-Facing Flow

### 4.1 Entry Point

Place the action in the project detail page, not on V3 home.

Suggested button copy:

```text
保存为品牌风格
```

Alternative copy:

```text
以后继续沿用这个风格
```

### 4.2 Review Modal

The modal must show a proposed memory summary before saving.

Required sections:

```text
这个风格适合什么
以后要保持什么
以后尽量避免什么
参考了哪些图片
```

Example:

```text
适合: 清爽饮品宣传、社媒封面、活动海报
保持: 明亮自然光、浅色背景、产品主体清晰、留出文案空间
避免: 暗色氛围、杂乱桌面、过度卡通化
参考: 已选中的 2 张项目图片
```

### 4.3 User Edit

The user may edit:

```text
brand name
style summary
keep notes
avoid notes
usage scenes
```

The user should not edit raw JSON.

### 4.4 Confirmation

The user clicks:

```text
确认保存
```

Only after this click may Brand Memory be changed.

## 5. API Contract

### 5.1 Create Brand Memory Proposal

```text
POST /api/v3/creative-agent/projects/{project_id}/brand-memory/proposal
```

Request:

```text
target_brand_id: string | null
mode: "create" | "append"
```

Response:

```text
proposal_id
project_id
target_brand_id
mode
brand_name_suggestion
style_summary
keep_notes
avoid_notes
usage_scenes
reference_output_ids
reference_asset_ids
created_at
```

Behavior:

```text
read project context
use selected outputs and active references only
include active avoid feedback
do not write Brand Memory
```

### 5.2 Confirm Brand Memory Proposal

```text
POST /api/v3/creative-agent/projects/{project_id}/brand-memory/confirm
```

Request:

```text
proposal_id
edited_brand_name
edited_style_summary
edited_keep_notes
edited_avoid_notes
edited_usage_scenes
```

Response:

```text
brand_id
memory_update_applied: true
updated_at
plain_summary
```

Behavior:

```text
validate proposal belongs to project
validate user-confirmed edited fields
create or append BrandProfile
append project timeline item
return user-facing summary
```

### 5.3 Cancel Proposal

No backend write is required for cancellation.

If proposal drafts are persisted, mark them:

```text
status: "cancelled"
```

## 6. BrandProfile Update Rules

When creating a new BrandProfile:

```text
brand name comes from user edit or project title
visual tone comes from confirmed direction
color palette comes only from selected/reference summaries if available
layout preference comes from selected outputs if summarized
rejected style tags come from active avoid feedback
```

When appending to an existing BrandProfile:

```text
append new confirmed notes
deduplicate repeated notes
preserve existing rejected style tags
do not remove existing brand rules unless user explicitly edits them in a future brand manager
```

## 7. Project Timeline

After confirmation, append a visible timeline item:

```text
已保存为品牌风格
```

Summary example:

```text
以后可以在新项目中继续沿用这组清爽明亮的视觉方向。
```

Do not expose memory update JSON.

## 8. Frontend States

```text
brand_save_hidden
brand_save_available
proposal_loading
proposal_ready
proposal_saving
proposal_saved
proposal_failed
```

### 8.1 brand_save_hidden

Condition:

```text
no selected output
no active reference
```

No button is shown.

### 8.2 brand_save_available

Condition:

```text
project has selected output or active reference
```

Show:

```text
保存为品牌风格
```

### 8.3 proposal_ready

Show the review modal and editable fields.

### 8.4 proposal_saved

Show:

```text
已保存。以后新项目也可以沿用这个风格。
```

## 9. Guardrails

Mandatory rules:

```text
No automatic Brand Memory write after generation.
No automatic Brand Memory write after selection.
No Brand Memory write from unselected candidates.
No Brand Memory write from rejected outputs except avoid notes after confirmation.
No cross-project context read unless user chooses a brand.
```

## 10. Implementation Steps

Recommended sequence:

```text
1. Add proposal schema.
2. Add proposal builder service that reads ProjectContextPackage.
3. Add proposal route.
4. Add confirm route.
5. Integrate with existing BrandProfile store.
6. Add project timeline event after confirmation.
7. Add project detail UI button and modal.
8. Add tests for no automatic writes.
9. Add tests for confirmed writes.
```

## 11. Required Tests

Backend:

```text
test_brand_memory_proposal_does_not_write_brand
test_brand_memory_confirm_creates_new_brand
test_brand_memory_confirm_appends_existing_brand
test_unselected_outputs_excluded_from_brand_proposal
test_rejected_feedback_enters_avoid_notes_only_after_confirmation
test_project_timeline_records_brand_memory_confirmation
```

Frontend:

```text
brand save button hidden before selected reference
brand save button visible after selected output
proposal modal shows beginner-facing fields
confirm save shows success copy
cancel does not write brand memory
normal UI does not show BrandProfile JSON
```

## 12. Acceptance Criteria

This phase is complete when:

```text
1. Project Memory remains local unless user confirms saving.
2. Brand Memory proposal is understandable to a beginner.
3. User can edit the proposed brand summary before saving.
4. Confirmed save updates BrandProfile.
5. Selection alone does not update Brand Memory.
6. Generation alone does not update Brand Memory.
7. All project continuation tests remain green.
```
