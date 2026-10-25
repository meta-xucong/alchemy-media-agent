# RB21 VPS runtime and durable-state adaptation

## Correction model and scope

The new Bridge adapter is lazy-imported by V2. The ordinary V2 setup already
installs its neutral package, but guarded candidate/activate inline setup did not.
This is a future **new-version update** packaging gap, not evidence that existing
API-only VPS main is broken. Install the package in those existing paths and
reuse the existing runtime guard to import the lazy dependency. No extra
installer, manifest version, source-hash gate, or manual live patch is required.

Local Windows launchers and the base Docker Compose file remain unchanged.
Only the VPS Compose override and VPS systemd templates supply production
persistent paths. No service is deployed/restarted by this development work.

## Persistent paths

Defaults are `/var/lib/alchemy/render-bridge-primary/control.json` and its
`ledgers` directory. Existing V1 and V2 environment files may supply matching
custom absolute paths outside the active/candidate release trees. The control
directory must be dedicated to Bridge, because atomic administrator updates
require a directory bind. Unrelated files (for example a Veyra environment file)
make preflight reject the mount rather than exposing them inside the container. The read-only
preflight accepts these paths and rejects disagreement or checkout-relative
storage instead of overwriting environment files. Credentials, authentication,
pricing, source identity and workspace are not migrated or generated. Existing
control JSON is checked for its current schema/profile/mode, HTTPS origin and
environment endpoint/workspace agreement; a missing control is allowed for
disabled/API-only first deployment.

The VPS-only Compose override mounts the effective control directory and ledger
root at the same absolute paths used by V2. Systemd defaults are overridden by
its existing EnvironmentFile. Before public reopening, the existing activation
gate also compares actual Docker bind mounts/container environment and all three
V2 process environments against these effective paths. Deployment provisions missing directories only;
existing modes/ownership are not changed. Lack of runtime write access stops
cutover. Existing checkout/container-local journals require explicit
reconciliation, never implicit migration, deletion or a new execution identity.

## Cutover/backup contract

The existing work inventory additionally inspects neutral unit ledgers, V2
native direct jobs, and frozen request records. Unknown/create-uncertain,
api-ready/not-yet-executed, running, artifact-awaiting-ACK and pending cancellation
remain active. Completed API and ACKed units do not block forever. Frozen job
and task aliases are deduplicated and matched to native terminal job records;
unit IDs with `:index` are not confused with parent job IDs. Result cache files
are not interpreted as task records. Malformed authoritative records fail closed.

Existing database snapshots now include the durable neutral ledgers; control
and V2 frozen/result JSON files are included in source backups and size estimates.
Pre-writer restore includes their allowed roots. The existing forward-recovery
rule after new writers start remains unchanged; never roll old main over pending
Bridge work or delete a journal to make an upgrade pass.

## Validation and limits

Tests exercise matching custom/default paths, conflicts, nonpersistent paths,
lazy dependency probing, workflow installation wiring, direct/frozen/unknown work,
terminal API/ACK, and pending/reconciled cancel. Existing cutover and runtime
regressions must remain green. Workflow shell bodies are syntax checked.

These are offline code/configuration checks. Real VPS environment/mounts,
permissions, HTTPS reachability, Windows process recovery, Veyra identity and
server-side billing still require controlled deployment acceptance. A successful
runtime import or health response does not certify real CLI generation.
