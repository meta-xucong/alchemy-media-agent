# V3 Single Production Entry And Suite Flow Spec

Current compatibility note:

```text
Document 52 is the current authority for the next suite-flow deepening:
SuiteVariationDirector, post-generation visual inspection, automatic retry,
and output curation.

The single production entry defined here remains unchanged. Doc52 adds
background intelligence and folded quality details; it must not add multiple
engineering-style production buttons to the beginner UI.
```

## 1. 背景

V3 项目制的核心不是把流程拆成很多看似专业的步骤，而是让用户打开一个项目后，能持续产出同一套视觉方向的商业图片。

当前 46 号文档落地后，项目页已经具备：

- 项目制：Project 包住多轮 Job
- 模板先选：项目创建前选择通用、电商或未来模板
- 成果区：生成图片、已确认参考、工作流记录、长期风格
- 图片卡操作：可设为后续参考、可标记不喜欢
- 子页面：可以弹出独立操作页

但当前项目续作区仍保留了 4 个流程卡片：写需求、看图片、选方向、继续做。对初级用户来说，这会造成三个问题：

- 误以为每一步都要点进去操作
- 看图、选图、继续生成的入口重复
- 子页面像工程工作台，不像一个商业级生图制作页

因此，本阶段要把项目续作区收敛为一个真正有必要的生产入口。

## 2. 本阶段目标

把 V3 项目页重构成：

```text
项目主页
  - 项目概览
  - 生成图片
  - 已确认参考
  - 项目产物与记录
  - 长期风格
  - 一个继续生产入口

点击继续生产入口
  - 弹出制作页
  - 写一句本次需求
  - 可选上传参考图
  - 生成一组同项目风格图片
```

用户不需要理解 Prompt、工作流、Provider、Job、Scenario、Manifest 等概念。页面只告诉用户：

- 这个项目已有多少图片
- 已选哪些图作为后续参考
- 下一次生成会沿用什么
- 现在只需要写一句话就能继续生成

## 3. 固定交互原则

### 3.1 模板只在新建项目前选择

项目创建后，模板不可在项目中途切换。

项目内所有生成都读取项目的 `primary_template_id`，并通过现有 Scenario Pack 执行。

### 3.2 项目主页不堆功能面板

项目主页只承担 4 件事：

1. 看项目状态
2. 看生成图片
3. 选中满意方向或标记不喜欢
4. 查看必要记录与长期风格

不把制作表单、结果列表、解释说明全部堆在主页。

### 3.3 续作区只保留一个入口

把原来的 4 个步骤卡片收敛为 1 个主入口：

```text
继续生成套图
```

入口文案要表达：

- V3 会读取本项目已选参考
- V3 会避开用户标记过的不喜欢方向
- 用户只需要补一句本次想做什么
- 生成结果仍回到项目成果区沉淀

### 3.4 看图和选方向不进入子页面

图片相关动作直接在成果区完成：

- 放大图片
- 下载图片
- 设为后续参考
- 不喜欢这个方向

不再设置单独的“看图片”“选方向”子页面。

### 3.5 长期风格只在项目主页出现

长期风格不是“继续生产”的一部分，不在制作页重复展示。

项目主页的长期风格区负责：

- 保存当前项目方向
- 更新已有风格
- 用此风格新建项目

制作页只负责本项目继续生成。

## 4. 页面结构

### 4.1 项目主页

项目主页保留当前两区结构，但语义调整为：

- 常驻展示区
  - 项目概览
  - 生成图片
  - 已确认参考
  - 项目产物与记录
  - 长期风格

- 继续生产区
  - 一个主入口卡片

主入口卡片显示：

- 标题：继续生成套图
- 主文案：沿用这个项目的风格，继续生成新图
- 状态信息：
  - 已选参考数量
  - 已生成图片数量
  - 避开方向数量

### 4.2 制作页

制作页由主入口打开，仍复用当前 `v3ProjectSubpage`，但只作为“制作页”，不是多步骤工作台。

制作页显示：

- 一句本次需求输入框
- 可选上传参考图
- 可选品牌或感觉字段
- 生图进度条
- 生成按钮
- 当前生成结果区

制作页隐藏：

- 侧边工程面板
- 重复的长期风格入口
- 单独的看图、选方向、继续做解释卡片

生成完成后：

- 当前制作页可以看到本次结果
- 项目主页的生成图片区同步显示
- 用户在图片卡上选择满意结果

## 5. 文案规则

禁止使用：

- Provider
- Job
- Prompt Compiler
- Scenario Runtime
- Manifest
- Capability Module
- Seed
- Sampler
- ControlNet
- IP-Adapter

推荐使用：

- 项目
- 图片
- 参考
- 方向
- 风格
- 套图
- 继续生成
- 保存长期风格

按钮必须像用户真实动作：

- 继续生成套图
- 生成一组图片
- 设为后续参考
- 不喜欢这个方向
- 下载
- 返回项目主页

避免把解释文案做成大量卡片。说明信息应尽量压缩为：

- 一行提示
- 状态标签
- 折叠详情
- 进度条提示

## 6. 代码改造范围

### 6.1 HTML

修改 `src_skeleton/app/static/index.html`：

- `v3StepActionRegion` 标题从“继续这个项目”调整为“继续生成套图”
- 副文案改为更短、更面向小白
- 子页面默认文案改成制作页语义
- 制作页按钮文案允许改成“生成一组图片”

### 6.2 JavaScript

修改 `src_skeleton/app/static/app.js`：

- `renderV3StepCards`
  - 不再渲染 4 个步骤卡片
  - 改为渲染 1 个 `v3-production-entry`
  - 点击后打开 `compose` 制作页

- `v3ProjectSubpageCopy`
  - `compose` 改成“继续生成套图”
  - 其他旧步骤不作为正常入口

- `renderV3BriefScene`
  - 改成制作页前的极简状态摘要
  - 不再展示流程说明式卡片

- `applyV3SubpageSceneVisibility`
  - `compose` 同时展示输入区和本次结果区
  - 默认隐藏侧边面板和项目下一步动作

- `createV3Job`
  - 生成完成后保持在制作页，不跳到旧的 review 步骤
  - 图片选择仍由成果区和结果卡片承担

- `selectV3OutputItem`
  - 选中后不跳转到旧的 select 步骤
  - 保持项目主页或当前制作页状态即可

### 6.3 CSS

修改 `src_skeleton/app/static/styles.css`：

- 保留旧 `.v3-step-card` 基础样式以兼容测试与历史 DOM
- 新增或强化 `.v3-production-entry`
- 让继续生产入口更像一个主 CTA，而不是流程步骤
- 桌面端规整、紧凑、有商业质感
- 移动端单列、不横向溢出

### 6.4 Tests

修改 `tests/test_v3_commercial_frontend_shell.py`：

- 断言存在 `.v3-production-entry`
- 断言脚本包含 `renderV3ProductionEntry` 或等价单入口逻辑
- 断言页面出现“继续生成套图”
- 保留现有项目制、模板先选、成果区、工作流、长期风格测试

## 7. 验收标准

### 7.1 静态验收

- V3 首页仍先选模板再创建项目
- 项目内不出现模板切换入口
- 项目页只有一个继续生产入口
- 子页面不再显示 4 个操作台
- 生成结果、已确认参考、工作流记录、长期风格仍存在
- 普通可见 UI 不出现工程术语

### 7.2 行为验收

- 打开项目后能看到生成图片区
- 点击“继续生成套图”打开制作页
- 制作页能写需求、上传参考、生成图片
- 生成后图片能在制作页和项目主页看到
- 图片卡能设为后续参考
- 已选参考会进入项目上下文
- 继续生成读取项目上下文
- 不喜欢方向会被记录为避开方向
- 长期风格仍在项目主页保存和复用

### 7.3 测试命令

```powershell
node --check src_skeleton\app\static\app.js
node --check src_skeleton\app\mobile_static\mobile.js
python -m pytest tests\test_v3_commercial_frontend_shell.py -q
python -m pytest alchemy_creative_agent_3_0\tests\test_v3_project_mode.py tests\test_v3_commercial_frontend_shell.py -q
python -m compileall -q alchemy_creative_agent_3_0 src_skeleton
git diff --check
```

## 8. 非目标

本阶段不做：

- 后端大重构
- 替换 Scenario Pack
- 替换 Product API
- 替换 Provider
- 重写电商模板完整业务逻辑
- 删除旧接口

本阶段只把 V3 项目续作体验从“流程步骤卡片”升级为“单一商业生图制作入口”。
