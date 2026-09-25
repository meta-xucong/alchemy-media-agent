# Alchemy API 与 MCP 统一接入架构方案

> 状态：架构评审定稿 v0.2（2026-09-25）。本版是开发约束，不是功能已实现或公网已可用的声明。
> 评审基线：`6e14dce54ee9c8b99e98a2d80a784bb2780eb8d1`；修订原 43 号方案，旧版本由 Git 历史保留。
> 总目标：API、Web、产品级 MCP 共享 V3 产品事实、授权与交付语义；保留既有本地 Codex 规划与 Materialization。
> 当前阶段：只评估和修订文档；不改业务代码、配置、依赖、部署和数据，不触发模型或生图调用。

## 一、定稿结论与最小架构

采用 **API-first、MCP-adapter、V3 单一业务核心**。API-first 是合同设计优先，不要求同进程 Web 绕行 HTTP，也不意味着 MCP 渲染执行等同普通 HTTP 传输。

```text
第三方服务 / SDK ── Public API /api/v1 ─┐
现有 Web ───────── Veyra Session ──────┼─ 共享产品访问入口 ─ V3 Product / Project / Asset 服务
产品级本地 MCP ─── stdio 适配器 ──────┘                      │
                                             现有 Brain / 冻结计划 / 执行 / 审核 / 选择 / 存储
                                                         │
                           服务端 Provider 或已授权本地 Codex Materialization
```

“共享产品访问入口”是现有 V3 服务前的薄授权与命令边界，不是新增微服务或第二个业务编排器。Project、Asset 等仍由各自现有服务负责，不把所有职责塞进 `V3ProductApiService`。

API 和 Web 同进程时调用同一入口；产品级 stdio MCP 首版通过配置的本地 `/api/v1` 调用，避免独立进程另开一套服务实例、锁和 Store。已有低层 MCP 继续使用既有冻结与 handoff 协议，不强行改成公共 API。

生产公共 API 首先提供服务端可自主完成的执行路径。公网请求不得隐式等待某台开发电脑的 Codex，也不得在 Provider 失败时偷偷切换到本地渲染。

首版不新增：MCP 生图引擎、API Provider Router、第二套审核器、第二套 Job 状态机、通用事件总线、完整组织权限系统、多个 SDK、远程 MCP 网关或跨机调度平台。

## 二、源码复核与原方案的必补项

以下是现状或新增方案风险，不把未开发的公共 API 风险误报为已经发生的线上漏洞。源码位置与行号对应评审基线，见第十五节。

| 复核事实 | 原方案缺口 | 定稿处理 |
| --- | --- | --- |
| 部分资源鉴权在 Web 路由；`get_job(job_id)` 不接收主体，若干 owner=None 分支允许本地兼容读取 | 直接复用 Service 不自动获得多用户隔离 | Public API 和产品 MCP 必须先进入共享授权边界，禁止匿名降级 |
| Web 异步规划先持久化 operation，返回时 `job_id` 为空 | generation_id 不能简单等同尚未存在的 Job ID | 复用 operation→Job 绑定，公开句柄保持稳定 |
| `begin_project_planning_operation` 遇到正在规划的项目直接返回当前操作 | 不同请求可能被错误合并 | 幂等按请求摘要判断；不同请求同项目忙碌返回冲突，不冒充重放 |
| 后台执行在 `main.py` 中使用线程池和进程内登记表，另有持久化恢复记录 | 返回 202 不等于持久队列和跨进程单次执行 | 共享调度入口，持久化接收和认领；首版限制单实例执行拓扑 |
| MCP handoff 路由主要判断连接源地址为 loopback | 同机反向代理、浏览器请求、错误转发头可能破坏“本地即可信”的假设 | 公网反代显式隔离，本地调用附带运行时授权，不只依赖 IP |
| V3 BalanceAdapter 仍是零费用估算桩；另有 Veyra 实际扣费入口 | “复用统一计费”不是现成的完整预占与结算合同 | 对账后接现有账务权威，不把估算或用量日志当作账本 |
| 当前 Job 枚举没有通用 canceled 状态 | 原方案直接列取消接口和 canceled，缺少实际能力依据 | 先实现真实安全取消边界，不能只改公开状态 |
| 输出下载路由按归属取文件；最终交付资格在其他产品投影中判断 | 直接包装 Store 或复制下载入口可能绕过审核交付集合 | v1 下载、选择、导出再次核验逐图交付资格 |
| 已合入受保护数据保留策略 `e98af145` | 新任务、素材、下载链接、Webhook 与清理策略未协调 | 使用既有保留策略并保护活动引用，公开过期语义 |

原方案中的“API 与 MCP 差别只有传输”收窄为：**产品请求与业务结果共享，渲染通道可有不同执行合同和可用性；不得因此形成第二套业务权威。**

原方案中的 `MCP → V3 Job/Output Store` 对照是职责说明，不是工具可以直接读写裸 Store 的授权。所有产品查询经资源鉴权和公共投影，所有写操作经现有业务入口。

## 三、唯一权威与访问边界

服务端身份解析产生不可由请求正文构造的主体：账户、调用者、凭证 ID、作用域、认证方式。首版账户对应已有用户和计费归属；Veyra 会话与 API Key 映射到同一账户。不要为了一个 tenant 字段先建设组织、成员和委托体系。

身份入口不同不改变权限：同账户、同作用域可以跨 API/Web/MCP 查到同一资源；不同账户必须拒绝。客户端 owner_id、tenant_id、veyra_user_id、local_default 以及嵌套 metadata 均不得成为授权依据。

`/api/v1` 首版只解析 API Key；Web Session 在旧 Web 入口解析。缺少或错误 Key 不得用浏览器 Cookie 兜底，也不能把两种凭证权限取并集。

Public API 必须始终认证，不受 `veyra_auth_enabled=false` 的本地开发开关影响。缺少 API 鉴权配置时关闭入口并返回明确错误，不能降级为 owner=None。旧无主记录默认不对外可见；迁移归属需可审计的服务端证明，不批量认领。

鉴权覆盖项目、Job、operation、素材、参考图、输出、复核预览、选择、导出、列表计数和分页游标。资源间还要验证从属关系：同属一个账户不代表任意输出都可选进任意任务。账户匹配不能代替素材授权、身份同意和内容使用约束。

新共享入口只统一产品操作的授权、参数转换与既有服务调用，不复制完整 V3 实现。Web 逐个接入经测试的同一边界，保留当前 Session/CSRF 保护和响应形状，不进行无必要的前端大改。

### API Key 定稿

Key 为高熵随机凭证，只显示一次；持久化不可逆校验值和安全前缀，支持撤销、过期与轮换，不记录完整 Key。首版管理能力放在已有经过登录与权限检查的用户/管理入口，不能提供匿名创建 Key。

最小作用域按读写区分：`generation:read`、`generation:write`、`asset:read`、`asset:write`、`project:read`、`project:write`、`output:read`、`selection:write`；复核预览另有 `review:read`。只有实际实现的操作才发放作用域，普通 Key 不授予人工审核放行或后台管理权。

轮换不改变账户归属；幂等不能因换 Key 失效。撤销后新请求和下载须拒绝；已受理任务由账户级授权及已有计费承诺处理，不自动反复认证旧 Key 或无声退款。任务若未进入受理承诺边界，执行前仍需核验授权和配额。

`alk_test_` 不代表天然免计费或模拟执行；没有真实隔离的测试环境就不发行测试 Key。API Key 只放 Authorization，不放 URL、提示词、MCP 工具参数或浏览器持久存储；不向任意用户提供的 base_url 转发凭证。

## 四、Public API 合同与首版资源范围

命名空间为 `/api/v1`，这里的 v1 是公开合同版本，不是项目中的 V1 生图引擎，也不承诺 OpenAI API 兼容。现有 `/v1`、`/api/v2`、`/api/v3/creative-agent` 保持兼容；禁止通配反向代理顺带发布全部旧路由。

| 阶段 | 新公开接口 | 边界 |
| --- | --- | --- |
| Phase 1 | GET /projects、/projects/{id}、/projects/{id}/outputs | 当前主体有权访问的现有项目和正式输出；分页先鉴权后计数 |
| Phase 1 | GET /generations/{id}、/generations/{id}/outputs | 读取稳定公开投影，不创建或自动重试任务 |
| Phase 1 | GET /assets/{id}、/assets/{id}/content、/outputs/{id}、/outputs/{id}/download | 素材归属与输出交付双检查；首版用鉴权流下载 |
| Phase 2 | POST /projects、POST /assets、PUT /assets/{id}/content、POST /assets/{id}/complete | 有界上传与不可变 ready 素材，复用原业务服务 |
| Phase 2 | POST /generations、POST /generations/{id}/selection | 异步接收、幂等、配额、可恢复执行、仅选择允许交付的输出 |
| Phase 2 受能力限制 | POST /generations/{id}/cancel | 仅已实现的安全取消阶段；未支持的阶段返回冲突，不伪造 canceled |
| 后续按需 | 项目修改/时间线、续作、导出包、Webhook 管理 | 复用已有明确业务语义后逐项开放，不将所有内部端点一次公开 |

表内路径均以 `/api/v1` 为前缀。导出若创建新包或记录，使用 POST 命令；GET 只能读取已有结果，不能偷偷触发长任务。首版逐图下载已构成最小交付闭环。

### 4.1 产品输入，不允许内部合同透传

生成输入保留 prompt、project_id、template、quality_mode、image_count、size 等产品参数；参考素材使用 `references: [{asset_id, role, notes}]` 表达当前用途，role 仅限现有产品支持值，引用库资产/人物身份需独立的现有授权绑定。此修改发生在尚未发布的 v1 合同，不影响现有 Web 接口。

`metadata` 收窄为可选 `client_metadata`（有数量/长度限制的字符串标签），只供客户关联，不转发给 Brain、Provider 或内部运行时；`client_request_id` 只用于关联，不替代幂等键。prompt 与用户素材 notes 按原意、原字符串保留，不能因 SDK、适配器或去重而改写。

拒绝未知字段和嵌套内部指令：provider/model、最终编译 Prompt、checkpoint、trusted_*、审核认证、winner、handoff/nonce、文件路径、凭证摘要、owner/tenant、内部超时/重试/执行通道。参数要正向白名单映射，禁止 `{**request.metadata}` 进入 V3。

template、size、count、quality 的产品别名必须显式映射到现有合同并有合同测试；不支持组合返回 422，不静默更换模板、尺寸、Provider 或绕过冻结计划。Phase 2 先开放 general；电商/摄影等按其现有模块验收门槛逐项加入，未开放返回明确不支持。

### 4.2 素材冻结

首版使用有大小和像素数上限的二进制上传，不接任意远程 URL、服务器路径、压缩包、SVG/HTML 或无限 Base64。核验实际文件类型、可解码性、尺寸、内容摘要和账户归属；文件名不是存储路径。分片和预签名上传延后。

同一 asset_id 仅在 uploading 阶段可写；complete 幂等，READY 后字节不可替换，换图获得新 ID。任务接收和执行均绑定授权素材版本/摘要；哈希或授权变化按原合同拒绝，不借机重写已签名 Prompt 或使用同 ID 新图。

### 4.3 状态必须拆清“运行”和“交付”

不建立 API 专用状态机。公开字段由既有 operation、Job、审核包、逐图最终交付集合和选择记录统一投影，API 和产品 MCP 不各算一套。

`status`：queued / planning / running / reviewing / action_required / completed / failed / canceled。
`delivery.status`：none / ready / partial / withheld；附 requested_count、generated_count、deliverable_count、review_count、selected_count。
`next_actions`：仅给当前调用者有权且服务端实际支持的操作，如补素材、查看复核、选择输出；不能返回内部路径、handoff 或后台放行入口。

有已交付图片但仍待人工确认时可以是 action_required + partial；全部确定结束且只有部分通过时可以是 completed + partial。只有证据不足不能投影成视觉质量失败；完成生成不等于允许交付，用户选择不等于审核认证。

`completed` 不要求调用者已经 selection，`partial` 不作为另一个会漂移的运行终态。原始内部状态保留；公共失败需区分输入/权限、Brain/执行不可用、质量问题、证据不足和取消，未知原因不猜。是否有部分交付独立于失败/取消原因。

## 五、异步任务、标识与幂等的完整边界

### 5.1 接收前后只有一个业务任务

Phase 1 已存在的任务允许以其 Job ID 查询；Phase 2 新异步任务以现有持久化 planning operation ID 作为 generation_id，Job 生成后保持原 generation_id 不变，通过已存在的 operation→job_id 关联查询。ID 是不透明标识，客户端不得解析前缀。

同一个 Job 的原始 ID 可作为兼容查询别名，但列表、计数、扣费和事件只计算一次；不得为了版本统一重新创建历史 Job。operation 终结后仍必须能按原 ID 查询，不能只依赖项目当前 operation 指针。映射只存引用，不保存第二套生成/审核事实。

POST /generations 应在完成认证、请求校验、幂等登记、必要配额承诺以及可恢复的任务接收后返回 202、稳定 ID、查询地址与建议轮询间隔；不能先同步等待 Brain 完成。提交到线程池不等于已持久受理。

project_id 缺省时由服务端创建账户名下普通独立项目，纳入同一幂等命令和现有保留策略；不再发明“短生命周期项目”隐式删除语义。任务创建失败不能遗留一堆重复项目；保留可恢复命令引用。

### 5.2 幂等不是重复请求字符串缓存

生成写入必须带 Idempotency-Key。作用域为服务端账户 + 操作种类 + API 合同版本 + key；不按 API Key ID 或 API/MCP 传输拆开。主体相同、业务请求相同且主动复用 key，返回同一任务；相同 key 不同摘要返回 409。没有共用 key 的两次显式创作是两项任务，不按相似提示词合并。

摘要覆盖用户 prompt/notes、素材及其已冻结版本、project、模板、尺寸、数量、品质、产品用途等实际参数。不得删否定词、重排有语义顺序的引用、截断文字或使用语义相似缓存充当幂等。client_metadata 是否参与摘要必须固定；本版参与，避免首次响应与重放回显不一致。

同一项目只允许一个活动规划命令，暂不增加项目并行 DAG；并发不同请求返回 `project_busy`，相同 key 由幂等层重放。同一 key 的并发接收须原子认领，不能依赖“先查再建”或进程内字典。

幂等记录跨进程重启保存，非终态不得过期；终态后至少保留 24 小时，既有任务 ID 的查询按资源保留期处理。保留期后不得承诺仍去重，客户端重试窗口须有明确合同。重复查询与重放不重复预占/扣费。

### 5.3 调度与崩溃恢复

优先把已有 Web planning/generation 调度抽为共享入口，保留它的 typed continuation、attempt 标识、watchdog 和恢复检查，不 import 整个 main.py 形成循环，也不为 v1 再写一套生成循环。

首版限定单应用实例、单执行权威和持久化目录；即便单实例也要有 durable 接收记录和重启恢复，不是纯内存任务。多进程/多实例上线前再建设共享认领与 fencing；未实现时由部署检查拒绝该拓扑，不靠文档口头约定。

HTTP 回包、持久记录和线程调度间不能假定有跨系统事务。用既有命令记录建立“已接收→可调度”的可恢复关系；崩溃后查已绑定 Job/attempt/扣费引用，不能直接再建一个。Provider 已发出但结果未知时进入既有不确定结果处理，禁止自动重发并重复计费。

确需新增小型事务存储时，只保存 API Key、幂等、配额承诺和执行认领的接入记录及业务引用；不复制 Job、输出或审核状态。技术存储选型由现有部署约束决定，不预先引入 Redis/Celery/事件总线组合。

## 六、取消、重试、续作与计费

取消是业务命令，不是前端改标签。初版仅承诺尚未开始外部消耗的 queued 命令安全取消；执行权威原子确认停止后才给 canceled。已 dispatch 的阶段无法安全停止时返回 409 `cancellation_not_supported_at_stage`，不能谎称成功或承诺必退款。

完成与取消竞争按持久化的最终裁决处理；已经完成不能改为 canceled。后续支持执行中取消时，需明确停止未来步骤、迟到结果的审计保留和结算，不抹掉已产生费用，也不让迟到回包重新开任务。

客户端网络超时使用同一 key 查询/重放，不自行增大任务数。内部重试沿用 V3 预算和既有审批边界；主动重新生成/续作是新命令，引用原输出并重新验权，不能用旧 key 修改原任务，不能直接复用客户端提交的冻结计划。

### 统一费用事实，而不是双重收费

首先核对现有实际扣费入口与 V3 执行通道。`V3BalanceAdapter` 的零费用估算不是生产结算能力，`record_veyra_usage` 的本地日志也不是资金权威；不得把两者包装成“统一账务已完成”。

首版继续以现有账户/余额服务为资金权威，接入层只做必要的并发配额与额度承诺。若 Veyra 不支持预占，要有经验证的本地预占加幂等结算方案，或限制灰度额度；没有可靠并发防超支和不确定扣费恢复时，不开放付费公共写入。

每个业务命令的估算、预占、扣费、释放和退款共享稳定业务引用；内部 Provider 重试也要关联同一账务事实，不能由 API 与下游各扣一次。费用金额不用浮点累计；计价版本在接收时固定，账务状态和实际图像质量分开。

明确 Brain、图像生成、审核、自动修复分别何时计入，MCP 本地渲染实际由谁承担费用；不能按返回图片数猜上游消耗。失败/取消不等于无消耗；支付接口回包丢失必须按幂等引用查证，不再次无条件扣款。

配额必须覆盖读取频率、下载带宽、上传字节/像素、单次图数与尺寸、排队数、运行并发、预算和存储，不只限 HTTP QPS。队列满应在接受前返回 429/503 和 Retry-After，不能无限堆内存。

## 七、审核、下载和选择统一出口

`post_generation_review_package` 及现有最终交付投影是质量和交付依据。Public API 的 serializer 只改字段名、删私有信息，不能重新计算 mock 分数或再造“全部通过/全部失败”规则。

默认 outputs 仅含有当前权限且允许最终交付的输出；未决项通过 review_items 的安全概要呈现。逐图精确 output_id 绑定，不能用 asset_id 或批次 ready 让其他图混入。手部/无脸适用范围、严格 True、缺失凭证关闭等既有规则必须保留。

GET download、选择、导出都要重复验证归属和当前交付资格，不能仅凭知道 output_id、存在物理文件或过往一次 pass 放行。`review:read` 可获得受控复核预览，不赋予正式交付或管理员复核通过权限；selection 不得将 manual_review 变为 pass。

首版使用鉴权文件流；短期签名 URL 后置，届时绑定具体输出/变体、权限用途与到期时间，不指向内部路径。签名 URL 属可转交的临时能力，需定义撤销/审核状态变化后的有效性和短 TTL；不能号称签名后永远实时鉴权。

客户端可回读自己有权查看的原始创作输入，不代表可看内部系统提示、冻结 Provider Prompt、推理过程或供应商返回。默认摘要不带原文；日志、错误、Webhook 也不包含 Key、nonce、原始人物素材、服务器路径和私有合同。

## 八、MCP 保留与产品化边界

### 8.1 三类工具分开标识，不混淆完成语义

| 类别 | 既有/计划工具 | 权威与输出 |
| --- | --- | --- |
| 本地对话规划 | prepare_native_imagegen_plan、prepare_frozen_specialized_native_imagegen_plan、prepare_frozen_professional_native_imagegen_plan | 保留；conversation-only，可调用既有 Brain，但不伪装正式 Job/交付，也不隐式导入对话图片 |
| 本地执行交接 | prepare_shared_mcp_materialization、submit_shared_mcp_materialization | 保留；服务于已有 V3 handoff，客户端只按冻结合同渲染，提交成功不等于审核通过 |
| 产品级工具 | alchemy_create_project、alchemy_upload_asset、alchemy_create_generation、alchemy_get_generation、alchemy_list_generation_outputs、alchemy_get_project、alchemy_select_outputs | Phase 3 新增薄映射；调用共同产品入口，返回相同 ID、状态和安全 next_actions；导出工具随导出能力后置 |

“低层工具不得直接访问 Provider”指不得绕开既有规划/交接而另外启动图片 Provider；已有 conversation-only 工具调用 Brain 的能力保留。对话规划的外部费用沿用其明确的本地凭证/配置，不因为没有 Job 就宣称免费或补造虚假平台扣费。

产品 MCP 与 Web/API 一样受账户、scope、配额、计费和逐图交付规则约束。stdio 是传输方式，不是账户授权。只读工具不触发生图；写工具说明持久化/费用影响并依赖宿主的用户授权，不按名字就授予管理权限。

### 8.2 本地文件与低层必要例外

产品级 API 和远程 MCP 只认素材 ID，不接服务器路径。本地 stdio 上传工具可读取用户明确授权的本机文件，将字节提交上传服务；限制可访问根目录、文件类型/大小、符号链接/路径越界及 UNC 网络路径，不能遍历用户电脑或直接写媒体 Store。

低层 Codex 渲染工具必须收到精确冻结 Prompt 和已授权的引用路径，这是受信渲染执行所需，不适用“公共投影绝不返回 Prompt/路径”的笼统禁令。范围只限当前 handoff 及允许的素材，不可把此返回结构转发到公网或混入产品工具普通结果。

handoff 的 nonce、Prompt hash、素材 hash、rendering fingerprint、跨进程锁、pending/submitted/consumed、单次消费与恢复继续由现有 owner 维护。产品 wrapper 不重新签名、不改模板/身份约束、不生成第二套 nonce，不把超时直接当作需要新 Job。

### 8.3 loopback 必须是真正的网络与身份边界

公网反向代理明确拒绝 mcp-materializations、local-runtime 及内部管理端点；应用公网监听不注册低层路由，或使用独立本地监听器。不能因反代来自 127.0.0.1 就把外部请求认作本地授权。

本地手工指定 base_url 与自动发现都须绑定允许的运行时身份/目录；不能只在自动发现路径做身份核验。运行时增加最小本地认证能力，凭证放受保护描述文件或受控配置，不出现在工具输出。nonce 是提交合同字段，不代替入口认证。

校验 Host/Origin、禁用不必要跨域和重定向；代理头只信任显式可信代理。检查浏览器跨站访问本机接口、DNS 重绑定及公网→本机反代路径。无需开发整套本地用户管理，但 IP、可猜 ID 和 runtime_id 都不能单独证明授权。

### 8.4 产品级 MCP 的协议与执行可用性

首版 stdio 工具对长任务快速返回 generation_id，后续轮询与继续操作；不把 MCP 客户端一次工具超时当作任务已取消。重放必须沿用同一命令的幂等键，不把 JSON-RPC 临时 request id 当成永久去重键。

复用当前实现时补测初始化协议协商、tools/list 与实际参数验证一致、标准 JSON-RPC 错误、UTF-8、输入大小和 stdout 只输出协议消息。只声明实际支持的协议版本；不直接回显未知客户端版本作为协商成功。工具的只读/破坏性提示不能代替授权。

Public API Phase 2 只调度服务端可完成的路径。将来产品 MCP 发起本地 Codex 渲染时，必须明确已连接且已授权的本地执行者；等待渲染者属于 action_required，产品只给安全下一步动作，真正 handoff 留在本地控制面。

远程产品 MCP 与远程渲染 worker 是两项不同能力。前者适配产品 API；后者涉及上传、认领、nonce 和执行者权限，不能借“远程 MCP”直接发布现有本地 handoff。

## 九、错误、分页与兼容性

公共响应至少包含 request_id，任务响应另含 generation_id/project_id、status、delivery、next_actions、更新时间或版本。错误使用稳定的 code、message、request_id、retryable；无原始异常堆栈、Provider URL/密钥或内部 Prompt。内部诊断可保留更细事件，受管理员授权。

401：缺少/失效凭证；403：作用域不足；404：不存在或不可见资源；409：幂等内容冲突、项目忙碌、选择版本冲突或不支持的取消阶段；413：超限上传；422：产品请求不支持；429：配额/速率限制；503：入口/执行能力暂不可用。已受理任务随后失败体现在任务资源，不把原 202 事后改成 HTTP 错误。

轮询返回 Retry-After，客户端退避并设最长等待；网络中断不会创建新 Job。只读查询不得触发 Brain、Provider 或恢复性重新生图；现有超时终结等惰性维护必须受原生命周期控制且幂等，不变成 GET 触发新工作。

列表使用有界 cursor/limit、稳定排序和账户绑定的游标，过滤后再返回计数；不可利用其他用户游标或总数推断资源。selection 使用资源版本或等价并发校验，保持已有业务基数，不凭接口复数名称允许任意数量 winner。

以 OpenAPI 和对应合同测试冻结 v1；公共枚举、错误语义和必填字段变动属于版本兼容评审。新增内部 V3 字段不自动进入公开响应。测试须检查响应完整白名单，而不只搜索几个敏感字段。

## 十、Webhook、SDK 与远程 MCP：冻结原则，推迟实现

Phase 1/2 以轮询闭环为准，不创建空 webhook.py、空 SDK 包或事件平台。没有公开回调功能时不接受 callback_url，避免暗中启用新的外部请求路径。

Webhook 启用前必须同时具备：已认证的账户级订阅；HTTPS 目标及出口限制；DNS/解析后地址校验，拒绝 loopback、内网、链路本地、云元数据地址及重定向绕过；限制请求大小、耗时、并发和响应体。不得只检查 URL 字符串一次。

Webhook 使用原始请求体、时间戳和事件 ID 的 HMAC 签名，独立密钥、轮换窗口和接收方重放防护。投递按至少一次设计，event_id 稳定去重，attempt_id 区分投递尝试；不承诺严格有序或恰好一次，消费者按资源版本处理乱序并可轮询校正。

事件只能由持久化业务变化产生，不由每次 GET 临时触发。使用最小持久 outbox/投递记录并与业务写入建立可恢复关系；有界退避、重试上限、失败记录及显式重放。回调失败不回滚已完成图片、不重开生成。事件仅带公共概要，不带下载密钥和敏感源数据。

SDK 后置，优先一种实际需要的语言，复用 OpenAPI；超时、错误映射、幂等键持久化与轮询退避必须先稳定。不能自动为同一失败重试换 key，也不能把网络超时解释为支付/生成没有发生。

远程 MCP 后置。采用实施时明确验证的协议版本及授权要求，不能把“API Key 或 OAuth”当成所有 MCP 客户端都兼容。面向第三方授权委托时设计 OAuth 资源范围、受众及撤销；平台内部受控客户端可使用绑定账户的凭证，但不复用上游 Provider token。

## 十一、保留策略、兼容旧数据与可观测性

复用 `e98af145` 引入的现有保留设置，不新增 API 专属定时删除器。活动任务、待消费 handoff、来源/选中依赖、未完成结算和有效幂等引用必须列入清理保护；过期策略与任务最大时长、回调重试窗口一致。

下载链接到期与资源删除是两回事。文件过期后任务摘要、合法计费/审计记录按各自政策保留；有权限且能证明原记录存在时可返回 410，否则仍 404。不能为了兼容查询重建已删输出。保留时限未确定时不虚报永久可下载或精确 expires_at。

复用现有环境级保留设置，但上线前核对管理员更新对公共 API 的影响。历史无主资源默认隐藏，不能因之前 Web 本地模式可读而直接面向所有 Key 发布。

请求日志关联 request_id、generation_id、operation_id、job_id、execution attempt、账户和凭证安全标识；handoff 关联仅供内部审计。记录实际 dispatch/结果未知/审核/交付/扣费边界，不能编造上游已收到的事实。

最小指标：接收/排队延迟、规划/生成/审核耗时、队列拒绝、幂等冲突、跨账户拒绝、不确定调用、可交付/待复核计数及结算异常。默认不记录完整用户提示、素材 URL 或人脸数据；需要诊断时单独授权和限期保留。

## 十二、代码分层与防止过度开发

在现有 `product_api`/`project_mode` 旁补共享主体、资源授权和命令入口；现有服务继续处理业务。公开 HTTP 包仅按需求增加 routes、schemas、auth 和 serializers；幂等/配额/调度共用接入服务，不各在 API 和 MCP 复制一份。

本地产品 MCP 增加 product_tools 薄客户端即可；不新增 product_projections 再计算推荐或质量，最多整理已经授权的公共结果。现有 materialized_bridge 只补必要本地安全检查，保持合同兼容；不重写生图、审核和恢复机制。

每一新增模块必须对应不可由现有 owner 承担的职责和验收用例；不为“未来可能需要”建空目录、插件层、通用工作流 DSL 或组织账本。需要改共享合同的工作单独列出兼容测试，不伪装成仅新增路由。

首版不改 V1/V2 生图；不把 V2 task_queue 搬来成为 V3 的第二套任务系统。不重写前端，不强迫现有 Web 立即使用第三方 API Key；当前登录、选图、复核、素材绑定和数据保留行为均需要回归。

## 十三、实施阶段及明确退出门禁

| 阶段 | 必须交付 | 明确不做 | 进入下一阶段条件 |
| --- | --- | --- | --- |
| Phase 0 合同/安全准备 | 固定主体映射、输入/输出白名单、ID/状态/错误映射、计费责任表、部署信任边界、单实例约束和故障点测试设计 | 生图行为变更、发布公网接口 | 本文阻断项有 owner 和验证方式；认可新增接入权限/持久化不是已存在能力 |
| Phase 1 只读接入 | Key 创建/撤销/过期、共享授权入口、只读项目/任务/素材/输出、鉴权下载、OpenAPI、请求 ID、分页与读取限流 | 上传写入、生成、取消、Webhook、远程 MCP | 跨用户/无主数据不泄漏；旧公开路径不能绕过保护；不触发执行；与 Web 正式交付集合一致 |
| Phase 2 异步生成最小闭环 | 项目创建、上传完成、稳定 generation_id、持久幂等接收、共享调度、并发额度、统一结算、轮询、允许范围的选择/取消 | 多节点执行、所有专业模板、批量 SDK、回调系统 | 崩溃重启无丢单/重建；同 key 不双 Job/双扣；不确定 dispatch 不自动重发；general 真实正负例通过 |
| Phase 3 本地产品 MCP | 产品工具映射同一 v1 服务、受控本地上传、任务恢复；本地低层 MCP 安全收口和兼容回归 | 公网 handoff、独立 Store/Reviewer、本地自动兜底生图 | 同账户跨入口互查，同 key 可重放；既有冻结/nonce/hash/恢复/审核通过；本地/公网隔离通过 |
| Phase 4 独立按需里程碑 | 每项分别评审并交付：Webhook、首个 SDK、更多模板/续作/导出、多租户组织、远程产品 MCP | 一次性打包所有扩展 | 对应真实需求、授权协议、风险与测试具备；不把 Phase 4 当作首版必选依赖 |

Phase 0 的 loopback 暴露风险如果当前公网配置已存在，应先作为小型安全修复处理，不等 Phase 3 才修；本轮未读取 VPS 配置，不能声称线上已有或已不存在该暴露。

Phase 1 可以上线只读；Phase 2 才可声明对外生成 API 可用；Phase 3 才可声明产品 MCP 与 API 的同权限闭环。每个阶段只报告自身结果，不能用旧 V2/V3 测试通过数替新 API/MCP 验收。

## 十四、测试与验收矩阵

| 验收面 | 必测条件与预期 |
| --- | --- |
| 身份/Key | 缺失、过期、撤销、轮换、作用域不足；关闭 Veyra 浏览器认证仍不得开放公共 API；换 Key 不改变账户幂等 |
| 资源隔离 | 账户 A 访问 B 的项目/任务/素材/下载/复核/选择/导出/游标均拒绝；混合引用跨项目输出也拒绝；旧无主数据不公开 |
| 请求隔离 | 内部 metadata、owner、路径、认证和 handoff 注入拒绝；用户 prompt/notes 保真；尚未开放模板无静默降级 |
| 持久幂等 | 同 key 并发、响应丢失、进程重启、不同 Key 同账户；最多一次业务接收和结算；同 key 内容变化 409 |
| 项目并发 | 不同请求同时规划同一项目不能误返回同一任务；缺省项目不重复建；历史 operation→Job 可恢复查询 |
| 调度故障 | 认领前后、落 Job 前后、外部 dispatch 前后、扣费回包前后的故障注入；无未知结果盲目重发、无内存丢单 |
| 取消/续作 | 未 dispatch 可取消；取消完成竞争有确定结果；已开始但无法停止时不伪造成功；续作重新鉴权、不覆盖父任务 |
| 审核交付 | 一张 pass 一张 manual 独立交付；缺失/字符串/数字认证拒绝；只读 outputs 与下载/选择/导出资格一致 |
| 人物与产品 | 无脸商品、手部、明确人脸的现有适用范围不改变；素材使用渠道不扩权；不同入口不丢冻结 hash |
| 配额/结算 | 并发超额、排队上限、失败/取消/自动修复/回包未知；不双扣、不按图片数猜费用，不因本地 MCP 跳过账户策略 |
| 上传与清理 | MIME 伪装、超大像素、上传中断、重复 complete、READY 覆盖；清理与活跃任务/幂等/输出依赖竞争不得产生悬空交付 |
| 本地 MCP | stdio UTF-8、协议版本协商、错误返回、未知字段、源路径越界/符号链接、伪造 runtime descriptor、显式 base_url 不跳过校验 |
| handoff | nonce/hash/fingerprint、并发/重复提交、已消费重放、中断恢复、只认现有 Job；提交图片仍经共享审核 |
| 公网边界 | 外部直连、反代到 loopback、Origin/Host、伪造转发头、错误监听地址和未保护旧路由全部覆盖 |
| Webhook 后续 | SSRF/重定向/DNS变化、签名重放、密钥轮换、事件重复乱序、重试耗尽；不改变图片状态、不泄漏正文 |
| 回归与实测 | 既有 Web/V3/MCP 冻结与审核测试；隔离账号真实 API 请求和本地 Codex 交接；日志、输出、费用与实际运行版本一致 |

API/MCP 一致性比较的是合同、授权、执行策略、状态与审核依据，不要求两次独立随机生成的像素相同。同一业务命令主动复用相同幂等键时才要求相同业务 ID 与不重复执行；否则不能为了“相同结果”把两次用户操作误去重。

所有故障注入先在隔离环境进行，不放宽真实认证、消费或账务门槛。交付证据记录实际源码/进程版本、输入摘要、任务/操作/输出 ID、请求关联和去密钥日志；生产验收另核对反代规则、工作进程数量与保留配置。

## 十五、源码依据、评审范围与最终约束

本版实际读取基线 main `6e14dce5`，确认原方案、AGENTS、现有 HTTP/Service/MCP/账务边界及新保留代码；不是仅根据上一轮 V2/V3 修复总结推断。以下行号为该固定提交的定位，后续代码变动可能位移。

| 引用 | 文件与基线位置 | 支持的事实 |
| --- | --- | --- |
| S1 | `services/alchemy_codex_local_adapter/mcp_server.py:20–305` | 五个现有工具；本地规划与交接分离；当前手写 stdio/协议分发需补产品化协议测试 |
| S2 | `services/alchemy_codex_local_adapter/materialized_bridge.py:29–165` | loopback base_url、runtime descriptor 验证、文件读入与提交；显式 base_url 不走自动发现验证 |
| S3 | `src_skeleton/app/main.py:632–638,1862–1872` | handoff 路由依据 client.host 判断本地；需结合实际代理配置评审 |
| S4 | `src_skeleton/app/main.py:2426–2520`；`product_api/service.py:3055–3063,3434–3447`（V3） | 路由层归属检查与 Service 的本地兼容默认，不可裸露复用 |
| S5 | `src_skeleton/app/main.py:770–793,1109–1184,1699–1753` | 进程内后台调度；HTTP 异步规划在 Job 出现前返回 operation |
| S6 | `alchemy_creative_agent_3_0/app/project_mode/service.py:3296–3426` | 已有持久 operation；项目忙碌返回已有操作；完成后 operation 与 Job 关联 |
| S7 | `alchemy_creative_agent_3_0/app/product_api/contracts.py:38–46,84–156,395–406` | 内部 Job 枚举、产品输入和已有品质选项；不能直接等同新公开状态和输入 |
| S8 | `alchemy_creative_agent_3_0/app/platform_adapters/balance_adapter.py:1–37`；`src_skeleton/app/services/image_service.py` 的 debit_balance 调用；`veyra_usage.py:1–51` | 估算桩与实际扣费/用量记录不是同一责任层 |
| S9 | `src_skeleton/app/main.py:1904–1916`；V3 `_public_final_delivery_projection`、`_canonical_final_delivery_output_ids` | 当前下载和业务交付依据位于不同入口，v1 需同时执行权限与交付检查 |
| S10 | `alchemy_creative_agent_3_0/app/generation_router/mcp_materialization.py` 的 `_transaction_lock`、submit、consume | 现有 handoff 事务与消费校验应复用，不另造流程 |
| S11 | 提交 `e98af145`；`src_skeleton/app/services/retention_settings.py`；`ops/vps-storage-maintenance/v3_storage_maintenance.py` | 当前可配置受保护数据清理已经存在，公共 API 需定义过期与依赖保护 |

### 15.1 定稿后的不可省略项

公网只读前必须完成身份/资源隔离、输出交付边界及本地接口网络隔离；公网写入前还必须完成 durable 幂等、规划前句柄、项目并发、可恢复调度和并发结算。以上不是可后置的“优化”。

取消仅开放实际支持范围；远程 Codex 不作为公共任务的默认执行条件；第三方 Key 不得成为管理员票据。不得用“同一个 Service”掩盖缺少授权，也不得用“同一个 API”让本地特权合同外泄。

暂不指定所有接口的文件数量或把上述能力一次性施工。每个阶段先补失败合同测试，再在责任层最小实现；新模块需说明为什么现有 owner 不能承担。只读 API 达标即可独立交付，不被 SDK/Webhook/远程 MCP 拖住。

### 15.2 本轮评审结论

原方案方向通过；原 6e14dce5 版本不应不加补充就直接开发全部公网写入。此次已明确补齐权限与租户默认、规划前 ID、并发幂等、调度持久性、取消能力、收费权威、审核下载边界、MCP 本地信任、数据保留与后续回调安全。

本版作为后续阶段开发依据。所有接口、主体模型和调度/计费增强在本文中均为待实现约束；当前未新增 `/api/v1`、API Key、产品 MCP 或 Webhook 功能。评审未检查 VPS 当前反代/网络配置，也未对外部 MCP 最新规范或实际第三方客户端作兼容认证，实施远程 MCP 时须另行锁定协议版本。

本轮只修订此 Markdown，不改变业务源码、依赖、配置、工作流或运行数据，不进行真实生成或部署。文档复核应确认源码依据存在、阶段无自相矛盾、暂缓功能不成为首版依赖，并用 Git 变更范围与源文件哈希核验“仅文档改动”。

## 十六、可直接转发的决策摘要

采用 API-first、MCP-adapter：新增稳定 `/api/v1` 面向第三方服务，现有 Web 和产品级本地 MCP 共用经过授权的 V3 产品入口，不直接裸调 Store，也不复制生成、审核和状态逻辑。

保留现有 conversation-only 规划和正式 Materialization 两类低层 MCP，冻结 Prompt、素材、handoff、校验与恢复链不动；本地特权接口继续隔离，不能简单经反代发布公网。API 首版不依赖本地 Codex 才能完成任务。

先做安全的只读 API，再做具备持久幂等、统一额度/结算和稳定任务句柄的异步生成；最后增加产品 MCP。取消只承诺可真正停止的阶段；待复核与部分交付独立表达。Webhook、SDK、组织体系及远程 MCP 按真实需求逐项后置。

方案已完成架构评审定稿，但功能尚未开发；下一步以 Phase 0 合同测试和 Phase 1 只读接入为工作边界，不一次性构建全部远期能力。
