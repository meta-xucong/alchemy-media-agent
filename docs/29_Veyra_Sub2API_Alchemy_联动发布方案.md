# Veyra / sub2api / Alchemy 联动发布方案

> 生产登录门禁、匿名访问收紧、以及“聚合平台 / Alchemy / 首页登录”按来源回跳的下一步优化，以
> [30_生产登录门禁与来源回跳开发文档.md](30_生产登录门禁与来源回跳开发文档.md)
> 为准。

## 边界

本次联动由两个 GitHub 仓库共同承载，但职责必须保持分离：

- `meta-xucong/alchemy-media-agent`
  - Alchemy V1 shell、H5、管理员计费页。
  - `custom_media_agent_2_0` 独立 V2 后端。
  - Alchemy 侧 Veyra session、账户展示、历史隔离、扣费前置校验和扣费流水。
- `meta-xucong/sub2api-adapted`
  - 基于 upstream sub2api 的最小适配层。
  - Veyra Portal 首页、登录回跳、login-ticket、账户摘要和 debit 内部 API。
  - 保持 `custom/main` 为“upstream + custom overlay”的可重放分支。

不把 sub2api 账号、密码、邮箱验证码、充值逻辑复制到 Alchemy。sub2api 仍是唯一账号和资金源。

## 发布顺序

1. 先部署 `sub2api-adapted`。
2. 确认 `/api/veyra/portal/config`、`/api/veyra/login-ticket`、`/api/veyra/internal/*` 可用。
3. 再部署 `alchemy-media-agent`。
4. Alchemy V2 配置：
   - `VEYRA_AUTH_ENABLED=true`
   - `VEYRA_SUB2API_BASE_URL=https://aiself.vip`
   - `VEYRA_INTERNAL_TOKEN` 与 sub2api 的 `veyra.internal_token` 完全一致
   - `VEYRA_SESSION_SECRET` 使用独立随机密钥
5. Alchemy V1 如果运行在 Docker 容器中，`VEYRA_BILLING_SETTINGS_URL` 必须使用容器可访问地址。生产推荐：
   - `VEYRA_BILLING_SETTINGS_URL=https://alchemy.aiself.vip/api/v2/veyra/billing/settings/public`
   - 不要使用 `http://127.0.0.1:8020/...`，除非 V2 也在同一容器网络中且该地址真实可达。
6. 最后切换域名/反代，不在代码推送阶段触碰 VPS。

## 回归矩阵

sub2api：

- 未登录点击“聚合平台”进入登录页，登录后回到 sub2api 控制台。
- 未登录点击“Alchemy”进入登录页，登录后带一次性 ticket 跳到 Alchemy。
- 已登录点击“Alchemy”直接签发 ticket 并跳转。
- `/api/*`、`/v1/*`、`/v1beta/*` 不被首页 portal 接管。
- 内部接口必须要求 `X-Veyra-Internal-Token`。

Alchemy：

- 桌面和 H5 都能消费 `?ticket=...`。
- 生产强制登录开启后，匿名用户不能读取 V1/V2 历史、输出、runtime/provider 设置或管理员页面。
- 未登录直接打开 Alchemy 桌面/H5 时，应回到 sub2api 登录页，登录后自动回到对应 Alchemy 入口。
- 账户页展示 sub2api 余额、当前用户生成记录、扣费流水。
- 管理员用户显示“管理员设置”，普通用户不显示。
- V2 未显式保存 Mock 时优先使用 OpenAI/Gemini 真实通道。
- 从 V1 容器内部访问 `VEYRA_BILLING_SETTINGS_URL?rule_key=alchemy:v1` 返回 200。
- 余额不足时不调用生图 provider。
- 生成失败不扣费，生成成功后扣费。

## sub2api 上游更新原则

`sub2api-adapted` 不直接改 upstream 发布分支。流程：

1. 从 `upstream/main` 拉取原版更新。
2. 在 `custom/main` 上合并 upstream。
3. 保留并修复这些最小接点：
   - `backend/internal/veyra/**`
   - `extensions/veyra/portal/**`
   - `backend/internal/server/router.go`
   - `backend/internal/server/http.go`
   - `backend/internal/config/config.go`
   - `backend/cmd/server/wire_gen.go`
   - `frontend/src/views/auth/LoginView.vue` 的 `/_veyra/return` reload 钩子
4. 运行 sub2api 回归测试。
5. 再部署。

这个结构保证“原版更新完毕后，我们自己的适配和调整能很方便地覆盖回来”。
