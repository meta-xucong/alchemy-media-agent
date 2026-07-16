# Doc156 — Doc155 约 6 岁人物表达与年龄适配对比记录

状态：代码回归通过；视觉样本为 Codex conversation-only、不可认证交付

## 1. 本轮范围

本轮在 Doc155 与 `f3e378f` 之后，复用此前约 10 岁蓝裙人物的四类棚拍条件和一类花园条件，将人物意图改为约 6 岁。服装事实、画面类别、参考来源和输出尺寸保持不变。

共享 Human Realism v6 的验收重点是：

- 约 6 岁与约 10 岁使用同一套共享语义合同；
- 年龄由用户意图/参考事实决定，不由本地年龄配方决定；
- 普通温和/愉快意图不自动展开成固定露齿商业笑；
- 最终完整 prompt 仍由 remote_v3_llm_brain 负责；
- MCP 不创建项目、候选、review、retry 或认证交付。

## 2. MCP/Brain 证据

单图白底与蓝灰布景规划均通过 canonical relay，并记录了：

- `creative_direction_owner=remote_v3_llm_brain`；
- `canonical_prompt_signing.stages` 包含 `provider_prompt_finalize` 与
  `provider_prompt_human_naturalness_resign`；
- `human_realism_natural_presence_resigned=true`；
- 人物方向分别保留了“warm but unforced / gentle and absorbed”的情境化表达；
- canonical prompt SHA-256 分别为：
  `324695df6e40a4a845063f312adbfd054097607b749bd2e5b4c50a994555a676`、
  `37d2675e3cc891e7180f5e55f60069b2de1aa1c7de6c3ce3e90580fb6c26e3d6`。

一次五输出批量规划虽然保持了精确五条 whole-image direction，但 provenance 只有
`provider_prompt_finalize`，没有 Human Realism re-sign。该批量结果不计入本轮验收，
也不应被误当作已通过的人物质量证据；它证明批量请求必须继续以“每个输出完成共享
Human Realism signoff”为前置条件。

部分后续单图规划因远端 Brain 超时而 blocked；没有用本地规则或手写 prompt 冒充成功。

## 3. 视觉补测样本

下列图片是基于 MCP 产生的完整方向或其安全等价表述，经 Codex 内置 ImageGen
生成的 conversation-only 样本。它们没有经过 V3 Web Provider 的共享 review/retry，
不能进入 Gate C/D 或生产统计：

- 白底棚拍：`exec-05bfc201-ea72-4668-a1c4-652fd4c0dd84.png`；
- 蓝灰布景：`exec-761c7d56-05e1-4d25-80c2-22269125a896.png`；
- 气球棚拍：`exec-013ce604-093e-4f8d-aacd-bc4ec628d0e1.png`；
- 灰底目录：`exec-5313de4b-a26d-415d-bb29-f348243b3bdd.png`；
- 花园：`exec-904e2e9c-2b7e-4551-b33c-606481eebf68.png`。

原始图片仍保留在本地 Codex generated-images 目录，不进入 Git。

## 4. 对比结论

### 年龄适配

约 6 岁方向在脸型、眼睛比例、身材长度和整体幼态上比此前约 10 岁样本更年轻，
说明 `identity_age_fidelity=explicit_or_reference_backed` 能进入 Brain prompt。可是
由于当前服装参考图本身包含一名较大的儿童，参考图对身高和面部成熟度仍有牵引，
部分样本视觉上更接近 7–9 岁，而不是严格的 6 岁。这个差异不能归咎于 Human
Realism 的年龄分支；它是“人物出现在服装参考中”带来的参考通道混杂，需要后续用
纯服装参考或更清晰的 product-only 证据复验。

### 商业假笑

- 花园样本的低头关注花朵、蓝灰布景的侧向注意力，明显没有统一的正面露齿主持人笑；
- 灰底目录样本是轻微、个体化的微笑，不是整齐露出六颗牙；
- 白底正面和气球场景仍容易被 ImageGen 推回商业化露齿笑，说明静态正面商品构图
  仍有强先验，Human Realism v6 已降低概率但尚未彻底消除；
- 因此本轮不能声称“所有场景均消除 AI 商业假笑”，只能确认语义分辨率在有注意力
  和动作的场景中有效，并且同一合同对不同年龄可用。

### 皮肤与真人材质

本轮样本的皮肤不再呈现明显油画式厚涂，光线、衣物和环境融合正常；但棚拍成片
仍有商业级柔化倾向。由于 MCP 没有共享视觉审查与有界重试，本轮不对像素材质
作生产级认证。

## 5. 最终状态

代码层：Doc155 实现、Human Realism v6 合同、Brain payload、共享 reviewer 合同和
年龄适配回归均已通过；V3 全量回归为 `868 passed`，仅有 2 个既有 FastAPI 弃用警告。

视觉层：约 6 岁样本已完成跨棚拍/花园的受控对比，但为 conversation-only，且存在
内容安全拒绝、Brain 超时和参考图年龄混杂证据。因此本轮结论是：

```text
共享代码与语义合同：通过
不同年龄的通用适配：基本通过，仍需纯服装参考复验
商业假笑抑制：明显改善但未完全解决
生产级视觉 Gate：未通过，也未宣称通过
```
