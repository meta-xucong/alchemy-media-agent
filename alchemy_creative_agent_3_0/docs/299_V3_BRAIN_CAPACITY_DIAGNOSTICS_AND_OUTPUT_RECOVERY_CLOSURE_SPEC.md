# V3 Brain 容量、请求归因与输出恢复闭环收口规范

状态：本地实现、确定性验收与独立审计完成；部署后 VPS Brain 探针和四模式受控真实任务已通过链路验收，`creative_exploration` 的 Doc276 人工确认仍待完成（2026-09-12）
范围：V3 foundation 的 LLM Brain transport/adapter、finalizer lifecycle、Product API 输出恢复与 Project Mode 选择恢复。
上游参考：Doc286、Doc288、Doc290、Doc294、Doc296、Doc297、Doc298，以及仓库 `AGENTS.md` 的 theory-first、code-first audit 和 Core/Enhanced/Auxiliary 分层规则。

本规范是 Doc298 的实施收口补充。它只覆盖 Brain 响应容量/归因、finalizer 生命周期和 job-scoped 持久化输出恢复；Doc298 的外部元数据隔离、执行 envelope、closure 和模式投影规则仍然有效。关于 Brain 输出容量的规则以本规范为准。

## 1. 总目标与本阶段目标

总目标是让同一份原始提示词从本地或 VPS 的正式 V3 入口执行时，能够保留用户意图和已激活模块，并在 Brain、Provider、review、模式投影和重启恢复之间形成可审计的单一事实链。

本阶段目标：

1. 让复杂的结构化 Brain 请求有足够的输出预算，不因推理 token 耗尽而被误报为“Brain 不可用”；
2. 把“本地调用已进入”“请求已被上游接受”“上游开始返回”“返回合同不合格”区分开；
3. 让 finalizer 在响应合同失败时仍保留完整的生命周期证据；
4. 让 Project Mode 在进程重启后只从当前 project 所属 job 的真实、可读取 output record 恢复选择和参考上下文；
5. 通过本地确定性回归和一次部署后的 VPS 受控真实请求验收，不用重复真实生图掩盖控制流问题。

## 2. 理论先行：证据、偏差与责任层

### 2.1 VPS Brain 证据

测试使用冻结的原始提示词，只记录长度和 SHA-256，不把正文写入日志：

| 事实 | 结果 |
|---|---|
| UTF-8 字符数/字节数 | 2196 / 5420 |
| 原始提示词 SHA-256 | `f37928b680e56b7258583f0ab27b4232ea5bafe68703d3fb8628bde3b6a5d2d7` |
| `GET /v1/models` | 200，约 86 ms |
| 最小 Chat Completions（stream/non-stream） | 200，约 1.5–2.2 s，正常结束 |
| 简化 production-shape stream | 200，约 5.8 s，但输出块为空并以 `length` 结束 |
| 完整 production-shape，`max_tokens=12000` | 200，约 171.6 s，`finish_reason=length`，completion 达到 12000 |
| 相同请求，`max_tokens=20000` | 200，约 90.8 s，`finish_reason=stop`，completion 约 6284 |

这组证据说明：Aiself/DeepSeek 路由和鉴权不是普遍不可达；复杂请求确实能返回，但旧 12000 上限会在部分采样中被推理消耗。旧链路的 read timeout、没有首个内容块和长度截断共同造成了“不可用”表象。不能仅凭这一组数据断言 Aiself 内部或 DeepSeek 下游的具体实现故障，但可以确认本地旧容量默认值不足以稳定承载该合同。

### 2.2 本地已确认的责任边界

| 偏差 | 责任层 | 修复方向 |
|---|---|---|
| Brain 进入 SDK 调用就被记为 dispatched | transport diagnostics | 只有显式 accepted/status/response 证据才能记为 dispatched；否则 unknown |
| finalizer 的 request stage 是 `generate` 时 lifecycle 被 sanitizer 丢弃 | adapter/finalizer lifecycle | lifecycle 使用固定 `provider_prompt_finalize` 边界，creative stage 仍留在事件和普通审计字段 |
| Brain 已返回但 canonical prompt 合同失败时没有 lifecycle | adapter response validation | 外层 finalizer boundary 为所有响应校验失败补 dispatched/response_started 证据 |
| output record 已落盘但 Job 没有 candidate projection，重启后选择上下文为空 | Project Mode recovery adapter | 仅对显式 selector 查询当前 job 的 output store；唯一、可渲染记录才能恢复 |
| 只凭像素记录恢复 GENERATED | Product API/output closure | 继续由 immutable output、mode envelope、review/delivery closure 共同决定恢复状态 |

这些问题分别属于 Auxiliary 诊断/恢复适配器和 Core 状态投影边界。恢复适配器不能改变 formal slot、模式或 Brain 创意所有权，也不能用本地创意文本替代必需的远程 Brain 签名。

## 3. 权威修复模型

### 3.1 Brain 输出预算

- `V3_LLM_BRAIN_MAX_TOKENS` 默认值为 `20000`；显式配置范围为 `512..32768`，越界由服务端 clamp。
- 该值只控制远程 Brain response budget，不改变用户提示词、能力激活、模块合同或 Provider image 参数。
- 共享 logical execution budget 仍为 520 秒，单次 transport timeout 仍由既有 300 秒默认和安全上下界控制；提高 output budget 不是无限等待授权。
- 仍保留一次 JSON/长度恢复和一次瞬态 transport retry，二者共享 logical budget；不增加无界重试。
- 对真实图片请求，Brain 失败仍 fail-closed，不得用本地 deterministic creative fallback 冒充 Brain 结果。

### 3.2 Stream/JSON 合同

Chat Completions stream 解析器必须支持：

- 单行 `data: {json}`；
- 多行 SSE `data:` event，空行 flush；
- `[DONE]`、注释/heartbeat 和历史 raw-JSON 兼容输入；
- 只收集 renderer 所需的 `content`，reasoning 只参与长度/诊断，不进入最终 prompt。

响应必须有 `[DONE]`、有效 JSON object 和 exact-N canonical prompt records。禁止通过截取 JSON 前缀、删除尾部或正则拼接来“修复”不完整响应；失败应进入有界的 remote semantic/JSON recovery，恢复失败后阻断并保留安全 receipt。

### 3.3 请求接受状态

生命周期事实按以下顺序解释：

```text
request_call_entered -> request_acceptance(not_started|unknown|dispatched)
                      -> response_started -> first_content_observed
                      -> complete_response_observed -> json_parse_completed
```

- `request_call_entered` 仅表示本地线程进入 SDK/HTTP 调用；
- `not_started` 表示有明确的本地发送前失败或 provider 未启动；
- `unknown` 表示调用已进入但没有足够证据判断是否发送/接受；
- `dispatched` 只由明确请求发送、HTTP status、response context、首个响应或等价 transport 证据导出；
- timeout/read error 不能因为 call entry 自动升级为 dispatched；
- finalizer lifecycle 的 `stage` 固定为 `provider_prompt_finalize`，而 `BrainRunRequest.stage` 仍用于 creative-stage 审计。

### 3.4 Project Mode 的持久化输出恢复

选中结果的权威短路径仍为：

```text
explicit selector -> current project job binding -> output_store record
                  -> renderable/file integrity check -> selected OutputRef
                  -> ProjectContext selected_reference_assets
```

恢复适配器必须满足：

1. 只读取已经通过 `_ensure_project_job` 的当前 project/job；
2. 只有显式 candidate、asset 或 output selector 才触发 output-store fallback；
3. selector 必须在该 job 内唯一命中，匹配不到或多重命中都不得替换为兄弟输出；
4. 文件、preview、thumbnail、download URL 均需可用，且由 canonical output resolver 验证；
5. 只有完整 output record 才能写入 `generated_selected` reference；恢复不能伪造 planning candidate；
6. closure 缺失时仍不得把 output-only record 投影成普通 GENERATED；本条只修复显式选择/参考恢复，不放宽交付闭环。

## 4. 实施边界与禁止事项

实现位于 V3 foundation/runtime：

- `llm_brain/providers.py`：预算、SSE、JSON、transport receipt；
- `llm_brain/adapter.py`：finalizer response boundary 和错误归因；
- `llm_brain/finalizer_lifecycle.py`：固定 lifecycle contract；
- `project_mode/service.py`：job-scoped output recovery adapter；
- `product_api/outputs.py` 与 `product_api/service.py`：immutable output/closure；
- `.env.example`：仅公开非敏感预算配置。

Project Mode 的公共 response 也统一经过安全投影：mutation 返回中的 project/context/reference/feedback/proposal，以及 Job route 返回中的 ProductJobStatus，均不得绕过公共 projection 直接 `model_dump`。本地回归已覆盖该边界；VPS 真实验收仍待部署后执行。

不允许借此把电商、童装、摄影、超市场景或某个历史 prompt 变成 shared default；不允许把内部 prompt、API key、endpoint、candidate storage path 或完整 reasoning 写入公共 receipt；不允许通过提高阈值、重复重试或放宽审查来伪造成功。

## 5. 本地验收与独立审计证据

- Project/Brain 焦点回归：`167 passed`；
- 全量 V3 + 根目录回归：`3673 passed, 4 warnings`；
- `compileall`、`git diff --check`：通过；release staging hygiene：`2 tests OK`；
- 最终独立只读审计：Brain lifecycle、Runtime/Product fail-closed、Project Mode 公共响应投影均 PASS；
- 以上是部署前证据，不能替代 VPS 健康检查、Brain 探针、原始 prompt 受控真实生成和图像质量复核。部署后上述链路已执行；其中一个模式的图像因人脸一致性 attestation 不可验证而保留人工确认状态，不能把该模式报告为自动交付通过。

## 6. 验收矩阵

### 6.1 本地确定性验收

必须通过：

- Brain provider timeout/transient recovery 及既有 adapter contract tests；
- exact-N canonical prompt、SSE 多行/单行/[DONE] 和 strict JSON tests；
- finalizer generic/contract failure lifecycle tests；
- external Create/Generate server-owned metadata injection tests；
- output closure immutable hash/index tests；
- restarted Project Mode selection and persisted partial-output tests；
- mode execution projection aggregation tests；
- `compileall`、`git diff --check`。

浏览器 Playwright 验收是独立环境门槛；若依赖未安装，只能报告未运行，不能把它标成通过。

### 6.2 VPS 受控真实验收

部署后按以下顺序执行（本轮已完成第 1–5 项）：

1. 健康检查和 `/v1/models`；
2. 最小 non-stream/stream Chat Completions；
3. 原始 prompt 的完整 production-shape Brain 请求，核对 prompt SHA、`max_tokens`、finish reason、content/JSON 完整性和安全 lifecycle；本轮 `max_tokens=20000`、`deepseek-v4-pro`、约 139.8 秒完成，完整 receipt 通过；
4. 使用真实 V3 入口跑目标项目的四个生成模式，检查 Brain source projection、能力模块 receipt、canonical prompt 长度和 Provider 输入；四个任务均 `generated`，每个都有真实输出和完成的 pixel review，但 `creative_exploration` 因 `face_integrity_unverified` 保留人工确认；
5. 失败时只保留 append-only safe audit，不自动重复真实生图；需要重试时必须先修复/验证代码假设；
6. 只有本地测试、部署后链路、四模式交付状态和真实输出视觉复核都通过，才能报告总目标完成；当前还不能越过 `creative_exploration` 的人工确认门槛，也未完成浏览器端可视化复核。

VPS 证据只记录 job id、attempt id、prompt SHA、耗时、token 用量、finish reason、request acceptance 和状态，不记录 key、完整 prompt、response body 或 reasoning 原文。

## 7. 当前阶段结论

在本规范对应的代码收口前，旧 VPS 证据已经足够证明“Brain 请求不可用”不是单纯本地无法连接，也不是单纯把 Aiself 判活失败；它是上游长复杂请求的输出容量/长尾行为与本地诊断、恢复边界缺陷叠加的结果。

本规范的实现通过后，必须重新执行一次部署后的真实请求来确认 20k budget 下是否能稳定取得完整合同。若仍失败，receipt 应能直接区分：

```text
本地未启动 / 接受状态未知 / 上游已接受但超时
/ 上游响应已开始但截断 / 合同返回不合格 / 本地响应校验错误
```

部署后真实 Brain 探针和四模式链路目前证明：上游可达、复杂请求在 20k budget 下可完整返回、Alchemy 能正确记录 lifecycle 并让四种模式分别落盘；这不等于所有输出均已自动交付。`creative_exploration` 的 `face_integrity_unverified` 必须经过真实用户/浏览器确认后才能关闭剩余验收门槛。
