# Doc184 — V3 主线权威与旁支隔离登记

**状态：主线导航与集成边界生效**
**登记日期：2026-07-21**
**审计快照：`origin/main@3a9775ed7e435ea542623b8ebaeaf735c9da8fe8`**
**当前主线判断：始终以最新 `origin/main` 为准**

## 1. 这份文档解决什么问题

V3 在持续迭代中同时存在功能分支、审计分支、真实验收分支、旧归档工作树和不同阶段的临时主线分支。它们的提交历史、文档编号和验收状态不能混为一谈。

从本版本起，以下规则是主线导航的唯一依据：

1. 只有 `D:\AI\w\main-codex-reference-parity-integration` 的 `main` 工作树承担 V3 主线集成。
2. `origin/main` 的最新提交是当前实现真相；旧 archive 工作树、旧测试工作树和功能分支不能代表主线状态。
3. 旁支提交即使名称相同、测试通过或曾经被交接，也不能再次合并，除非它以最新 `origin/main` 为基线重新审计并提交新的集成请求。
4. 本文只登记分支关系和责任边界，不把真实 Provider/Vision 结果伪装成代码完成，也不打开任何生产门禁。

## 2. 当前主线已经包含的能力

`main@3a9775e` 的第一父链已经连续包含以下主线能力：

```text
基础 V3 共享质量与 Brain/Provider/Review/Retry
  → 标准版 / 专业版工作区分离
  → Visual Asset Library-first 与项目资产绑定
  → People Asset / Face Identity / Character Card
  → 中文 UTF-8 意图与 canonical prompt 保真
  → 共享串行非人脸视角检查
  → Character Card 有界失败、暂停、从断点继续
  → Provider / Local MCP 同一冻结计划与同一物化/交付链
```

当前主线最近的权威提交范围为：

- `cfbe506`：Professional Character Card 工作区；
- `1dadeb1`、`ebcdf34`：共享 Character Card 运行接缝和安全失败投射；
- `820e487`：有界失败、暂停和恢复；
- `d6c480a`：Provider 与 MCP 统一 Character Card 物化；
- `3a9775e`：保留 MCP 物化 provenance。

当前文档权威链的最近部分为：

- Doc173–177：专业模式以视觉资产库为中心、工作区导航、资产准入与项目绑定；
- Doc178：People Asset Character Card 合同；
- Doc179：原生 UTF-8 输入和 prompt 保真；
- Doc180：专业人物角色卡前端工作区；
- Doc181：共享串行非脸部视角检查；
- Doc182：角色卡分阶段失败、暂停和续作；
- Doc183：Provider/MCP 同一冻结计划、同一 canonical prompt、同一共享审查与交付链；
- 本 Doc184：主线与旁支关系登记。

## 3. 旁支分类

### 3.1 已被主线吸收：不得重复合并

以下分支 tip 已是 `origin/main` 的祖先，主线相对它已经继续前进：

| 分支 | tip | 处理结论 |
|---|---:|---|
| `codex/professional-character-card-doc178` | `a34e030` | Doc178 及其运行时收口已在主线；只读留档 |
| `codex/professional-frontend-ux-20260719` | `1584191` | 专业入口、资产生命周期 UI、目录 fail-closed 已在主线；只读留档 |
| `codex/ecommerce-ux-remediation-implementation-20260719` | `2016a3f` | E-Commerce UX 修复已进入主线后续链；不再直接合并旧 tip |
| `codex/photography-frontend-ux-remediation-20260719` | `e7a2d71` | 摄影前端共享修复已进入主线后续链；摄影专属继续工作需从最新主线重基 |

这些分支仍可用于追溯原始实现和测试证据，但不能作为“待合并任务”再次交给主线。

### 3.2 已完成代码阶段、真实验收仍独立：不得把代码通过当生产通过

| 分支 | 当前定位 | 主线处理 |
|---|---|---|
| `codex/professional-m5-three-view-acceptance` | M5 真实三视角验收证据与历史探针 | 不合并旧验收分支；按最新主线重新执行 front → three-quarter → profile |
| `codex/ecommerce-gate-*`、`codex/ecommerce-doc127-*` | E-Commerce Gate C/D 证据/文档 | 仅作受限证据；Gate C/D 未通过前不改变生产状态 |
| `codex/photography-p10-*`、`codex/photography-module` | 摄影 P10/P12 证据与专属文档 | 真实像素验收须在受控实例按当前主线复测 |

这类分支可以证明某个合同或代码阶段曾经运行，但不能证明当前主线已经完成真实像素质量门。

### 3.3 仍是旁支候选：未经最新主线审计，不得合入

以下分支不是当前主线的权威实现，应视为候选或历史试验：

- `codex/brain-prompt-reliability-20260720`；
- `codex/v3-brain-optimization-20260717`；
- `codex/codex-local-mode-spike`；
- `codex/local-mcp-specialized-frozen-relay`；
- `codex/codex-native-canonical-prompt-parity`；
- `codex/ecommerce-llm-architecture-correction`；
- `codex/photography-llm-first-mainline-contract`；
- `codex/shared-text-pixel-*`、`codex/provider-native-text-architecture-audit`；
- 其他以 `doc*`、`*-mainline-integration*`、`*-preacceptance*` 命名的旧临时分支。

它们的共同处理规则是：

1. 不直接 cherry-pick、merge 或从旧 worktree 继续开发；
2. 先确认是否仍有未被主线覆盖的真实需求；
3. 如仍有需求，在最新 `origin/main` 上新建独立 worktree 和新分支；
4. 只提交最小范围的文档、代码和测试，并明确它不能改变 Standard/General 或共享 Provider/Brain/Review/Retry 的既有契约；
5. 真实验收证据另行登记，不把旁支离线测试数字当作 Gate 通过。

### 3.4 归档与其他产品线：不进入 V3 主线

- `archive/v3-creative-os-acceptance-20260705` 及其工作树是旧归档，不是当前代码基线；
- `codex/session-setup-20260712` 是历史受控会话快照，不代表最新运行代码；
- V2 分支和 `custom_media_agent_2_0` 属于独立产品线，遵守 V2 自己的锁定与隔离规则，不与 V3 分支混合；
- `codex/shared-text-pixel-*` 的旧字体/OCR/本地叠字思路不重新启用，除非新文档明确证明仍是当前架构的一部分；Doc183 的 provider-native / shared materialization 规则优先。

## 4. 之后唯一允许的主线工作流

```text
用户新需求
  → 判断是主线缺口、专业版缺口、摄影/电商专属缺口，还是外部 Provider 证据
  → 只读取最新 origin/main
  → 在独立新 worktree 建新分支
  → 先更新当前可用的下一个文档编号
  → 红测 / 实现 / 审计 / 回归
  → 主线唯一写入者审查并合入
  → 合入后再做受控真实验收
```

今后任何交接必须同时写明：

- 基线 `origin/main` commit；
- 分支最新 commit；
- 是否已被主线吸收；
- 代码测试与真实 Provider/Vision 测试是否分开；
- 是否改变生产门禁；
- 未完成项和下一步唯一动作。

## 5. 当前主线的真实剩余项

主线代码层面的 Character Card/MCP parity 已有完整闭环，但以下事项不能因代码测试通过而自动标记完成：

1. 真实共享 Vision 对 Character Card 必要阶段的可认证结果；
2. Professional M5 的 front、three-quarter、profile 全链路真实 winner 和 anchor-pack activation；
3. E-Commerce Gate C/D 的当前主线受控实例真实证据；
4. Photography P10 的当前主线受控实例真实证据；
5. Browser 受控实例的真实端到端刷新、恢复、失败提示和最终交付投射。

这些是验收队列，不是重新修改主线架构的理由。Provider/Vision 不可用时，必须记录为外部运行阻断；不能为了“通过”而在主线增加第二套 Provider、关键词规则、私有 Review/Retry 或静态降级。

## 6. 当前工作树保护声明

主线当前工作树保留一个未跟踪目录：`.controlled-validation/`。它属于受控验收证据，不是代码改动。本次审计没有删除、覆盖或改写它。

旧 archive 工作树和所有列出的功能 worktree 均保持原状。本登记只写入主线文档，不改变任何旁支内容。
