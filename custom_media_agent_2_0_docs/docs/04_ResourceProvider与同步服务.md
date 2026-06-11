# 04. ResourceProvider 与同步服务

## 目标

ResourceProvider 负责把外部案例资源接入 2.0。它不能被写死为某个 GitHub 仓库，而要支持未来扩展：

1. GitHub prompt 仓库。
2. 内部精选案例库。
3. 客户私有案例库。
4. 设计师上传的模板包。
5. 第三方 marketplace。

## Provider Manifest

每个 ResourceProvider 必须声明：

1. `provider_id`。
2. `provider_type`。
3. `source_uri`。
4. `license_policy`。
5. `sync_mode`。
6. `parser`。
7. `capabilities`。
8. `risk_policy`。
9. `enabled_categories`。
10. `update_detection`。

示例见 [resource_provider_manifest.example.json](../templates/resource_provider_manifest.example.json)。

## 首个 Provider

首个 provider：

```text
provider_id: github_evolinkai_gpt_image_cases
provider_type: github_repository
source_uri: https://github.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts
```

解析优先级：

1. `cases/*.md` 为 prompt 和案例描述主来源。
2. `images/` 为案例预览图来源。
3. `data/ingested_tweets.json` 可作为来源 metadata 辅助。
4. 多语言重复内容默认不作为独立案例。

## 同步架构

```text
Scheduler
  -> ResourceSyncService
  -> ProviderAdapter
  -> RawSnapshotStore
  -> Parser
  -> CaseNormalizer
  -> SafetyLicenseClassifier
  -> EmbeddingIndexer
  -> PublishIndex
```

## 同步模式

### 定时同步

后台 scheduler 按 provider 配置运行。默认：

1. 每 6 小时检查一次更新。
2. 若远端 commit SHA 未变化，不重新解析。
3. 若变化，创建 `provider_sync_run`。

### 手动同步

中枢 agent 可调用 `request_resource_sync()`，但只是创建同步请求，不在 agent turn 中跑完整同步。

### 增量同步

若 provider 支持 commit diff：

1. 只拉取变化文件。
2. 只重算变化案例。
3. 只刷新受影响 embedding。

否则回退到 snapshot 解析。

## 解析输出

Parser 输出 `PromptCase`：

1. `case_id`。
2. `provider_id`。
3. `source_ref`。
4. `title`。
5. `category`。
6. `raw_prompt`。
7. `prompt_atoms`。
8. `visual_features`。
9. `use_cases`。
10. `style_tags`。
11. `risk_tags`。
12. `asset_refs`。
13. `license_policy`。
14. `quality_score`。
15. `embedding_text`。

示例见 [prompt_case.example.json](../templates/prompt_case.example.json)。

## 发布策略

解析完成后不能立刻覆盖线上索引。必须：

1. 写入 staging。
2. 校验 case count、解析率、风险分类。
3. 生成 sync report。
4. 通过后切换 active index。

失败时保持上一版 active index。

## 错误处理

1. 网络失败：重试并记录。
2. 仓库结构变化：标记 `parser_error`。
3. 图片缺失：保留案例，但标记 `asset_missing`。
4. prompt 缺失：不发布该案例。
5. 授权不明：标记 `commercial_use_unknown`，只能用于灵感，不用于模板最终资产。

## Agent 可见信息

Agent 不能看到 provider token。Agent 只能通过工具看到：

1. provider 是否可用。
2. 最新同步时间。
3. 案例摘要。
4. 授权与风险标签。
5. 可用模板字段。

## 未来扩展

新增 provider 不需要修改 `CreativeManagerAgent` 主逻辑，只需要：

1. 增加 manifest。
2. 实现 adapter。
3. 实现 parser。
4. 通过 provider contract test。
5. 开启同步。
