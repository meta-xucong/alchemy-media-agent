# Doc290 - V3 共享 Brain 请求减负与可靠性优化开发规范

状态：正式开发规范；运行代码尚未实施，性能和真实出图尚未验收。

审计基线：`542d01fc1f9fcfcf3203d722b1c1a249f9e78a65`，2026-09-06。
适用层：V3 共享基础能力及其现有 Brain 适配器；普通版与专业版共同适用。
本轮交付：方案审计与开发文档，不包含运行代码、模型切换、真实调用、GitHub 推送或 VPS 部署。

## 1. 目标与结论

总目标：在不改变现有架构、用户意图、成片效果和证据权威的前提下，减少 Brain 的重复输入与无效输出负担，降低规划失败概率，使普通版和专业版使用同一套可诊断、有限时、无本地创意替代的链路。

本阶段目标：明确最小修改边界、尚缺证据、兼容规则和验收方法，供后续开发逐阶段执行。文档审计通过不等于超时问题已解决或产品已稳定。

**审计结论：方向合理，但原提案不能直接实施。** 应先测量正常入口的真实请求，再在已有紧凑规划与最终 Prompt 签发流程内去重；不能另造一层压缩服务、删除必需收据、盲目缩短时限，或以更换模型掩盖协议问题。

质量顺序：美感第一，真人感第二，其余优化不得破坏这两项；明确尺寸、人物/产品真值和用户禁止事项属于不可交换的硬约束。速度提高但美感降低，判定不通过。

## 2. 原方案审计与证据边界

| 项目 | 审计判断 | 正式修订 |
| --- | --- | --- |
| 通用减负，普通版和专业版不依赖更重模型 | 合理 | 先固定当前实际模型与路由，优化现有请求构造；不按模板切换所谓重型 Brain |
| 请求越来越重导致最近失败 | 证据不足 | 重复内容是待验证风险；不能凭代码行数、内部对象大小或一次失败确定因果和引入提交 |
| 新增语义压缩层或再调用一次 LLM 摘要 | 不采纳 | 复用现有 payload builder；程序仅投影可信事实，不新加模型、服务、语义中间表示或场景分类器 |
| 只发送已激活能力 | 前置阶段不合理 | 初次 Brain 必须看见模板允许的精简能力目录；激活后才可依据冻结 ledger 选择相关执行契约 |
| 输出仅保留最终 Prompt，其他字段交给服务端补 | 不采纳 | 语义规划与签发已有下游消费者；保留现有类型、必需字段、逐输出审批和绑定验证 |
| ID、digest、version 都不应进入 Brain | 过度概括 | 私有存储细节不应进入；但既有协议要求原样回签的身份和摘要必须保留，不能伪造或代签 |
| 降为固定短超时或只有一次总重试 | 证据不足且冲突 | 保留 Doc288 时限与现有不同层的有界恢复；先核对实际调用树和每次耗时 |
| 比较旧模型别名与规范模型名 | 不能证明模型差异 | 若最终映射到同一模型/账号，只是路由别名比较，不能据此得出换模型有效 |

已有诊断说明上游可以响应，也发生过返回内容不能解析为完整 JSON 的情况；这不等于“上游质量没问题”，也不等于“必然是本地 Prompt 太重”。必须区分连接、内容生成、传输完成、JSON 序列化、语义契约校验和最终签发失败。

此前将 `BrainRunRequest.model_dump` 大小称为完整 HTTP 请求大小的口径不成立。调用 `_run_llm_brain(..., resolution, None, stage="plan")` 而未提供正常入口的 pre-activation、catalog 和 policy，也不能充当生产等价复现。之前约 266 秒结束的 JSON 解析失败，不能直接标注为碰到 300 秒传输上限。

因此本规范不确认某次更新是唯一根因，不承诺改完永久无失败。后续结论必须关联确切提交、入口、请求指纹、失败类别和同条件对照结果。

## 3. 现有权威与调用链

本规范只新增“请求表达减负”的开发约束，不取代以下权威：

- [Doc76](76_V3_FOUNDATION_VS_SPECIALIZED_TEMPLATE_GOVERNANCE_SPEC.md)：共享质量与专业交付隔离。
- [Doc77](77_V3_REAL_VISUAL_REVIEW_AND_AESTHETIC_STABILITY_FOUNDATION_SPEC.md)、[Doc78](78_V3_LONG_TERM_IDENTITY_AND_BEAUTIFUL_REALISM_FINAL_TUNING_SPEC.md)：美感、真人感和稳定性。
- [Doc91](91_V3_HUMAN_REALISM_PLUGIN_GOVERNANCE_SPEC.md)、[Doc92](92_V3_STYLE_AWARE_HUMAN_REALISM_AI_FEEL_SUPPRESSION_SPEC.md)、[Doc93](93_V3_REFERENCE_CHANNEL_POLICY_AND_PROMPT_OWNERSHIP_GOVERNANCE_SPEC.md)、[Doc94](94_V3_UNIVERSAL_VISUAL_CAPABILITY_DEOVERFITTING_AND_GOVERNANCE_SPEC.md)、[Doc95](95_V3_UNIVERSAL_PORTRAIT_IDENTITY_EVIDENCE_AND_BEST_RESULT_CLOSURE_SPEC.md)、[Doc96](96_V3_HIGH_FIDELITY_PORTRAIT_IDENTITY_METRIC_AND_LOCAL_REPAIR_SPEC.md)：通用质量、参考继承和身份执行边界。
- [Doc145](145_V3_REMOTE_BRAIN_JSON_SERIALIZATION_RECOVERY_SPEC.md)：有限 JSON 序列化恢复。
- [Doc269 / E30](ecommerce_module/E30_DOC269_PHYSICAL_RENDERER_REFERENCE_PLAN_CONTRACT.md)、[Doc270 / E31](ecommerce_module/E31_DOC270_PHASE4_VIEW_AWARE_PRODUCT_SOURCE_ACTIVATION_CONTRACT.md)：专业电商产品真值和物理参考计划。
- [Doc281](281_V3_UNIFIED_SOURCE_LIBRARY_SMART_MATCHING_AND_DRIFT_RECOVERY_CONTRACT.md)：共同原图素材库、来源绑定及漂移闭锁。
- [Doc288](288_V3_BRAIN_PROGRESSIVE_TRANSPORT_DEADLINE_CORRECTION_SPEC.md)：当前传输和共享准备预算。
- [Doc289](289_V3_GENERAL_VARIATION_EXECUTION_COMPATIBILITY_CONTRACT.md)：General 多图差异化及逐输出签发回执。

基线代码已经存在以下流程，不新增同义的“轻量 Brain”旁路：

```text
正常项目命令 / Native 专业入口
  -> 服务端请求、引用和模板权威
  -> runtime: 预激活事实 + eligible capability catalog + policy
  -> adapter.build_request
  -> 紧凑语义规划: VisualTaskProfile + 能力意图 + ImageSetPlan
  -> 验证语义结果、执行能力激活、冻结约束
  -> 现有 canonical Prompt finalizer 签发完整逐图 Prompt 和必需收据
  -> Provider 物理输入验证与生成
  -> 现有 Review / Output / Slot / 前端投影
```

这是两个语义职责，不是保证永远只有两次 HTTP 调用：序列化恢复、语义重答和既有签发子阶段可能增加调用，均受原共享预算约束。`plan` 与 `generate` 还会经过准备或冻结结果复用，必须按实际路径统计，不得把复用误算为新调用或再次开启无效规划。

| 现有位置 | 权威与本次用途 |
| --- | --- |
| [product_api/service.py](../app/product_api/service.py) `_runtime_request_payload` | 组装正常可信请求；只读跟踪，不把内部持久模型误当公共 API 请求 |
| [scenario_runtime/runtime.py](../app/scenario_runtime/runtime.py) `_prepare_capability_execution_within_brain_budget`、`_run_llm_brain` | 保留 pre-activation、目录、policy、冻结复用和共享预算 |
| [llm_brain/adapter.py](../app/llm_brain/adapter.py) `build_request`、签发结果验证 | 用户输入目前直接传入；保留必需语义字段、回执消费者及有限恢复 |
| [llm_brain/prompts.py](../app/llm_brain/prompts.py) `system_prompt_for_stage`、`_compact_remote_creative_payload`、`build_remote_payload` | 已有紧凑真实请求；优先在此清理重复说明，不制造第二套协议 |
| [llm_brain/prompts.py](../app/llm_brain/prompts.py) `_canonical_provider_prompt_finalization_payload` | 已有冻结签发上下文；只保留该阶段必需输入，保持结果格式 |
| [llm_brain/providers.py](../app/llm_brain/providers.py) `run`、实际传输构造 | 区分网络、流完成、JSON 和 budget；采集真实消息指标，不改变路由 |

## 4. 必须保留的边界

### 4.1 Brain 与程序分别负责什么

Brain 负责理解当前需求、参考语义与继承权、人物/年龄/风格适用性、能力选择、构图、机位、动作、灯光、审美和完整 Prompt。专业模板继续规定专业套图的角色和交付范围；Brain 在该范围内创作，不重定义冻结的产品/参考权威。

程序仅负责认证、来源可用性、已有类型校验、精确身份/摘要绑定、确定性字段投影、Provider 能力校验、状态和时间预算。结构化数据是现有协议载体，不是本地创意决策器。

禁止新增按提示词正则、关键词、题材名单或固定摄影配方决定能力、画面、尺寸、肤色、身份继承。也禁止靠删门禁、降低质量阈值、伪造成功回执来提升“成功率”。

### 4.2 输入减负规则

| 输入种类 | 处理规则 |
| --- | --- |
| 当前用户原文 | 完整保留，不为预算截断、改写、概括或删除明确细节；包含尺寸、比例、数量、禁止事项和字面文字要求 |
| 有效项目方向和约束 | 只取当前命令需要且权威有效的部分；删除重复序列化副本，不丢弃真实的延续约束，不导入完整失败历史 |
| 参考语义事实 | 保留当前可用且经授权的证据、用途和渠道权威；去重只针对同一事实，不能因来源图相同就合并不同继承权 |
| 初次能力发现 | 提供模板允许的精简目录及已有可信预激活事实，保留 Brain 发现“产品图中有人”等跨场景需求的能力 |
| 激活后执行规则 | 按实际冻结 ledger 与签发契约投影；不得由本地场景识别替代适用性判断，不移除负责发现适用性的基础规则 |
| 专业交付事实 | E-Commerce、Photography、Character Card 等只带本模块必要角色、数量和真值事实；不得进入 General 默认规则 |
| 绑定 ID、摘要、版本 | 仅保留现有验证协议确实消费的字段；必须原值传输/回签，不自创短 ID 映射，不让 Brain 计算来源哈希 |
| 路径、凭据、存储快照、重复全量 schema 和历史流水 | 不新增到 Brain；需要本地校验的完整事实留在原权威层，不以缩短请求为由删持久证据 |

主用户输入在当前 builder 中已直传，不能为了“修复截断”无证据重写入口。现有 `_compact_text` 等截断工具只可在逐字段审计证明该字段是可裁剪辅助说明时使用；新减负不得扩大到用户要求或身份关键事实。若发现原有必要字段被裁剪，先写失败回归和字段权威说明，再作最小修复。

“历史图不进入原图匹配”不等于禁用当前合法的 generated-selected 延续或首张自动人物锚点。经既有权威确认的项目锚点、解绑/重绑、真实上传原图与历史候选的区别必须保留；不新增历史图自动晋升入口。真实参考仍通过原物理通道传给图像 Provider，不能用文本摘要替代。

### 4.3 Prompt 规则去重方法

先建立一张审计用对照表：`原说明 -> 所属权威 -> 适用阶段 -> 保留位置 -> 对应回归`，不建立新的运行时规则库。

优先删除同阶段 system / user payload 中重复的序列化要求、同义规则和无消费用途的说明。某条语义规则从一个位置移除时，必须在同一所需阶段保有等义、可见的权威表达；“另一个阶段会看到”不自动构成等价。

首轮不缩减 `_compact_required_remote_creative_schema` 或 finalizer 返回类型，不删除字段，不改 required/optional 条件。没有重复的部分可以不改，禁止为了达到缩短百分比拼凑改动。

Human Realism 的美感、表情、材质、参考所有权和风格保真不得统统替换为“高质量、自然、真实”。保持用户指定的主色、冷暖、明暗、电影/胶片风格和氛围；不能用统一高调补光、肤色处理或反差偏好换取写实感。

多图保留 Doc289 的逐图差异意图和精确 digest 回签；尺寸继续由 Brain 理解明确用户要求，网页选项只在未指定时补缺。本规范不新增支持尺寸、不改变 Provider 路由能力，也不改变图像裁切策略。

### 4.4 输出与历史兼容

- 保持 `BrainRunRequest`、规划结果、canonical Prompt 和回执的现有协议形状；逐输出数量、索引、语义审批和身份绑定均不降低。
- 保留最终签发必需的 user-direction integrity、reference ownership、human-naturalness、专业约束和 variation execution 等实际启用回执。完整名单须由开发者从当前消费者导出，不能把这几个例子当作穷尽清单。
- 服务端只能按已有契约绑定机械事实，不能补写 Brain 未返回的 `approved`、语义决策或创意内容。缺失和伪造仍按原规则失败。
- 首轮是兼容的说明文字/输入投影调整，不迁移历史记录、不重签旧收据、不清理原输出、不使旧有效签发失效。新请求、现有运行中 checkpoint、失败终态重放和新命令仍遵从原身份及冻结复用规则。
- 若方案实际上需要新增字段版本、改变签发输入绑定、必需字段或缓存有效性规则，立即停止该项实施，补充迁移与旧任务兼容设计后重新审计；不能夹带在 Prompt 去重补丁中。

## 5. 时限、恢复与失败分类

继续采用 Doc288：单次 Brain 默认 300 秒、最大 360 秒，共享准备预算默认 520 秒，Native MCP 规划父边界默认 540 秒；显式配置及派生预算按该文档执行。传输可用窗口不得超过共享剩余预算，不回退到 210 秒，不自动延长，也不预先改成更短的数值。

首轮不调整 `max_tokens`、流式模式、重试次数、模型或网关路由。先记录现有值和实际调用树，避免同时改变多个变量。已知的 provider JSON 重答与 adapter 语义重答是不同边界，不能各称“一次”就推断整个流程最多一次重试。

基线调用图有以下条件上界，必须保留并在阶段 A 验证，而不是增加一个全局重试器：

| 层 | 基线行为 |
| --- | --- |
| Provider 序列化恢复 | 每次 `provider.run` 最多两次 remote attempt，第二次用于既有 JSON/明确输出截断恢复；不是 HTTP/超时通用重试 |
| 规划语义重答 | strict contract 拒收后最多再调用一次 `provider.run`，该阶段理论最多四次 attempt |
| Canonical finalizer | 特定 anchor-view 缺失或 `BrainPromptContractInvalid` 可触发一次重答，该阶段理论最多四次 attempt |
| Professional capture re-sign | 满足现有 capture-continuity 条件时另有独立签发，理论最多两次 attempt；不是新增恢复，也不是所有专业任务必经 |

普通两阶段上述分支理论合计最多八次，具备额外 capture 条件时最多十次；这是静态条件上界，不是失败探针实测，也不是八/十倍时间预算。所有分支仍共享同一剩余 deadline。显式 Responses 模式不支持时的协议适配请求另行计数，不混作创意恢复。

现有 `remote_brain_call_count` 来源于 transport-history，不能直接当作全部 HTTP attempt 数；需核对回执的 `attempts` 和被替换的失败签发。在现有 dispatch/trace 边界补足测量，不借此重写调度。Native 父 deadline 的终止/取消和 Character Card 限域兼容分支保持原边界，不能推广为 General 或电商的本地创意 fallback。

| 失败类别 | 必须区分的证据 | 本次处理原则 |
| --- | --- | --- |
| 连接/HTTP/认证 | 状态码、开始到响应头耗时、规范化错误码 | 不当作输出 schema 问题；回到所属传输/上游层诊断 |
| 首个可用内容迟到或流中断 | 响应头、首个 content、reasoning/content 类型、最近进展、结束信号 | 心跳字节不等于完整内容；不把 reasoning 文本拼进 JSON；不越过共享预算 |
| JSON 不完整/不合法 | finish reason、结束信号、解析错误位置、响应长度 | 保留原有有界序列化恢复；不使用正则修 JSON、猜字段或本地补语义 |
| JSON 合法但语义契约无效 | 被拒绝字段、binding/digest、阶段 | 使用既有同一冻结请求的有限重答；不恢复已无效来源，不伪造签发 |
| 最终签发不通过 | 具体回执与完整 Prompt 的校验结果 | 保留原责任层，不绕过 finalizer 直达图像 Provider |
| 共享预算耗尽 | 剩余预算、此前调用累计、终态分类 | 停止新 Brain 和图像请求；不得后台继续同一未受控调用 |

规划失败后不得再对 blocked Job 调用 generate 来“探一下”，更不能把由此产生的第二次错误算成独立业务重试。解析失败、预算耗尽、无输出和像素复核未通过必须分开统计。本规范不增加任何自动生图或质量重试。

## 6. 修改范围

首选修改面仅为现有 `llm_brain/prompts.py` 及对应测试：去重说明、复用同一份现有规则定义、在已经拥有适用性事实的阶段投影必要上下文。

仅当测量或失败回归证明有必要时，允许在既有 `adapter.py` / `providers.py` 中修正紧邻的字段传递或补充脱敏计时；不得借机改业务结果类型、恢复算法或模型选择。若需修改 runtime、公开 schema、Native 调用边界或专业模块权威，先提交具体调用链证据和修订范围，独立审计后才能开发。

明确不在范围：新压缩服务、新 LLM 阶段、复杂路由器、模型自动切换、场景规则库、Review 阈值、身份/产品门禁、图像 Provider 参数、Slot 语义、前端重构、自动重试策略、V1/V2、Veyra/Sub2API、部署配置和历史数据清理。

## 7. 实施阶段与闸门

### 阶段 A：生产等价基线与假设核对

1. 从唯一 main 的最新已同步 SHA 建独立 worktree，记录 dirty 状态并保护其他工作；不在旧证据目录或旧分支继续开发。
2. 用隔离测试存储和现有服务入口构造同样的服务端请求，保留 catalog、policy、预激活、来源/命令绑定；在真正 HTTP/SDK dispatch 前替换传输并截获最终消息。不得创建生产 Job、候选、输出、handoff 或 slot。
3. 分开测量 system 文本、user JSON、完整传输 body 的 UTF-8 字节、字符、框架说明占比、逐图输出 schema 体积。token 只有在获得相同 tokenizer 或上游 usage 时才能称实测；估算须标注。
4. 用同一请求证明阶段字段完整、参考所有权不变、被省略部分没有消费者。签发阶段可以用既有确定性合法 fixture 推进，但必须标注这是离线模拟，不是上游成功证据。
5. 对历史失败精确匹配项目 ID、命令、创建时间、来源指纹、提交与阶段，核实生产记录；不得仅凭截断项目标题复用另一个项目。受保护原始证据不提交仓库，报告只保存必要脱敏统计。
6. 列出现有 provider/adapter/finalizer 的恢复分支、最大调用数与共享 deadline 传递。记录每次序列化重答是否又进入语义恢复，确认无预算重置。

闸门：只有确定重复或错层信息的具体位置，并有保真回归后，才进入阶段 B。若请求本来已简洁、失败来自上游/流处理，则记录“请求减负不是已证实根因”，转向所属层修订方案，不能继续删内容。

### 阶段 B：一次最小完整修复

1. 先提交失败测试或基线快照，明确希望减少的重复项以及保持不变的输入/输出字段。
2. 按第 4 节对照表只改重复项；使用已有 builder，不新建抽象层，不改变调用次数。
3. 对修改后的完整消息进行一次独立审计，而不只审查较短的局部字符串。
4. 运行阶段 C 矩阵；出现两处以上跨层失配时停止补丁/重试循环，重新画权威和生命周期图。

闸门：保真与故障边界测试通过，且测量显示真实框架冗余确实减少。不可通过截断用户信息或降低契约要求达到指标。

### 阶段 C：离线回归与有界传输模拟

覆盖第 8 节矩阵；模拟成功、慢流、流截断、invalid JSON、合法 JSON 缺字段、错回执、预算耗尽和取消。用固定时钟或短测试时限验证，不用真实等候数分钟代替逻辑测试。

闸门：关键不变量全部通过；区分环境问题与真实失败并保留证据，不能把未归因失败简单归类为“历史问题”。无外部请求是本阶段硬边界。

### 阶段 D：受控真实验收

只有离线审计通过、真实调用边界明确并得到相应授权后才进行。沿用正常前端对应后端入口，不直接调用缺上下文的私有 Brain 方法。使用已核实的历史失败场景及至少三个实质不同的共享质量场景，覆盖 General 和至少一个专业模板；专业 Character Card/MCP 未实际验证时，单列为未验收，不用 HTTP 成功代替。

固定当前模型、实际路由、图片 Provider、提示词、参考、数量和尺寸。一个案例先验证规划和签发成功，再允许一次计划内生成；已失败的任务不被强推到后续阶段。记录人工重试和所有失败，不能挑成功样本。

每张输出对照原提示词与基准图人工评估美感、真人感、氛围/色彩、身份/产品保真、尺寸/主体完整、多图差异和前端最终可见性。缺少同条件基准只能标注“可用样本”，不能宣称质量提升或无回归。

闸门：只有阶段 A-C 和真实链路验收均通过，且用户审美要求未降低，才申请集成。出现错误先归因，再决定下一次受控验证；不无限生成到碰巧成功。

### 阶段 E：集成与发布

开发 worktree 先同步/rebase 最新 `origin/main`，重复受影响回归并独立复审；由唯一 main 集成者处理集成。GitHub/VPS 变更需要相应发布授权，不能从本文推导授权。

发布前核对目标 SHA、镜像内容与运行中模块、配置来源；不改 Veyra/Sub2API、V1/V2 设置或路由。若共享容器更新涉及服务重建，按既有发布规程保护 bridge 环境、挂载和回滚点。部署后分别检查版本、健康、桥接会话和 V3 正常入口；健康 200 不代表已出图成功。保留旧已验证 release 和用户历史，失败则按既有机制回滚代码版本，不删业务记录。

## 8. 必要测试矩阵

| 类别 | 必测行为 |
| --- | --- |
| 原文保真 | 长提示词、中文/英文、引号/换行、末尾硬条件、精确文案；原文不被截断或摘要代替 |
| 数量与画幅 | 单图、2/3 图，Doc289 的 2..16 协议边界；明确比例/尺寸优先、未指定时网页补缺；不新增四图限制 |
| 能力发现 | General 无人景物、单人/群像、商品本体、产品上身；未预激活 Human Realism 仍能由 Brain 从允许目录发现适用性 |
| 美感与风格 | 至少三类明显不同场景，包括低调氛围和明快画面；不把暖色/高调/磨皮/过度锐化作为统一答案 |
| 来源与延续 | 无上传、上传原图、合法首图自动锚点、显式 selected-output、解绑重绑、多图以首图为锚点；来源缺失/错项目/错 SHA 不被压缩掩盖 |
| General 差异化 | suite/exploration 契约到最终签发保持每图目的、不同机位/动作的语义空间；digest/索引/回执不丢失；不回灌历史固定 Prompt 配方 |
| 专业隔离 | E-Commerce 产品真值/Doc269/E31 不变；Photography 保留角色；Character Card Face/Expression/Body 的正式 slot 权威不变；General 不加载专业交付表 |
| 输出契约 | 必需字段、空列表、optional 条件、审批和逐图数量正确；缺失/交换/伪造签发仍失败；不能由服务端补语义 approval |
| 冻结与生命周期 | 同一合法 checkpoint 复用；来源/命令变化不得错用旧结果；blocked plan 不再 dispatch；旧历史只读和新运行契约均正确 |
| 传输与恢复 | HTTP错误、慢 content、reasoning-only、EOF/DONE、length、invalid JSON、语义拒绝、取消、预算耗尽；不叠加新重试或重置 deadline |
| 跨入口 | HTTP 与 Native MCP 使用一致共享契约；无 mock/兼容路径误入真实生成；本地与模拟 VPS 环境显式配置不污染 fixtures |

优先复用以下现有回归文件，新增 Doc290 测试只补本规范新增的请求等价性和负担指标，不另造一套生成测试框架：

- [test_v3_llm_brain_adapter.py](../tests/test_v3_llm_brain_adapter.py)
- [test_v3_llm_brain_provider_timeout.py](../tests/test_v3_llm_brain_provider_timeout.py)
- [test_v3_doc162_bounded_brain_contract_recovery.py](../tests/test_v3_doc162_bounded_brain_contract_recovery.py)
- [test_v3_doc161_reference_ownership_brain_signoff.py](../tests/test_v3_doc161_reference_ownership_brain_signoff.py)
- [test_v3_doc175_remote_brain_prompt_availability.py](../tests/test_v3_doc175_remote_brain_prompt_availability.py)
- [test_v3_variation_compatibility_contract.py](../tests/test_v3_variation_compatibility_contract.py)
- [test_v3_doc269_ecommerce_physical_renderer_reference_plan.py](../tests/test_v3_doc269_ecommerce_physical_renderer_reference_plan.py)
- [test_v3_doc281_unified_source_library_smart_matching_phase0.py](../tests/test_v3_doc281_unified_source_library_smart_matching_phase0.py)
- [test_v3_photography_llm_first_mainline_005.py](../tests/test_v3_photography_llm_first_mainline_005.py)
- [test_v3_ecommerce_product_truth_provider_scope.py](../tests/test_v3_ecommerce_product_truth_provider_scope.py)

这不是穷尽测试清单。阶段 A 必须从实际签发消费者补齐专业身体比例、年龄/人物存在、自然度、Doc136/165 签发恢复、capture-continuity、Doc289、Native deadline/取消及正式 slot 相关回归；新增组合恢复 attempt 计数和共享 deadline 不重置测试。不能只跑 General 单图就宣称专业版通过。

## 9. 指标、审计与完成条件

### 9.1 每个阶段保留的脱敏测量

记录：提交 SHA、入口/阶段、实际模型与路由标识、单次/共享预算、请求指纹、消息字节/已知 token、响应字节、调用序号、响应头耗时、首个有效 content 耗时、完整响应耗时、解析/校验耗时、finish reason、恢复原因、剩余预算和最终结果。

使用既有诊断/trace 扩展，不引入监控数据库。任何 request fingerprint 都不得包含可公开回推的密钥；完整用户输入、图片字节、私有路径、Cookie、Authorization 和生物特征不进入普通日志或 Git。时间统计必须包括失败和恢复，分清“规划准备”和“生图+复核总时长”。

### 9.2 通过标准

1. **正确性**：第 8 节关键不变量全部通过，所有必需消费者字段保持；没有引入本地语义捷径、schema 放宽或隐藏失败。
2. **减负**：对阶段 A 固定案例，真实消息中已确认的重复框架内容减少，完整用户输入与必须事实等价。阶段 A 完成后冻结各案例的基线和目标；不得事后挑案例，也不预设“必须压到 N KB”的硬截断指标。
3. **可靠性**：原失败类型有可复现回归和前后对照；真实验收未再出现同一已修缺陷。少量成功样本仅证明这些样本通过，不证明永久成功或可靠的 p95；统计报告写明次数、失败分布和尚未覆盖路径。
4. **性能**：相同环境和模型下分别比较正常请求、恢复路径和全链路耗时；输入更短但调用数增加或尾延迟明显恶化，不得自动判优。上游拥堵/账号路由变化必须作为混杂因素披露。
5. **效果**：用户明确意图、尺寸、身份/产品真值和多图差异合格；成片美感不下降，真人感不以改氛围/主色/面部美感为代价。自动分数仅辅助，保留人工并排评估。
6. **集成**：最新 main 集成态回归、获授权的发布和真实入口验收均通过，才能宣称相应范围完成；未运行的入口必须列出，不能称“全绿”。

### 9.3 开发与独立审查分工

主控维护本规范、批准最小阶段和验收边界；一个开发者负责隔离 worktree 的代码；一个独立审查者只读核对文档、完整请求、diff、回归和质量证据。文档审计阶段可由主控撰写、独立审查者复核，不提前启动运行代码开发。

每次审核固定提交或文件 SHA，结论采用“符合 / 不符合 / 证据不足”。发现删用户意图、删必需收据、专业规则泄漏、额外 LLM、扩大重试或修改 bridge/Sub2API，立即发出 `AUDIT_FIX_REQUIRED`，暂停受影响阶段。修改后复审对应部分，不沿用旧版批准。

阶段完成报告必须写：影响范围、验证方法及结果、提交 SHA、push 状态、未验收项和下一阶段。当前文档完成后的下一步是阶段 A，不是直接换模型、缩短超时或发布 VPS。
