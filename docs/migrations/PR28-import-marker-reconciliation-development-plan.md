# PR #28 导入标记与旧库对账闭环开发计划

日期：2026-10-11
开发基线：PR #28 head `81953cb84ba9925215d8f634a8f300052835a10d`，base `main`。
工作分支：`codex/pr28-import-marker-closure`。本计划只处理 PR #28 的首次导入证据和旧库对账准备，不触碰主工作区已有改动。

## 1. 总目标与本阶段目标

**总目标：** 让 PR #28 的 V1/V2 history 与 favorites 持久化迁移具备可审计的首次导入证据，并提供安全识别旧完成标记的只读入口；修复与审计通过后达到可合并的代码标准。

**本阶段目标：** 冻结导入标记的权威语义，实现新导入的原子 provenance receipt、旧标记盘点命令、配套测试及运行文档。此阶段不读取或修改 VPS/生产数据库，不执行 RAM 导出、生产数据恢复、合并或部署。

## 2. 风险分级与修正模型

- **D0：** 业务风险评估已完成。不能安全自动重放已有完成标记对应的来源文件。
- **I2：** 实施涉及 V1/V2 四个导入器与不同 SQLite schema。
- **A2：** 错误的恢复策略可能复活用户删除的收藏/历史，或改变历史 owner/payload。

### 2.1 已确认的行为差异

最新 PR 已使新发生的首次导入严格校验、事务回滚并 fail closed。但既有完成标记只说明旧代码曾经写入过一个标记，无法证明当时完整导入。另一方面，标记写入后，运行时继续在 SQLite 中新增、更新和删除数据；部分旧 JSON/JSONL 不会同步这些变更。直接重放或以文件覆盖数据库，可能复活已删除记录并覆盖较新的数据库状态。

### 2.2 唯一权威规则

1. **未完成标记：** 只有严格校验完整来源后，才能在同一 SQLite 事务内导入记录、所有权证据、首次导入 receipt 和完成标记。
2. **含严格 receipt 的完成标记：** receipt 证明该库由指定严格导入器完成首次导入，并记录当时解析的记录数；它不声称来源文件与当前 SQLite 内容持续一致，也不阻止后续合法业务写入。
3. **无 receipt 的旧完成标记：** 分类为 `legacy_completion_unverified`。运行时保持 SQLite 当前状态，不自动重放、不自动删标记、不覆盖、不猜 owner。V1 history 的 `owner_evidence_backfilled` 单独存在但缺 `jsonl_imported` 属于不一致状态，必须 fail closed；同时，存在严格 receipt 却只有 `jsonl_imported` 的反向半状态也必须 fail closed。仅在无 receipt 的旧 `jsonl_imported` 标记缺 owner-evidence 标记时，才走原有只补 owner evidence 路径。
4. **来源与 SQLite 当前状态不一致：** 默认分类为“待对账差异”，不能仅凭 source-only 推断漏导入；它也可能是合法删除。只有冻结快照、备份、审计日志/明确删除证据和人工批准组成证据后，才允许另行制定精确、可回滚的修复。
5. **只读盘点：** 不初始化应用、不触发导入、恢复、Provider、队列或写入；数据库使用 SQLite `mode=ro`。仅输出脱敏状态、计数、schema/marker 摘要及错误类别，不输出 prompt、业务 payload、原始 ID、凭据或图片内容。

## 3. 变更范围

### 允许

- 为 V1/V2 的四个首次导入路径增加同事务 provenance receipt，包含固定 importer/version 标识和导入条数；与 completion marker 同时提交。receipt 使用每个数据库的专用 receipt 表，不改变既有 marker 的含义。
- 新增只读离线 marker inventory 命令，明确区分无标记、带 receipt 的严格首次导入、无 receipt 的旧完成标记、receipt/marker 不一致及 schema/读取异常。
- 在临时 SQLite 与合成来源上增加测试：原子性、重复初始化、旧标记分类、只读性和脱敏输出。
- 更新 PR #28 迁移文档，定义旧数据对账与人工修复门槛。

### 禁止

- 不自动重放已有 completion marker，不更改任何线上/历史 SQLite，不自动恢复 source-only 行。
- 不修改 owner、删除状态、历史 payload 或跨产品数据隔离。
- 不调用真实 Provider、启动 V1/V2 API/worker、操作 VPS、导出 RAM-only 数据。
- 不扩大到 PR #28 之外的长期保留、队列或前端优化。

## 4. Receipt 契约

receipt 与当前完成标记应位于同一个 SQLite 事务中，保存在 `v1_import_receipts`、`v2_image_history_import_receipts` 或 `favorite_import_receipts`。字段：

- `importer_id`：稳定且带命名空间的值，例如 `v1.history.jsonl`、`v1.favorites.json`、`v2.history.jsonl`、`v2.favorites.json`。
- `importer_version`：本次严格导入规则的显式版本常量；语义变化时递增。
- `record_count`：导入循环实际验证并处理的来源记录数，合法空文件为 `0`。
- `completed_at`：现有完成时间或同事务生成的 UTC 时间。

receipt 是首次导入来源的处理证明，不是当前表计数或文件哈希的持续一致性断言。旧 marker 缺 receipt 时不得回填伪造 receipt。若已经存在 completion marker 但没有 receipt，现有入口必须继续按兼容规则只读返回，不触发二次导入。

## 5. 只读盘点命令契约

- 显式接收四种 namespace 与数据库路径；可按需检查一个或多个 namespace，不导入应用配置或执行 bootstrap。退出码只覆盖本次传入的范围；完整迁移盘点必须显式传入四个 namespace。
- 使用只读 SQLite URI 并在单一只读事务中检查 marker、receipt 和计数；不创建不存在的数据库，不建表，不更新 schema/marker。输入应是通过 SQLite backup API 得到的离线一致副本；不要直接把正在写入的 WAL 数据库文件复制给该命令。
- 每个 namespace 报告 marker 状态、receipt 是否存在且结构合法、当前目标表计数、数据库读取错误类别。不得把当前行数与首次 `record_count` 不同直接判为损坏。
- 对已存在的 marker/data 表校验必需列；表名存在但列结构不兼容时归类为 `schema_incomplete`，不得仅因 `COUNT(*)` 可执行就认定结构有效。V1 history 有状态表时还必须验证 owner-evidence 表具备 output_id、owner_id、owner_conflict；receipt 表需具备完整字段且以 namespace/migration_key 为主键，否则归类为 `receipt_invalid`。
- 默认 stdout 为脱敏 JSON；不包含绝对路径、原始 record/output/session/user ID、完整 SQLite 错误字符串或业务 payload。必要的文件定位由调用者本地掌握。
- exit code：所有 namespace 可读且状态已分类为 0；存在 `legacy_completion_unverified` 或 marker/receipt/schema 异常为 2；输入无效/数据库不可读为 3。命令不执行任何修复。
- 文档明确：inventory 不是数据完整性对账、生产迁移批准或恢复许可。

## 6. 验收标准

1. 四个导入器均在同一事务写入严格 receipt 和完成标记；坏来源时二者都不存在且本批数据回滚。
2. 重复初始化不会重新消费来源或改变 receipt。
3. 旧 completion marker 无 receipt 时仍不回放来源；inventory 报 `legacy_completion_unverified`。V1 history 的任一半标记不一致状态 fail closed；仅无 receipt 的旧 history marker 可按兼容路径补 owner evidence，不回放 history rows。
4. receipt 字段错误、只有 receipt 无 marker、marker/receipt importer 不匹配均被明确分类，不改变库。
5. 表存在但缺必需列时归类为 schema 异常，即使 `COUNT(*)` 可执行也不能报严格 receipt。
6. inventory 对不存在 DB 不创建文件；运行前后数据库主文件和 WAL/SHM 字节、marker、表计数一致。
7. 默认输出没有原始业务 ID、payload、prompt、路径或凭据。
8. 目标测试、V1 API smoke、V2 全套、来源映射 CI 均通过；完整性声明只报告实际运行的测试。
9. 独立 Audit 与 Source Fidelity 对同一最终 SHA 和文件清单给出 PASS。未通过前不推送或请求合并。

## 7. 生产数据闭环边界

代码通过只表示未来首次导入更可审计、旧状态可安全识别。VPS 上已存在的旧 marker 是否对应不完整数据，仍需在生产维护方案中对冻结备份做只读逐域对账。实际修复必须使用精确记录 allowlist、说明每条证据、保留原库快照、插入前冲突检查、事务/幂等执行及修复后完整 readback；没有可信删除/变更证据的差异保持未决。此开发不声称生产旧数据已修复，也不授权部署或重启。

## 8. 本轮执行记录

2026-10-11，针对最终候选代码运行：

- V1 importer、owner-evidence 半状态、inventory 与来源指纹定向套件：169 passed。
- V1 完整 API smoke：97 passed，6 条既有 FastAPI deprecation warnings。
- V2 favorites/history 原子导入与 receipt：245 passed；V2 完整 `custom_media_agent_2_0/tests`：698 passed，1 条既有 deprecation warning。最终迭代只改 V1 history、离线盘点工具和测试/文档，V2 生产代码未再变。
- Python 编译与 `git diff --check` 通过。

这些组存在重叠，不相加。测试进程显式设置 `ORT_DISABLE_TELEMETRY=1`、`OPENAI_AGENTS_DISABLE_TRACING=1`；V1、V2 因依赖版本冲突分开运行。中途审计发现并修正了 malformed schema 误报、owner-evidence 表漏检和两种不一致半 marker 可读/写来源的问题；不可能代表旧安装的测试夹具也已更正为无 receipt 的 legacy 状态。没有运行真实 Provider、浏览器、VPS 或生产数据库。最终独立 Audit 与 Source Fidelity 尚待本次候选 SHA 的回执；在收到 PASS 前不得推送或请求合并。
