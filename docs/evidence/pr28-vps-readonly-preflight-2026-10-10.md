# PR #28 VPS read-only preflight evidence

- Captured: 2026-10-10 UTC
- Target: Alchemy Media Agent VPS, via the configured SSH host wrapper
- Purpose: determine the active release and whether the persistent SQLite repositories from PR #28 are already present before planning a cutover.
- Operations: read-only `docker inspect`, `docker ps`, `git rev-parse`, `find` over SQLite filenames, `du`, `free`, `df`, `systemctl is-active`, file SHA-256 comparison, and loopback health GETs.
- Data handling: no image, prompt, credential, or user record content was read or included; no file, database, service, container, or release was changed.

## Sanitized observations

```text
release HEAD:       3915b24d0cdab6cc626ad5a7d07c0839e5239064
release origin/main:3915b24d0cdab6cc626ad5a7d07c0839e5239064
V1 container:       Up; restart count 0; image created 2026-10-08T14:10:59Z
V1 main.py hash:    container matches active release file
V1 /healthz:        HTTP 200
V2 /api/v2/health:  HTTP 200
V2 API unit:        active
V2 sync worker:     active
V2 task worker:     active
host RAM:           total 1.9 GiB; available 821 MiB
root filesystem:   total 30 GiB; available 6.4 GiB
V1 media storage:   2.8 GiB
V2 image storage:   2.2 GiB
V1 api_access DB:   /var/lib/alchemy/v1/media_storage/api_access/keys.sqlite3; 28,672 bytes
V2 task queue DB:   /var/lib/alchemy/v2/task_queue.sqlite3; 137,433,088 bytes
repository.sqlite3: not found under /var/lib/alchemy
container memory:  444,723,200 bytes at capture
container limits:  memory.max=max; cpu.max=max 100000
```

V1 media storage is mounted read-write into the container. The V2 storage bind mounted into the V1 container is read-only; this does not establish the permissions seen by separate V2 systemd processes. The task queue database is on its separately configured persistent path. V2 unit activity was checked, but the active V2 processes' resolved code SHA was not verified. The release is the pre-PR version; PR #28 is not deployed.

## Interpretation and limits

The health responses establish that the current services answer requests; they are not load, restart-recovery, memory-trend, or performance acceptance. The absent repository databases mean the new durable repository cutover has not happened. The V1 and V2 repository state at the active release is memory-backed, while the V2 task queue and image/history files have their own existing durable stores.

No complete admin snapshot/export route was found for all V1 sessions/jobs/assets/outputs and V2 repository/Lab session state. A disk-only backup cannot be treated as a complete snapshot of live RAM state. Do not restart or deploy the persistence change until a read-only streaming export, isolated dry-run importer, entity/ID/owner/reference reconciliation, and reviewed rollback procedure exist.
