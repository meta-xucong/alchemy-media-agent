# 16. 开发前 Ready Checklist

## 产品确认

- [ ] 确认 2.0 MVP 只做模板定制和智能增强两个主流程。
- [ ] 确认第一个 ResourceProvider 是 EvoLinkAI GitHub 仓库。
- [ ] 确认 2.0 只和原版共用域名与前端入口。
- [ ] 确认旧版功能不迁移到 2.0。

## 架构确认

- [ ] 确认 `CreativeManagerRuntime` 是当前主业务流水线。
- [ ] 确认 Claude Code Orchestrator 是创意决策中枢。
- [ ] 确认 Kimi / DeepSeek / Doubao / GLM 只作为 Claude Code 背后的模型源或备用源。
- [ ] 确认 OpenAI Agents SDK 只作为可选 planner/tool/tracing 边界，不接管主链路。
- [ ] 确认专业 agent 默认作为工具边界或复检边界。
- [ ] 确认 handoff 只用于对话接管场景。
- [ ] 确认 agent 不能直接访问数据库、密钥和供应商 API。
- [ ] 确认生产启用 Claude Code 时设置 `V2_CLAUDE_ORCHESTRATOR_ENABLED=true`。

## 数据确认

- [ ] 确认 DB schema 或表前缀。
- [ ] 确认 Redis namespace。
- [ ] 确认对象存储 prefix。
- [ ] 确认 trace project。
- [ ] 确认 migration 不触碰旧表。

## Provider 确认

- [ ] 确认 GitHub adapter 访问方式。
- [ ] 确认同步频率。
- [ ] 确认案例解析范围。
- [ ] 确认 license 和 risk 默认策略。
- [ ] 确认 provider 更新失败时的 fallback。

## 安全确认

- [ ] 确认 SafetyDecision schema。
- [ ] 确认商用授权文案。
- [ ] 确认肖像、品牌、版权风险处理。
- [ ] 确认用户上传素材授权记录。
- [ ] 确认 trace 脱敏策略。

## 前端确认

- [ ] 确认 `/v2` route。
- [ ] 确认 `/api/v2` client。
- [ ] 确认模板库页面。
- [ ] 确认创意运行页面。
- [ ] 确认反馈入口。

## 验收确认

- [ ] 确认 OpenAPI 初稿。
- [ ] 确认 JSON contract 示例。
- [ ] 确认 Mermaid 架构图。
- [ ] 确认测试分层。
- [ ] 确认上线回滚方案。
