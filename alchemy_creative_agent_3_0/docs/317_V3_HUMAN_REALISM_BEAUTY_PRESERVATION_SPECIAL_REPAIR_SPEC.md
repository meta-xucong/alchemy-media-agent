# V3 Human Realism 美感保持专题修复开发文档

## 1. 任务边界与基线

- 任务 ID：`v3-human-realism-beauty-preservation-20260916`
- 所属层：V3 Foundation / Shared Visual Capability Cluster / Human Realism。
- 依据：Doc65、Doc71、Doc76、Doc77、Doc78、Doc91、Doc92、Doc93、Doc94、Doc170，以及本次修复前的主线 `main` 基线 `534522b5`。
- 本次只处理真实感模块的语义契约、Brain 传递和兼容性重试文案；不改套图扩展模式、模式路由、质量审核阈值、审核器数量、Provider 路由、General Template 交付逻辑或 VPS。
- 当前主线基线已验证：工作区干净，`HEAD == origin/main == 534522b5ea81fb1ea787803456d541a0b1cc4dbf`。

## 2. 观察到的问题

现有 Human Realism 已有 `aesthetic_boundary`、`facial_light_priority` 和“不要让真实感降低吸引力”的自然语言，但存在三个实现层缺口：

1. `_compact_human_realism_execution_contract()` 没有把 `aesthetic_boundary` 投影到 Brain 的规划请求，导致前置创意决策只看到“真实材质”而看不到美感边界。
2. 契约没有结构化表达“美感是硬约束；与真实感冲突时先降低真实感干预”的决策顺序，Brain 只能从较宽泛的说明中自行推断。
3. 兼容性重试补丁仍包含可能被 Provider 放大的“tiny asymmetry”“clean luminous complexion”等表述：前者可能把面部不对称误当成真实感目标，后者可能在暗调、传统或用户自定义肤色场景中改变美感和风格。

这不是新增审核器的问题。现有审核与重试入口继续保留；修复点是让同一个 Foundation 真实感模块在生成前就拥有明确、可传递的美感优先决策。

## 3. 修正模型（Theory-First Correction Model）

### 3.1 权威顺序

对可见真人图像，以下顺序是不可逆的：

1. 用户明确要求的美感、风格、情绪、光线、肤色和参考图身份/面部和谐关系。
2. 真实感模块的物理呈现义务。
3. 真实感用于证明摄影材质，而不是重新设计人物。

当美感与真实感干预发生冲突时，执行固定规则：

> 保留用户/参考拥有的美感与风格，降低真实感干预的强度或范围；绝不通过变暗、变疲惫、变粗糙、变严厉、改变面部比例或破坏面部和谐来“证明真实”。

### 3.2 允许真实感作用的通道

真实感只能在不改变用户拥有的视觉方向前提下改善：

- 场景一致的光线、阴影、景深、接触和镜头响应；
- 克制的皮肤/头发/服装/物体材质纹理与非均匀反应；
- 曝光与高光滚降的物理一致性；
- 必要的肢体、手部和物体接触合理性。

### 3.3 禁止真实感干预的通道

真实感不得主动改变：

- 用户或参考拥有的面部特征和谐、身份关系、面部比例与吸引力；
- 用户或参考拥有的肤色/明暗方向、情绪、风格、色温和光线意图；
- 通过“更真实”引入疲惫、暗沉、粗糙、严厉、丑化、纪录片式不讨喜或刻意面部不对称；
- 任何通用的美容重塑、脸型重塑、去美化或泛化成另一种人物。

## 4. 冻结的实现契约

在现有 `semantic_contract` 中增加一个闭合、场景中立的 `beauty_preservation_policy`，不增加公开 API 字段，不增加审核维度。其固定语义为：

```text
contract_version: v3_human_realism_beauty_preservation_v1
priority: hard_user_or_reference_aesthetic
conflict_resolution: preserve_beauty_reduce_realism_intervention
style_authority: prompt_and_resolved_reference_channels
protected_channels: user_owned_style_mood_appearance_and_facial_harmony
realism_channels: texture_light_material_camera_depth_contact_and_physical_coherence
forbidden_interventions: facial_redesign_beauty_reduction_unrequested_dulling_or_harshness_style_override
```

约束要求：

- Human Realism 层生成该契约；不把它展开成 Provider 关键词清单。
- Brain 规划和最终签名都必须收到该契约，并将其解释成一条完整、场景一致的最终提示词。
- 兼容性重试只做最小的材质/光线/镜头修复；不再用“微小面部不对称”或固定明亮肤色作为通用真实性目标。
- 旧的 `v3_human_realism_semantic_v8` 核心版本保持不变；本次策略以独立 v1 子契约扩展，避免无必要地破坏历史记录读取和现有审核合同。

## 5. 代码修改范围

### 5.1 `human_photorealism.py`

- 定义固定的美感保持策略工厂，返回全新副本，避免共享可变列表。
- 在普通真人和手/皮肤细节两条 Human Realism guidance 路径中加入 `beauty_preservation_policy`。
- 保持 Brain-owned 路径的 prompt fragments/retry templates 为空；该策略是语义契约，不是本地提示词追加。

### 5.2 Brain 传递链

- `prompts.py` 的精简规划投影补充 `aesthetic_boundary` 和 `beauty_preservation_policy`。
- 增加一段共享、场景中立的 Brain 语义指令：美感与用户风格为硬约束，冲突时降低真实感干预；不输出契约字段或检查清单。
- canonical finalizer 使用同一段规则；现有完整提示词作者、参考通道所有权和全图语义重写职责不变。
- `ScenarioRuntime` 的最终执行契约投影和主动语义契约白名单同步增加该字段并校验闭合结构。

### 5.3 兼容性重试文案

- 将通用“恢复美感”重试改为“保护用户/参考美感，减少真实感介入”，避免默认改变肤色、光线或面部结构。
- 移除将面部 `tiny asymmetry` 作为真实性修复目标的表述。
- 保留现有审核、issue code、一次有界重试和 Brain-owned evidence-only 语义，不新增审计系统或阈值。

## 6. 回归测试与验收

新增专题测试覆盖：

1. 普通真人与 hand/skin detail guidance 都有闭合策略，且策略不含场景、年龄、地区、模板或面部部件配方。
2. Brain 精简规划请求实际收到 `aesthetic_boundary` 与策略；Brain-owned guidance 仍没有本地 prompt fragments/retry prose。
3. finalizer 的完整语义契约收到策略，且 Brain 指令明确包含“冲突时降低真实感干预”。
4. 兼容性重试不再包含 `tiny asymmetry`、固定 `luminous complexion` 等有风格漂移风险的默认修复；仍保留用户/参考方向保护。
5. 现有 Human Realism、Brain、ScenarioRuntime、视觉审查相关回归测试全部通过。

验收判定：

- 文档、代码、测试、独立审计均完成，才算本地专题修复完成。
- 本阶段不做远端真实生图；按照 Code-First 原则，先以契约传递和确定性回归证明修复正确。VPS/Provider 验收属于后续发布阶段，不在本次授权范围内。

### 当前本地验证证据（实现候选版本）

- 专题测试：`test_v3_doc317_human_realism_beauty_preservation.py`，7 passed。
- Human Realism、Brain、ScenarioRuntime、表达/肤色/年龄/材质边界回归：92 passed。
- 共享 Human Realism 治理与通用视觉治理回归：9 passed、12 passed。
- 人像交付回归：28 passed。
- `compileall`：通过。
- `doc290` Brain 超时历史回归：63 passed、2 failed；失败只涉及既有超时测试对 `read timeout` 的旧期望（实际 61 秒，期望 270/160 秒），本次改动未触及该实现，暂不纳入本专题阻断项。

## 7. 审计清单

独立审计 Agent 只读检查固定版本，逐项给出“符合/不符合/证据不足”：

- [ ] 范围是否只触及 Human Realism Foundation 与其 Brain 投影；
- [ ] 美感硬约束与冲突降级规则是否由代码生成并完整传递；
- [ ] 是否没有把策略展开成新增 Provider 关键词清单；
- [ ] 是否没有新增审核器、审核阈值、模式逻辑或远端副作用；
- [ ] 是否保留参考通道所有权、Brain-only prompt ownership 与历史合同兼容；
- [ ] 专题测试及相关回归测试是否通过；
- [ ] 是否存在未覆盖的跨层缺陷。
