# Doc326 — V3 参考图隔离的向后兼容适配与废弃改动隔离方案

状态：本地实现已落地；专项自审通过；全量回归存在基线失败，尚未放行合并

日期：2026-09-28

基线：`46ca6dd1b42f48577ecbae430e5bb9d7ffe5b2b0`

范围：V3 Foundation 的参考输入边界与连续性主图适配

不包含：V1/V2/Alchemy Lab、API/MCP 路由、Brain 传输模式、Vision 审核规则、
Provider 重试、OutputStore 恢复、计费、数据清理和 VPS 部署。

---

## 1. 结论先行

本次只保留一个有明确产品价值的方向：

> 防止历史生成图、旧 selected 引用和项目级素材池在没有用户明确操作的情况下，
> 自动进入下一次 V3 生图；同时保留原版历史展示、旧接口和各专业模式的输入契约。

实现方式不是直接把旧的 `_reference_scoped_project` 改成“无锚点即清空全部字段”，
而是增加一个仅用于**当前生成任务**的严格参考输入适配层：

```text
项目持久化记录 / 历史展示 / 旧接口
        │ 保持原版兼容
        ▼
当前 Job 的 ReferenceInputPlan 冻结适配器
        │ 只允许本次明确输入 + 0/1 个已验证连续性主图
        ▼
Brain / Provider / MCP 的唯一物理输入
```

这样同时获得两项结果：

1. 原版项目不会因为历史字段被删除、重写或改变公开结构而失效。
2. 新任务不会再把历史生成图、旧多选结果或同一素材的派生图自动追加给 Provider。

当前工作区中的其他未提交改动不属于本方案，必须拒绝带入：

- `product_api/service.py` 的 PLANNED 任务自动 OutputStore 恢复；
- `providers.py` 的流式首语义超时扩大；
- 以 Doc324 为理由改变当前非流式 V3 主链路；
- API/MCP 统一文档和任何 V1/V2/Lab 改动。

---

## 2. 审计对象与冻结约束

### 2.1 原版基线

当前 `main` 与 `origin/main` 均为：

```text
46ca6dd1b42f48577ecbae430e5bb9d7ffe5b2b0
```

审计时工作区存在其他未提交修改。本文只把以下当前脏改动作为比较对象，
不把它们视为已合入功能：

- `app/project_mode/service.py`：无 active anchor 时清空 selected output 和 generated selected refs；
- `app/product_api/service.py`：PLANNED 任务查询时扫描 OutputStore；
- `app/llm_brain/providers.py`：流式首语义超时由 60/120 改为 120/180；
- 对应的专项测试和 Doc324 文档。

### 2.2 权威文档

- [Doc322 单一连续性主图与参考输入重建](322_V3_SINGLE_CONTINUITY_ANCHOR_AND_REFERENCE_POOL_RECONSTRUCTION_SPEC.md)
- [Doc299 输出恢复闭环边界](299_V3_BRAIN_CAPACITY_DIAGNOSTICS_AND_OUTPUT_RECOVERY_CLOSURE_SPEC.md)
- [Doc315 Brain 非语义响应开始超时](315_V3_BRAIN_NO_SEMANTIC_RESPONSE_START_TIMEOUT_REPAIR_SPEC.md)

### 2.3 不可破坏的原版能力

适配层不得破坏以下现有能力：

1. 已完成项目的历史输出、时间线、选中标记和下载入口仍可读取。
2. 旧客户端提交明确的 `selected_output_id` 或 `selected_candidate_id` 时，仍进入原有选择服务。
3. 选择服务对正式输出、账户归属、项目归属和完整性校验仍然有效。
4. 一个正式通过且被用户确认的输出，仍可成为后续任务的连续性主图。
5. 用户解绑后，后续任务不会暗中恢复旧图。
6. Standard/General 的当前任务直接上传仍可正常生图。
7. Professional 和 E-Commerce 的专用来源、商品事实和派生表示仍由各自契约负责。
8. 重试、审核、Provider 调用和计费流程不因本适配层新增分支而改变。

---

## 3. 兼容性原则

### 3.1 持久化兼容优先

旧字段不删除、不批量重写、不把历史 selected 数组压缩成一条记录：

```text
selected_output_refs       = 历史/用户操作记录，继续保留
reference_assets            = 原有项目资产记录，继续保留
selected_output_states      = 原有状态投影，继续保留
active_continuity_anchor    = 当前唯一连续性主图权威
ReferenceInputPlan          = 每个新 Job 的冻结物理输入权威
```

`selected_output_refs` 是历史和兼容展示字段，不能再被 Provider 直接当成输入。
`active_continuity_anchor` 是项目当前唯一主图，不能由多个历史 selected 记录推导。

### 3.2 生成入口收窄，读取入口不破坏

严格隔离只作用于以下生成边界：

- 新建 Project Job 时的上下文冻结；
- `ReferenceInputPlan` 生成；
- Brain 规划上下文；
- Provider/MCP 输入物化。

以下读取边界不因本方案清空：

- 项目历史页面；
- 历史输出列表；
- 时间线；
- 旧版 selected 输出投影；
- 审计和恢复查询。

旧前端可以继续看到历史选择；新前端必须用
`metadata.continuity_anchor.active_continuity_anchor` 判断当前唯一主图。

### 3.3 显式操作优先，隐式历史降级

兼容规则固定为：

```text
本次明确上传
  > 已验证 active_continuity_anchor
  > 当前模式自己的显式资产/商品契约
  > 历史 selected / 最近输出 / 项目源池：不得进入新任务 Provider 输入
```

“降级”不是删除历史，也不是阻断普通无参考生图；没有主图时，普通任务应以零
连续性参考继续执行。需要延续旧图的用户，通过旧的明确选择接口或新的绑定入口
完成一次显式绑定即可。

---

## 4. 具体保留方案

### 4.1 不直接改造公共 `_reference_scoped_project`

当前未提交改动直接把无锚点项目的 `selected_output_refs` 和
`GENERATED_SELECTED` 资产清空。这会同时影响生成上下文和公共项目投影，存在
以下兼容风险：

- 旧前端刷新后看不到历史选中结果；
- review-pending 的旧选择被误显示为不存在；
- 旧客户端依赖的字段集合出现语义变化；
- 公共投影和内部历史记录不一致；
- 未隔离的 Brain 测试会把网络/慢调用误认为参考隔离失败。

因此，不应把该函数改造成新的全局清洗器。

### 4.2 增加生成专用适配器

建议新增一个明确命名的内部方法，名称可为：

```python
_generation_reference_scope(
    project,
    template_id,
    direct_reference_ids,
    continuity_snapshot,
    *,
    job_id,
) -> GenerationReferenceScope
```

该方法只构造当前 Job 的内存副本，不修改 ProjectStore，不改变公共历史投影。
它必须输出可审计的来源摘要，至少包含：

```text
project_mode
direct_reference_ids
active_anchor_binding_id / null
selected_legacy_refs_seen
selected_legacy_refs_used = 0
mode_contract_owner
reference_plan_digest
```

### 4.3 Standard/General 规则

对 Standard/General，适配器只允许：

1. 当前请求明确携带并已完成账户/项目/文件完整性校验的上传素材；
2. 当前有效且来源完整的一个 `active_continuity_anchor`；
3. 同一素材只选择一个默认物理表示：原始完整帧；
4. 不读取 Professional 资产池、E-Commerce 商品事实、通用 `project_source_library`；
5. 不读取旧 `selected_output_refs` 作为隐式输入；
6. 不生成 `product_truth_crop` 等电商派生物。

无 active anchor 且无当前直接上传时，`physical_provider_reference_count` 必须为 0，
但任务仍可按原版无参考路径继续执行。

### 4.4 Professional 规则

Professional 不使用 Standard/General 的通用过滤器替代自身契约。它必须继续由
显式、冻结版本的视觉资产绑定提供输入。适配器只负责追加 0/1 个连续性主图，
不能把历史 generated selected 记录提升为 Professional 资产。

### 4.5 E-Commerce 规则

E-Commerce 的商品事实计划、来源证明、裁剪图和全幅图选择必须继续由现有
Product Truth 契约决定。参考隔离修复不得做以下事情：

- 用 Standard 的“只保留原图”规则覆盖商品事实计划；
- 删除商品契约明确允许的派生表示；
- 把连续性主图塞进 `UploadedAssetInfo`；
- 以通用 `reference_assets` 合并逻辑替代 E-Commerce 的来源证明；
- 因为发现历史 selected 图而追加一份商品输入。

E-Commerce 是否发送原图、商品裁剪图或二者，必须由已冻结的商品计划决定，
不是由本适配器猜测。

### 4.6 连续性主图规则

只有以下来源可以进入 `continuity_anchor`：

- 已完成完整性校验的正式输出；
- 当前项目、当前账户归属下的 canonical OutputStore 记录；
- 已通过现有正式交付/审核门槛，或符合明确的手动绑定前置契约；
- 由现有 ContinuityAnchorBindingService 原子绑定。

以下内容一律不能成为当前连续性主图：

- 最近生成但未完成审核的候选；
- retry-superseded 输出；
- review-only 或被拒绝输出；
- 浏览器临时 URL；
- Provider URL、文件路径或客户端传来的 asset id；
- 多个旧 selected 记录的自动合并结果。

### 4.7 旧项目迁移规则

不做静默批量迁移。旧项目分为三类：

| 旧状态 | 新任务行为 | 用户如何继续使用 |
|---|---|---|
| 已有有效 active anchor | 直接沿用该 anchor | 无需操作 |
| 只有一个历史 selected，但没有 anchor | 保留历史展示，新任务不隐式使用 | 用户明确重新选择/绑定 |
| 多个历史 selected 或来源无法验证 | 全部保留历史，新任务零隐式生成参考 | 用户明确绑定一张 |

这是兼容性安全降级：旧数据不丢，普通生图不被阻断，但系统不再把不确定的旧
记录当作 Provider 输入。

### 4.8 重试与并发规则

- Job 创建时冻结参考计划和连续性版本；
- Job 内 retry 必须复用同一个冻结计划；
- 生成出新图后，不得在当前 Job 内自动追加第二个连续性参考；
- 绑定/解绑使用现有版本号和 CAS；
- 绑定失败时旧 anchor 不变；
- 已冻结 Job 不回读用户后来更换的 anchor；
- 多个历史 selected 不得在重试时被重新合并。

---

## 5. 代码落地边界

### 5.1 允许修改

第一阶段只允许修改以下 V3 生成输入边界：

- `alchemy_creative_agent_3_0/app/project_mode/service.py`
- `alchemy_creative_agent_3_0/app/reference_input_plan.py`（如确有字段缺口）
- 与生成输入计划直接相关的 V3 专项测试文件

### 5.2 明确禁止修改

本阶段不得修改：

- `app/product_api/service.py` 的普通 `get_job()` 恢复语义；
- `app/llm_brain/providers.py` 的当前非流式主路径和流式超时默认值；
- Vision 审核、Provider 重试和质量阈值；
- V1/V2/Alchemy Lab；
- API/MCP 公共路由；
- 计费、账户、OutputStore 持久化格式；
- VPS、GitHub、生产数据。

### 5.3 推荐最小实现顺序

1. 恢复公共项目投影的原版语义，不删除历史 selected 字段。
2. 把严格过滤从公共投影移到 Job-local generation scope。
3. 让 `ReferenceInputPlan.freeze()` 成为 Provider/MCP 的唯一输入来源。
4. 为 Standard/General、Professional、E-Commerce 分别加隔离测试。
5. 用 Fake Brain 和受控 Provider 验证参考图数量，不调用真实上游。
6. 通过专项回归后，再做一次静态 diff 审计。

---

## 6. 验收矩阵

### 6.1 必须通过

| 场景 | 预期 |
|---|---|
| 原版无参考项目生图 | 成功，Provider 参考图为 0 |
| 当前明确上传 3 张原图 | 只发送 3 个 Standard 原图表示 |
| 无 anchor 的旧项目有 2 张 selected 历史 | 历史仍可见，下一任务 Provider 参考图为 0 |
| 显式绑定 1 张正式输出 | 下一任务只追加 1 张 continuity anchor |
| anchor + 当前上传 3 张 | 计划清楚区分两类来源，物理数量与收据一致 |
| 用户解绑 | 下一任务不再发送旧 anchor，不自动补历史图 |
| 多个旧 selected | 不合并、不猜选、不追加 |
| E-Commerce 商品计划 | 继续使用既有商品事实契约，派生表示不被通用规则误删 |
| Professional 绑定 | 继续使用冻结资产绑定，不读取 General/E-Commerce 源池 |
| Job retry | 复用原冻结计划，不重新扫描项目历史 |
| 项目刷新/历史读取 | 原版历史字段和输出仍可见 |
| 账户/项目越权输入 | 与原版一样拒绝 |

### 6.2 必须失败或阻断

- Provider/MCP 从 `selected_output_refs`、最近输出或项目源池自行取图；
- 无 anchor 时自动选择最近生成图；
- 多个 selected 记录自动合并为多个 continuity refs；
- 同一 Standard 上传素材同时自动生成并发送电商 crop；
- retry 重新读取变化后的项目 anchor；
- 用 URL、路径、客户端 asset id 伪造连续性主图；
- 以 PLANNED 任务查询触发 OutputStore 恢复；
- 以流式超时扩大作为当前非流式 V3 修复。

### 6.3 证据要求

每个通过用例必须保留：

- frozen `ReferenceInputPlan`；
- `plan_digest`；
- Provider/MCP 实际输入收据；
- 逻辑来源数量和物理输入数量；
- active anchor 版本；
- 项目历史未被修改的前后摘要。

只有单元测试或模型配置文件，没有输入收据的，不得宣称“实际只发送了 N 张图”。

---

## 7. 对当前未提交改动的最终处置

### 7.1 保留方向，但不能原样合并

`project_mode/service.py` 的“无锚点不把历史生成图送给 Provider”方向保留；
当前实现必须改为 Job-local 适配器，不能直接清空公共 scoped project。

### 7.2 坚决抛弃

以下内容不进入本方案，也不进入后续合并：

1. `product_api/service.py` 的 `_planned_output_recovery_status()`。
   它会绕过 Doc299 的显式恢复选择器边界，并且当前 Job 与 History 投影可能不一致。
2. `providers.py` 将流式首语义超时改为 120/180 秒。
   当前默认是 `chat_nonstream`，该修改不改善主路径，且与 Doc315 冲突。
3. 将 Doc324 当作当前 V3 生图修复的一部分。
   流式协议保护可作为未来兼容测试，但不能改变当前非流式入口或超时契约。
4. 将 API/MCP 统一适配文档、V1/V2/Lab 代码带入本次 V3 参考图修复。

### 7.3 不得用测试删除掩盖差异

任何旧测试失败必须先归类为：

- 真实产品契约变化；
- 新逻辑回归；
- 测试夹具未隔离；
- 已废弃契约但未标注；
- 未知原因。

不得通过删除断言、取消测试、改成更宽松的计数或接入真实上游来制造通过。

---

## 8. 本次设计审计结论

### 主控静态审计：PASS（实现范围）

通过理由：

- 只保留了参考输入隔离这一项与用户问题直接相关的能力；
- 历史数据、旧接口和公共投影没有被要求删除或重写；
- Standard/General、Professional、E-Commerce 的输入权威被分开；
- active anchor 和 Job-local `ReferenceInputPlan` 的职责明确；
- retry、并发、解绑、跨账户和物理输入数量都有失败边界；
- 已明确排除 OutputStore 自动恢复和流式超时改动；
- 没有扩展到 V1/V2/Lab、API/MCP、Provider 或 Vision。

### 本地实现摘要

- `V3ProjectModeService._build_context()` 增加显式 `generation_scope` 参数。
- 只有新建 Project Job 的上下文使用 `generation_scope=True`。
- 公共项目读取继续使用原版 `_reference_scoped_project()`。
- Standard/General 的生成副本只保留当前 Job 直接上传和 0/1 个 active anchor。
- Professional/E-Commerce 继续返回原有专用入口，不经过通用隔离过滤器。
- 新增 `test_v3_doc326_reference_scope_compatibility.py`，覆盖历史兼容、直接上传、
  单锚点和真实 Project Job 冻结计划。

本地专项结果：Doc326 4 passed、Doc322 Reference Plan 17 passed、Continuity Binding
12 passed、Project Workflow 10 passed。

### 本轮证据

- `test_v3_doc322_reference_plan.py`：17 passed。
- `test_v3_doc322_continuity_binding.py`：12 passed。
- `compileall`：通过。
- UTF-8 文档标题/替换字符检查：通过。
- `git diff --check`：通过；仅报告既有工作区的换行格式提示。
- `test_v3_doc322_reaudit.py`：前 11 个用例输出通过后发生挂起，已中止；
  不把它计入通过，也不把挂起解释为产品逻辑通过。

上述测试是当前工作区的基础契约证据，不是新适配器已经实现的证据。
适配器实现后必须补充本文第 6 节的 generation-scope/Fake Brain 测试，
并冻结新 diff 后重新执行独立只读审计。

### 独立审计状态：未执行

当前 Codex 会话没有可验证的独立只读审计代理运行证据，因此不能把本结论
表述为独立验收通过。代码实现后的版本必须冻结 diff，再由不同审计角色重新检查。

### 生产代码状态：NOT READY FOR MERGE

当前实现已经完成最小落地，但仍不能合并或部署，原因是：

- 全量测试共收集 3725 项；首个确定失败为未修改的
  `test_runtime_run_llm_brain_forwards_injected_profile_into_brain_request`，
  已通过 `-x` 记录为 265 passed / 1 failed。失败原因是测试构造的
  `RuntimeRequest` 缺少既有 `optional_brand_id` 字段，涉及
  `scenario_runtime/runtime.py`，不在本次 diff 内。
- 不带 `-x` 的全量运行在约 30% 后进入既有长时间无输出的测试，已停止，
  因而不能宣称全量通过。
- 当前会话没有可验证的独立只读审计代理，因此仍缺独立验收证据。

被拒绝的 OutputStore 计划恢复、流式超时扩大和 Doc324 已从本地项目改动中移除；
API/MCP 方案文档被保留在项目中，但未纳入本次实现范围。

因此本文对应的是“已完成本地实现、等待基线失败处理和独立审计”的状态，
不是合并或生产放行结论。

---

## 9. 给开发人员的简述

保留参考图隔离，但不要直接清空旧项目字段。旧历史、旧接口和页面展示继续按原版
工作；只在创建新 Job 时生成一份临时、冻结的参考输入计划。这个计划只允许本次
明确上传的素材和一个已经验证的连续性主图，历史生成图和旧多选记录只能留在历史里，
不能自动送给 Provider。E-Commerce 和 Professional 继续由各自契约决定输入表示，
不被通用规则覆盖。

这样既不会破坏原版项目的读取、历史和生图能力，又能消除“历史图自动串入、同一素材
重复物化、3 张上传变成 6 张 Provider 输入”的问题。OutputStore 自动恢复、流式超时扩大、
Doc324 当前流式改造和 API/MCP 文档都不要带入本次合并。
