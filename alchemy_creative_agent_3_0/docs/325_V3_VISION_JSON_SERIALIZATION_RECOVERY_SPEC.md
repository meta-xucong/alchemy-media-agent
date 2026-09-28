# Doc325 — V3 Vision Review JSON Serialization Recovery

## 目的

修复视觉审核 Provider 已收到图片、但返回不完整或格式错误 JSON，导致
一张已成功生成的图片被误留在人工审核状态的问题。

本修复只处理审核响应的传输与序列化边界，不改变图片质量标准、审核阈值、
参考图规则、Provider 路由或自动交付门槛。

## 根因

原实现存在三个组合风险：

1. 仅使用 OpenAI-compatible `json_object`，它不能保证所有网关和视觉模型
   都返回字段完整、可解析的 JSON。
2. 强制审核契约包含评分、证据、身份认证和摘要等字段，但 Chat/Responses
   输出上限固定为 1600，存在输出被截断的风险。
3. 第一次 JSON 解析失败后，第二次请求仍发送完全相同的提示词，没有告知模型
   需要重新输出完整 JSON，因此可能重复得到同类格式错误。

## 修复契约

单张图片的一次审核遵循：

```text
冻结图片 + 冻结审核上下文
  -> Provider 第一次审核
  -> 合法 JSON：进入既有像素审核与交付门禁
  或
  -> 空/非 JSON/语法错误
  -> 同一图片、同一上下文、同一路由的一次 JSON 序列化恢复
  -> 合法 JSON 或 fail-closed 人工审核
```

硬边界：

- 不在本地补逗号、补括号、猜字段或修复视觉结论。
- 恢复请求只能增加序列化说明，不能改变用户提示词、参考图、审核契约或
  视觉判定。
- 两次都失败时，图片仍保留，状态为 `manual_review`，不能自动交付。
- Provider 错误与图片质量失败分开记录；格式错误使用
  `provider_error_class=malformed_json` 和公开问题码
  `provider_malformed_json`，且 `universal_quality_failure=false`。
- 每次真实视觉审核默认最多两次 Provider 调用；运维仍可通过现有配置显式
  降低次数。

## 输出预算

视觉审核输出默认上限由 1600 提高为 3200 tokens，并支持
`V3_VISION_INSPECTION_MAX_OUTPUT_TOKENS` 覆盖，范围限制为 800–8000。
这是为完成冻结审核结构预留序列化空间，不是放宽审核内容或让模型输出更多
创意文本。

## 验收要求

至少覆盖：

1. 不完整 JSON 被识别为 `malformed_json`，而不是被本地修复。
2. 第一次格式错误、第二次合法时，第二次带序列化恢复标志并最终认证。
3. 两次格式错误时，准确进入人工审核，不产生质量失败结论。
4. Chat Completions 使用新的输出预算；既有 Responses/Chat 协议选择、超时
   和 fail-closed 行为不回退。
