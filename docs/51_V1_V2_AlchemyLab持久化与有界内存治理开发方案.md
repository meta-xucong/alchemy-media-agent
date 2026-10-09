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

### 增量复审收尾（2026-10-09，基线 9c325b21）

#### 修正模型

增量复审指出三项归属/删除问题和一个 JSON 数字边界问题。三项权限问题的共同根因是不同入口把 outputs 行、Job 内嵌副本、history 索引与文件是否存在当成互不相关的 owner 来源；某个副本缺失或清理中断时，ownerless 不得自动解释成公共。修正后的统一优先级为：规范化 outputs 行中的明确 owner 优先；没有该证据时按 output ID 精确查 history 索引中的明确 owner（不受列表页窗口限制，且不要求图片文件存在）；两者都没有明确 owner 时才回退检查旧 Job-only 记录，同一回退层出现冲突则拒绝授权。历史列表投影采用相同优先级，确保列表、下载和删除使用相同 owner 判定。常规规范化私有图片可以直接由 outputs 行完成鉴权，不再逐请求扫描所有 Job/历史行。删除完成前保留 repository/Job 或 history 的授权锚点，使 history-only 旧记录在文件已删除后仍可由原 owner 重试。`preserve_output_owner` 在单一事务中同步 outputs 行及 ownerless 的 Job 内嵌副本。

收藏解析器只在数字 token 可能跨过当前读取块时补读并重新解析；不恢复每项解析后无条件预读 64 KiB 的行为。V1、V2 使用相同边界规则。

#### 新增回归与验证边界

- 历史 API：较新缺图 manifest 仍有明确私有 owner 时，其他账户的历史列表不返回该 ID，下载返回 403；真实文件恢复候选仍携带 owner。另覆盖 10,001 条历史中排在列表窗口之外的私有记录仍按 ID 正确拒绝跨账号下载、规范 outputs owner 优先于 stale Job 副本、Job-only 同层 owner 冲突时历史和下载均 fail-closed，以及 history owner 覆盖旧 Job 投影时列表与下载一致。
- 删除重试：故障注入使最后的收藏清理遇 SQLite busy；文件已消失后 history-only owner 仍可识别，其他用户不能读取，原 owner 重试完成幂等清理。repository output 存在的中断用例也断言 Job 内嵌 owner 已同步。
- V1/V2 收藏解析：数字 token 从 64 KiB 分块边界中间开始，必须作为完整合法 JSON 数字解析；此前多条小记录缓冲上界测试继续保留。
- 本机执行：V1 删除/收藏/迁移/SQLite 容量/历史边界/Lab 相关套件 37 passed；V2 收藏迁移/留存/SQLite 容量及相关套件 15 passed；V1 公开 API owner/删除定向用例 7 passed；V2 数字边界专项 2 passed。分组有交集，不合并成一个总数。完整 V1 `test_api_smoke.py` 曾启动但未完成，不能记为通过；有 FastAPI/Starlette 生命周期弃用警告。
- Python 编译和 `git diff --check` 通过。未运行真实 Provider、浏览器、生产数据迁移或 VPS/RSS/性能验收。
- 当前候选指纹为 `30193274431c04f0c339d9c12dd904c0cc39a8618a09378acf8dde81648281d2`，覆盖相对 `origin/main` 的 39 个变更/新增 Python 文件；排序与散列算法和本节前述规则一致，文档与 `PROGRESS.md` 不计入。此前所有 fingerprint 审计回执对本次源码/测试修改均失效。
- 旧 Job-only fallback 仍需扫描 Job 记录以发现没有规范 output/history 锚点的历史归属冲突；常规规范 outputs owner 和精确 history owner 路径不做全表扫描。该 fallback 的实际延迟未做生产基准，PR #28 在独立审计完成前保持 Draft，不合并、不部署。

#### 10,001 条历史权限边界修正（2026-10-09）

前一候选 `30193274431c04f0c339d9c12dd904c0cc39a8618a09378acf8dde81648281d2` 被独立 A2 复审拒绝：owner resolver 仍用 10,000 条倒序列表查找历史 owner，造成第 10,001 条私有记录可能降级为 public；同时每个图片鉴权都扫描全部 Job 和最多 10,000 条 history。该候选不得作为可接受版本。

修正为：有明确 owner 的规范 outputs 行直接完成鉴权；否则通过 `v1_history_records.output_id` 主键精确查找 history manifest，含缺图记录且不受列表窗口限制；只有两者都没有明确 owner 时，才扫描旧 Job-only 记录以保持冲突 fail-closed。历史列表的临时 owner 证据表增加来源优先级：规范 outputs owner 优先于 history owner，history owner 优先于 Job 副本；同一回退层的不同显式 owner 仍 fail-closed。列表、下载和删除共用该 authority 顺序。这个修正未引入常驻 owner 缓存或新数据库。

新增回归将私有目标放在 10,001 条索引记录的最旧端，并通过真实下载 API 验证非 owner 得到 403、owner 成功；另验证规范 outputs owner 覆盖 stale Job、history owner 覆盖 stale Job 时列表/下载一致、Job-only 冲突仍拒绝，以及删除中断后非 owner 不能删除或读取。

本轮定向验证：V1 persistence/history/favorites/SQLite/Lab 37 passed；V1 owner/history/download API 8 passed；V2 favorites/retention/SQLite 15 passed。组间重叠，不相加。编译和 `git diff --check` 通过。完整 V1 smoke、浏览器、Provider、生产数据和 VPS 未验证。旧 Job-only 无规范 output/history 行仍需全 Job 回退扫描；正常规范 owner 或精确 history owner 不扫描整批记录。

修正后的 Python 源码/测试 fingerprint：`d98c5a4e660cf9863726662fa1462a2d32d1d6576ae1437a2a38c5e051003299`，39 个相对 `origin/main` 的变更/新增 Python 文件。文档与 `PROGRESS.md` 排除。该版本需重新取得 Source Fidelity A2 和独立 Audit A2；此前收据全部过期。审计双通过后只更新 Draft PR #28，不合并、不部署。

#### 历史列表投影的增量修正

在审计派发前的本机重跑中发现两个未覆盖边界：其一，下载鉴权虽已按 output ID 精确查询 history，但 filesystem 恢复进入历史列表时仍只依赖当前 10,000 条列表窗口，可能让更旧的私有 manifest 失去 owner 约束；其二，同源重复 Job 中 ownerless 副本先到时，会在归属纠正后留下该副本的 `job_id`，而不是与明确 owner 相符的投影。

历史列表的候选暂存现在在请求期按 output ID 解析规范 outputs owner，其缺失时精确读取 history 索引（包含文件不存在的行），再使用 Job-only 副本作为低优先级兼容证据。下载与列表采用同一 owner 来源顺序。临时去重记录还保留候选原 owner 是否匹配最终权威 owner；同一来源优先级下，匹配权威 owner 的候选优先，避免 ownerless 副本覆盖有效 Job 投影。该匹配标记仅存在于请求期 SQLite 临时表，不进入持久记录或 API 响应。

10,001 条历史回归现在验证最旧端私有记录在文件恢复列表和下载端均不会暴露给其他账户，且 owner 能看到被恢复的图片。重复 Job 顺序用例验证返回的 owner 与 `job_id` 投影均稳定。最终增量测试证据为：V1 persistence/history/favorites/SQLite/Lab 37 passed；V1 owner/history/download API 12 passed；V2 favorites/migration/SQLite 14 passed；变更 Python compileall 与 `git diff --check` 通过。完整 V1 smoke、浏览器、Provider、生产数据、VPS/RSS 与性能仍未验收。

由于上述 Python 变更，前一节 `d98c5a4e` fingerprint 及所有此前审计收据均失效。当前版本需重新冻结完整 PR Python 改动集 fingerprint，并通过独立 Source Fidelity A2 与普通 Audit A2。审计未完成前 PR #28 仍保持 Draft，不合并、不部署。

#### 同级历史归属冲突保护

针对同一 output ID 的历史清单记录，索引只保留最新展示行并不足以证明 owner 唯一。独立 A2 复现了“旧记录 owner=41、图片文件存在；新记录 owner=77、图片文件缺失”的跨账号下载：最新索引行覆盖旧 owner 后，按 output ID 回退找到旧文件并把文件交给 user 77。该版本因此被拒绝。

现在单独持久化 `v1_history_owner_evidence(output_id, owner_id, owner_conflict)`。每次历史记录 upsert 都累计明确 owner 证据；若同一历史来源出现不同 owner，冲突位只能被设为 true，不会被较新的行覆盖。旧安装在首次使用时从现存 append-only JSONL 逐行回填该索引，并以持久迁移标记避免每次扫描；不把全部 owner 放进 Python 内存。按 ID 的 history 查询同时返回内部冲突证据。输出列表的历史投影和下载鉴权遇到该同级冲突均 fail-closed；明确的规范 outputs owner 仍按更高 authority 决定可见性。成功删除 history 行时，同一数据库事务也删除对应 owner evidence；前序清理失败时 owner/conflict 锚点继续保留，供幂等重试与安全拒绝使用。

新增隔离 API 回归模拟升级前已有最新索引但没有 owner-evidence 表：回填扫描发现 JSONL 中 owner 41/77 冲突，普通账户双方均不能在列表看到图片或下载文件，且响应不包含旧文件内容。此项是新的持久化索引迁移，部署前仍应在临时副本/备份环境确认现存 `outputs.jsonl` 可读及一次性扫描耗时；不得用线上真实库做探索性测试。

本候选本地定向验证：V1 persistence/history/favorites/SQLite/Lab 37 passed；V1 owner/history/download API 13 passed；V2 favorites/migration/SQLite 14 passed；变更 Python compileall 和 `git diff --check` 通过。全量 V1 smoke、浏览器、生产旧库回填、VPS、RSS/性能仍未验证。前一个 `636def67` 指纹的 Source Fidelity A2 曾 PASS，但普通 A2 随后发现上述 P1；两份收据都不能放行当前修改。新的完整 Python fingerprint 必须同时取得 Source Fidelity A2 与普通 Audit A2 PASS，PR #28 仍保持 Draft。

当前候选 fingerprint：`45754d8d23c8682a7281a8c0c185fd808d54d2803b79a972a0d69a7ab76360ae`，39 个相对 `origin/main` 的变更/新增 Python 路径；路径 UTF-8 排序，按“相对路径 + NUL + 每文件小写 SHA256 十六进制 + NUL”计算，文档与 `PROGRESS.md` 排除。只有此版本的 Source Fidelity A2 与普通 Audit A2 双 PASS 才能作为更新 Draft PR #28 的放行依据。

#### 删除重试及历史查询成本收尾（2026-10-09）

对 `9c325b21` 的增量复审还发现：JSONL 已替换但 SQLite 删除遇 busy 时，重试虽然删除了剩余索引，返回值却只看 JSONL 删除数，导致清理完成后仍报告 404；另有按图片逐项开数据库连接导致的请求成本放大。当前 `delete_history_record` 以 JSONL 行数和 SQLite 受影响行数的较大值报告删除结果。失败注入测试验证首次请求 503、非 owner 重试 403、原 owner 重试成功。owner evidence 与 history 行仍在同一成功事务删除，失败期间保留权限依据。

历史列表现在在一次请求中复用 repository SQLite 连接，精确 output/history owner 读取使用调用方连接；解析后的 authority 存入请求临时 SQLite，避免为每个图片重复开库，也不引入进程级持久缓存。24 项历史候选的连接计数回归验证该边界。V1/V2 收藏解析器对跨 64 KiB 边界的 JSON 数字 token 仅在可能未完整时补读，再完整解析。

最新相关回归结果：V1 persistence/history/favorites/SQLite/Lab 38 passed；V1 history owner/API 14 passed；V2 favorites/migration/SQLite 14 passed。分组有重叠。变更 Python compileall、`git diff --check` 通过。完整 V1 smoke、浏览器、真实 Provider、旧生产库回填耗时、VPS RSS/CPU/P95 未验证。此前 `45754d…` Audit A2 的删除重试问题已修，但所有旧审计收据均因源码/测试变化失效；需冻结新 fingerprint 并通过新一轮 Source Fidelity A2 与独立 Audit A2 后，才可更新 Draft PR #28。仍不合并、不部署。

#### 跨 Job 重复输出的删除闭环（2026-10-09）

对 `13fda1a0…` 的 Source Fidelity A2 又发现旧库可能在第二个 Job.outputs 中保留相同 output ID 的 ownerless 副本，并在该 Job 目录保留同 ID 图片。此前 `preserve_output_owner` 和最终删除只处理规范 output.job_id；规范 output/history 清理完成后，旧副本会成为 ownerless 唯一证据，下载文件回退可找到另一 Job 文件。该候选被拒绝。

删除闭环现按 output ID 工作：清理文件时遍历生成目录，删除该 ID 所有受支持图片格式的副本；`preserve_output_owner` 在事务中遍历所有持久 Job，对仍 ownerless 的同 ID 投影补上经授权确认的 owner；最终 `delete_output_with_event` 在同一事务删除规范 output 并从全部 Job 投影移除同 ID 副本。文件删除中途失败时 history/repository 锚点尚未清理；最后数据库事务失败时，先前保存的 owner 仍留在规范 output 与所有 Job 副本中，原 owner 可重试，其他账户不会因缺少文件而获得公共回退。

新增旧库回归直接写入 `save_job` 规范化逻辑之前可能留下的 ownerless duplicate，确认规范目录和重复目录文件都删除、重复 Job.outputs 清空，且删除后下载不能返回图片；现有中途事务故障测试扩展为跨 Job duplicate，验证失败状态给副本补归属，原用户重试最终清理重复文件与记录。新用例在修复前复现为失败（重复图片残留），修复后通过。

最新局部结果：V1 持久化/历史/收藏/SQLite/Lab 39 passed；V1 历史 owner/API 14 passed；V2 收藏/迁移/SQLite 8 passed。分组不相加。完整浏览器、全量 V1 smoke、真实 Provider、旧生产库迁移耗时、VPS 资源仍未验证。上一指纹 `13fda1a0…` 的 A2 双审均失败/失效；该跨 Job 修复后所有代码审计收据需重新获取，PR #28 仍保持 Draft。

当前候选 Python 源码/测试指纹为 `796eefbfe3b160d3dcb43486f9f87af2cf2e604203a9d7db31777c0abb2f2bdb`，覆盖相对 `origin/main` 的 39 个变更/新增 Python 文件；使用 UTF-8 相对路径排序，并按“相对路径 + NUL + 每文件小写 SHA256(raw bytes) 十六进制 + NUL”计算。文档与 `PROGRESS.md` 不在该指纹内，但属于 Source Fidelity 审阅范围。只有对此精确候选的 Source Fidelity A2 和独立 Audit A2 双 PASS 才允许更新 Draft PR #28；不授权合并或部署。

#### 仅 history/Job 记录的迁移前删除边界

后续 A2 又验证了没有规范 `outputs` 行的迁移前形态：owner=41 的 history 记录关联到 ownerless Job.outputs 和本地图片。删除 bundle 原先只在规范 output 存在时传播 owner，且最终 repository 删除仅在 output 行存在时调用，导致文件与 history 已清除但 Job 投影残留。现已将授权 owner 传播与 Job 投影清理扩展为按 output ID 执行，不依赖规范 output 行存在；`preserve_output_owner` 在缺少规范行时仍给旧 Job 副本补归属，最终删除事务即使没有规范 output 行也会从全部 Job 中移除该 ID。配套回归在修复前因残留 Job.outputs 失败，修复后通过。

更新后的局部验证：V1 persistence/history/favorites/SQLite/Lab 40 passed；V1 history owner/API 14 passed；V2 favorites/migration/SQLite 8 passed。分组重叠。`796eefbf…` 已因上述源码/测试变化失效，需要再冻结新 Python 指纹并重新通过 Source Fidelity A2、独立 Audit A2；完整 V1 smoke、浏览器、真实 Provider、生产库迁移与 VPS 性能仍未验证。PR #28 保持 Draft，不合并、不部署。

该候选的 Python 源码/测试指纹为 `6d550e063430d3de58609443209c7820466709a873461c01348ae031647c9dc5`，覆盖 39 个相对 `origin/main` 变更/新增的 Python 文件；按路径 UTF-8 排序并使用“相对路径 + NUL + 每文件小写 SHA256(raw bytes) 十六进制 + NUL”计算，文档和 `PROGRESS.md` 不纳入散列。该文档和测试证据作为 Source Fidelity 审阅材料。此候选只有重新取得 Source Fidelity A2 与独立 Audit A2 双 PASS 后，才可更新 Draft PR #28。

#### 最终清理顺序修正（2026-10-09）

Source Fidelity A2 对 `6d550e0…` 继续发现：删除 history 行和 owner evidence 发生在 repository/Job 清理之前；若后者失败，旧 Job 副本上的另一 owner 可能暂时成为权限依据。最终顺序现调整为：移除所有文件副本及缩略图/预览，清理收藏，再在 SQLite 事务中删除规范 output 与全部 Job 投影，最后删除 history 行及 owner evidence。这样 repository 清理失败时 history owner 仍是权威；而 history 删除遇锁失败时，已清理的 repository 不会留下 Job 副本，持久 history owner 仍可供原用户重试。

新增故障交错使用 history-only 旧记录、Job owner=77 与 history owner=41，注入 repository 清理失败，验证 history owner 仍解析为 41、错误账户不能接管删除，原 owner 可重试完成。已有 JSONL 替换后 SQLite busy 用例现在证明 repository/Job 已清理但 history owner 锚仍在，原 owner 重试成功。历史 output 存在/缺失、跨 Job duplicate 文件与 Job 副本两种删除用例均通过。

当前最终局部结果：V1 persistence/history/favorites/SQLite/Lab 41 passed；V1 history owner/API 14 passed；V2 favorites/migration/SQLite 8 passed；变更 Python compileall 与 `git diff --check` 通过。FastAPI/Starlette 生命周期弃用告警仍存在；完整 V1 smoke、浏览器、真实 Provider、旧库生产迁移、VPS RSS/CPU/P95 未验证。此前 `8590db1c` 前候选的审计收据已失效，须对下列新 fingerprint 重新完成 Source Fidelity A2 和独立 Audit A2。

当前 Python 源码/测试指纹：`8590db1c057978f8b4698c189cb4b56d181c442dd76fb85c662721bd20e0b32f`，39 个相对 `origin/main` 的变更/新增 Python 文件，路径 UTF-8 排序，散列格式为“相对路径 + NUL + 每文件小写 SHA256(raw bytes) 十六进制 + NUL”；文档/PROGRESS 不计入指纹。双审仅放行更新 Draft PR #28，不授权合并或部署。

最终只读审计收据：Source Fidelity A2 PASS 与独立 Audit A2 PASS，均复算同一 `8590db1c…` 指纹；未修改源码。A2 额外执行 V1 history/delete/favorites/migration/SQLite/Lab 33 passed、V1 owner/history API 14 passed、V2 favorites/migration/SQLite 14 passed；本机单独执行的相邻组为 41/14/8 passed，组间重叠，各自报告、不相加。A2 标记路由溯源 `ROUTE_UNVERIFIED`。双审允许更新 Draft PR #28；不构成完整 V1 smoke、浏览器、Provider、生产旧库迁移或 VPS RSS/CPU/P95 验收，也不授权合并/部署。

#### 私有规范输出的删除事件目标再次收紧（2026-10-10）

对前一候选 `0a9e14e…` 的独立 Audit A2 发现，规范 output 明确属于用户 41、关联 Job 副本 ownerless 时，仓库仍会把该 Job session 当作可投递删除事件的目标。即使另一个 session 有明确 owner=41 的重复 Job 副本，ownerless 关联 Job 也不能证明其 session 属于 41；session 事件读取端仅凭 session ID 取数，因此不得向该 session 发送私有 output/job ID。

修正规则：私有规范 output 的事件只能投递到其规范关联 Job，且该 Job 内同 ID 的每个副本都必须显式 owner=规范 owner；缺少副本、ownerless 或 owner 不同均抑制事件，不转投重复 Job。输出删除和权威清理继续完成，事件仅用于辅助刷新，客户端可重新读取授权列表。公有 ownerless 与 history/Job-only 私有事件沿用已定义的显式授权证据规则。新增交错回归覆盖规范 owner=41、关联 Job ownerless、另一 session 存在 owner=41 重复副本；旧实现失败，新实现删除成功且两边都无事件。另验证明确匹配规范 owner 的关联 Job 仍收到事件。

前一候选的 Audit A2 为 FAIL，Source Fidelity A2 PASS；两者均不适用于本修订。当前修订已完成局部定向回归，需重新冻结 Python 源码/测试指纹并取得同一指纹上的独立 Audit A2 与 Source Fidelity A2；未通过前不更新 Draft PR #28，不合并、不部署。宽范围 V2 provider-seed-sync 测试失败信号仍作为单独未解释限制记录。

#### 删除事件 session 归属收敛（2026-10-09）

对 `6dc1542c` 的三项删除/历史缺口完成修正后，独立 A2 又指出：迁移前数据可能把同一 output ID 复制到不同 session。删除旧 Job 副本时，不能把迭代遇到的第一份 Job 当作事件接收 session；否则 ownerless 或 stale-owner 副本所在 session 会收到私有 output/job ID。事件读取接口当前只校验登录态，不验证 session 归属，因此删除路径必须自己 fail-closed。

最终规则：存在明确 owner 的规范 output 时，沿用规范 output 的 Job/session；否则，私有输出仅在找到明确 owner 与已授权 owner 相同的 Job 副本时向该 Job session 写事件。ownerless/stale/conflicting Job 不能单独证明私有事件的目标 session。对于无法证明目标 session 的迁移前私有记录，删除和持久清理仍正常完成，但不向任意 session 广播私有 ID；客户端应重新读取权威列表。Repository 在 SQLite 删除事务内再次校验目标 Job 确实含该 output ID 且副本 owner 匹配，再原子追加事件。删除权限锚点仍按规范 output、history owner/conflict、Job owner 的优先级留存；不再为了发事件或排序而把已授权 owner 复制到无关 ownerless Job/session。

新增回归覆盖：history owner=41 指向 ownerless Job A，另有 stale owner=77 的 Job C 与显式 owner=41 的 Job B；canonical output 存在且 ownerless 时，事件仅进入 B 的 session，A/C 不收到；Job-only 旧记录同样优先通知显式 owner Job；无明确 owner session 的私有记录不发事件；规范 output/history/Job 部分清理失败仍可由原 owner 重试。原有跨 session 列表归属、SQLite busy 重试、无关/共享 Job 目录写入竞态回归继续通过。

当前候选本机验证：V1 history/delete/favorites/migration/SQLite/SSE/Lab 及 session owner API 组 39 passed；V2 favorites/migration/retention/SQLite 组 15 passed；Python compileall、`git diff --check` 通过。分组不相加。6 个 FastAPI lifecycle 弃用警告仍在。宽泛 V2 provider-seed-sync 用例此前独立审计有 1 项未解释失败且本轮未覆盖；完整 V1 smoke、浏览器、Provider、旧生产库回填耗时及 VPS RSS/CPU/P95 仍未验证。

本候选 Python 源码/测试指纹：`4b14a4c2de06ef3e4645ff39a0dde7de71207b3e5ee5d0c9bed3cc41a250b074`，39 个相对 `origin/main` 的变更/新增 Python 路径，按 UTF-8 相对路径排序并使用“路径 + NUL + 每文件小写 SHA256(raw bytes) 十六进制 + NUL”计算；文档和 `PROGRESS.md` 不在散列内。此前 `80ba9d…`、`5e4498…`、`99eb42…` 的 A2/Source Fidelity 收据均因后续事件路由修正失效。只有对此精确候选重新取得 Source Fidelity A2 与独立 Audit A2 双 PASS，才可更新 Draft PR #28；不授权合并或部署。

#### 规范 owner 与 Job session 不一致时的事件保护（2026-10-09）

后续 A2 发现，即使规范 output 明确属于 owner 41，它关联的 Job 副本仍可能是缺失或 stale owner=77。规范 output 继续作为删除授权权威，但不能单凭其 `job_id` 把删除事件投递到未经验证的 Job session。更新后的规则是：规范 output 有明确 owner 时，只有关联 Job 仍包含该 output，且副本 owner 缺失或与规范 owner 相同，才向规范 session 追加事件；若 Job 副本缺失或明确冲突，清理仍成功，但不向该 session 发事件。不会改投另一个重复 Job 的 session，因为那不是规范输出与当前事件的关联关系。

规范 output ownerless 时，私有事件只在事务内验证到明确 matching-owner Job 后才发出；无法证明安全目的地时不发事件。Job-only / history-only 场景同样对目标 Job 输出身份和 owner 做事务内复核。该规则优先保护跨账号元数据隔离，可能让少数迁移前异常记录的客户端依赖下一次权威列表刷新。

本修正新增回归：规范 output owner=41、规范 Job 输出副本 stale owner=77，同时存在另一 Job owner=41；由 41 删除时不向 stale session 或另一非规范 session发事件。规范 ownerless + history owner=41 + ownerless/stale/matching Job 三方重复场景仍只向显式 matching-owner Job session 通知。

当前代码候选 fingerprint 为 `0a9e14e5351f7829952fd5e829a0bf3b8422e25f8cf9f4d4be5517ef47b34fad`（39 个相对 `origin/main` 的 Python 路径，计算方式同前；文档和 `PROGRESS.md` 排除）。旧 `4b14a4…` Source Fidelity/Audit 收据因本次补丁失效。V1 相关回归、V2 持久化回归及独立双审须针对新的同一指纹重新通过；仍不合并、不部署。

#### Session 归属证据与删除锚点收尾（2026-10-09）

对 `6dc1542c` 的增量审计确认了三个缺口。修正模型先统一权威规则：session 参数只决定哪些历史投影可出现在列表，不能限制 output ID 的 owner 证据范围；规范 outputs 行是最高优先级授权锚点，在整个删除成功前不得因清理顺序退位；文件系统清理只负责本次确实删除了目标文件的 Job 目录，不能顺便回收其他空目录。

实现边界：历史列表扫描全部旧 Job 副本并累计其 owner 证据，但只为请求 session 暂存候选；不增加持久缓存。删除先解析当前 owner authority：明确 owner 的规范 output 高于明确 owner/conflict 的 history evidence，后者高于 Job 副本。每次清理都要保留当前唯一或最高等级的有效归属/冲突证据直到更低层记录清除；不能把 ownerless history 行误作 owner 锚点。图片删除不移除空 Job 目录：写入端会先建目录再写文件，存储层没有与删除共享的 Job 锁，即使目录刚因删除目标图片变空，也可能正被同一 Job 的另一张图使用。

必须回归：跨 session 的 Job-only 同 ID 副本不得把 ownerless 投影作为公共历史返回；规范 owner 41 与 stale history owner 77 并存、history 清理遇 busy 后，41 可重试、77 仍拒绝；无规范 output、ownerless history manifest、owner 41 Job 副本并存且 history 清理遇 busy 时，Job owner 必须仍能重试；删除目标 A 不得删除无关的空 Job 目录，也不得删除共享目录中暂停写入 B 的目录，B 随后应能写入文件。新增探针须先在旧行为上失败，再验证一致性。V1/V2/Lab 其他持久化范围与 VPS 部署条件保持不变。

独立 A2 又发现 ownerless history manifest 被错误当作删除重试锚点：当 Job 副本是唯一显式 owner、没有规范 output/history owner 时，先删除 Job 后遇到 history SQLite busy 会使原 owner 无法重试。故本轮原 `64b201da…` fingerprint 和双审收据失效。继续实现前的修正模型是按实际 authority 而不是记录存在性选择删除顺序：若规范 output 显式携带 owner，history 先删、规范 output/Job 后删；否则若 history 显式 owner 或同级冲突存在，Job 先删、history 最后删；否则 Job 副本是 owner authority 时，history（包括 ownerless manifest）先清理，Job 最后清理。每一步出错时，至少一个保有相同 resolved owner/conflict 的源仍在。

最终本机定向验证：V1 persistence/history/favorites/migration/SQLite/SSE/delete/Lab 相关组 46 passed；V1 API history 24 passed；V2 favorites/migration/retention/SQLite 15 passed。组间有重叠，不相加。三个审计场景及同 Job 暂停写入竞态均在修复前失败、修复后通过；变更 Python `compileall` 与 `git diff --check` 通过。生命周期 deprecation warnings 保留记录。完整全量 smoke、浏览器、真实 Provider、生产数据、VPS/RSS/CPU/P95 不在本轮验证范围。

当前冻结 Python 源码/测试 fingerprint：`64b201da6b9aee752b190dcdb5c72415161555e131a57f6d9deda351479cc934`，39 个相对 `origin/main` 的变更/新增 Python 文件；路径按 Python UTF-8 字符串顺序排序，哈希格式为相对路径 + NUL + 每文件小写 SHA256(raw bytes) 十六进制 + NUL。文档与 `PROGRESS.md` 不参与指纹。该树只有在新的独立 Source Fidelity A2 与 Audit A2 均对同一指纹复核通过后，才允许更新 Draft PR #28；不授权合并或部署。

#### Job-only owner 重试锚点收尾（2026-10-09）

此边界已补回归并修正：删除前读取精确的 history owner/conflict authority；只有规范 output 明确携带 owner 时才按规范 output 优先路径清理 history，否则显式 history owner/conflict 保留到 Job 清理后，ownerless/无 history 归属时先尝试 history 清理并保留 Job 副本。`delete_output_with_event` 在没有规范 output 行时仍返回事务中移除的旧 Job 输出副本，使已经清理 Job-only 结果的幂等重试返回成功，而不是在图片/manifest 已被前次尝试清理后误报 404。故障回归覆盖 owner 41 Job 副本 + ownerless history manifest + history SQLite busy：首次 503 时 Job owner 保留，owner 77 被拒绝，owner 41 重试成功。

该修正后本机相关组：V1 persistence/history/favorites/migration/SQLite/SSE/delete/Lab 47 passed；V1 API history 24 passed；V2 favorites/migration/retention/SQLite 15 passed。组间重叠。上一独立 A2 曾在宽选集报告 V2 provider-seed 用例 1 项失败；定向 15 项持久化组未覆盖该功能，本机单测尝试超时并中断，因此它仍是未解释的宽套件信号，不能记作全绿。当前源码变化已使 `64b201da…` 双审收据失效，需要重新冻结并通过两路独立审计。完整 smoke、浏览器、真实 Provider、生产数据、VPS/RSS/CPU/P95 未验证。

#### 私有规范输出事件规则勘误（2026-10-10）

Source Fidelity A2 对 `f63f08e…` 指出，第 428 行附近历史章节仍写“副本 owner 缺失或与规范 owner 相同”即可向规范 Job session 投递删除事件。该句记录的是旧规则，现已被本文件后续章节“私有规范输出的删除事件目标再次收紧”取代，不再是当前实现或开发的依据。

唯一现行规则：规范 output 为私有时，规范关联 Job 必须包含该 output 的副本，且同 Job 内同 ID 的所有副本都必须显式携带与规范 owner 完全相同的 owner；ownerless、缺失或冲突均抑制事件，不转投重复 Job。删除和权威清理仍完成，事件只用于辅助刷新。规范 ownerless 的私有 legacy 记录，只能向事务内验证为显式匹配 owner 的 Job session 发事件；无法证明目的地时抑制事件。本节优先于第 428 行附近及更早的同主题历史描述。

该候选现已获得同指纹双审：独立 Audit A2 PASS，Source Fidelity A2 PASS，均绑定 `f63f08e3932c574acde5e77a7225e8b04487a80d351224d302e3b3559c1336ac`（39 个变更/新增 Python 文件）。Audit A2 独立复核上述 ownerless 事件边界、跨 session 历史归属、删除失败后的 owner 锚点与重试、SQLite 事务和目录竞态；审计环境缺 pytest，未独立执行测试。主控本机验证为 V1 history/delete/favorites/migration/SQLite/SSE/Lab + session-owner API 42 passed，另 V1 history API 14 passed、V2 favorites/migration/retention/SQLite 14 passed，分组有重叠；compileall、`git diff --check` 通过。路由溯源标记 `ROUTE_UNVERIFIED`。该双审只放行更新 Draft PR #28，不代表完整 V1/V2/Lab 生产验收，不授权合并或部署；此前宽范围 V2 provider-seed-sync 用例的一项失败信号仍未解释，生产旧数据迁移、浏览器、真实 Provider 和 VPS 资源验收也未完成。

#### b8bd6b6 增量审计后的收尾模型（2026-10-10）

总目标仍是 V1/V2/Alchemy Lab 的持久化与有界留存优化。当前阶段只关闭 b8bd6b6 审计提出的删除关联竞态、V1 session 事件/写入归属、V2 seed-sync 测试环境确定性；不合并、不部署、不调用真实 Provider、不操作生产数据。基线为 PR #28 分支 `codex/durable-bounded-retention` 的 `b8bd6b6ffed0de01b54d7b9970713fecc16c7e7d`；唯一 main checkout 与 `origin/main=3915b24d0cdab6cc626ad5a7d07c0839e5239064` 保持分离。既有未跟踪 `custom_media_agent_2_0/uv.lock` 和 `src_skeleton/custom_media_agent.egg-info/` 属于基线，不得纳入提交或清理。

纠正模型：

1. 删除授权、规范 output 当前关联、删除事件目标必须来自同一持久化删除 claim。claim 在任何图片/收藏/历史副作用前，以 `BEGIN IMMEDIATE` 原子校验当前规范 owner 与调用方已授权 owner，并固定当前 Job 关联；之后 `save_job` 对被 claim 的 output ID 不得重绑或重新写入。claim 同时含单次清理 attempt token 与 15 分钟 lease：同一 owner 的并发删除不能复用正在运行的 attempt；可捕获失败会释放 attempt 但保留授权锚点，便于同 owner 重试；进程崩溃遗留的 attempt 在 lease 到期后可恢复。全部清理成功后释放 claim。最终事务只允许使用 claim 中绑定的关联，不能回退到事务外旧 `event_job_id`。owner/规范关联在 claim 建立前已变化时拒绝本次旧授权请求，要求重新读取/授权。该 claim 是跨 SQLite/JSONL/文件副作用的短期并发栅栏，不把事务跨越到文件 I/O。
2. Session 是独立的隐私边界，不由图片 ownerless/public 兼容规则推导。新增 session 由服务端写入不可由请求体指定的 `veyra_user_id`；auth 开启时，普通用户只可读写明确属于本人的 session，管理员只获得读取全局 session/SSE 的权限，跨 owner 写入仍拒绝。ownerless 旧 session 没有足够证据证明完整事件流归属，普通用户按 not-found 拒绝；既有 ownerless 图片仍按原 history API 的 public 兼容规则工作。关闭 auth 的本地模式保持原行为。消息和直接 image-job 两个带 session_id 的写入口必须在副作用前应用同一 session 守卫。
3. V2 `test_provider_sync_publishes_seed_cases` 明确请求 `mode=seed`，由测试固定该用例目的，不依赖 `enable_remote_github_sync` 环境开关；不更改运行时 provider 同步策略。

边界与验收：只允许修改 V1 `Session` schema/service/repository/session 路由、V1 删除 claim 和对应定向测试、V2 该 seed-sync 测试、本文及 `PROGRESS.md`。每个新增缺陷先在基线行为上以隔离数据复现，再实现最小修正。覆盖 Job A→B 重绑发生在删除 claim 前/后的行为、同 owner 并发删除只能有一个活动 attempt、可捕获失败释放 attempt 且同 owner 可重试、进程中断后 lease 到期可恢复、删除中 SQLite busy 后原 owner 重试及其他 owner 拒绝、私有/公有/ownerless session 的 owner/admin/auth-off 读写、session owner 保存不可清除/改绑、未授权请求零事件/零 Job 副作用，以及开启 remote GitHub sync 时 seed 测试仍不访问远端。实现后须执行 V1 删除/history/session 定向组与 V2 seed-sync/相关持久化组、变更文件编译和 diff 检查；冻结精确代码指纹后取得独立 Audit A2 与 Source Fidelity A2 同指纹 PASS，再更新 Draft PR #28。完整 V1 smoke、浏览器、生产旧数据迁移、VPS RSS/CPU/P95 仍是独立后续阶段。

风险分类：D1，legacy session 能否按图片 owner 继承事件权限存在隐私语义歧义；独立 Think 已裁定不能继承，应对 auth-enabled 普通用户 fail-closed。I2，删除横跨 SQLite、JSONL、图片和收藏副作用，需要明确 claim/重试不变量。A2，涉及跨账号隐私、持久化及公开路由。路由溯源为 `ROUTE_UNVERIFIED`；Hook 状态为 `HOOK_UNVERIFIED`，均不作为代码正确性收据。

实施状态：本轮本机 V1 定向组 55 passed、V2 定向组 13 passed、V1 history API 选择 4 passed；Python compileall 与 diff 检查通过。新增“同 owner 并发删除 attempt 序列化”回归在改动前失败、改动后通过。当前 42 个 Python 源码/测试文件相对 `origin/main` 的候选 fingerprint 为 `589385966facdf2682670b7dd20ec9ccde6ed61753982eb15503fbbb747506cc`，计算格式见 `PROGRESS.md`；此提交仍需独立 Audit A2 和 Source Fidelity A2 同树复核。未完成双审前不更新 PR；双审只允许更新 Draft PR，不授权合并或 VPS 部署。旧 session 的生产归属迁移、浏览器、真实 Provider、生产数据和 VPS 资源验收均未执行。
