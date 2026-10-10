# PR #28 旧进程 RAM 状态导出与切换计划

日期：2026-10-10  
阶段：迁移可行性与协议冻结；不是生产迁移或切换许可。  
PR：#28，仍为 Draft。

## 1. 目标与当前结论

目标是把旧 V1、V2 和 Alchemy Lab 进程内权威记录安全迁入 PR #28 的 SQLite 存储，同时保持 ID、所有者、关联关系、状态、收藏和图片引用一致。

既有只读 VPS 预检确认 active release symlink 和 V1 容器源码对应旧发布 `3915b24d0cdab6cc626ad5a7d07c0839e5239064`；V1 health 返回正常。三个 V2 systemd 单元当时均 active，但其实际进程源码 SHA 未核实，不能声称每个 V2 进程都运行该提交。预检检查位置没有发现 V1/V2 `repository.sqlite3`。冻结源代码显示旧版仓库把多类权威对象保存在进程内字典，且 V2 API、资源同步 worker、任务 worker 是不同进程，各自有独立仓库副本。旧版没有完整、稳定快照导出接口；现有公开 API 也不能枚举全部对象。给当前进程增加导出代码需要更新/重启进程，而重启会销毁正在尝试导出的 RAM 状态。

因此，**当前线上 RAM-only 状态不能通过现有 API 或普通离线导入程序被证明完整导出**。本文件冻结安全协议、目标映射和验收门槛；它不声称已经生成快照、实现导入器或迁移线上数据。若不能接受可能的部分恢复，保持当前旧进程运行，不得为 PR #28 迁移而重启或部署。

## 2. 冻结基线和源映射

- 旧版参考提交：`3915b24d0cdab6cc626ad5a7d07c0839e5239064`
- 目标基线：`a582b37d32ac6317ca9b24a900c8e2de83286906`
- 源清单摘要算法：路径按 UTF-8 字节序排序；每行按 `path NUL source_git_blob NUL target_git_blob LF` 拼接后做 SHA-256。
- 源清单摘要（38 个直接来源文件）：`75dc6244e548a0b7e60ad4342eac9d61bcd2135563e0f89cf9e93946998542b8`

| 源文件 | 旧版 Git blob | 目标 Git blob | 映射类别 / 数据权威 |
|---|---|---|---|
| `src_skeleton/app/api_access.py` | `dd9900c42a86d91fcd81ea5c0497f533a42944a9` | `dd9900c42a86d91fcd81ea5c0497f533a42944a9` | `PLATFORM_SHELL`；V1 API key 是独立持久库，不进入 RAM 快照 |
| `src_skeleton/app/config.py` | `e327d8d26e0b4068fa853366dd41b390b3888ca6` | `e327d8d26e0b4068fa853366dd41b390b3888ca6` | `PLATFORM_SHELL`；V1 路径、usage JSONL 等独立文件来源 |
| `src_skeleton/app/main.py` | `c190ff437f53e31863333848eb7c2bf767ac3032` | `f0b2e9562fca4250046e2f1c05bbd11381dfbc3d` | `PLATFORM_SHELL`；路由可见范围和副作用边界 |
| `src_skeleton/app/repositories/memory.py` | `7f669bed354a3bdd061d3f369615a3c1baf18551` | `7c64a60f521a5a30d17def3452dff946469019f4` | `DIRECT_REUSE`；V1 记录身份和关联语义 |
| `src_skeleton/app/schemas.py` | `585a128b2f54f0482399daf7cd14ea285d0b517d` | `55847a0fe177bfaca6ebb3a976b9a3dae0a128b0` | `DIRECT_REUSE`；V1 记录字段与验证 |
| `src_skeleton/app/services/api_keys.py` | `89f4e0a3f847295438c45e2562efbc34feb4c41d` | `89f4e0a3f847295438c45e2562efbc34feb4c41d` | `PLATFORM_SHELL`；证明 API key 独立持久化实现，密钥不进入迁移 bundle |
| `src_skeleton/app/services/veyra_usage.py` | `942c08b6083baafa6809fe2d368a9586bac70cef` | `942c08b6083baafa6809fe2d368a9586bac70cef` | `PLATFORM_SHELL`；V1 usage JSONL 读写实现 |
| `src_skeleton/app/services/alchemy_lab.py` | `5254f0e03fe407d9d2a6b4ea7db7e5e2d4110c21` | `de31e51cc8019e53043c88c07dde0f35a0444b4d` | `DIRECT_REUSE`；Lab session / variant / favorite 语义 |
| `src_skeleton/app/services/alchemy_lab_uploads.py` | `5c05cddccc5801a1a36e840cc14687db4126a0b7` | `5c05cddccc5801a1a36e840cc14687db4126a0b7` | `PLATFORM_SHELL`；Lab 上传资产文件/manifest 写入实现 |
| `src_skeleton/app/services/favorites.py` | `febcf1f481e6feaaa5c71804826bd264ecf22520` | `346906f72590f7690524a9266cbbfb4165260e6b` | `THIN_ADAPTER`；文件收藏到 SQLite 的既有迁移边界 |
| `src_skeleton/app/services/session_service.py` | `af9baa3e57de1635d4d4134826129d6716d3e0d1` | `2d5a8bc60570949c87bbf48bb03b1f5353fb0417` | `DIRECT_REUSE`；旧 Session 创建没有 owner 赋值 |
| `src_skeleton/app/storage/local.py` | `f4470a6dbba12cef6586d7075d584653c42c7098` | `aa57c169788935280f1899f1edfac25e33b227f8` | `DIRECT_REUSE`；媒体文件与文件型历史来源 |
| `custom_media_agent_2_0/app/config.py` | `c571b5084ab10245402d99e67bae6a0ab73b87d3` | `c571b5084ab10245402d99e67bae6a0ab73b87d3` | `DIRECT_REUSE`；V2 数据根配置 |
| `custom_media_agent_2_0/app/main.py` | `4c7d0a00665cea66b651bc892ac684941fe6a6f3` | `18680401fb96c9eea0ee21b31c351ff927f6f332` | `PLATFORM_SHELL`；V2 路由枚举与公开投影 |
| `custom_media_agent_2_0/app/repositories/memory.py` | `6bb600b30098237b7b7c231bf283422ba0a0d59f` | `189521be3c933a46517b6b77798c125ffeccbd65` | `DIRECT_REUSE`；V2 仓库命名空间与关联语义 |
| `custom_media_agent_2_0/app/schemas.py` | `26abf7596c37c78636ad0e8d907716425b66e175` | `26abf7596c37c78636ad0e8d907716425b66e175` | `DIRECT_REUSE`；V2 记录字段与验证 |
| `custom_media_agent_2_0/app/services/bootstrap.py` | `e1d3bd1ba851b2ae0391847f5c34cbbba2a6f1b9` | `e1d3bd1ba851b2ae0391847f5c34cbbba2a6f1b9` | `DIRECT_REUSE`；V2 case index/bootstrap 的独立持久来源 |
| `custom_media_agent_2_0/app/services/case_index_store.py` | `74f7db118b47c3982a1a68ac64d5d6e89e918914` | `74f7db118b47c3982a1a68ac64d5d6e89e918914` | `PLATFORM_SHELL`；V2 case index 的文件写入实现 |
| `custom_media_agent_2_0/app/services/case_assets.py` | `1c363be051bfffa62fc6c62325391121d98238b2` | `1c363be051bfffa62fc6c62325391121d98238b2` | `PLATFORM_SHELL`；V2 remote snapshot 读取和 case thumbnail 派生缓存 |
| `custom_media_agent_2_0/app/services/github_archive.py` | `33a10065ae8f9c6d6514a90a4a14da1de0f8567d` | `33a10065ae8f9c6d6514a90a4a14da1de0f8567d` | `PLATFORM_SHELL`；V2 remote snapshot 下载/写入实现 |
| `custom_media_agent_2_0/app/services/runtime_model_settings.py` | `06a92205d798f68c408c399476a85f7b3506055d` | `06a92205d798f68c408c399476a85f7b3506055d` | `PLATFORM_SHELL`；V2 runtime model settings JSON 持久化和启动加载 |
| `custom_media_agent_2_0/app/services/favorites.py` | `1b75c9edf1f370dfe2d8af0db34a121c807c809d` | `0b1b28c1bd92420117f9adea9023ab238b04be9e` | `THIN_ADAPTER`；V2 文件收藏到 SQLite 的既有迁移边界 |
| `custom_media_agent_2_0/app/services/image_history.py` | `d6ec4e5f558a07456ff92deb57ceecaebb20aa2f` | `abdd2e2fb719d477d882d5784aa5a325a158d035` | `DIRECT_REUSE`；V2 JSONL 历史投影 |
| `custom_media_agent_2_0/app/services/output_storage.py` | `116a9363429b5c849ff7ab249dfc4f4bace8e560` | `116a9363429b5c849ff7ab249dfc4f4bace8e560` | `PLATFORM_SHELL`；V2 原图、history thumbnail/preview 文件写入 |
| `custom_media_agent_2_0/app/services/uploaded_assets.py` | `7f731275535e6e544b1670cc49f8493dcd597657` | `7f731275535e6e544b1670cc49f8493dcd597657` | `PLATFORM_SHELL`；V2 上传文件及关联持久记录写入 |
| `custom_media_agent_2_0/app/services/safety.py` | `810c567503b45935d4cc3d1f34fae841d0769227` | `810c567503b45935d4cc3d1f34fae841d0769227` | `DIRECT_REUSE`；V2 safety decision 持久化调用 |
| `custom_media_agent_2_0/app/services/queue_worker.py` | `24b6a271823cca2a1776e7f184f5ba3bb2dfd7be` | `24b6a271823cca2a1776e7f184f5ba3bb2dfd7be` | `DIRECT_REUSE`；任务 worker 对 V2 仓库的写入路径 |
| `custom_media_agent_2_0/app/services/resource_sync.py` | `30fa9be04e43c2c3b56dd1fa06512c072df158ff` | `30fa9be04e43c2c3b56dd1fa06512c072df158ff` | `DIRECT_REUSE`；资源同步 worker 对 V2 仓库的写入路径 |
| `custom_media_agent_2_0/app/workers/resource_sync_worker.py` | `c52b93b82abc8dd0603522a5a67388e7a29b9787` | `c52b93b82abc8dd0603522a5a67388e7a29b9787` | `PLATFORM_SHELL`；实际同步 worker 入口与初始化路径 |
| `custom_media_agent_2_0/app/workers/task_queue_worker.py` | `c4582a8b8fe2c5fab012a2fc45da7e4ae823e7a3` | `c4582a8b8fe2c5fab012a2fc45da7e4ae823e7a3` | `PLATFORM_SHELL`；V2 task worker 进程入口 |
| `custom_media_agent_2_0/app/agents/runtime.py` | `29114b3641958bf74eacdf55cdf218986deeef8c` | `29114b3641958bf74eacdf55cdf218986deeef8c` | `DIRECT_REUSE`；任务 worker 使用的创意运行时与记录写入调用 |
| `custom_media_agent_2_0/app/services/generation.py` | `8cdb994ec7f25be1ec560d993d4cfd3056b97cb3` | `8cdb994ec7f25be1ec560d993d4cfd3056b97cb3` | `DIRECT_REUSE`；V2 generation 写入调用链 |
| `custom_media_agent_2_0/app/services/veyra_billing_settings.py` | `b508f8216a4c83d9efb3851c0734e05f872a74a8` | `b508f8216a4c83d9efb3851c0734e05f872a74a8` | `PLATFORM_SHELL`；V2 billing rules 的独立 JSON 持久化实现 |
| `custom_media_agent_2_0/app/services/veyra_usage.py` | `b8e6e10102a809b8b4ba22760f3ca608266e1be6` | `b8e6e10102a809b8b4ba22760f3ca608266e1be6` | `PLATFORM_SHELL`；V2 usage JSONL 读写实现 |
| `custom_media_agent_2_0/app/services/claude_orchestrator.py` | `c7eaf398d9eae95f97e16b35435d67067536e412` | `b2ad712ae5a882cc1b23cd157ae91b2530da7a89` | `PLATFORM_SHELL`；V2 checkpoint/workspace 路径；旧版 JSON cache 与目标版新增 SQLite decision cache 的差异 |
| `custom_media_agent_2_0/deploy/systemd/alchemy-v2-api.service` | `24c09cde1d69dc43470dac5dd09a85b28c6cac5f` | `24c09cde1d69dc43470dac5dd09a85b28c6cac5f` | `PLATFORM_SHELL`；V2 API 独立进程启动配置 |
| `custom_media_agent_2_0/deploy/systemd/alchemy-v2-sync-worker.service` | `ef0c7dc77bca0fab1b4e8a4ff3dd340088d185d4` | `ef0c7dc77bca0fab1b4e8a4ff3dd340088d185d4` | `PLATFORM_SHELL`；资源同步 worker 独立进程启动配置 |
| `custom_media_agent_2_0/deploy/systemd/alchemy-v2-worker.service` | `744fd43f6b4258b15ab4187e23206558d9b9a321` | `744fd43f6b4258b15ab4187e23206558d9b9a321` | `PLATFORM_SHELL`；任务 worker 独立进程启动配置 |

## 3. 权威数据与目标映射

| 旧权威来源 | 目标 PR #28 存储 | 迁移时必须保留 |
|---|---|---|
| V1 `MemoryRepository.sessions` | V1 `v1_records` namespace `sessions` | 保留 session ID、项目、标题、模式、创建时间；旧 `Session` 没有 owner 字段，导入必须保留为 ownerless/unverified。只有单独的权威映射证据可补 owner；不得从图片历史、public/legacy-public 规则或事件内容推断。 |
| V1 `assets` | `v1_records/assets` | asset ID、owner、状态、上传/派生文件引用及元数据 |
| V1 `jobs` + 嵌入的 outputs | `v1_records/jobs`，并同步规范 `outputs` | 完整 Job 状态、原始 ID、session、owner、幂等键、嵌入输出；与规范输出副本一致 |
| V1 `outputs`、`idempotency_index` | `v1_records/outputs`、`v1_records/idempotency` | ID 唯一性、owner 与 Job 关联；不得让旧全局幂等键跨 session 授权 |
| V1 `events_by_session` | `v1_events` | 每个 session 内原始顺序与事件 payload；旧事件无独立 owner，沿用 ownerless session 的受限访问策略，不得从图片 owner 推断会话/事件权限 |
| V2 `InMemoryV2Repository` 全部九个映射 | V2 `v2_records` 对应同名 namespace | `providers`、`sync_runs`、`prompt_cases`、`creative_runs`、`image_jobs`、`outputs`、`uploaded_assets`、`feedback_events`、`safety_decisions` 的完整记录和关联 |
| Lab `lab_store.sessions` | V1 DB 的 `lab_sessions` namespace | session owner、请求、variants、progress/status、favorites、references 与上传文件引用 |

V1/V2 收藏 JSON、图片历史清单/JSONL、上传/输出图片文件、V2 task queue DB 是独立持久来源，不属于 RAM snapshot 的替代物。它们需作为独立输入或只读引用参加核对；不能把 API 投影重新写成权威 Job/session，也不能把 V2 task queue DB 当作 V2 repository DB。图片内容不进入 SQLite；只核对相对路径、存在性、大小和 SHA-256。

当前资料清单还包括以下非 RAM 数据，处理时不得与 repository snapshot 混为一谈：

| 持久来源 | 权威性与处理策略 |
|---|---|
| V1 API access-key SQLite | 独立认证数据；不进入普通快照或测试夹具。新环境通过受控凭据迁移/重新签发恢复，验证方式只记录计数和脱敏指纹。 |
| V1 `.env` / runtime settings | `persist_runtime_settings_to_env` 会写运行配置，文件可能含 provider secrets。配置值与凭据分开盘点；非秘密运行参数按键核对并安全重放，secret 通过既有 secret 管理单独配置，禁止复制进报告或 RAM bundle。 |
| V1/V2 usage JSONL、favorites JSON、image-history JSONL、Lab upload manifests | 各自的持久来源；先全文件预检，再在隔离环境核对计数/引用。不得让 lazy importer 静默跳过坏行或提前写完成标记。 |
| V2 `veyra_billing_settings.json` | 独立业务配置，含 V1/V2 billing rule；在目标启用 billing 前需受控保留并对账，不能只依赖默认值或旧 `.env` 推断。 |
| V2 `runtime_model_settings.json` | API 启动会加载、管理路由会更新；属于有效运行配置。切换前按 schema 预检并安全重放/迁移，启用生成前逐 provider/model 对账。 |
| V2 case index / provider seed | 与 repository PromptCase 数据交叉核对；确认内容可由冻结 seed/上游重新构建后，可作为派生数据重建，否则保留源文件并校验摘要。 |
| V2 task-queue SQLite | 与 V2 repository DB 分开。队列条目、claim 和运行态按独立 schema/策略对账，不伪装成 repository namespace；未批准 active task 处置前不导入并恢复执行。 |
| V2 remote snapshots | 外部同步快照/缓存来源；先盘点 manifest、来源版本和引用，再决定保留或重新下载。未验证前保留原件，不将其当作 RAM 仓库的替代快照。 |
| V1/V2 原始上传、输出图片与 Lab 文件 | 媒体源数据；不写进 SQLite。保持原数据根或独立安全复制，并核对规范路径、存在性、大小与 SHA-256。 |
| V2 case/history thumbnails | 派生缩略图；仅在来源 case/image 校验完整且重建流程通过后，允许排除并重建。 |
| V2 Claude orchestrator workspace/checkpoint 和 cache | workspace 可能含 prompt、检查点或敏感上下文；不作为可重放业务记录导入。隔离保留原件，按活动 checkpoint 清点并等待处置。冻结旧版将配置路径 `claude_orchestrator_cache.json` 作为 JSON cache 读写；它可重建，但因可能含敏感上下文，先加密留档并清点活动依赖，获批后才能淘汰。目标版另新增 `claude_orchestrator_cache.sqlite3` decision cache；该 target-only cache 在 staging/生产新目标均从空库启动，不将旧 JSON cache 转换成其权威记录。 |

以上策略来自冻结源码配置和写入点，不证明 VPS 每个文件实际存在或与默认路径一致。目标 V1 `output_delete_claims` 是删除过程的短期并发 claim，不存在旧版对应项；新 staging DB 初始化为空，不从旧 Job/历史推导 claim。

## 3.1 V2 按进程划分的仓库写入范围

| 冻结进程 | 已确认写入范围 | 直接实现依据 |
|---|---|---|
| V2 API | 请求路由可写入九个 repository namespace；另有持久 history、上传、billing 和 task-queue 路径，分别按上表处理。 | `custom_media_agent_2_0/app/main.py`、`app/repositories/memory.py` 及相应 service。 |
| V2 resource-sync worker | `providers`、`sync_runs`、`prompt_cases`；会更新 case index 文件，并可预热缩略图缓存。 | `app/workers/resource_sync_worker.py`、`app/services/resource_sync.py`、`app/services/case_index_store.py`。 |
| V2 task worker | `creative_runs`、`image_jobs`、`outputs`、`safety_decisions`；依具体生成路径更新关联记录。 | `app/workers/task_queue_worker.py`、`app/services/queue_worker.py`、`app/agents/runtime.py`、`app/services/generation.py`、`app/services/safety.py`。 |

该表是冻结源代码中的可能写入边界，不是 VPS 运行态的进程清单或进程 SHA 证明。Exporter 开发时还需逐条追踪 API route 到 repository method，并列出各 namespace/key 的唯一合并规则；如果实机发现额外 worker/写入路径，manifest 必须扩展后再冻结。

## 4. 现有 API 为什么不能构成完整快照

以下判断只针对冻结源提交，不代表线上曾尝试拉取或读出用户记录：

- V1 `/v1/sessions` 是创建路由；events 和 Job 读取要求已知 session/job ID；`/v1/image/history` 是分页图片投影，不枚举所有 sessions、assets、jobs、events，也不保证保留仓库原始记录。
- V2 `/api/v2/image/history` 是分页输出投影；`/api/v2/image/jobs/{job_id}` 和 `/api/v2/creative/runs/{run_id}` 要求已知 ID。没有完整枚举全部 repository namespaces 的接口。
- Lab `/api/lab/history` 将 limit 截至 200，返回历史投影；session detail 要求已知 session ID，没有所有 Lab sessions 的完整枚举路由。
- 私有 owner、失败/运行态、幂等索引、完整对话事件、上传记录或重复规范副本可能未出现在这些投影中。拼接分页响应不能证明缺失数据为零。

因此现有列表/详情 API 返回的是局部对象或投影；部分详情路由要求调用方已知 ID，但并非所有 API 都要求已知 ID。从现有 API 抓取只能标为“可见记录部分恢复”，永远不能标为完整迁移快照。

V2 的 `InMemoryV2Repository` 是进程内单例，不是跨进程共享内存。旧 VPS 上 API、资源同步 worker、任务 worker 各自运行独立进程，worker 代码也会写仓库。因此未来 source exporter 必须覆盖三个实际运行进程/服务，不能只导出 API 进程。进程 SHA 尚未从 VPS 预检验证，开始快照前必须逐进程确认 release、代码指纹和数据根。跨进程 snapshot 必须有共同维护 epoch/写栅栏；同一 namespace/key 的多份副本只有在规范 payload 与 owner 完全一致时才可折叠，任何冲突或缺少进程快照均 fail closed。单进程内存导出不构成完整 V2 snapshot。

## 5. 后续可信快照协议（尚未实现）

只有在源进程仍带有可读取权威 map 的版本中预先安装、审计并演练以下 exporter，才可从旧运行态构造完整快照。它不能被热加到当前 `3915b24d` 进程；为安装它而重启当前进程会令来源消失。

1. 对 V1 API、V2 API、V2 resource-sync worker、V2 task worker 和 Lab 写入建立可观测的全域维护/写入栅栏；拒绝新的写入与后台 generation handoff，并等待已准入写入到达终态。V2 三个独立进程必须回报同一 snapshot epoch 和确切运行代码指纹；导出期间保持该 epoch。若无法协调全域屏障或任一进程缺席/不匹配，则中止，不导出“最佳努力”快照。
2. 在旧进程内按固定 namespace 顺序逐条读取；JSON 编码器流式输出，不构造全库副本。导出记录带 namespace、稳定 key、原始序号（事件）及经 schema 校验的 payload。输出到受限权限的本地文件，执行完成后关闭并 fsync。
3. 清单必须有格式版本、source release SHA、每个进程的进程身份/单元名/代码指纹、snapshot epoch、开始/结束时间、各 namespace 数量/字节数/sha256、媒体清单摘要、完整完成标记。任何序列化失败、重复 key、跨进程 payload/owner 冲突、超时、维护屏障丢失都使 bundle 不完整且不可导入。
4. 快照包含提示词和私人会话资料，应加密、限制读取权限和短期保留；报告/日志只保留计数、ID hash、状态分布及错误类别，不输出 prompt、事件 payload、凭据或图片内容。

该 exporter 必须是只读的：不清理历史、不修正 owner、不恢复或重新排队运行态 Job、不触发 provider。活动 Job/Lab session 的导入状态策略尚未获用户/产品明确批准；默认 dry-run 只报告其原始状态并阻断可写导入，不自动重放任务。

## 6. 隔离 dry-run / reconciliation 验收门

未来 importer 只能消费完整、校验通过的 snapshot bundle，并写入新建的 staging SQLite 文件，不连接生产路径。第一阶段 dry-run 默认不写 staging；后续隔离导入也必须使用全新临时目标并可删除重建。

必需检查：

- 精确验证源 release、格式/schema 版本、完整标记、namespace 集合、条目数、字节数与每个流 SHA-256；流式读取并限制最大单条记录体积，超限明确失败，不截断或跳过。
- 使用目标 Pydantic schema 验证所有记录；禁止隐式字段丢弃、owner 修复、ID 重写和“坏记录跳过”。未知字段/版本按不兼容失败处理。
- 对每个 namespace 比较源/目标计数、ID 集合摘要、状态及 owner 分布；比较 Job.outputs 与规范 outputs、session/job/output/asset/run/reference/favorite/event 链接，显式报告孤儿、重复 ID 和 owner 冲突。V1 ownerless sessions/events 必须保持 ownerless/unverified，不作为导入失败，但报告受限访问记录数；不得自动猜测 owner。
- 在目标 app/bootstrap 触发任何 history lazy import 之前，对源 JSONL/manifest 做完整语法和完整性预检；坏行不得跳过，也不得留下 `jsonl_imported`/`owner_evidence_backfilled` 完成标记。导入后显式核对 `v1_history_records` 与 `v1_history_owner_evidence` 的计数、ID/owner/conflict 摘要和所有源 history 行。目标表不完整或完成标记已写而校验不一致则阻断，不以再次启动自动补救。
- 将目标专属 `output_delete_claims` 初始计数验证为 0；它不是旧数据实体，不从其他记录合成。
- 图片/上传文件不搬入数据库；对每个文件引用核对规范化路径边界、存在性、大小及内容摘要。脱离允许存储根、缺失或摘要不同均阻断 cutover。
- 原始运行态 queued/running 保持为未决项；dry-run 不调用 Provider，不把状态悄悄转为成功/失败，不触发启动恢复。必须单列并等待切换政策。
- 输出只生成脱敏报告和 staging DB 摘要；不将 prompts、私有事件、API keys 或图片字节写入普通日志。

## 7. 切换、回滚与停止条件

通过 dry-run 不等于切换通过。正式切换还需维护窗口和全写屏障：最后一次完整快照、隔离导入、逐域对账、备份 staging DB/旁路文件、验证健康检查，然后只在零新写入期间切换服务指向。切换后开放新写入前保存回滚点。

旧 RAM-only 服务一旦停止，未导出的记录不可由旧版本恢复。新 SQLite 已接受写入后，简单回滚旧版本会丢失切换后的新增/更新；除非有经验证的反向增量导出或正向修复方案，否则回滚目标必须是继续使用持久化版本并前向恢复，而非切回旧内存仓库。

任何以下情况均停止：快照不完整；源进程/代码版本未逐个核实；V2 三进程快照缺失或 epoch 不一致；跨进程同 key payload/owner 冲突；源版本不符；活动写入未静止；schema/JSONL 校验失败；目标 history/owner-evidence 表或迁移完成标记与源不一致；计数/ID/owner/引用不一致；媒体文件缺失/越界/摘要不符；运行态任务没有获批处置；磁盘或 staging 容量不足；或 rollback 只能依赖已经消失的 RAM state。

## 8. 当前阶段完成标准与下一阶段入口

当前阶段只完成事实核验、映射冻结和切换协议，不实现导出 API/脚本、不构造生产快照、不写生产 SQLite、不重启 VPS。当前阶段可通过的标准是：Source Fidelity A2 和独立 Audit A2 均对本文件、源清单摘要和映射矩阵给出同版本 PASS；文档链接、命名空间映射、已有 VPS 证据措辞准确。

完成文档审计后仍有一个**外部恢复能力阻断**：当前运行中的旧进程没有完整导出入口。若必须保留 RAM-only 记录，保持运行并评估可否在不重启该进程的条件下取得可信快照；不可行时，需要用户明确选择“保持旧服务/接受明确列出的部分恢复/放弃无法导出的 RAM-only 记录”中的业务处置。未获该决定前，不开发会暗示当前实例可安全 cutover 的脚本，也不合并/部署 PR #28。

