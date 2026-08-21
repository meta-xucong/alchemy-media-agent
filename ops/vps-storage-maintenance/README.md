# V3 Storage Maintenance

V3 storage is maintained separately from V2 storage and from Sub2API. The
maintenance tool is deliberately conservative because a record that is not
visible in the current project list may still be needed for replay, MCP
handoff recovery, review, or audit.

## Safety model

`ops/vps-storage-maintenance/v3_storage_maintenance.py` scans project records, history, Job records,
output records, and MCP handoffs before proposing anything. It may propose:

- expired files in `provider_reference_cache` and `share_cache`;
- old, unreferenced Jobs explicitly produced by a mock/test provider;
- old, unreferenced output directories explicitly produced by a mock/test provider.

It never automatically removes projects, uploads, real-provider outputs,
history, or pending/unknown MCP handoffs. Unreadable records block related
automatic deletion by making their references unknown.

## Manual validation

```bash
python3 ops/vps-storage-maintenance/v3_storage_maintenance.py \
  --root /var/lib/alchemy/v1/media_storage \
  --retention-days 30
```

The command is read-only by default. `--apply` moves only listed candidates to
`.v3_maintenance_trash/<timestamp>` and writes a manifest. This is a reversible
quarantine, not an immediate delete. The daily VPS timer purges quarantine
batches older than 7 days; the first batch therefore remains available for
manual recovery during that observation period.

```bash
python3 ops/vps-storage-maintenance/v3_storage_maintenance.py \
  --root /var/lib/alchemy/v1/media_storage \
  --retention-days 30 --trash-retention-days 7 --purge-trash
```

## VPS scheduling

The checked-in installer is intentionally separate from the application
release. It copies the patch to `/opt/alchemy-media-agent-ops` and installs
only the maintenance units; it does not rebuild or restart Alchemy:

```powershell
$env:POLYMARKET_SSH_PASSPHRASE = '...'
pwsh -File ops/vps-storage-maintenance/install-vps.ps1
```

Install the service and timer only after reviewing one dry-run report:

```bash
install -m 0644 ops/vps-storage-maintenance/systemd/alchemy-v3-storage-maintenance.service /etc/systemd/system/
install -m 0644 ops/vps-storage-maintenance/systemd/alchemy-v3-storage-maintenance.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now alchemy-v3-storage-maintenance.timer
systemctl start alchemy-v3-storage-maintenance.service
```

This directory is an explicitly installed VPS-only patch. It is not imported
by the application and is not invoked by local runs or MCP deployments. It
touches only `/var/lib/alchemy/v1/media_storage`; it does not inspect or
modify V2 storage, Sub2API containers, billing data, or provider credentials.
