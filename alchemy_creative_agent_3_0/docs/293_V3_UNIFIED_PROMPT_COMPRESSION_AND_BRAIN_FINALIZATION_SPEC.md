# Doc293 V3 Unified Prompt Compression and Brain Finalization Specification

**Status:** implemented in the isolated feature worktree; focused audit and regression tests passed; integrated acceptance pending

**Contract revision:** `v3_unified_prompt_compression_v1`

## 1. User requirement and objective

原始要求：最终的生成提示词只在过于冗长时压缩。经补充分析，本规范采用超过 6000 字符才压缩、最终控制在 3500 字符以内的保守策略；未超过时不压缩。历史版本的压缩逻辑不得互相叠加、互相覆盖或继续产生隐藏阈值。

本规范只解决 V3 的**最终自然语言 Renderer Prompt**。它不改变图像 Provider、模型、参考图绑定、Review、V1/V2、Veyra/Sub2API 或 VPS 部署。

目标：

1. 保留 Brain 作为最终创意方向和 Provider Prompt 的唯一语义作者。
2. 统一阈值、目标长度、压缩入口和失败行为。
3. 用户原文、明确尺寸、场景、构图、镜头、光影、材质、风格、人物真实感和参考边界不得因压缩丢失。
4. 不使用正则、关键词命中、按行裁剪或本地拼接来判断或修复语义。
5. 让短 Prompt 可以自然地短，但不允许复杂请求在缺少完整语义签字时静默通过。

## 2. Root cause and historical boundary

### 2.1 2026-09-06 是触发点，但不是唯一的压缩器

`684a8478` 在 2026-09-06 从规划阶段请求中删除了一份重复的
`human_expression_authenticity_instructions`，保留 system/finalizer 权威；
`5f3b9f52` 随后只补回紧凑的 Human Realism 规划上下文。这两次变更没有直接把最终
Renderer Prompt 截断到 304 字符，但使最终 Prompt 对 Brain 的完整语义编排依赖更高，
而现有 canonical finalizer 没有“完整语义已覆盖”的硬签字。

真正把这类短 Brain 输出直接送给 Provider 的边界是 2026-07-16 引入的
Brain-owned canonical provider prompt：canonical prompt 存在时，Provider 绕过本地
Prompt 组装和旧压缩器，直接使用 Brain 返回文本。因此 2026-09-06 暴露的是
**上下文去重后的最终语义完整性缺口**，不是一个单独的字符串切片函数。

### 2.2 必须明确区分的三类长度处理

| 层 | 现有职责 | 本规范处理方式 |
|---|---|---|
| Brain 请求 payload 的结构化裁剪 | 限制 ID、列表和结构化字段，降低请求体冗余 | 继续由 Doc290/契约 owner 管理；不得截断 `user_input` 或硬事实 |
| 最终 Renderer Prompt 的语义压缩 | 过长自然语言方向进入 Provider 前的唯一压缩 | 由本规范统一为一套 Brain-owned policy |
| Provider transport limit | 上游协议/网关的技术上限 | 只做长度校验和发送，不改写创意文本 |

不能把三者都叫作“Prompt 压缩”，也不能用 payload 的字段限长证明最终创意方向已保真。

## 3. Authority model

按以下顺序解释和执行：

1. 用户原始请求和服务器冻结的硬事实是不可丢失输入。
2. Brain 根据冻结上下文、共享能力契约和参考边界作语义判断。
3. Brain canonical finalizer 生成最终 Renderer Prompt，并签发语义完整性结果。
4. 若触发压缩，只能由同一 Brain finalizer 在同一冻结上下文中语义重写。
5. Provider 只验证签字、绑定、长度和 transport 能力，然后发送文本；不得追加、删除、按行挑选或本地改写。

`HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS` 等通用规则在 system/finalizer 保持单一权威，
不能为了“恢复细节”再次完整复制进 planning payload。规划 payload 只携带一次必要的、
紧凑的结构化能力上下文。

## 4. Unified compression policy

### 4.1 Single source of truth

新增一个版本化的内部策略常量/契约，所有新 Renderer Prompt 只读取这一份：

```text
policy_rev                    = v3_unified_prompt_compression_v1
compression_threshold_chars   = 6000
compression_target_max_chars  = 3500
max_length_policy_recovery    = 1
transport_required_hard_limit = 6000
```

`3500` 是上限而不是填充目标。压缩后的结果可以是 2200、3000 或 3500 字符，
只要 Brain 证明语义完整；系统不得为了凑长度添加废话。

这里的 `6000/3500` 是 V3 的保守产品策略，不是对上游 Provider 硬限制的猜测：
现有历史证据只显示约 15000 至 16000 字符附近更容易触发网关拒绝，尚未证明
6000 字符本身就是失败拐点。选择 6000 是为了在已知风险区之前主动收敛，选择 3500
是为了给复杂人物/场景保留足够的语义密度；不得继续降到 3000 以下作为默认值。
该策略只作用于逐输出的 Renderer Prompt，不作用于 Brain JSON 请求体、结构化事实
或 `max_tokens`。Brain 请求体仍按 Doc290 的字段权威和共享 token 预算治理。

长度策略按 Unicode 字符计数；Provider 另外按实际 UTF-8 序列化检查安全传输包络。当前
配置项表达的是 Unicode 字符上限，因此安全包络按每个 Unicode code point 最多四个
UTF-8 字节计算；这不是第三个语义阈值。若某个
新 Provider 的硬上限低于 6000 字符，不能偷偷引入第三个阈值，必须把该 route 标记为
不支持此契约并在 Provider admission/能力协商边界失败；严格路径不得静默取
`min(configured_cap, 6000)`。非法 UTF-8 文本同样必须在该边界转换为结构化 contract
failure，不能让底层编码异常直接冒泡。

### 4.2 Decision table

| canonical Prompt 长度 | 行为 | 是否追加 Brain 调用 |
|---|---|---|
| `0` 或缺少合法签字 | fail-closed | 否 |
| `1..6000` | 按签字文本发送，不做语义压缩 | 否 |
| `>6000` | canonical finalizer 在本次签发中选择 `brain_semantic_once`，目标不超过 3500；若返回仍违规，只复用既有 finalizer bounded recovery | 最多一次长度策略 recovery |
| 压缩后仍 `>3500` 或签字不完整 | 不发送图像请求，返回明确 Prompt contract failure | 否 |

压缩只在最终 canonical Prompt 超过 6000 时发生。不能因为模型、场景、人物、
Human Realism 或 Provider 的偏好提前压缩短 Prompt。

### 4.3 Single execution pipeline

所有新 real-image 请求只能经过下面这一条顺序管线；不得在 Provider、Review 或
scenario adapter 中再加第二个 Prompt 长度判断，也不得新增独立的摘要/压缩 LLM 阶段：

```text
frozen Brain canonical record
  -> one existing canonical finalizer signs prompt + semantic/compression receipt
  -> count Unicode characters
  -> <= 6000 + compression=none: keep signed text unchanged
  -> <= 3500 + compression=brain_semantic_once: keep signed text unchanged
  -> length/completeness violation: reuse existing finalizer bounded recovery once
  -> validate complete semantic/compression receipt
  -> check route transport bytes (no text rewrite)
  -> send exactly the validated text
```

执行器必须返回唯一的 `compression_decision`：`none`、`brain_semantic_once` 或
`blocked`。该决定和 `policy_rev` 随脱敏 receipt 保存，后续代码不能根据旧的
`max_provider_prompt_chars`、`internal_budget` 或某个 Provider 名称再次决定。

canonical finalizer 在一次响应中完成“是否需要语义压缩”和最终创作，不返回中间草稿，
也不新增一个 Prompt 摘要服务。若现有 bounded recovery 仍返回超过目标、缺少完整度
签字或绑定的冻结上下文不同，直接 `blocked`。不能回退到本地旧 Prompt、旧行裁剪器、
真人感片段或重新组装的 scenario recipe。

### 4.4 Semantic preservation contract

当 canonical finalizer 判断需要压缩时，它必须基于完整的冻结 render context 完成一次
语义重写；现有的 Prompt/上下文契约必须让 Brain 能看到用户原文和硬事实。Brain 必须：

- 保留用户明确的主体、场景、动作、构图、镜头、光线、色彩、材质、风格和情绪；
- 保留用户明确的画幅、比例和尺寸意图；
- 保留活动的 Human Realism、年龄真实性、皮肤材质、真实相机和反塑料语义；
- 保留参考图/历史生成图实际拥有的身份、产品或其他渠道边界；
- 删除重复表达、解释性废话、内部字段名和流程说明；
- 不新增用户没有要求的场景、商品、年龄、镜头、风格或审查标准；
- 不把内部 contract key、review code、项目 ID、Prompt 压缩说明写入 Renderer Prompt。

这是 Brain 的语义职责。运行时只验证结构化签字和冻结绑定，不用正则、关键词列表或
字符扫描来推断“脸、皮肤、光线是否真的保留”。

### 4.5 Completeness for short canonical Prompts

短不等于完整。canonical finalizer 继续使用现有的
`final_prompt_semantic_preflight`、`user_direction_integrity` 和 Human Realism
语义契约作为权威，但必须把最终 Prompt 的状态明确签为：

```text
prompt_status: complete
semantic_coverage: complete
```

这两个字段是 Brain 的语义结论，不是本地关键词匹配结果。对复杂的人物/场景请求，
304 字符可以是合法文本长度，但不能在缺少上述完整语义签字时被认为是可执行的最终方向。
一次同上下文的 bounded finalizer recovery 可以重新生成完整方向；恢复后仍未签为
`complete`，则 fail-closed，不应把本地旧 Prompt、真人感片段或历史模板拼接回来。

## 5. Removal of conflicting historical behavior

以下旧行为不再拥有新请求的决策权：

1. `internal_budget = 6000` 作为隐藏的提前压缩阈值。
2. `provider_prompt_target_chars = 15000` 与隐藏 6000 上限并行存在。
3. `_compact_provider_prompt` 的按行优先级、前缀命中和局部裁剪用于 Brain canonical Prompt。
4. canonical Prompt 超限时由 Provider 自己选择性截断或追加本地真人感句子。
5. 用 `protected_user_direction in prompt` 的字符串包含关系判定语义无损。

旧方法如因历史记录读取仍需保留，只能成为 legacy read-only compatibility path；新建
的 real-image job 不得走它，也不能以兼容名义再次发出第二套 Prompt。

历史已签发 Job 的 Prompt 不自动重写、不迁移、不重新审查。新生成请求从本策略版本开始
使用统一决策；历史重放只能使用其冻结 Prompt，除非用户明确发起新命令。

### 4.3.1 Existing Character Card auxiliary boundary

Professional Character Card 的 Face/Body/Expression slot-delta recovery 是现有的、显式
元数据门控的专业辅助适配器。它只在已冻结的 Character Card slot、参考链、年龄/裁切和
MCP/Provider 通道都成立时处理一个单独的 slot delta；它不是普通 V3 的 finalizer，也不
参与 General、E-Commerce 或普通摄影请求的 prompt 作者选择。Doc293 不把它扩展成第二套
通用压缩机制；普通请求仍必须走上面的 Brain canonical sign-off。该适配器已有独立的
slot-delta contract 和 shared Vision/Provider gates，继续保持兼容读取，不得被普通请求
通过伪造 recovery 标记进入。

## 6. Minimal implementation scope

未来实现只允许修改下列范围：

1. `app/llm_brain/prompts.py`：canonical finalizer 的完整度和一次压缩请求说明。
2. `app/llm_brain/adapter.py` / 相关 Brain contract owner：压缩回执、既有 finalizer bounded
   recovery 的长度/完整度错误分类和失败投影；不得新增独立压缩阶段。
3. `app/generation_router/providers.py`：删除隐藏 6000 预算的 active effect；canonical Prompt 只做
   签字/长度/transport 校验，不做本地自然语言改写。
4. 新增 `tests/test_v3_doc293_unified_prompt_compression.py`，必要时只更新 Doc175、Doc290
   的冲突断言和使用新 canonical schema 的离线 Brain 夹具。
5. 本规范及对应任务记录。

明确不改：Visual Capability Cluster、Human Realism 具体内容、Review 分数/阈值、Provider
模型或路由、参考图绑定、V1/V2、前端、Sub2API、Veyra、配置秘钥和 VPS。

## 7. Verification matrix

### 7.1 Prompt policy tests

- 5999 字符：发送文本与 Brain signed text 一致，`compression_applied=false`。
- 6000 字符：仍不压缩，边界行为稳定。
- 6001 字符：只发生一次 Brain semantic compression，结果不超过 3500。
- 远超长度的中英文混合文本：按字符计数，不因 UTF-8 字节误触发第二个阈值。
- 压缩后仍超 3500、缺回执、回执绑定错误：不发送图像请求。
- 第二次重试不再次压缩、不循环调用、不重置共享 Brain 预算。

### 7.2 Semantic and authority tests

- 用户原文、尺寸/比例和硬事实在 Brain request payload 中保持完整。
- 2026-09-06 的 lean planning payload 只保留一份通用 Human Realism 权威，不恢复重复的整段 expression 文本。
- 304 字符的复杂请求缺少 `prompt_status=complete` 时被拒绝或进入同上下文 bounded recovery，不能静默发送。
- 简单请求的短 Prompt 只要 Brain 签为 complete，不因字符少被误拒。
- 本地 Provider 不追加真人感、场景、镜头或负面词；canonical path 不调用旧按行 compactor。

### 7.3 Regression matrix

至少覆盖 General、E-Commerce、Photography、无人物场景、单图、多图、参考图编辑、
历史重放和失败/恢复路径。必须确认 V1/V2、Doc269/281 来源绑定、输出数量、尺寸解析和
review/交付投影没有变化。

## 8. Acceptance and rollout gates

1. 文档先固定并由独立审计确认没有与 Doc175/Doc290 冲突。
2. 实现只改第 6 节范围；没有新增 provider、模型、配置或 Prompt 平行路径。
3. 定向测试、Brain adapter/timeout 矩阵和受影响消费者矩阵通过。
4. 只在最终代码版本固定后进行一次真实本地 Provider 验证；不以离线测试冒充成片质量验收。
5. GitHub、VPS、Sub2API 和真实生产项目不在本规范自动授权范围内，需单独批准。

## 9. Task record

```text
目标：统一 V3 最终 Renderer Prompt 压缩，修复 2026-09-06 后暴露的过度变薄。
非目标：不改模型、Provider、Review、参考绑定、V1/V2、Sub2API、VPS 和前端。
基线：main 62422dad6a36a05bb24f502afc9f94ae65a02c90；相关审计工作树 HEAD 5f3b9f52；
       工作树已有未提交改动属于外部基线，不归入本任务。
唯一写入者：主控在隔离 feature worktree 内完成实现；独立审计只读检查。
审计职责：独立只读审计本规范与实现差异，不修改被审对象。
COMPLEXITY_GATE：ESCALATE_REQUIRED；原因是 Brain/Provider 公共契约和多层历史兼容边界。
当前状态：实现已落在隔离 feature worktree，定向与相邻测试通过后再进行最终只读审计；
           当前未提交、未推送、未部署，未调用真实 Provider。
```
