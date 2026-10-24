# RB15: shared administrator control for product-primary transport

The total target is Bridge-primary image transport for V1, V2, V3 and Lab.
This change connects the existing simple administrator controls, not another
routing button or API/MCP credential bridge. Product transport and acceptance
are verified separately; this document is not a live-provider acceptance receipt.

## Authority and compatibility

The old administrator file lived next to V1's preview ledger. V2 cannot import
V1 or read its database. The product-neutral control file is therefore the sole
new write authority. Its location is ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG; all
product processes must use the same absolute configured path. Tokens remain in
each process's environment and are never written into this JSON.

The existing disabled/enabled/draining mode and profiles govern ordinary primary
routing. Only an explicitly configured codex-image profile enables that route;
fake-only defaults do not silently activate real image generation. There is no
new user-facing toggle. Existing trial controls retain their separate meanings.

On host startup, a valid old admin-settings.json is migrated once if the neutral
file does not exist. A malformed neutral file never falls back to the old enabled
file. Writes are atomic replacements of one control document, not two mirrored
files with independently successful saves.

The Bridge database remains the sole shared queue-capacity authority. Product
transport ledgers are isolated under a neutral state root, not V1's preview or
media storage. Scope changes are refused while any product ledger is pending.
Pausing/disabling stops new admissions only; existing owned units must continue
their same-origin recovery and may not become API-provider fallbacks.

## Verification requirements

Test legacy migration, masked credentials, invalid-file fail-closed behavior,
fake-only isolation, scope-change guards for product pending work, and pause.
Run the original administrator controls suite and browser coverage without
changing card layout or adding technical UI requirements.

## Process packaging and persistent paths

The V1/V3/Lab container copies the neutral transport package alongside its app.
Standalone V2 installs that package separately, without installing/importing V1.
Both Windows setup and the Linux V2 environment preparation must install the
same release's neutral package. This is source preparation, not a deployment.

For multiple interpreters, installed wheels, containers, or different releases,
set the same **absolute** ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG and
ALCHEMY_RENDER_BRIDGE_PRIMARY_STATE_ROOT values for every process. Mount the
neutral directory persistently when using a container; do not rely on container
layers or a package installation directory for durable recovery. Keep this data
outside the versioned checkout and keep each product's subdirectory separate.
For example, an operator may mount /var/lib/alchemy/render-bridge-primary and use
control.json and ledgers beneath it. No secrets are stored in control.json.

This phase does not edit an operator's existing .env, permissions, credentials,
container volumes or running services. Local Windows setup must choose persistent
absolute paths accessible to all authorized local product processes, then enable
the existing administrator controls. A valid enabled environment baseline is
published to the neutral file on host startup when no saved control file exists.

## Post-registration recovery

The host has a bounded five-second maintenance loop for already persisted ACK
and cancellation intents across the four isolated product ledgers. It does not
create tasks, generate images, import results or invoke API-key providers. It
continues when new primary admissions are paused/disabled, because a native
result already saved before an ACK outage must not leave its receipt handshake and retention eligibility
unresolved. The original registration identity is persisted before the ACK call.
Missing credentials or a scope mismatch do not authorize fallback; the intent
remains pending for the operator to restore the original configuration.
