# VPS SSH Key Recovery Runbook

本文记录 `alchemy-media-agent` VPS 的 SSH key 失效排查与 VNC 恢复流程。

## 2026-06-28 事故结论

现象：

- 本地 `D:\AI\SSH\VPS_SSH_KEY\hosts\alchemy-media-agent` 的加密私钥可以被口令解密。
- SSH 客户端明确向服务器提交了原 key：
  `SHA256:4upNcf2LEK8powCFH37ySSLSA3mgYPCbzfMF4/cYjrY`
- 服务器返回 `Permission denied (publickey)`。
- GitHub Actions `Deploy VPS` 也同样在 SSH 阶段失败。

根因：

- VPS 上 `cloud-init` 使用 `DataSourceNoCloud [seed=/dev/sr0]` 重新跑了一次实例初始化。
- `cloud-init` 在 `2026-06-27 23:25:59 CST` 重新生成了 `/etc/ssh/ssh_host_*`，因此服务器 host key 指纹发生变化。
- `cloud-init` 日志显示它读取 `/root/.ssh/authorized_keys` 后写回空内容：
  `Writing to /root/.ssh/authorized_keys - wb: [600] 0 bytes`
- 当前 cloud-config 里还包含：
  `rm -f /root/.ssh/authorized_keys`

因此不是客户端私钥损坏，也不是口令错误，而是 VPS 侧 `authorized_keys` 被 cloud-init/实例初始化清空。

## 原 key 信息

原 key 的服务器端公钥如下，可以通过 VNC 写回：

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIhsATsRGuwntbZM6/8rfjF+cfc2Vd0qgWgqW11mK2xz root@103.23.148.225
```

指纹：

```text
SHA256:4upNcf2LEK8powCFH37ySSLSA3mgYPCbzfMF4/cYjrY
```

## VNC 恢复原 key

VNC 控制台不适合粘贴长串命令，建议分段执行。

第 1 段，关闭 bash 历史展开，避免 `!` 触发 `unrecognized history modifier`：

```bash
set +H
```

第 2 段，准备 SSH 目录：

```bash
mkdir -p /root/.ssh && chmod 700 /root/.ssh
```

第 3 段，写回原公钥：

```bash
echo ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIhsATsRGuwntbZM6/8rfjF+cfc2Vd0qgWgqW11mK2xz root@103.23.148.225 >> /root/.ssh/authorized_keys
```

第 4 段，修权限并确认：

```bash
chmod 600 /root/.ssh/authorized_keys && echo ok
```

本地验证：

```powershell
$p = '<统一口令>'
& 'D:\AI\SSH\VPS_SSH_KEY\hosts\alchemy-media-agent\connect.ps1' -Passphrase $p -ExtraSshArgs @('-o','BatchMode=yes','-o','IdentitiesOnly=yes') -RemoteCommand 'hostname; date -Is; whoami'
```

成功时应看到 `root` 和主机名 `ser467022953094`。

## 如果原 key 还不能登录

1. 在本地生成临时 key，不要让 VNC 复制私钥：

```powershell
$keyPath = Join-Path $env:TEMP 'alchemy_codex_deploy_ed25519'
$empty = ''
ssh-keygen -t ed25519 -f $keyPath -N $empty -C 'codex-deploy-temp' -q
Get-Content "$keyPath.pub"
```

2. 在 VNC 上只粘贴临时公钥到 `/root/.ssh/authorized_keys`。

3. 本地确认 `ssh -vv` 出现：

```text
Server accepts key
Authenticated to 103.23.148.225
```

4. 完成部署或修复后，立刻删除临时公钥：

```bash
sed -i '/codex-deploy-temp/d' /root/.ssh/authorized_keys
rm -f /root/.ssh/codex_temp_key /root/.ssh/codex_temp_key.pub
```

## fail2ban / 防火墙处理

多次错误 key 尝试可能导致 SSH 端口从外部表现为 timeout。VNC 中可临时解封：

```bash
systemctl stop fail2ban 2>/dev/null || true
fail2ban-client unban --all 2>/dev/null || true
ufw allow 11506/tcp 2>/dev/null || true
systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || true
echo ok
```

修复完成后恢复 fail2ban：

```bash
systemctl enable --now fail2ban
```

## 事后检查

登录 VPS 后检查：

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
stat /root/.ssh /root/.ssh/authorized_keys /etc/ssh/ssh_host_ed25519_key
journalctl -u ssh -u sshd --since '2026-06-23' --no-pager | tail -160
grep -Ein 'authorized|ssh|host key|ssh_deletekeys|ssh_genkeytypes' /var/log/cloud-init.log | tail -120
cloud-init status --long
```

这次事故的关键证据是：

```text
DataSourceNoCloud [seed=/dev/sr0]
Writing to /root/.ssh/authorized_keys - wb: [600] 0 bytes
```

## GitHub Actions 注意事项

- `Deploy VPS` 使用仓库 secret `VPS_SSH_KEY_B64` 或 `VPS_SSH_KEY`。
- 临时部署 key 可以短期写入 `VPS_SSH_KEY_B64`，但部署完成后必须删除该临时 secret。
- 正常状态下应依赖原 `VPS_SSH_KEY`，并保证 VPS 的 `/root/.ssh/authorized_keys` 包含原公钥。
