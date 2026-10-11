# 本轮验证与交接记录

## 固定范围

- 原始基线：`5a33c05e3f54dbef786eb179973ec1407511b4e4`。
- 功能分支：`dot/history-read-scalability-20261011`。
- 最终代码、测试和 CI 工作流共 30 个变化文件的 SHA256 清单见 `evidence/source-fingerprint.json`。
- 最终指纹：`bf250cc36ca0ef2bf55342bffa1cb3c6ebd344b5f05332da5a62149c95d96317`。算法按排序路径串联 `path + TAB + file_sha256 + LF` 后计算 SHA256。文档不包含在此代码指纹中。
- 最终 Git 提交及对应 CI 以 PR 的 head/checks 为准；本记录不以父提交或旧运行冒充新提交验证。

## 云端本机验证（2026-10-11）

V1、V2 使用各自隔离 Python 3.12 环境。测试使用临时存储、mock 模式、关闭远程规划/同步 worker/telemetry；本机测试入口禁止 socket 出站。文件式入口支持 multiprocessing spawn，避免 stdin 入口的进程启动错误。

| 组别 | 结果 | 范围与限制 |
| --- | --- | --- |
| V1 综合套件 | 375 passed，256.80 秒 | 完整 `test_api_smoke.py` 加持久化、历史/索引、收藏/迁移/删除、幂等/归属、SQLite 取消与准入、Lab、SSE、严格导入等 18 个文件；有 6 条既有 FastAPI 弃用告警 |
| V2 完整 tests 目录 | 739 passed，51.38 秒 | 包括新精确计数桶、503、只读队列、查询计划、bootstrap 及既有功能；1 条 Starlette 弃用告警 |
| Node 前端合同 | 139 passed，0 failed，0 skipped | `node --test tests/*.test.mjs`；执行发布函数的 VM 合同，非完整浏览器 |
| PR28 来源/迁移映射 | 23 passed，0.33 秒 | 原始 38 项历史映射保留；新增候选源码覆盖层校验实际文件，保留 LF/CRLF 不变量 |
| 最终前端静态 smoke | 3 passed，94 deselected，1.15 秒 | 在 Lab provider 兼容补丁后重跑桌面、移动、V2 模板/历史非阻塞断言；与 375 组重叠 |
| 冷构建修订后定向复验 | 102 passed，9.39 秒 | 最终 28 项 V1 索引、44 项双池准入、7 项测量安全及 23 项来源映射；与前组重叠。375 项综合结果先于这一纯索引修订，最终 CI 将重跑完整 smoke |
| 静态检查 | 通过 | 三份前端脚本 `node --check`；全部变化 Python 文件 AST 解析；工作流 YAML 解析；`git diff --check` |

测试组有重叠，不累加成“总通过数”。源码审计者的独立工作是只读复核，不将其报告的实现者测试数冒充审计者亲自运行。

独立只读复审覆盖全部 30 项变化的代码/测试/工作流，及之后的冷构建复合索引修订；索引修订独立 10,000 行 hit/miss 探针从 100,025 降至 35 SQLite VM 步。初次冻结指纹因后续索引/测试/测量脚本变化已作废，以上为最终重新计算的交接指纹。文档、运行时性能及生产验收不包含在源码复审结论内。

可复现命令：V1 从仓库根目录按照 `.github/workflows/capacity-retention-regressions.yml` 的 V1 文件清单及完整 smoke 执行；V2 从 `custom_media_agent_2_0` 目录执行 `python -m pytest -q tests`；两者不可混用同一个 `app` 导入环境。规模测试命令及原始结果见 `benchmark-results.md`。

## 调试过程中未通过的尝试

1. 首次 V2 全套从 stdin 入口启动，两项 multiprocessing spawn 测试找不到 `<stdin>`，其余 718 项通过。改为文件式隔离入口后旧套件 720 项通过；新增计数测试后的最终套件为 739 项通过。未修改产品进程逻辑来隐藏该环境问题。
2. 首次 V1 完整 smoke 为 96 passed、1 failed。失败是连接计数测试仍要求旧主路由全扫描连接恰好一次；新测试先完成冷构建，验证热请求不逐条开库、结果一致，主路由旧连接数为零。最终综合套件全部通过。
3. 最终 V2 运行命令曾在已切换 V2 cwd 的入口再次传入 `custom_media_agent_2_0/tests`，报告找不到路径、未执行测试；更正为 `tests` 后得到上述 739 项结果。
4. 首轮规模夹具 ID 不符合旧文件恢复命名规则，不能用于前后等价验收，已经作废。正式报告使用有效 ID。图片文件为只做存在性/元数据检查的字节 stub；不证明图片解码、缩略图或视觉展示。
5. 规模探针发现首次构建中的 `kind='history' AND file_path=?` 被 SQLite 规划为逐文件扫描全部 history source。新增 `(kind,file_path)` 复合索引及增长回归后，1k→10k 冷 VM 步数近似十倍；最终 50k V1 构建约 29.69 秒。此前平方增长的探索报告未作为验收材料交付。

## 发布前后的门禁

新增 CI 覆盖 Windows 来源/有界队列、Linux V1/Lab 与 V2 小规模只读矩阵、完整 smoke/V2 suite、Node 合同，并上传矩阵报告。等待最终提交的实际 CI，不能仅凭本机结果标记为生产可部署。

用户本机脏文件、业务存储、VPS、真实 Provider 均未操作。代码通过不关闭 `risks-and-boundaries.md` 的既有生成文件归属发布窗口，也不证明旧进程 RAM 迁移、真实浏览器/图片传输或 VPS 容量已验收。首次派生构建持有写锁，部署前须在隔离副本上测量并安排受控准备。
