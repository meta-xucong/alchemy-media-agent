# Alchemy API MCP 安装指南（Codex）

此独立安装包通过 Codex 本地 STDIO MCP 连接 Alchemy 已有的认证 API。运行需要 Python 3.10+，只使用 Python 标准库；无需下载或安装完整 Alchemy 项目，也不需要额外安装 Python 包。

工具包含 V3 产品 API，以及由当前 API 密钥授权的 V1、V2 和 Alchemy Lab API。此包不包含原有本地 Native ImageGen 规划与 handoff 工具。

## 安装步骤

1. 下载并解压 `alchemy-api-mcp-v1.zip` 到固定目录，例如 Windows 的 `%USERPROFILE%\AlchemyMCP`。
2. 登录 Alchemy，打开 `https://alchemy.aiself.vip/api-access` 创建 API 密钥。密钥只显示一次，请妥善保存。默认永久有效，也可以在创建时选择有限期限。
3. 在 Codex 中打开 **Settings → MCP Servers → Add server**，添加本地 STDIO 服务：
   - **Command**：Python 可执行文件。Windows 可填 `py`（若 Codex 找不到它，请填写 `python.exe` 的完整路径）；macOS/Linux 可填 `python3` 或完整路径。
   - **Arguments**：分别添加 `-m`、`alchemy_api_mcp.server`。
   - **Working directory**：解压目录，也就是其中包含 `alchemy_api_mcp` 文件夹的目录。
4. 在 MCP 服务的环境变量中添加：
   - `ALCHEMY_PRODUCT_API_BASE_URL` = `https://alchemy.aiself.vip`
   - `ALCHEMY_PRODUCT_SESSION_TOKEN` = 你的 Alchemy API 密钥

   值中不要加 `Bearer ` 前缀。不要把密钥放进对话或工具参数；只保存在本机 MCP 配置中。
5. 保存配置并重启 Codex。确认工具列表出现 `alchemy_list_capabilities`，调用它可查看此密钥能使用的 API 范围。

连接自建 Alchemy 服务时，将服务地址改成该服务的 origin。

## Codex 选图工作台

在 Codex 的内置浏览器打开已部署的 Alchemy 服务的 `/codex-workbench`，并使用同一个 Alchemy 账号登录网页和 MCP。选 V2 案例或 LAB 风格后，可在会话里请 Codex 读取或修改当前草稿。打开页面的 Site tools 可查看此页提供的操作。用工作台的「生成图片」提交，页面会自动跟踪并显示原任务结果。

要在会话中交付，开始时告诉 Codex「跟踪这次生成，完成后显示预览并附原图」。Codex 可读取页面的 `alchemy_read_result` 得到输出 ID，再调用独立 MCP 的 `alchemy_read_workbench_image`。`preview` 返回图片块，`original` 返回原始文件资源。若在 MCP 中设置 `ALCHEMY_WORKBENCH_OUTPUT_DIR` 为一个已存在且可写的本机绝对目录，原图会原样保存并返回本地路径，Codex 可把该文件附在回复里。工作台的「下载原图」也使用同一输出 ID。

## 费用与密钥

- MCP 调用 Alchemy 已有认证 API；账户归属、权限、审核、存储和计费仍由 Alchemy 服务端处理。
- 查询类工具不会创建生图任务。生成等写操作可能修改账户数据；生图会按账户原有规则计费。
- 写操作超时且结果不确定时，先查询已有项目或任务，不要直接重复提交。
- 不再使用时，可在 Alchemy 的 API 与 MCP 页面停用密钥。
