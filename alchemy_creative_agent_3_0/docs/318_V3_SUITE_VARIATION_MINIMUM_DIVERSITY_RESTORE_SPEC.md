# V3 套图扩展模式最低差异语义回迁开发文档

## 1. 任务边界与历史基线

- 任务 ID：`v3-suite-variation-minimum-diversity-20260917`
- 所属层：V3 Foundation / General Template / Visual Capability Cluster 的套图执行语义。
- 历史基线：最早的 V3 专业版存档 `v3-creative-os-acceptance-20260705`，提交 `c75e8a37`。
- 主要历史依据：Doc58、Doc59、Doc62，以及基线中的 `human_variation.py`。
- 当前问题：当前版本的角色配方仍包含 angle、pose、wide/context，但跨 Brain 的中性执行合同在两张图的常见路径上只暴露 `scale` 或 `detail/framing`，真实结果容易退化为同一机位的裁切变化。
- 本次不改：上游 AISelf、Provider 路由、Human Realism 美感契约、质量审核阈值、专用模板交付图谱、公开 API 和持久化结构。

## 2. 历史设计中可复用的部分

早期版本并不是依靠一个“套图”关键词，而是同时建立了三层约束：

1. Doc59/Doc62 为套图分配中性的职责：hero、subject focus、side/three-quarter、wide/context。
2. Human Natural Variation 为整组图定义最低差异：至少有表情/视线差异、姿势/身体或头部角度差异、裁切/机位距离差异；禁止复制同一张定格图。
3. 批次复核以“图像职责”和“实际差异”判断套图是否塌缩，而不是只看输出数量或角色字符串。

这些规则是场景中立的视觉变量，符合 V3 Foundation 与 General Template 的边界，可以回迁。旧版静态摄影措辞、角色标签和 Provider 拼接方式不直接回迁；当前 Brain 仍是完整提示词的唯一作者。

## 3. 理论修正模型

### 3.1 权威层

根因在 General 的 `ModeAwareRoleDirector -> VariationExecutionContract -> Brain` 语义投影层：角色目录有差异，但首批输出的中性轴不足，Brain 没有得到“必须换机位/姿势”的结构化证据。

因此最小完整修复是扩大当前已有的中性语义合同，而不是在 Provider 端追加提示词或放宽审核：

```text
delivery_suite, count >= 2
  保持 subject/style/user intent
  至少一个非首图输出必须包含 viewpoint、pose、gesture、context 之一
  detail、framing、scale、layout 只能作为补充，不能单独完成套图差异
```

这是“最低差异”而不是“每张都必须大幅换场景”。用户明确要求的动作、机位、场景和参考通道仍然优先；Brain 在这些约束内选择可行变化。

### 3.2 具体回迁

- 真人 `subject_focus` 保留 detail 职责，同时补充 `head angle/body turn` 中性轴，避免第二张只能近裁切。
- Generic `detail_focus` 保留 detail 职责，同时补充 angle/pose 中性轴，覆盖未被识别为 character 的真人场景。
- Product `context_scene` 继续承担 context 职责，并补充 angle 证据，避免 context 只变道具不变视角。
- `build_variation_execution_contract()` 增加一个安全归一化：若未来角色目录再次漏掉最低差异轴，向首个非首图输出补充 `viewpoint/pose`；无容量可安全补充时返回无合同，由现有 enforced 路径阻断，而不是静默生成克隆套图。

### 3.3 模式隔离

- `selection_candidates` 仍是近邻比较，不强制远机位或大姿势变化。
- `format_layout_adaptation` 仍以画布、裁切和留白为主，不强制改人物动作。
- `creative_exploration` 继续由 concept/mood/palette 等轴驱动。
- 只有 `delivery_suite` 使用本次最低差异规则；不把套图职责泄漏到其他模式或专用模板。

## 4. 实现范围

允许改动：

- `app/shared_capabilities/visual_cluster/mode_role_director.py`
- 现有模式/变异合同回归测试
- 本开发文档

实现不新增公开字段、不改变 `v3_general_variation_execution_v1` 的序列化形状，不把内部 role key、camera rule 或 prompt pressure 发送给 Brain；只改变已有 `variation_axes` 的中性内容。

## 5. 验收标准

1. Generic、Character、Product 的 `delivery_suite` 两图合同中，至少一个非首图输出带有 `viewpoint/pose/gesture/context` 轴。
2. 真人两图不再只有 `detail/framing`；保留 identity/style/user intent 和 detail 语义。
3. 四种模式的合同仍然互相隔离；selection/format 不被套图最低差异规则污染。
4. 合同仍不包含 role key、camera distance、angle rule、prompt pressure 等本地配方字段。
5. 既有模式导演、General variation compatibility、Brain payload purity 回归通过。
6. 代码审计确认未修改 Provider、Human Realism、Review 阈值或专用模块。

## 6. 后续真实验收

本地合同测试通过后，使用此前的同一真人项目执行两图和三图真实生成：两图应至少出现 hero + alternate-view 语义，三图应继续覆盖 context 或更宽场景。像素结果仍需人工检查；合同通过不等于自动宣称视觉成片质量通过。

## 7. 审计清单

- [ ] 历史基线、当前回归和根因层级与代码一致。
- [ ] 最低差异只作用于 `delivery_suite`，且不穿透 Brain prompt ownership。
- [ ] 不新增场景特例、专业摄影交付图谱或质量阈值。
- [ ] 旧合同/历史记录读取不因新增字段或版本变更而失效。
- [ ] 测试覆盖正常、模式隔离和 Brain 纯净投影。
- [ ] 真实生成结果与合同语义一致，未退化为单纯裁切变化。
