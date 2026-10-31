# V2 Bridge 终态失败队列状态修正范围

日期：2026-11-01

## 目标与观察到的偏差

Render Bridge 返回终态 `failed` 时，V2 `generation.py` 将图片 job 和
CreativeRun 标记为失败；`bridge_terminal` 不可重试，也不会创建替代 task。
但 `queue_worker` 随后无条件调用 `task_queue.complete_task`，使同一 V2
queue row 持久化为 `completed`。前端/队列投影因此会把失败 run 表示成成功完成。

## 权威状态与修正模型

- Bridge 的 task/attempt 终态是这次本地执行结果的依据。
- V2 CreativeRun 和 image job 的 `failed` 状态保留失败详情与现有错误信息。
- 当 Bridge 已给出终态失败时，V2 queue row 也必须以同一失败 run 快照终态为
  `failed`，释放原 claim；不重试、不创建新 task、不回退到 API/Sub2API。
- 非 Bridge 的普通成功、可重试等待及既有 reconciliation deadline 路径保持原有行为。

## 最小实现

在 V2 queue worker 中识别 `run.status == failed` 且至少一个 job 的 provider 为
`render_bridge`、error code 为 `bridge_terminal`、retryable 为 false 的情况，
调用已有 `task_queue.fail_task(..., run, force_terminal=True)` 保存该失败快照。
不要把所有 provider 的失败统一改写成新的队列规则。

## 回归验收

使用确定性 fake Bridge client 返回终态 `failed`，验证：

1. queue row 最终为 `failed`，`result_json` 保留失败 CreativeRun/image job；
2. claim 被释放，任务无 not-before/retry；
3. Bridge task/query 次数没有因队列重试增加，也没有创建新 task；
4. `bridge_wait` 仍沿原同 task 有界轮询路径；其他 provider 的完成/重试行为不变。

测试不得调用真实生图 provider；真实 V2 生图只作为所有代码门禁通过后的单次验收。
