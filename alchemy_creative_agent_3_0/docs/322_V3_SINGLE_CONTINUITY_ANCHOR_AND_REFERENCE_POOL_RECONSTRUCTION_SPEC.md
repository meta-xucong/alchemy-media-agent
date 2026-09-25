# Doc322 - V3 Single Continuity Anchor And Reference Pool Reconstruction

状态：设计冻结，待实现

范围：V3 Foundation reference/continuity layer

前置依据：Doc45、Doc73、Doc93、Doc97、Doc281、Doc287、Doc306

本文件解决的问题：V3 当前同时存在自动首图锚点、用户选中成片、上传原图、视觉资产绑定、Provider 派生裁剪图等多个参考来源。逻辑参考与 Provider 物理输入没有清晰隔离，导致用户只上传 3 张图时，Provider 可能收到 6 个物理输入；同时“第一张正式通过图作为后续唯一连续性参考”的产品语义没有成为单一权威状态。

本文件是后续实现的开发契约。实现前不得以局部 prompt、Provider 重试、前端临时字段或历史兼容分支替代本文件定义的状态与边界。

---

## 1. 用户目标与产品结论

用户原始目标：

> 为了保证方向的一致性（比如人脸等等），只选定生成的第一张正式通过的图作为后续参考。可以手动在前端解绑与绑定新图。

产品结论：

1. 一个项目在任一时刻最多只有一个“当前连续性主图” `active_continuity_anchor`。
2. 第一张正式通过、且符合自动锚点条件的生成图，可以成为项目的连续性主图。
3. 用户手动绑定新的生成图时，新图原子替换旧主图；不能同时保留多个“当前主图”。
4. 用户解绑后，项目进入无连续性主图状态；系统不能自动从历史记录中重新挑选一张图补回去。
5. 用户上传的原图属于事实参考池 `fact_reference_pool`，负责人物/商品/Logo 等事实约束，不会因为“上传过”而成为连续性主图。
6. Provider 为识别事实生成的裁剪图、特征图或尺寸适配图属于临时派生证据，不属于项目参考图、历史生成图或连续性主图。
7. Provider/MCP 只消费服务端冻结的 `ReferenceInputPlan`，不能自行从项目历史、浏览器状态、最近输出或路径字段推断参考图。

这是一项 V3 Foundation 修复。它不增加 General Template 的行业交付角色，也不改变 E-Commerce、Photography、Brand、New Media 的交付包定义；它只统一跨场景的参考来源、绑定、物化和生命周期语义。

---

## 2. 现有设计回顾与本次修正

### 2.1 已确认的历史设计

Doc73 已定义：在没有用户上传或手动选择参考图的多图、真人、写实、非电商任务中，同一批次第一张输出可以作为后续输出的强身份参考。用户参考优先，E-Commerce 默认不走这条自动链。

Doc97 已定义：用户明确选择的生成图是下一次生成的第一操作参考，但上传事实仍保留；未选择的生成图不能自动进入正向上下文；生成图不能静默替换上传根事实。

Doc287 已定义：自动锚点必须来自冻结计划中的第 0 个输出，经过服务端持久化和完整性校验后固定；重试、额外 Provider 输出、后续目标图不能替换同一 Job 的源锚点；连续性输入不等于正式审核事实。

Doc45 已定义：前端应展示已选生成参考和上传参考，并支持移除参考；移除已选生成参考时，同时取消其正向上下文作用。

### 2.2 当前偏差

当前实现的主要偏差不是“没有首图锚点”，而是多个概念被并行实现：

| 概念 | 当前语义 | 本文件后的权威语义 |
| --- | --- | --- |
| 自动首图锚点 | Brain/Project Mode 私有连续性来源 | 统一写入 `active_continuity_anchor` |
| 已选生成图 | Project selected output / continuation direction | 手动绑定后成为唯一主图；未绑定只留在历史 |
| 上传原图 | 用户参考、商品真值、身份真值 | `fact_reference_pool`，不自动成为连续性主图 |
| 裁剪/特征图 | Provider 参考输入派生物 | `derived_evidence`，仅在单次 Job 物化期间存在 |
| 视觉资产绑定 | 人物资产/商品资产的项目绑定 | 保持独立；不得与生成图主图混用 |
| Provider 输入 | 可能合并所有 reference_assets、uploaded_assets 与派生物 | 只能消费冻结的 `ReferenceInputPlan` |

当前 VPS 问题中的 6 张参考图属于最后两层混淆：3 张上传原图被展开为原图加商品事实裁剪图。它们不是 6 张用户上传图，也不是历史生成图自动成为参考；但物理输入层不应无条件把同一事实来源的两种表示同时送给 Provider。

---

## 3. 权威模型

### 3.1 三层参考模型

V3 运行时必须把参考分为三层，禁止混用：

```text
Project state
├── active_continuity_anchor      # 最多一个，项目级当前连续性主图
├── fact_reference_pool            # 用户上传/资产库事实，多条，不承担连续性主图语义
└── historical_outputs             # 所有生成历史，不自动参与正向上下文

Job-local materialization
└── derived_evidence               # 单次 Provider/MCP 输入的临时派生表示，不写回项目参考池
```

### 3.2 权威优先级

对于“项目当前连续性主图”，优先级固定为：

```text
用户显式绑定的新生成图
  > 用户显式解绑（无主图）
  > 已验证的自动首张正式通过图
  > 无主图
```

自动选择器、最近输出排序、最大评分、最新创建时间和 Provider 返回顺序都不能覆盖用户显式绑定或解绑。

对于“事实参考”：

```text
用户/服务端确认的上传原图或视觉资产版本
  > 单次 Job 生成的派生证据
  > 生成历史图
```

派生证据不能反向升级为事实参考；生成历史图不能因为存在于项目中而自动进入事实参考池。

### 3.3 连续性主图与事实参考可以同时存在，但不是同一类参考

当项目既有连续性主图又有上传原图时：

- 连续性主图负责延续人物/主体的当前方向、已选构图倾向或用户确认的视觉方向；
- 上传原图负责事实校验，例如脸部根事实、商品外观、Logo 和产品结构；
- 两者在内部计划中必须使用不同的 `reference_channel`；
- “主图只有一张”不等于“Provider 在所有场景都只能收到一张图片”。Provider 是否需要事实图，由冻结的能力计划决定，但事实图不能被统计为多个连续性主图。

---

## 4. 自动主图生成规则

### 4.1 自动晋升的前提

只有同时满足以下条件，第一张正式输出才可以自动晋升为主图候选：

1. `requested_image_count >= 2`。
2. 任务是真人/人物/肖像连续性任务。
3. Brain 提供明确的真实摄影/写实渲染意图。
4. 不是 E-Commerce 默认商品套图。
5. 没有现存的 `active_continuity_anchor`。
6. 没有用户明确解绑状态覆盖当前任务。
7. 生成计划中存在冻结的计划位置 `0`。
8. 该输出是初次物化结果，不是 retry、refinement、额外 Provider response 或 MCP resume 产物。
9. 输出已经形成 canonical OutputStore record，文件存在，SHA-256 与服务端记录一致。
10. 输出通过正式的共享视觉交付门槛，或被明确标记为本产品定义的 `anchor_eligible`。仅有 Provider 返回图片、preflight candidate 或 metadata-only review 不足以自动晋升。

如果任一条件无法证明，系统关闭自动晋升，不寻找替代输出，不从历史中猜一张补位。

### 4.2 自动晋升时机

自动晋升必须发生在正式输出落库和最终交付审核之后，由服务端完成：

```text
Provider/MCP materialize
  -> OutputStore canonical record
  -> shared visual review
  -> final delivery winner
  -> anchor eligibility validation
  -> atomic claim active_continuity_anchor
```

Browser 不能提交 `output_id` 来伪造自动主图；Provider 返回的 URL、路径、请求序号或自带 ID 不能成为主图权威。

### 4.3 同一批次固定规则

对于一个逻辑 Job：

- 只有计划位置 `0` 的正式通过图可以成为自动主图；
- 计划位置 `0` 失败时，位置 `1` 或后续图不能顶替；
- retry 必须复用已有冻结主图；
- 如果首次 Job 没有成功主图，后续新的显式 Job 是否自动晋升，按项目当前状态重新判断；
- 一旦用户手动解绑，当前项目自动晋升保持关闭，直到用户重新绑定或明确开启新的自动连续性流程。

### 4.4 自动主图与用户手动绑定的关系

自动主图只是系统在满足条件时提出并写入的项目主图。用户手动绑定任何正式生成图后：

- 手动绑定成为新的唯一 `active_continuity_anchor`；
- 原自动主图转为 `superseded`，不再参与后续生成；
- 不删除原文件和历史记录；
- 不自动保留多个 generated continuation refs。

---

## 5. 手动绑定、替换和解绑

### 5.1 可绑定对象

允许绑定的对象必须满足：

- 是当前用户可见的项目正式输出；
- 有 canonical `output_id`、`job_id`、`candidate_id` 和 OutputStore record；
- 文件存在且完整性校验通过；
- 不属于失败、被拒绝、被撤销、retry-superseded 或 review-only 记录；
- 不来自另一个用户或另一个项目；
- 不使用浏览器临时 URL、客户端路径或 Provider URL 作为身份。

### 5.2 绑定接口

新增 V3 Foundation 项目级接口；已有选中输出接口保留兼容，但不得绕过新服务：

```text
GET  /api/v3/creative-agent/projects/{project_id}/continuity-anchor
POST /api/v3/creative-agent/projects/{project_id}/continuity-anchor/bind
POST /api/v3/creative-agent/projects/{project_id}/continuity-anchor/unbind
```

绑定请求：

```json
{
  "output_id": "v3_output_xxx",
  "expected_job_id": "job_xxx",
  "confirm_binding": true,
  "reason": "用户选择这张图作为后续人物/风格连续性主图"
}
```

服务端必须重新解析并校验输出，不信任 `expected_job_id` 之外的客户端来源字段。绑定成功后返回：

```json
{
  "project_id": "project_xxx",
  "active_continuity_anchor": {
    "binding_id": "anchor_binding_xxx",
    "output_id": "v3_output_xxx",
    "source_job_id": "job_xxx",
    "binding_mode": "manual",
    "state": "active",
    "public_label": "当前连续性主图"
  }
}
```

响应中不公开文件绝对路径、内部 digest、Provider 账号、MCP handoff、原始错误或内部证据字段。

### 5.3 替换语义

绑定新图不是追加第二张主图，而是一次原子替换：

```text
active(anchor_A)
  -> append superseded(anchor_A)
  -> append active(anchor_B)
  -> update current-anchor index to anchor_B
```

如果新图校验失败，旧主图保持不变。不能先解绑旧图，再因为新图失败而让项目意外进入无主图状态。

### 5.4 解绑语义

解绑请求：

```json
{
  "confirm_unbind": true,
  "reason": "用户不再沿用当前连续性主图"
}
```

解绑后：

- 当前主图状态变为 `unbound`；
- 后续 Job 不得使用该图作为 continuity input；
- 图片仍保留在项目成果和历史记录；
- 系统不得自动挑选最近一张图补回；
- 上传事实参考池不受影响；
- 已经冻结的旧 Job 不被回写修改。

### 5.5 绑定历史

当前索引只保存一个 active 记录；所有替换、解绑和自动晋升事件追加写入不可变 binding history。历史用于审计和恢复检查，但默认不进入 Provider 输入。

---

## 6. 持久化数据模型

### 6.1 当前锚点记录

建议新增项目级私有记录：

```json
{
  "schema_version": "v3_continuity_anchor_binding_v1",
  "binding_id": "anchor_binding_xxx",
  "project_id": "project_xxx",
  "state": "active",
  "binding_mode": "auto_first_formal|manual",
  "source_type": "generated_first_formal|user_bound_output",
  "source_job_id": "job_xxx",
  "source_output_id": "v3_output_xxx",
  "source_candidate_id": "candidate_xxx",
  "source_asset_id": "asset_xxx",
  "source_integrity_id": "sha256:...",
  "source_content_sha256": "...",
  "channel": "continuity",
  "lock_targets": [
    "identity geometry",
    "subject direction",
    "approved visual continuity"
  ],
  "created_at": "UTC ISO-8601",
  "bound_at": "UTC ISO-8601",
  "unbound_at": null,
  "superseded_by_binding_id": null,
  "record_binding_digest": "sha256:..."
}
```

### 6.2 上传事实参考

上传原图沿用现有资产记录，但必须保证它们可被识别为：

```text
source_type = uploaded
reference_channel = product_truth | person_identity | brand_truth | declared_scene_truth
project_owned = true
content_sha256 = server-computed
```

事实参考不能写入 `source_type=generated_first_formal`，也不能因为有 `created_from_output_id` 而自动成为连续性主图。

### 6.3 临时派生证据

派生证据只存在于 Job-local `ReferenceInputPlan` 或 provider materialization record：

```json
{
  "source_asset_id": "uploaded_asset_xxx",
  "derivative_kind": "product_truth_crop",
  "provider_input_role": "product_identity",
  "ephemeral": true,
  "persist_as_project_reference": false
}
```

派生图可以落盘用于一次任务重试和审计，但不能出现在项目的 active reference 列表，也不能被后续任务通过历史扫描自动选中。

---

## 7. Provider/MCP 参考输入计划

### 7.1 唯一输入入口

Central Brain、Provider 和 MCP Materialization 必须消费同一份服务端冻结的 `ReferenceInputPlan`：

```json
{
  "schema_version": "v3_reference_input_plan_v2",
  "project_id": "project_xxx",
  "job_id": "job_xxx",
  "continuity_anchor": {
    "binding_id": "anchor_binding_xxx",
    "output_id": "v3_output_xxx",
    "required": true,
    "provider_input_mode": "reference_image"
  },
  "fact_references": [
    {
      "asset_id": "uploaded_asset_xxx",
      "reference_channel": "product_truth",
      "required": true,
      "selected_representation": "product_truth_crop"
    }
  ],
  "derived_evidence": [],
  "selection_policy": "single_continuity_anchor_plus_bounded_fact_sources",
  "logical_continuity_reference_count": 1,
  "logical_fact_reference_count": 3,
  "physical_provider_reference_count": 3,
  "max_physical_provider_reference_count": 5,
  "plan_digest": "sha256:..."
}
```

### 7.2 单一连续性主图约束

`ReferenceInputPlan.continuity_anchor`：

- 只能是 0 或 1 条；
- 必须携带 `binding_id`；
- 不能来自项目历史自动扫描；
- 不能与 `fact_references` 共享相同的逻辑语义；
- retry 必须复用同一个 binding digest；
- 新生成结果不会在当前 Job 内自动追加为第二个 continuity input。

### 7.3 事实参考物化约束

对每个事实源，Provider 默认只能选择一个物理表示：

```text
product_truth_crop 优先，用于商品身份/细节
original_full_frame 作为缺少裁剪图或明确要求构图/场景时的 fallback
```

只有在冻结能力计划明确要求“同一事实源同时提供细节和全幅构图”时，才允许同一来源的两个物理表示同时进入 Provider；这必须记录原因并计入上限。

因此，3 张上传商品图不能因为内部存在 3 张 crop 就无条件变成 6 个 Provider 输入。默认行为应是：每个源选择一种最适合当前任务的表示，最多 3 个物理输入；如果确实需要 6 个，必须由能力计划显式说明并通过 Provider 上限检查。

### 7.4 Provider 与 MCP 对齐

Provider 和 MCP 必须接收同一份逻辑计划：

- 两者都只能使用 `active_continuity_anchor`；
- 两者都不能自行解析浏览器选中的历史图；
- 两者都不能把派生图写回项目事实池；
- 两者的 physical input count、source order、digest 和 required/optional 标记必须一致；
- MCP 只负责外部物化，不能改变锚点选择或绑定状态。

### 7.5 可观察计数

日志、Job 状态和管理员诊断必须分别记录：

```text
logical_continuity_reference_count
logical_fact_reference_count
derived_evidence_count
physical_provider_reference_count
suppressed_reference_count
```

不能只记录一个 `reference_asset_count`，否则用户的 3 张原图和 Provider 的 6 个物理文件会继续被误解为同一概念。

---

## 8. Project Context 与前端设计

### 8.1 项目上下文公开投影

公开 `ProjectContextPackage` 只提供：

```json
{
  "continuity_anchor": {
    "state": "active|unbound|invalid",
    "output_id": "v3_output_xxx",
    "public_label": "当前连续性主图",
    "binding_mode": "auto|manual",
    "preview_url": "safe project media route"
  },
  "fact_reference_pool": [
    {
      "asset_id": "uploaded_asset_xxx",
      "reference_channel": "product_truth",
      "public_label": "商品原图"
    }
  ]
}
```

公开投影不能暴露 `source_content_sha256`、内部 binding digest、绝对路径、Provider/MCP 字段或私有 review evidence。

### 8.2 前端项目参考板

项目页只显示两个明确区域：

1. `当前连续性主图`
   - 只显示 0 或 1 张；
   - 显示“自动绑定”或“手动绑定”；
   - 操作：`更换主图`、`解除主图`。

2. `事实参考图`
   - 显示上传原图/已绑定视觉资产；
   - 操作：`移除事实参考`；
   - 不显示 Provider crop 作为额外用户参考图。

生成结果卡片上提供：

```text
设为连续性主图
```

操作成功后，前端刷新项目上下文和结果板；不在浏览器本地追加多个“已选生成参考”数组作为下一次请求的权威来源。

### 8.3 绑定确认和替换提示

绑定已有主图时，前端必须提示：

```text
这张图将替换当前连续性主图。旧图仍保留在项目历史中，但不会参与后续连续性生成。
```

解绑时提示：

```text
解绑后，后续生成不会自动使用当前主图。上传的事实参考仍然保留；系统不会自动挑选历史图片替代它。
```

### 8.4 生成按钮语义

“重新生成/再出几张”只代表创建新的显式 Job：

- 如果项目有 active anchor，使用该 anchor；
- 如果项目没有 active anchor，不扫描最近历史；
- 用户没有手动绑定新图时，不自动把刚生成的所有图加入后续参考；
- 同一请求的 retry 复用该 Job 冻结的参考计划。

---

## 9. 状态机与并发规则

### 9.1 锚点状态

```text
none
  ├── auto_eligible -> proposed -> active
  └── manual_bind -> active

active
  ├── manual_replace -> superseded + active(new)
  ├── manual_unbind -> unbound
  ├── integrity_failure -> invalid
  └── project deletion/retention cleanup -> historical-only

unbound
  ├── manual_bind -> active
  └── new auto-eligible first formal output -> proposed -> active
```

`invalid` 只能 fail closed；不能由最近输出自动修复。管理员或系统修复任务必须通过明确的绑定/重建流程重新产生新的 binding。

### 9.2 并发写入

绑定、替换、解绑必须使用项目级 compare-and-swap 或等价锁：

- 请求携带当前 binding version/digest；
- 版本不匹配返回 `continuity_anchor_conflict`；
- 旧 binding 不被覆盖，只追加 superseded/unbound 事件；
- 同一项目不能出现两个 active binding；
- 旧 Job 的 frozen plan 不受新绑定影响。

### 9.3 失败关闭

以下情况一律不生成新的连续性主图：

- 输出记录缺失或不是 canonical record；
- 文件路径存在但 digest 不匹配；
- review 只有 metadata-only 结果；
- 只存在 Provider URL，没有本地/对象存储正式记录；
- 绑定对象属于另一个项目；
- 自动晋升条件缺少 typed Brain profile；
- 当前 Job 的第 0 个计划输出失败；
- 参考计划超过 Provider/MCP 物理输入上限。

---

## 10. 兼容与迁移

### 10.1 旧 Doc73 自动锚点

已有合法 `doc73_auto_identity_anchor_receipt` 的项目，在第一次读取时可转换为新的 `active_continuity_anchor`：

1. 校验 project/job/output/candidate/plan position/digest/file bytes；
2. 校验其状态不是用户已解绑或 invalid；
3. 创建新的 binding record，`binding_mode=auto`、`source_type=generated_first_formal`；
4. 保留旧字段只读兼容；
5. 新任务只读取新的 active anchor index。

非法或无法完整校验的旧记录不迁移、不自动补图，返回 `unbound` 或 `invalid`。

### 10.2 旧 selected generated reference

历史上明确经过用户选择的生成图，可转换为 `binding_mode=manual`，前提是满足 canonical output 和 source integrity 校验。仅存在于 `reference_assets`、历史列表或浏览器缓存但没有服务端选择绑定的记录，不得自动升级。

### 10.3 旧上传参考

上传参考继续进入 `fact_reference_pool`。不因为兼容字段中出现 `created_from_output_id` 就改变其 `source_type=uploaded` 语义。

### 10.4 旧派生图

旧项目中的 crop/feature sidecar 可以继续用于已冻结 Job 的重试和审计，但不写入新的项目参考池，不在前端作为独立参考展示。

### 10.5 接口兼容

现有接口保留兼容入口：

- `POST /projects/{project_id}/jobs/{job_id}/select`：继续记录用户选择，但内部转发到 continuity anchor binding service；
- `POST /projects/{project_id}/outputs/{output_id}/unselect`：如果该输出是 active anchor，转为 unbind；否则只更新历史选择状态；
- `/references/{reference_id}/remove`：只处理事实参考或旧兼容引用，不得从历史扫描中自动生成新主图；
- `/visual-asset-bindings`：保持视觉资产库项目绑定语义，不与生成输出 anchor 复用表或状态。

新代码禁止继续新增直接写 `reference_assets` 的旁路逻辑。

---

## 11. 实现边界与建议改动面

### 11.1 允许改动的模块

```text
alchemy_creative_agent_3_0/app/project_mode/
  contracts.py
  service.py

alchemy_creative_agent_3_0/app/product_api/
  route_handlers.py
  service.py
  outputs.py
  output_resolver.py

alchemy_creative_agent_3_0/app/creative_core/
  central_brain.py
  doc281_output_plan_binding.py 或相邻现有 envelope helper

alchemy_creative_agent_3_0/app/generation_router/
  providers.py

alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/
  reference_channel_policy.py
  review_evidence.py

src_skeleton/app/main.py
src_skeleton/app/static/app.js
src_skeleton/app/static/index.html
src_skeleton/app/static/styles.css
```

### 11.2 不允许的实现方式

- 不新增第二套项目级参考注册表；
- 不把 `active_continuity_anchor` 复制成多个模块字段并分别决定；
- 不用最近输出、最高分、最新时间替代用户绑定状态；
- 不把 Provider crop 写回用户事实参考；
- 不在 Provider 层根据“只要有路径”自动追加原图；
- 不修改 General Template 的行业交付角色；
- 不用 prompt 文案解决状态权威问题；
- 不让 MCP 直接写项目主图或绕过共享 review/winner/output store；
- 不删除历史输出，不重写旧 Job 的 frozen plan。

### 11.3 最小实现顺序

1. 新增 anchor contract、当前索引和 append-only binding history。
2. 把旧 Doc73/selected-output 兼容读取收敛到 binding service。
3. 修改 Project Context 公共投影，区分 anchor/fact/history。
4. 修改 Central Brain，只读取冻结 anchor，不自行追加历史输出。
5. 修改 Provider/MCP reference materialization，消费 `ReferenceInputPlan`，按源选择单一表示并记录计数。
6. 增加项目页绑定、替换、解绑 UI。
7. 完成迁移、回放、retry、并发和失败关闭测试。
8. 通过本地回归后再做一次受保护的 VPS 验证。

---

## 12. 验收测试矩阵

### 12.1 自动锚点

| 场景 | 预期 |
| --- | --- |
| 无上传参考、真人写实、请求 2 张以上 | 第 0 张正式通过输出成为唯一 active anchor |
| 第 0 张失败、第 1 张成功 | 不自动产生 anchor |
| 第 0 张为 retry 输出 | 不作为该 Job 自动 anchor |
| Provider 返回额外图片 | 额外图片不能成为 anchor |
| 只有 metadata-only review | 不自动产生 anchor |
| E-Commerce 商品套图 | 不触发 Doc73 自动人物锚点 |
| Brain profile 缺失或 rendering intent 不明确 | fail closed，不产生 anchor |

### 12.2 手动绑定/解绑

| 场景 | 预期 |
| --- | --- |
| 用户绑定正式输出 A | A 成为唯一 active anchor |
| 已有 A，用户绑定 B | A=superseded，B=active，不能同时 active |
| 用户解绑 B | anchor=unbound，后续不使用历史图补回 |
| B 校验失败 | A 保持 active，不出现空状态 |
| 两个并发绑定 | 只有一个成功，另一个返回 conflict |
| 绑定另一个项目输出 | 拒绝 |
| 绑定 review-only/失败输出 | 拒绝 |

### 12.3 事实参考与物理输入

| 场景 | 预期 |
| --- | --- |
| 3 张上传原图，无 active anchor | fact pool=3，continuity=0，不产生历史生成参考 |
| 3 张上传原图，有 1 张 active anchor | continuity=1，fact pool=3，按计划选择物理表示 |
| 3 张商品图各有 crop | 默认每源选择一种表示，不无条件变成 6 个 Provider 输入 |
| 明确要求 full-frame + detail 双表示 | 允许双表示，但记录原因并通过上限检查 |
| 生成历史中有多张图片但未绑定 | 不进入 positive context |
| retry | 复用同一个 frozen `ReferenceInputPlan` 和 anchor digest |

### 12.4 Provider/MCP parity

- Provider 与 MCP 收到相同的 anchor binding、fact source IDs、顺序和 plan digest。
- MCP 物化回写的输出必须走同一 OutputStore、review、winner 和 anchor eligibility 路径。
- Provider/MCP 不能通过 URL/path/客户端 output ID 改变 anchor。
- public projection 不暴露私有 binding、digest 和派生证据路径。

### 12.5 前端验收

- 项目页最多显示一张“当前连续性主图”。
- 可以从正式成果中绑定新主图。
- 替换主图前有确认提示，替换失败时旧主图仍在。
- 解绑后明确显示“未绑定”，不会自动补回历史图。
- 上传事实参考与连续性主图分组展示。
- crop/feature 派生图不作为额外用户参考卡片展示。
- “重新生成”不会把当前 Job 的所有输出自动追加为参考。

---

## 13. 观测、错误码与诊断

建议新增或统一以下内部错误码：

```text
continuity_anchor_not_found
continuity_anchor_conflict
continuity_anchor_output_not_canonical
continuity_anchor_integrity_mismatch
continuity_anchor_not_formally_accepted
continuity_anchor_project_mismatch
continuity_anchor_unbound
reference_input_plan_over_capacity
reference_representation_selection_failed
```

用户界面只显示可理解的结果：

- “当前主图已解绑，后续生成不会自动沿用历史图片。”
- “这张图片还没有正式通过，暂时不能设为连续性主图。”
- “参考素材过多，系统正在按任务需要收敛输入。”
- “原图仍保留，但本次任务只选取必要的事实参考。”

管理员诊断必须能看到：

```text
active_anchor_binding_id
anchor_state
anchor_source_type
fact_reference_ids
derived_evidence_ids
logical counts
physical count
suppressed sources and reason codes
plan digest
provider/mcp operation
```

不能只显示 `reference_asset_count=6`，否则无法判断 6 是 6 个用户来源、3 个来源的双表示，还是错误重复。

---

## 14. 完成定义

本设计实现完成必须同时满足：

1. 项目存在唯一可验证的 `active_continuity_anchor` 权威来源。
2. 第一张正式通过图只能在满足冻结条件时自动成为主图。
3. 手动绑定、替换、解绑均服务端持久化、可审计、可并发保护。
4. 事实参考池与生成连续性主图在数据、UI、Provider 计划和日志中分离。
5. Provider/MCP 不再通过历史扫描或旁路字段自动追加生成参考。
6. 同一用户源的原图与派生图不会默认无条件同时发送。
7. retry、refresh、service restart、MCP resume 不改变已冻结的 anchor 和 reference plan。
8. 旧 Doc73、Doc97、Doc281、Doc287 记录可安全读取并按规则迁移。
9. 通过正常、失败、边界、并发、回放和 Provider/MCP parity 测试。
10. 受保护 VPS 验证确认 3 张上传图不会再因隐式双表示直接产生未解释的 6 张输入，也不会把历史生成图当成自动参考。

---

## 15. 开发交接摘要

请开发按以下一句话理解本次修正：

> 项目只维护一个当前连续性主图；第一张正式通过图只是可验证的自动候选，用户可以手动更换或解绑；上传原图是事实参考，Provider 裁剪图是临时派生证据，任何历史生成图都不能未经绑定自动进入后续生成。

本文件不要求立即删除旧字段或旧文件。第一阶段应先建立新的权威 binding service 和 frozen `ReferenceInputPlan`，再让旧接口通过适配层进入新模型；确认回归通过后，才允许逐步收窄旧旁路写入。
