# Doc180 — V3 Professional Character Card Frontend Workspace

## 1. Decision

Professional Mode is a visual-asset workspace, not a decorated version of the
Standard Mode composer. Standard Mode keeps its current home, project creation,
prompt, reference and result flow unchanged. Professional Mode gets its own
asset-library and project surfaces while reusing the same shared runtime
contracts.

The first professional asset is a People Visual Asset containing one resumable
Character Card. The browser never writes prompt prose, candidate IDs, review
decisions or provider parameters. It only starts an explicitly named shared
stage and renders the safe public state returned by the server.

## 2. Beginner-facing information architecture

The V3 title switch opens two choices:

- 基础版：the existing Standard Mode home and project flow;
- 专业版：a dedicated Visual Asset workspace.

The Professional home is intentionally short:

1. `视觉资产库` — one card with the current asset count and `建立人物资产`;
2. `我的专业项目` — the same project cards as the normal project list;
3. `人物资产角色卡` opens in a modal workspace when an asset is created or
   selected.

The project page visibly shows `选择视觉资产`. This is a binding choice, not
an upload shortcut. A project may later bind multiple compatible asset types;
the first release exposes People assets only and states that limitation in
plain language.

## 3. Character Card layout

The modal uses a stable card grid. Every slot is rendered even when empty, so
the user always knows what is missing and a completed image fills the same
place on refresh.

### Face Identity — 人物脸部基础

Five fixed slots:

- 正面；
- 左/右侧前方；
- 侧面；
- 反侧前方；
- 后脑/背面。

The neutral expression slot is an alias of the active front face and does not
create another generation request.

### Expression Set — 表情组

Four fixed slots:

- 中性；
- 微笑；
- 愤怒；
- 悲伤。

The user does not type expression prompt fragments. The shared Brain decides
the natural expression direction from the asset intent and stage contract.

### Body Silhouette — 身形与全身关系

Three fixed slots:

- 正面全身；
- 侧面全身；
- 背面全身。

The user supplies only a natural-language body fact or chooses “由共享中枢
根据现有资料判断”. Observed full-body evidence, when provided, must be an
authorized ready upload. The browser never turns the facts into a body recipe.

Each slot has four visual states: 空位、处理中、待确认、已完成. Failed or
stale material remains visible as a non-delivery status and never overwrites an
older append-only winner.

## 4. Linear stage behavior

The three modules run in order:

```text
Face Identity → 用户确认启用 → Expression Set → 用户确认启用
→ Body Silhouette → 用户确认启用
```

Each module provides:

- `开始本部分` when its prerequisites are satisfied;
- `重新生成本部分` after a blocked/stale result;
- a progress bar and plain-language current step;
- a module-level confirmation button after shared review passes;
- fixed slot cards updated from the latest server projection.

`一键按顺序准备` starts the same three stage calls in order. It does not
silently activate anything: it pauses at each required user confirmation and
continues automatically after the user confirms. Refreshing or closing the
modal never loses state; reopening reads the asset again.

The Face Identity stage uses the existing shared Character Card face route,
which reuses the existing Anchor Pack/Brain/Provider/Vision path. Expression
and Body stages use the existing Character Card routes. No new Provider,
Brain, review, retry, selector or storage path is introduced.

## 5. Safe public data needed by the card

The existing public visual-asset projection remains free of prompts, paths,
provider details, raw review payloads and source credentials. For a reviewed
or active slot only, it may add a server-generated `preview_url` and
`download_url` for the existing V3 output endpoint. Empty, preparing, blocked
and stale slots contain no media URL. This allows the UI to fill a fixed slot
without exposing internal prompt or provider data.

## 6. Compatibility and isolation

- Standard Mode markup, state, request payloads and behavior are unchanged.
- General, E-Commerce and Photography do not receive Character Card fields.
- Historical assets without Character Card data remain readable and show the
  current Face Identity/three-view summary only.
- A missing shared Character Card host is rendered as “专业建模服务暂不可用”
  with a retry action; it never falls back to an offline generator or General.
- All stage calls are idempotent at the UI level through busy guards and use
  the server's append-only lifecycle as the authority.

## 7. Acceptance matrix

The implementation is accepted only when the following are true:

1. Standard Mode snapshot/contracts are unchanged.
2. Professional home opens the library card and project list without exposing
   Standard Mode controls as the asset workflow.
3. A newly created People asset renders all 12 fixed slots empty; generated
   slots fill in place and empty slots remain visible.
4. Face → Expression → Body dependency gates are visible and enforced.
5. A stage can be run independently, retried after a block, or started through
   the sequential one-button flow; no duplicate request is sent while busy.
6. Refresh/reopen preserves module status, slot media and the next action.
7. Body input uses natural language or shared inference only; no local prompt
   or keyword recipe is emitted.
8. Shared-host unavailable, malformed responses and provider-independent
   upstream holds are shown as human-readable blocked states.
9. Project asset selection remains explicit and is visible in Professional
   project pages; Standard projects do not acquire this panel.

The real Provider/Vision character-card acceptance remains a separate gate.
This document only makes the frontend a truthful, usable client of that gate.
