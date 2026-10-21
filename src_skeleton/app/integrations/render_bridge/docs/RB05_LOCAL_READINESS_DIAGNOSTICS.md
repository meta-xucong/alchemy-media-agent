> RB06 supersedes the native fake-only implementation limit below. Defaults remain fake-only; explicitly configured real profiles now negotiate typed options and stay development/review-only. See [RB06](RB06_REAL_PROFILE_OPTIONS.md).

# RB05: local-readiness doctor and read-only diagnostics

## Scope and authority

Continue local Alchemy `2da931dc` (tree `fa90f25a10bf43ae89e71c374a5f6dacb7b3ae91`),
equivalent to published feature `e43d164b`. Bridge starts from local `be9fe31`
(tree `e717e60288861503e18b5f53e82d0cc12041d603`), equivalent to published
`feat/phase1-bridge-contracts` `c8b16a77`. Main branches are not merged.

The missing feature is an operator-visible readiness explanation, not another
rendering implementation. Distinguish server configuration, Agent configuration,
CLI version/protocol observations, unconfirmed login, operator acceptance
declarations, and the actual request parameter contract.

1. Bridge owns a shared profile descriptor, strict Agent configuration, and a
   read-only doctor CLI. Defaults are local configuration reads only. Optional
   CLI probing runs only isolated version/help commands, never login or image
   generation. No credential files, database, configuration, or acceptance
   markers are read/written by the diagnostic path.
2. Alchemy owns an optional diagnostics page. Loading it reads only Alchemy's
   configuration. An explicit button queries the configured Bridge capability
   endpoint. No URL discovery or caller-supplied remote destination is added.
3. A user may import a bounded versioned doctor JSON report. The server validates
   and projects a small schema, then returns it without storing it. It is
   unverified, user-supplied evidence, never profile authorization or proof of
   current CLI login/capability. A server cannot inspect another machine's CLI.

The existing native entry remains **fake-image only** and review-only. Real
native routing and its quality/format/fidelity parameter contract are still
missing code; login alone cannot enable them. The Bridge's existing width,
height, and seed transport does not imply structured real-tool support for
quality, output format, or input fidelity. No default business, billing, review,
selection, delivery, pairing, PostgreSQL or deployment changes are included.

## Compatibility and acceptance

Additive capability metadata has its own version and does not change existing
task/profile revisions. Older v1 servers without descriptors remain readable,
with parameter information explicitly unavailable. Unsupported major versions
are not inferred. Unknown fields are ignored and not reflected; diagnostics
never change a rendering gate.

Doctor JSON has a stable schema and exit codes; fake/config checks passing do
not mean real generation is verified. Validate malformed configurations,
mocked CLI observations, no-side-effect defaults, report limits/provenance,
capability compatibility, explicit HTTP checks, and the optional page's key
interactions. Run focused old-path regression, one independent review and stop.
No real account, provider, production deployment or local capability acceptance
is part of this milestone. Local Chromium is restricted in the cloud; collect
the intercepted browser tests and use the existing feature CI for actual clicks.

## Acceptance receipt: 2026-10-20

Functional Alchemy commit `a5ce8e5088ebca75ba90db8a08f73ff7ba3a7b42`, tree
`b85eb4f2d3db5f3b3d5459c4f20055e638892680`; companion Bridge commit
`5c157ff91127b8a39dd749f3a282b20b4e60bd69`, tree
`0ccdec5dbffe801d5774f35f8463d89f289aba81`. Later receipt-only edits do not alter
the verified runtime paths.

- Alchemy focused contracts and key original-path regressions: **204 passed**,
  including 18 new diagnostic tests. The same command as RB04 was used with
  fresh isolated mock-provider storage. Evidence:
  `alchemy-media-agent-cloud-dev/logs/bridge-doctor-contracts.{log,xml}`.
- Bridge: **123 unittest cases passed**, including 15 new doctor/config/descriptor
  tests. Compileall, contract export and whitespace checks passed; existing API
  and task JSON schemas did not change. Tests use mock CLI version/help, not a
  real local Codex probe.
- Independent scoped review found no blocker. Actual doctor JSON for fake,
  Codex, manual, combined and invalid configuration passed Alchemy's schema;
  all three actual profile descriptors projected without changing known fields.
- Ten intercepted Chromium tests collect successfully (previous three plus
  seven diagnostic cases). JavaScript syntax passed. Local Chromium was not
  retried after the prior OS restriction. The existing feature/manual CI includes
  the new contract glob and all ten browser cases; collection is not a browser
  or CI pass.

Actual HTTP acceptance used the standalone Bridge runtime and the full Alchemy
host, not a MockTransport server. Before Bridge started, Alchemy's local-only
diagnostic endpoint returned configuration successfully. After startup, direct
and proxied capability reads agreed for all three profiles. The real doctor
command, with all profiles configured but Codex disabled/model blank/acceptance
flags false, returned exit 1 and `attention`, with login and real generation
unverified. It created no runtime storage or home entries and changed no config.

The generated JSON was imported and re-imported through real HTTP. Each response
retained `source=user_imported_local_report`, `verified_by_server=false` and
`authorization_effect=none`. Unsupported report version returned 422; an
oversized report returned 413. The diagnostic HTML/JS/CSS returned 200. Page
retrieval is not browser rendering or interaction acceptance.

Before and after the diagnostic calls, Bridge tasks, attempts, inputs, receipts,
acknowledgments, claims, uploads and dispatch entries were all zero. Alchemy's
module jobs, inputs and receipts also remained zero; no native store or usage
record was created. Configuration and source hashes were unchanged during the
run, and both services stopped. No renderer, plan, review or accepted ack was
needed to validate this read-only milestone.

Reproducible harness and evidence remain outside source Git:
`alchemy-media-agent-cloud-dev/bridge-doctor-joint-check/`;
successful run `run-20261020-221601-2/report-verified.json`. Optional syscall
tracing was unavailable for both doctor and Bridge; earlier tracing wording is
corrected in that report while original attempts remain preserved. The final
successful run used the ordinary authorized runtime command. Its evidence is
actual CLI/HTTP results, read-only ledger counts and hashes, not packet/syscall
tracing. Offline tests and code inspection verify the default no-execution path.

The six unrelated baseline fixture/string failures described in RB01 remain
outside this milestone and were not re-expanded or repaired. This is not a
whole-repository-green claim. Real Codex/Midjourney capability, account login,
native real-profile adaptation, real billing, browser clicks and deployment are
not newly accepted by these diagnostics.
