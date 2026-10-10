# PR #28 严格导入与 Windows 来源指纹修复交接

日期：2026-10-10。基线：`d7b97c7af777ceba7fa85db4a6b5d94aa9539720`。
本轮是该基线后的迁移安全补丁；此前队列领取保护不改写。保持 Draft，不合并、不部署。

## 1. 已确认的问题

- 来源映射测试直接计算 checkout 字节的 Git blob；Windows CRLF 转换会产生假阳性。改为仅对已声明文本来源将 CRLF 规范化为 LF，仍检测内容、空白、BOM、孤立 CR、缺失末尾换行等真实变化。不改为读取可能落后的 index，也不跳过 Windows 检查。
- V1/V2 history 的首次 JSONL 导入会跳过坏行后标记完成；V1/V2 favorites 也会跳过非对象或缺 ID 的条目。该行为可能永久遗漏修复后的来源记录。
- V2 history 的旧迁移去重允许同一 output 的私有 owner 被后续 ownerless/其他 owner 覆盖；错误 owner 类型还可能转成 public 或另一个整数 ID。此问题在临时数据中复现，不代表已发现线上事件。

## 2. 修正后的运行规则

1. 四个首次导入器均逐条验证，失败时回滚本次记录、owner evidence 和完成标记。来源原件不截断、不删除，修复后可重新尝试。显式 `BEGIN IMMEDIATE` 内重新检查标记，避免等待中的第二个初始化者重复导入；回归也覆盖 autocommit 连接。
2. 拒绝坏 JSON、无效身份/记录结构、重复 JSON key、非有限数、指数溢出、非法 Unicode 等输入，异常仅带安全原因，不携带源 payload。V1 的可选历史字段保持兼容，不把它改造成完整 GenerationJob schema。
3. 显式 owner 仅接受 SQLite 范围内非负整数及兼容的 ASCII 整数字符串；缺失/null/空白/0 保持既有 ownerless 语义。所有浮点形式都拒绝，包括 `1.0`、`1e0`：解析成浮点后可能已经丢失原 ID 精度。此限制只用于旧来源导入，不改全局运行时 schema。
4. V2 history 的同 ID 混合 ownerless/private 或不同私有 owner 在导入中阻断并回滚，不能凭更新时间改归属。相同 owner 的合法重复仍按原排序规则合并；V1 原有 owner-conflict evidence 机制保留。Favorites 的不同 owner 复合键仍是不同记录。
5. 来源初始缺失时不写新完成标记，之后恢复来源仍需验证；存在且合法的空输入可完成。已有完成标记不自动清除、不自动重放，避免复活已删除数据。旧版已经错误完成的库需要单独离线对账和获批修复。
6. API 对导入错误返回脱敏 503，`history_import_blocked` / `favorites_import_blocked`，`retryable=false`，不建议客户端自动重试未修复的存储。SQLite 暂时忙锁仍按原有独立重试规则处理。
7. Favorites 继续分块读取、不累积所有 items；根元数据去重限制为 64 个字段、累计 64 Ki 字符键名，超限回滚而非无限增加辅助内存。合法历史 writer 的 `items` 格式不受影响。

## 3. 验证和源码绑定

- 完整 V2 测试目录：**694 passed，0 failed，0 skipped**，49.18 秒。
- V1/Lab/来源映射/严格迁移定向组合：**220 passed，0 failed，0 skipped**，5.12 秒。
- 完整 V1 `tests/test_api_smoke.py`：**97 passed，0 failed，0 skipped**，230 秒；这不是全 V1 测试目录。
- 来源/对账文件独立运行 **23 passed**。50 个来源复制为 CRLF 且没有 `.git` 的临时目录后通过完整来源检查；追加实际内容变更仍失败。这是跨平台逻辑验证，实际 Windows runner 结果以新提交 CI 为准。
- 独立审计验证了真实坏来源经 V1/V2 history/favorites GET 返回脱敏 503、没有部分数据或新完成标记；修复来源后返回 200。无真实 Provider 或生产数据参与。
- 独立只读复审在同一最终指纹上 PASS：V1 专项 161 项、V2 专项 249 项、来源对账 23 项通过，并再次完成全 50 来源 CRLF 正例及真实修改反例。与上述全量/定向结果重叠，不累计计数。
- 本轮 16 个变更/新增 Python 文件指纹：`35fd11371931ca2c694d6212da8a534d8d9c407a470d6e58dbbf38843a2f8745`。相对上述基线按 UTF-8 路径排序；将各声明文本文件 CRLF 规范化为 LF 后，串联 `path NUL SHA256(content) 的小写十六进制 NUL`，再求 SHA-256。文档、工作流、生成的 egg-info 不计入。
- 保留原始 38 来源历史矩阵；候选 overlay 24 行、扩展 50 来源，摘要 `b64f707f72f233f0106543535aa6182a77571d8ce5762970e14b436c87e17991`。详见相邻 cutover plan。
- Python 语法解析和 diff hygiene 通过。新增 Windows 来源/对账 CI job，继续运行 Linux V1/V2 回归。此文写入时尚未发布新 SHA 的 CI 结果；新提交和最终 CI 记录以 PR 更新为准。

## 4. 测试遥测边界

一次未配置的全量 V2 测试轮次被工具因潜在未知遥测外发拦截，其结果不计入通过；没有重试被拒绝的会话轮询。只读核查发现实际安装的 ONNX Runtime 1.31.0 包含 OneCollector 上传器和进程启动前的关闭开关。依据版本匹配源码，在新测试进程启动前设置：

```sh
ORT_DISABLE_TELEMETRY=1 OPENAI_AGENTS_DISABLE_TRACING=1 python -m pytest -q
```

GitHub 工作流在全局环境设置同样的值；V1/V2 conftest 在导入应用/SDK 前再次强制设置，防止继承的 `0` 恢复遥测。上述最终测试结果来自此配置的新进程。Windows 新 job 只安装来源/SQLite 对账所需依赖，不安装或启动 OCR。

依据：[ONNX v1.31.0 环境开关](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.31.0/onnxruntime/core/platform/telemetry_environment.h)、[ONNX v1.31.0 上传器初始化前检查](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.31.0/onnxruntime/core/platform/telemetry_1ds.cc)、[Agents tracing 配置](https://openai.github.io/openai-agents-python/tracing/)。

这些设置控制已识别 SDK/原生遥测，不是通用网络沙箱；不据此宣称所有依赖或所有平台没有网络访问。未改生产 OCR/Provider 行为，也没有为未知遥测申请或授予外发权限。

## 5. 本地交叉复审建议与剩余边界

拉取 PR #28 新 head 到隔离 worktree，确认 commit SHA，保留既有未提交工作。重点检查：

- Windows CRLF 不再误报，实际修改仍会被发现。
- 坏行出现在第一个/中间/最后一个时，记录与完成标记都不部分提交；来源修复后重试成功。
- ownerless/private 混合重复、浮点舍入、布尔/下划线/Unicode 数字等 owner 反例均阻断。
- 并发初始化只导入一次；SQLite 忙锁、文件 I/O 错误和旧完成标记的行为没有混淆。
- 运行工作流中的 V1 定向列表、完整 smoke、完整 V2 目录；先配置适用平台的测试遥测关闭选项。不要为复审调用真实 Provider。

此补丁防止新的不完整导入，不会自动找回旧版已经跳过的数据。恢复陈旧文件到未完成导入但已有原生写入/删除的库仍需对账，不能把 pending-on-missing 解释为任意恢复都无复活风险。严格解析和事务不能替代冻结来源的写屏障。

生产旧进程 RAM 完整导出、一致快照、实机进程 SHA、真实数据迁移/恢复演练、VPS RSS/磁盘/延迟验收仍未完成。不得为部署此补丁直接重启旧服务。本轮未合并、部署、访问 VPS 或操作生产数据库。
