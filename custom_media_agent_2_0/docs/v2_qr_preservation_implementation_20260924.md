# V2 QR 最小修复：更新后基线复核与实施记录

## 当前阶段
目标：关闭未经明确授权的 QR 后处理，验证失败原样返回 QR 前图片。
阶段：本地代码与回归；不执行 VPS 部署、历史修复或付费生成。
基线：6f2f059dff3928b928c12ab979e24f6d82e8933a；2026-09-24 任务日期。
实际远程设备时钟与会话日期不同，提交/测试以各工具原始时间为准。
工作区：`.codex-work/v2-qr-opt-in-safety`，分支 `codex/v2-qr-opt-in-safety`。
主工作区仍为 `D:\AI\Alchemy Media Agent System` 的 main，保持不变。

## 兼容性复核
已 fetch origin/main；开始时 HEAD 与 origin/main 相同且工作区干净。
3e16d43a 到当前基线的整个 V2 目录无 Git 差异。
前次审计列出的 7 个源码文件原始 SHA256 全部一致，AGENTS 也未变化。
结论：前次最小方案可直接作为修复依据；不覆盖已合并的 V3 优化。
前次两份未提交 Markdown 已不在本地目录；会话附件完整，已读取核对。
本记录补充本轮执行事实，不把前次设计通过冒充运行验收。

## 修正模型与边界
权威仅是当前合法 Brain 决定，经内部 keyword-only 参数传递。
metadata 是诊断镜像；外部请求、Provider、旧诊断和语义缓存不能开启。
只有布尔 True 开启；坏的可选字段独立降级 False，不改变主 Brain 生命周期。
关闭时不调用 QR helper；正常文字合成、保存和派生图继续。
源必须可解码、目标必须是明确 QR 专属意图；不猜位置、不抹白搬码。
合成只在副本上，最终编码字节目标区可解同 payload 且区外不变才提交。
失败回退 pre_qr_bytes；不增加模型请求、计费、生成重试或数据库结构。
仅改 schemas、claude_orchestrator、prompting、agents/runtime、generation、
output_storage、qr_preservation 七个既有源码文件及对应测试/本文档。
PNG/无损 WebP 可验证处理；JPEG、旋转、多帧、不确定曲面不强行改图。
本地完整回归与真实正负例的验收状态分别记录，不合并宣称完成。

## 本轮验证结果
V2 原始全量基线：258 passed，1 个既有 Starlette 弃用警告，68.60 秒。
首批新增回归先验证旧实现：40 failed，5.91 秒；随后修复为 40 passed。
更新旧 QR 合同断言后，QR 定向回归 53 passed；没有保留涂白搬码旧行为。
首次全量：311 passed，1 failed。失败为新增说明使无素材 inline prompt 超预算。
责任层是 Brain 请求压缩，不是 QR 像素质量；没有扩大 3600 字符原测试上限。
修正为无参考素材只携带关闭说明，有素材保持完整授权规则；用户提示词不裁剪。
补充两类输入回归后，全量最终：314 passed，0 failed，0 skipped，0 deselected。
实际用时 71.03 秒，pytest exit 0；包含新增的 56 项 QR 安全/决策测试。
警告仅为同一 Starlette/anyio 弃用提示，本次不做依赖升级。

## 审计结论与支持范围
严格布尔值、普通任务 QR 零调用、外部 metadata 伪造拒绝均通过测试。
真实 QR 测试素材使用本地 qrcode 创建并由 OpenCV 实际解码，不是伪造 decoded 字段。
PNG 和无损 WebP 正例通过；最终目标解码与非目标 RGBA 像素一致性通过。
同图第二次处理原字节复用；整图其他位置相同 payload 不能替目标区域代验。
源无解码/几何异常、多来源、无明确 QR 位置、编码后无 QR 均保持输入字节。
可选处理错误不撤销合法文字合成；任务取消和主图磁盘写入错误仍正常抛出。
经受控 Brain 和原生 V2 mock Provider 的端到端正例通过下载、预览、缩略图及历史检查。
这些是受控本地测试，不是已调用真实 Brain/生图服务或验证原五张历史图片。
首版明确海报平面位置才支持贴回；包装曲面/不明映射不猜、不新增角标。
旧的危险覆盖/重定位辅助函数虽可能仍在文件中，活动入口已不调用；审计检查通过。
变更仅七个既有 V2 源码文件、相关测试及本文档；不改 V3、Provider、计费或公共路由。

## 本地证据与后续门禁
证据位于仓库根 `.controlled-validation/v2-qr-opt-in-20260924/`。
主要文件：baseline-full.log/xml、qr-red.log、qr-round1.log、legacy-qr-contract.log、
qr-round2.log、final-full.log/xml、final-full-round2.log/xml。
状态：本地代码与回归阶段通过；仍需真实 Brain/Provider 正负例与审批后的集成/部署。
本轮未请求付费生图、未连接 VPS、未恢复历史污染图片、未重启任何服务。
功能分支不等于主线或生产版本；合并前须复核主线最新版本并保留其他会话的提交。

## 后续复审修正
上一节的 314 项通过是 d614d53d 阶段结果，不是最终无漏洞结论。
后续复审确认并修正了缓存指令遗漏、分阶段授权、多码歧义、源透明度及 PNG 色彩元数据五类边界。
最新本地 V2 全量为 331 passed，零失败/跳过/排除；新增 17 项复审反例/控制用例。
详见同目录 `v2_qr_preservation_reaudit_20260924.md`，使用最新复审提交，不继续应用旧补丁。
主线合并、真实供应商验收、VPS 部署和历史污染恢复仍未在本轮执行。
