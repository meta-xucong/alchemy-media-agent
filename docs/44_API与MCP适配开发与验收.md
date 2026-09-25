# API / MCP 适配：开发与验收

基线：`5503e0f92098866053735ee9a827b1e42b83cdf2`。范围依据 43 号精简方案。
本次只增加已有 HTTP 接口的工具封装和示例；不新增服务端业务能力。

## 实施前的调用模型

- 保留原五个 MCP 工具、顺序、冻结/handoff/loopback 合同；追加六个产品工具。
- 产品工具仅调用 `/api/v3/creative-agent`，不导入 Product Service、Provider、计费或 Store。
- 使用用户显式配置的既有 Bearer Session；缺配置/登录过期即报错，不匿名回退。
- 地址来自进程配置，不来自模型参数。远程地址要求 HTTPS；不跟随重定向转发凭证。
- 创建生成只提交一次项目 `/jobs` 的 `auto_generate`；不追加 `/generate`，不自动重试。
- 原 `project_id`、`operation_id`、`job_id` 原样返回。项目原完整查询用于规划期进度；已有 Job 走原查询路由。
- 服务端原查询可能恢复已受理操作；适配器不自行创建、重试或推断最终状态。
- 输出只省略内部字段，复制原审核/交付/选择值，不另算分、不生成新公开状态。
- 上传只读取这次明确指定的本地普通 PNG/JPEG/WebP 文件，最多12MiB；写入仍走原上传流程。
- 本地运行的单元与原生路由测试使用隔离存储和受控凭证/Provider，不产生付费请求。

预期文件：新增 `services/alchemy_codex_local_adapter/product_tools.py`；
在原 `mcp_server.py` 追加注册；新增专项测试；更新本说明和插件 README。
账户、扣费、队列、ID、恢复、审核、选择、前端、V2、反代与生产配置不改。

## 原生路由核对时发现的适配差异

首轮工具合同59项通过；原生HTTP对照中，项目 `view=summary` 不带规划 operation，
导致工具虽然没有改状态，却丢失了规划期查询句柄。责任在适配器选错查询视图。
修正为沿用 Web 的默认完整项目查询，再仅省略内部字段；不修改项目服务或另造状态。
查询可能触发原服务已受理任务的恢复，与 Web 一致；适配器不再提交新的创建/生成请求。

## 配置与启动

保持原账户登录方式。将现有合法 Bearer 会话通过用户授权的本地安全配置提供：
`ALCHEMY_PRODUCT_API_BASE_URL` 是已部署服务的根地址（例如 `https://alchemy.aiself.vip`）；
`ALCHEMY_PRODUCT_SESSION_TOKEN` 是该账户的现有会话值，不带 `Bearer ` 前缀，不是模型供应商 Key。
服务地址不含 `/api/...`、账号密码、查询参数或片段；仅 localhost/127.0.0.1/::1 可使用 HTTP。
未配置时产品工具明确报错；旧五个本地工具不依赖这两个值，不受影响。
不要将真实凭证写入 Git、工具参数、提示词、URL 或示例；不自动提取浏览器 Cookie。

复用已安装的 `alchemy-codex-local-mode` 插件，更新仓库后重启 MCP 进程。
`.mcp.json` 只追加这两个环境变量名称，不包含凭证值；原启动方式和已有变量保持不变。
手动启动仍使用项目现有环境：

```powershell
Set-Location 'D:\AI\Alchemy Media Agent System'
# 先从安全配置加载上述两项；不打印会话。
& '.\src_skeleton\.venv\Scripts\python.exe' '.\plugins\alchemy-codex-local-mode\scripts\start_mcp.py' --enable-native-imagegen
```

工具列表应为原五个加六个产品工具，共11个。产品工具调用现有服务，不在 MCP 内运行生图核心。

## 六个工具的实际参数与接口

| 工具 | 参数 | 现有 HTTP 路径（前缀 `/api/v3/creative-agent`） |
| --- | --- | --- |
| alchemy_create_project | user_goal；可选 title、primary_template_id、uploaded_asset_ids | POST /projects |
| alchemy_upload_asset | file_path；可选 role（沿用原角色） | POST /uploads → PUT /uploads/{id}/content → POST /uploads/{id}/complete |
| alchemy_create_generation | project_id、user_input；可选 template_id、uploaded_asset_ids、requested_image_count、requested_image_size、quality_mode、use_project_context | POST /projects/{id}/jobs，仅一次 auto_generate |
| alchemy_get_generation | project_id 或 job_id，二选一 | GET /projects/{id} 或 GET /jobs/{id} |
| alchemy_list_outputs | project_id；可选 limit（1–60） | GET /project-outputs?project_id=...&compact=true&limit=... |
| alchemy_select_outputs | project_id、job_id、selected_output_ids（显式非空） | POST /projects/{id}/jobs/{job_id}/select |

默认模板为 `general_template`，张数1，quality_mode=standard，use_project_context=true。
quality_mode 仅接受原来的 standard/explore/strict；其他产品限制仍由原服务判断。
不支持的专业设置、取消、续作、导出管理继续走原 Web/API，不借工具加入新机制。

MCP 参数示例（使用真实返回的 ID 替换占位）：

```json
{"name":"alchemy_create_project","arguments":{"user_goal":"白底银色护肤品海报"}}
{"name":"alchemy_upload_asset","arguments":{"file_path":"D:\\Pictures\\product.png","role":"product_reference"}}
{"name":"alchemy_create_generation","arguments":{"project_id":"project_ID","user_input":"沿用产品外观，白底，无人物，不要二维码。","uploaded_asset_ids":["v3_asset_ID"],"requested_image_count":1,"requested_image_size":"1024x1024"}}
{"name":"alchemy_get_generation","arguments":{"project_id":"project_ID"}}
{"name":"alchemy_get_generation","arguments":{"job_id":"job_ID"}}
{"name":"alchemy_list_outputs","arguments":{"project_id":"project_ID"}}
{"name":"alchemy_select_outputs","arguments":{"project_id":"project_ID","job_id":"job_ID","selected_output_ids":["v3_output_ID"]}}
```

生成会沿原服务收费。规划期可能返回空 job_id，应保留 metadata.current_operation.operation_id，
用 project_id 查询，出现原 job_id 后按它继续查。工具不伪造 job_id，也不轮询到超时才返回。
HTTP成功不代表审核或选择成功；检查原 status、final_delivery、review_items 和 selection_held。
返回的下载/预览地址为原鉴权相对路径，用配置的同一服务根地址与同一会话访问。

## 直接调用现有 API

所有请求携带原 `Authorization: Bearer <会话值>`。没有新增 API Key 或 `/api/v1`。
上传声明字段为 filename、mime_type、size_bytes、可选role；PUT JSON为 content_base64、mime_type。
后端仍验证实际图片、尺寸与归属；不要把本机路径传给服务端当作文件位置。

以下示例会创建一个项目并发起一次真实生成；验收时确认账户与费用后只执行一次：

```powershell
$base = $env:ALCHEMY_PRODUCT_API_BASE_URL.TrimEnd('/')
$headers = @{ Authorization = "Bearer $env:ALCHEMY_PRODUCT_SESSION_TOKEN" }
$contentType = 'application/json; charset=utf-8'
$p = Invoke-RestMethod -Method Post -Uri "$base/api/v3/creative-agent/projects" -Headers $headers -ContentType $contentType -Body '{"user_goal":"A clean product photograph"}'
$projectId = $p.project.project_id
$metadata = @{ require_real_images = $true; requested_image_count = 1; requested_image_size = '1024x1024' }
$payload = @{ user_input = 'A clean product photograph'; template_id = 'general_template'; metadata = $metadata; auto_generate = @{ quality_mode = 'standard'; metadata = $metadata } }
$bytes = [Text.Encoding]::UTF8.GetBytes(($payload | ConvertTo-Json -Depth 8))
$accepted = Invoke-RestMethod -Method Post -Uri "$base/api/v3/creative-agent/projects/$projectId/jobs" -Headers $headers -ContentType $contentType -Body $bytes
# 不再补发 /generate，不循环重试创建。保留 $accepted 中原 operation/job ID。
$progress = Invoke-RestMethod -Method Get -Uri "$base/api/v3/creative-agent/projects/$projectId" -Headers $headers
$outputs = Invoke-RestMethod -Method Get -Uri "$base/api/v3/creative-agent/project-outputs?project_id=$projectId&compact=true&limit=60" -Headers $headers
```

接口可能沿原实现返回 HTTP 200 和 `status=planning`；不要只凭 HTTP 状态断言完成。
其他调用直接按上表原路由执行。选择请求为 `{"selected_output_ids":["v3_output_ID"]}`。
下载例：`Invoke-WebRequest "$base<返回的download_url>" -Headers $headers -OutFile '<用户指定的保存文件>'`。

## 错误与未确认结果

MCP 错误以 isError 返回，保留原安全错误码及 HTTP 状态，不返回原异常全文、服务器路径或会话。
401/过期按原登录流程重新取得会话；403/404/余额错误保留原限制，不切换账户或支付路径。
写请求发生超时、响应截断/无效、408或5xx，可能已被服务受理；返回 outcome_unknown 时先查已有项目。
上传中途失败会尽可能带回已取得的 asset_id；不自动重建上传、不盲目重复生成或选择。
所有写请求无自动重试，也不跟随重定向。改URL或重新登录之前先确认既有任务状态。

## 兼容检查中的历史测试边界

旧 DOC134 测试从 runtime 导入已删除的电商常量别名，原 main 上也无法收集测试。
仅改测试导入到现有电商 contracts 的同一常量，不修改运行代码或凭证校验。
旧测试要求“工具总数只能是5个”，按本次明确授权扩展为“原5个保持不变，追加6个”。
原生渲染器禁止平台调用的检查仍覆盖所有原文件；新增产品HTTP适配独立检查不导入业务后端。
测试环境故障与旧电商冻结上下文测试需作基线对照，不能改核心或降低校验来强行清零。

## 开发侧最终验证与已知边界

新增适配测试：63项工具/传输/配置测试 + 7项原生HTTP对照与受控闭环，70项全部通过。
受控闭环保留现有后台worker、typed continuation、审核和选择边界；使用隔离图片夹具，非付费生图。
旧测试组存在模块级配置互相影响，最终采用相同环境、逐文件独立进程，对照基线与候选。
对照15个文件共407项：候选377通过、30失败、0跳过；基线原有337项为307通过、相同30失败。
失败集合完全一致，新增失败0；未通过的均为旧 DOC134 专业电商原生规划合同用例。
原基线测试先有常量旧导入错误；对照工作树只修测试导入到当前contracts，业务源码保持原样。
原计划冻结上下文校验在这些旧用例中提前阻断，不能据此声称原有专业电商Native MCP已验收。
本次未改变这条低层逻辑；产品工具走原HTTP服务，和原生Codex渲染交接是不同入口。
失败清单、逐文件日志/JUnit和对照结论保存在仓库根：
`.controlled-validation/api-mcp-product-adapters-20260925/isolated-comparison.json` 及同名目录。
原始组合测试失败日志也保留，不以新的通过统计覆盖旧记录。

范围审计：运行实现仅新增 product_tools.py，并在 mcp_server.py 追加10行注册；
插件配置仅增加两个环境变量名称。原五工具schema逐字段一致，原启动器与handoff源码未变。
V2/V3业务、账户、计费、队列、审核、路由、生产配置、依赖均无改动；没有新增API路径。
例行修正仅涉及3份旧测试的追加工具断言、原生路径扫描范围与1处过期常量导入。

验收同事须用原账户完成：插件更新重启→11工具发现→上传→建项目→一次生成→按ID查询→
下载/选择；比较Web同一Job状态与原费用记录，验证过期登录和其他账户资源被拒绝。
同一项目多个不同生成请求沿用原串行/规划互斥行为；本适配不承诺新的幂等或并发机制。
写请求不确定时先查原记录，不自行补发收费操作。原生专业模块的未通过用例另列待验证。
本次开发未调用真实账户或付费供应商，未验证真实扣费金额，未部署VPS。
结论：本次最小适配代码及受控链路可交接实测，不是全仓或生产环境最终验收。

## 用户 API 密钥入口

可在 `/api-access` 使用原账户创建密钥，并将它填入既有 `ALCHEMY_PRODUCT_SESSION_TOKEN` 配置。原会话仍然兼容，参数名不变。密钥仅支持文档列出的 V3 产品路由，不适用于管理后台或低层 MCP handoff。
