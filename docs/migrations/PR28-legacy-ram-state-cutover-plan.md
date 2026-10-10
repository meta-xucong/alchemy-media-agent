# PR #28 旧进程 RAM 状态导出与切换计划

日期：2026-10-10
阶段：迁移可行性与协议冻结；不是生产迁移或切换许可。
PR：#28，仍为 Draft。

首次导入标记与旧库对账准备的实现边界见[开发计划](PR28-import-marker-reconciliation-development-plan.md)；该计划与本切换协议互补，不授权修改生产数据。

## 1. 目标与当前结论

目标是把旧 V1、V2 和 Alchemy Lab 进程内权威记录安全迁入 PR #28 的 SQLite 存储，同时保持 ID、所有者、关联关系、状态、收藏和图片引用一致。

既有只读 VPS 预检确认 active release symlink 和 V1 容器源码对应旧发布 `3915b24d0cdab6cc626ad5a7d07c0839e5239064`；V1 health 返回正常。三个 V2 systemd 单元当时均 active，但其实际进程源码 SHA 未核实，不能声称每个 V2 进程都运行该提交。预检检查位置没有发现 V1/V2 `repository.sqlite3`。冻结源代码显示旧版仓库把多类权威对象保存在进程内字典，且 V2 API、资源同步 worker、任务 worker 是不同进程，各自有独立仓库副本。旧版没有完整、稳定快照导出接口；现有公开 API 也不能枚举全部对象。给当前进程增加导出代码需要更新/重启进程，而重启会销毁正在尝试导出的 RAM 状态。

因此，**当前线上 RAM-only 状态不能通过现有 API 或普通离线导入程序被证明完整导出**。本文件冻结安全协议、目标映射和验收门槛；它不声称已经生成快照、实现导入器或迁移线上数据。若不能接受可能的部分恢复，保持当前旧进程运行，不得为 PR #28 迁移而重启或部署。

## 2. 冻结基线和源映射

- 旧版参考提交：`3915b24d0cdab6cc626ad5a7d07c0839e5239064`
- 原始目标基线：`a582b37d32ac6317ca9b24a900c8e2de83286906`；以下 38 文件矩阵只冻结这一历史目标，不代表修正后的最终候选。
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
| `src_skeleton/app/services/favorites.py` | `febcf1f481e6feaaa5c71804826bd264ecf22520` | `346906f72590f7690524a9266cbbfb4165260e6b` | `e7c52cd1c3ae20dd600bc8f7ec66d6fbb1218718`；文件收藏到 SQLite 的既有迁移边界 |
| `src_skeleton/app/services/session_service.py` | `af9baa3e57de1635d4d4134826129d6716d3e0d1` | `2d5a8bc60570949c87bbf48bb03b1f5353fb0417` | `DIRECT_REUSE`；旧 Session 创建没有 owner 赋值 |
| `src_skeleton/app/storage/local.py` | `f4470a6dbba12cef6586d7075d584653c42c7098` | `aa57c169788935280f1899f1edfac25e33b227f8` | `7b5154a27251902d8078f2dc58e4c311614fc232`；媒体文件与文件型历史来源 |
| `custom_media_agent_2_0/app/config.py` | `c571b5084ab10245402d99e67bae6a0ab73b87d3` | `c571b5084ab10245402d99e67bae6a0ab73b87d3` | `DIRECT_REUSE`；V2 数据根配置 |
| `custom_media_agent_2_0/app/main.py` | `4c7d0a00665cea66b651bc892ac684941fe6a6f3` | `18680401fb96c9eea0ee21b31c351ff927f6f332` | `PLATFORM_SHELL`；V2 路由枚举与公开投影 |
| `custom_media_agent_2_0/app/repositories/memory.py` | `6bb600b30098237b7b7c231bf283422ba0a0d59f` | `189521be3c933a46517b6b77798c125ffeccbd65` | `DIRECT_REUSE`；V2 仓库命名空间与关联语义 |
| `custom_media_agent_2_0/app/schemas.py` | `26abf7596c37c78636ad0e8d907716425b66e175` | `26abf7596c37c78636ad0e8d907716425b66e175` | `DIRECT_REUSE`；V2 记录字段与验证 |
| `custom_media_agent_2_0/app/services/bootstrap.py` | `e1d3bd1ba851b2ae0391847f5c34cbbba2a6f1b9` | `e1d3bd1ba851b2ae0391847f5c34cbbba2a6f1b9` | `DIRECT_REUSE`；V2 case index/bootstrap 的独立持久来源 |
| `custom_media_agent_2_0/app/services/case_index_store.py` | `74f7db118b47c3982a1a68ac64d5d6e89e918914` | `74f7db118b47c3982a1a68ac64d5d6e89e918914` | `PLATFORM_SHELL`；V2 case index 的文件写入实现 |
| `custom_media_agent_2_0/app/services/case_assets.py` | `1c363be051bfffa62fc6c62325391121d98238b2` | `1c363be051bfffa62fc6c62325391121d98238b2` | `PLATFORM_SHELL`；V2 remote snapshot 读取和 case thumbnail 派生缓存 |
| `custom_media_agent_2_0/app/services/github_archive.py` | `33a10065ae8f9c6d6514a90a4a14da1de0f8567d` | `33a10065ae8f9c6d6514a90a4a14da1de0f8567d` | `PLATFORM_SHELL`；V2 remote snapshot 下载/写入实现 |
| `custom_media_agent_2_0/app/services/runtime_model_settings.py` | `06a92205d798f68c408c399476a85f7b3506055d` | `06a92205d798f68c408c399476a85f7b3506055d` | `PLATFORM_SHELL`；V2 runtime model settings JSON 持久化和启动加载 |
| `custom_media_agent_2_0/app/services/favorites.py` | `1b75c9edf1f370dfe2d8af0db34a121c807c809d` | `0b1b28c1bd92420117f9adea9023ab238b04be9e` | `31b45823f1490f4e85f785c81a854769855e1a16`；V2 文件收藏到 SQLite 的既有迁移边界 |
| `custom_media_agent_2_0/app/services/image_history.py` | `d6ec4e5f558a07456ff92deb57ceecaebb20aa2f` | `abdd2e2fb719d477d882d5784aa5a325a158d035` | `0e46b63f938583d4b6d488e5a55dbda488655ea6`；V2 JSONL 历史投影 |
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

## 2.1 PR #27 依赖与候选版本冻结规则

原始目标 `a582b37d` 和仅修改文档的 `b72c75f8` 不包含 PR #27 `af505d08` 的 V2 queue claim fencing、generation capacity lease 和成功 checkpoint 保护。不能把已审计的旧目标矩阵当作这些保护已进入 PR #28 的证据。本轮候选集成这些必要的 V2 保护，保留 PR #28 的 SQLite repository、异步 SQLite 边界及其既有修正；依赖以最终候选源码与回归结果为准，不以 PR 编号或另一个分支的测试代替。

本轮包含范围仅为 V2 queue/capacity/provider 调度闭环及其 API、worker、repository 接口适配。PR #27 的 V1/Lab capacity guardrails 和无关的 V2 upload/history 限额保护未在本轮引入；不能把这个子集称为合并整个 PR #27，也不能声称 PR #28 替代其全部范围。其他部署依赖需另行审计和验收。

候选必须共同覆盖 queue claim/token 与 heartbeat、stale worker 拒写、generation admission/lease、provider dispatch 检查、成功 checkpoint 恢复及 API/standalone worker 入口。它们保护后续执行边界，**不提供当前旧 RAM 进程的完整 exporter，也不批准恢复活动任务**。queue DB 与 repository DB 仍是两个持久存储，不能据此宣称二者具备单一跨库原子快照。

新增列也不提供混合新旧二进制的安全性：旧 queue 的 complete/fail/retry 仍可只按 `task_id` 写入，旧 standalone 启动还会按 worker label bulk-release，因此新 token/claim generation 无法约束仍在运行的旧写入者。只有先解决当前 RAM 导出/业务处置阻断，再让所有旧 API inline worker、standalone worker 及其他 queue writer 停止写入，逐进程确认替代者使用同一已验证 fencing 协议/候选代码后，才可恢复 dispatch。不得滚动共用同一 queue DB，让旧无栅栏写入者与新候选并存；此要求不是现在重启旧进程的许可。

下面的候选补充矩阵在集成完成后按最终文件内容冻结；未列出的原始 38 文件沿用上表目标 blob。新增来源和修改来源均单列，`ABSENT` 表示对应提交中没有该文件。候选 blob 是按下述文本规范计算的 Git blob SHA-1，审计提交的 SHA 由 PR/提交记录绑定，不把尚未生成的自引用 commit SHA 写成既成事实。任一列明来源再次变更，都需更新补充矩阵并重跑源保真检查和相关回归；本轮文档修正不是生产切换验收。

源路径均相对于仓库根；V1 前缀为 `src_skeleton/`，V2 前缀为 `custom_media_agent_2_0/`。下文 V2 进程表中缩写的 `app/...` 均沿用 V2 前缀，不指 V1 的同名 package。候选清单只声明 `.py`、`.service`、`.env.example` 为文本来源：读取当前工作树文件字节，仅把 `CRLF` 替换为 `LF`，然后计算 `SHA-1(b"blob " + ASCII(规范字节长度) + NUL + 规范字节)`。这与当前 LF Git 源 blob 一致，允许 Windows 的 CRLF checkout；不删除 BOM、不转换独立 CR、不修剪空白、不改变编码或内容。检查不使用可能落后于工作树的 index，也不依赖 Git 可执行文件或历史对象；真实内容编辑仍必须失败。该规则不是任意 Git clean filter 的模拟：若新增二进制来源、`-text`、`working-tree-encoding` 或其他改变来源字节的 filter，必须重新审计并显式扩展规范，不能直接沿用此文本清单。原始 38 文件历史矩阵及其摘要保持不变。

<!-- PR28_CANDIDATE_SOURCE_MATRIX -->

- Candidate overlay: 25 files; SHA-256 `39244dd769d02a1b6d9f1a0bea31408686b7707d0671fe77611ca8e63ce7f90e`.
- Overlay digest: UTF-8 path order; `path NUL old_blob NUL original_target_blob NUL candidate_blob LF`.
- Expanded old-to-candidate manifest: 51 files; SHA-256 `c614dbedae723e7c5dbe5d2013297666dbf6c9c3dccac2b8570788608ad2f615`.
- Expanded digest uses section 2 encoding; merge the original matrix with this overlay by path, replacing target blobs and adding new paths.

| Source file | Old release blob | Original target blob | Candidate blob | Scope / authority |
|---|---|---|---|---|
| `custom_media_agent_2_0/app/agents/runtime.py` | `29114b3641958bf74eacdf55cdf218986deeef8c` | `29114b3641958bf74eacdf55cdf218986deeef8c` | `64356f788643398bf9eec5ae73f03ec07a0a583d` | V2_DEPENDENCY; claim-aware run, output and billing persistence boundaries |
| `custom_media_agent_2_0/app/config.py` | `c571b5084ab10245402d99e67bae6a0ab73b87d3` | `c571b5084ab10245402d99e67bae6a0ab73b87d3` | `028d02004231333e7ebefa217bae06405581fcf8` | V2_DEPENDENCY; queue/claim/capacity settings |
| `custom_media_agent_2_0/app/main.py` | `4c7d0a00665cea66b651bc892ac684941fe6a6f3` | `18680401fb96c9eea0ee21b31c351ff927f6f332` | `af7631d34d13f8ec83a59371cf5080cf2fee0bf5` | V2_ADAPTER; async admission, capacity errors, inline-worker identity and sanitized legacy import failures |
| `custom_media_agent_2_0/app/providers/images/claim_fenced_http.py` | `ABSENT` | `ABSENT` | `d95baf0c17e5c23669d1f02f7775a5ea3dc2f541` | V2_DEPENDENCY; shared claim check at wire-request boundary |
| `custom_media_agent_2_0/app/providers/images/doubao_image.py` | `5d21f7ae7dce64d525c54fcf9d3908ac64cef0fb` | `5d21f7ae7dce64d525c54fcf9d3908ac64cef0fb` | `605ef62d62dc77697f3389eb4f5551e1014b06ab` | V2_DEPENDENCY; fenced provider dispatch |
| `custom_media_agent_2_0/app/providers/images/gemini_image.py` | `772006ea72d10d13a812afbd87e2c1624b601901` | `772006ea72d10d13a812afbd87e2c1624b601901` | `c000b5920cfb670acdabafef4ec37b79d36564ce` | V2_DEPENDENCY; fenced provider dispatch |
| `custom_media_agent_2_0/app/providers/images/openai_gpt_image_2.py` | `5bcd48939a44402f8c72c82fc583665a373717c4` | `5bcd48939a44402f8c72c82fc583665a373717c4` | `0fc8edfa280bb07285d8ed001b06910884036f73` | V2_DEPENDENCY; fenced provider dispatch |
| `custom_media_agent_2_0/app/providers/images/response_payloads.py` | `9c93947564b2a05c3cae8057b627dd9263483c25` | `9c93947564b2a05c3cae8057b627dd9263483c25` | `8512ae8cb582f8a8512288ca8066b8bb40be6cf4` | V2_DEPENDENCY; fenced output download |
| `custom_media_agent_2_0/app/repositories/memory.py` | `6bb600b30098237b7b7c231bf283422ba0a0d59f` | `189521be3c933a46517b6b77798c125ffeccbd65` | `282c8e0b59c5287c78b96dc00ab3745d7d092939` | V2_ADAPTER; atomic conditional stale-running image-job cleanup |
| `custom_media_agent_2_0/app/repositories/sqlite_json.py` | `ABSENT` | `14eebe2baef11ca152ffc1678c97ca361d5c1f94` | `14eebe2baef11ca152ffc1678c97ca361d5c1f94` | TARGET_STORAGE; V2 case index columns, filtered reads and WAL schema |
| `custom_media_agent_2_0/app/services/asset_binding.py` | `d5668779e583bdd00283b79f281dfe854e6cba3a` | `d5668779e583bdd00283b79f281dfe854e6cba3a` | `d5668779e583bdd00283b79f281dfe854e6cba3a` | DIRECT_REUSE; task-runtime asset lookup leading to uploaded_assets hydration |
| `custom_media_agent_2_0/app/services/favorites.py` | `1b75c9edf1f370dfe2d8af0db34a121c807c809d` | `0b1b28c1bd92420117f9adea9023ab238b04be9e` | `31b45823f1490f4e85f785c81a854769855e1a16` | THIN_ADAPTER; validated atomic favorites import with repair retry |
| `custom_media_agent_2_0/app/services/generation.py` | `8cdb994ec7f25be1ec560d993d4cfd3056b97cb3` | `8cdb994ec7f25be1ec560d993d4cfd3056b97cb3` | `3fefe202af88c5e50429c19672d9700f2cc3fe7c` | V2_DEPENDENCY; claim-aware generation persistence/checkpoint boundary |
| `custom_media_agent_2_0/app/services/generation_capacity.py` | `ABSENT` | `ABSENT` | `3f4ef455560c2627496d64b72a5b13413f58f1ec` | V2_DEPENDENCY; cross-process lease, stale recovery and cancellation safety |
| `custom_media_agent_2_0/app/services/image_history.py` | `d6ec4e5f558a07456ff92deb57ceecaebb20aa2f` | `abdd2e2fb719d477d882d5784aa5a325a158d035` | `0e46b63f938583d4b6d488e5a55dbda488655ea6` | DIRECT_REUSE; V2 fail-closed JSONL history import |
| `custom_media_agent_2_0/app/services/queue_worker.py` | `24b6a271823cca2a1776e7f184f5ba3bb2dfd7be` | `24b6a271823cca2a1776e7f184f5ba3bb2dfd7be` | `f1e07daeb10b3aadd43fa8ab09e75ea6387e6d07` | V2_DEPENDENCY; heartbeat, guarded transitions and success recovery |
| `custom_media_agent_2_0/app/services/task_queue.py` | `d0cce383588e9f261745c6f7f5398982f0bac471` | `d0cce383588e9f261745c6f7f5398982f0bac471` | `8b2b81ab442478e70e875cc9c36bac0eccfd6db8` | V2_DEPENDENCY; claim protocol, checkpoint schema and bounded async admission |
| `custom_media_agent_2_0/app/workers/task_queue_worker.py` | `c4582a8b8fe2c5fab012a2fc45da7e4ae823e7a3` | `c4582a8b8fe2c5fab012a2fc45da7e4ae823e7a3` | `36336b2f43ac7325c698c29b402cd7da36bab536` | V2_DEPENDENCY; unique process identity, no old bulk release |
| `custom_media_agent_2_0/deploy/systemd/alchemy-v2.env.example` | `967bf46d7e59e938cde170b3942846c2d3c864f5` | `967bf46d7e59e938cde170b3942846c2d3c864f5` | `73718048234d7eb29c0ea630aa79f4f4dbf5ccea` | V2_CONFIGURATION; queue limit, claim timeout and generation lease example settings |
| `scripts/pr28_import_marker_inventory.py` | `ABSENT` | `ABSENT` | `3cee3bf92cf2fd434ef60082f75f13583f7f9471` | OFFLINE_DIAGNOSTIC; read-only import marker inventory |
| `src_skeleton/app/main.py` | `c190ff437f53e31863333848eb7c2bf767ac3032` | `f0b2e9562fca4250046e2f1c05bbd11381dfbc3d` | `096b8053e07011166020ba1092530fa797600f73` | PLATFORM_SHELL; sanitized fail-closed legacy import API responses |
| `src_skeleton/app/repositories/sqlite_json.py` | `ABSENT` | `4c719e7603cc3723d75ac392f8782810220bbe73` | `4c719e7603cc3723d75ac392f8782810220bbe73` | TARGET_STORAGE; V1 indexed columns, filtered reads and WAL schema |
| `src_skeleton/app/services/favorites.py` | `febcf1f481e6feaaa5c71804826bd264ecf22520` | `346906f72590f7690524a9266cbbfb4165260e6b` | `e7c52cd1c3ae20dd600bc8f7ec66d6fbb1218718` | THIN_ADAPTER; validated atomic favorites import with repair retry |
| `src_skeleton/app/services/retention_settings.py` | `1b199826c2a72577e9fea4bdfea9df2dcde89860` | `1b199826c2a72577e9fea4bdfea9df2dcde89860` | `1b199826c2a72577e9fea4bdfea9df2dcde89860` | PLATFORM_SHELL; V1 user-edited retention JSON and fallback defaults |
| `src_skeleton/app/storage/local.py` | `f4470a6dbba12cef6586d7075d584653c42c7098` | `aa57c169788935280f1899f1edfac25e33b227f8` | `7b5154a27251902d8078f2dc58e4c311614fc232` | DIRECT_REUSE; V1 fail-closed JSONL history and owner-evidence import |

<!-- /PR28_CANDIDATE_SOURCE_MATRIX -->

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
| V1 `<media_store.root>/retention_settings.json` | 用户可编辑的独立保留策略；`services/retention_settings.py` 通过管理路由读写。保留原文件、摘要及 `retention_days`、`delete_protected_data`、`updated_at`，核对有效值和 `persisted`。文件缺失/解析失败会回退 `retention_days=30`、`delete_protected_data=false`，不能把默认返回当作迁移成功。源确实不存在时也需记录缺失证据和显式接受的默认策略。此读写证据不证明存在自动删除任务，不据此声称缺文件已造成自动删除。 |
| V1/V2 usage JSONL、favorites JSON、image-history JSONL、Lab upload manifests | 各自的持久来源；先全文件预检，再在隔离环境核对计数/引用。不得让 lazy importer 静默跳过坏行或提前写完成标记。 |
| V2 `veyra_billing_settings.json` | 独立业务配置，含 V1/V2 billing rule；在目标启用 billing 前需受控保留并对账，不能只依赖默认值或旧 `.env` 推断。 |
| V2 `runtime_model_settings.json` | API 启动会加载、管理路由会更新；属于有效运行配置。切换前按 schema 预检并安全重放/迁移，启用生成前逐 provider/model 对账。 |
| V2 case index / provider seed | 与 repository PromptCase 数据交叉核对；确认内容可由冻结 seed/上游重新构建后，可作为派生数据重建，否则保留源文件并校验摘要。 |
| V2 task-queue SQLite | 与 V2 repository DB 分开。队列条目、claim 和运行态按独立 schema/策略对账，不伪装成 repository namespace；候选新增 claim token/generation、成功 checkpoint、capacity lease 等 schema 差异需逐列清点。候选 async 准入采用纯 queued-run builder → 单次 queue INSERT，准入前不写 repository；尚未消费的 run 只存在 `queued_run_json` 可能是合法状态，需核对 task/run ID、trace、created_at 和完整 snapshot，不能仅因 repository 缺少 run 就当作孤儿或补写。不能凭旧 running 状态合成有效新 claim/lease，也不让初始化/过期恢复替代获批的状态转换。未批准 active task 处置前不导入并恢复执行。 |
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
| V2 task worker | 八个 namespace：`providers`、`sync_runs`、`prompt_cases`、`creative_runs`、`image_jobs`、`outputs`、`uploaded_assets`、`safety_decisions`；九个映射中仅未找到 `feedback_events` 写入路径。启动 bootstrap/seed sync 可写前三项；生成/安全检查写中间业务记录；asset binding 从持久 asset manifest 加载时会回填 `uploaded_assets`。 | `app/workers/task_queue_worker.py` → `app/services/bootstrap.py` → `app/services/resource_sync.py`；`app/services/queue_worker.py` → `app/agents/runtime.py` → `app/services/generation.py` / `app/services/safety.py` / `app/services/asset_binding.py` → `app/services/uploaded_assets.py:get_uploaded_asset`。 |

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
3. 清单必须有格式版本、source release SHA、每个进程的进程身份/单元名/代码指纹、snapshot epoch、开始/结束时间、各 namespace 数量/字节数/sha256、媒体清单摘要、完整完成标记。事件保留 session 内原始序号；其他具有稳定排序语义的来源也保留插入顺序（包括 V1 同时间 Job），不能只按 key 重新插入。任何序列化失败、重复 key、跨进程 payload/owner 冲突、超时、维护屏障丢失都使 bundle 不完整且不可导入。
4. 快照包含提示词和私人会话资料，应加密、限制读取权限和短期保留；报告/日志只保留计数、ID hash、状态分布及错误类别，不输出 prompt、事件 payload、凭据或图片内容。

该 exporter 必须是只读的：不清理历史、不修正 owner、不恢复或重新排队运行态 Job、不触发 provider。活动 Job/Lab session 的导入状态策略尚未获用户/产品明确批准；默认 dry-run 只报告其原始状态并阻断可写导入，不自动重放任务。

## 6. 隔离 dry-run / reconciliation 验收门

未来 importer 只能消费完整、校验通过的 snapshot bundle，并写入新建的 staging SQLite 文件，不连接生产路径。第一阶段 dry-run 默认不写 staging；后续隔离导入也必须使用全新临时目标并可删除重建。

必需检查：

- 精确验证源 release、格式/schema 版本、完整标记、namespace 集合、条目数、字节数与每个流 SHA-256；流式读取并限制最大单条记录体积，超限明确失败，不截断或跳过。
- 使用目标 Pydantic schema 验证所有记录；禁止隐式字段丢弃、owner 修复、ID 重写和“坏记录跳过”。未知字段/版本按不兼容失败处理。
- 逐条执行源→目标 canonical full-payload equality/digest 对账。原始源 payload 在受限加密 bundle 中保持不变，并按批准的短期保留策略管理；迁移前冻结版本化转换表，逐字段注明来源、目标、理由和批准依据，包括新增字段默认值、明确的时间/枚举表示转换和 ownerless Session 的目标表示。没有登记的字段增加、删除、改名或值变化均失败；不能先经目标 schema 丢弃未知字段再比较。将批准转换后的完整源 payload 与从目标 DB 重新读出的完整 payload 用同一规范编码比较：UTF-8、对象键排序、固定 JSON 分隔符、保留数组顺序与全部字段、禁止 NaN/Infinity，不做未批准的字符串/数值归一化。每条 SHA-256 与按稳定 namespace/key/序号排序的全量流摘要必须一致；转换清单自身也带版本和摘要。提示词、metadata、错误细节、嵌套输出、Lab variants、事件和收藏内容都在比较范围内。计数、ID、状态、owner 与链接仅为补充检查，不能代替完整 payload 对账。
- 对每个 namespace 比较源/目标计数、ID 集合摘要、状态及 owner 分布；比较 Job.outputs 与规范 outputs、session/job/output/asset/run/reference/favorite/event 链接，显式报告孤儿、重复 ID 和 owner 冲突。V1 ownerless sessions/events 必须保持 ownerless/unverified，不作为导入失败，但报告受限访问记录数；不得自动猜测 owner。
- 验证派生 SQL 列及索引，不能只写 `namespace, record_key, payload`。V1 Job 的 `session_id`、`job_type`、`sort_at=updated_at or created_at`、`idempotency_key` 必须与完整 payload 一致；核对 `v1_records_jobs_idx`、`v1_records_idem_idx`、`v1_records_scoped_idem_idx` 的定义，保留独立 `idempotency` map 并验证其目标 Job。通过 `list_jobs(session_id=...)`、`list_jobs(job_type=..., session_id=...)`、带 session/owner 的幂等读取验证预期 ID 集合、同时间稳定顺序和跨 session 不命中。只要 `get_job(id)` 正确但 filtered readback 缺记录，就必须失败。
- V2 `prompt_cases` 的派生列 `provider_id`、`active=int(is_active)`、`quality=quality_score`、`index_version` 必须与 payload 一致；核对 `v2_records_provider_idx`、`v2_records_case_sort_idx` 的定义。用 `list_cases(active_only=True/False)` 验证启用集合及 quality/ID 排序、`get_active_index_version()` 验证版本，并以只读 SQL 的 provider/active/version 过滤核对期望集合。禁止用删除/替换 provider 来测试索引。直接 `get_case(id)` 的正确性不能代替这些过滤读取。
- 在目标 app/bootstrap 触发任何 history lazy import 之前，对源 JSONL/manifest 做完整语法和完整性预检。候选的 V1/V2 history 首次导入现在对坏行 fail closed：失败必须回滚本次导入，不能静默跳过后写入 V1 `jsonl_imported`/`owner_evidence_backfilled` 或 V2 `jsonl` 完成标记；修复输入后才可重新导入。导入后显式核对 V1 `v1_history_records` / `v1_history_owner_evidence`、V2 `v2_image_history` 的计数、ID/owner/conflict 摘要和所有源 history 行。此保护不自动修复旧版本已写入的完成标记或已有不完整表；完成标记已存在但校验不一致时必须阻断，并由单独获批的恢复流程处理，不能以再次启动自动补救。V1/V2 favorites 的首次 JSON 导入同样必须完整验证后原子提交记录与完成标记；history/favorites 导入错误在 API 边界仅返回脱敏的修复提示，不向客户端暴露源 payload，也不建议自动重试未修复输入。
- 四个首次导入入口（V1/V2 history、V1/V2 favorites）在输入失败时回滚本次记录/owner-evidence 写入与新完成标记，保留原来源供修复后重试；来源缺失时不写完成标记，之后恢复来源仍需验证。历史写入器产生的整数/null owner 保持兼容；显式 owner 接受 SQLite 整数范围内的非负整数及去除外围空白后的 ASCII 十进制整数字符串（可带 `+`），0/null/缺失/空字符串沿用 ownerless 语义。所有浮点 owner token（包括 `1.0`、`1e0`）均拒绝，因为 JSON 浮点解码可能已把不同的原始 ID 舍入为同一个整数；布尔值、负数、越界值和其他字符串形式也拒绝，不能静默改成 public/ownerless 或另一 owner。此处的修复后重试只适用于未完成的导入，不授权清除旧完成标记或自动重放历史数据；已有完成标记仍需人工对账及单独获批的恢复。
- 将目标专属 `output_delete_claims` 初始计数验证为 0；它不是旧数据实体，不从其他记录合成。
- 图片/上传文件不搬入数据库；对每个文件引用核对规范化路径边界、存在性、大小及内容摘要。脱离允许存储根、缺失或摘要不同均阻断 cutover。
- 原始运行态 queued/running 保持为未决项；dry-run 不调用 Provider，不把状态悄悄转为成功/失败，不触发启动恢复。必须单列并等待切换政策。
- 输出只生成脱敏报告和 staging DB 摘要；不将 prompts、私有事件、API keys 或图片字节写入普通日志。

### 6.1 初次启动不是只读检查

对账应由离线显式连接及无启动钩子的 repository/readback 完成；仅限全新 staging 路径，不能为读取而启动 API 或 worker。V1/Lab 启动恢复会修改中断记录；V2 API lifespan 会加载配置、bootstrap provider/cases、初始化 queue，并可按配置启动 remote sync、周期 resource sync 和 inline queue worker。standalone task worker 也先 bootstrap，资源 worker 先 bootstrap 再同步。旧 task worker 还有 `release_worker_running_tasks`，候选替换为 claim/heartbeat/fencing 流程；新 claim/lease 的过期恢复及成功 checkpoint 恢复依然是状态转换，不是 migration readback。

因此，先完成无副作用的完整对账并保存不可变恢复点，再在另一份可丢弃副本演练启动。显式隔离 provider/账单网络，禁用 inline/standalone task consumption、remote/startup/定时 sync 和所有不获准的恢复入口；现有开关不能保证 bootstrap 不写，不能把“worker disabled”视为完整只读模式。演练必须对启动前后完整 payload、queue/lease/checkpoint、case index 和文件摘要做差异核对；仅接受已批准转换。未知差异、未获批活动任务或没有可验证隔离方式时阻断启动，不通过重启自动修复对账差异。

### 6.2 有界离线反例检查

`tests/test_pr28_migration_reconciliation.py` 验证历史/候选清单摘要，并按第 2.1 节的文本规范从当前工作树计算 Git blob SHA-1，防止所有候选来源在审计后发生实质漂移；不依赖 Git index 或浅克隆中缺失的历史 Git 对象。回归覆盖 LF/CRLF 同源一致性，以及实际内容、尾部空白、末尾换行、独立 CR 和 BOM 修改仍改变指纹；未声明的文件类型必须拒绝。其数据检查只使用合成记录与临时 SQLite 文件，证明完整 payload 或 direct-ID 读取正确仍可能遗漏索引可见性，同时覆盖 canonical payload 变化、独立 retention policy 默认值和 WAL 一致备份。它不连接 VPS、不调用 provider、不启动 app/worker，也不实现或证明生产 exporter/importer。运行入口：`python -m pytest -q tests/test_pr28_migration_reconciliation.py`。

### 6.3 严格导入 provenance 与旧 marker 盘点

后续首次导入会在写入完成标记的同一 SQLite 事务中写入版本化 receipt：V1 存入 `v1_import_receipts`，V2 history/favorites 分别存入专属 receipt 表。receipt 记录 importer ID/version、当次实际验证处理的来源记录数与完成时间。它只证明首次导入路径和当时处理量，不是来源文件哈希、不代表当前 SQLite 行数，也不声称后续增删与来源文件保持一致。V1/V2 的既有旧 marker 不会自动补 receipt；当 marker 已存在但 receipt 缺失时仍不会重放来源。

使用 `python scripts/pr28_import_marker_inventory.py --db NAMESPACE=PATH [--db ...]` 可对通过 SQLite backup API 得到的冻结一致副本只读盘点，namespace 为 `v1_history`、`v1_favorites`、`v2_history` 或 `v2_favorites`。工具不导入应用、不执行 schema 初始化，在一个 `mode=ro` 事务中读取，只输出脱敏 marker/receipt 状态和当前目标表行数，不输出路径或业务 ID/payload；不一致时返回非零分类状态。不要直接复制正在写入的 WAL 主文件。它不解析旧来源文件，也不判断 source-only / DB-only 差异的业务意图，因此不是完整数据对账或修复工具。

`legacy_completion_unverified` 必须保持为待核验状态。导入后合法删除会使旧来源继续含有对应行；因此不能把 source-only 直接补回数据库。生产对账仍要求先生成一致的受限快照、核对 SQLite/WAL 和来源文件、结合删除/审计/备份证据，形成逐条 allowlist 并经批准；无足够证据的差异不改。inventory 的 `strict_import_receipt` 只提升首次导入可追溯性，不代替该流程。

## 7. 切换、回滚与停止条件

“来源缺失时不写完成标记”只保证之后的首次导入仍可验证，不证明任意旧文件恢复都是安全的。如果未完成导入的目标库已经发生原生新增、更新或删除，再恢复陈旧来源必须先离线对账；运行时没有足够的 tombstone 证据自动判断每条恢复记录是否应该存在。防复活回归覆盖的是已有完成标记不重放，不能扩展成“任意来源恢复都不会复活记录”。严格解析/事务也不能替代来源文件的维护写屏障。

通过 dry-run 不等于切换通过。正式切换还需维护窗口和全写屏障：最后一次完整快照、隔离导入、逐域对账、备份 staging DB/旁路文件、验证健康检查，然后只在零新写入期间切换服务指向。切换后开放新写入前保存回滚点。

SQLite 备份必须覆盖 WAL 中已提交的数据：在维护栅栏内使用 SQLite backup API 创建独立一致备份，或在停止该持久库全部写入者/连接、成功完成并核实 checkpoint 后复制完整数据库；不能仅复制仍在使用的 `.sqlite3` 主文件，也不能手工删除 `-wal`/`-shm` 作为备份步骤。repository、task queue、认证库和其他 SQLite 分别备份，在同一已验证无写入 epoch 清单中记录各自摘要和旁路配置/媒体摘要；单库 backup 不提供跨库一致性。离线恢复每份备份并运行 `PRAGMA integrity_check`、完整 payload/索引/readback 对账及媒体引用校验，记录恢复演练证据后才能把它称作回滚点。此流程不授权关闭仍持有未导出 RAM 状态的旧进程。

旧 RAM-only 服务一旦停止，未导出的记录不可由旧版本恢复。新 SQLite 已接受写入后，简单回滚旧版本会丢失切换后的新增/更新；除非有经验证的反向增量导出或正向修复方案，否则回滚目标必须是继续使用持久化版本并前向恢复，而非切回旧内存仓库。

任何以下情况均停止：快照不完整；源进程/代码版本未逐个核实；V2 三进程快照缺失或 epoch 不一致；跨进程同 key payload/owner 冲突；源版本或候选源码映射不符；PR #27 必需保护未进入最终候选或回归未通过；活动写入未静止；schema/JSONL 校验失败；未登记转换或 canonical full-payload/digest 不一致；SQL 派生列/索引/filtered readback 不一致；目标 history/owner-evidence 表或迁移完成标记与源不一致；计数/ID/owner/引用不一致；保留策略等配置缺失或默认为未批准值；媒体文件缺失/越界/摘要不符；运行态任务没有获批处置；启动副作用未经隔离/批准；WAL 备份不一致或恢复演练失败；磁盘或 staging 容量不足；或 rollback 只能依赖已经消失的 RAM state。

## 8. 当前阶段完成标准与下一阶段入口

迁移文档阶段限定为事实核验、映射冻结和切换协议。PR #27 的必要 V2 依赖子集已在候选提交 `d7b97c7af777ceba7fa85db4a6b5d94aa9539720` 中集成；第 2.1 节列明的未引入范围保持不变。本轮新增阶段是四个 history/favorites 入口的严格原子导入、脱敏 API 错误及跨 LF/CRLF checkout 的源保真修正，不能把历史依赖集成或历史测试结果当成本轮验收。不实现导出 API/脚本、不构造生产快照、不写生产 SQLite、不重启 VPS。当前阶段可通过的标准是：Source Fidelity 和独立 Audit 均对同一最终候选、本文件、原始及补充源清单摘要和映射矩阵给出 PASS；文档链接、命名空间映射、已有 VPS 证据措辞准确；候选依赖回归、严格导入回归与有界离线检查通过。历史 A2 结论不能自动沿用到本轮变更。

完成文档审计后仍有一个**外部恢复能力阻断**：当前运行中的旧进程没有完整导出入口。若必须保留 RAM-only 记录，保持运行并评估可否在不重启该进程的条件下取得可信快照；不可行时，需要用户明确选择“保持旧服务/接受明确列出的部分恢复/放弃无法导出的 RAM-only 记录”中的业务处置。未获该决定前，不开发会暗示当前实例可安全 cutover 的脚本，也不合并/部署 PR #28。
