final result: passed

# Mobile H5 Design QA

Date: 2026-06-07

## Reference

- Layout reference: option 1, mobile-first vertical workflow.
- Visual-language reference: option 3, Gallery Ritual.
- Functional reference: existing desktop V1/V2/video application.
- Implemented URL: `http://127.0.0.1:8017/h5`

## Scope

This QA covers the independent mobile H5 surface only. The existing desktop page remains mounted at `/` and keeps using `/static/*`; the H5 page is served from `/h5` and `/mobile` and uses `/mobile-static/*`.

## Checks

- Layout: passed. The H5 uses a mobile-first vertical workflow while preserving the desktop application's functional sections.
- Functional parity: passed. V1 includes workbench, basic controls, advanced image assets, output gallery, revision, history, model/API, and events. V2 includes case gallery, search, facets, Agent studio, V2-native uploads, output reasoning, V2 history, external provider status, V2 image model cards, Claude Code brain card, and advanced scheduling. Video demo is also present.
- Progressive disclosure: passed. Non-essential controls are gathered into one `高级` entry per mode. V1 advanced contains parameters, assets, revision, model/API, and events. V2 advanced contains assets, ratio/template controls, Agent output details, Provider, and model/kernel controls. V1 and V2 history are standalone sections outside `高级`.
- Visual language: passed. The UI now follows option 3's Gallery Ritual language more closely: near-white canvas, spaced serif brand lockup, underline tab navigation, thin dividers, low-saturation sage active states, lightweight outlined secondary buttons, and sage pill primary actions.
- Mobile viewport: passed. Verified at 390 x 844. No horizontal overflow; page width fits the viewport.
- Interaction: passed. V1/V2/video switch works; V2 templates load; V1 and V2 functional nodes are present; model controls, upload controls, revision/history controls, and provider controls are mounted.
- Independence: passed. H5 loads `mobile-static/mobile.js` and does not load desktop `static/app.js`. Showcase images are also served from `/mobile-static/showcase`.
- Asset display: passed. Uploaded asset preview uses `background-size: contain`, so images preserve full content inside the card.
- Backend wiring: passed. H5 keeps V1 calls on `/v1/*`; V2 calls go to the V2 API base.

## Remaining P3 Polish

- The final mini-program shell may later need native safe-area tuning per host container.
