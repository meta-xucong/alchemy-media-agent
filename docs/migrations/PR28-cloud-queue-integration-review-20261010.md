# PR #28 云端队列保护集成与迁移复审交接

日期：2026-10-10。修复基线：`b72c75f843b27235a3c5828e0281749d728dfca5`。
复用来源：PR #27 `af505d089ee5b7bd8e2da7067aa87675e4785197` 的 V2 队列保护。

## 1. 结论和范围

本轮关闭已复现的 V2 旧 claim 回写终态缺陷，并修正迁移方案中的来源清单和对账缺口。
候选适合提交独立代码复审；PR 保持 Draft，不据此批准生产切换。
只集成 PR #27 的 V2 queue/capacity/provider 依赖闭环，并针对 PR #28 的持久化仓库适配。
这不是合并整个 PR #27：V1/Lab 的相关容量保护、其他 V2 上传/历史限额不在此次集成中。
原 PR #28 的 V1 产品代码、V2 SQLite 映射、历史读取、收藏和缓存留存实现未被旧分支覆盖。

## 2. 修正模型与实际变更

1. 旧实现只按 `task_id` 完成/失败/重试，允许 A 过期、B 接管完成后由 A 的晚到重试把终态改回 queued。当前领取具备唯一 token、worker identity 和 generation；所有任务状态提交校验当前领取及 running 状态。领取心跳、进程唯一标识、成功 checkpoint、过期任务清理、并发 schema 初始化、WAL 有界重试一并复用已有保护。
2. 生成名额在同一台机器的共享 queue SQLite 上协调，限制 direct/worker 并发及待排队数量。数据库操作使用有界异步卸载；最后一次有效尝试仍获得队列优先权。Provider HTTP 请求前再次检查 claim，SDK 包装的 stale-claim 错误仍向外传播。不能把这些检查解释为撤回已经发出的请求。
3. 直接照搬旧内存仓库的 `.get/.pop` 会带来持久化竞态。仅对无 outputs 的 running ImageJob 的清理改为 `BEGIN IMMEDIATE` 内的条件删除，保护并发完成结果。
4. 集成中再次发现“先持久化 planning run，再排队，拒绝后补偿删除”存在取消/清理忙锁孤儿风险。最终采用纯 `build_queued_run`，API 只持久化权威 queue snapshot，不先写另一份 repository planning row。原 `queue_run` 保留兼容保存语义；worker 首先从 queue snapshot 恢复 trace/created_at。拒绝和忙锁均不会产生额外 repository orphan；取消后已经提交的队列请求仍可能继续执行，不能把 HTTP 断开等同于撤销任务。
5. 最后一轮独立复审发现 WAL 初始化抛出的自定义 `QueueStorageBusy` 未经通用 SQLite 错误转换。已补显式 503 / Retry-After 映射和回归。
6. 迁移计划补齐 task worker 的八个可写 namespace、V1 `retention_settings.json`、完整规范化 payload 和派生索引对账、启动写入隔离、WAL 一致备份与恢复验证。新增测试用合成数据证明单靠数量/ID/owner 摘要和按 ID 读回不足以验收迁移。

## 3. 冻结证据与本地云端验证

- 21 个变更/新增 Python 文件摘要：`126459bea33fe506c1b4e7049acc405d27c23bf90fc656a43bcabdf9ab5eb4df`。算法：相对基线变更和新增的 `.py`，按 UTF-8 路径排序，串联 `path NUL SHA256(raw bytes) 的小写十六进制 NUL` 后取 SHA-256；不含生成的 egg-info、文档和工作流。
- 迁移来源矩阵：保留历史 38 文件摘要；新候选扩展为 50 来源，摘要 `e3479260b46079e8c0d91449ce9380dbe131830b0ad504cbc1387307f626a11c`。候选 overlay 及完整算法见相邻迁移方案，测试直接核对当前文件 Git blob 值，不依赖浅克隆缺失的历史对象。
- V2 **完整测试目录：453 passed，0 failed，0 skipped**（49.81 秒）。包括真实临时 SQLite/进程并发、模拟 Provider、API、持久化及留存；不等于真实 Provider 验收。
- V1/Lab/迁移定向组合：**79 passed，0 failed，0 skipped**（6.86 秒）。其中新增迁移与源保真检查 11 项；不要与之前的重叠测试相加。
- V1 **完整 `tests/test_api_smoke.py`：97 passed，0 failed，0 skipped**（231.02 秒）。这不是整个 V1 仓库测试目录。
- 21 个 Python 文件语法解析、工作流 YAML 解析及 `git diff --check` 通过。现有 FastAPI/AnyIO 弃用警告仍存在。
- 独立只读复审确认相同 `126459be…` 指纹，没有发现本轮范围内的剩余阻断；最终五组队列专项 81 项通过，并将并发 WAL/旧库初始化、末次尝试/过期领取优先级等 7 项连续运行 10 轮，70 次全部通过。这些与完整 V2 结果重叠，不累计计数。
- 新增只读权限的 GitHub 回归工作流：V1 与 V2 分开环境；V1 安装自己的依赖，V2 从其 pyproject 读取声明依赖并在源目录运行，避免混用两个 `app` 包。未引用 VPS secrets，不部署，不上传先前未授权的审计 artifacts。
- 此文件写入时尚未形成新远端 SHA 的 CI 结果。最终提交身份和该 SHA 的 CI 结果应以 PR 更新及 Actions 为准，不能用本地测试冒充 GitHub 检查。

## 4. 本地独立复审建议

先获取 PR #28 最新提交，在新隔离 worktree 核实其 SHA；不要覆盖旧工作区或把本轮子集等同于合并 PR #27。

重点检查：

- A 过期 / B 接管 / B 完成后，A 与 B 的晚到 complete、fail、retry、snapshot、release 均不能改写终态。
- direct 与 worker 使用相同 DB 路径和限制；有效末次尝试、延迟重试、并发初始化与取消仍保持预期语义。
- API admission 不写 repository planning row；排队后的读取、worker trace/created_at、legacy queue_run 和异常 HTTP 映射兼容。
- 条件删除不会删除已完成或已有 outputs 的 ImageJob；Provider 网络请求和成功 checkpoint 的 claim 校验完整。
- 新候选 50 来源 blob 与 checkout 一致；payload/索引/用户配置/多进程清单缺口已经覆盖。

复跑：在 V2 源目录执行 `python -m pytest -q`；V1 使用其独立依赖环境，按 `.github/workflows/capacity-retention-regressions.yml` 中的定向列表及完整 smoke 文件执行。

## 5. 仍然不能批准生产迁移

当前旧进程的完整 RAM exporter 与一致快照屏障尚未实现和实机验证。不得为安装 exporter 先重启旧进程，也不得把 API 投影视为完整备份。旧进程的代码身份、全量导出/导入、跨进程冲突规则、真实数据演练和 VPS 资源验收仍待完成。

新增 token 列不是旧二进制写入栅栏：旧 worker 仍可能执行无 token 条件的 SQL。必须先解决 RAM 保存阻断，再停止所有旧 API inline/standalone/其他 queue writer，核对替代者版本后切换；不支持新旧协议混跑。已在途的 Provider 请求、计费和跨数据库/文件写入仍需独立核对，不能以本次回归承诺 exactly-once 外部副作用。

未合并、部署、访问 VPS、操作生产数据或调用真实 Provider。本轮不构成整仓零漏洞或整机内存/性能已验收的声明。
