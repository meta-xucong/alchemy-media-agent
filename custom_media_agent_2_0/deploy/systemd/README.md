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
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now alchemy-v2-api alchemy-v2-worker alchemy-v2-sync-worker
```

Edit `/etc/alchemy/alchemy-v2.env` before starting production. In particular, configure domain CORS, image provider credentials, Claude Code access, and any Kimi/sub2api timeout or failover settings outside this app.

The templates assume:

1. Project checkout: `/opt/alchemy/AlchemyOS`.
2. Python venv: `/opt/alchemy/AlchemyOS/custom_media_agent_2_0/.venv`.
3. Linux user/group: `alchemy`.
4. Reverse proxy maps `/api/v2/*` to `http://127.0.0.1:8020/api/v2/*`.
