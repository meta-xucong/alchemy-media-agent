# 15. 开发任务拆解 / Backlog

## Epic 1：项目基础设施

| ID | 任务 | 验收 |
|---|---|---|
| INF-001 | 初始化 monorepo / backend / frontend / docs | CI 可跑，README 完整 |
| INF-002 | 配置 PostgreSQL、Redis、对象存储 | 本地 docker compose 可启动 |
| INF-003 | Secret 管理和 `.env.example` | 无真实 key，配置文档完整 |
| INF-004 | OpenTelemetry trace_id 贯通 | API 到 worker 有同一 trace_id |

## Epic 2：用户、项目、会话

| ID | 任务 | 验收 |
|---|---|---|
| APP-001 | 用户/组织/项目模型 | CRUD 可用 |
| APP-002 | Session 和 Message API | 可创建会话、发送消息 |
| APP-003 | SSE 事件流 | UI 能收到 job/status/output 事件 |

## Epic 3：素材上传与解析

| ID | 任务 | 验收 |
|---|---|---|
| AST-001 | 签名 URL 上传 | 文件可上传到对象存储 |
| AST-002 | 文件扫描和 MIME 检测 | 非法类型拒绝 |
| AST-003 | 图片元数据和缩略图 | UI 可预览 |
| AST-004 | PDF 文本和页面图解析 | MaterialBrief 可生成 |
| AST-005 | PPT/DOC 文本解析与 PDF 转换 | 视觉保真路径可选 |
| AST-006 | 表格摘要和变量抽取 | BatchPlanner 可读取字段 |
| AST-007 | 短视频抽帧和音频转写 stub | 产生 keyframes 和 transcript 字段 |

## Epic 4：OpenAI Agents Runtime

| ID | 任务 | 验收 |
|---|---|---|
| AGT-001 | RuntimeManagerAgent | 可识别生图/改图/批量/视频 |
| AGT-002 | MaterialAnalyzerAgent | 输出 MaterialBrief JSON |
| AGT-003 | PromptArchitectAgent | 输出 ImagePromptPlan JSON |
| AGT-004 | ProviderSelectorAgent | 可选择 provider/model |
| AGT-005 | ImageGenerationAgent tool | 可创建 image job |
| AGT-006 | CriticAgent | 可评分并给建议 |
| AGT-007 | RevisionAgent | 可输出 PromptPatch |
| AGT-008 | Agent eval cases | CI 中可跑 20 条样例 |

## Epic 5：图片生成

| ID | 任务 | 验收 |
|---|---|---|
| IMG-001 | ImageProvider 基类 | mock provider 测试通过 |
| IMG-002 | OpenAI GPT Image 2 adapter | 单图生成成功 |
| IMG-003 | 图片编辑 adapter | 基于 output_id 生成修改版 |
| IMG-004 | 批量任务队列 | 10 张并发生成 |
| IMG-005 | 输出转存和缩略图 | 不依赖 provider 临时 URL |
| IMG-006 | 版本树 | UI 可看到父子版本 |
| IMG-007 | 下载导出 | 单张/批量 zip 下载 |

## Epic 6：多模型 provider

| ID | 任务 | 验收 |
|---|---|---|
| PRV-001 | ProviderRegistry | 可注册和查询能力 |
| PRV-002 | Gemini Image adapter stub/PoC | 可在项目设置中切换 |
| PRV-003 | 成本估算 | 任务前可提示成本 |
| PRV-004 | 熔断/重试/降级 | 429 和 5xx 有策略 |

## Epic 7：Claude Code 中枢

| ID | 任务 | 验收 |
|---|---|---|
| CLD-001 | `.claude/agents` 模板 | 5 个 subagent 可用 |
| CLD-002 | Claude hooks | 工具调用日志和密钥检查 |
| CLD-003 | Claude Orchestrator 调 OpenAI Runtime tool | 可触发 image job |
| CLD-004 | `ORCHESTRATION_MODE` 策略开关 | runtime_first/claude_first 可切换 |

## Epic 8：视频预留

| ID | 任务 | 验收 |
|---|---|---|
| VID-001 | VideoProvider 基类 | mock 测试通过 |
| VID-002 | `/v1/video/jobs` API | 未配置 provider 返回友好错误 |
| VID-003 | Seedance provider stub | 可提交 mock task 并轮询 |
| VID-004 | Veo provider stub | 能力字段完整 |
| VID-005 | 视频 UI 实验入口 | 内部开关可见 |

## Epic 9：安全与合规

| ID | 任务 | 验收 |
|---|---|---|
| SEC-001 | 上传授权声明 | 未勾选不可上传 |
| SEC-002 | 内容安全检查 tool | 风险请求可阻断 |
| SEC-003 | API Key 加密存储 | DB 无明文 key |
| SEC-004 | 审计日志 | 可按用户/项目/任务查询 |
| SEC-005 | 下载 URL 权限 | 越权访问失败 |

## Epic 10：测试与上线

| ID | 任务 | 验收 |
|---|---|---|
| QA-001 | Provider contract tests | 所有 adapter 通过 |
| QA-002 | E2E：上传→生图→炼金→下载 | CI 或 nightly 可跑 |
| QA-003 | 压测批量任务 | 队列不丢任务 |
| QA-004 | 灰度发布 | feature flag 控制 provider 和视频 |
| QA-005 | 运营看板 | 成本、成功率、模型表现可见 |
