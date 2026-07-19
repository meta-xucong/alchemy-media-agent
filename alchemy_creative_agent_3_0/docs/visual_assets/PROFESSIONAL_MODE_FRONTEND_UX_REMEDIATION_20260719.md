# Professional Mode 前端 UX 修复合同（People Asset / Face Identity / Anchor Pack）

状态：`implementation_required`

基线：`origin/main@56fbac6`

共享前端原则见 Doc172。本文件只定义 Professional Mode 的界面和交互，不新增
Provider、Brain、Review、Retry 或存储实现。

## 1. 当前阻断

当前 V3 首页只有通用模板、电商模板和摄影师模板，没有 Professional Mode、Visual
Asset Library、People Asset、Face Identity 或 Anchor Pack 的入口。用户输入“建立
专业视觉资产”仍然只能创建 General 项目，形成静默降级风险。

后端已经存在 project-scoped People Asset 生命周期 handler，但前端没有正式接缝，
也没有向普通用户解释 root upload、ready、prepare、review、activate 的区别。

## 2. 用户可见入口

Professional 必须是明确选择的模式，不得因“人物”“模特”“人脸”等关键词自动打开。

入口文案建议：

```text
标准创作
适合一次生成和普通项目续作

专业模式：使用视觉资产
适合需要长期保持同一个人物形象的项目
```

选择 Professional 后必须显示：

- 当前项目的人物资产；
- 新建人物资产；
- 选择其他人物资产；
- 返回标准创作。

Professional 未完成资产绑定时，不能悄悄使用 Standard 生成。用户可以明确选择
“返回标准创作”，但这必须是用户主动操作。

## 3. People Asset 生命周期界面

### 3.1 状态卡

使用共享状态模型，显示以下人话状态：

```text
需要上传源图
源图正在保存
源图已准备好，可以建立人物资产
正在准备多视角人物参考
等待质量检查
部分视角需要处理
人物资产已准备好，等待确认启用
已启用
已过期/已被新版本替代
无法完成，可查看原因并重新开始
```

不要显示 `PeopleAsset`、`AnchorPack`、hash、pack_version_id、provider 或 job_id。

### 3.2 正式 API 接缝

前端 adapter 只调用既有 project-scoped 路由：

```text
GET  /api/v3/creative-agent/projects/{project_id}/people-assets
POST /api/v3/creative-agent/projects/{project_id}/people-assets
GET  /api/v3/creative-agent/projects/{project_id}/people-assets/{people_asset_id}
POST /api/v3/creative-agent/projects/{project_id}/people-assets/{people_asset_id}/prepare
POST /api/v3/creative-agent/projects/{project_id}/people-assets/{people_asset_id}/activate
```

需要主线补齐公开 route contract 或前端可发现的 API schema，但不得让前端自行拼接
pack、prompt、reference path、candidate 或 retry 信息。

### 3.3 上传与激活的边界

- 上传图片不等于人物资产已建立；
- ready 不等于 Anchor Pack 已通过；
- prepare 不等于已激活；
- 只有服务端返回完整、已审核、用户明确确认的 pack 才显示“启用”；
- 激活必须有确认对话框，说明“后续项目会使用这个人物版本”；
- 资产切换必须先显示当前版本和新版本差异，并支持取消；
- 不允许把 metadata-only 或 manual confirmation 显示为“已通过”。

## 4. 新手路径

```text
选择“专业模式：使用视觉资产”
→ 新建人物资产
→ 上传一张清晰正面源图
→ 等待图片准备好
→ 开始准备人物参考
→ 查看每个视角：准备中/通过/需要处理
→ 完成后确认启用
→ 回到项目继续创作
```

每个阻断状态都必须提供下一步：换图、重新准备、选择其他资产、返回标准创作或
回到项目，不能只显示“失败”。

## 5. 必须补的回归

- V3 首页能发现 Professional，但 Standard/General 不出现专业字段；
- 未选择 Professional 时，人物上传仍走普通参考图语义；
- 创建 People Asset 后，刷新、返回、重开仍保持 project-scoped 绑定；
- 上传、ready、prepare、review、activate 的按钮按状态启用，处理中不可重复点击；
- 资产未 ready、pack 不完整、版本不一致、Brain 不可用时均 fail-closed；
- 激活前没有“已启用”假状态；
- 激活后可明确返回项目并继续；
- 错误不显示内部 ID、hash、Provider 或 HTML；
- 1440/1024/390/430 四种宽度下完成完整路径；
- 浏览器刷新后服务端状态优先于 localStorage。

## 6. 完成标准

Professional 前端只有在普通用户可以独立完成“创建人物资产→准备→确认启用→回到
项目”，且没有任何静默回退、伪成功和内部错误泄漏时，才可标记
`professional_frontend_ux_passed`。这不等于 M5 或生产门禁通过。