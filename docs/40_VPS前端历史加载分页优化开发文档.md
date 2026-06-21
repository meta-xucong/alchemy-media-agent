# 40. VPS 前端历史加载分页优化开发文档

## 背景

VPS 端已经完成过一轮静态资源优化：前端 JS/CSS 由 Nginx 直出并预压缩，首屏初始化也减少了非必要同步请求。V2 案例库也已经通过第 31/32 章完成轻量索引、分页案例、缩略图分档、ETag、下一页预取和 zip 成员索引缓存。

继续审计后，剩余的低成本优化点集中在历史缩略图列表：

- 桌面端 V1 历史仍请求 `/v1/image/history?limit=1000`。
- 手机版 V1 历史仍请求 `/v1/image/history?limit=1000`。
- 桌面端 V2 历史仍请求 `/api/v2/veyra/history?limit=1000`，失败或为空时再请求 `/api/v2/image/history?limit=1000`。
- 手机版 V2 历史同样如此。
- 前端虽然只先渲染 24 张，但网络和 JSON 解析已经承担了最多 1000 条历史记录的成本。

本章把历史缩略页改成兼容分页：接口保留旧行为，新增 `offset` 参数；前端创作页首批只拉一页，需要更多时再追加。账户面板仍保留原来的完整聚合请求，避免影响账户历史、用量和模板使用记录的准确展示。

## 目标

1. V1/V2 创作页历史列表首屏不再拉取 1000 条历史。
2. “加载更多历史”可以先展开本地已取数据，不够时再请求下一页。
3. 星标筛选继续可用；分页模式下只显示当前已加载范围内的星标，用户可继续加载更多历史扩展范围。
4. V1/V2 后端接口保持向后兼容，旧 `limit` 调用不需要修改。
5. 不改变生图、继续修改、星标写入、账户隔离、扣费、模板锁定、Claude 编排和 provider 选择逻辑。

## 非目标

- 不引入 CDN、对象存储、图片服务或新的带宽成本。
- 不重写历史存储格式。
- 不改变账户面板的完整历史聚合。
- 不清理生产历史图片。
- 不改 V2 生成链路，不让 V2 backend 调用 V1。

## 模块边界

### V1

- 后端：`src_skeleton/app/main.py` 的 `/v1/image/history` 新增 `offset` 查询参数。
- 存储：`src_skeleton/app/storage/local.py` 不需要改存储格式。V1 endpoint 仍统一聚合 repository、manifest 和 stray generated output 后排序，再做分页切片。
- 前端：`src_skeleton/app/static/app.js` 和 `src_skeleton/app/mobile_static/mobile.js` 的 V1 历史加载改为分页追加。

### V2

- 后端：`custom_media_agent_2_0/app/main.py` 的 `/api/v2/image/history` 与 `/api/v2/veyra/history` 新增 `offset` 查询参数。
- 服务：`custom_media_agent_2_0/app/services/image_history.py` 只负责 V2-native history 文件，不读写 V1 `.media_storage`。
- 前端：V2 创作页历史加载使用分页路径；账户面板继续沿用完整聚合。

该改造满足 V2 Strict Isolation：V2 后端不调用 V1，不读取 V1 历史，不依赖 V1 存储。

## 接口设计

### V1 历史

```text
GET /v1/image/history?limit=72&offset=0
```

返回仍为：

```json
{
  "items": [],
  "total": 0
}
```

兼容规则：

- `offset` 默认 `0`。
- `limit` 保持原范围 `1-1000`。
- 旧请求 `/v1/image/history?limit=1000` 返回行为不变。
- `total` 表示权限过滤后的总数，不是当前页数量。

### V2 历史

```text
GET /api/v2/veyra/history?limit=72&offset=0
GET /api/v2/image/history?limit=72&offset=0
```

兼容规则同 V1。V2 服务内部只对 V2-native history 做 offset 切片。

## 前端设计

新增常量：

```text
historyFetchPageSize = 72
v2HistoryFetchPageSize = 72
```

桌面和手机统一策略：

1. 刷新历史时请求第一页 `limit=72&offset=0`。
2. 本地初始仍只渲染 24 张，降低 DOM 和图片加载压力。
3. 点击“加载更多历史”：
   - 如果本地已取但未渲染完，先多渲染 24 张；
   - 如果本地已取全部渲染完但后端还有更多，使用当前已取数量作为 `offset` 请求下一页并追加；
   - 追加后继续保持最多多展示 24 张。
4. 删除或手动刷新历史后，重新从第一页加载，避免 offset 与数据变动错位。
5. 账户面板保留 `limit=1000`，因为它不是首屏创作页，并且承担账户历史聚合展示。

## 验收标准

1. V1 `/v1/image/history` 支持 `offset`，total 正确，分页顺序稳定。
2. V2 `/api/v2/image/history` 和 `/api/v2/veyra/history` 支持 `offset`，total 正确，权限过滤后分页。
3. 桌面端 V1/V2 创作页脚本不再用 `limit=1000` 加载创作历史首屏。
4. 手机端 V1/V2 创作页同样分页加载。
5. 星标按钮、只看星标、继续修改入口不受影响。
6. 全量测试通过。

## 测试计划

- `python -m pytest tests/test_api_smoke.py::test_v1_image_history_supports_offset_pagination -q`
- `python -m pytest tests/test_api_smoke.py::test_v2_image_history_supports_offset_pagination -q`
- `python -m pytest tests/test_api_smoke.py::test_frontend_static_app_is_served tests/test_api_smoke.py::test_mobile_h5_app_is_served_independently -q`
- `node --check src_skeleton/app/static/app.js`
- `node --check src_skeleton/app/mobile_static/mobile.js`
- `python -m pytest tests -q`
- `git diff --check`
