# Custom Media Agent 2.0 文档包

本目录是 2.0 版本的独立开发文档包。它不属于旧版 `custom_media_agent_docs`，也不沿用旧版后端功能边界。

## 当前口径

先读：

1. [00_CURRENT_ARCHITECTURE.md](docs/00_CURRENT_ARCHITECTURE.md)

当前 V2 已从早期 **OpenAI Agents SDK-first** 方案演化为：

```text
确定性业务流水线
+
Claude Code 创意中枢
+
可替换模型源 / 备用模型源
+
SDK-compatible tool boundary
+
V2-native provider/storage/history/review
```

因此，旧文档中关于 `Runner.run(CreativeManagerAgent)`、SDK 接管主链路的表述，均作为历史设计参考，不再代表当前代码事实。Claude Code 仍是创意中枢；Kimi / 火山 / DeepSeek / 豆包是 Claude Code 背后的模型源或备用源。后续开发以 `00_CURRENT_ARCHITECTURE.md` 为准。

2.0 的当前定位：

1. 使用确定性后端 pipeline 承担业务主链路和副作用执行。
2. 使用 Claude Code Orchestrator 生成结构化创意决策；Kimi / DeepSeek / Doubao 等只作为 Claude Code 模型源。
3. 使用 OpenAI Agents SDK 作为可选 planner capsule、function-tool boundary、structured output 与 tracing 的未来接入点。
4. 当前第一个 ResourceProvider 是 `EvoLinkAI/awesome-gpt-image-2-API-and-Prompts`。
5. 2.0 仅与原版共用域名和前端入口，功能、后端、数据、任务队列、资源同步和运行时全部独立。

## 快速阅读顺序

1. [00_CURRENT_ARCHITECTURE.md](docs/00_CURRENT_ARCHITECTURE.md)
2. [00_总览与边界.md](docs/00_总览与边界.md)
3. [01_PRD与成功指标.md](docs/01_PRD与成功指标.md)
4. [02_系统架构：SDK-first 历史方案与当前 Claude Code 中枢口径](docs/02_系统架构_OpenAI_Agents_SDK优先.md)
5. [03_Agent运行时设计.md](docs/03_Agent运行时设计.md)
6. [04_ResourceProvider与同步服务.md](docs/04_ResourceProvider与同步服务.md)
7. [05_案例智能与模板库.md](docs/05_案例智能与模板库.md)
8. [08_API接口与前端集成.md](docs/08_API接口与前端集成.md)
9. [12_开发任务拆解与里程碑.md](docs/12_开发任务拆解与里程碑.md)
10. [13_测试验收标准.md](docs/13_测试验收标准.md)
11. [15_迁移隔离策略_仅共用域名和前端.md](docs/15_迁移隔离策略_仅共用域名和前端.md)
12. [17_Claude_Code中枢与VPS部署方案.md](docs/17_Claude_Code中枢与VPS部署方案.md)
13. [18_稳定化可观测与质量闭环开发文档.md](docs/18_稳定化可观测与质量闭环开发文档.md)
14. [19_V2上传图片与TemplateLock开发文档.md](docs/19_V2上传图片与TemplateLock开发文档.md)
15. [20_V2彻底独立模块化重构开发文档.md](docs/20_V2彻底独立模块化重构开发文档.md)
16. [21_Claude_Code速度优化开发文档.md](docs/21_Claude_Code速度优化开发文档.md)
17. [24_架构纠偏方案_Creative_Orchestrator_Hybrid_Runtime.md](docs/24_架构纠偏方案_Creative_Orchestrator_Hybrid_Runtime.md)
18. Veyra 生产登录门禁、匿名访问收紧和来源回跳方案见 [`../docs/30_生产登录门禁与来源回跳开发文档.md`](../docs/30_生产登录门禁与来源回跳开发文档.md)。

## 文档结构

```text
custom_media_agent_2_0_docs/
  README.md
  sources.json
  docs/
    00_总览与边界.md
    00_CURRENT_ARCHITECTURE.md
    01_PRD与成功指标.md
    02_系统架构_OpenAI_Agents_SDK优先.md  # 历史文件名，内容已按当前 Claude Code 中枢口径修正
    03_Agent运行时设计.md
    04_ResourceProvider与同步服务.md
    05_案例智能与模板库.md
    06_Tools与DomainServices契约.md
    07_数据模型与状态机.md
    08_API接口与前端集成.md
    09_安全合规与授权风控.md
    10_质量评测与炼金闭环.md
    11_部署配置与运行模式.md
    12_开发任务拆解与里程碑.md
    13_测试验收标准.md
    14_Agent提示词与结构化输出模板.md
    15_迁移隔离策略_仅共用域名和前端.md
    16_开发前ReadyChecklist.md
    17_Claude_Code中枢与VPS部署方案.md
    18_稳定化可观测与质量闭环开发文档.md
    19_V2上传图片与TemplateLock开发文档.md
    20_V2彻底独立模块化重构开发文档.md
    21_Claude_Code速度优化开发文档.md
    24_架构纠偏方案_Creative_Orchestrator_Hybrid_Runtime.md
  specs/
    openapi.yaml
  diagrams/
    system_architecture_v2.mmd
    agent_runtime_graph_v2.mmd
    resource_sync_state_v2.mmd
    image_generation_sequence_v2.mmd
    deployment_isolation_v2.mmd
  templates/
    creative_run_result.example.json
    image_prompt_plan.example.json
    prompt_case.example.json
    resource_provider_manifest.example.json
    safety_decision.example.json
```

## 非目标

2.0 不做以下事情：

1. 不训练新模型。
2. 不复制旧版后端。
3. 不让 agent 直接访问数据库、API key 或对象存储。
4. 不把外部案例的原图直接当作客户最终商用资产。
5. 不让 agent 或 SDK 直接执行 provider、数据库、存储、扣费等副作用。

## 开发口径

开发时默认使用 `/api/v2` API 前缀、`v2_` 数据表前缀、独立 Redis namespace、独立对象存储 prefix 和独立 trace project。旧版仅保留域名与前端 shell 的复用价值。
