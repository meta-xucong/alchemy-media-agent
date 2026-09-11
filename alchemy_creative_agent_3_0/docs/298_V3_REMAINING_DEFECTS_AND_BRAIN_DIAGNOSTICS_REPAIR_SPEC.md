# V3 剩余边界缺陷与 Brain 不可用诊断修复规范

状态：本地实现、确定性验收与独立审计完成；VPS 健康、Brain 探针、原始提示词与四模式受控真实链路已执行。`creative_exploration` 的 Doc276 人脸一致性人工确认仍待用户验收（2026-09-12）
范围：V3 Product API、LLM Brain transport/adapter、V3 generated-output restore  
上游参考：Doc290、Doc293、Doc294、Doc296、Doc297，以及仓库 `AGENTS.md` 的 theory-first、code-first audit 和 Core/Enhanced/Auxiliary 分层规则。

## 1. 总目标与本阶段目标

总目标是让相同原始提示词在本地和 VPS 上经过完整的 V3 入口时，能够：

1. 保留用户提示词及其附加模块意图；
2. 由已配置的 Brain 完成需要远程创意决策的阶段，失败时明确、可审计、fail-closed；
3. 让各生成模式、能力激活、候选和输出恢复读取同一份服务端权威执行事实；
4. 不因重试、崩溃恢复或外部伪造元数据而产生错误的 GENERATED、错误的模式或错误的 Brain 请求归因。

本阶段不重新设计 Brain 创意提示词，也不放宽重试/超时阈值。只修复已经由代码审计确认的边界缺陷，并用确定性回归测试和一次受控真实验收验证。

## 2. 观察到的偏差与层归属

### 2.1 Brain “不可用”不是单一故障

只读探针显示：VPS 容器中的 `GET /v1/models`、最小 Chat Completions 请求、最小 streaming 请求均可通过 `aiself.vip` 返回 200；简化的 production-shape 请求也可返回。此前相同原始提示词的完整生产请求曾出现“已收到响应/开始流式响应，但未观察到完整 JSON”的长尾读取超时；在本次部署后的 `max_tokens=20000` 受控探针和真实 V3 任务中，Brain 均取得了完整合同。

因此当前证据支持的结论是：

- 不是本地 Alchemy 完全无法访问上游；
- 不是 Brain 路由或鉴权的普遍失败；
- 更接近上游网关/其下游 DeepSeek 生成链路对高复杂度、长上下文、结构化 JSON 请求的长尾响应或截断问题；
- 本地仍存在状态归因和边界信任缺陷，会把“调用已进入但是否被上游接受未知”错误说成 dispatched，或在没有证据时说成 Brain 已开始请求。这些本地缺陷必须修复，否则无法可靠区分上游问题。

### 2.2 已确认的六类本地边界缺陷

1. 外部 Create 元数据可注入伪造的 Brain lifecycle receipt，并被公共 status 投影。
2. 外部 Generate 元数据可替换服务端执行 envelope；当前默认逻辑还可能把有冻结计划的请求自动当成 trusted reuse。
3. finalizer 收到没有 typed transport receipt 的 `BrainProviderUnavailable` 时，会默认 `remote_brain_request_started=True`。
4. transport timeout/connection error 仅因进入 SDK 调用就被提升为 `request_dispatched=True`，混淆“未启动”和“接受状态未知”。
5. image 文件先落盘、模式 envelope/审查/交付闭环后落盘。进程在中间退出时，restore 仅凭像素记录就返回 GENERATED，并且只信任第一条 output record。

6. Project Mode 的部分 mutation/worker HTTP 响应曾把原始 `ProjectRecord`、`ProjectContextPackage`、`feedback` 或 `ProductJobStatus` 直接序列化，绕过统一公共投影，存在执行元数据泄露和跨出口语义漂移。

归属：1、2、5 是 Product API/persistence Core 边界；3、4 是 Brain transport/adapter 的 Auxiliary 诊断边界，但会污染 Core 的失败归因和用户可见状态；6 是 Project public projection 的 Auxiliary 边界，但会污染公共安全契约。

## 3. 权威模型

### 3.1 外部输入与服务端事实

浏览器/API 请求只能提供用户意图、类型化图像选项和上传资产选择。以下内容永远由服务端生成或从当前 job 的持久记录恢复：能力计划、执行 envelope、resolved ledger、Brain lifecycle/transport receipt、provider/review/delivery closure、模式执行投影和 provenance。

外部入口必须拒绝这些 server-owned keys，而不是静默合并。内部 continuation 必须经过显式 trusted seam，并以当前 source job 和计划 fingerprint 绑定。

### 3.2 Generate 的信任边界

普通 Generate 不得从请求 metadata 读取或写回任何执行权威。它只能使用当前 job 已持久化的 request metadata 和 typed image options。只有服务端内部 continuation 才能显式传递 trusted reuse，并且必须验证：

- `issued_for_job_id` 与当前 source/job 身份绑定；
- envelope 的 `execution_fingerprint` 与 capability plan/ledger 的 fingerprint 一致；
- reuse 的 source job、plan id、plan fingerprint 与持久记录一致。

不满足时 fail-closed，不创建新的生成意图，不改写当前 job 的模式。

### 3.3 Brain 请求生命周期

请求生命周期必须分别记录：

- `request_call_entered`：本地线程进入 SDK/HTTP 调用，仅为本地控制流事实；
- `request_acceptance`：`not_started`、`dispatched` 或 `unknown`；
- `response_started`/`first_content_observed`/`complete_response_observed`：上游响应事实。

仅凭 `request_call_entered` 不得推导 `dispatched`。没有 status/response-context/明确 transport accepted 证据时，超时或连接异常应为 `unknown`（若客户端在发送前失败则为 `not_started`）。最终 public projection 必须保留 acceptance，旧 boolean 只能由明确 `dispatched` 证据导出。

finalizer 遇到没有 typed receipt 的 `BrainProviderUnavailable` 时，`remote_brain_request_started=False`；不得用“provider.available 已返回 true”替代请求生命周期证据。

### 3.4 Output restore 的闭环一致性

`output.json` 的可见 GENERATED 资格不是“文件存在”，而是：

`像素记录 + server-owned mode envelope + review/delivery closure receipt(status=complete)`。

写入顺序或恢复策略必须保证 crash window 不会把未审查输出发布成 GENERATED。若输出已存在但闭环 receipt 缺失/无效，restore 应返回保守的 BLOCKED/needs-recovery 投影，保留只读诊断和可恢复的 output identity，但不提供已完成交付语义。

多个 output record 恢复时必须聚合并验证共同的 job/execution fingerprint，不能因第一条记录缺失投影就丢弃后续有效事实，也不能接受互相冲突的 envelope。

## 4. 最小完整修复方案

1. Product API：建立统一的 external-ingress server-owned metadata guard；Generate 禁止 untrusted metadata merge；trusted continuation 增加 job-bound provenance/envelope integrity 校验。
2. Brain provider/adapter：引入显式 request acceptance 状态，修复 timeout/exception 归因，保留安全 attempt receipt；finalizer 无 receipt 默认未开始。
3. Output store/Product API：定义安全的 durable closure marker；在 restore 时严格验证模式 envelope、closure 状态和跨输出一致性；对 crash-window 输出保守阻断。
4. Regression tests：增加 hostile Create/Generate、call-entered-before-send、no-receipt finalizer、partial output restore、multi-output mixed projection 测试。
5. Project public response：统一 `ProjectRecord`、`ProjectContextPackage`、`ProjectReferenceAsset`、`ProjectFeedbackRecord`、`ProjectBrandMemoryProposal` 和 `ProductJobStatus` 的公共投影；HTTP route adapter 不得直接序列化未经投影的 Job status。
6. 真实验收：修复和独立审计通过后才重跑原始提示词；一次完整请求失败时用 receipt 区分本地 preflight、上游 acceptance unknown 和上游完整响应失败，不再反复生成作为 exploratory debugger。

## 5. 验收证据

本规范完成的必要证据：

- 相关回归测试全绿，且覆盖上述六类缺陷；
- `compileall`、`git diff --check` 通过；
- 独立只读审计确认没有新的 server-owned ingress、public projection 或 restore 绕过；
- 当前本地证据：Project/Brain 焦点回归 `167 passed`，全量 V3 + 根目录回归 `3673 passed, 4 warnings`；`compileall`、`git diff --check`、release staging hygiene `2 tests OK`；最终独立审计 PASS。上述均为部署前证据，不代表 VPS 已验收；
- VPS 部署前后服务健康检查通过；
- 原始提示词 SHA-256 仍为 `f37928b680e56b7258583f0ab27b4232ea5bafe68703d3fb8628bde3b6a5d2d7`；
- 真实 Brain 失败时能明确给出 `request_acceptance`、timeout phase、response/JSON 进度，而不泄露 prompt/body/provider 原文。

部署后 VPS 证据（2026-09-12）：

- active release 为 `/opt/alchemy-media-agent-releases/v3-release-governed-20260911T201923Z-4db73233b331`，代码提交为 `4db73233b331cdadef86fd74c902d67d8ee32579`；`/healthz`、`/api/v2/health` 和容器内 V2 health 均返回 200，V2 systemd 单元保持 active。
- `aiself.vip` `/v1/models`、最小 non-stream/stream Chat Completions 均成功；完整 production-shape Brain 请求使用 `deepseek-v4-pro`、`max_tokens=20000`，约 139.8 秒完成，receipt 依次包含 dispatched、response_started、first_content_observed、complete_response_observed、json_parse_completed，无 recovery。
- 四个真实 V3 任务均使用冻结原始提示词（2196 字符、5420 字节、SHA-256 `f37928b680e56b7258583f0ab27b4232ea5bafe68703d3fb8628bde3b6a5d2d7`），且持久化 `effective_variation_mode` 分别为 `selection_candidates`、`delivery_suite`、`creative_exploration`、`format_layout_adaptation`；四个 Provider prompt 指纹互不相同。
- `selection_candidates`（`job_eb091e7eca`）、`delivery_suite`（`job_431ce8844e`）和 `format_layout_adaptation`（`job_c4275eea02`）各产生 1 个有预览/缩略图的输出，Brain `llm_used=true`、无 fallback，真实像素审查为 pass、推荐保留。
- `creative_exploration`（`job_4da79ed1ab`）也产生了有预览/缩略图的真实输出，Brain 和模式质量均通过，视觉审查报告核心要求满足；但因 `face_integrity_unverified` 被置为 `manual_review`，不自动重试或自动交付。这是 Doc276 的安全人工确认门槛，不是上游不可达。
- 本次每个模式请求 1 张图；多图模式的正式 variation contract 仍以本地确定性测试为依据，未把单图真实运行夸大为多图套图最终验收。浏览器端可视化复核因当前 CUA 浏览器不可用，未标记为通过。

阶段通过不等于总目标完成；只有本地回归、独立审计、部署后探针和受控真实验收全部完成，才可报告最终可用。

## Addendum — Doc299 实施收口优先级（2026-09-11）

后续代码审计确认，原文“本阶段不放宽重试/超时阈值”的表述不能覆盖一个独立的
Brain response-capacity 缺陷：同一冻结请求在 VPS 上使用 12000 output tokens
时可达到 `finish_reason=length`，使用 20000 时可正常 `stop`。因此，Brain
输出预算、finalizer lifecycle 固定 stage、响应合同失败归因和 job-scoped
持久化输出选择恢复，统一由
`299_V3_BRAIN_CAPACITY_DIAGNOSTICS_AND_OUTPUT_RECOVERY_CLOSURE_SPEC.md`
收口；Doc299 仅 supersede 本文对应的容量/归因段落，其余 server-owned
metadata、closure、mode projection 和 Core/Enhanced/Auxiliary 规则仍以本文为准。

本次部署后真实验收证明 Brain 链路可达且 20k budget 下可取得完整合同；但因一个模式仍处于 Doc276 人工确认、且浏览器端可视化复核未完成，本规范与 Doc299 仍不得被解读为“所有输出已自动交付”或“总目标已完成”。
