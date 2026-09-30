# VPS 低内存稳定性与 OOM 优化开发文档

## 1. 目标与当前阶段

### 总目标

在不增加 VPS 内存、不降低 V3 图片质量、不跳过视觉审核、不缩短 Provider 等待时间的前提下，消除 Alchemy VPS 的整机 OOM 风险，使超出当前容量的任务排队等待，而不是同时占用内存并拖垮整台主机。

### 本阶段目标

先完成低风险、可回滚的峰值压制：

1. V3 完整生成流水线同时只执行一条，后续任务排队；
2. 视觉审核并发默认降为一条，并改为可配置；
3. 同步任务从每分钟全量扫描改为低频、不可重入、只做必要同步；
4. 启动后的 V2 资源预热不阻塞主服务，后续按批次或按需执行；
5. 增加内存、Swap、OOM、同步耗时和健康检查证据；
6. 观察稳定后再决定是否设置硬内存上限，不在本阶段盲目限容器内存。

## 2. 现场证据

2026-09-30 VPS 只读诊断得到：

- 主机内存约 1.9 GiB；
- Alchemy V1 容器约 1.13--1.42 GiB；
- V1 Python 进程约 1.12 GiB RSS，并有约 1.08 GiB 进入 Swap；
- Swap 2 GiB 已使用约 1.1--1.4 GiB；
- 根分区约 94%，`/opt/alchemy-media-agent-releases` 约 15 GiB；
- `2026-09-30 00:46:42 CST` 发生 `global_oom`，内核杀掉 Alchemy 容器内 Python 进程；
- Docker 记录 Alchemy 容器以 exit 137 退出并重新启动；
- `2026-09-30 06:34:19 CST` 再次出现 system slice 被 OOM killer 杀进程；
- `alchemy-media-sync.timer` 每 60 秒运行一次；
- 每次同步扫描约 285 MB 的 V1 输出和约 1.3 GB 的 V2 输出，并递归执行远端 `chown/find/chmod`；
- 当前没有证据证明磁盘错误、hung task 或网络故障是主因。

## 3. 修正模型

### 3.1 权威判断

根因是低内存主机上多个完整工作流、Base64/图片临时副本、视觉审核并发、周期性大目录扫描叠加，最终触发主机级 OOM。Provider 超时不是根因，不能通过缩短超时掩盖问题。

### 3.2 Core 与辅助层边界

- Core：V3 任务状态、参考图权威、Provider 输入、审核结论和正式交付语义保持不变；
- Enhanced：生成并发和视觉审核并发改为有界排队；
- Auxiliary：同步、缩略图预热、资源监控和恢复策略不得改变生图结果；
- 任何资源不足都必须表现为 queued / waiting / safe failure，不能伪造 GENERATED、审核通过或已交付。

### 3.3 具体策略

#### A. V3 生成入口单并发

将 `V3_BACKGROUND_GENERATION_WORKERS` 设为 1，保留现有 Provider 内部串行锁。第二个任务仍创建并保留服务端记录，但等待执行，不重复创建 Job、不自动改变提示词、不丢失项目上下文。提交到执行器队列时保持 `planned`，只有真正拿到 worker 后才转为 `generating` 并启动 Provider watchdog，排队时间不消耗生图预算。

规划并发保持 1。

#### B. Vision 单并发

将视觉审核并发上限从固定 2 改为环境变量控制，默认 1。视觉审核失败仍按原有 `certified=false` 和人工确认语义处理，不降低审核标准。

#### C. 图片内存生命周期

后续实现必须优先使用路径/临时文件传输；Brain 使用缩略图或摘要，Provider 使用正式输入，Vision 使用受控审核副本。大对象在请求完成后解除引用，不把完整 Base64 写入日志、Job metadata 或历史投影。

本阶段只添加边界和测试，不改变 V3 参考图选择、原图事实或最终输出质量。

#### D. 同步任务降频与防重入

同步从每 60 秒改为每 10 分钟起步，并增加 `flock`。同步失败不阻断 Alchemy 主服务。远端权限不再每轮对完整目录递归修改；权限应依赖同步参数、目录默认权限或只处理新增文件。

#### E. 预热改为非阻塞

V2 case thumbnail 预热不得成为启动阻塞或一次性峰值。索引先可用，预热按批次执行，单项失败只记录，不影响主服务和已有索引。当前代码已经通过独立 `asyncio.to_thread` 任务执行搜索索引预热；V2 资源同步 worker 也独立于 API/任务 worker，当前 VPS 周期为 7 天，因此本轮不额外改动其业务代码。

#### F. 资源保护延后

完成 A--E 并观察峰值后，才决定 `MemoryHigh/MemoryMax`。硬限制必须预留系统、Nginx、V2 和 Docker 的空间，不能未经峰值证据直接设置过低值。

## 4. 非目标与禁止事项

- 不减少 V3 Provider 超时；
- 不关闭 Vision Review；
- 不减少用户明确上传的参考图；
- 不修改 V3 参考图权威、连续性主图、Prompt、审核阈值或计费；
- 不增加 Uvicorn worker 或 V3 并发；
- 不关闭 Swap；
- 不通过周期性重启掩盖内存增长；
- 不直接删除用户图片、项目、历史或上传素材；
- 不使用无差别 `docker system prune`；
- 不在没有新版本和回滚证据时直接覆盖 VPS 代码。

## 5. 允许修改边界

代码与测试：

- `src_skeleton/app/main.py`：V3 生成执行器并发默认和排队测试；
- `alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/vision_inspector.py`：Vision 并发配置；
- `alchemy_creative_agent_3_0/tests/`：并发、失败、排队和配置回归；
- `scripts/` 或 `ops/`：同步脚本/定时任务的可回滚配置；
- 本文档及必要的部署说明。

远程只读/运维边界：

- `/etc/systemd/system/alchemy-media-sync.timer`；
- `/etc/systemd/system/alchemy-media-sync.service`；
- `/usr/local/bin/sync_alchemy_media_to_amadeus.sh`；
- Docker 当前容器的环境和状态检查；
- systemd journal、kernel OOM、Docker events、cgroup memory events。

远程改动必须先备份原文件，先执行 `systemd-analyze verify` 和 shell 语法检查，再 reload；任何失败可恢复原文件并重新加载。

## 6. 分阶段执行顺序

### Phase 0：冻结与审计

- 保存本次现场证据；
- 记录当前 main、未提交文件和 VPS active release；
- 独立审计本方案，确认没有改变 Core 业务语义。

### Phase 1：本地最小代码修复

- V3 generation worker 默认 1；
- Vision 并发默认 1、环境变量可配置；
- 生成队列生命周期保持 `planned -> generating` 的真实转移，排队任务不提前启动超时计时；
- 增加配置和排队行为回归；
- 运行相关 V3/V2/前端回归、语法和编译检查。

### Phase 2：同步与预热修复

- 同步定时器改为 10 分钟；
- 加 `flock` 防止重叠；
- 删除每轮全目录权限递归操作，改为 rsync `--chown/--chmod` 处理本轮新增或更新文件；
- 已核实 V2 启动索引预热是非阻塞任务，资源同步 worker 与 API/任务 worker 分离；本轮保留现有逻辑，不人为增加 V2 改动面。

### Phase 3：独立审计与本地放行

- 冻结 diff；
- 独立审计检查 scope、并发、失败语义、V3 Core 不变和回滚路径；
- 审计只能返回 PASS/FAIL/INSUFFICIENT_EVIDENCE；
- FAIL 只修复指出的边界，然后重新冻结和审计。

### Phase 4：VPS 受控应用

- 先只应用 Phase 2 的备份式 systemd/同步配置；
- 代码版本只有在用户明确要求发布并完成集成后才部署；
- 应用后验证 timer、sync、healthz、V2 health、Docker 状态和 OOM 增量；
- 观察期间不执行真实付费生图作为资源试验。

本轮已在 VPS 完成的运维应用（2026-09-30）：

- `/etc/systemd/system/alchemy-media-sync.timer`：`OnUnitActiveSec=10min`；
- `/etc/systemd/system/alchemy-media-sync.service`：通过 `/usr/bin/flock -n /run/alchemy-media-sync.lock` 防重入；
- `/usr/local/bin/sync_alchemy_media_to_amadeus.sh`：移除每轮远端全目录 `chown/find/chmod`，由 rsync `--chown=www-data:www-data` 和已有 `--chmod` 负责目标文件权限；
- 当前应用容器 `.env`：`V3_BACKGROUND_GENERATION_WORKERS=1`、`V3_VISION_INSPECTION_CONCURRENCY=1`；
- 备份目录：`/root/alchemy-media-stability-backup-20260930T122955Z`；
- 应用后 V1/V2 health 通过，容器 `restart_count=0`；最近同步正常结束。

说明：以上记录的是本次代码发布前的 VPS 状态：当时运行的是 `f41dd365` 镜像。随后需以本次发布的完整提交号重新核验 active release、容器环境变量和进程状态；不要把发布前的状态记录误读为最终线上验收结论。

### Phase 5：资源上限决策

- 至少取得一段稳定观察窗口的 RSS、cgroup、Swap、延迟和 OOM 证据；
- 再决定是否设置 MemoryHigh/MemoryMax；
- 若单个 V3 任务峰值本身超过剩余容量，必须明确报告“单机容量不足”，不能用审核或超时策略掩盖。

## 7. 验收标准

### 本地

- V3 worker 默认值为 1，环境变量可覆盖；
- Vision 并发默认值为 1，非法配置安全回退；
- 两个并发生成请求最多一个进入完整执行，另一个保持可查询的等待状态；
- Provider、参考图、review、delivery 语义测试不变；
- 同步脚本 shellcheck/语法检查和防重入测试通过；
- 既有相关回归全部通过；
- `compileall`、JavaScript `node --check`、`git diff --check` 通过。

### VPS

- `alchemy-media-sync.timer` 显示 10 分钟间隔；
- 同步任务不重入，单次执行有明确开始/完成日志；
- Alchemy、V2、Nginx health 全部正常；
- Docker restart policy 保持 `unless-stopped`；
- 配置应用前后原文件可恢复；
- 观察期间无新增 `global_oom`、`Out of memory`、exit 137 或服务反复重启证据。

## 8. 回滚

- 本地代码回滚仅限本次新增文件/符号，不覆盖用户已有未提交前端改动；
- 远程 systemd 文件按时间戳备份，恢复后执行 `daemon-reload`；
- 同步脚本恢复后先 `bash -n`，再手动运行一次只读/受控检查；
- 不通过 `git reset --hard`、`git clean` 或覆盖式 checkout 回滚。

## 9. 当前放行状态

Phase 1 本地代码修复、Phase 2 远程同步运维修复、独立审计和受控健康复核已完成；专项回归、编译和 diff 检查通过。仍不声称 OOM 已根治：当前主机可用内存仍很低，必须经过观察窗口确认无新增 OOM/exit 137；Phase 5 的硬内存上限决策暂缓。本次发布后，必须以实际 active release、health、容器重启计数和内核 OOM 观测结果作为线上放行依据。
