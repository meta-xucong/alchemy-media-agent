# V1、V2 与 Alchemy Lab 资源容量护栏修复（非完整内存治理）

日期：2026-10-08

基线：`3915b24d0cdab6cc626ad5a7d07c0839e5239064` (`origin/main`)
范围：仅 V1、Custom Media Agent 2.0 (V2) 与 Alchemy Lab 的内存、队列、历史读取、上传和生图并发风险；不扩展 V3 方案。

## 目标与阶段

总目标是让 V1、V2 和 Alchemy Lab 在资源压力下有界、可恢复、用户可理解，同时保持 API 与正常工作流兼容。当前阶段先修复能在不删除权威业务数据、不改变生图语义的前提下完成的容量护栏，并用离线、fake-provider 回归证明跨进程及失败路径；VPS 资源表现仍需独立验收。

## 核实方法与证据边界

本文把可从当前源码直接证明的资源行为称为“代码风险”。它不证明线上已发生 OOM、请求堆积、数据丢失或性能故障。基线检查确认唯一主线 checkout 为 `main`，当前远端提交与上述 commit 相同；原工作区的未提交文件不属于本分支且未修改。

### 已证实代码风险

| 区域 | 源码证据 | 影响与边界 |
|---|---|---|
| V1 MemoryRepository | `src_skeleton/app/repositories/memory.py` 中 `sessions`、`assets`、`jobs`、`outputs`、`idempotency_index`、`events_by_session` 均为进程内字典/列表；只有显式 `reset()` 删除。 | 进程寿命内持续增长；重启后元数据本来就不可恢复。没有安全 TTL/LRU 淘汰依据。 |
| V1 生图提交 | `src_skeleton/app/main.py` 的 V1 生图/修图端点把工作交给 FastAPI `BackgroundTasks`；未见跨 worker 的统一准入。 | 每个 API worker 都可接收任务，进程内并发参数不能代表全局上限。 |
| V1 历史 | 基线 `/v1/image/history` 汇总仓库、JSONL 和输出目录，排序后分页；`LocalMediaStore.list_history_records` 用 `read_text().splitlines()`，且全量去重/排序。 | 单次请求的原始文件字符串、行列表、记录映射和排序列表都随历史量增长。 |
| V1 上传 | `/v1/assets/{asset_id}/content` 在读取完整 body 后才调用服务层；服务层已配置 12 MiB 内容限值，但限制发生在完整读取之后。 | 超大请求仍先占用请求体内存。JSON base64 与二进制传输需分别按 wire bytes 与解码内容校验。 |
| V2 MemoryRepository | `custom_media_agent_2_0/app/repositories/memory.py` 中 runs/jobs/outputs/uploads/feedback/safety decisions 等均仅存内存。 | 一部分输出/历史有本地存储，但该仓库对象本身不是可靠持久权威源；不得直接淘汰或声称重启可恢复。 |
| V2 历史 | 基线 `services/image_history.py` 对整个 JSONL 使用 `read_text().splitlines()`，去重、全量排序后切片；async 路由中的列表、权限回退、缩略图/预览、下载、参考图创建和删除都会在 repo miss 时扫描历史。 | 历史增长会增加峰值内存并阻塞事件循环；删除 JSONL 原记录还会形成全量 retained-lines 列表。 |
| V2 队列/入口 | `services/task_queue.py` 用 SQLite 持久化并由独立 worker claim；队列表无 pending 上限。`POST /api/v2/image/jobs` 调用 provider 路径；同步 creative run 和 revision 也可绕开 durable queue。 | 队列积压未设上限；worker 的串行 claim 不约束直接 API 路径，也不跨多个服务进程形成统一 provider 并发上限。 |
| V2 Claude cache | `claude_orchestrator.py` 将决策及匹配元数据保存为 JSON cache 文件；每次加载/语义匹配都会读入完整 cache。 | cache 与决策记录同文件，缺少有界索引；但自动删除决策记录会改变重放/语义命中行为，不属于可擅自做的缓存淘汰。 |
| Alchemy Lab | `services/alchemy_lab.py` 的 `AlchemyLabStore.sessions` 是未淘汰全局字典；会话启动用 `asyncio.create_task`。`MAX_CONCURRENT_GENERATIONS=1` 出现在对外 limits 展示中，但当前代码没有用它跨 session/进程准入。 | session 记录增长；独立后台任务可同时启动，限制值不构成服务端保护。 |

### 尚未证实

- 当前没有线上 heap/队列/请求延迟测量，不能由静态代码推断真实 OOM 或用户可见故障。
- 本地模拟不代表 2 核 2 GiB VPS 的吞吐、provider 延迟或磁盘压力验收。

## 修正模型

1. **业务记录与缓存分层**：V1/V2 内存仓库、Lab session、历史 JSONL、队列终态、幂等证据和 Claude 决策没有完全覆盖的权威重载路径；本次不做 TTL/LRU 删除。先对并发、待处理工作和单次请求读取内存设硬边界；持久数据保留/归档周期另行决策。
2. **并发权威**：受控生图入口共用本机 SQLite 持久化准入状态；V2 API 直达入口在同一事务中检查 durable queue，并让位于 queued/running 任务。超过 claim 超时且已耗尽尝试次数的 running task 在准入或 worker claim 事务中转为 failed，保留错误证据和任务行，以免永久占据队列优先级。进程内 semaphore 不是跨进程保证。活跃调用由 heartbeat lease 表示；普通异常在本地调用结束后释放，调用者取消时 shield 正在执行的 provider coroutine，并等待它结束后再释放。进程崩溃后只能在 lease TTL 到期后恢复本机准入，不能推断远端 provider 已停止。
3. **积压权威**：V2 pending queue 上限由 SQLite 事务内的 active-row 检查与插入共同保证；过载返回明确可重试状态，不创建无界后台线程或替代队列。终态任务保留，直到用户批准明确保留策略。
4. **历史读取**：读取/查询 JSONL 逐行处理，避免常规读取使用 `read_text().splitlines()` 的完整副本；V1/V2 采用 top-K 选择减少全量排序状态。V1/V2 async 历史端点、V1 repo-miss 权限/收藏回退，以及 V2 权限回退、缩略图/预览、下载、参考图创建和删除的同步工作统一走线程池准入。删除 API 在取得准入前不执行任何输出/文件/收藏 mutation。每进程用可配置的非等待准入限制同时运行的扫描数，满载时返回带 `Retry-After`、`retryable=true` 的 429。为保持去重和准确 total，目前仍保留与唯一记录数成比例的 map；V1 聚合层也仍保留完整源记录。删除一条历史记录仍需完整读取并重写源 JSONL，虽已在线程池内执行并受同一并发上限约束，暂时仍是 O(N) 内存；严格有界删除还需可恢复的索引/改写协议，不能冒险丢掉并发追加的历史。严格有界的去重/total 需要可重建持久索引，本次不以截断破坏 API。
5. **上传**：先检查声明长度，再以 `max+1` 分块读取拒绝超限 body；对 JSON base64 同时限制 wire 大小和解码后内容大小；拒绝时不写文件、不推进 asset 状态。
6. **Lab 会话**：跨 session 的服务端并发值复用 V1 本机 SQLite lease；session 完成或实际本地生成协程结束后释放；调用者取消会等待协程结束，不删除终态 session。

## 本次实现与保证范围

| 范围 | 实施 | 保证边界 |
|---|---|---|
| V1 生图 | 新增 `MAX_CONCURRENT_IMAGE_GENERATIONS`（默认 1，范围 1–32）与 `GENERATION_CAPACITY_LEASE_TTL_SECONDS`。API BackgroundTasks 在创建 job 前取得容量 lease，并将 lease 转交给后台调用；直接 service 调用和 Lab 图像生成使用相同数据库。 | 同一台主机、共享同一 media root 的进程可协调本地调用准入；其他主机/容器卷不共享时不成立。容量已满时 API 返回可重试 429，不新建 job；已接收 job 若后续出现容量异常，标记 `generation_capacity`、`retryable=true`。相同幂等键且请求指纹一致时重试复用原 job，请求不同则不替换原请求。 |
| V2 生图与队列 | 新增 `V2_MAX_CONCURRENT_IMAGE_GENERATIONS`（默认 1，范围 1–32），lease 表与 `task_queue_db_path` 共用；同步 creative/image/revision 路径纳入 lease。新增 `V2_TASK_QUEUE_MAX_PENDING`（默认 100），事务内限制 queued 行；running 行不计 pending。direct API 检查同一 DB 中的 queued/running 并让位，worker 使用同一 lease。队列满返回可重试 429；无容量返回可重试 429。 | 多 API/worker 进程必须挂载同一 SQLite 文件。终态队列行保留。容量满响应不会创建新 provider 工作。queue worker 的容量等待复用原 task/run，capacity retry 不消耗 attempts。 |
| 取消与超时 | API caller 取消时 shield 本地 provider coroutine，等待该 coroutine结束后释放 lease；心跳临时 SQLite 异常会继续重试；进程崩溃则由 lease TTL 隔离后再回收。 | HTTP/provider client timeout 只表明本机客户端停止等待，不证明远端生成终止。lease 到期也只恢复本机准入，不对远端仍运行请求作并发承诺。VPS 需要 provider/gateway 的任务状态证据或容量余量策略另行验收。 |
| 上传 | V1/V2 上传 route 按流读取，拒绝超出 wire/body 限值的请求；在解码/存储前返回 413。 | 反向代理仍应配置请求体上限，避免 body 到达应用前已被缓冲。 |
| 历史 | V1/V2 JSONL 常规读取逐行处理；V1 output scan 与 V2/V1 排序使用 bounded top-K；V1/V2 async 历史端点、repo-miss 权限/收藏回退及删除路径，V2 缩略图/预览、下载和参考图创建都通过进程内有界准入移交线程池。默认 `HISTORY_SCAN_MAX_CONCURRENT=2`、`V2_HISTORY_SCAN_MAX_CONCURRENT=2`；满载返回 `429 history_scan_capacity_full`、`retryable=true` 和 `Retry-After: 2`。取消请求会等待线程任务结束后才归还准入。 | 此准入是每进程；多 worker 的总扫描上限等于每进程配置值乘 worker 数。精确去重/total 仍是 O(unique records)；V1 统一 history endpoint 仍持有全量聚合记录；V1/V2 历史删除仍 O(N) 读写。MemoryRepository、Claude decision cache、Lab terminal sessions、queue terminal rows 都未删除或改为有界持久加载。 |
| V2 终态恢复 | direct admission 与 `claim_next_task` 在共享 SQLite 事务内将超过 claim 超时且达到 `max_attempts` 的陈旧 running 行改为 failed，写入 `worker_recovery_exhausted`、`retryable=false`，清除锁字段但保留 task/run 快照和历史行。 | 扫描只处理明确陈旧且已耗尽尝试的任务；尚在超时窗口或仍可重试任务保持原有恢复语义。 |

默认配置的 1 个 slot 是保守本地调用上限，不是 VPS 性能结论。`GENERATION_CAPACITY_LEASE_TTL_SECONDS` / `V2_GENERATION_CAPACITY_LEASE_TTL_SECONDS` 最低 960 秒，并自动高于已配置的相关 provider client timeout 加 60 秒；heartbeat 会在本地调用仍活跃且可及时访问 SQLite 时续租。若一个活进程的 heartbeat 持续无法写入并超过 lease TTL，另一进程可能在旧调用尚未结束时取得 lease；这属于共享 SQLite 租约无法 fencing 远端调用的故障边界，本地测试不证明此时仍是严格的全局并发上限。若 provider client 自身报告 timeout，调用已经在本机返回/结束，lease 可释放，但远端是否仍计算无法由本代码确认。V2 direct API 让位于 queue 只约束共享 DB 的同主机进程。

## 配置与兼容

- 新增配置必须有保守默认值、范围校验、文档与测试；拒绝响应须带稳定错误码、`retryable=true`，并提供可用的 `Retry-After`。
- 历史扫描配置仅控制每个 API 进程的并发扫描上限；设置更高值会线性增加多 worker 部署的总并发扫描数和历史解析峰值内存。
- API 成功响应 schema 与正常请求流程保持不变；容量不足仅在过载时返回 429/503。
- 队列 DB 与容量状态需使用 V2 已配置的持久数据目录，API 和 worker 必须挂载同一 DB 文件/卷。SQLite 只适用于共享本机持久卷；跨主机/多副本部署需单独的共享协调器，不得将 SQLite 锁声称为跨主机锁。
- SQLite schema 采用向前兼容 `CREATE TABLE IF NOT EXISTS`；部署无需清理既有业务记录。

## 回滚

回滚只恢复代码与配置，不清除 `.v2_data`、V1 media storage、队列行、历史记录或 cache 文件。新增 DB 表可留存；旧代码忽略它。降低/关闭准入仅允许通过显式配置且仍需遵守容量安全边界。

## 验收矩阵

实现阶段需覆盖：跨进程竞争恰有上限数量获得准入；超限可重试响应；异常、取消、超时与进程退出后的占位恢复；陈旧且耗尽次数的队列任务保留终态；队列并发入队不超容量、运行中任务不计入待处理容量；请求体长度缺失/伪造/超限；JSON/base64 与二进制上传；分页、去重、总数和租户隔离；历史扫描拒绝超载且不阻塞异步 event loop、取消后保留扫描槽；Lab session 归属校验及并发释放；fake provider 不触发网络/计费。

测试只用临时目录、临时 SQLite 与 fake provider。VPS 上仍需验证共享卷语义、worker/API 部署拓扑、实际峰值内存、磁盘空间和 provider 超时边界；离线通过不等于生产容量已验收。

## 本轮验证记录

- V1：`tests/test_resource_capacity_guards.py`：14 passed。覆盖跨进程准入、crash TTL、heartbeat 临时异常、取消后 provider 线程仍运行、客户端超时而 fake remote 仍在运行、上传 body 边界、Lab session 准入、同幂等键重试、repo-miss 权限/收藏线程隔离和删除满载无副作用。
- V1：`tests/test_api_smoke.py` 单独运行：85 passed。`tests/test_api_smoke.py tests/test_api_access_keys.py` 合计 123 passed、2 failed。为核实失败归属，同一解释器和依赖在 detached `3915b24d` 基线上重跑两项失败节点，基线同样 2 failed：V3 project-output mock 缺少 `project_headers` 参数，MCP adapter 测试继发同一 `TypeError`。这两项不是由本次改动引入；不在本任务修 V3。
- V2：`tests/test_resource_capacity_guards.py`：16 passed，覆盖生图容量、queue crash/retry、历史超载/取消、权限回退及参考图/下载 repo-miss 路径不阻塞 event loop。
- V2 定向 API 回归（direct capacity 429、queue 满、worker 原任务重试、上传超限/租户隔离、历史记录/分页、缩略图/预览/删除、媒体加速重定向及回退）：12 passed。
- V2 全文件 `tests/test_v2_api.py` 曾与资源测试一并启动，连续运行约一分钟无后续输出后中断；不能将其计为通过。针对本次修改的精确用例已单独通过。
- `python -m compileall -q src_skeleton/app custom_media_agent_2_0/app tests custom_media_agent_2_0/tests` 已通过语法编译。
- 未调用真实付费图像 provider、未传递或读取密钥、未操作线上数据；未执行 VPS 性能或多副本部署验收。

## 用户决策与剩余边界

默认保留业务历史，不自动删除。仍留存且本次没有解决的增长面：V1/V2 MemoryRepository 的 session/job/output/idempotency/event/feedback 元数据；V1 聚合历史的全量记录和 dedupe set；V1/V2 JSONL 精确去重 map；V1/V2 历史删除操作暂存的全文件内容；Claude 决策 cache 的全文件读取与保存；Alchemy Lab 已完成 session；V2 durable queue 终态任务行。常规历史扫描已去掉全文件字符串/行数组副本、使用 top-K、限制同时执行数并从 V1/V2 async routes 移出事件循环，但不是严格 O(1) 内存分页。要安全限制这些剩余项，需要先确定可重载持久权威源、归档周期、恢复承诺、幂等/审计保留和管理员权限；当前无线上故障测量，不能据此优先删除。

### 长期数据的代码依据与下一阶段最小方案

- V1 `MemoryRepository` 将 sessions/assets/jobs/outputs/idempotency index/events 放在进程字典/列表中（`src_skeleton/app/repositories/memory.py`）；代码没有从数据库或文件重新装载这些记录的恢复路径。
- V2 `InMemoryV2Repository` 将 creative runs/image jobs/outputs/uploads/feedback/safety decisions 放在进程字典中（`custom_media_agent_2_0/app/repositories/memory.py`）。 durable task queue 只保存 queued task/run snapshot，不等于上述全部业务对象的完整、可重建仓库。
- Alchemy Lab `AlchemyLabStore.sessions` 是全局字典；只有 `delete_unpublished` 和显式 `reset` 会移除 session，完成的 session 没有自动保留期限或压缩路径（`src_skeleton/app/services/alchemy_lab.py`）。
- Claude decision cache 持续把 cache key 到完整 decision/metadata 写入单个 JSON 文件，并在查询时整体 `read_text`/`json.loads`（`custom_media_agent_2_0/app/services/claude_orchestrator.py`）；没有 TTL/LRU 或独立持久索引。

下一阶段最小开发顺序应先提供权威持久化和重载，再谈有界缓存/归档：先为 V1/V2 业务仓库与 Lab session 定义 SQLite schema、写入迁移及启动重载，证明租户归属、幂等恢复、worker 重启和用户继续流程；再把 Claude decision JSON 读取改为有索引的逐键查找，但保留完整决策记录，除非另行确定保留期；最后设计队列终态与 Lab session 的可配置归档。迁移完成前不对唯一内存状态做 TTL/LRU，避免丢失 job/session 身份、幂等证据、上传元数据、访问控制及恢复状态。这个迁移会改变持久化和重启语义，超出本次仅加容量护栏的最小修复范围，故在本 PR 中明确保留为未完成工作。

总目标仍未达到最终生产验收：本轮修复已覆盖源码内可安全实施的本机准入、队列、上传和历史扫描路径；完整 V2 API 文件、线上 VPS 共享卷/部署拓扑、内存峰值及远端 provider 终止状态均未验收。Draft PR 需在独立审查后提交，仍不合并、不部署。
