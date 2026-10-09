# V1、V2 与 Alchemy Lab 持久化及有界内存治理方案

## 目标与范围

总目标：V1、V2、Alchemy Lab 在保留现有 API 和历史可见性的前提下，不再让进程 RSS 随累计会话、Job、输出、反馈或 Lab session 数量持续增长。磁盘/SQLite 是权威数据源；进程内对象只作可丢弃、有硬上限的读缓存。

本阶段目标：为 V1、V2 与 Lab 建立可恢复的持久状态，给可重建缓存加条目数和序列化字节双上限，并将历史读取改为有界读取。默认不自动过期或删除用户数据；管理员显式删除仍按现有授权路径执行。磁盘增长、VPS 压测和部署另行验收。

非目标：不修改 V3；不新增 worker/进程；不改变生成、审核、计费、权限或 API 响应语义；不将缓存上限冒充数据留存期限；不直接清理旧历史。

## Correction model（改代码前固定）

- 观察到的根因：V1 `MemoryRepository`、V2 `InMemoryV2Repository` 和 `AlchemyLabStore` 同时充当业务权威和进程缓存；这让常驻内存随记录数增长。V2 部分文件/JSONL 副本不覆盖所有实体，不能直接据此淘汰字典。
- 所属层：持久化/Repository 与历史投影；不是生成、Provider 或前端问题。
- 被否决的修法：对现有 dict 直接 `pop`、TTL 删除整条业务记录、按固定日期裁掉 JSONL。这会丢失会话、任务状态、幂等证据或可见历史。
- 权威来源：新增模块自有的 SQLite 持久记录库，WAL、事务写入和索引；二进制图片/上传仍留在现有文件存储。JSONL 作为兼容导入/导出依据，导入完成后不再作为无界内存读取源。
- 派生缓存：每进程 LRU 同时限制最多条目数和最大估算序列化字节数。大于单条缓存阈值的记录只读磁盘，不进入 RAM 缓存。淘汰仅移除缓存引用，不能删除数据库行。
- 历史投影：索引查询按现有分页/排序规则返回窗口；事件按游标分批流出；禁止为“只返回一页”先构建全量 Python 列表。

## 现有来源与目标映射

| 模块 | 基线权威/缺口（3915b24） | 本轮实现及保持的权威 |
|---|---|---|
| V1 repository/events | `src_skeleton/app/repositories/memory.py` 中 sessions、assets、jobs、outputs、idempotency index、events 是 RAM 权威；资产二进制和部分历史另在文件 | V1 自有 `repository.sqlite3` JSON 表；Job、output 和幂等映射在单事务写入；事件游标读取；图片字节继续使用原文件存储 |
| V1 history/favorites | `LocalMediaStore` JSONL 与生成文件；收藏 JSON 整文件读取和改写；历史接口会全量组装后分页 | 旧 JSONL/收藏按单条流式迁入 SQLite 索引，来源文件保留；历史接口逐 Job 解码并写入请求级临时 SQLite 页索引，再按原排序分页；临时索引关闭后删除；文件恢复 top-k；收藏按当前页 ID 查询。内存不再同时持有全量 Job/历史投影，但请求 CPU、临时磁盘与 I/O 仍随总历史量增长 |
| V2 repository/history | repository 的 runs/jobs/outputs/feedback/safety/sync/provider/cases 为 RAM 权威；图片 JSONL、task queue、case index、上传 `asset.json` 已各存一部分 | V2 自有 `repository.sqlite3`，与 V1 隔离；主实体按 ID/索引查询，Job/output 与反馈选择在事务内更新；JSONL 一次按行导入并索引分页，原 JSONL 保留 |
| Alchemy Lab | `alchemy_lab.py` 的 `lab_store.sessions` 是 RAM 唯一完整 session store | Lab session 存入 V1 自有 SQLite，按 ID 读写，不由 Store 长期持有已解码 session |
| 可重建缓存 | V2 Claude 决策 JSON cache、V2 case intelligence 和 Lab style search 存在无界全对象/字典缓存 | Claude 缓存迁至独立 SQLite，128 项/8 MiB/64 KiB 单条上限；其他对象缓存 LRU，同时限条目、估算序列化字节和单条尺寸。旧 Claude JSON 不覆盖或删除 |

V1/V2 必须保持存储隔离；V2 不能导入 V1 repository。每个数据库路径必须来自该模块现有持久数据根目录，不写进代码仓库，不与临时目录共用。

## 分阶段实施

### 第 1 阶段：持久化契约与独立存储基座

建立 schema/version、原子 upsert/get/delete、分页查询、连接关闭、WAL/busy timeout 和受控迁移工具。数据库行保存完整 JSON model + 可索引字段。事务失败必须让调用失败，不能吞掉后回退成仅内存成功。测试 SQLite 重开/多进程读取写入、损坏行隔离、幂等唯一性、数据库 busy 错误映射。

### 第 2 阶段：V1 repository 与事件

将 V1 Repository 方法改为持久读写；替换直接字典访问。`list_jobs`/history 只取所需结果页；SSE 事件用稳定递增 ID 分批输出。保持 job 状态流转、失败信息、revision 关系、资产 owner 与显式删除语义。迁移既有文件/JSONL 时按单条流读，校验总数、ID、owner 和重复记录。

### 第 3 阶段：V2 repository 与 Lab sessions

逐表持久化 V2 repository，现有 task queue 保持自己的 schema/claim authority；creative run 与 queue snapshot/result 核对后导入，不能从新缓存覆盖 queue authority。上传元数据优先沿用现有 `asset.json` 并按需加载；feedback、安全决策、sync 状态增加持久表。Lab session 增加持久状态读写，不重启即丢失。

### 第 4 阶段：RAM 硬上限与历史读路径

使用可测的按条目数+序列化字节数淘汰的 LRU。初始上限：普通实体合计不超过 256 条且 32 MiB；单记录超过 256 KiB 不缓存；Claude 决策缓存不超过 128 条且 8 MiB，单条不超过 64 KiB。数值集中配置并写入启动日志（不记录用户内容）；并发不重复解析同一 ID。根据具体对象模型验证这些配置足以作为实际强上限；若 Pydantic/容器开销导致不能形成内存上界，应按保守系数下调，而不是声称序列化大小等于 RSS。

历史 list/count/详情查询必须走索引和分页；数据库读取页大小受 API limit 上限约束。V1/V2/Lab 不因打开首页而 materialize 所有项目或历史记录。Claude semantic lookup 仅扫描有界候选集；cache miss 不影响输出质量或授权判断。

### 第 5 阶段：兼容导入、故障恢复与验收

提供 dry-run 导入报告和可重入应用；核对旧来源与新表数量、ID/owner、状态/时间戳和输出引用。任何不一致 fail closed，原来源保持可读。重启/重复导入/并发启动测试全部通过后，代码阶段才可交付。

现有运行进程中的 V1/Lab 纯内存状态无法从已停止进程恢复。部署前必须从仍运行的旧版本通过受限只读导出生成本地快照，校验后再切换；本地代码改动不会自行恢复已经消失的进程内状态。本方案不访问 VPS、不触发现场导出、不自动删除任何旧文件。

## 验收

1. 持久记录重启后可完整读取；V1/V2/Lab 的现有接口输出与迁移前固定 fixture 一致。
2. 10 万条合成记录下连续随机读取/分页后，缓存条目和序列化字节不超过配置上限；GC 后 store 不持有全量实体；RSS 另行实测，不能以 `tracemalloc` 代替。
3. list limit=1 不同时解码/驻留全量历史 Python 对象；历史候选逐条读入临时磁盘索引，事件按游标流出；查询顺序、总量、owner、幂等与显式删除语义保持。扫描和临时磁盘使用仍是 O(N)。
4. 多线程/多进程写入、相同幂等键竞态、进程中断、数据库忙、坏 JSON 行、重复迁移均有回归；错误不能伪装成功或“无历史”。
5. 旧数据导入前后按实体类别比较 count、稳定 ID 集合、owner、状态、关联 Job/output；任何差异停止切换。
6. 内存/对象上界及离线回归通过后，再由单独授权的运维阶段做 VPS 快照导出和受控切换。本开发任务不声称 VPS 验收通过。

## 影响路径与回滚

允许改动：V1 repository/storage/配置/历史路由；V2 repository/config/history/cache；Alchemy Lab session store；相关测试和本开发文档。禁止改动 V3、图片生成质量逻辑、公开 schema、Provider 路由、部署配置和 VPS 数据。

回滚只切回旧代码并保留新增数据库和旧来源文件；不删除数据库、不回写旧 JSONL、不在未核对时双向合并。若新 schema 写入已开始，应使用兼容版本读取；回滚前记录新旧 authority 状态，避免旧进程覆盖新记录。

## 当前进度与本轮实现状态

- 冻结 baseline：`origin/main` / `3915b24d0cdab6cc626ad5a7d07c0839e5239064`。
- 工作边界：隔离 feature worktree `codex/durable-bounded-retention`；主工作区原有未提交改动保持不动。
- 风险：A2（跨模块持久化/权限/幂等/历史）；I2（多存储交互与恢复）；D0（默认永不自动过期，业务语义不变）。
- 实现已经开始。当前版本以模块专属 SQLite 保存 V1/V2 repository 元数据、Lab session、V1/V2 历史索引和收藏；V2 Claude 决策缓存与两个对象缓存已加双重预算。
- 持久化契约测试先按失败状态运行，再实现并复测；定向测试目前分批通过（详见 `PROGRESS.md`）。后续必须在最终冻结 diff 上完成 Source Fidelity A1 与普通 A2 独立审计。
- V1 `/v1/image/history` 现在只在 RAM 保留当前 Job、受 API 上限约束的结果页，以及既有固定上限 10,000 条的文件恢复窗口；全量候选排序/去重状态落在每请求临时 SQLite 文件。它消除了全量 Python 对象集合，但没有消除 O(N) 磁盘写入、元数据解析和扫描 CPU；并发请求会各自使用临时文件。磁盘空间与延迟必须在本地/VPS验证，不能由该实现宣称 CPU 或 P95 已改善。
- V2 `list_cases()` 等明确请求全部案例的现有调用仍会在单个请求中临时加载整个集合；本轮消除了进程长期保留该集合的无界 repository/cache，但不把该读取契约改为分页。因此高并发 case 查询仍可能叠加 transient RAM 峰值，属于本次不扩大的后续容量风险。
- 有界对象缓存的“字节数”为递归 `sys.getsizeof` 估算值，不等于 RSS 硬上限；用户/业务记录已改为 SQLite authority，缓存条目和估算字节有明确上限，但 Python runtime、请求 payload、单 Job、V2 全量 case 查询和临时磁盘不包含在该 cache budget 中。
- 持久化改变了运行权威；任何正在旧进程内、尚未落盘的 V1/V2/Lab 业务状态不能靠新 SQLite 自动恢复。切换前必须制定并执行旧进程只读导出、逐类计数/ID/owner/状态对账与可回滚导入。当前未访问 VPS，未准备现场快照。

## 冻结源代码映射（Source Fidelity 输入）

- Reference repository/root：本仓库；immutable reference commit：`3915b24d0cdab6cc626ad5a7d07c0839e5239064`（实现开始时的 `origin/main`）。
- Target root：`.codex-work/durable-bounded-retention`；target baseline 同 reference commit；实现分支 `codex/durable-bounded-retention`。
- Reference source manifest SHA-256（按下表 13 个 source path 的 baseline bytes 计算）：`a307ad572b76d0f0cb57cfb4c19d591084b6887204fe1e98139aafb8df3b53e5`。
- 本次冻结目标代码+测试指纹 SHA-256：`685d51d6f66c39f396bf2b5b9ccfc96950198d52e60280062ece1210d6439190`（包含 25 个 changed/untracked source/test files，排除本方案与 `PROGRESS.md` 两份滚动文档）。任何代码/测试修改后须更新指纹并重跑 Source Fidelity。
- 来源文件清单和映射如下；审计必须逐项比较该 commit 的源行为与 target，不得仅按本方案文字推断源契约。

| Baseline source path @ 3915b24 | Target path | Mapping | 保持的源行为/边界 |
|---|---|---|---|
| `src_skeleton/app/repositories/memory.py` | 同路径 | THIN_ADAPTER | repository 方法与返回模型保持兼容；仅将 RAM 权威改为 SQLite，原 job/output/idempotency 语义及删除联动保持 |
| `src_skeleton/app/services/events.py` | 同路径 | THIN_ADAPTER | SSE 事件内容和先后顺序一致；改为游标迭代 |
| `src_skeleton/app/storage/local.py` | 同路径 | THIN_ADAPTER | 文件字节、历史字段、排序/过滤和删除语义保持；JSONL 导入逐行，SQLite 索引分页 |
| `src_skeleton/app/services/favorites.py` | 同路径 | THIN_ADAPTER | owner/public 可见、收藏/取消收藏/删除行为保持；旧 JSON 流式一次导入并保留 |
| `src_skeleton/app/main.py` | 同路径 | THIN_ADAPTER | V1 history API 字段、owner 过滤、排序、offset/limit 与 total 保持；Job 候选逐条读取、全量排序状态在临时 SQLite 中，favorite 查询缩为返回页。扫描 CPU 和临时磁盘仍随历史规模增长 |
| `src_skeleton/app/services/alchemy_lab.py` | 同路径 | THIN_ADAPTER | Lab session API/model/state 原语义保持，session 不再依赖 RAM 生存 |
| `src_skeleton/app/services/alchemy_lab_style_search.py` | 同路径 | AUTHORIZED_NEW | 本任务明确授权的派生搜索缓存限条数/估算字节；不改变持久数据和搜索结果 authority |
| `custom_media_agent_2_0/app/repositories/memory.py` | 同路径 | THIN_ADAPTER | V2 repository 调用/模型、owner/filter、队列 authority 边界保持；V2 SQLite 独立于 V1 |
| `custom_media_agent_2_0/app/services/image_history.py` | 同路径 | THIN_ADAPTER | JSONL 字段、owner、重复 ID 取舍、稳定排序、total/page/delete 行为保持；SQLite 索引按行导入 |
| `custom_media_agent_2_0/app/services/favorites.py` | 同路径 | THIN_ADAPTER | 用户收藏隔离和当前行为保持；旧 JSON 流式导入并保留 |
| `custom_media_agent_2_0/app/services/claude_orchestrator.py` | 同路径 | AUTHORIZED_NEW | 仅可重建 LLM 决策缓存被有界；不得缓存裁剪用户历史、改变持久输出 authority 或删除旧文件 |
| `custom_media_agent_2_0/app/services/case_intelligence.py` | 同路径 | AUTHORIZED_NEW | 仅派生内存对象缓存有限额；查询数据源和外部 case 刷新语义保持 |
| `custom_media_agent_2_0/app/main.py` | 同路径 | THIN_ADAPTER | 路由与既有 favorite/owner 返回契约保持，只将无界收藏查询改成单 ID 查询 |

禁止/未授权映射：任何 V3 路径、Provider/模型调用、用户数据自动删除/过期、公共 schema 更改、部署配置变化。Source Fidelity 若发现原行为证据与上述目标表述冲突，应报告 `SOURCE_CONFLICT`，不能自行将映射改为新语义。

## 执行冻结（2026-10-09）

- 用户目标：立刻治理 V1、V2、Alchemy Lab 的内存留存；PR 集成和 VPS 验收暂缓。
- 非目标：不做 VPS 操作/部署、不合并 PR、不自动清除任何用户业务记录、不改 V3、不触发模型或 Provider。
- 写入者：主控在本 feature worktree 单独写入；当前没有其他 writer。
- 允许边界：本方案涉及的 V1 repository/history/events、V2 repository/history/decision-cache、Lab session store、相应测试与本文件。不得修改根 main 工作区既存改动。
- 风险分类：D0（保留数据、持久权威、内存有界已明确）；I2（跨仓库原子性、分页/兼容与异常恢复交错）；A2（持久化、owner、幂等及用户记录）。
- 关键不变量：数据库/现有文件是业务权威；读缓存可丢弃但有双重预算；写入持久化失败必须显式失败；owner、状态、排序、幂等及历史可见性保持；任何缓存淘汰不得删除用户数据。
- 运行进程数据边界：当前 V1/Lab RAM-only 记录无完整导出入口。此代码变更不能复原已消失记录；VPS 切换必须先从旧进程做经过校验的只读导出，否则阻止切换并明确记录损失范围。
- 验收方式：先写失败回归；完成三模块持久化和有界读取后冻结版本，分别运行 Source Fidelity A1 只读侧审与普通 A2 独立代码审计。审计 PASS 前不提交/推送或部署。
- 当前阶段：实现与测试收尾；下一步冻结精确 diff，先做 Source Fidelity A1，再做普通 A2。未完成审计与历史接口峰值问题之前，不合并、不部署。
