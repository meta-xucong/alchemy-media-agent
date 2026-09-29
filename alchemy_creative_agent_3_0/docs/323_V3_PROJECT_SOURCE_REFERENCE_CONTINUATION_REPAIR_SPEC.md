# Doc323：V3 项目源图续用最小纠偏开发文档

状态：实现修订版，已按独立审计意见补充来源证明、旧项目迁移失败闭环和电商通道隔离，待最终回归与发布验收。

前置依据：Doc322 单一连续性主图与参考通道隔离契约。

优先级说明：Doc323 仅 supersede Doc322 关于 Standard/General“直接上传默认只属于当前 Job、不得跨 Job 续用”的条款。Doc322 关于全局素材库隔离、Professional/E-Commerce 通道隔离、生成图与连续性主图分离、Provider 只能消费冻结计划的规则继续有效。

## 1. 用户目标与观察到的偏差

用户在同一个 V3 项目中首次上传饰品、商品或人物原图并生成后，点击“继续生成”时，应当继续使用首次生成时的同一组项目源图，除非用户主动解绑、删除或替换它们。

当前偏差是：首次 Job 使用 `uploaded_asset_ids`，Job 结束后普通 General 项目没有可靠地保存这些源图；下一次点击生成时前端不再携带新上传 ID，服务端又按 Doc322 的严格当前 Job 规则把历史上传排除，于是 Provider 收到 0 张源图，只能按文字生成。

## 2. 纠偏后的权威模型

Doc322 的“禁止全局素材池污染”规则继续有效。本文件只对 Standard/General 增加一个受控的项目级源图通道：

```text
Project
├── project_source_references      # 当前项目明确使用过并被服务端保存的上传原图
├── active_continuity_anchor       # 最多一张正式生成图，负责连续性
└── historical_outputs             # 生成历史，不自动成为参考

Job input for Standard/General
├── current explicit uploads       # 本次新上传的原图
├── active project source refs     # 同项目已保存的原始上传图
└── 0/1 continuity anchor          # 当前唯一连续性主图
```

权威优先级：

1. 本次明确上传的原图加入当前 Job，并在服务端保存为该项目的源图引用；
2. 后续 Job 自动复用同项目仍为 active 的上传源图；
3. 当前 Job 的新上传与已有项目源图按 `asset_id` 去重；
4. 生成图、选中输出、Provider 裁剪图和通用/跨项目素材库不得通过本规则进入源图引用；
5. 用户停用或删除项目源图后，后续 Job 不得自动恢复它；
6. 连续性主图仍然最多一张，与项目源图是不同的 `reference_channel`，可以同时存在。

本文件只修正“同项目源图续用”，不把所有项目历史素材重新解释为源图池。Professional 和 E-Commerce 继续由各自的资产绑定、商品事实契约负责。

## 3. 最小实现方案

### 3.1 后端保存首次明确上传

在创建 General/Standard 项目时传入的初始上传，以及后续创建 General/Standard Job 时请求中的明确 `uploaded_asset_ids`，服务端都调用已有 `_persist_job_uploaded_references`。保存信息必须包含：

- `source_type=uploaded`；
- `use_policy=general`（由现有上传策略继续负责身份/产品提示，不改变 Provider 语义）；
- `metadata.project_source_reference=true`；
- `metadata.persisted_from_project_job=true`；
- 当前模板与 Job 来源信息。

保存发生在上下文冻结前，并通过项目 Store 持久化；必须先完成保存，再进入规划或 Provider 调用，不能只依赖后续 Job 关联时保存。浏览器不能伪造项目源图引用；`project_source_reference` 等来源证明字段只允许服务端内部写入。

### 3.2 后续 Job 解析受控源图

仅在 `GENERAL_TEMPLATE_ID` 的 Standard/General 分支中，将以下集合合并后作为当前 Job 的 direct reference IDs：

```text
current request uploaded IDs
+ active project reference_assets where source_type=uploaded
  and metadata proves project-source origin
```

必须排除：

- `GENERATED_SELECTED`；
- active continuity anchor 的输出 ID（它走独立 anchor 通道）；
- E-Commerce `product` 引用；
- Professional 视觉资产绑定；
- 没有项目源图来源证据的旧全局/智能匹配记录；
- 其他项目的任何素材。

解析结果继续进入现有 `ReferenceInputPlan.freeze()`，由同一个冻结计划驱动 Brain、Provider 和 MCP。不得在 Provider 层另行扫描项目历史。

### 3.3 旧项目兼容恢复

对于在 Doc323 部署前已经生成过的项目，如果项目当前没有任何带项目源图来源证据的 active 上传引用，服务端可以按 `project.job_ids` 的项目内顺序读取最早一个有效 Standard Job 的已冻结 `ReferenceInputPlan.direct_references`。这不是全局历史搜索：

- 只读取当前项目已经关联的 Job；
- 只接受服务端校验过摘要的 Standard 冻结计划；
- 只恢复该计划中的上传 `asset_id`；
- 恢复后立即写入新的 `project_source_reference=true` 项目引用；
- 旧 Job 明确声明过 Standard 源图、但冻结计划摘要或源文件无法验证时，返回 `needs_input` 阻断状态，停止在 Brain/Provider 之前，不降级成无参考文生图；用户可检查项目源图或重新上传。
- 没有任何旧 Standard 源图候选（例如项目本来就是纯文字生成）时，继续允许既有的 0 张参考图文生图路径。

该兼容分支只在项目从未拥有可验证的项目源图来源记录时执行。若用户已经把全部项目源图停用/删除，则视为明确解绑，不得再从旧 Job 恢复。项目已有 active 源图后同样不回看旧 Job，也不把后续未保存的临时上传自动合并进来。若本次请求带有新上传图，仍先尝试恢复同项目旧源图，再与本次上传按 `asset_id` 去重合并，避免一次补传把旧源图集合静默丢掉。

### 3.4 解绑与替换

现有项目参考删除/停用接口继续作为权威。解析时只读取 active 的 `source_type=uploaded` 项目源图；停用后不得因为旧 Job、legacy `uploaded_asset_refs` 或生成历史再次恢复。

### 3.5 前端边界

本次不改上传协议和 Provider 调用。前端继续只上传本次新文件，服务端负责复用已保存源图。项目刷新后，现有参考图投影应显示项目源图；不再通过浏览器复制生成图或全局素材库来实现续用。

如后续需要“只本次使用”的高级开关，应另立文档；本次不增加第二套前端状态。

## 4. 不变项与负面约束

- 不恢复 Doc281 全局/智能素材匹配到 General 默认生成链路；
- 不自动把生成图片当作多个参考图；
- 不改变最多一张 `active_continuity_anchor`、手动绑定、手动解绑规则；
- 不改变 E-Commerce 商品真值、Professional 视觉资产和 MCP 物化路径；
- General/Standard 的服务端来源证明不能进入 E-Commerce 商品真值候选；E-Commerce 候选必须来自 E-Commerce 模板来源或兼容的旧 E-Commerce 项目镜像。
- 不改变 Brain、Provider、Vision 审核阈值或超时策略；
- 不新增 Provider 重试，不用 Prompt 补救参考图缺失；
- 不修改历史 Job 的冻结计划；修复只从新 Job 起生效。

## 5. 验收测试

### 5.1 必须通过

1. General 项目首次用 3 张上传图生成，第二次不上传新图，冻结计划仍包含同样 3 个 `direct_references`；
2. 同一项目源图与当前新上传重复时只出现一次；
3. 同一项目同时存在一张连续性主图时，计划包含“源图 N 张 + anchor 1 张”，两类通道不混淆；
4. 停用/删除项目源图后，后续计划不再包含该图；
5. 只有另一个项目或全局素材库拥有的图，不会进入当前项目；
6. 生成历史图未手动绑定为 anchor 时，不会进入 direct references；
7. E-Commerce 与 Professional 现有参考计划回归通过；
8. Provider/MCP 最终输入数量与冻结 `ReferenceInputPlan` 一致。
9. Doc323 部署前创建、且只有旧 Job 冻结计划保存源图的项目，首次修复后续生成能恢复同一组源图；
10. 旧 Job 源图计划摘要/源文件损坏时在规划前阻断；旧项目停用的 legacy 源图不会被迁移复活；带新上传图仍会合并可验证旧源图；General 来源不会进入 E-Commerce 商品真值池。

### 5.2 真实验收

部署后复用用户刚才的 V3 项目，在不重新上传原图的情况下点击“继续生成”，记录：

- 新 Job ID；
- `reference_input_summary`；
- `reference_input_plan.direct_references` 的 asset ID 与数量；
- Provider 实际参考图数量；
- 输出是否保留原饰品/商品事实。

真实测试只允许执行一次受控续生成；若计划显示 0 张源图，先停止 Provider，不以错误图片作为验收结果。

## 6. 变更边界与审计证据

预计改动范围：

- `app/project_mode/service.py`：General/Standard 源图持久化与受控复用；
- `tests/test_v3_doc322_reference_isolation.py`：更新旧的“永不恢复项目源图”契约；
- `tests/test_v3_doc326_reference_scope_compatibility.py`：补充续用、停用、anchor 分离回归；
- 本开发文档。

不应改动 Provider、MCP、Brain、E-Commerce、Professional 参考物化实现。若 diff 出现这些区域，必须退回审计，不得带入发布。
