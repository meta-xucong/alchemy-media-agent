# Systemd Deployment Templates

These files are VPS templates for running Custom Media Agent 2.0 as independent Linux services.

Recommended service split:

1. `alchemy-v2-api.service`: HTTP API on `127.0.0.1:8020`.
2. `alchemy-v2-worker.service`: persistent creative/revision task worker.
3. `alchemy-v2-sync-worker.service`: periodic ResourceProvider sync worker.

Install shape:

```bash
sudo mkdir -p /etc/alchemy /var/lib/alchemy/v2
sudo cp deploy/systemd/alchemy-v2.env.example /etc/alchemy/alchemy-v2.env
sudo scripts/vps_prepare_v2_runtime.sh \
  --release /opt/alchemy-media-agent \
  --release-link /opt/alchemy-media-agent \
  --install-systemd
sudo systemctl enable --now alchemy-v2-api alchemy-v2-worker alchemy-v2-sync-worker
```

Edit `/etc/alchemy/alchemy-v2.env` before starting production. In particular, configure domain CORS, image provider credentials, Claude Code access, and any Kimi/sub2api timeout or failover settings outside this app.

The templates assume:

1. Active release link: `/opt/alchemy-media-agent`.
2. Python venv: `/opt/alchemy-media-agent/custom_media_agent_2_0/.venv`.
3. Linux user/group: `alchemy`.
4. Reverse proxy maps `/api/v2/*` to `http://127.0.0.1:8020/api/v2/*`.

The service templates use the active release link and run
`v2_runtime_guard.py` before every V2 process start. Install the templates
through `scripts/vps_prepare_v2_runtime.sh --install-systemd`; do not point
systemd at an immutable historical release directory or copy the template
files directly, because `__ALCHEMY_RELEASE_LINK__` must be rendered first.
