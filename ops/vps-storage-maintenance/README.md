# V3 Storage Maintenance

V3 storage is maintained separately from V2 storage and from Sub2API. The
maintenance tool is deliberately conservative because a record that is not
visible in the current project list may still be needed for replay, MCP
handoff recovery, review, or audit.

## Safety model

`ops/vps-storage-maintenance/v3_storage_maintenance.py` scans project records, history, Job records,
output records, and MCP handoffs before proposing anything. It may propose or expire:

- expired files in `provider_reference_cache` and `share_cache`;
- old, unreferenced Jobs explicitly produced by a mock/test provider;
- old, unreferenced output directories explicitly produced by a mock/test provider.
- terminal `failed`, `blocked`, or `not_found` Job records and their associated
  output directories after seven days from their last update.

It never automatically removes project records, uploads, successful deliveries,
history, or pending/unknown MCP handoffs. Failure cleanup uses the existing
terminal status and last-update timestamp only; it does not inspect prompts,
filenames, providers, or image contents. Unreadable records are left alone.

## Manual validation

```bash
python3 ops/vps-storage-maintenance/v3_storage_maintenance.py \
  --root /var/lib/alchemy/v1/media_storage \
  --retention-days 30
```

The command is read-only by default. `--apply` moves only listed candidates to
`.v3_maintenance_trash/<timestamp>` and writes a manifest. Expired terminal
failures are removed directly after their seven-day user-visible window;
cache/mock cleanup remains reversible quarantine. The VPS timer runs every
Sunday at 04:00 and purges old quarantine batches.

```bash
python3 ops/vps-storage-maintenance/v3_storage_maintenance.py \
  --root /var/lib/alchemy/v1/media_storage \
  --retention-days 30 --failure-retention-days 7 --trash-retention-days 7 --purge-trash
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
