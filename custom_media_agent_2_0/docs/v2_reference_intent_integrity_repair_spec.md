# V2 参考图与原始意图完整性修复方案

- 日期：2026-07-17
- 状态：V2 独立分支已完成第一阶段实现，待主线评审/合并；未改动 V3、上游路由或运行配置
- 适用范围：`custom_media_agent_2_0`（以下简称 V2）

## 1. 结论与目标

V2 当前的“手选模板优先、上传素材填充模板、Claude 负责创意”方向是正确的，但实现把多个局部规则写成了可截断的 prompt 字符串。其结果是：模板锚点、资产 guard、视觉语法锁在后续层以前缀形式不断叠加，用户原始意图和 Claude 最终决策位于尾部，可能被静默硬裁剪。

## 实施状态（2026-07-17）

本分支已将本方案的第一阶段接入 V2 运行时：

- `intent_integrity.py` 将用户请求、Claude 创意决定、资产关系、模板框架与控制项编译为可追踪的 intent manifest；不再对 provider payload 做前缀硬裁剪。
- 普通模板与参考图任务的安全预算为 12,000 字符。超过预算时保留完整语义并在 provider 前以 `constraint_budget_unsatisfied` 失败，而不是丢弃尾部意图。
- 上传资产、运行时资产绑定和 provider 输入均记录 `role_source`、`reference_mode`、`reference_index`；明确角色优先于系统建议，参考图顺序会在 preflight 中核对。
- 最终 `CreativeRun`、`ImageJob` 与输出元数据引用经 transform/preflight 后的有效 prompt trace，并保存脱敏 hash、长度、manifest 与 preflight 结果。
- 有参考图的 live 返回只证明传输完成；在未接入像素级审查前，结果会标记为 `needs_review` 和 `reference_adherence_unverified`，不再因 metadata 成功而声称已经遵循参考图。

仍待后续阶段接入的是可配置的像素级参考遵循审查与前端的角色确认交互；两者均不应通过改写、截断或降级原始意图来规避。

这不是单纯的提示词质量问题，而是意图数据模型、冲突解析、预算控制、实际请求追踪和结果验收共同缺失造成的架构问题。

本方案的目标是：

```text
任何进入 V2 的必需用户意图、硬参考约束和 Claude 已确认的创意决策，
在送往 provider 前都必须可追溯、可验证、不可因字符预算被静默删除。
```

这里的“完整”指语义完整，不要求逐字保留原始自然语言。系统可以压缩重复表述、归并同义约束、缩短模板说明；但不得把一个必需语义原子裁掉、降级或改写为相反含义。

## 2. 范围、边界与非目标

### 2.1 本次范围

- 上传资产的角色、用途、约束强度及其来源。
- 用户意图、模板框架、资产意图、Claude 决策之间的优先级与冲突处理。
- 从 `ImagePromptPlan` 到实际 provider payload 的编译、预算与完整性校验。
- 参考图的 provider 输入计划、端点选择和最小能力协商。
- 运行记录、调试追踪与生成后参考遵循验收。
- V2 API、前端确认界面和回归测试。

### 2.2 明确不做

- 不修改 V2 边界之外的业务服务、账户路由或网关。
- 不把 V2 请求转发到非 V2 的存储、队列或接口。
- 不以增加长篇负面提示词、模板名称特例或正则黑名单代替结构化修复。
- 不改变选中模板优先的原则；修复的是模板锁的权限边界。
- 不在未校准前以视觉审核误判为由大面积阻断普通用户生成。
- 不持久化人脸向量、原图像素副本或用户凭据作为审核数据。

## 3. 已核实的故障模式

一次近期的真实 V2 图生图任务显示：

- 上传 JPEG 是可用 reference，V2 打开了本地二进制文件并调用 OpenAI 兼容的 `images.edit`。
- 上游事务也确认实际端点为 `/v1/images/edits`，不是文本生图端点、mock 或无图 fallback。
- 该任务的原始用户输入约 89 字符，Claude final prompt 约 928 字符，而实际 provider prompt 约 5600 字符。
- 输出元数据标记为 `claude_final_prompt`，但实际 prompt 并非 Claude final 的完整内容，也未能证明完整的用户意图仍以等价语义存在。
- 本次 prompt transform 没有额外修改；丢失发生在 transform 之前的模板锚点、资产上下文和视觉语法锁编译阶段。
- 输出 review 在 live provider 成功时自动给出 `pass`，但只检查元数据，不检查生成像素是否真正遵循参考图。

因此，不能把这类问题归因为“模型偶尔不听话”或“原图未上传”。参考图的文件传递可以成功，而表达其用途的语义已经在 provider 调用前失效。

## 4. 当前实现的系统性缺口

| 层 | 当前行为 | 风险 |
| --- | --- | --- |
| 上传 | `role` 可为空，按文件名、透明通道等自动建议角色 | 用户未明确选择时，原图可被静默归类为 `style_reference`；运行记录不能区分用户指定和系统推断 |
| 资产绑定 | 模板锁下 style reference 只能贡献兼容的色彩、光线、材质和氛围 | 用户本想参考原图主体、产品、脸、版式或文字时，可能被错误降级为软审美证据 |
| 意图编排 | 本地资产规则先于 Claude 固化，之后 Claude 决策又可被本地规则改写 | “Claude final”并不是真正的最终创意决定 |
| prompt 组装 | 依次前置模板锚点、资产 guard、视觉语法锁 | 越靠后的用户/Claude 内容越容易被截断 |
| 预算控制 | 多处 `text[:limit] + "..."` 的前缀截断 | 有效意图没有原子级存活保证，且无失败信号 |
| provider 调用 | 参考图时正确使用 edit，但 prompt 不标注每张图的职责 | 上游即使收到图片，也缺少清晰的图像—约束对应关系 |
| 审核 | 以元数据和固定默认分数判定 live 输出 | 无法发现“图已传但没有被参考”的成功假象 |
| 审计 | CreativeRun、ImageJob、history 保存的 prompt 版本可能不同 | 无法可靠回答“实际送上游的是什么、何时发生变化、为何变化” |

## 5. 不可变设计原则

### 5.1 意图原子不可静默丢失

每个必需语义必须以稳定 `intent_id` 表示。只要该原子在当前任务有效，最终 provider 请求或受控的等价编译物中必须有它的可验证映射。

允许：

- 将“不要裁掉产品边缘”“产品需要完整出现”压缩为一个 `subject_visibility=complete` 原子。
- 合并重复的颜色、光线、构图描述。
- 把冗长模板说明压缩为结构化 frame directive。

不允许：

- 因长度到达上限而删除原子。
- 将 `required` 的原图主体降为 `style_reference`。
- 将用户已确认的替换关系改成“仅提取信息”或“仅作装饰”。
- 以 `prompt_source=claude_final_prompt` 标注一个已被后续本地文字实质改写的 payload。

### 5.2 模板控制框架，不拥有用户事实

选中模板仍是最高优先级的视觉框架，控制构图纪律、层级、视觉节奏、灯光逻辑、背景密度和排版气质。

模板不自动拥有以下内容：

- 模板中的原始人物、商品、食物、logo、文案、二维码和占位内容。
- 与用户明确要求或硬上传资产冲突的字面模块。

当两者冲突时，模板框架保留，模板中的可替换槽位适配用户/资产事实。只有用户明确选择“严格复刻模板内容”时，模板字面内容才能成为硬约束。

### 5.3 资产角色必须有来源和可见确认

角色值本身不足以表达用户意图。每个资产都必须记录：

```text
role                 subject / face / logo / background / style / composition / color / negative
role_source          user_explicit / client_default / system_suggestion / claude_validated
intended_use         用于什么、放在哪里、是否保留内容/身份/版式/文字
constraint_strength  required / strong / soft
reference_mode       preserve / replace_slot / style_only / extract_content / avoid
```

系统建议只能是建议。若资产被自动推断为 `style_reference`、`composition_reference` 或 `negative_reference`，而用户提示中存在“原图”“按这个”“保留”“替换”“同款”“不要改产品/人物”等硬信号，必须在提交前要求确认或升级为可解释的硬关系，不可静默降级。

### 5.4 Claude 决策不可被确定性文案替换

Claude 继续负责创意意图、语义融合和最终表达。本地代码只能：

```text
收集事实 -> 验证约束 -> 编译结构 -> 控制预算 -> 选择 provider 能力 -> 记录追踪
```

本地代码不得通过长前缀、旧的角色推断或模板文案把 Claude 已确认的关系替换成另一种创意关系。

### 5.5 无法安全表达即失败或请求决策

若 provider 的真实输入预算、图像数量或能力无法同时承载所有 `required` 原子，系统必须：

1. 先压缩可压缩框架说明；
2. 再尝试更短的 Claude 微阶段，生成等价语义表达；
3. 仍无法满足时，不调用 provider，并返回可解释的 `constraint_budget_unsatisfied` 或要求用户选择哪些可选项可放宽。

不能“先生成再看看”。

## 6. 目标架构

```text
V2 请求
  -> 上传资产事实与用户显式选择
  -> Intent Manifest（不可变语义账本）
  -> Claude 意图/视觉策略 checkpoint
  -> 关系归一化与冲突解析
  -> 模板框架 + 槽位计划
  -> Prompt Compiler（按原子预算编译）
  -> Provider Preflight Integrity Gate
  -> provider payload（prompt + input images + capability profile）
  -> 生成结果
  -> 像素/语义审核与交付决策
  -> 不可变 Trace 和历史记录
```

`Intent Manifest` 是唯一的语义真相来源；自然语言 prompt、模板摘要、provider 参数和审核清单都是它的派生物。任何阶段不得直接对上阶段的长字符串做业务性拼接后截断。

## 7. 核心数据合同

### 7.1 Intent Manifest

建议在 `app/schemas.py` 增加内部模型，所有字段均使用 V2 命名空间：

```json
{
  "manifest_id": "imf_…",
  "version": 1,
  "user_goal": "压缩后的任务目标",
  "atoms": [
    {
      "intent_id": "intent_subject_01",
      "kind": "asset_subject_identity",
      "value": "asset:asset_… must appear as the concrete subject",
      "source": "user_explicit",
      "priority": "required",
      "compressibility": "lossless_semantic_only",
      "provider_evidence_required": true,
      "review_evidence_required": true
    }
  ],
  "template_frame": {
    "selected_case_id": "case_…",
    "priority": "highest_frame_only",
    "locked_elements": ["composition_discipline", "visual_hierarchy", "lighting_logic"],
    "replaceable_slots": ["primary_subject", "supporting_subjects", "literal_copy"]
  },
  "asset_intents": [],
  "conflict_resolutions": [],
  "created_from": ["user_request", "asset_metadata", "claude_checkpoint"]
}
```

关键要求：

- `intent_id` 在一次 run 内稳定，所有后续产物只引用它，不复制不受控的长文本。
- `priority` 只能由有明确来源的规则提升或降低，并记录 `reason`。
- `compressibility=lossless_semantic_only` 的原子不能通过字符串前缀截断解决。
- `source` 不能只写 `system`；必须说明是用户、上传 API、自动建议、Claude checkpoint 或安全策略。

### 7.2 Asset Intent

对每个上传资产建立一次、仅追加的 `AssetIntent`：

```json
{
  "asset_id": "asset_…",
  "requested_role": "subject_reference",
  "resolved_role": "subject_reference",
  "role_source": "user_explicit",
  "reference_mode": "replace_slot",
  "constraint_strength": "required",
  "preserve_channels": ["subject_identity", "product_shape", "visible_markings"],
  "prompt_owned_channels": ["scene", "lighting", "wardrobe", "camera"],
  "placement_intent": "primary_subject_slot",
  "provider_input_required": true,
  "provider_reference_index": 1,
  "review_expectations": ["subject_visible", "subject_complete", "identity_or_product_consistent"]
}
```

对于只作风格参考的图，`reference_mode=style_only` 必须是用户明确选择、或用户确认系统建议后的结果。文件名中含有 `style`、`mood` 等只能产生建议，不能在没有来源说明时覆盖用户文本。

### 7.3 冲突解析记录

冲突不再以一段 prompt 文案处理，而是形成结构化记录：

```json
{
  "conflict_id": "conflict_…",
  "left_intent_id": "intent_template_literal_recipe_card",
  "right_intent_id": "intent_subject_01",
  "resolution": "adapt_template_slot",
  "winner": "user_required_asset",
  "preserved_template_elements": ["hierarchy", "typography_rhythm"],
  "reason": "selected template owns frame, not literal placeholder content"
}
```

冲突顺序固定如下：

1. 安全、法律和平台硬限制。
2. 用户显式的 `required` 事实与硬资产事实。
3. 用户显式的模板锁定选择。
4. Claude 已确认且未与以上冲突的创意决策。
5. 系统建议、默认角色和模板中的字面占位内容。

模板的“最高优先级”只在第 3 层的 frame 属性范围内生效，不得跨层删除第 2 层事实。

## 8. Prompt Compiler 与预算控制

### 8.1 替换现有前缀拼接

应逐步替换 `app/services/prompting.py`、`asset_binding.py` 和 `visual_grammar_lock.py` 中“生成一段 guard -> 放在 prompt 最前面 -> `text[:limit]`”的模式。

新的 compiler 接收：

```text
Intent Manifest
Claude final decision（附 intent_id 引用）
Template frame directive
Asset/provider input plan
Provider capability profile
```

输出：

```text
ProviderPromptArtifact
  canonical_prompt
  sections（每段对应哪些 intent_id）
  included_intent_ids
  compressed_intent_ids
  omitted_optional_intent_ids
  budget_report
  payload_hash
```

### 8.2 编译顺序

编译顺序不是优先级顺序，而是可读性顺序。建议的 provider 文本顺序：

1. 任务目标与主体。
2. 每张输入图的编号和具体职责。
3. 不可变保留/替换要求。
4. 模板框架要求。
5. Claude 的创意实现、场景、光线、镜头和风格。
6. 可选细节与负向约束。

每节只能由它声明引用的 `intent_id` 生成。编译器不应再接收和裁剪一段来源不明的“下游草稿”。

### 8.3 预算算法

设 provider prompt 预算为 `B`，每个原子估算最小语义表达成本 `m_i`：

```text
required 原子的最小表达总量 > B  -> 失败，不发起 provider 调用
否则：
  先保留所有 required 原子
  再保留 strong 原子
  再压缩模板重复说明、Claude 理由、soft 装饰与可选细节
  最后才省略明确标记为 optional 的原子，并写入 omitted 列表
```

禁止使用以下策略作为正常预算控制：

```python
prompt = prompt[:limit]
```

只有在发生程序异常的最后一道防护中可以截取诊断展示文本；该文本不得作为 provider payload。任何 payload 级截断必须转化为可验证的原子压缩或失败。

### 8.4 Claude 交互

Claude checkpoint 和 final prompt 必须返回引用的 `intent_id` 列表，并声明：

```text
covered_intent_ids
needs_clarification_intent_ids
conflict_candidates
```

如果 Claude 的 final 表达未覆盖必需原子，compiler 不得默默补一大段本地创意文案；应要求一次受限的 Claude micro-stage 补齐，或以结构化、非创意的约束短语补足事实，并在 trace 中标记原因。

## 9. Provider 输入与能力协商

### 9.1 参考图端点

当存在 `provider_input_required=true` 的资产时，V2 必须：

- 使用支持图像输入的 V2-native provider 路径。
- 在实际调用前验证文件存在、可读、MIME 合法、数量与输入计划一致。
- 将 `provider_reference_index` 与 prompt 中的“Image 1 / Image 2 …”职责一一对应。
- 保存脱敏的输入数量、角色、索引和文件摘要，不保存不必要的原图副本。

纯文生图保持 generation 路径；有参考图才使用 edit 路径。不得因为 prompt 编译失败而退化到无图 generation。

### 9.2 能力配置文件

在 provider adapter 中引入 capability profile，而不是把上游私有参数写死：

```text
supports_reference_images
max_reference_images
supports_input_fidelity
supported_input_fidelity_values
supports_background
supported_sizes
supported_formats
```

例如，`input_fidelity` 可作为支持时的可选增强，但不是本次根因，也不得在未证实兼容的上游路由中强行发送。缺少该参数不能成为跳过参考图或放弃完整性校验的理由。

## 10. 双层验收：Preflight 与输出审核

### 10.1 Provider Preflight Integrity Gate

在 `create_image_job` 调用 provider 前增加纯结构化检查：

- 所有 `required` intent 都出现在 `included_intent_ids`。
- 每个必需图像资产都出现在 `input_images`，并有匹配的索引和角色。
- 选中模板的 frame directive 存在，但不包含与已决冲突相反的字面锁。
- `prompt_source` 与真实 artifact 来源一致。
- 实际 prompt hash、长度、参数和 endpoint 计划可记录。

失败分类：

```text
intent_manifest_invalid
required_intent_not_compiled
required_reference_missing
provider_capability_insufficient
constraint_budget_unsatisfied
trace_consistency_failed
```

此 gate 不分析图片像素，因此低成本、可同步执行、适合作为硬门。

### 10.2 输出像素审核

现有 `output_review.py` 的 metadata rule 保留为链路检查，但不得再把它当作视觉通过证明。新增独立的 V2 visual adherence reviewer：

- 输入：生成图、必要参考图的短时读取权限、Intent Manifest 的审核期望。
- 输出：每个 `intent_id` 的 `pass / uncertain / fail`、置信度、简短理由和建议。
- 第一阶段仅标记 `needs_review`，不自动删图、不强制重试。
- 对 `required` 主体/产品/face/logo 等高价值任务，在校准并取得足够低误判率后，才允许自动阻止“final delivery”。
- 审核只保存决策、模型版本、输入 hash 和短时 trace；不持久化生物特征向量。

live provider 成功只能表示“链路成功”，不能等同于“参考遵循成功”。

## 11. 可观测性与不可变 Trace

为每次 run 建立 `PromptCompilationTrace`，并让 CreativeRun、ImageJob 与 image history 通过同一 `trace_id` 关联：

```text
trace_id
manifest_id / manifest_version
submitted_prompt_hash + length
Claude checkpoint/final hash + length + covered_intent_ids
compiled prompt hash + length + included/compressed/omitted ids
effective payload hash + endpoint + model + capability profile
input image count + asset role/index summaries
preflight result
review result
```

原则：

- UI 默认显示简明解释，例如“原图作为主体替换参考，已传入 Image 1”。
- 调试页可展示脱敏结构化差异，不默认暴露完整 prompt、原图、用户资料、密钥或 cookie。
- `prompt_source=claude_final_prompt` 仅当 effective artifact 未被实质重编译时允许使用；否则标为 `compiled_from_claude_and_manifest`。
- Queue、history、API response 使用同一 trace 的不可变版本，禁止分别保存互相矛盾的 prompt 快照。

## 12. API 与前端改造

### 12.1 兼容原则

保留现有 V2 请求字段和旧客户端行为。新增字段全部可选，但服务端会为旧请求创建明确的 `client_default` 或 `system_suggestion` 来源记录。

### 12.2 新增/扩展字段

上传请求与 CreativeRun asset input 支持：

```json
{
  "role": "subject_reference",
  "intended_use": "将原图产品替换进模板主视觉",
  "reference_mode": "replace_slot",
  "constraint_strength": "required",
  "preserve_channels": ["product_shape", "visible_markings"],
  "role_confirmation": "user_confirmed"
}
```

前端在提交前展示一张简短的“素材会如何使用”卡片：

```text
素材 A：作为主体替换参考；保留产品外形；将传给图像模型；模板控制构图和光线。
```

当系统仅有推断而用户文本可能表达硬意图时，展示“系统建议：仅作风格参考”并要求用户确认或修改，不得在后台静默处理。

### 12.3 运行状态

将原有的笼统成功状态细化为：

```text
compiled -> preflight_passed -> provider_running -> provider_completed
-> visual_review_pending / visual_review_passed / visual_review_uncertain
```

这不会改变 provider 的同步/异步边界，只改善用户和运维人员对“生成成功”含义的理解。

## 13. 实施分期

### Phase 0：基线与回归夹具

目标：冻结当前行为的可复现、安全脱敏样例。

- 将近期“参考图已传但未被遵循”的任务整理为脱敏 fixture，仅保存结构、尺寸、角色和预期，不纳入用户图片。
- 为直接 API、CreativeRun、重试和 provider edit 建立测试入口。
- 建立 trace 对比工具，比较 manifest、compiled prompt 与 effective payload 的 hash/意图覆盖。

验收：不改生产行为；已有 V2 测试全绿。

### Phase 1：数据合同与 Trace（影子模式）

目标：先记录事实，不影响现有 prompt。

- 增加 `IntentManifest`、`AssetIntent`、`PromptCompilationTrace` schema 与持久化。
- 上传角色记录 `role_source`；旧记录迁移为可解释的默认来源。
- 在现有链路旁生成 manifest 和 trace，但仍使用旧 compiler。

Feature flags：

```text
V2_INTENT_MANIFEST_ENABLED=true
V2_PROMPT_TRACE_ENABLED=true
V2_INTENT_PREFLIGHT_ENFORCED=false
```

验收：同一 run 的 queue/history/API 能关联一个 trace；无用户可见行为改变。

### Phase 2：关系解析与资产确认

目标：消除静默 role 降级。

- 本地角色推断改为 suggestion，不直接当作最终 resolved role。
- Claude intent checkpoint 消费 preliminary evidence，但不接收已硬化的本地创意结论。
- 解析 `replace_slot`、`preserve_identity`、`style_only`、`extract_content` 等通用关系。
- 在前端增加确认卡与服务端 `role_confirmation` 验证。

验收：显式主体/产品/face/logo 诉求不会变成 style-only；未确认歧义场景有可解释状态。

### Phase 3：原子化 Prompt Compiler（影子比较）

目标：替换字符串拼接，但先不切流。

- 实现 compiler、预算报告和 `included_intent_ids`。
- 在每次 run 同时生成旧/new 两份 artifact，比较必需原子覆盖与 token/字符预算。
- 移除 payload 路径中的前缀硬截断依赖；保留旧逻辑仅供对照。

Feature flag：

```text
V2_INTENT_COMPILER_ENABLED=false
```

验收：所有 `required` 原子都能通过新 compiler；预算不足得到明确失败分类而非截尾。

### Phase 4：Provider Preflight 与实际切流

目标：只让完整、可解释的请求到达 provider。

- 以新 compiler artifact 替代旧 prompt 文本。
- 在图像编辑前检查参考图、索引、端点和能力配置。
- 将实际有效 payload 的 hash 与 endpoint 写入同一 trace。

Feature flags：

```text
V2_INTENT_COMPILER_ENABLED=true
V2_INTENT_PREFLIGHT_ENFORCED=true
```

验收：有参考图的 required 任务不能降级为无图 generation；trace 可准确复原实际请求结构。

### Phase 5：审核与交付状态

目标：检测“链路成功但参考失效”。

- 先接入 advisory visual adherence reviewer。
- 将 metadata review 改名为 transport/metadata review，避免语义误导。
- 为高价值硬参考任务收集人工复核样本，校准视觉审核阈值。

验收：审核能区分 provider 成功与参考遵循成功；在未校准前不造成批量误拦截。

### Phase 6：清理、默认开启与旧数据兼容

目标：完成迁移。

- 移除或隔离旧的 payload 硬截断代码路径。
- 将新 compiler 设为默认，保留按 run 的回滚开关。
- 补齐历史记录的 `trace_version` 兼容读取。

验收：V2 回归、部署 smoke、真实单图参考任务和多图任务均通过；旧历史可读取。

## 14. 代码落点

| 模块 | 改动职责 |
| --- | --- |
| `app/schemas.py` | Intent Manifest、Asset Intent、Trace、preflight/review 状态模型 |
| `app/services/uploaded_assets.py` | 保存 role source、用户确认和资产用途，不把 suggestion 当最终结论 |
| `app/services/uploaded_asset_vision.py` | 仅输出角色建议与置信度，不输出不可逆业务决定 |
| `app/services/asset_binding.py` | 根据 manifest/Claude 关系解析 provider 输入和槽位计划；不再通过文本 guard 裁决语义 |
| `app/services/claude_orchestrator.py` | 输出带 intent_id 覆盖声明的 checkpoint/final decision |
| `app/services/prompting.py` | 改为原子化 compiler，删除正常路径的前缀截断 |
| `app/services/visual_grammar_lock.py` | 输出结构化 frame directive；不得生成覆盖业务意图的大段前缀文本 |
| `app/services/prompt_transform/*` | 只变换已验证 artifact，保留 trace，不再引入无记录的语义改变 |
| `app/services/generation.py` | 执行 preflight，保存实际 payload trace，统一 queue/history 快照 |
| `app/providers/images/openai_gpt_image_2.py` | 消费 capability profile，显式绑定图像索引、端点与可选 fidelity 参数 |
| `app/services/output_review.py` | 区分链路审核与视觉遵循审核 |
| `app/services/visual_review_agent.py` | 接入短时像素审核，输出 intent 级证据，不把 metadata 当视觉结论 |
| V2 前端 | 资产用途确认、运行 trace 摘要、审核状态展示 |

## 15. 测试与验收矩阵

### 15.1 必做单元与性质测试

- 对任意 `required` intent 集合，compiler 输出必须覆盖全部集合；否则报明确错误。
- 增加超长模板、超长 Claude 文本、超长用户文本的 property test，证明不会出现尾部静默丢失。
- `style_reference` 的系统建议不能覆盖用户显式 `subject_reference`。
- 选中模板时，硬资产能替换可替换槽位，但不会改写模板的框架属性。
- `extract_content` 与 `replace_slot` 不能相互退化。
- provider input count、参考索引、prompt 中图像职责和 manifest 一致。
- queue、history 和 API 返回的 effective payload hash 一致。

### 15.2 回归场景

| 场景 | 必须证明 |
| --- | --- |
| 单张产品原图 + 手选模板 | 产品作为具体主体传入 edit，模板只控制 frame |
| 人像原图 + 新场景 | 保留身份关键特征，场景/光线由当前提示词控制 |
| logo 放在包装/衣物 | logo 是场景表面元素，不退化为角标 |
| 纯风格参考图 | 仅在用户确认 style-only 后允许弱化内容保留 |
| 多图主体替换 | 每张 required 图都有索引、槽位和审核期望 |
| 菜单/海报信息提取 | 保留事实而不复制来源版式，除非用户明确要求 |
| 无图纯文生图 | 仍走 generation，且不引入 edit 或参考审核负担 |
| provider 超时/4xx | 保持既有重试与错误分类；不以 mock 掩盖真实失败 |
| 预算不足 | 阻止 provider 调用，返回 `constraint_budget_unsatisfied`，不截断 |

### 15.3 部署验收

1. 本地 V2 focused tests 与完整 V2 test suite 通过。
2. staging/受控 VPS 完成一条无图任务、一条单图硬参考、一条多图替换和一条纯风格参考任务。
3. 每条任务仅回传脱敏 trace 摘要：端点类型、输入图数量、原子覆盖、状态、时长、是否得到文件和审核结论。
4. 不记录或打印用户完整 prompt、图片、cookie、token、密码、provider 密钥。

## 16. 指标、告警与回滚

### 16.1 指标

```text
v2_intent_required_coverage_ratio
v2_prompt_budget_unsatisfied_total
v2_asset_role_suggestion_confirmation_rate
v2_required_reference_preflight_fail_total
v2_trace_consistency_fail_total
v2_visual_adherence_uncertain_or_fail_rate
v2_provider_edit_with_reference_success_rate
```

重点告警：`required_intent_not_compiled`、`required_reference_missing`、queue/history payload hash 不一致，以及 provider 成功但视觉审核高频 fail。

### 16.2 回滚

- 以 feature flag 按 run 切回旧 compiler；不删除已写入的 manifest/trace。
- 若 visual reviewer 不稳定，仅关闭其 delivery gate，保留 advisory 记录。
- 若 capability profile 与兼容上游不匹配，只关闭该可选能力；不得改回无图 fallback。
- 回滚限定在 V2 服务和 V2 数据表/文件，不能依赖或修改 V2 边界之外的运行时。

## 17. Definition of Done

本修复只有同时满足以下条件才算完成：

- 没有正常请求路径通过 `prompt[:limit]` 一类代码裁剪 provider payload。
- 每个 required 用户/资产意图从输入到 provider payload 都有稳定 trace。
- 自动资产角色建议不会在无来源、无确认的情况下覆盖显式用户意图。
- 模板锁明确只锁 frame，且对可替换资产槽位的冲突有结构化解释。
- 有参考图的任务能证明实际传入 V2-native provider edit/input-image 路径。
- provider 成功、文件落盘、视觉审核通过是三个不同且可见的状态。
- CreativeRun、ImageJob、history/API 对实际 payload 的记录一致。
- V2 回归矩阵通过，且没有引入对其他版本、存储或路由的依赖。

## 18. 实施顺序建议

建议严格按 Phase 0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6 推进。不要跳过 trace 和影子比较直接改 prompt 文案；否则仍无法区分“意图没被编译”“图没被传入”“上游没有遵循”“审核没有发现”四种不同问题。

本文件是 V2 独立优化规格。它可与现有 V2 的中央意图模型、模板视觉语法转移设计协同实施，但不引入其他版本的治理、运行时、存储或 provider 路径。
