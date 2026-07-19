# Doc173 — V3 视觉资产库优先的专业工作区与项目绑定重构规范

状态：`authoritative_forward_reconstruction`

基线：`origin/main@64d684b`

> **前端信息架构替换说明（Doc174，2026-07-20）**
>
> 本文关于 Visual Asset Library、ProjectVisualAssetBindingSet、Job freeze、
> Brain-owned canonical prompt 与共享运行时的所有权规则仍然有效。
> 但第 1、5、7、8、10 节中把“项目工作台”和“视觉资产库”设为并列一级
> V3 入口的前端描述，已由 **Doc174** 替换。新前端必须提供“基础版 / 专业版”
> 两个明确工作台：基础版保持原有项目路径；专业版在同一独立页面内先提供视觉
> 资产库，再提供可绑定资产的专业项目工作区。不得把本文件旧版的并列入口当作
> 新前端实现依据。

## 0. 结论、范围与权威关系

V3 的专业能力不应被理解成“在创建项目时勾选一个专业模式”。它的产品核心是：

```text
先建立可复用、可审核、可版本化的视觉资产
→ 再在任意明确的创作项目中按需选择并绑定这些资产
→ 每个 Job 冻结本次实际使用的资产版本和授权通道
→ Remote Brain 依据用户意图、模板语义与冻结资产证据创作完整最终提示词
→ 共享 Provider / Review / bounded retry / final delivery 执行
```

第一阶段只开放 **People Asset / Face Identity** 的资产建立能力；产品资产、场景资产、
品牌资产等是同一母目录下的未来类型，不能在本次重构中以半成品方式实现。

本文件是以下 **新建资产、新建项目绑定、新前端入口和新运行时写入路径** 的最高权威：

```text
Visual Asset Library 的归属与生命周期
项目级 VisualAssetBindingSet
Professional Workspace 的前端信息架构
资产绑定的冻结、续作、撤换与兼容迁移
```

它不重写 Doc76 的 foundation/template 边界、Doc93 的参考图通道所有权、Doc101 的
冻结能力计划、Doc134–140 的 Brain-first 语义/提示词约束，或现有共享
Provider、Review、Retry、Delivery 的所有权。

### 0.1 本文件取代的旧前向描述

以下文档中的 **project-scoped asset、项目创建时 Professional Mode 开关、每 Job 只选
一个 project People Asset、以及相应前端流程**，自本文件进入实现后仅保留历史读取
兼容，不再是新功能的设计依据：

```text
docs/visual_assets/PROFESSIONAL_MODE_VISUAL_ASSET_LIBRARY_AND_PEOPLE_ASSET_MODULE_SPEC.md
docs/visual_assets/PROFESSIONAL_MODE_IMPLEMENTATION_HANDOFF_AND_ACCEPTANCE.md
docs/visual_assets/PROFESSIONAL_MODE_FRONTEND_UX_REMEDIATION_20260719.md
docs/visual_assets/PROFESSIONAL_MODE_PERSISTENT_ASSET_LIFECYCLE_AND_CONTROLLED_RUNTIME_HANDOFF_20260718.md
docs/visual_assets/PROFESSIONAL_MODE_ASSET_CHANNEL_AUTHORITY_AND_REFERENCE_ADMISSION_SPEC.md
docs/visual_assets/PROFESSIONAL_MODE_IMPLEMENTATION_STATUS_AND_M5_HANDOFF.md
Doc172 的 Professional 前端专节
```

这些文档保留的有效内容包括：Face Identity 首发边界、root/consent provenance、三视角
Anchor Pack、共享 Brain/Provider/Vision/Retry、无本地 prompt 拼接、无静默降级、
append-only 历史、及既有 M5 证据记录。历史验收记录不得被倒改成新的体系描述。

### 0.2 变更深度评估

这不是换文案或单页 UI 微调，而是 **“资产归属 + 项目绑定 + 前端导航”三层薄重构**。
它不是第二套生成框架：

| 层面 | 需要调整 | 不需要重建 |
| --- | --- | --- |
| 资产归属 | 从项目私有目录升级为用户/工作区可复用的 Visual Asset Library；保留旧记录只读兼容 | 图片字节存储、Anchor Pack 服务、共享证据体系 |
| 项目运行时 | 用冻结 `VisualAssetBindingSet` 取代新写入的 `professional_mode + people_asset_id` | ScenarioRuntime、CapabilityActivationPlan、Brain、Provider、Review、Retry |
| 前端 | 增加独立资产库入口与项目绑定弹层；移除把资产建立藏进项目创建页的心智模型 | 模板选择、项目工作台、上传、结果区、共享状态与错误投射 |
| 专业模板 | 各模板只声明可接受的资产类型与通道，不拥有资产库 | General/E-Commerce/Photography 的既有交付语义 |

因此实施应由专业版分支负责资产库和绑定表面，由主线负责公共 Project/API/前端共享
投射；任何一方均不得复制共享生成、审核、重试或资产字节存储。

## 1. 产品心智模型

### 1.1 两个并列入口，而非两种互斥项目

顶层 V3 导航应提供：

```text
项目工作台
  用于创建 General / E-Commerce / Photography 等项目并完成创作

视觉资产库
  用于建立、查看、准备、审核、激活、归档可复用资产
```

“专业”不再是首页创建项目时与“标准创作”并列的一张项目模板卡。用户可以：

```text
先进入视觉资产库建立人物资产
→ 返回项目工作台
→ 新建任意模板项目
→ 在“使用视觉资产”弹层中绑定已激活资产
```

也可以先建立普通项目；只有当用户主动在该项目中选择已激活资产时，才形成资产绑定。
未绑定资产的项目就是当前的 Standard 路径，不需要显示“专业模式关闭”或制造额外门槛。

### 1.2 第一阶段用户能理解的对象

普通用户界面采用下面的词，不展示 `pack_version_id`、hash、provider、job ID、
embedding 或内部 capability 名称：

| 用户语言 | 系统概念 | 第一阶段状态 |
| --- | --- | --- |
| 视觉资产库 | Visual Asset Library | 本次建立 |
| 人物资产 | People Asset | 本次建立 |
| 人物标准建模 | Face Identity Anchor Pack preparation | 本次建立 |
| 已启用版本 | active reviewed pack/version | 本次建立 |
| 本项目使用的资产 | frozen project/job binding | 本次建立 |
| 产品资产、场景资产、品牌资产 | future Visual Asset types | 仅预留，不展示可点击入口 |

### 1.3 典型无障碍路径

```text
第一次建立人物资产
视觉资产库 → 新建人物资产 → 上传并确认可使用的源图
→ 等待“源图已准备好” → 开始标准建模
→ 查看正面 / 侧前方 / 侧面状态 → 审核完成 → 明确“启用此版本”

在项目中使用人物资产
项目工作台 → 选择模板 → 填写需求 → “使用视觉资产（可选）”
→ 勾选一个已启用人物资产 → 确认绑定 → 提交生成
→ 看到“本次使用：人物资产名称 / 已启用版本”而非内部编号
```

对于未来的“人物 + 产品”项目，用户在同一绑定弹层中选择两个不同类型的已启用资产。
用户不需要手动合成参考图、挑选证据视角、输入 prompt 片段或理解通道冲突。

## 2. 不可变架构边界

### 2.1 资产库不取代模板

```text
Visual Asset Library
  负责资产的可复用身份、版本、许可/同意来源、准备状态、激活状态和证据生命周期

Template / Scenario Pack
  负责用户明确选择的创作场景、交付数量和专业交付结构

Shared Foundation
  负责能力计划、参考证据接纳、Remote Brain、canonical prompt、Provider、视觉审核、
  bounded retry、winner 和追加式交付历史
```

资产库不得把商品套图、摄影角色、平台规则、镜头/场景配方或任何“该生成什么”的决定
塞入 General 或资产记录。General 继续简单中立；E-Commerce 与 Photography 继续拥有
各自明确的模板语义。

### 2.2 Brain-first，禁止结构化堆词与本地创作

资产记录和绑定集只贡献 **类型化、已审核、已授权的事实与通道主张**。它们绝不贡献：

```text
本地拼接的 prompt / negative prompt
年龄、肤色、镜头、姿态、灯光、妆容、场景等关键词配方
正则或关键词驱动的“自动选择资产”
本地 retry 文案、风格化修补或私人评分器
```

新 Job 的最终 Provider prompt 必须始终由 Remote Brain 基于下列输入完整思考、校验并
签名输出：

```text
保护后的用户意图
+ 模板/场景的合法结构合同
+ 已冻结的 VisualAssetBindingSet
+ Doc93/共享 evidence admission 的裁决
+ CapabilityActivationPlan 与 ResolvedConstraintLedger
→ Brain-owned canonical provider prompt
```

Provider、MCP relay、Review 与 Retry 只消费同一份 canonical prompt、引用证据与 hash。
资产绑定不得成为绕过 Brain 或把结构化片段偷偷送入 Provider 的通道。

### 2.3 资产通道所有权

首发 People Asset / Face Identity 只声明：

```text
face_geometry
face_feature_relationships
same_person_continuity
```

它不拥有毛发、妆容、服装、姿态、灯光、场景、相机、画面风格或产品真相。当前 prompt
仍拥有这些通道，除非未来存在用户显式绑定的、具有独立合同的资产类型。Doc93 的参考图
通道裁决和 Doc171 的保护用户意图仍优先适用。

未来 Person + Product 的组合只是一个 `VisualAssetBindingSet` 内两个不重叠的通道主张：

```text
People Asset  -> 人物身份通道
Product Asset -> 产品身份/外形/包装等产品真相通道
current request -> 场景、动作、光线、构图和商业表达
Remote Brain -> 把以上事实解释为本次完整图像意图与最终 prompt
```

重叠、过期、未经激活、无同意来源或证据不一致的资产必须在 Provider 前阻断；不得偷偷
选另一个资产、改成无资产项目或把完整人物图当作任意风格参考。

## 3. 新的领域合同

### 3.1 Library Asset（资产库记录）

新建资产的逻辑归属是 library，不是某一个 project：

```python
class VisualAsset:
    visual_asset_id: str
    asset_type: str              # people | future_product | future_scene | future_brand
    display_name: str
    owner_scope: str             # current authenticated workspace/user scope
    lifecycle_status: str        # draft | preparing | review | active | superseded | archived | blocked
    root_source_provenance: dict # existing V3 uploaded asset IDs + consent references only
    active_version_id: str | None
    versions: list[dict]         # metadata/lifecycle pointers; no duplicated image bytes
    created_at: str
    updated_at: str
    provenance: dict

class VisualAssetVersion:
    version_id: str
    visual_asset_id: str
    module_type: str             # face_identity first release
    lifecycle_status: str        # draft | preparing | review | active | failed | superseded
    owned_channels: list[str]
    approved_evidence_refs: list[dict]
    review_summary: dict         # safe user-facing projection + protected audit receipt
    activation_confirmed: bool
    immutable_source_provenance: dict
```

现有 `PeopleAsset`、`FaceIdentityModule`、`IdentityAnchorPackVersion` 可作为这些合同的
第一阶段内部实现或迁移来源，但新记录不再以 `project_id` 作为所有权根。

资产库不复制上传图、输出图、Provider 响应、候选图、review/retry 历史或生物特征向量。
这些仍留在现有 V3 Upload / Output / Job / History 存储中，仅以安全 ID 与摘要关联。

### 3.2 ProjectVisualAssetBinding（项目选择）

项目不“拥有”资产；项目只保存用户明确确认过的当前绑定意图：

```python
class ProjectVisualAssetBinding:
    binding_id: str
    project_id: str
    visual_asset_id: str
    selected_version_id: str
    asset_type: str
    owned_channels: list[str]
    user_confirmed: bool
    status: str                  # active | removed | superseded_for_future_jobs | blocked
    created_at: str
    provenance: dict

class VisualAssetBindingSet:
    binding_set_id: str
    project_id: str
    bindings: list[ProjectVisualAssetBinding]
    state: str                   # valid | empty | blocked
    contract_version: str
```

规则：

1. 一个项目可以拥有零个或多个当前绑定；首发 UI 只允许选择 People Asset。
2. 同一 binding set 内不能存在重叠 `owned_channels` 的活跃资产版本。
3. 用户创建新 Job 时，服务端将当前有效 set 复制为不可变 `FrozenVisualAssetBindingSet`。
4. 资产库之后激活新版本、归档旧版本或项目后来更换绑定，均不得改变历史 Job。
5. “继续制作”默认继承父 Job 的 frozen set；用户想切换资产时必须明确创建新的绑定修订，
   保留 lineage 与用户确认记录。
6. 已绑定但失效的资产不会触发 Standard fallback；新运行被阻断并给出“选择其他已启用
   资产 / 解除本项目绑定 / 返回项目”的明确动作。
7. 无资产绑定不叫失败，也不需要 Professional flag；它就是既有 Standard execution path。

### 3.3 FrozenVisualAssetBindingSet（Job 真相）

```text
Project 的当前绑定
→ 服务端确认资产版本、同意来源、通道不重叠与引用证据有效
→ 生成 Job 时冻结一份 binding set snapshot
→ 将安全的 typed evidence 送入 Reference admission / Brain / envelope / ledger
→ Provider 与 Reviewer 使用完全相同的 admitted evidence IDs + hashes
```

公开响应只显示资产昵称、类型、状态和用户可理解的下一步。原始路径、完整 prompt、
候选 ID、供应商细节、hash、内部 score 仅进入受控审计。

## 4. API 与迁移合同

### 4.1 新的库级 API（目标公共合同）

所有写入要求认证的 owner scope，且服务端从会话/工作区和项目授权上下文解析权限，
不相信浏览器传入的 owner、版本、证据、路径或 prompt：

```text
GET  /api/v3/creative-agent/visual-assets
POST /api/v3/creative-agent/visual-assets
GET  /api/v3/creative-agent/visual-assets/{visual_asset_id}
POST /api/v3/creative-agent/visual-assets/{visual_asset_id}/prepare
POST /api/v3/creative-agent/visual-assets/{visual_asset_id}/activate
POST /api/v3/creative-agent/visual-assets/{visual_asset_id}/archive
```

创建仍复用现有 upload → content → complete 机制；输入只能包含已经 `ready` 的上传资产 ID、
用户可读显示名、同意/来源记录与一个受保护的 preparation intent。`prepare` 公共 body
为空；Brain plan、视角证据、canonical prompt、Provider 与 Vision 全由共享服务端 host
控制。`activate` 仅接受服务端已有 version 和 `confirm_activation=true`。

### 4.2 项目绑定 API（目标公共合同）

```text
GET    /api/v3/creative-agent/projects/{project_id}/visual-asset-bindings
POST   /api/v3/creative-agent/projects/{project_id}/visual-asset-bindings
PATCH  /api/v3/creative-agent/projects/{project_id}/visual-asset-bindings/{binding_id}
DELETE /api/v3/creative-agent/projects/{project_id}/visual-asset-bindings/{binding_id}
```

`POST/PATCH` 只能提交可选资产 ID / version ID 与显式 `confirm_binding=true`；服务端验证
类型、所有权、版本、通道、引用和模板 compatibility。`DELETE` 只影响后续 Job，并要求
用户确认。它绝不删除资产本身、历史 Job 或历史 final delivery。

模板可通过 catalog 返回可接受的 `asset_type`/channel capability；前端不得硬编码
General/E-Commerce/Photography 的资产上限或未来类型。首发模板全部可以接受 active
People Asset，但每个模板继续控制自身交付结构。

### 4.3 历史 project-scoped 路由与数据

历史路由：

```text
/projects/{project_id}/people-assets
```

只保留读取、历史恢复与可审计迁移用途。新前端、新项目、新 Job、新 anchor pack 不得继续
写入它们。迁移不得自动发生：

```text
旧 project-scoped People Asset
→ 用户在资产库中明确“加入视觉资产库”
→ 服务端重新验证 ready root、consent、active reviewed pack/version 与 owner scope
→ 创建或关联 library asset，并保留 migration provenance
→ 用户再明确绑定到任意项目
```

不能证明来源、同意、版本或资产所有权的旧记录维持只读，不可提升成 library asset。
历史 `professional_mode`、`people_asset_id`、legacy resolver 只用于读取历史 Job；它们
不得被写进任何新 Brain、envelope、provider 或普通 UI 路径。

## 5. 前端完整重构

### 5.1 全局导航与首页

V3 首页保留清晰的模板选择和“最近项目”，并新增相邻但独立的入口：

```text
[项目工作台]  [视觉资产库]

项目工作台
  General / E-Commerce / Photography 模板卡
  最近项目
  新建项目

视觉资产库
  我的视觉资产
  新建人物资产（第一阶段唯一可点击类型）
  未来资产类型：不展示伪按钮，不提前承诺
```

删除新用户路径中的“标准创作 / 专业模式”二元单选。若旧 V1/V2 仍有历史“专业模式”
标签，必须写明其仅属于 V1/V2，不是 V3 视觉资产库。

### 5.2 视觉资产库工作区

资产卡只显示：名称、类型、缩略图（如可安全显示）、状态、最近使用、当前已启用版本、
可用操作。状态必须是人话：

```text
需要源图
源图正在准备
正在建立标准建模
正在检查人物参考
等待你确认启用
已启用，可用于项目
需要重新处理
已归档
```

人物资产建立流程：

```text
新建人物资产
→ 上传或选择已准备好的源图
→ 明确来源/授权确认
→ 填写自然语言的建模意图（不是 prompt 表单）
→ 开始标准建模
→ 展示正面 / 侧前方 / 侧面的进行状态、通过/需处理和人话原因
→ 全部合格后“启用此版本”确认弹窗
→ 回到资产库，显示“已启用，可用于项目”
```

锚点候选、raw prompt、score、hash、Provider、内部 review issue 和 job ID 不进入普通表面。
“准备素材”不计入项目正式交付；它和项目结果区完全分离。

### 5.3 新建项目与资产绑定弹层

项目创建仍然是：选择模板 → 写需求 → 可选上传普通参考。创建后，在项目 compose 顶部
提供：

```text
视觉资产：未使用  [选择视觉资产]
```

点击后打开绑定弹层：

```text
选择要用于本项目的已启用视觉资产

[ ] 人物资产：小雨（已启用）
[ ] 人物资产：童模 A（已启用）

未来：产品 / 场景 / 品牌资产在其模块上线后由同一列表出现

说明：选中的资产只会保护它所负责的真实信息；本次需求仍决定服装、场景、光线、
构图和风格。开始生成后，本次使用的版本会固定在该任务中。

[取消] [确认使用]
```

弹层必须：

```text
只显示当前模板可接受、当前用户有权使用、已启用且证据完整的资产
明确显示无可用资产时“前往建立人物资产”，而非默认创建 General 项目
在通道冲突、版本过期或模板不支持时显示人话原因
让用户先确认，不能点击卡片即静默写入绑定
```

### 5.4 项目详情、续作与资产切换

项目页固定显示一个“本项目视觉资产”摘要：

```text
本项目使用
人物资产：小雨 · 已启用版本
[管理资产]
```

管理页允许新增、替换或移除后续项目绑定，并解释：

```text
已完成的图片和正在保留的历史不会变化。
下一次生成会使用你确认后的资产选择。
```

续作默认从父 Job 的 frozen binding set 继续，不能因资产库“当前版本”变化而悄悄漂移。
如果用户要对续作换人物/产品资产，前端必须先创建一次明确的 binding amendment；系统保留
lineage，且与现有 Doc105 continuation 兼容。

### 5.5 状态、错误、恢复与无障碍

Doc172 的共享状态真相仍是所有页面的底座。新增资产层的人话动作：

| 状态 | 显示 | 下一步 |
| --- | --- | --- |
| asset draft | 还需要一张可用源图 | 上传/选择源图 |
| root not ready | 正在保存或检查源图 | 等待/刷新 |
| preparation running | 正在建立人物标准参考 | 等待/返回资产库 |
| review withheld | 标准参考尚未通过检查 | 查看说明/重新准备 |
| ready to activate | 人物标准参考已完成 | 确认启用 |
| binding blocked | 本项目选中的资产暂时不能使用 | 选择其他资产/解除绑定 |
| catalog unavailable | 视觉资产暂时无法读取 | 重新加载；禁止写操作 |

错误映射不得显示 HTML、HTTP、Provider、Brain、hash、路径、job ID、候选 ID 或秘密。
四个断点 1440/1024/430/390 都需要验证：焦点顺序、弹层返回、非颜色状态、按钮禁用、
长名称换行、图片加载失败恢复和刷新后的服务端状态回读。

## 6. 运行时整合

### 6.1 创建 Job

```text
project template + protected user intent + current valid binding set
→ Binding Resolver 验证类型、版本、owner、consent、通道与模板 capability
→ FrozenVisualAssetBindingSet
→ Doc93 Reference Admission / ResolvedConstraintLedger
→ Remote Brain complete semantic task profile + canonical prompt
→ frozen CapabilityActivationPlan
→ shared Provider / Review / bounded retry / final delivery
```

没有绑定的项目直接使用当前 Standard path。存在但无效的用户明确绑定必须 `blocked`；
系统不得根据 prompt 关键词猜测用户想用哪个资产，也不得将它悄悄从项目中移除。

### 6.2 模板隔离

```text
General
  接收可选的 binding set，但不获得电商、摄影或专业套图语义。

E-Commerce
  接收可选的 binding set 与自身事实/平台证据；不重启 recipe、slot、默认营销文案。

Photography
  接收可选的 binding set 与自身摄影角色；不产生 General 降级或私有身份路径。

Visual Asset Library
  不拥有 E-Commerce/Photography 的 deliverable map，也不决定镜头、场景或套图。
```

### 6.3 本地 MCP 与 Web Provider 一致性

本地 Codex Native relay 可作为 conversation-only 的图像通道，但仅在 binding set、
canonical prompt hash、reference source hashes 与输出数量完全匹配时转发。同一资产绑定
不允许在 MCP 中重新规划、替换引用、生成 Provider 私有记录、认证交付或跳过共享真相。
MCP 的存在不能改变资产库、项目绑定或 Web Provider 的产品语义。

## 7. 实施顺序

### P0 — 文档消歧与红色回归

```text
发布本 Doc173，并给冲突旧文档加明确的 forward-authority 标记
为“新资产不 project-scoped”“新项目不写 professional_mode”“无绑定即标准路径”写红测
为 library owner、asset version、binding set、job freeze、历史只读兼容写合同测试
```

### P1 — Library ownership 与兼容迁移

```text
实现 library-scoped VisualAsset catalog/resolver
复用既有 Upload、Output、AnchorPackPreparationService、Persistent catalog storage
实现旧 project-scoped record 的只读 adapter 和显式 promotion/migration
禁止新写 project-scoped people-assets
```

### P2 — 项目绑定与冻结执行

```text
实现 ProjectVisualAssetBinding / BindingSet API
在 Project 创建、Job 创建、continuation 中冻结版本与证据
以共享 ledger/admission 验证通道冲突
保留历史 professional_mode resolver 仅用于旧 Job readback
```

### P3 — 前端信息架构重构

```text
增加“视觉资产库”一级入口
实现人物资产 lifecycle UI
实现项目内选择/管理视觉资产弹层
移除新项目的 Professional Mode 二元开关与 project-scoped 资产创建表面
将旧项目显示为历史兼容，不误标为当前资产绑定
```

### P4 — 跨模板与浏览器验收

```text
General / E-Commerce / Photography 各验证一个无资产项目和一个 People Asset 绑定项目
模板目录不可用、资产库不可用、资产失效、冲突、刷新/重开、重复点击、移动端进行验证
每条失败路径有下一步；无 HTML/内部标识泄漏；无 silent Standard fallback
```

### P5 — 未来扩展（不在本次实现）

产品资产、场景资产、品牌资产以及多人/人+产品组合只在 P1–P4 的通用 binding set、
channel conflict、UI selection 和冻结合同都通过后，分别由独立规格开发。不得为了预留
而写产品提示词配方、产品表单、固定组合卡或本地多资产拼接。

## 8. 必须验证的验收矩阵

### 8.1 数据与运行时

```text
新建资产没有 project_id ownership；旧资产可读但不自动升级
同一个 active People Asset 可被两个不同项目明确绑定
一个 Job 冻结一个完整 binding set，资产库版本更新不改历史 Job
无绑定项目与当前 Standard path 字节/合同兼容
显式无效绑定在 Provider 前 blocked；不得静默回到 Standard
绑定资产的 Provider 与 Reviewer evidence IDs/hashes 完全一致
Brain 输入只包含 sanitized typed asset evidence；最终 prompt 只来自 Brain
General/E-Commerce/Photography 不出现对方的 asset or deliverable 语义
future Product Asset 未实现时不能通过伪 type 或 metadata 进入 binding set
```

### 8.2 用户路径

```text
视觉资产库：源图上传 → ready → prepare → review → explicit activate → 刷新重开
项目：选择模板 → 创建 → 选择一个 active People Asset → 生成
项目：无资产创建与生成（保持 Standard）
项目：资产过期/冲突 → 看懂原因 → 换资产或解除绑定
项目：更新绑定后继续制作 → 新 Job 使用新 snapshot，旧 Job 保持原 snapshot
项目：同时显示现有与未来 placeholder 类型时，不出现不可用的伪按钮
```

### 8.3 浏览器与可访问性

```text
1440 / 1024 / 430 / 390 均完成上述路径
弹层打开后焦点进入；关闭后返回触发按钮
所有状态有文字而非仅颜色
键盘可到达上传、选择、确认、取消、刷新与返回
图片加载失败、网络失败、刷新/重开能恢复到服务端真相
```

## 9. 明确禁止

```text
把 Visual Asset Library 伪装成一个新模板或“专业版 General”
新项目继续写入 project-scoped People Asset 作为权威资产
根据“人物/模特/产品”等关键词自动绑定资产
把资产状态、候选图或锚点包误计为项目最终交付
本地拼接提示词、负面词、年龄/肤色/场景/镜头配方来使用资产
新增 Provider、Brain、Review、Retry、图片库、embedding 库或私有 face repair
让旧 metadata/recipe/slot/overlay 进入新 binding、Brain 或普通 UI
资产失败时偷偷改成无资产生成；或因无资产而阻断普通 Standard 项目
在产品/场景资产尚未有独立合同前开放它们的创建按钮
```

## 10. Definition of Done

本重构只有同时满足下列条件才可标记 `visual_asset_library_first_frontend_ready`：

1. 新建资产的 library ownership、项目 binding、Job freeze 与历史兼容均有测试。
2. 新前端有独立视觉资产库，项目创建不再要求/显示 Professional Mode 二元开关。
3. 用户可从资产库建立并显式启用 People Asset，也能在 General、E-Commerce、Photography
   项目中独立选择或不选择它。
4. 标准无资产项目、已有模板语义、共享 Brain/Provider/Review/Retry、Doc93 通道所有权
   和 Doc101 冻结计划均没有回归。
5. 无 silent fallback、无内部错误泄漏、无项目级资产新写入、无本地 prompt/关键词配方。
6. P4 的浏览器矩阵、重点后端契约和完整 V3 回归均通过。
7. 现有 Professional M5/production/Gate C/D 仍按其独立真实像素门槛判断；本前端重构
   不得借用文档、MCP 或结构测试宣称已通过生产验收。
