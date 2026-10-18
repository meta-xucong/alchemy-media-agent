# Kimi-First Backup Order Amendment

Status: current user-directed amendment to the frozen unified-gateway contract.

## Required route order

For V1, V2, V3, and LAB text planning, preserve Claude Sonnet 5.5 as primary
and use this built-in ordered backup chain:

1. `kimi-k3`
2. `gpt-6.1-sol`

An explicitly configured additional fallback may remain between Kimi and GPT,
but must not displace Kimi as the first backup or GPT as the final built-in
route. The same unified gateway key is used for every text candidate.

## Automatic transition

On a failover-eligible primary failure, attempt Kimi automatically. If Kimi
also fails with a failover-eligible route/model failure, attempt GPT within the
existing bounded logical deadline. Policy refusals, shared-key authentication
failures, malformed or unscoped permission errors, and exhausted deadlines
remain terminal according to the owning product's existing failover contract.
V2 must allow the whole default two-model backup chain in each eligible stage,
and retry eligible Kimi timeout/connection failures through to GPT.

## Product boundaries

- V1 and LAB use their existing ordered candidate loops.
- V2 uses its existing Claude Code/OpenAI-compatible fallback queue and stage
  timeout reserve divided across remaining candidates; this change does not
  bypass Claude Code continuation rules.
- V3 retries the same frozen Brain request through each candidate in order and
  retains its existing refusal, shared-key, and deadline gates.
- The image-generation provider is unchanged.

## Acceptance evidence

Focused tests must prove the order `Claude -> Kimi -> GPT`, successful Kimi
short-circuiting, GPT use after eligible Kimi timeout/connection failures, and unchanged terminal
behavior for non-failover failures. Real provider calls are not required for
this configuration-order amendment.
