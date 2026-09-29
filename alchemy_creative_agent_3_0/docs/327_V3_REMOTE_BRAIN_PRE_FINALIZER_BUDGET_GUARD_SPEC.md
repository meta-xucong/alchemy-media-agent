# Doc327 — V3 Remote Brain 前置阶段预算保护与失败语义

状态：实现与专项回归已完成，待集成验收

## 1. 问题与边界

V3 的真实图片链路必须先完成 Remote Brain 语义方案和正式 Provider Prompt 签名，之后才允许调用图片 Provider。共享 Brain 预算属于同一份逻辑预算，不能因为前置阶段或恢复阶段耗尽，导致最终签名只剩一个不可用的残余窗口。

本修复不改变以下边界：

- Brain 失败时不构造本地 Prompt，不绕过签名；
- 签名未完成时不调用图片 Provider；
- 不增加自动重复生图；
- 不修改非流式 V3 主链路为流式；
- 不调整 Vision 审核门槛。

## 2. 修正模型

旧逻辑只在 Brain 阶段名称严格等于 `plan` 或 `generate` 时预留最终签名窗口。项目规划、续作和其他入口可以使用描述性阶段名，因此同一条真实生图链路可能绕过预留，前置 Brain 调用消耗全部逻辑预算，最终签名阶段才收到几十秒的残余超时。

新规则是：

```text
真实图片 Brain 前置阶段
    └─ 保留 BRAIN_EXECUTION_BUDGET_HANDOFF_SECONDS
       给 provider_prompt_* 正式签名阶段

provider_prompt_* 正式签名阶段
    └─ 使用已保留的剩余预算，不再次扣除签名预留
```

阶段名称不是入口契约；`provider_prompt_` 前缀是最终签名阶段的保留命名空间，其余真实图片 Brain 阶段均按前置阶段处理。

## 3. 失败投影

共享预算耗尽属于 Brain 时间边界失败，不属于图片 Provider 不可用，也不属于图片质量失败。公开生命周期保持 `blocked`、`provider_request_started=false`，并保留安全的 `remote_error_class=execution_budget_exhausted`；Product API 的 `failure_category` 归入 `brain_timeout`，避免将陈旧或矛盾的可用性字段投影成错误的 Provider 故障。

## 4. 验收证据

- `test_v3_llm_brain_provider_timeout.py` 覆盖 `plan`、`generate` 以及 `doc277_project_planning` 描述性前置阶段；
- `test_v3_doc321_brain_failure.py` 覆盖共享预算耗尽的公开失败分类；
- 最终签名阶段仍保持“不额外预留”的既有契约；
- 失败路径继续证明图片 Provider 请求未启动。
