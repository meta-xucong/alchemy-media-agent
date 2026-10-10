# PR #28 旧进程 RAM 状态导出与切换计划

日期：2026-10-10  
阶段：迁移可行性与协议冻结；不是生产迁移或切换许可。  
PR：#28，仍为 Draft。

## 1. 目标与当前结论

目标是把旧 V1、V2 和 Alchemy Lab 进程内权威记录安全迁入 PR #28 的 SQLite 存储，同时保持 ID、所有者、关联关系、状态、收藏和图片引用一致。

当前 VPS 运行旧发布 `3915b24d0cdab6cc626ad5a7d07c0839e5239064`。既有只读预检没有在检查位置发现 V1/V2 `repository.sqlite3`，旧版仓库代码把多类权威对象保存在进程内字典。旧版没有完整、稳定快照导出接口；现有公开 API 也不能枚举全部对象。给该进程增加导出代码需要更新/重启进程，而重启会销毁正在尝试导出的 RAM 状态。

因此，**当前线上 RAM-only 状态不能通过现有 API 或普通离线导入程序被证明完整导出**。本文件冻结安全协议、目标映射和验收门槛；它不声称已经生成快照、实现导入器或迁移线上数据。若不能接受可能的部分恢复，保持当前旧进程运行，不得为 PR #28 迁移而重启或部署。

## 2. 冻结基线和源映射

- 旧版参考提交：`3915b24d0cdab6cc626ad5a7d07c0839e5239064`
- 目标基线：`a582b37d32ac6317ca9b24a900c8e2de83286906`
- 源清单摘要算法：路径按 UTF-8 字节序排序；每行按 `path NUL source_git_blob NUL target_git_blob LF` 拼接后做 SHA-256。
- 源清单摘要：`f8c288af008997371827805c58ea3ed42b63f0065beb37c644d1c841ab50ae37`

| 源文件 | 旧版 Git blob | 目标 Git blob | 映射类别 / 数据权威 |
|---|---|---|---|
| `src_skeleton/app/main.py` | `c190ff437f53e31863333848eb7c2bf767ac3032` | `f0b2e9562fca4250046e2f1c05bbd11381dfbc3d` | `PLATFORM_SHELL`；路由可见范围和副作用边界 |
| `src_skeleton/app/repositories/memory.py` | `7f669bed354a3bdd061d3f369615a3c1baf18551` | `7c64a60f521a5a30d17def3452dff946469019f4` | `DIRECT_REUSE`；V1 记录身份和关联语义 |
| `src_skeleton/app/schemas.py` | `585a128b2f54f0482399daf7cd14ea285d0b517d` | `55847a0fe177bfaca6ebb3a976b9a3dae0a128b0` | `DIRECT_REUSE`；V1 记录字段与验证 |
| `src_skeleton/app/services/alchemy_lab.py` | `5254f0e03fe407d9d2a6b4ea7db7e5e2d4110c21` | `de31e51cc8019e53043c88c07dde0f35a0444b4d` | `DIRECT_REUSE`；Lab session / variant / favorite 语义 |
| `src_skeleton/app/services/favorites.py` | `febcf1f481e6feaaa5c71804826bd264ecf22520` | `346906f72590f7690524a9266cbbfb4165260e6b` | `THIN_ADAPTER`；文件收藏到 SQLite 的既有迁移边界 |
| `src_skeleton/app/storage/local.py` | `f4470a6dbba12cef6586d7075d584653c42c7098` | `aa57c169788935280f1899f1edfac25e33b227f8` | `DIRECT_REUSE`；媒体文件与文件型历史来源 |
| `custom_media_agent_2_0/app/config.py` | `c571b5084ab10245402d99e67bae6a0ab73b87d3` | `c571b5084ab10245402d99e67bae6a0ab73b87d3` | `DIRECT_REUSE`；V2 数据根配置 |
| `custom_media_agent_2_0/app/main.py` | `4c7d0a00665cea66b651bc892ac684941fe6a6f3` | `18680401fb96c9eea0ee21b31c351ff927f6f332` | `PLATFORM_SHELL`；V2 路由枚举与公开投影 |
| `custom_media_agent_2_0/app/repositories/memory.py` | `6bb600b30098237b7b7c231bf283422ba0a0d59f` | `189521be3c933a46517b6b77798c125ffeccbd65` | `DIRECT_REUSE`；V2 仓库命名空间与关联语义 |
| `custom_media_agent_2_0/app/schemas.py` | `26abf7596c37c78636ad0e8d907716425b66e175` | `26abf7596c37c78636ad0e8d907716425b66e175` | `DIRECT_REUSE`；V2 记录字段与验证 |
| `custom_media_agent_2_0/app/services/favorites.py` | `1b75c9edf1f370dfe2d8af0db34a121c807c809d` | `0b1b28c1bd92420117f9adea9023ab238b04be9e` | `THIN_ADAPTER`；V2 文件收藏到 SQLite 的既有迁移边界 |
| `custom_media_agent_2_0/app/services/image_history.py` | `d6ec4e5f558a07456ff92deb57ceecaebb20aa2f` | `abdd2e2fb719d477d882d5784aa5a325a158d035` | `DIRECT_REUSE`；V2 JSONL 历史投影 |

## 3. 权威数据与目标映射

| 旧权威来源 | 目标 PR #28 存储 | 迁移时必须保留 |
|---|---|---|
| V1 `MemoryRepository.sessions` | V1 `v1_records` namespace `sessions` | session ID、项目、创建时间、可信 owner；禁止由图片公开兼容规则推导 session owner |
| V1 `assets` | `v1_records/assets` | asset ID、owner、状态、上传/派生文件引用及元数据 |
| V1 `jobs` + 嵌入的 outputs | `v1_records/jobs`，并同步规范 `outputs` | 完整 Job 状态、原始 ID、session、owner、幂等键、嵌入输出；与规范输出副本一致 |
| V1 `outputs`、`idempotency_index` | `v1_records/outputs`、`v1_records/idempotency` | ID 唯一性、owner 与 Job 关联；不得让旧全局幂等键跨 session 授权 |
| V1 `events_by_session` | `v1_events` | 每个 session 内原始顺序与事件 payload；不得从图片 owner 推断会话事件权限 |
| V2 `InMemoryV2Repository` 全部九个映射 | V2 `v2_records` 对应同名 namespace | `providers`、`sync_runs`、`prompt_cases`、`creative_runs`、`image_jobs`、`outputs`、`uploaded_assets`、`feedback_events`、`safety_decisions` 的完整记录和关联 |
| Lab `lab_store.sessions` | V1 DB 的 `lab_sessions` namespace | session owner、请求、variants、progress/status、favorites、references 与上传文件引用 |

V1/V2 收藏 JSON、图片历史清单/JSONL、上传/输出图片文件、V2 task queue DB 是独立持久来源，不属于 RAM snapshot 的替代物。它们需作为独立输入或只读引用参加核对；不能把 API 投影重新写成权威 Job/session，也不能把 V2 task queue DB 当作 V2 repository DB。图片内容不进入 SQLite；只核对相对路径、存在性、大小和 SHA-256。

## 4. 现有 API 为什么不能构成完整快照

以下判断只针对冻结源提交，不代表线上曾尝试拉取或读出用户记录：

- V1 `/v1/sessions` 是创建路由；events 和 Job 读取都要求已知 session/job ID；`/v1/image/history` 是分页图片投影，不枚举 sessions、assets、jobs、所有 events，也不保证保留仓库原始记录。
- V2 `/api/v2/image/history` 是分页输出投影；`/api/v2/image/jobs/{job_id}` 和 `/api/v2/creative/runs/{run_id}` 要求已知 ID。没有完整枚举全部 repository namespaces 的接口。
- Lab `/api/lab/history` 将 limit 截至 200，返回历史投影；session detail 要求已知 session ID，没有所有 Lab sessions 的完整枚举路由。
- 私有 owner、失败/运行态、幂等索引、完整对话事件、上传记录或重复规范副本可能未出现在这些投影中。拼接分页响应不能证明缺失数据为零。

因此从现有 API 抓取只能标为“可见记录部分恢复”，永远不能标为完整迁移快照。

## 5. 后续可信快照协议（尚未实现）

只有在源进程仍带有可读取权威 map 的版本中预先安装、审计并演练以下 exporter，才可从旧运行态构造完整快照。它不能被热加到当前 `3915b24d` 进程；为安装它而重启当前进程会令来源消失。

1. 进入可观测的维护/写入栅栏：拒绝新的 V1/V2/Lab 写入和后台 generation handoff，等待已准入写入到达终态；导出期间保持同一快照 epoch。若不能获得全域屏障则中止，不导出“最佳努力”快照。
2. 在旧进程内按固定 namespace 顺序逐条读取；JSON 编码器流式输出，不构造全库副本。导出记录带 namespace、稳定 key、原始序号（事件）及经 schema 校验的 payload。输出到受限权限的本地文件，执行完成后关闭并 fsync。
3. 清单必须有格式版本、source release SHA、snapshot epoch、开始/结束时间、各 namespace 数量/字节数/sha256、媒体清单摘要、完整完成标记。任何序列化失败、重复 key、owner 冲突、超时、维护屏障丢失都使 bundle 不完整且不可导入。
4. 快照包含提示词和私人会话资料，应加密、限制读取权限和短期保留；报告/日志只保留计数、ID hash、状态分布及错误类别，不输出 prompt、事件 payload、凭据或图片内容。

该 exporter 必须是只读的：不清理历史、不修正 owner、不恢复或重新排队运行态 Job、不触发 provider。活动 Job/Lab session 的导入状态策略尚未获用户/产品明确批准；默认 dry-run 只报告其原始状态并阻断可写导入，不自动重放任务。

## 6. 隔离 dry-run / reconciliation 验收门

未来 importer 只能消费完整、校验通过的 snapshot bundle，并写入新建的 staging SQLite 文件，不连接生产路径。第一阶段 dry-run 默认不写 staging；后续隔离导入也必须使用全新临时目标并可删除重建。

必需检查：

- 精确验证源 release、格式/schema 版本、完整标记、namespace 集合、条目数、字节数与每个流 SHA-256；流式读取并限制最大单条记录体积，超限明确失败，不截断或跳过。
- 使用目标 Pydantic schema 验证所有记录；禁止隐式字段丢弃、owner 修复、ID 重写和“坏记录跳过”。未知字段/版本按不兼容失败处理。
- 对每个 namespace 比较源/目标计数、ID 集合摘要、状态及 owner 分布；比较 Job.outputs 与规范 outputs、session/job/output/asset/run/reference/favorite/event 链接，显式报告孤儿、重复 ID 和 owner 冲突。
- 图片/上传文件不搬入数据库；对每个文件引用核对规范化路径边界、存在性、大小及内容摘要。脱离允许存储根、缺失或摘要不同均阻断 cutover。
- 原始运行态 queued/running 保持为未决项；dry-run 不调用 Provider，不把状态悄悄转为成功/失败，不触发启动恢复。必须单列并等待切换政策。
- 输出只生成脱敏报告和 staging DB 摘要；不将 prompts、私有事件、API keys 或图片字节写入普通日志。

## 7. 切换、回滚与停止条件

通过 dry-run 不等于切换通过。正式切换还需维护窗口和全写屏障：最后一次完整快照、隔离导入、逐域对账、备份 staging DB/旁路文件、验证健康检查，然后只在零新写入期间切换服务指向。切换后开放新写入前保存回滚点。

旧 RAM-only 服务一旦停止，未导出的记录不可由旧版本恢复。新 SQLite 已接受写入后，简单回滚旧版本会丢失切换后的新增/更新；除非有经验证的反向增量导出或正向修复方案，否则回滚目标必须是继续使用持久化版本并前向恢复，而非切回旧内存仓库。

任何以下情况均停止：快照不完整；源版本不符；活动写入未静止；schema 校验失败；计数/ID/owner/引用不一致；媒体文件缺失/越界/摘要不符；运行态任务没有获批处置；磁盘或 staging 容量不足；或 rollback 只能依赖已经消失的 RAM state。

## 8. 当前阶段完成标准与下一阶段入口

当前阶段只完成事实核验、映射冻结和切换协议，不实现导出 API/脚本、不构造生产快照、不写生产 SQLite、不重启 VPS。当前阶段可通过的标准是：Source Fidelity A2 和独立 Audit A2 均对本文件、源清单摘要和映射矩阵给出同版本 PASS；文档链接、命名空间映射、已有 VPS 证据措辞准确。

完成文档审计后仍有一个**外部恢复能力阻断**：当前运行中的旧进程没有完整导出入口。若必须保留 RAM-only 记录，保持运行并评估可否在不重启该进程的条件下取得可信快照；不可行时，需要用户明确选择“保持旧服务/接受明确列出的部分恢复/放弃无法导出的 RAM-only 记录”中的业务处置。未获该决定前，不开发会暗示当前实例可安全 cutover 的脚本，也不合并/部署 PR #28。

