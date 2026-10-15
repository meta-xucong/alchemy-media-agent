# V3 复核图可见性修复方案与验收

## 目标与阶段

**总目标：**V3 已生成但未取得正式交付资格的图片（包括证据不完整、待人工复核和明确质量失败）均可在 review-only 区域查看；正式交付资格仍只由现有审核与交付规则决定。

**本阶段目标：**修复桌面端和移动端对所有未取得正式交付资格图片的呈现缺口，确保不同审核结论使用准确提示；修复图片身份合并、移动空态/灯箱及 generic export 的逐图交付过滤，并完成回归与独立代码审计。本阶段不批准合并或部署。

## 冻结范围

- **设计/实现/审计等级：**D0 / I2 / A2（generic export 改动触及正式输出合同）。
- **I2 触发依据：**同一张图在后端复核投影、当前 Job 候选、项目历史、移动端图库之间有不同读路径；必须保证图片可见性改善不改变正式交付资格、引用和历史语义。
- **允许修改：**
  - `src_skeleton/app/static/app.js`
  - `src_skeleton/app/mobile_static/mobile.js`
  - `alchemy_creative_agent_3_0/app/product_api/service.py`
  - `alchemy_creative_agent_3_0/tests/test_v3_doc263_ecommerce_ui_recovery_browser.py`
  - `alchemy_creative_agent_3_0/tests/test_v3_generic_export_review_gate.py`
  - `tests/v3_review_image_identity.test.mjs`
- 本目录中的本方案与验收记录。
- **禁止扩展：**不改审核器、质量阈值、任务状态、选择接口、品牌记忆、参考继承、模型/provider 调用或审核结论；不新增状态框架；不改 E-Commerce 专属规则。本次仅把通用导出限制到现有逐图交付投影已授权的图片；不合并或部署。

## 现状与诊断

针对 VPS 上最近检查的 V3 Job 只读检查到：图片文件和预览/缩略图地址存在；审核回执状态为 `complete`，但审核包状态为 `incomplete`，总评为 `needs_manual_review`，`quality_failure=false`。混合像素检查已完成，记录同时含有皮肤修饰、细节观感方面的疑虑，以及人物自然度和面部完整性尚未验证的证据缺口。采样时间：2026-10-13（UTC+08:00）；受控诊断引用 `V3-RI-20261013-01`。Job 标识只在受控诊断记录中，不在本功能文档公开，以免把用户项目标识长期写入通用开发文档。

因此当前提示**不是“没有运行审核”**，也**不是“已证明图片质量不合格”**。已有审核指出若干疑虑并要求人工复核，但没有给出自动质量失败结论。未对该 Job 的原始像素作人工视觉评估；不能仅凭状态推断图片好坏。

后端已有独立 `review_items` 投影，正式输出和复核图分开。前端存在可见性缺口：桌面复核区默认收起；候选列表非空时可能遮住带真实媒体 URL 的持久复核记录；移动端图库遗漏复核输出；一种审核闭环拦截状态会清空图片网格。

## 权威规则

本方案针对 `Doc55` 中“失败图片默认隐藏或折叠”的前端默认，作一个有边界的产品修订：项目复核区默认可见这些图，但每张明确标为 review-only。它不改变质量审核结论、推荐列表、正式交付或正向项目上下文；用户只是在复核区看到生成像素。

1. **图片是否可见**由经过权限过滤的项目复核输出或当前 Job 中具有安全图片地址的生成候选决定。前端只使用服务端已授权返回的数据，并按当前项目 ID 精确筛选；不得跨项目补入或重新请求其他项目资源。
2. **图片是否正式交付**仍由现有逐图审核证据和交付门控决定。复核图不能因为可见而成为正式交付。
3. `incomplete`、`needs_manual_review`、`quality_failure=false` 必须保持各自语义；UI 不把它们改写为“质量失败”或“审核通过”。
4. 复核图只用于观察，不提供正式选择、设置后续参考、写入品牌记忆或正式导出的新入口。
5. 文件/URL-less 候选与持久复核记录合并时，`output_id` 是首要图片身份；两个非空 `output_id` 不同时，不允许通过较弱别名合并。缺少 output ID 时才按相同 candidate ID 或 output-ref ID 精确匹配；共享 `asset_id` 单独不足以证明是同一图片。top-level、metadata 与 `related_job_id` 中的项目/任务身份必须一致。只有身份已确认后才补媒体 URL 和缺失元数据。
6. `hidden_output_ids` 不授予访问权限，也不替代逐图审核。授权的 review-only 区域可显示后端返回的未交付图片；它们仍不能进入正式交付、选择、后续参考、品牌记忆或 generic export。generic export 只使用 `_public_final_delivery_projection` 提供的合格 output/asset 精确绑定；若持久选择同时有 candidate 和 asset ID，candidate 精确身份优先，asset ID 只作一致性校验，不能经共享 asset alias 扩大导出集合。E-Commerce 专属导出继续使用其既有绑定规则。用户权限和后端投影优先，前端不能恢复后端未返回的资源。

## 最小实现方案

### 桌面端

- 将项目输出板中的复核记录区默认展开。
- 复核卡片持续显示“仅供复核 · 未进入正式交付”和现有复核原因。
- 对 `review_withheld_finalization_failed` 移除结果区只显示提示即早退的行为：正式交付结果保持为空，状态提示保留，随后显示 review-only 图片。
- Job 复核图来源合并持久 `review_items`、候选和资产数据；候选无 URL 时保留匹配复核行中的 URL。
- 复核图沿用 review-only 呈现路径，不加入正式输出操作。

### 移动端

- 对 `review_withheld_finalization_failed` 保留“审核未闭环”说明，但不再清空复核图；正式输出集合继续为空。
- 状态标题跟随现有 review hold kind：证据不完整/无法判定显示“审核证据需确认/自动审核需确认”，明确质量失败显示“视觉问题需处理”；不以统一的“未通过自动审查”覆盖不同原因。
- 项目图片面板和项目图库均纳入有可显示媒体 URL 的复核输出。
- 图库用可见徽标标明“复核图 · 非交付”；面板说明不能设为后续参考。
- 合并规则与桌面一致；复核图可在面板和图库直接打开，灯箱保留“复核图 · 非正式交付”和逐图原因，不显示“可继续使用”一类误导语。
- 当复核状态存在但图片集合为空时，区分仍在加载、读取失败和读取成功但无图；错误后成功刷新应清除错误提示。

### Generic export

- generic manifest 与 download 只输出逐图交付投影确认的 output/asset 绑定；全被拦截时 `generated_assets` 为空，部分交付只含合格图片。
- 不修改 E-Commerce 的专属 package 语义，也不把 review-only 图片转成新的正式交付。

### 回归用例

- 桌面：持久复核记录有图片 URL、Job 候选无 URL 时仍能显示；复核区默认展开；`needs_manual_review` 与明确 `fail_final` 图片均可查看；二者都不进入正式输出且没有正式选择动作。
- 移动端：证据未闭环图片显示审核证据待确认提示；明确 `fail_final` 图片显示质量审核失败原因，不显示“审核未闭环/证据不完整”；两者均可查看但正式输出为空，图库显示非交付徽标。
- 两端：跨字段 ID 碰撞、不同 Job/项目同值 ID 不会误合并；同字段且同 scope 的匹配记录可补媒体 URL。
- 两端：不同非空 `output_id`、共享 asset、跨字段 ID 碰撞或互相矛盾的 scope 不会合并；相同已确认图片才补 URL/元数据。
- 移动端：通过生产项目打开入口进入项目主页，断言详情与候选复核按钮可见后正常点击；复核卡打开灯箱时显示非交付标题与逐图原因。终态复核空集合分别显示读取失败、仍在读取或确实暂无图，不退化为普通“还没有图片”。
- generic export：全失败不含图片 URL；部分合格只导出合格图；manifest 与 download 一致。

## 验收标准

| 门槛 | 通过条件 | 证据 |
|---|---|---|
| 诊断准确 | 能区分审核执行、证据完整性、自动质量失败和人工确认 | 对真实只读记录逐字段核对；不声称未检查的像素结论 |
| 桌面可见 | URL-less 候选回退到持久 URL；manual-review 和 fail-final 图在默认展开区可查看 | Playwright 断言两种状态、准确原因文案、无选择动作、正式输出不含复核图 |
| 移动端可见 | 证据未闭环与 fail-final 分别显示不同原因且均可查看；正式输出为空 | Playwright 断言 `incomplete` 不显示质量失败；`fail_final` 不显示审核未闭环；图库有非交付徽标 |
| 身份/投影边界 | ID 类型碰撞、已知 Job/项目冲突不错误合并；审核排除 ID 只阻止正式晋升，不阻止 review-only 查看；其他项目记录不可见；匹配记录可补 URL | 确定性合并器及桌面/移动正反例 |
| 不改交付权威 | 正式结果仍为空/保持原值；没有放宽审核或新增晋升动作 | 代码审计与回归断言 |
| Generic export | 非 E-Commerce 清单和下载只含逐图合格绑定 | Python service 回归：全失败、部分交付、manifest/download 对照 |
| 静态验证 | 两份 JS 语法、Python 测试文件语法、`git diff --check` 通过 | 本地命令输出 |
| 独立审计 | 另一名只读审计者对冻结差异返回 PASS | 固定工作树/差异摘要及审计回执 |

真实浏览器回归若因测试依赖不可用，必须记为“未执行”，不能记为通过。它是验收限制，需要在具备 pytest/Playwright 的环境补跑。

## 风险与回滚

- 本改动影响前端复核图显示和 generic manifest 投影，不改变持久记录，也不写新数据。回滚需同时回滚两端 UI、通用导出过滤及相应测试；不需要数据迁移或清理。
- 主要风险是错误合并两张图或误展示为正式交付。通过按 ID 字段与已知 Job/项目 scope 限定合并，并显式标注 review-only 及保持正式交付逻辑不变来控制。
- 此文档和代码通过仅代表本地修复阶段完成，不代表发布、VPS 版本一致、真实图片人工质量验收或整个 V3 生产验收完成。

## 当前执行记录

- 目标基线：`569dffea4381bcd4175a44c50f3c76d0ebc46246`。
- 独立工作分支：`codex/v3-review-raw-images`。
- 主工作区：`main` 保持未修改；本地功能改动不在主工作区。
- 设计审计：通过；明确 `hidden_output_ids` 只阻止正式推荐/交付晋升，授权复核区仍可看 fail-final 图，并说明对 Doc55 默认 UX 的有限修订。
- Dot 增量审计指出前端身份合并、移动端终态空态/灯箱、浏览器断言不可靠及 generic export 缺逐图资格过滤。身份合并已改为 output/candidate/ref 精确匹配并核对 scope；灯箱优先按 output、再 candidate 匹配原因；generic manifest/download 使用共享正式交付投影和审核认可的精确 `(output_id, asset_id)` 对。
- Node 回归共 169 项通过，覆盖桌面/移动图片身份合并、共享资产和跨字段同值下的灯箱审核原因、终态提示、历史分页与资源清理。JS 语法检查通过。
- `pytest` 当前不可用；generic export 的 4 个真实 service 回归函数通过隔离 Python harness 直接调用（混合 pass/fail、全拦截、审核绑定错配、真实 `select_result` 保存 candidate+asset 后共享 asset ID 下仍只导出所选 candidate，以及下载/manifest 一致）。这不是 pytest 套件通过记录。
- Python AST/语法解析通过 3 个文件，`git diff --check` 通过。Playwright 浏览器用例已修正 badge/`innerHTML` 断言并扩展覆盖，但因环境缺少 pytest/Playwright 未运行，不能记为浏览器通过。
- 独立只读复审：代码改动范围 PASS，无新增生产代码阻断；pytest/Playwright 完整运行仍待具备依赖的环境补验。
- 未调用真实模型、未修改 VPS；PR #34 仍未合并或部署。
