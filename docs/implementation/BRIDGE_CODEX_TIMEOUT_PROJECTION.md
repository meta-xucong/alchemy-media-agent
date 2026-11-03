# Bridge Codex timeout projection

## Correction model

Bridge is authoritative for the Codex execution deadline: one 600-second
budget spans app-server initialization and the image turn. On timeout it
terminates and reaps the local app-server process, then reports
`codex_turn_timed_out` as terminal failure for the same task and attempt. The
user accepts that upstream work may still finish and a later generation may
duplicate it. Bridge releases its local slot after process exit and retries
terminal reporting in the background. The server releases its slot when it
confirms the terminal-failure evidence. Generic unknown states
and unconfirmed local process exit remain occupied and require reconciliation.
Alchemy shows the timeout as terminal and does not auto-route it to the API.

The previous projection lost this information: `action_required_detail` was
filtered by Alchemy's curated attention map, and the V3 outer call could expire
before Bridge's 600-second Codex timeout. Users therefore saw a generic wait
state even though Bridge had stopped its local session.

## Minimal correction

1. Add the Bridge timeout and overdue-reconciliation codes to Alchemy's curated
   message map. Do not forward arbitrary Bridge text.
2. Carry only the allowlisted reason code through the existing primary
   transport projection. V1/Lab, V2 and V3 use their existing status surfaces
   to show the same-task reconciliation message.
3. When V3 Bridge is enabled, give its outer provider call and poll budget
   enough time to receive and persist Bridge's timeout result.
4. Convert only the specific 600-second execution timeout, after successful local
   process reaping, into terminal evidence for the same attempt. Do not infer
   this outcome from generic `execution_unknown` or overdue lease status.
5. Mark the Alchemy V1/Lab and V2 product job terminal-failed for the explicit
   timeout and overdue-reconciliation codes. Bridge frees the slot for a
   confirmed timeout terminal failure; an overdue unknown remains occupied.

## Acceptance

- A timeout reason reaches desktop/mobile V1, Lab, V2 and V3 through curated
  text; arbitrary remote message text is not exposed.
- V1/Lab and V2 stop presenting the product job as actively generating after
  the Bridge timeout. Confirmed timeout releases the Bridge physical slot;
  generic unknown and overdue states remain held.
- V3 outer and polling budgets cover the Bridge timeout.
- The 600-second timeout stays on the original Bridge route, terminalizes only
  after local process exit, warns that upstream may still finish, and does not
  invoke the API provider.
