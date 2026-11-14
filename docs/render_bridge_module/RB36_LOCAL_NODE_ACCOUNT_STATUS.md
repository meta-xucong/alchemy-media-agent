# RB36: Local Node Alchemy Account Status

## Purpose

Show the currently bound Alchemy account on the local RenderBridge Node Agent
page (`127.0.0.1:8766`) without duplicating ownership in Bridge or exposing the
account on the anonymous fleet dashboard.

## Source of truth and trust boundary

`node_reward_node_bindings` remains authoritative. The internal read-only route
`POST /api/internal/render-bridge/node-account-binding` accepts only a signed
`pool_id/node_id/executor_instance` tuple from Bridge. It requires a timestamp
within 120 seconds and a constant-time HMAC comparison. The request signature
uses a key derived from the existing Alchemy/Bridge reward-read secret under the
separate context `alchemy-node-binding-status-key-v1`; neither the Node bearer
nor the raw reward-read secret is sent in this request.

The response is intentionally limited to `available`, `bound`, and
`account_user_id`. It contains no email, display name, image/reward history, or
other account data. The API endpoint is excluded from the public schema and
returns `Cache-Control: no-store`.

## Behavior

- Bridge derives the full node identity only after authenticating the Node
  bearer on `GET /bridge/node/v2/status`.
- Bridge queries Alchemy for that exact tuple and adds only the validated
  account-binding projection to the authenticated self-status response.
- The loopback page displays `已绑定 Alchemy 账号 #<id>`, `未绑定`, or a
  temporary unavailable message. It continues to render node execution metrics
  if the Alchemy lookup fails.
- Unbind removes the active mapping from the lookup immediately; historical
  reward records are not surfaced by this endpoint.
- `/bridge/status/v1` stays anonymous and redacted.

## Acceptance

Verify signed active and unbound lookups; reject invalid signatures, stale
timestamps, duplicate/malformed headers, extra identity fields, and invalid
identifiers. Verify the self-status API includes the projection while the public
fleet API does not. Verify the loopback UI renders the account reference and
continues to show node status during an Alchemy outage. Deploy Alchemy before
the Bridge caller; no account API token is added to the Node Agent.
