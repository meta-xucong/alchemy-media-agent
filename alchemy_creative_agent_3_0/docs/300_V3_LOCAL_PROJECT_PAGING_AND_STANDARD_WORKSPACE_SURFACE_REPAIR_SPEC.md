# Doc300 - V3 Local Project Paging And Standard Workspace Surface Repair

Status: active local repair contract. This document narrows the existing
Doc284 pagination contract and Doc174 Standard/Professional workspace
contract. It does not change Brain, Provider, Review, Retry, account
ownership, or VPS behavior.

## 1. Intended behavior

1. A project list page is only a page. The browser must make the server
   `total`, cursor continuation, and remaining-page state understandable; a
   first page of four mobile cards must not look like the account only has
   four projects. A page containing only the other workspace must still show
   the load-more affordance instead of returning an empty terminal state.
2. Standard and Professional project cards are separated by the persisted
   server-owned `metadata.v3_workspace` value. Missing or malformed workspace
   metadata fails closed to Standard.
3. Opening a Standard project must never expose the project visual-asset
   panel. The panel must be hidden during the loading transition as well as
   after the project summary arrives. The CSS projection must preserve the
   semantic `hidden` state even though the shared panel class sets `display`.
   Visual-asset dialogs and binding reads are Professional-only.
4. The mobile and desktop shells use the same workspace truth and restore it
   from the opened project instead of retaining the previous project’s mode.

## 2. Correction model

The observed mismatch had three owners:

| Mismatch | Owning layer | Correction |
| --- | --- | --- |
| A four-card first page looked like the full history | Browser projection | Track and display server pagination state; retain cursor loading |
| Recent-project summaries had no workspace fact | Public summary projection | Add only the safe `v3_workspace` metadata to `ProjectMemorySummary` |
| A Professional panel remained while a Standard project was opening | Frontend state transition | Render the fail-closed panel state whenever view state changes and restore mode from project truth |

The server remains authoritative for account ownership and cursor ordering.
The persisted project workspace remains authoritative for Standard versus
Professional. Browser state is only a projection and may not promote a
missing value to Professional.

## 3. Acceptance gates

- Desktop and mobile preserve cursor pagination and expose a remaining-page
  affordance when `has_more` is true.
- Workspace summaries carry only `metadata.v3_workspace` and classify
  Standard/Professional consistently.
- Standard project entry hides the visual-asset panel before and after the
  summary request; Professional project entry still exposes it.
- Opening a project on mobile restores the project workspace and refreshes the
  project list projection when the workspace toggle changes.
- Focused Doc174/Doc284/frontend and backend tests, JavaScript syntax checks,
  and the adjacent V3 shell tests pass.

## 4. Non-goals

This repair does not increase the page size to hide the pagination boundary,
weaken authenticated ownership filtering, auto-claim legacy ownerless
projects, or add any creative/prompt/provider behavior.
