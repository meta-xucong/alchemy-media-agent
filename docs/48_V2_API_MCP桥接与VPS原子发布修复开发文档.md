# V2 API/MCP 桥接与 VPS 原子发布修复开发文档

## 1. 任务目标

修复生产环境中 V2 API 和 V2 MCP 使用 Alchemy API Key 时返回
`veyra_session_required` 的问题，并使 V1、V2、V3、Alchemy Lab 的统一入口
能够在同一版本、同一认证契约下完成可复现验收。

本次范围只包含：

1. V1 网关到 V2 的 API-Key 身份桥接保持可验证。
2. V1、V2 使用同一个 `ALCHEMY_ACCESS_BRIDGE_SECRET`，并在启动前完成配置。
3. VPS 发布改为干净的、按目标 commit 创建并切换的原子 release。
4. 部署后具备 API/MCP 读操作闭环测试条件。
5. 增加 V1 代理签名到 V2 验签的回归测试。
6. 发布时同步并校验 V1/V2 的 Veyra 账户认证运行配置。
7. 发布时收敛公网 Nginx 到 V1 网关，避免 `/api/v2/*` 绕过 API-Key 桥接。

不包含：V2 生图业务逻辑重写、V1/V2 数据合并、API Key 存储重构、MCP 工具扩展、
计费规则调整和真实生图任务。

## 2. 基线与已确认问题

基线提交：`614872a457ad0d0d6492bf7de9fe24548be80da8`。

生产观测：

| 场景 | 结果 |
| --- | --- |
| V2 使用 Alchemy Session | 200 |
| API Key 调用 V1/V3/Lab | 成功 |
| API Key 调用 V2 | 401，`veyra_session_required` |
| 同 API Key 调用 MCP V2 | 失败，`veyra_session_required` |

本地签名/验签模拟成功，说明 HMAC 合同和路径规范本身没有发现不一致。

生产只读 preflight 还发现：

```text
GUARDED_PREFLIGHT_STOP=active_release_tracked_changes
```

这说明旧部署流程把新文件覆盖到旧 release 目录，却没有保持 release 的 Git
提交一致性，无法证明 V1、V2 进程加载的是同一目标版本。

随后真实验收又确认了一个独立的运行配置缺口：原子 release 已成功切换，V2
Session 仍可用，但使用 Session 创建 API Key 返回 `503 account_login_not_configured`。
代码路径明确表明这是 V1 的 `VEYRA_AUTH_ENABLED` 未开启，而不是 HMAC、API Key
索引或 V2 业务处理错误。V1/V2 还必须共享 `VEYRA_SUB2API_BASE_URL`、
`VEYRA_INTERNAL_TOKEN`、`VEYRA_SESSION_SECRET`，否则账户验证、session 和后续
扣费链路可能在不同阶段失败。

配置同步后，隔离 Cookie 的真实 API/MCP 验收又确认：V1、V3、Lab API Key
均可用，但 V2 API/MCP 仍返回 `veyra_session_required`。这排除了 API Key
签发和 V1/V3/Lab 授权问题，说明公网请求绕过了 V1 `/api/v2/*` 代理，直接到达
V2 8020 端口。线上 Nginx 配置与仓库网关配置漂移，是本次第二个运行态根因。

## 3. 权威认证契约

公网统一入口保持：

```text
API Key
  -> V1 api_access 中间件验证密钥、账户、surface
  -> V1 /api/v2/* 代理移除 API Key
  -> V1 生成 X-Alchemy-Access-* HMAC 头
  -> V2 仅在回环或 RFC1918 私有来源上验签
  -> V2 恢复 user_id 并执行原有 V2 权限、计费和资源逻辑
```

V2 不直接把 `alk_live_*` 当作 Veyra Session。API Key 只允许从 V1 公网网关
进入 V2；V2 不复制 API Key 数据库，也不新增第二套账户认证路径。

桥接密钥要求：

- V1 容器环境和 V2 systemd 环境必须使用同一个非空值。
- 只比较 SHA256 指纹，不在日志、接口或验收回执中输出原值。
- 密钥缺失时部署失败，不允许以 V2 Session 路径冒充 API Key 通过。
- V2 进程必须在密钥写入后重启，运行态检查必须绑定当前 release。
- 私网来源只是传输层门禁，不能单独授权；V2 仍必须验证完整 HMAC、时间窗、路径、方法和
  `v2` surface。公网来源或验签失败均 fail-closed。
- V2 在本机收到但无法验证桥接头时返回 `access_bridge_invalid`，不再把桥接失败
  伪装成 `veyra_session_required`；这样 API/MCP 调用能准确暴露桥接配置或签名
  不一致，而不会误导排查方向。

## 4. 修复设计

### 4.1 原子 release

发布流程使用 `scripts/vps_migrate_release_layout.sh`：

1. 从 Git 仓库获取目标完整 commit。
2. 在新的 release 目录创建 detached worktree。
3. 从正在运行的 V1 容器复制生产 `.env`，保留生产密钥和 provider 配置。
4. 确认并同步 V1/V2 桥接密钥。
5. 安装并验证 V2 runtime manifest、依赖和 systemd 模板。
6. 构建新 V1 镜像。
7. 原子切换 `/opt/alchemy-media-agent` 软链接。
8. 重启 V1 容器和三个 V2 systemd 服务。
9. 等待 V1、V2 本地健康检查，并确认 V2 主进程 cwd 指向新 release。
10. 任意步骤失败时恢复旧软链接、旧镜像和旧 systemd 单元。

不再通过 GitHub Actions 将源码 tar 覆盖到当前稳定 release；这会导致代码文件
与 `.git` HEAD 分离，是本次问题的重要诱因。

### 4.2 桥接密钥初始化与一致性

迁移脚本在复制生产环境之前执行：

- 读取 V1 容器挂载的 env 文件。
- 缺少 `ALCHEMY_ACCESS_BRIDGE_SECRET` 时生成 32 字节随机十六进制值。
- 写回 V1 env，并同步 `/etc/alchemy/alchemy-v2.env`。
- V2 env 文件不存在时直接失败。
- 新 release 复制已经完成同步后的 V1 env。

这样既不覆盖既有生产密钥，也不允许 V1、V2 在不同 secret 下启动。

### 4.3 Veyra 账户认证配置同步

迁移脚本在桥接密钥同步后执行 `ensure_veyra_auth_config`：

- 从 V1 容器挂载的 env 和 `/etc/alchemy/alchemy-v2.env` 读取三个共享配置；
- 一侧缺失时从另一侧补齐；两侧都缺失或值不一致时立即失败，不输出密钥原文；
- 将 V1、V2 的 `VEYRA_AUTH_ENABLED` 固定为 `true`，但不改变独立的
  `VEYRA_REQUIRE_UI_AUTH` 页面跳转开关；
- V1 缺少容器可达的计费地址时补齐生产地址
  `https://alchemy.aiself.vip/api/v2/veyra/billing/settings/public`；
- 所有 env 在切换 release 前备份，失败时与 release、systemd 单元一起回滚。

这样 API Key 创建不会再被 V1 默认值静默关闭，V1 发出的 API Key、V1 代理签名、
V2 session/账户解析和扣费配置使用同一份生产认证契约。

### 4.4 部署工作流

GitHub Actions 仅上传必要的迁移脚本，向 VPS 传入 checkout 的完整
`GITHUB_SHA`，由 VPS 迁移脚本自行创建目标 worktree。工作流不再向稳定软链接
目录解压源码。

迁移脚本同时安装候选 release 中的 `alchemy-media-agent.nginx.conf`，先执行
`nginx -t` 再 reload，并把旧配置放入本次备份目录。该配置通过精确 `/api/v2`
和 `^~ /api/v2/` location 明确将公网 `/api/v2/*` 继续进入 V1 8017；`^~`
用于压过历史正则 location，防止旧规则再次绕过网关。V1 再把请求转到本机 V2
8020 并注入 HMAC。V2 8020 只作为
本机后端，不作为 API Key 的公网入口。若后续步骤失败，Nginx 配置随 env、systemd
单元和 release 一起恢复。

当系统同时存在 `sites-available` 和旧 `/etc/nginx/conf.d/alchemy-media-agent.conf`
时，迁移会先备份并移除同名旧配置，避免两个 server block 并存导致旧的 V2 直连
规则继续优先；回滚时恢复该旧文件。

重启后还检查 V1 容器和 V2 API 进程实际读取的桥接密钥 SHA256 指纹，以及两侧
`VEYRA_AUTH_ENABLED=true`；只输出匹配状态，不输出密钥原文。

由于 Docker Compose 的 `env_file` 只保证文件注入，不足以证明最终容器环境已采用
迁移后的值，V1 启动还使用一次性的 0600 权限 Compose override 显式注入桥接密钥。
override 在容器启动命令返回后立即删除，不进入 release、Git 或日志。

迁移开始时还会清理两份受控 env 文件的 CRLF 行尾，再写入规范值，避免 Docker
将隐藏的 `CR` 字符带入 V1 进程而导致 HMAC 指纹表面一致、实际验签失败。

## 5. 验收矩阵

| 编号 | 验收条件 |
| --- | --- |
| R1 | 本地桥接单测确认 V1 签名可被 V2 验证 |
| R2 | 本地代理模拟确认 API Key 被移除、V2 目标为 `/api/v2/*` |
| R3 | 部署脚本测试确认目标 commit 使用干净 worktree，不执行旧目录覆盖 |
| R4 | 部署后 V1/V2 运行态的 release、secret 指纹和服务启动时间可核对 |
| R5 | 使用临时 API Key 读取 V2 provider capabilities 成功 |
| R6 | 使用同一临时 API Key 调用 MCP `alchemy_v2_list_history` 成功 |
| R7 | Session、V1、V3、Lab 原有读路径回归通过 |
| R8 | 临时 API Key 撤销后 V2 API/MCP 请求均被拒绝 |
| R9 | 不创建生图任务、不产生费用，除非单独批准真实生图验收 |

## 6. 完成判定

只有满足 R1-R8，且运行版本为同一目标 commit 时，才能把 V2 API/MCP 标记为
阶段性可测试。若 API Key V2 或 MCP V2 任一仍返回 `veyra_session_required`，
结论必须是桥接未闭环，不能用 Session 成功替代 API Key 验收。
