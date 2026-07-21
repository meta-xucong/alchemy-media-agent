# Doc182 — V3 Character Card bounded failure, pause, and resume

状态：主线实现规范（2026-07-21）

## 目标

人物角色卡的每个缺失视角或槽位都使用共享 V3 生成、审查、有限重试和最终选择流程。一次候选失败时，系统继续尝试；同一视角/槽位最多消耗 3 个候选机会。3 次都没有形成可接受结果时，流程进入可解释的暂停状态，不再自动重复请求。

暂停不是失败数据丢失。系统必须保留已经通过审查的视角、槽位、追加式历史和安全失败原因；用户以后明确点击“从断点继续”时，创建新的追加式运行，只从第一个未完成的视角/槽位开始，不能重跑已经完成的部分。

## 适用范围与边界

- 这是共享人物角色卡运行时的故障恢复合同，不是新的 Provider、Brain、Vision、Retry、Selector 或 Storage。
- 具体创意方向仍由 Remote Brain 产生，最终像素仍由共享 Provider 和共享 Vision review 负责。
- 本机制不把上游策略拒绝伪装成可无限重试；每次尝试仍受既有 Provider、网关和内容策略边界约束。
- General、E-Commerce、Photography 只复用共享生命周期语义，不获得角色卡私有规则。

## 运行语义

### 1. 单视角/槽位的有界尝试

每个 Face Identity 视角、Expression Set 槽位和 Body Silhouette 槽位都有独立的 3 次候选预算。一次尝试可以是：

```text
共享 Brain 方向
→ 共享 Provider materialization
→ 共享 Vision review
→ 通过则成为候选，失败则记录安全 failure event
```

Provider 没有形成像素、共享审查没有通过、或共享运行时返回可归因的候选失败，都只能消耗当前视角/槽位的一个机会。成功的槽位不会因为后续槽位失败而被删除。

### 2. 暂停与可恢复检查点

当前槽位的 3 次机会用尽后：

- 模块状态为 `blocked`；有已完成兄弟槽位时保留它们，模块可表现为 `partial`；
- 角色卡记录 `last_failed_module`、`last_failed_slot_key`、安全 `last_failure_code`、`last_failure_attempt_count=3`；
- 对外只投射“本部分暂时未完成，可从断点继续”，不投射 prompt、Provider、内部 URL、job/hash 或原始错误；
- 失败运行和已通过历史均追加保存，不覆盖旧版本；
- 不自动进入下一个模块，不把部分结果标为可启用。

### 3. 手动继续

用户明确点击“从断点继续”后：

- 请求带 `resume=true`；
- Face Identity 从最近一个绑定一致、状态为 `failed` 的 pack 读取已通过的连续视角；Expression/Body 从角色卡中读取已选 winner 槽位；
- 创建新的 pack/card revision，旧运行保持只读历史；
- 只生成第一个未完成视角/槽位及其后续依赖；已通过部分不重新生成；
- 新一轮仍然最多 3 次，耗尽后再次暂停并更新检查点；成功后继续原有 review → explicit activation 流程。

## 前端要求

角色卡固定槽位始终可见。失败位置显示“暂未完成”，模块显示“从断点继续”。点击后按钮进入处理中，刷新页面从服务端状态恢复；成功的图片和历史不消失。用户无需理解候选、重试或 Provider，只看到当前阶段、已完成位置和下一步。

## 验收矩阵

- Provider/共享审查连续 3 次失败：稳定返回 blocked，保存 3 个失败事件，不抛出未处理异常。
- 前一槽位成功、后一槽位耗尽：前一槽位保留；手动继续只请求后一槽位及之后尚未完成的槽位。
- Face pack 在 supplementary 视角暂停：继续时不重做 front/three-quarter，产生新的 pack version。
- resume 绑定不一致、无 failed checkpoint、非布尔 resume：阻断。
- 普通 public projection 仅含状态、固定槽位、媒体投射 URL 和安全恢复信息。
- 共享 receipt 证明 review/retry owner；不新增专用路径。

## 明确不做

- 不把失败变成无限后台重试。
- 不用静态关键词、正则或本地 prompt 修补来“解决”失败。
- 不因失败而静默降级 Standard/General，不把半成品当成 active 角色卡。
- 不为 Character Card 复制一套 Provider、review、retry、存储或候选选择器。
