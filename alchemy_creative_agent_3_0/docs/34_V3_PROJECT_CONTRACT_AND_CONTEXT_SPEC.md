# 34 V3 Project Contract And Context Specification

Current compatibility note:

```text
Document 52 extends ProjectContextPackage additively for post-generation visual
inspection, retry execution, suite variation planning, and output curation.

This document remains the base Project Mode contract. Doc52 fields must be
optional/additive and must not break existing ProjectContextPackage readers.
```

This document defines the product contracts for V3 Project Mode.

The contracts are application-level. They must not expose provider controls or
internal agent implementation details to the public API.

---

## 1. Route Contract

Add these routes under the existing V3 namespace:

```text
GET  /api/v3/creative-agent/projects
POST /api/v3/creative-agent/projects
GET  /api/v3/creative-agent/projects/{project_id}
POST /api/v3/creative-agent/projects/{project_id}/jobs
GET  /api/v3/creative-agent/projects/{project_id}/timeline
POST /api/v3/creative-agent/projects/{project_id}/jobs/{job_id}/generate
POST /api/v3/creative-agent/projects/{project_id}/jobs/{job_id}/select
```

Keep existing routes:

```text
POST /api/v3/creative-agent/jobs
GET  /api/v3/creative-agent/jobs/{job_id}
POST /api/v3/creative-agent/jobs/{job_id}/generate
POST /api/v3/creative-agent/jobs/{job_id}/select
GET  /api/v3/creative-agent/history
```

The Project API should call the existing job service. It must not duplicate the
creative planning/generation runtime.

Current storage rule:

```text
PersistentProjectStore -> .media_storage/v3_projects/{project_id}/project.json
PersistentProjectStore -> .media_storage/v3_projects/{project_id}/timeline.json
```

This is an application-layer store for project continuity. It does not replace
ProductJobRecord, generated output storage, upload storage, provider storage,
or Brand Memory.

---

## 2. ProjectRecord

`ProjectRecord` is the user-facing container for one coherent design chain.

Required fields:

```text
project_id
title
status
primary_template_id
allowed_template_ids
linked_brand_id
user_goal
short_summary
confirmed_style_summary
selected_output_refs
uploaded_asset_refs
rejected_direction_notes
timeline_refs
created_at
updated_at
metadata
```

Recommended status values:

```text
draft
active
archived
blocked
```

Rules:

1. `project_id` must be V3-owned, for example `project_<short_uuid>`.
2. `primary_template_id` is usually `general_template` in the current phase.
3. `allowed_template_ids` must include only templates enabled for this project.
4. The current phase should set `allowed_template_ids` to
   `["general_template"]` unless a later accepted phase activates more
   templates.
5. `selected_output_refs` may contain only user-selected or restored outputs.
6. `rejected_direction_notes` should influence future context negatively.

---

## 3. ProjectTimelineItem

The timeline is the beginner-friendly history inside a project.

Required fields:

```text
timeline_item_id
project_id
item_type
title
summary
job_id
asset_ids
candidate_ids
selected_output_refs
created_at
metadata
```

Recommended `item_type` values:

```text
project_created
reference_uploaded
job_created
job_generated
candidate_selected
style_continued
text_updated
export_created
note_added
```

The UI should show timeline items in product language:

```text
创建了项目
上传了参考图
生成了一组创意图
选中了 1 张作为后续风格
继续生成了同风格素材
```

The UI must not show route names, raw metadata, provider messages, or job ids
as normal text.

---

## 4. ProjectContextPackage

`ProjectContextPackage` is the reusable context sent into future project jobs.

Required fields:

```text
project_id
context_version
goal_summary
template_id
linked_brand_id
confirmed_visual_tone
confirmed_color_logic
confirmed_layout_logic
selected_reference_assets
selected_output_assets
uploaded_reference_assets
required_text_or_facts
rejected_style_tags
negative_direction_notes
continuation_instruction
source_timeline_item_ids
created_at
metadata
```

Rules:

1. Build positive visual context from selected or explicitly restored outputs.
2. Build reference context from user-uploaded assets and their V3 upload roles.
3. Build negative context from rejected directions and user corrections.
4. Do not include unselected candidates as positive references.
5. Do not include V1, V2, or Alchemy Lab records unless a future V3 import tool
   explicitly imports them into V3-owned project assets.
6. Do not include provider-specific fields.

---

## 5. ProjectMemorySummary

`ProjectMemorySummary` is the compact user-facing summary shown on project
cards and project detail pages.

Recommended fields:

```text
project_id
title
goal
active_template_label
latest_thumbnail_urls
confirmed_style_chips
selected_asset_count
job_count
last_action_label
updated_at
next_suggested_actions
```

Example UI copy:

```text
已形成清爽、高级、留白多的新品宣传风格
已选 2 张图作为后续参考
可以继续生成同风格小红书封面
```

---

## 6. OutputRef

Use a normalized reference object for selected outputs.

Recommended fields:

```text
output_ref_id
source_type
project_id
job_id
asset_id
candidate_id
output_id
preview_url
thumbnail_url
download_url
selection_reason
selected_at
metadata
```

Allowed `source_type` values:

```text
selected_candidate
selected_asset
restored_project_output
imported_v3_job_output
```

Do not store raw provider response bodies in `OutputRef`.

---

## 7. Create Project Request

Minimum request:

```json
{
  "user_goal": "帮我做一组夏季新品宣传图，清爽、高级，适合小红书",
  "title": "夏季新品宣传",
  "primary_template_id": "general_template",
  "linked_brand_id": null,
  "uploaded_asset_ids": [],
  "metadata": {}
}
```

Validation:

1. `user_goal` is required.
2. `primary_template_id` defaults to `general_template`.
3. Current phase rejects active project creation for templates other than
   `general_template`.
4. Uploaded assets must be V3 upload ids.

---

## 8. Project Job Request

Minimum request:

```json
{
  "user_input": "继续同风格，做一张朋友圈海报",
  "template_id": "general_template",
  "uploaded_asset_ids": [],
  "use_project_context": true,
  "metadata": {}
}
```

The Project API converts this into the existing job request:

```text
CreateCreativeJobRequest
scenario_selection.scenario_id = general_creative
metadata.project_id = project_id
metadata.template_id = general_template
metadata.project_context_version = current context version
```

The exact code shape may use explicit fields later, but the first
implementation may use metadata to preserve backward compatibility.

---

## 9. Selection Rule

When the user selects a candidate or asset:

```text
selected output -> ProjectTimelineItem(candidate_selected)
selected output -> ProjectRecord.selected_output_refs
selected output -> next ProjectContextPackage
selected output -> optional Brand Memory proposal
```

Do not apply Brand Memory by default. The UI may offer:

```text
保存为品牌风格
仅用于当前项目
```

Default for the current phase:

```text
仅用于当前项目
```

---

## 10. Imported History Rule

Existing raw V3 job history can be used as a temporary source for project cards.

When a raw job history item is opened:

1. If it already has `project_id`, open that project.
2. If it has no `project_id`, create or hydrate a lightweight compatibility
   project.
3. Mark the project metadata as `created_from_legacy_job_history=true`.
4. Future continuation should create new project jobs, not mutate the legacy
   job.

---

## 11. Error And Fallback Rules

Use product-language errors:

```text
项目不存在 -> 这个项目没有找到
template locked -> 这个模板还未开放
no selected context -> 还没有已选图片，先生成并选中一张
asset missing -> 有参考图暂时不可用，请重新上传
```

Do not expose stack traces, route names, provider errors, or internal schema
names in the normal UI.

---

## 12. Acceptance Criteria

The contracts are complete when a future implementer can build Project Mode
without deciding:

1. which object owns user history,
2. how jobs attach to projects,
3. which outputs enter continuation context,
4. whether Brand Memory updates are automatic,
5. how General Template maps to Scenario Pack runtime.
