# 42. Alchemy 视频入口剥离与 aiself 平台边界开发文档

## 1. 结论

Alchemy 当前只负责图片生成。视频生成已经在 aiself 首页独立实现，因此 Alchemy 中旧的“生视频（DEMO）”导航、占位页面、Seedance provider 和 `/v1/video/jobs` 接口不再属于产品边界，必须同时从前端、运行时和 API 契约中移除。

## 2. 问题与修正模型

旧实现把一个未实现的 provider 作为可见产品能力发布：桌面/H5 有视频入口，运行时注册 Seedance，消息自动分流可以创建视频 job，OpenAPI 也公开了视频接口。即使 provider 只返回占位错误，用户仍会把它理解成 Alchemy 的生视频入口，也会让维护者误以为该链路需要继续修复。

权威关系调整为：

```text
aiself 首页独立视频平台 -> 视频生成
Alchemy -> 图片生成、炼金、V1/V2/Lab 图片工作流
```

旧客户端若仍发送 `target=video` 或文本视频意图，只得到迁移提示；这个兼容哨兵不调用图片 provider、不创建视频 job，也不把视频需求误判成图片需求。

## 3. 实施范围

### 前端

- 删除桌面与 H5 的视频 tab、占位页面、视频 provider 展示和对应 CSS。
- 保留 V1、V2、Alchemy Lab、登录/设置及图片工作流。
- 不改 aiself 首页的独立视频平台。

### 运行时与契约

- 删除 `VideoProvider`、`SeedanceVideoProvider`、视频 service、视频 agent tool 和视频 job 路由。
- Provider catalog 只发布 image 能力。
- `GenerationJob` 的活动类型只允许 `image`。
- 从 OpenAPI 删除 `/v1/video/jobs` 和视频请求 schema。
- 保留 `GenerationOutput` 对历史 `mp4` 字段的读取兼容，不让当前图片链路生成视频输出。

### 兼容与安全

- `MessageRequest.target` 暂时保留 `video` 作为旧客户端迁移哨兵，返回 aiself 引导文案。
- 自动文本识别先拦截视频意图，再执行图片关键词判断，避免视频请求创建图片任务。
- 删除 Seedance 默认配置，避免新部署误以为需要视频密钥或 provider。

## 4. 验收门槛

1. 桌面/H5 HTML、JS、CSS 不包含旧视频 tab、占位面板或 Seedance 展示。
2. `POST/GET /v1/video/jobs` 返回 404。
3. 显式和自动视频消息均不产生 job，并返回 aiself 迁移提示。
4. `/v1/providers` 和 OpenAPI 不发布视频能力。
5. 图片会话、生图、炼金、provider 查询及 V3 前端回归测试通过。
6. 独立审计确认没有把 aiself 视频平台代码误删，也没有让旧视频意图回退到图片链路。
