# 定制化图片和视频生成 Agent 平台 文档包

生成日期：2026-06-02

这个包是面向产品、研发、算法/模型接入、测试和安全合规的第一版开发文档。为了便于直接落地到代码仓库，正文采用 Markdown，接口采用 OpenAPI YAML，架构图采用 Mermaid，并附带一个 Python/FastAPI + OpenAI Agents SDK 风格的代码骨架。

## 目录

- `docs/01_需求分析_PRD.md`：业务目标、用户流程、功能范围、非功能要求。
- `docs/02_实施蓝图_里程碑.md`：MVP 到视频扩展的阶段计划、验收口径。
- `docs/03_技术路线与选型.md`：OpenAI Agents SDK、Claude Code 中枢、多模型适配、存储队列部署路线。
- `docs/04_系统架构设计.md`：分层架构、运行链路、关键组件。
- `docs/05_Agent编排设计.md`：中枢调度 agent、专业 agent、handoff/tools/guardrails。
- `docs/06_多模态素材处理方案.md`：图片、短视频、PDF、PPT、DOC、表格的解析与资产化。
- `docs/07_生图工作流与炼金闭环.md`：首次生成、批量生成、继续调整、评价与版本管理。
- `docs/08_视频生成预留接口.md`：Seedance/Veo 风格的异步任务接口与状态机。
- `docs/09_模型供应商适配层.md`：LLM、图片、视频 provider 抽象与 API Key 接入。
- `docs/10_数据模型与状态机.md`：核心表、对象存储、任务状态机。
- `docs/11_API接口规范说明.md`：REST/SSE/WebSocket 接口说明。
- `docs/12_安全合规与风控.md`：内容安全、版权、隐私、密钥、审计。
- `docs/13_测试验收标准.md`：单测、集成、E2E、模型回归、灰度。
- `docs/14_提示词与Agent模板.md`：系统提示、角色提示、图片提示词模板。
- `docs/15_开发任务拆解_Backlog.md`：可直接进 Jira/Linear 的任务拆解。
- `docs/16_参考资料.md`：本次资料基线与官方文档链接。
- `docs/17_开发前准备与本地运行手册.md`：本地配置、mock/live 边界、开发顺序。
- `docs/18_验收执行矩阵.md`：全量、模拟、冒烟、live-readiness 验收命令。
- `docs/19_全量自检报告.md`：对照开发文档的模块覆盖、修复项和验收边界。
- `docs/20_前端界面说明.md`：Apple 风格前端工作台、接口接入和验证结果。
- `docs/21_密钥与部署配置.md`：模型密钥、OpenAI-compatible 网关、VPS 部署和冒烟验证配置。
- `docs/22_2.0_Agent化案例库与中枢调度方案.md`：2.0 Agent 化案例库、中枢调度、资源 provider 和案例智能化方案上一版。
- `docs/23_2.0_OpenAI_Agents_SDK优先架构方案.md`：2.0 新主方案，OpenAI Agents SDK 优先，中枢、专业 agent、tools、handoffs、sessions、guardrails 和 tracing 设计。
- `docs/24_V1素材高级版_开发文档.md`：V1 素材高级版后端方案，定义基础参数与高级图片素材增强的叠加关系、素材用途、AssetVisionProfile、AssetPlan、PromptPlan、provider 图片输入、视觉复检和实施分期。
- `docs/25_V1素材高级版_API与数据模型.md`：V1 素材高级版 API 扩展、请求 schema、视觉画像、复检结果、数据表、状态机和 provider capability 契约。
- `docs/26_V1素材高级版_测试验收与风控.md`：V1 素材高级版测试矩阵、真实图片输入验收、视觉画像/复检、历史验收、限流、上传安全、授权与内容风控。
- `docs/27_V1素材高级版_实施任务拆解.md`：V1 素材高级版从开关、schema、vision analyzer、Kimi planner、provider 图片输入、后处理到测试上线的任务拆解。
- `docs/28_移动H5前端交互重构开发文档.md`：移动 H5 前端信息架构重构方案，把高级设置、案例库、历史、运行详情和设置页改为更适合手机操作的独立层级。
- `specs/openapi.yaml`：第一版后端 API 草案。
- `diagrams/*.mmd`：Mermaid 架构图。
- `src_skeleton/`：最小代码骨架，方便研发快速起项目。
- `claude_code/.claude/agents/`：Claude Code subagent 示例定义。
- `claude_code/.claude/hooks/`：Claude Code hook 示例。
- `scripts/deploy_vps.sh`：VPS Docker 一键部署脚本。
- `.github/workflows/deploy-vps.yml`：GitHub Actions 远程部署模板。
- `src_skeleton/.media_storage/generated_images/`：随仓库分发的历史图片种子数据，用于新环境首屏展示。

## 重要假设

1. 你写的“生成实盘 agent”结合上下文按“生成视频 agent”理解；文档中统一叫“视频生成 Agent”。如果后续“实盘”另有所指，只需要替换该模块命名和接口字段。
2. 产品第一阶段只做生图闭环；视频模块只保留统一接口、异步任务、供应商适配和状态机。
3. “Claude Code 为中枢调度 agent”采用双层编排：Claude Code/Claude Agent SDK 作为控制面与复杂任务中枢；OpenAI Agents SDK 作为运行时底层框架，承载高频用户请求和专业 agents。
4. “免费/开源 agents”主要指 agent 框架、agent 定义、工具与子系统开源免费；实际 LLM/图片/视频 API 调用通常仍会产生模型费用。

## 使用方式

- 产品/项目经理先读 01、02、15。
- 后端/架构先读 03、04、05、09、10、11。
- 前端先读 01、07、11。
- 模型/提示词工程先读 05、06、07、14。
- 安全/法务/运维先读 12、13、16。

## VPS 快速部署

仓库已内置 Docker Compose 和 GitHub Actions 部署流程。把 `OPENAI_API_KEY`、`ANTHROPIC_AUTH_TOKEN`、`VPS_HOST`、`VPS_USER`、`VPS_SSH_KEY` 写入 GitHub Secrets 后，在 GitHub 页面执行 `Actions -> Deploy VPS -> Run workflow` 即可部署。

默认部署目录：`/opt/alchemy-media-agent`  
默认访问端口：`8017`
部署后会直接显示仓库内置的历史图片和案例参考图片。

如果你的图片供应商不是官方 OpenAI，而是 OpenAI-compatible 网关，比如 `https://aiself.vip/v1`，务必同时设置：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`

否则图片 provider 会默认直连官方 OpenAI，常见报错是 `Connection error.`。

另外要注意：

- `gemini_image` 已接入 Gemini `generateContent` 生图通道；生产环境需配置 `GEMINI_IMAGE_API_KEY`、`GEMINI_IMAGE_BASE_URL` 和模型 ID。
- `seedance` 目前仍是占位视频 provider，不是 live 视频入口。
- `docker-compose.yml` 已挂载 `./src_skeleton/.env:/app/.env`，因此运行时页面里改过的 provider/base URL 可以持久化到宿主机并在重建容器后保留。

建议直接按 `docs/21_密钥与部署配置.md` 里的“一次到位部署模板”和“冒烟验证”执行。
