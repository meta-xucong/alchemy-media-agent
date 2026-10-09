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
| `src_skeleton/app/repositories/sqlite_json.py` | 同路径 | AUTHORIZED_NEW | 本方案授权的 V1/Lab SQLite adapter；数据持久化与事务失败语义，不改公开模型 |
| `src_skeleton/app/services/events.py` | 同路径 | THIN_ADAPTER | SSE 事件内容和先后顺序一致；改为游标迭代 |
| `src_skeleton/app/storage/local.py` | 同路径 | THIN_ADAPTER | 文件字节、历史字段、排序/过滤和删除语义保持；JSONL 导入逐行，SQLite 索引分页 |
| `src_skeleton/app/services/favorites.py` | 同路径 | THIN_ADAPTER | owner/public 可见、收藏/取消收藏/删除行为保持；旧 JSON 流式一次导入并保留 |
| `src_skeleton/app/main.py` | 同路径 | THIN_ADAPTER | V1 history API 字段、owner 过滤、排序、offset/limit 与 total 保持；Job 候选逐条读取、全量排序状态在临时 SQLite 中，favorite 查询缩为返回页。扫描 CPU 和临时磁盘仍随历史规模增长 |
| `src_skeleton/app/services/alchemy_lab.py` | 同路径 | THIN_ADAPTER | Lab session API/model/state 原语义保持，session 不再依赖 RAM 生存 |
| `src_skeleton/app/services/alchemy_lab_style_search.py` | 同路径 | AUTHORIZED_NEW | 本任务明确授权的派生搜索缓存限条数/估算字节；不改变持久数据和搜索结果 authority |
| `custom_media_agent_2_0/app/repositories/memory.py` | 同路径 | THIN_ADAPTER | V2 repository 调用/模型、owner/filter、队列 authority 边界保持；V2 SQLite 独立于 V1 |
| `custom_media_agent_2_0/app/repositories/sqlite_json.py` | 同路径 | AUTHORIZED_NEW | 本方案授权的 V2 独立 SQLite adapter；与 V1 文件和命名空间隔离 |
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

## 审计后修订：跨调用一致性收尾

### 观察到的不一致

PR #28 的固定版本 `29148df9d7d2bbf70a5b4e411541d467e326a19f` 已通过原审计，但后续独立探针报告：历史重复记录可能把已知私有 owner 降级为无 owner；Lab runner 用旧 session 快照覆盖并发收藏；SQLite 同步锁等待阻塞异步事件循环；损坏收藏源仍可能写入迁移完成标记；SSE 跨 yield 保留 cursor/connection；测试先 reset 再切临时数据根；并发删除和重启中的生成状态仍需明确定义。

### 权威规则

1. SQLite 记录是 V1/V2/Lab 持久状态权威；任何并发更新都必须基于事务内最新行，不得用过期整对象快照覆盖其他字段。
2. 对历史记录，显式 owner 是访问控制权威。文件存在性、恢复扫描和重复 ID 只能补充可用性，不能删除已知 owner 或将其变成公共记录。已知 owner 的重复记录应优先于 owner 缺失的恢复副本，再按现有可见性规则过滤。
3. SQLite 忙锁是有限、可重试的存储错误；不能让同步等待阻塞事件循环，也不能无限等待或把失败报告为成功。同步数据库工作须在有界执行边界运行。
4. 收藏迁移标记只在完整验证来源并成功提交导入的同一个数据库事务中写入；无效/截断输入必须回滚，修复文件后允许重试，并发首次迁移结果须唯一。
5. SSE 不允许在响应迭代器跨 yield/线程复用 SQLite connection/cursor；以稳定事件游标分批读取，每批结束关闭连接，保持原事件顺序且不漏不重。
6. 删除联动需在同一存储事务内读取权威 output/job 并更新引用；跨文件删除保持可重入，不得由竞争删除留下指向已删除图片的 Job 引用。
7. 持久的 `queued/generating` 记录并不意味着后台工作可恢复。启动时必须把本进程无法续接的工作显式归为中断态；不得静默重放可能已到达 Provider 的请求，且幂等键不能永久卡在不可续接的旧状态。

### 最小修复边界和验收顺序

先为所有涉及全局 repository/SQLite 的测试安装临时数据根，再运行任何可能调用 `reset()` 的用例。其后先补跨账户历史重复 owner 回归，再按当前持久模型补 Lab 字段级更新、数据库有界线程/忙锁返回、严格迁移原子性、SSE 分页连接生命周期和并发删除/重启状态回归。每项先证明固定版本失败，再做局部实现；不新增缓存框架、通用状态机或超出本方案的公共 API。

交付门槛：V1/V2/Lab 定向测试及相关原有回归通过；迁移失败可修复后重试；锁压力下 event loop 心跳持续；强制线程切换的 SSE 全量序号无遗漏；私有 owner 不能通过任何 fallback 出现在其他账户响应；收藏更新不能被 runner 回滚；启动后无永久 `generating` 幂等阻塞。随后对最终代码/测试指纹运行 Source Fidelity A1 和独立 A2。PR #26/#27 交叉集成、旧进程 RAM-only 数据导出与 VPS RSS/磁盘/延迟验收仍是单独的后续门槛，本修订不授权合并或部署。

### 本轮最小实现与阶段验收记录

- 历史索引在重复 ID 合并时保留已知 owner；历史 API 在检查图片文件前先记录来源 ID，缺失文件不能让已知私有记录从恢复路径降级为公共记录。
- Lab 收藏使用事务内最新行作准；runner 保存状态时合并最新 favorites。V1/V2 非生成 API 的 SQLite 读写投影以及 Lab runner 的相关 SQLite 调用离开事件循环并有界执行；SQLite/执行容量忙映射成 `503` 与 `Retry-After: 1`。V1 `image_service` 和 V2 `generation` 中 Provider 前后的直接同步仓库调用不属于本轮已解决范围，按本文件末尾列出的残余处理。
- 收藏导入完整解析外层 JSON 后才写迁移标记，导入数据与标记同事务提交；补充截断修复重试及并发首次导入回归。
- SSE 历史事件先固定本次读取的最大事件 ID，再按 128 条游标批读取；每批在 yield 前关闭连接。
- V1/V2 删除图片均在读取 output/job 前取得 `BEGIN IMMEDIATE`，同一 Job 的并发删除不会互相恢复旧引用。
- V1 queued/generating 任务及 Lab queued/running session 在启动时分批标记为 `worker_interrupted`，不自动重放 Provider；部分完成 Lab 保留已成功结果及收藏。
- V2 测试使用 autouse 临时 `data_dir` 隔离，避免 `repository.reset()` 接触工作区或用户数据库。
- 当前定向证据：V1 持久化/历史/收藏/Lab/迁移/SSE/锁边界 20 项通过；V1 公开 API 关联用例 6 项通过；V2 持久化/历史/收藏/迁移/锁边界 9 项通过；V2 API 全套 173 项通过。V1 `test_api_smoke.py` 全文件长测曾手动中止，不能计作全套通过。编译、完整 diff 审查及独立 Source Fidelity A1 / A2 尚待完成。
- 本记录仅表示代码阶段的测试进展。精确 diff 与测试树冻结后必须重新进行 Source Fidelity A1 和独立 A2；当前旧版审计收据不适用于本轮改动。审计通过后只更新 Draft PR #28；不合并、不部署。旧进程数据导出及 VPS 运行验收仍是独立门槛。

### 审计追加修订：异步读取投影与终态分类

独立 A2 针对上一个工作指纹发现：V1 全历史、Lab 历史和 V1/V2 图片详情仍有 async handler 直接执行 SQLite-backed 同步读取。之前仅包装了部分收藏/删除/所有者调用，不能覆盖完整路由工作量；SQLite 锁等待仍可能阻塞事件循环。另有 Lab session 已将全部 variant 保存为成功、但在最终 session 汇总持久化前退出时被错误分类为部分成功。

保持的权威：SQLite 与已持久化图片继续是唯一来源，API 字段、owner/排序/分页和图片投影保持原实现。修正只把现有纯同步读取投影整体放入相同有界 off-loop 边界，禁止在投影里再嵌套调用有界 helper；DB 忙仍按既有可重试语义处理。Lab 启动恢复先检查 variant 结果：全部成功时补齐 `completed` 汇总且不增加中断错误；存在未完成工作才按已有规则标记中断，不重放 Provider。

验收增加实际路由级持锁＋event-loop heartbeat 回归，覆盖 V1 history/Lab history/download 与 V2 thumbnail/preview/download；并覆盖 Lab 全部 variant 成功但 session 汇总仍 running 的重启边界。此修订使前述 fingerprint 失效；实现后重新跑测试并重新执行 Source Fidelity A1 与独立 A2。

### 异步读取与 Lab 恢复修订实现记录

- V1 `/v1/image/history` 保留同步历史投影实现，但公开 async 路由现在将整次投影交给有界 SQLite worker；`/api/lab/history` 同样把整个列表投影移出事件循环。
- V1 下载、缩略图和预览路由在同一有界边界中解析 SQLite 输出记录；缩略图/预览的读取与派生生成也在 worker 中执行，未改变文件路径、媒体类型或响应头。
- V2 历史缩略图、预览、下载（包含文件读取回退）和收藏参考图创建均交给现有有界 SQLite worker；权限检查仍先完成，owner 过滤与公开返回结构不变。
- Lab 启动恢复若发现 session 仍是 queued/running，但所有非空 variants 均已成功，则只补齐 completed 汇总与进度，不附加 `worker_interrupted`；仍存在未完成 variant 时继续采用显式中断，不自动重放 Provider。空 variant 集合仍按中断处理。
- 新增真实路由调用级锁冲突＋异步心跳测试。V1 覆盖完整历史、Lab 历史及输出下载/缩略图/预览；V2 覆盖缩略图/预览/下载和收藏转参考图；锁等待应返回 503、`Retry-After: 1`，心跳在等待期间持续运行。Lab 增加“所有变体已成功、聚合 session 状态仍 running”的恢复回归。
- 本次阶段验证：V1 持久化/历史/Lab/迁移/SSE/锁边界加 10 个明确历史/owner/Lab API 回归共 26 项通过；V2 完整 API 及存储/迁移/路由锁边界共 181 项通过。前后测试有重叠，不相加为独立总数。`test_api_smoke.py` 全文件未通过执行；没有真实模型、VPS 或浏览器压力验证。
- 对 22 个修改/新增 Python 源与测试文件计算的冻结指纹为 `7dfd67fcc27e1c5af2d21468e48d926e3364f42f5ad0d2d49d593d37beee068a`。确定算法为按路径排序后，对每个条目依次写入 UTF-8 相对路径、NUL、该文件 SHA-256 的 64 字符小写十六进制、NUL，再对串接字节计算 SHA-256；排除本开发方案与 `PROGRESS.md`。目标分支基线为 PR #28 提交 `29148df9d7d2bbf70a5b4e411541d467e326a19f`；当时抓取的 `origin/main` `3915b24d0cdab6cc626ad5a7d07c0839e5239064` 是该基线的祖先，不是其后继。target 为该基线加工作区变更。任何源/测试文件变化都会使此指纹失效。
- 以上是实现阶段证据，不构成最终验收。旧 Source Fidelity A1/A2 回执均不适用于本指纹；下一步只读审计必须针对该精确指纹。审计通过前不提交/推送、不合并、不部署。

### 取消后物理工作容量修订

#### 观察到的不一致

A2 对上一冻结版实际取消 SQLite worker 的请求任务后发现：awaiter 被取消并进入 `finally`，semaphore 名额立即归还，但 `run_in_threadpool` 内原生同步函数仍在工作线程里执行。循环重复取消即可继续提交工作，使物理活动线程超过声明的两路并发。先前的“运行中取消”测试没有把活动调用线程的生存期与 awaiter 分开测量。

#### 权威与最小修复

每个 V1/V2 API 进程的最多两个 SQLite 工作名额，权威依据是同步函数对应的底层 concurrent future 是否完成，而不是请求协程是否完成。对取消，客户端可立即停止等待；已提交函数不强杀、不重复提交，原名额必须保持占用到该 future 真正结束。固定两线程 executor 与最多两个已准入 futures 一起限制物理并发及排队；第三个超限请求仍按既有约定返回 503/`Retry-After: 1`。请求 waiter 使用 `asyncio.shield`，不会取消尚未执行的 concurrent future；提交失败或 executor 明确取消已从物理队列移除的 future 时释放名额；SQLite busy 映射保持不变。

#### 回归要求

V1、V2 各增加确定性线程测试：同时阻塞两个已准入操作，取消两个 awaiter，在底层函数仍未结束时再提交第三个操作；第三个必须收到 503，记录的物理活动数不得超过 2。释放阻塞后，两项原操作退出，名额恢复，后续正常操作可以成功。测试还须验证 worker 抛出 SQLite busy 时 awaiter 收到 503，且清理后容量恢复。此修订变更 API helper 及测试，因此任何先前冻结指纹与审计均失效；完成后必须重新运行定向测试并重新派发 A1/A2。

### 取消容量、Lab 准入与恢复终态修订

#### 纠正模型

SQLite 线程池容量绑定底层 `concurrent.futures.Future` 的完成回调；API awaiter 取消不能归还尚在运行的工作名额。V1 与 V2 各自使用固定两线程执行器，且同一时刻最多准入两个 Future，不创建超限线程池队列。Lab 共享 V1 的 SQLite 执行边界；Lab 活跃会话先做非阻塞准入，最多两个，容量满时复用 `503 storage_busy` 与 `Retry-After: 1`，拒绝发生在规划、持久化和后台 task 创建之前。已准入会话仅在同步执行结束或 runner task 真正结束后释放相应容量。

重启恢复只聚合持久化变体状态：非空 variants 全部终态时按成功/失败数量归为 completed、partial_success 或 failed，并保留已有错误；只有仍有 queued/running variant 时才补 `worker_interrupted`。零 variant queued/running session 继续按中断处理。恢复不调用 Provider。

#### 回归要求

- V1、V2 与 Lab 分别阻塞两个线程操作、取消等待协程并尝试第三项；第三项保持被拒绝，底层活动峰值不超过 2，解锁后容量恢复。
- Lab 同时两会话准入后，第三个请求不得进入规划、持久化或后台执行；两个 runner 结束后可再次准入。
- Lab 重启恢复覆盖全成功、全失败、成功+失败、存在非终态、零 variants；全部终态均不得添加 `worker_interrupted`，存在非终态才追加，且不得触发 Provider。
- 启动恢复函数必须注册在 V1 FastAPI startup 列表并执行 V1 job 与 Lab session 恢复。

#### 当前实现进展

V1/V2 SQLite 调用现使用固定两线程的 `BoundedSQLiteCalls`；容量基于 `threading.BoundedSemaphore`，由底层 concurrent Future 完成回调释放；请求取消只取消 waiter，不会取消仍排在 executor 队列中的 Future。V1/Lab 共用 V1 执行器，V2 使用独立执行器。Lab runner 的会话准入上限为 2，先准入再进行 session 规划/持久化；完整 session 只在提示词和 variants 构造完成后写入一次，超限映射到现有 503 响应。Lab 重启恢复现可重建全终态 mixed/all-failed session 的聚合状态而不伪报中断。

另补 Lab create awaiter 取消边界：创建阶段由拥有准入租约的内部任务完成，并由外层 `asyncio.shield` 防止客户端取消提前中止 owner。若请求取消，内部任务仍被跟踪；session 保存成功后仍须 handoff 到唯一 runner，runner 结束后释放准入。创建准备失败则 owner 自行释放。此路径不因取消而自动重复 Provider。

#### 本轮明确排除：异步生成服务的 SQLite 调用

本 PR 的异步 SQLite 保证仅覆盖本次明确改造并由路由锁测试验证的 V1/V2 持久化投影、历史/收藏/delete API 及 Alchemy Lab session 生命周期，不应泛化为“所有非生成 API 已隔离”。以下调用仍可能在事件循环里同步等待 SQLite 锁；本轮不把它们表述为已解决，也不通过机械包装当前 fail-fast helper 来掩盖风险：

- V1 `src_skeleton/app/services/image_service.py` 的 `submit_image_job`、`create_image_job`、`revise_image_job`、`submit_revise_image_job`、`run_submitted_image_job`、`_prepare_submitted_image_run`、`_run_image_request`，以及 `_revision_source`、`_emit_image_events`、`_persist_history_records`、`_discard_job_outputs` 等被这些异步流程调用的同步仓库操作。
- V1 asset content 写入：`src_skeleton/app/main.py` 的异步 `PUT /v1/assets/{asset_id}/content` 路由同步调用 `src_skeleton/app/services/asset_service.py:store_asset_content` 或 `store_asset_content_bytes`；路径内同步读取/写入持久 asset 元数据并写内容文件。此端点未由本轮路由锁冲突测试覆盖。
- V2 `custom_media_agent_2_0/app/services/generation.py` 的 `create_running_image_job`、`create_image_job` 及 `_save_job` 中的同步仓库操作。
- V2 creative-run 路径：`custom_media_agent_2_0/app/agents/runtime.py` 的 `queue_run`、`complete_queued_run`、`_run_deterministic_manager`、`_save_run_stage` 对 creative-run 的同步读写；`custom_media_agent_2_0/app/services/safety.py:run_safety_check` 对安全决策的持久化；`custom_media_agent_2_0/app/main.py` 的 `/api/v2/creative/runs`、`/api/v2/creative/runs/async` 及异步 revision 路由中直接或间接调用上述方法的路径。
- V2 upload content 写入：`custom_media_agent_2_0/app/main.py` 的异步 `PUT /api/v2/uploads/{asset_id}/content` 路由，在读取请求 body 后同步调用 `custom_media_agent_2_0/app/services/uploaded_assets.py:store_uploaded_asset_content` 或 `store_uploaded_asset_bytes`；这些方法继续同步读取/写入 SQLite uploaded-asset 元数据并写内容文件。数据库锁等待可能阻塞 API worker 的事件循环。此上传写路径没有由本轮锁冲突路由测试覆盖，故明确列为残余。

V1/V2 生成及 creative-run 路径跨越 Provider 前后的任务建立、幂等检查和最终结果持久化。若 Provider 已成功或已扣费后，SQLite worker 容量满被 fail-fast 拒绝，图片结果可能无法持久化，并可能使客户端重试产生重复 Provider 费用。因此本轮不把这些生成写入直接改为可拒绝的 503。单独修复必须先设计 Provider 前的任务准入与终态提交保障，证明 Provider 后必需写入不会因容量拒绝而丢结果，也不得自动重放 Provider；Provider 网络调用及图像处理始终不得放进 SQLite executor。V1/V2 upload content 是另一类残余：当前异步路由同步完成文件写入和元数据读写，本轮未证明其文件/元数据原子性及安全重试语义，也未覆盖锁冲突，故明确记录为未解决项，而不机械套用现有 503 helper。

这些残余可能在数据库锁竞争时阻塞同一 API worker 的事件循环，影响并发响应性；它们不推翻本 PR 对持久化权威和有界缓存的修改，但不能据本 PR 宣称图像生成、V2 creative-run 或 V1/V2 upload content 写入路径也具备完整的异步 SQLite 隔离。后续需用独立变更和 fake Provider/锁竞争回归处理，不调用真实 Provider 作为探索性调试。

#### 本轮修订验证记录

- V1 持久化/历史/Lab/SSE/SQLite 容量相关测试 28 项通过；另有 10 项针对历史排序、分页、owner 隔离和 Lab 历史的公开 API 回归通过。两组不代表完整 `test_api_smoke.py`，该文件全量本轮未完成。
- V2 API、持久化、收藏导入和 SQLite 取消容量组合套件 183 项通过。
- 修改/新增的 V1/V2 Python 源和测试文件 `compileall` 通过，`git diff --check` 通过。测试输出包含 FastAPI/Starlette 生命周期弃用告警。
- 一次初始 V1 定向运行因新测试缺少 `sqlite3` 导入而失败；补上导入后，最终上述定向套件通过。另一次扩展到完整 V1 smoke 的组合运行被主动中止，不能计作通过或产品失败。
- 没有调用真实 Provider、读取/修改线上数据、部署 VPS 或进行 RSS/性能验收。当前代码与测试树必须按 Progress 中记录的精确 fingerprint 完成新一轮 Source Fidelity A1 与 A2；审计通过只允许更新现有 Draft PR，不授权合并、数据迁移或部署。

### 独立复审后的最后窄修订

#### 修正模型

上一次 A1/A2 均未放行，问题分属不同边界：A1 指出文档没有完整列出 V2 creative-run 的同步 SQLite 残余，且 SSE 测试未证明跨 128 条批次及开始迭代后的追加事件边界；A2 复现 Lab 创建调用在同步保存仍运行时被取消，可能先释放会话准入容量，而后台 SQLite 写入随后成功，留下 queued 但没有 runner 的会话。A2 后续复核还发现 V1 和 V2 异步 upload content 写入路径未列入残余范围，并建议对 Lab runner 单次 handoff 加明确断言。

保留的权威是 SQLite 行及其 owner、状态和事件游标。此次修订还将 V1/V2 upload content 写入补入残余清单，并让取消回归明确断言 runner handoff 恰好发生一次。客户端取消不再等于撤销已经开始的 session 创建，也不复制 Provider 工作。

#### Lab 取消交接规则

`create_exploration_session` 先非阻塞取得会话容量，再通过受 `asyncio.shield` 保护的内部 task 执行准备、持久化和 runner handoff。调用方取消时，只取消其等待；owner task 保留 admission lease，并由 `_background_tasks` 持有至结束。若 queued session 已持久化，必须继续安排且只安排一个 runner；容量直到 runner 完成才归还。准备/持久化失败则由 owner task 归还容量。进程关闭或崩溃后，既有启动恢复将无法续接的 queued/running 状态标为中断，不重放 Provider。

回归通过阻塞实际 SQLite-backed `save`、取消外层创建任务、再释放保存：取消后且 runner 活跃期间不能取得准入；已持久化 session 必须启动且只启动一个 runner；runner 结束后容量恢复。测试使用 fake runner，不调用 Provider。

#### SSE 快照边界

回归先建立 130 条事件，再启动 iterator 并读取第一项以固定最大 event ID；随后追加第 131 条事件。完整迭代必须准确得到原始 130 条，ID/顺序不变，且追加项不进入当前流。这覆盖 128 条分页边界和 snapshot isolation。实现仍按批读取、每批在 yield 前关闭 SQLite 连接。

#### 明确的生成链路残余

除了前文列出的 V1 `image_service` 与 V2 `generation` 外，V2 creative-run 也不属于本轮已解决的异步 SQLite 隔离范围：

- `custom_media_agent_2_0/app/agents/runtime.py`：`queue_run`、`complete_queued_run`、`_run_deterministic_manager`、`_save_run_stage` 的 creative-run 同步仓库读写。
- `custom_media_agent_2_0/app/services/safety.py`：`run_safety_check` 的安全决策持久化。
- `custom_media_agent_2_0/app/main.py`：`/api/v2/creative/runs`、`/api/v2/creative/runs/async` 和异步 revision 路由直接或间接进入上述逻辑的调用路径。

这些逻辑可能在 SQLite 锁等待时阻塞 API worker 的事件循环。它们横跨 Provider 前的任务建立、幂等判断与 Provider 后的必要结果提交，不能直接改用可拒绝的 fail-fast 写入，否则可能丢掉已付费结果或诱发重复请求。后续若治理，必须先设计 Provider 前 admission 和 Provider 后不可丢失的终态提交，并用 fake Provider/锁冲突回归验证；本轮不做 Provider 调用、重放或生成路由行为修改。

#### 本轮验证与审计状态

- V1/Lab/SSE/SQLite 容量相关焦点测试：30 passed；其中包含取消保存交接及 SSE 130 条固定快照。
- 五项公开 API 回归（历史排序、分页、用户/管理员 owner 可见性、重复 owner 防降级、Lab 私有历史）：5 passed。
- V2 API/持久化/迁移/容量组合套件：183 passed。
- 变更 Python 文件 `compileall` 与 `git diff --check` 通过；FastAPI/Starlette 有弃用告警。完整 V1 `test_api_smoke.py` 未运行通过，不能视为全量通过。
- 上述为本地隔离测试。未调用真实 Provider、未访问生产数据、未部署或采样 VPS RSS/延迟。
- 本节后冻结所有 `.py` 源码和测试文件，生成新 fingerprint，并重新运行独立 Source Fidelity A1 与 A2。旧指纹审计收据一律不适用。只有两项新审计均 PASS 才更新现有 Draft PR #28；仍不合并、不部署。
- 本节最终代码/测试冻结指纹：`d6d8f3de469e4c01dc2ed3c3b994d849d45c5fd25ce05f0e9dd159513c974fa0`，覆盖 26 个改动或新增的 Python 文件。计算规则沿用本文冻结映射：按相对路径排序，对每个路径串接 UTF-8 路径、NUL、该文件小写 SHA-256 十六进制、NUL，再对总字节计算 SHA-256；文档与 `PROGRESS.md` 不参与。任何 `.py` 改动都会使此指纹失效。此最终指纹包括 Lab runner 恰好一次的回归断言；V1/V2 upload content 残余已列入本节上文。
- 最终独立审计回执：Source Fidelity A1 与独立 A2 均对上述指纹 PASS。A1 核对文档范围及源码/测试证据；A2 复核 Lab 取消 handoff、唯一 runner、SSE 固定快照、V1/V2 上传残余及其他相关持久化路径。审计者的 Python 环境未安装 pytest；本机验证单独记录为 V1/Lab/SSE/SQLite 容量 30 passed、五项公开 API 回归 5 passed、V2 组合套件 183 passed，Lab/SSE 两项最终断言回归亦通过。完整 V1 `test_api_smoke.py` 未运行通过。未调用 Provider、未访问生产数据、未部署或执行 VPS RSS/性能验收。现有 Draft PR #28 可更新，但不得据此合并或部署。

### 增量审计收尾（2026-10-09）

#### 审计基线与修正模型

针对 Draft PR #28 的 `58333063b5b7521518c95de834d70e861a584339` 增量审计，复现了三项遗漏：V1/V2 收藏解析器在每条 JSON 值后无条件读入 64 KiB，导致输入缓冲逐步接近整份文件；Lab 已持有成功输出的 runner 在 SQLite worker 饱和超过一秒时放弃成功状态写入，随后恢复读取也可能受同一容量拒绝；V1 历史删除分步申请 SQLite 名额，前面已删输出与图片后，后续步骤可能返回 503，破坏重试授权依据。

保留的权威仍是现有文件和 SQLite 记录，不新增缓存或状态框架。解析器仅在当前 token 不完整、确需更多字节时压缩已消费内容并补读。Lab 已准入 runner 对临时 worker 容量满或数据库 busy 使用 capped exponential backoff 重试关键状态读取/提交，等待期间持有现有 session/task 所有权；源码调用路径不因这类忙锁重试重新进入 Provider 调用，但本轮测试只是检查点辅助层模拟，并非端到端 Provider 执行证明。其他 Lab 操作仍沿用原有有限等待策略。V1 删除在身份校验后只申请一次 SQLite worker 名额，名额内完成幂等文件、收藏及历史清理；若已验证 owner 只存在于历史投影，则先将该 owner 补到仍保留的 repository output，避免历史投影删除后丢失同 owner 重试资格。最后由一个 SQLite 事务删除 output/job 引用并写删除事件；仅当 Job 关联 session 时才产生事件。这样容量拒绝发生在任何清理副作用之前，中途失败可由同一 owner 重试。

#### 新增回归及局部验证

- V1/V2 收藏 reader 各以 3,000 条小记录（约 468 KiB）逐项解析，并记录 `_fill()` 后的最大缓冲；上限低于 80 KiB，证明不会把整个文件累积在解析器内存中。两项在修改前均因原断言/缓冲增长失败，修复后通过。
- Lab 检查点辅助层回归用真实共享 SQLite executor 的两个阻塞 worker 持续超过原一秒期限，再提交预先构造的成功 Job/output 快照。它验证 checkpoint task 保持等待、容量释放后快照保存成功；测试没有运行 `run_exploration_session` 或 Provider，也不作为 Provider 调用次数的端到端证据。源码调用路径显示 busy 重试 helper 不调用 Provider。
- V1 删除路由回归覆盖 bundle 名额在副作用前被拒绝；还覆盖 owner 只存在于 history 投影时，history 已删除而最后 output/job/event 事务遇 busy，repository output 仍保留并接收此前已验证的 owner；随后在启用 Veyra 鉴权的条件下，非 owner 重试被拒、同 owner 重试成功。同时断言关联 Job/session 的删除事件只写一次。初始增量审计中的分步删除失败已在基线上复现；新增的 history-only owner 组合由 A1 指出后加入回归并在修复后通过。
- 当前局部验证：V1 持久化/历史/收藏/SQLite 容量/删除回归 19 passed；公开 API owner/删除回归 3 passed；Lab 恢复/缓存/快照 11 passed；V2 收藏迁移/留存 4 passed。上述测试组有交集，不相加为一个总数。变更 Python 文件 `compileall` 与 `git diff --check` 通过；有既存 FastAPI/Starlette lifespan 弃用告警。
- 此局部验证不是完整 V1/V2 套件、不是浏览器验证，也不证明生产数据、RSS 或 VPS 容量。没有调用 Provider、读取/改动线上数据或部署 VPS。
- 该三项增量修复仍须基于精确最终源码/测试指纹取得新的 Source Fidelity A1 与独立 A2；此前针对 `d6d8…`、`0def…` 的审计收据均不能套用于当前树。仅当两项新审计均 PASS，才可更新 Draft PR #28；仍不合并或部署。
- 上述 `720a2de…` 候选收到 A1 隐私阻断：同一 Job 以 ownerless 输出再次保存时，唯一 output 表保留了原 owner，但 Job 内嵌输出仍可能被保存为 ownerless，历史接口直接从 Job 投影 owner。现已改为先规范化 Job 的全部 outputs，再在同一事务保存规范 Job 与 output 行；新增同一 Job owner 41→ownerless 重存后，owner 41 与管理员各见一条私有项目、用户 77 看不到的真实 API 回归。
- 此修正后的当前候选 Python 源码/测试指纹为 `754f1b10222c2c3e0161d699005b91ac31728cd0ae387f7059bc5e97f3a51fba`，覆盖相对 `origin/main` 的 39 个变更或新增 Python 文件。算法为按 UTF-8 相对路径字节序排序，每项拼接路径、NUL、文件原始字节 SHA-256 的小写十六进制、NUL，再对总字节计算 SHA-256；本文件和 `PROGRESS.md` 不参与。任何 `.py` 编辑都会使指纹失效。
- 当前追加验证：same-Job ownerless 重存及相邻 owner 冲突 API 回归 4 passed；V1 删除/收藏/SQLite 容量与迁移组 11 passed；Lab 恢复/缓存/快照组 11 passed。定向组有交集，不相加为整仓通过。针对当前 `754f1b…` 的新 A1/A2 仍待完成；此前所有指纹收据均不适用。只有双审对同一指纹 PASS 才可更新 Draft PR #28；不合并、不部署。
- 针对 `754f1b…` 的 A2 又复现同一 Job owner 保护中的并发 TOCTOU：两个 `save_job` 事务都在首次写入前读取 owner，旧 ownerless 快照可先读取旧值，待私有 owner 写入提交后再覆盖 owner。现已在 `save_job` 读取与规范化前显式执行 `BEGIN IMMEDIATE`，将 owner 读取、规范 Job/output 写入与幂等索引写入串行化；新增确定性双线程屏障回归，验证旧快照持有写锁时私有更新不能越过，最终两份记录均保留 owner 41。
- 该并发修正后的当前候选 Python 指纹为 `0e0325479954b7c30eea5c81c5856da82fa2af5b86b67db569a15a974cd4a37f`，39 个变更/新增 Python 路径，算法与上条相同。最终局部验证：V1 删除/收藏/SQLite 容量/收藏迁移组 11 passed；V1 历史 owner API 6 passed；Lab 恢复/缓存/快照 11 passed；V2 收藏迁移/留存/SQLite 容量 7 passed。并发 ownerless 旧快照回归另连续运行 5 次，均通过。分组有交集；未运行完整 V1 smoke、浏览器、真实 Provider、生产数据或 VPS。compileall 与 `git diff --check` 通过。此前针对 `754f1b…` 的 A1/A2 均已被本修正作废；必须针对 `0e0325…` 重新取得 A1/A2 双 PASS，之后才可更新 Draft PR #28；不合并、不部署。

#### 历史审计记录：第二轮复审发现与收尾修正（后续被本节顶部的 754f/0e0325 候选记录更新）

对 `c1740a…` 的 A2 复审另外发现两个相邻边界。第一，同一 output ID 可出现在多个历史来源或 Job 输出中；若 ownerless 副本在私有副本后被单独投影，列表可能按旧版公共记录规则对其他账号可见，repository 的唯一 output 记录也可能被 ownerless 写入覆盖。现在请求临时 SQLite 表先按 output ID 合并候选，再按 owner 过滤：有效 owner 优先于 ownerless；两个不同的显式 owner 冲突时，该 ID 在本次历史投影中 fail closed。`MemoryRepository.save_job` 保留已确认 owner 的唯一 output 映射，并拒绝把该 ID 改派给另一个显式 owner。回归覆盖两种写入顺序、直接下载拒绝非 owner、owner 冲突投影拒绝，以及管理员看到唯一的规范记录。

第二，V1/V2 `BoundedSQLiteCalls` 的 Future 如果在 worker 取队列前被 asyncio waiter 取消，ThreadPoolExecutor 的 work item 仍留在内部队列，但 Future 会立即标记完成并触发 capacity callback。两处现在都通过 `asyncio.shield` 将 waiter 取消与底层 Future 解耦；名额保留至实际工作完成。使用可控延迟 executor 连续尝试 1,000 次超额提交，取消后实体等待队列仍保持两个，队列完成后容量恢复。该保护仅改变 awaiter 对已准入操作的取消传播，不放大 executor worker 数。

本轮最终局部验证：V1 持久化/历史/收藏/SQLite 容量/删除 20 passed；V1 历史权限与重复 owner API 回归 5 passed；Lab 恢复/缓存/快照 11 passed；V2 收藏迁移/留存/SQLite 取消容量 7 passed。组间结果不相加为完整仓库套件。FastAPI/Starlette 生命周期弃用告警仍存在。未运行完整 V1 API smoke、浏览器、真实 Provider 或 VPS 性能/RSS 验收。

当时针对 `c1740a…` 的 A1 PASS 与 A2 FAIL 均已过期；`720a2de…` 的审计状态也由后续顶部记录更新。以上仅保留历史审计经过，不代表当前审计状态。旧进程易失数据导出/对账及 VPS 运行验收仍是后续独立条件。

#### 当前审计收据与 PR 放行

- 最终审查代码/测试指纹：`0e0325479954b7c30eea5c81c5856da82fa2af5b86b67db569a15a974cd4a37f`，39 个 Python 源码/测试路径；HEAD `58333063b5b7521518c95de834d70e861a584339`，目标分支 `codex/durable-bounded-retention`，审查基线 `origin/main=3915b24d0cdab6cc626ad5a7d07c0839e5239064`。
- Source Fidelity A1：PASS，独立复算指纹；确认同 Job ownerless 顺序及并发重存保护、所有者投影/解析、删除及 SQLite cancellation 测试与文档范围一致。
- 独立 A2：PASS，独立复算相同指纹；检查 `BEGIN IMMEDIATE` owner 串行化及相邻权限、收藏、Lab checkpoint、V1 删除、V1/V2 SQLite cancellation 路径，并以临时 SQLite 双线程复现确认最终两份记录 owner 均为 41。审计环境没有 pytest，A2 未执行测试套件；本机测试证据见上文。
- 本机局部测试：V1 删除/收藏/SQLite 容量/迁移 11 passed；V1 历史 owner API 6 passed；Lab 恢复/缓存/快照 11 passed；V2 收藏迁移/留存/SQLite 容量 7 passed；并发 stale-owner 回归连续 5 次通过。各组存在重叠，不相加为全仓套件。完整 V1 smoke、浏览器、Provider、生产数据、VPS/RSS 与性能未验证。
- 双审仅放行更新 Draft PR #28，不放行合并、部署或数据切换。旧进程易失数据导出/对账、完整 V1 smoke/浏览器覆盖和 VPS 迁移与运行验收仍是独立上线门槛。
